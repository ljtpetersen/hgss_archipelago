# __init__.py
#
# Copyright (C) 2026 James Petersen <m@jamespetersen.ca>
# Licensed under MIT. See LICENSE

from collections import defaultdict
from collections.abc import Mapping, MutableMapping, MutableSequence, MutableSet, Sequence
from typing import Any, ClassVar, Optional, Tuple
from BaseClasses import CollectionState, ItemClassification, MultiWorld, Tutorial
import settings
import pkgutil
from worlds.AutoWorld import WebWorld, World

from .client import PokemonHgssClient
from .data import encounters as encounterdata, items as itemdata, rules as ruledata, Hm, species as speciesdata, regions as regiondata, trainers as trainerdata, AP_STRUCT_ADDRESS
from .data.locations import RequiredLocations, LocationTable
from .items import create_item_label_to_code_map, get_item_classification, PokemonHgssItem, get_item_groups
from .locations import PokemonHgssLocation, create_location_label_to_code_map, create_locations
from .options import OPTION_GROUPS, AddHMReader, PokemonHgssOptions, RandomizeTimeItems, Version
from .regions import create_regions
from .rom import generate_output, PokemonHeartgoldPatch, PokemonSoulsilverPatch
from .rules import set_rules, verify_hm_accessibility
from .species import add_virt_specs, encounter_slot_label, fill_species, randomize_starters, randomize_trainer_parties_and_encounters

class PokemonHgssSettings(settings.Group):
    class HeartgoldRomFile(settings.UserFilePath):
        description = "Pokemon HeartGold US ROM File"
        copy_to = "pokeheartgold.nds"
        md5s = PokemonHeartgoldPatch.hashes

    heartgold_rom_file: HeartgoldRomFile = HeartgoldRomFile(HeartgoldRomFile.copy_to)

    class SoulsilverRomFile(settings.UserFilePath):
        description = "Pokemon SoulSilver US ROM File"
        copy_to = "pokesoulsilver.nds"
        md5s = PokemonSoulsilverPatch.hashes

    soulsilver_rom_file: SoulsilverRomFile = SoulsilverRomFile(SoulsilverRomFile.copy_to)

class PokemonHgssWebWorld(WebWorld):
    theme = 'ocean'

    setup_en = Tutorial(
        'Multiworld Setup Guide',
        'A guide to playing Pokémon Platinum with Archipelago',
        'English',
        'setup_en.md',
        'setup/en',
        ['ljtpetersen']
    )

    tutorials = [setup_en]

    option_groups = OPTION_GROUPS

class PokemonHgssWorld(World):
    game = "Pokemon HeartGold and SoulSilver"
    web = PokemonHgssWebWorld()
    topology_present = True

    settings_key = "pokemon_hgss_settings"
    settings: ClassVar[PokemonHgssSettings] # type: ignore

    options_dataclass = PokemonHgssOptions
    options: PokemonHgssOptions # type: ignore

    item_name_to_id = create_item_label_to_code_map()
    location_name_to_id = create_location_label_to_code_map()
    item_name_groups = get_item_groups()

    origin_region_name = "virt_start"

    required_locations: RequiredLocations

    generated_starters: Tuple[str, str, str]
    generated_marill: str
    # (map header, encounter table, index) -> species.
    generated_encounters: MutableMapping[Tuple[str, str, int], str]
    ool_encounters: MutableMapping[Tuple[str, str, int], str]
    # (trainer, index) -> species
    generated_trainer_parties: MutableMapping[Tuple[str, int], str]
    dexsanity_specs: Sequence[str]
    trainersanity_trainers: Sequence[str]
    added_hm_compatibility: MutableMapping[str, MutableSequence[Hm]]

    accessible_mons: Sequence[str]
    accessible_once_mons: Sequence[str]
    accessible_see_mons: Sequence[str]

    ruledata: ruledata.Rules

    itempool: Sequence[PokemonHgssItem]
    slot_data: Optional[Mapping[str, Any]]

    def __init__(self, multiworld: MultiWorld, player: int) -> None:
        super().__init__(multiworld, player)
        self.generated_starters = ("chikorita", "cyndaquil", "totodile")
        self.generated_marill = "marill"
        self.generated_encounters = {}
        self.ool_encounters = {}
        self.generated_trainer_parties = {}
        self.added_hm_compatibility = {}
        self.itempool = []
        self.slot_data = None

    def generate_early(self) -> None:
        if hasattr(self.multiworld, "generation_is_fake") \
            and hasattr(self.multiworld, "re_gen_passthrough") \
            and "Pokemon HeartGold and SoulSilver" in self.multiworld.re_gen_passthrough: # type: ignore
            slot_data: Mapping[str, Any] = self.multiworld.re_gen_passthrough["Pokemon HeartGold and SoulSilver"] # type: ignore
            self.options.load_options(slot_data)
            self.dexsanity_specs = [speciesdata.species_id_to_const_name[id] for id in slot_data["dexsanity_specs"]]
            self.trainersanity_trainers = [trainerdata.trainer_raw_id_to_trainer_const_name[id] for id in slot_data["trainersanity_trainers"]]
            ool_encounters = set(slot_data["ool_encounters"])
            self.generated_encounters = {encounterdata.encounter_string_to_key(k):speciesdata.species_id_to_const_name[v] for k, v in slot_data["generated_encounters"].items() if k not in ool_encounters}
            def trainer_string_to_key(v) -> Tuple[str, int]:
                i = v.rfind("_")
                return v[:i], int(v[i + 1:])
            self.generated_trainer_parties = {trainer_string_to_key(k):speciesdata.species_id_to_const_name[v] for k, v in slot_data["generated_trainer_parties"].items()}
            self.slot_data = slot_data

        self.required_locations = RequiredLocations(self.options)
        self.options.validate()

    def get_filler_item_name(self) -> str:
        # TODO
        return "Great Ball"

    def create_regions(self) -> None:
        regions, trainers = create_regions(self)

        randomize_starters(self)
        if self.slot_data is None:
            randomize_trainer_parties_and_encounters(self)
        add_virt_specs(self, regions)
        if self.slot_data is None:
            required_trainersanity = self.options.trainersanity_required.to_const_names()
            trainers = trainers - required_trainersanity
            if len(self.options.trainersanity_whitelist.value) > 0:
                possible_trainersanity = sorted(trainers & self.options.trainersanity_whitelist.to_const_names())
            else:
                possible_trainersanity = sorted(trainers - self.options.trainersanity_blacklist.to_const_names())
            self.trainersanity_trainers = self.random.sample(possible_trainersanity, k=self.options.trainersanity.value - len(required_trainersanity)) + sorted(required_trainersanity)
        create_locations(self, regions)
        self.multiworld.regions.extend(regions.values())

    def create_items(self) -> None:
        locations: Iterable[PokemonHgssLocation] = self.multiworld.get_locations(self.player) # type: ignore
        item_locations = filter(
            lambda loc : loc.address is not None and loc.is_enabled and not loc.locked,
            locations)

        add_items: list[str] = ["razor_claw", "razor_fang", "sun_stone", "linking_cord"]
        if not self.options.randomize_encounters:
            add_items.append("thunderstone")
        for item in ["master_repel"]:
            if getattr(self.options, item).value == 1:
                add_items.append(item)

        if self.options.hm_reader == AddHMReader.option_itempool:
            add_items.append("hm_reader")
        elif self.options.hm_reader == AddHMReader.option_precollected:
            self.multiworld.push_precollected(self.create_item(itemdata.items["hm_reader"].label))

        time_items = [k for k, v in itemdata.items.items() if "time" in v.group]
        self.random.shuffle(time_items)
        if self.options.time_items:
            add_items.extend(time_items[1:])
            self.multiworld.push_precollected(self.create_item(itemdata.items[time_items[0]].label))
        else:
            for item in time_items:
                self.multiworld.push_precollected(self.create_item(itemdata.items[item].label))
        sound_items = [k for k, v in itemdata.items.items() if "sound" in v.group]
        self.random.shuffle(sound_items)
        if self.options.sound_items:
            add_items.extend(sound_items[1:])
            self.multiworld.push_precollected(self.create_item(itemdata.items[sound_items[0]].label))
        else:
            for item in sound_items:
                self.multiworld.push_precollected(self.create_item(itemdata.items[item].label))

        itempool = []
        for loc in item_locations:
            item_id: int = loc.default_item_id # type: ignore
            if item_id > 0 and get_item_classification(item_id) != ItemClassification.filler:
                itempool.append(self.create_item_by_code(item_id))
            elif len(add_items) > 0:
                itempool.append(self.create_item(itemdata.items[add_items.pop()].label))
            else:
                itempool.append(self.create_item_by_code(item_id))

        self.multiworld.itempool += itempool
        for item in add_items:
            self.multiworld.push_precollected(self.create_item(itemdata.items[item].label))
        self.itempool = itempool

    def create_item(self, name: str) -> PokemonHgssItem:
        return self.create_item_by_code(self.item_name_to_id[name])

    def create_item_by_code(self, item_code: int):
        return PokemonHgssItem(
            self.item_id_to_name[item_code],
            get_item_classification(item_code),
            item_code,
            self.player)

    def set_rules(self) -> None:
        set_rules(self)

    def generate_output(self, output_directory: str) -> None:
        if self.options.version == Version.option_heartgold:
            patch = PokemonHeartgoldPatch(player=self.player, player_name=self.player_name)
            base_patches = ["hg_us"]
        else:
            patch = PokemonSoulsilverPatch(player=self.player, player_name=self.player_name)
            base_patches = ["ss_us"]
        for name in base_patches:
            name = "base_patch_" + name
            patch.write_file(f"{name}.bsdiff4", pkgutil.get_data(__name__, f"patches/{name}.bsdiff4")) # type: ignore
        generate_output(self, output_directory, patch)

    def create_event(self, name: str) -> PokemonHgssItem:
        return PokemonHgssItem(
            name,
            ItemClassification.progression,
            None,
            self.player)

    def generate_basic(self) -> None:
        fill_species(self)
        if self.slot_data is None:
            verify_hm_accessibility(self)
        else:
            for spec, seq in self.slot_data["added_hm_compatibility"]:
                for hm in seq:
                    self.ruledata.hm_mons[Hm(hm.upper())].append("mon_" + spec)

    def fill_slot_data(self) -> Mapping[str, Any]:
        if self.slot_data is not None:
            return self.slot_data
        ret = self.options.save_options()
        ret["dexsanity_specs"] = [speciesdata.species[spec].id for spec in self.dexsanity_specs]
        ret["trainersanity_trainers"] = [trainerdata.trainers[trainer + "_chikorita" if trainer.startswith("rival_") or trainer.startswith("partner_rival_") else trainer].get_raw_id() for trainer in self.trainersanity_trainers]
        ret["generated_encounters"] = {f"{region}_{table}_{i}":speciesdata.species[spec].id for (region, table, i), spec in self.generated_encounters.items()}
        ret["ool_encounters"] = [f"{region}_{table}_{i}" for (region, table, i) in self.ool_encounters]
        ret["generated_encounters"].update({f"{region}_{table}_{i}":speciesdata.species[spec].id for (region, table, i), spec in self.ool_encounters.items()})
        ret["generated_trainer_parties"] = {f"{tr}_{i}":speciesdata.species[spec].id for (tr, i), spec in self.generated_trainer_parties.items()}
        ret["added_hm_compatibility"] = {spec:[hm.name.lower() for hm in compat] for spec, compat in self.added_hm_compatibility.items()}
        ret["world_version"] = "0.0.4"
        pfx = "hg" if self.options.version == Version.option_heartgold else "ss"
        ret["possible_ap_struct_addresses"] = [v for k, v in AP_STRUCT_ADDRESS.items() if k.startswith(pfx)]
        return ret

    @staticmethod
    def interpret_slot_data(slot_data: Mapping[str, Any]) -> Mapping[str, Any]:
        return slot_data

    ut_can_gen_without_yaml = True

    def get_world_collection_state(self) -> CollectionState:
        state = CollectionState(self.multiworld, True)
        progression_items = [item for item in self.itempool if item.advancement]
        locations = self.get_locations()
        for item in progression_items:
            state.collect(item, True)
        for item in self.get_pre_fill_items():
            state.collect(item, True)
        state.sweep_for_advancements(locations)
        return state


    def extend_hint_information(self, hint_data: dict[int, dict[int, str]]) -> None:
        dexsanity_specs = set(self.dexsanity_specs)
        def get_dexsanity_encounter_hint_data(dexsanity_hint_data: MutableMapping[str, MutableSet[str]]) -> None:
            for key, mon in self.generated_encounters.items():
                if mon in dexsanity_specs:
                    dexsanity_hint_data[mon].add(encounter_slot_label(key, self.options.in_logic_encounters.methods()))

        #am_set = set(self.accessible_mons)
        #def get_dexsanity_evolution_hint_data(dexsanity_hint_data: dict[str, set[str]]) -> None:
        #    for mon in self.dexsanity_specs:
        #        data = speciesdata.species[mon]
        #        if data.pre_evolution is None \
        #            or data.pre_evolution.species not in am_set \
        #            or data.pre_evolution.method not in self.options.in_logic_evolution_methods \
        #            or data.pre_evolution.other_species is not None and data.pre_evolution.other_species not in am_set:
        #            continue
        #        dexsanity_hint_data[mon].add("Evolve from " + speciesdata.species[data.pre_evolution.species].label)

        player_hint_data = hint_data.setdefault(self.player, {})
        if self.options.dexsanity > 0:
            dexsanity_hint_data: dict[str, MutableSet[str]] = defaultdict(set)
            get_dexsanity_encounter_hint_data(dexsanity_hint_data)
            player_hint_data.update({
                speciesdata.species[mon].id | (LocationTable.DEX << 16):", ".join(methods)
                for mon, methods in dexsanity_hint_data.items()
            })

    def write_spoiler(self, spoiler_handle) -> None:
        spoiler_handle.write(f"\nPokemon HeartGold and SoulSilver ({self.player_name}):\n")

        if self.options.randomize_starters:
            spoiler_handle.write("Starters: {}\n".format(", ".join(speciesdata.species[spec].label for spec in self.generated_starters)))

        encounters_per_pokemon = defaultdict(set)
        if self.options.randomize_encounters:
            for key, mon in self.generated_encounters.items():
                encounters_per_pokemon[mon].add(encounter_slot_label(key, self.options.in_logic_encounters.methods()))

        if encounters_per_pokemon:
            spoiler_handle.write(f"\nRandomized Pokemon ({self.player_name}):\n")
            lines = [f"{speciesdata.species[mon].label}: {', '.join(sorted(locations))}\n"
                     for mon, locations in encounters_per_pokemon.items()]
            lines.sort()
            spoiler_handle.writelines(lines)
