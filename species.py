# species.py
#
# Copyright (C) 2026 James Petersen <m@jamespetersen.ca>
# Licensed under MIT. See LICENSE

from collections.abc import Mapping, Sequence, Set
from typing import TYPE_CHECKING, Tuple

from BaseClasses import Region

from .locations import PokemonHgssLocation
from .regions import is_region_enabled
from .options import Version

from .data.encounters import encounters as encounterdata, encounter_types, EncounterSlot
from .data.regions import regions as regiondata
from .data.species import species as speciesdata, having_two_level_evos, expand_set_via_evolutions, affected_species
from .data.trainers import trainer_party_supporting_starters

if TYPE_CHECKING:
    from . import PokemonHgssWorld

def randomize_starters(world: "PokemonHgssWorld") -> None:
    if not world.options.randomize_starters:
        world.generated_starters = ("chikorita", "cyndaquil", "totodile")
    elif len(world.options.starter_whitelist.value) > 0:
        selection = sorted(world.options.starter_whitelist.value)
        world.generated_starters = tuple(world.random.sample(selection, k=3)) # type: ignore
    else:
        if world.options.require_two_level_evolution_starters:
            selection_set = having_two_level_evos
        else:
            selection_set = set(speciesdata)
        selection_set -= world.options.starter_blacklist.blacklist()
        world.generated_starters = tuple(world.random.sample(sorted(selection_set), k=3)) # type: ignore
    if world.options.randomize_intro_mon:
        world.generated_marill = world.random.choice(sorted(speciesdata))
    else:
        world.generated_marill = "marill"

def fill_unrandomized_encounters(world: "PokemonHgssWorld") -> None:
    done_encs = set()
    version = world.options.version.value
    acc_mthds = world.options.in_logic_encounters.methods()
    for name, rd in regiondata.items():
        if not is_region_enabled(name, world.options):
            continue
        if rd.encounters is None:
            continue
        done_encs.add(rd.encounters)
        encs = encounterdata[rd.encounters]
        for type in rd.accessible_encounters:
            if (rd.encounters, type) in done_encs:
                continue
            done_encs.add((rd.encounters, type))
            tbl: Sequence[EncounterSlot] = getattr(encs, type)
            if not tbl:
                continue
            if type == "rock_smash" and type not in world.options.in_logic_encounters.methods():
                continue
            for i, slot in enumerate(tbl):
                if not slot.in_logic(version, acc_mthds):
                    continue
                world.generated_encounters[(rd.encounters, type, i)] = slot.species

    # fill OOL encounters
    v = {"hg" if world.options.version == Version.option_heartgold else "ss", None}
    world.ool_encounters = {
        (header, type, i):slot.species
        for header, encs in encounterdata.items()
        for type in encounter_types
        for i, slot in enumerate(getattr(encs, type))
        if (header, type, i) not in world.generated_encounters and slot.version in v
    }

def fill_unrandomized_trainer_parties(world: "PokemonHgssWorld") -> None:
    for name, rd in regiondata.items():
        if not is_region_enabled(name, world.options):
            continue
        for trainer in rd.trainers:
            for i, slot in enumerate(trainer_party_supporting_starters(trainer)):
                world.generated_trainer_parties[(trainer, i)] = slot.species

def randomize_encounters(world: "PokemonHgssWorld", req_specs: Set[str]) -> None:
    version = world.options.version
    enc_methds = world.options.in_logic_encounters.methods()
    slots = {(rd.encounters, type, i)
        for name, rd in regiondata.items()
        if is_region_enabled(name, world.options) and rd.encounters is not None
        for type in rd.accessible_encounters
        if type != "rock_smash" or type in world.options.in_logic_encounters.methods()
        for i, slot in enumerate(getattr(encounterdata[rd.encounters], type))
        if slot.in_logic(version, enc_methds)
    }
    slots_s = sorted(slots)
    specs = sorted(req_specs)
    bl = world.options.encounter_species_blacklist.blacklist()
    pokemon_pool = [mon for mon in speciesdata if mon not in bl]
    specs += world.random.choices(pokemon_pool, k=len(slots) - len(specs))
    world.random.shuffle(specs)
    world.generated_encounters.update(zip(slots_s, specs))

    # fill OOL encounters
    enc_pool = list(set(speciesdata) - world.options.encounter_species_blacklist.blacklist())
    v = {"hg" if world.options.version == Version.option_heartgold else "ss", None}
    world.ool_encounters = {
        (header, type, i):world.random.choice(enc_pool)
        for header, encs in encounterdata.items()
        for type in encounter_types
        for i, slot in enumerate(getattr(encs, type))
        if (header, type, i) not in world.generated_encounters and slot.version in v
    }

def randomize_trainer_parties(world: "PokemonHgssWorld") -> None:
    slots = {(trainer, i)
        for name, rd in regiondata.items()
        if is_region_enabled(name, world.options)
        for trainer in rd.trainers
        for i in range(len(trainer_party_supporting_starters(trainer)))
    }
    slots_s = sorted(slots)
    bl = world.options.trainer_party_blacklist.blacklist()
    pokemon_pool = [mon for mon in speciesdata if mon not in bl]
    specs = world.random.choices(pokemon_pool, k=len(slots))
    world.generated_trainer_parties.update(zip(slots_s, specs))

def randomize_trainer_parties_and_encounters(world: "PokemonHgssWorld") -> None:
    rando_encs = bool(world.options.randomize_encounters)
    if rando_encs:
        required_mons = {"oddish", "magikarp", "pichu"}
        chansey_pevo = speciesdata["chansey"].pre_evolution
        if chansey_pevo is not None and chansey_pevo.method in world.options.in_logic_evolution_methods.methods():
            required_mons.add(world.random.choice([chansey_pevo.species, "chansey"]))
        if world.options.version == Version.option_heartgold:
            required_mons |= {"growlithe"}
            marill_pevo = speciesdata["marill"].pre_evolution
            if marill_pevo is not None and marill_pevo.method in world.options.in_logic_evolution_methods.methods():
                required_mons.add(world.random.choice([marill_pevo.species, "marill"]))
            jigglypuff_pevo = speciesdata["jigglypuff"].pre_evolution
            if jigglypuff_pevo is not None and jigglypuff_pevo.method in world.options.in_logic_evolution_methods.methods():
                required_mons.add(world.random.choice([jigglypuff_pevo.species, "jigglypuff"]))
        else:
            required_mons |= {"staryu", "lickitung", "vulpix"}
    if rando_encs and world.options.randomize_trainer_parties:
        randomize_encounters(world, generate_required_encounter_species(world) | required_mons)
        randomize_trainer_parties(world)
    elif rando_encs:
        randomize_encounters(world, generate_required_encounter_species(world) | required_mons)
        fill_unrandomized_trainer_parties(world)
    elif world.options.randomize_trainer_parties:
        fill_unrandomized_encounters(world)
        randomize_trainer_parties(world)
    else:
        fill_unrandomized_encounters(world)
        fill_unrandomized_trainer_parties(world)

def fill_species(world: "PokemonHgssWorld") -> None:
    for (trainer, i), spec in world.generated_trainer_parties.items():
        world.multiworld.get_location(f"{trainer}_party_{i + 1}", world.player).place_locked_item(world.create_event(f"see_mon_{spec}"))
    for (hdr, tbl, i), spec in world.generated_encounters.items():
        world.multiworld.get_location(f"{hdr}_{tbl}_{i + 1}", world.player).place_locked_item(world.create_event(f"mon_{spec}"))

def add_virt_specs(world: "PokemonHgssWorld", regions: Mapping[str, Region]) -> None:
    accessible_mons = expand_set_via_evolutions(
        set(world.generated_encounters.values()),
        world.options.in_logic_evolution_methods.methods(),
    )
    accessible_once_mons = accessible_mons.copy()
    accessible_see_mons = accessible_once_mons | set(world.generated_trainer_parties.values())

    required_dexsanity = world.options.dexsanity_required.blacklist()
    accessible_dexsanity = accessible_once_mons - required_dexsanity

    am_set = accessible_mons
    accessible_mons = sorted(accessible_mons)
    world.accessible_mons = accessible_mons
    accessible_once_mons = sorted(accessible_once_mons)
    world.accessible_once_mons = accessible_once_mons
    accessible_see_mons = sorted(accessible_see_mons)
    world.accessible_see_mons = accessible_see_mons

    reg = regions["virt_specs"]
    for mon in accessible_mons:
        location = PokemonHgssLocation(
            world.player,
            f"mon_map_{mon}",
            "once_mon_event",
            parent=reg,
        )
        location.show_in_spoiler = False
        location.place_locked_item(world.create_event(f"once_mon_{mon}"))
        reg.locations.append(location)
        data = speciesdata[mon]
        if data.pre_evolution is None \
            or data.pre_evolution.species not in am_set \
            or data.pre_evolution.method not in world.options.in_logic_evolution_methods.methods() \
            or data.pre_evolution.other_species is not None and data.pre_evolution.other_species not in am_set:
            continue
        location = PokemonHgssLocation(
            world.player,
            f"evo_to_{mon}",
            "mon_event",
            parent=reg
        )
        location.show_in_spoiler = False
        location.place_locked_item(world.create_event(f"mon_{mon}"))
        reg.locations.append(location)

    for mon in accessible_once_mons:
        location = PokemonHgssLocation(
            world.player,
            f"mon_map_once_{mon}",
            "see_mon_event",
            parent=reg,
        )
        location.show_in_spoiler = False
        location.place_locked_item(world.create_event(f"see_mon_{mon}"))
        reg.locations.append(location)

    if world.slot_data is None:
        if len(world.options.dexsanity_whitelist.blacklist()) > 0:
            possible_dexsanity_mons = sorted(accessible_dexsanity & world.options.dexsanity_whitelist.blacklist())
        else:
            possible_dexsanity_mons = sorted(accessible_dexsanity - world.options.dexsanity_blacklist.blacklist())
        world.dexsanity_specs = world.random.sample(possible_dexsanity_mons, k=world.options.dexsanity.value - len(required_dexsanity)) + sorted(required_dexsanity)

def encounter_slot_label(key: Tuple[str, str, int], in_logic_encounters: Set[str]) -> str:
    (header, table, index) = key
    def nicer_str(s):
        return " ".join(v[:1].upper() + v[1:] for v in s.split("_"))

    map_label = encounterdata[header].label
    map_label += f" ({nicer_str(table)})"
    slot: EncounterSlot = getattr(encounterdata[header], table)[index]
    if slot.accessibility:
        map_label += " (by any of {{{}}})".format(', '.join(nicer_str(v) for v in sorted(set(slot.accessibility) & in_logic_encounters)))
    return map_label

def generate_required_encounter_species(world: "PokemonHgssWorld") -> Set[str]:
    ret = set()
    accessible = set()
    poss_enc = speciesdata.keys() - world.options.encounter_species_blacklist.blacklist()
    not_added = sorted(poss_enc)
    world.random.shuffle(not_added)
    if len(world.options.dexsanity_whitelist.blacklist()) > 0:
        poss_dexs = world.options.dexsanity_whitelist.blacklist()
    else:
        poss_dexs = speciesdata.keys() - world.options.dexsanity_blacklist.blacklist()
    dexsanity_required = world.options.dexsanity_required.blacklist()
    poss_dexs |= dexsanity_required
    dexs = set()
    reqd_dexs = set()

    def add_spec(spec: str) -> None:
        nonlocal ret
        nonlocal accessible
        nonlocal dexs
        nonlocal reqd_dexs

        affected = affected_species[spec]
        ret.add(spec)
        accessible.add(spec)
        if spec in poss_dexs:
            dexs.add(spec)
        if spec in dexsanity_required:
            reqd_dexs.add(spec)

        while True:
            to_add = set()
            for mon in affected:
                data = speciesdata[mon]
                pevo = data.pre_evolution
                if mon in accessible or pevo is None:
                    continue
                if pevo.species not in accessible:
                    continue
                if pevo.method not in world.options.in_logic_evolution_methods.methods():
                    continue
                if pevo.other_species is not None and pevo.other_species not in accessible:
                    continue
                to_add.add(mon)
            if len(to_add) == 0:
                break
            accessible |= to_add
            dexs |= to_add & poss_dexs
            reqd_dexs |= to_add & dexsanity_required
            affected = {v for u in to_add for v in affected_species[u]}

    while len(dexs) < world.options.dexsanity.value or len(reqd_dexs) < len(dexsanity_required):
        spec = not_added.pop()
        add_spec(spec)

    return ret

