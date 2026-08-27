# options.py
#
# Copyright (C) 2026 James Petersen <m@jamespetersen.ca>
# Licensed under MIT. See LICENSE

from collections.abc import Mapping, MutableMapping, Sequence, Set
from dataclasses import dataclass
from Options import Choice, DeathLink, DefaultOnToggle, NamedRange, OptionDict, OptionError, OptionGroup, OptionSet, PerGameCommonOptions, Range, StartInventoryPool, Toggle, Option, FreeText, Visibility
from typing import Any, Literal, Optional

from .data import VersionEnum
from .data.encounters import encounter_types
from .data.species import species, having_two_level_evos, legendary_mons, expand_set_via_evolutions
from .data.regions import regions
from .data.trainers import in_game_trainer_labels, trainer_party_supporting_starters, trainer_name_to_trainer_const_name
from .data.encounters import encounters

class SpeciesBlacklist(OptionSet):
    cached_blacklist: Set[str] | None = None

    def blacklist(self) -> Set[str]:
        if self.cached_blacklist is None:
            if "legendaries" in self:
                self.cached_blacklist = (frozenset(self.value) - {"legendaries"}) | set(legendary_mons)
            else:
                self.cached_blacklist = frozenset(self.value)
        return self.cached_blacklist

class RegionEvoRequirement(Choice):
    option_kanto = 1
    option_johto = 2
    option_both = 3
    default = option_both

class Version(Choice):
    """
    Which version will be randomized.
    """
    display_name = "Version"
    option_heartgold = int(VersionEnum.HEARTGOLD)
    option_soulsilver = int(VersionEnum.SOULSILVER)
    default = option_heartgold


class RandomizeHms(DefaultOnToggle):
    """
    Adds the HMs to the pool.

    The expectation is that this will be enabled. If not, depending on
    other options—particularly barricades—certain locations may be inaccessible,
    or certain seeds uncompletable.
    """
    display_name = "Randomize HMs"

class RandomizeBadges(DefaultOnToggle):
    """
    Adds the badges to the pool.

    The expectation is that this will be enabled. If not, depending on
    other options—particularly barricades—certain locations may be inaccessible,
    or certain seeds uncompletable.
    """
    display_name = "Randomize Badges"

class RandomizeOverworlds(DefaultOnToggle):
    """Adds overworld items to the pool."""
    display_name = "Randomize Overworlds"

class RandomizeHiddenItems(Toggle):
    """Adds hidden items to the pool."""
    display_name = "Randomize Hidden Items"

class RandomizeNpcGifts(DefaultOnToggle):
    """Adds NPC gifts to the pool."""
    display_name = "Randomize NPC Gifts"

class RandomizeKeyItems(DefaultOnToggle):
    """Adds key items to the pool."""
    display_name = "Randomize Key Items"

class RandomizeRods(DefaultOnToggle):
    """Adds rods to the pool."""
    display_name = "Randomize Rods"

class RandomizeRunningShoes(Toggle):
    """Adds the running shoes to the pool."""
    display_name = "Randomize Running Shoes"

class RandomizeBicycle(Toggle):
    """Adds the bicycle to the pool."""
    display_name = "Randomize Bicycle"

class RandomizePokedex(Toggle):
    """Add the Pokedex to the pool. Note: this also adds the national dex to the pool."""
    display_name = "Randomize Pokedex"

class RandomizeTimeItems(DefaultOnToggle):
    """Adds the time items to the item pool. If set to false, they are precollected."""
    display_name = "Randomize Time Items"

class RandomizeSoundsItems(DefaultOnToggle):
    """Adds the sound items to the item pool. If set to false, they are precollected."""
    display_name = "Randomize Sound Items"

class RemoveBadgeRequirement(OptionSet):
    """
    Specify which HMs do not require a badge to use outside of battle. This overrides the HM Badge Requirements setting.

    HMs should be provided in the form: "fly", "waterfall", "rock_smash", etc.
    "all" specifies that all hms have their requirement removed.
    """
    display_name = "Remove Badge Requirement"
    valid_keys = ["cut", "fly", "surf", "strength", "whirlpool", "rock_smash", "waterfall", "rock_climb", "all"]

class VisibilityHmLogic(DefaultOnToggle):
    """Logically require Flash for traversing and finding locations in applicable regions."""
    display_name = "Logically Require Flash for Applicable Regions"

class DowsingMachineLogic(DefaultOnToggle):
    """Logically require the Dowsing Machine to find hidden items."""
    display_name = "Logically Require Dowsing Machine for Hidden Items"

class Goal(Choice):
    """
    The goal of the randomizer.
    
    Options:
    - clear_pokemon_league: defeat Lance in the Pokémon League.
    - defeat_red: defeat Red at the Summit of Mount Silver.
    """
    display_name = "Goal"
    option_clear_pokemon_league = 0
    option_defeat_red = 1
    default = option_clear_pokemon_league

class AddMasterRepel(Toggle):
    """
    Add a master repel item to the item pool. The master repel is a key item.
    It is a repel that blocks all encounters, and never runs out.
    """
    display_name = "Add Master Repel"

class ExpMultiplier(Option[int | str]):
    """
    Set an experience multiplier for all gained experience.
    This can either be an integer between 0 and 65535, inclusive,
    or a string of a fraction "a/b", where the numerator is
    between 0 and 65535, inclusive, and the denominator is
    between 1 and 65535, inclusive.

    This option can be modified in-game.
    """
    display_name = "Exp. Multiplier"
    default = 1

    def __init__(self, value: str | int):
        assert isinstance(value, str) or isinstance(value, int), "value of ExpMultiplier must be a string or an integer"
        self.value = value

    @classmethod
    def from_text(cls, text: str) -> "ExpMultiplier":
        try:
            return cls(int(text.strip()))
        except ValueError:
            return cls(text.strip())

    @classmethod
    def from_any(cls, data: Any) -> "ExpMultiplier":
        if isinstance(data, int):
            return cls(data)
        else:
            return cls.from_text(data)

    @classmethod
    def get_option_name(cls, value: str | int) -> str:
        if isinstance(value, str):
            return "".join(c for c in value if not c.isspace())
        else:
            return str(value)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return other.to_bytes() == self.to_bytes()
        elif isinstance(other, str) or isinstance(other, int):
            return ExpMultiplier(other).to_bytes() == self.to_bytes()
        else:
            raise TypeError(f"Can't compare {self.__class__.__name__} with {other.__class__.__name__}")

    def verify(self, *args, **kwargs) -> None:
        self.to_bytes()

    def to_bytes(self) -> bytes:
        def try_ints(num: int, denom: int = 1) -> bytes:
            if num < 0 or num > 65535:
                raise OptionError(f"exp multiplier numerator must be between 0 and 65535")
            elif denom < 1 or denom > 65535:
                raise OptionError(f"exp multiplier denominator must be between 1 and 65535")
            else:
                return num.to_bytes(2, 'little') + denom.to_bytes(2, 'little')
        if isinstance(self.value, int):
            return try_ints(self.value)
        pivot = self.value.find('/')
        if pivot == -1:
            # only a numerator
            try:
                return try_ints(int(self.value.strip()))
            except ValueError:
                raise OptionError("exp multiplier string must be an integer or fraction")
        else:
            try:
                return try_ints(int(self.value[:pivot].strip()), int(self.value[pivot + 1:].strip()))
            except ValueError:
                raise OptionError("exp multiplier string must be an integer or fraction")

class BlindTrainers(Toggle):
    """
    Set whether trainers will be blind.

    This option can also be modified in the in-game options menu.
    """
    display_name = "Blind Trainers"

class GameOptions(OptionDict):
    """
    Presets in-game options.

    Allowed options and values, with default first:

    text_speed: mid/slow/fast - Sets the text speed
    sound: stereo/mono - Sets the sound mode
    battle_scene: on/off - Sets whether the battle animations are shown
    battle_style: shift/set - Sets whether pokemon can be changed when the opponent's pokemon faints
    button_mode: normal/l=a - Sets the button mode
    text_frame: 1–20 - Sets the textbox frame. "random" will pick a random frame.
    received_items_notification: jingle/nothing/message - Sets the received_items_notification.

    The text_speed, sound, battle_scene, battle_style, button_mode, text_frame, and received_items_notification
    options can additionally be modifier in the in-game options menu.
    """
    display_name = "Game Options"
    default = {
        "text_speed": "mid",
        "sound": "stereo",
        "battle_scene": "on",
        "battle_style": "shift",
        "button_mode": "normal",
        "text_frame": 1,
        "received_items_notification": "jingle",
    }

    def __getattr__(self, name: str) -> Any:
        if name in GameOptions.default:
            return self.get(name, GameOptions.default[name])
        else:
            raise AttributeError(name, self)

class RemoteItems(Choice):
    """
    Whether local items should be given in-game, or sent by the server.
    This overrides the show randomized progression items option: all items are shown.

    Choices:
    - off: no items are remote.
    - only_randomized: only randomized items are remote.
    - only_randomized_or_progression: only randomized items or progression items are remote.
    - all: all (randomizable) items are remote.
    """
    display_name = "Remote Items"
    option_off = 0
    option_only_randomized = 1
    option_only_randomized_or_progression = 2
    option_all = 3
    default = option_off

class FPS60(Toggle):
    """
    Whether the 60 FPS patch should be applied.

    This option can also be modified in the in-game options menu.
    """
    display_name = "60 FPS"

class HMCutIns(Toggle):
    """
    Whether HM Cut-Ins should be played.

    This option can also be modified in the in-game options menu.
    """
    display_name = "HM Cut-Ins"

class NormalizeEncounters(DefaultOnToggle):
    """
    In the vanilla game, encounter table entries have varying probabilities, from 20% down to 1%.
    This option will normalize these, so they all have the same probability. The normalized
    probabilities are 1/12 for each entry in the land table, and 1/5 for each entry in the water
    and rod tables.

    This option is modifiable in the in-game options menu.

    Note: this does not mean that there are twelve encounter slots, and a 1/12 chance for each slot.
    Often there will only be two or three encounter slots per route, occupying all twelve entries
    in the encounter table. This option only means that the *smallest* possible probability for any
    slot will be 1/12. (except for special encounters, where there may be more or less table
    entries)
    """
    display_name = "Normalize Encounters"

class InstantText(Toggle):
    """
    Have text scroll instantly.

    This option is modifiable in the in-game options menu.
    """
    display_name = "Instant Text"

class HoldAToAdvance(Toggle):
    """
    You no longer need to press A to advance text, holding it will suffice. (Same for B)

    This option is modifiable in the in-game options menu.
    """
    display_name = "Hold A to Advance"

class ReusableTms(Toggle):
    """TMs are reusable."""
    display_name = "Reusable TMs"

class AlwaysCatch(Toggle):
    """
    Have a 100% chance of catching any encounter.

    This option is modifiable in the in-game options menu.
    """
    display_name = "Always Catch"

class APItemsShopInAPHelper(DefaultOnToggle):
    """
    Non-reusable progression bag (named AP items shop) items shop is available with the AP Helper.
    (the AP Helper is present in the basement floor of any Pokémon Center)
    """
    display_name = "AP Item Shop in AP Helper"

class GuaranteedEscape(Toggle):
    """
    You will always be able to escape from wild encounters.

    This option is modifiable in the in-game options menu.
    """
    display_name = "Guaranteed Escape"

class TalkTrainersWithoutFight(Toggle):
    """
    You can talk to trainers without having to fight them.
    This only applies when you talk to them, not if they spot you.
    Note: them spotting you can be disabled by the blind trainers option.

    This option is modifiable in the in-game options menu.
    """
    display_name = "Talk to Trainers without Fighting Them"

class RandomizeEncounters(Toggle):
    """Randomize encountered Pokémon. This does not affect static legendaries, like Ho-Oh and Lugia."""
    display_name = "Randomize Encounters"

ENCOUNTER_METHOD_MAP: Mapping[str, Set[str]] = {
    "rods": {"good_rod", "super_rod", "old_rod"},
    "time": {"morning", "day", "night"},
    "sounds": {"hoenn", "sinnoh"},
}

class InLogicEncounters(OptionSet):
    """
    - rods: fishing encounters.
    - time: tall-grass or fishing encounters which require a specific time of day.
    - rock_smash: rock smash encounters.
    - sounds: hoenn/sinnoh sounds encounters.
    """
    display_name = "In Logic Encounters"
    default = {"rods", "time", "rock_smash", "sounds"}
    valid_keys = ["rods", "time", "rock_smash", "sounds"]
    cached_methods: Set[str] | None = None

    def methods(self) -> Set[str]:
        if self.cached_methods is None:
            self.cached_methods = {v for s in self.value for v in ENCOUNTER_METHOD_MAP.get(s, {s})} | {"surf"}
        return self.cached_methods


class EncounterSpeciesBlacklist(SpeciesBlacklist):
    """
    Specify the banned encounter species.
    The whitelist has precedence over this.
    This has no effect if starters are not randomized.

    The species names should be entered entirely in lowercase.
    Spaces should be replaced by underscores. For example,
    Mr. Mime would be mr_mime.

    legendaries, all lowercase, will be interpreted as banning all legendary
    species.
    """
    valid_keys = list(species.keys()) + ["legendaries"]
    display_name = "Encounter Species Blacklist"

class RandomizeTrainerParties(Toggle):
    """Randomize trainer party members."""
    display_name = "Randomize Trainer Parties"

class TrainerPartyBlacklist(SpeciesBlacklist):
    """
    Specify the banned trainer party species.
    The whitelist has precedence over this.
    This has no effect if starters are not randomized.

    The species names should be entered entirely in lowercase.
    Spaces should be replaced by underscores. For example,
    Mr. Mime would be mr_mime.

    legendaries, all lowercase, will be interpreted as banning all legendary
    species.
    """
    valid_keys = list(species) + ["legendaries"]
    display_name = "Trainer Party Blacklist"

class RandomizeStarters(Toggle):
    """Randomize starter Pokémon."""
    display_name = "Randomize Starters"

class RequireTwoLevelEvolutionStarters(Toggle):
    """
    If the starters are randomized, require that they all be two-level-evolution species.
    This option only applies to the blacklist. If the whitelist is nonempty,
    it is ignored.
    """
    display_name = "Require Two Level Evolution Starters"

class StarterWhitelist(OptionSet):
    """
    Specify the possible starters that can be randomized.
    This has precedence over the blacklist and requiring two-level-evolution
    species.
    This has no effect if starters are not randomized.

    The species names should be entered entirely in lowercase.
    Spaces should be replaced by underscores. For example,
    Mr. Mime would be mr_mime.

    Note: legendaries is **not** a valid key for this option.
    """
    display_name = "Starter Whitelist"
    valid_keys = list(species)

class StarterBlacklist(SpeciesBlacklist):
    """
    Specify the banned starters.
    The whitelist has precedence over this.
    This has no effect if starters are not randomized.

    The species names should be entered entirely in lowercase.
    Spaces should be replaced by underscores. For example,
    Mr. Mime would be mr_mime.

    legendaries, all lowercase, will be interpreted as banning all legendary
    species.
    """
    display_name = "Starter Blacklist"
    valid_keys = list(species) + ["legendaries"]

class RandomizeMarillInIntro(DefaultOnToggle):
    """Randomize the species of the Pokémon that is shown in the intro."""
    display_name = "Randomize Intro Pokémon"
    # currently doesn't work
    visibility = Visibility(0)

NUM_TRAINERS = sum(len(r.trainers) for r in regions.values())
class TrainersanityCount(NamedRange):
    """
    Each trainer adds a location to the game. These locations are
    filled with nuggets by default.
    """
    display_name = "Trainersanity Count"
    default = 0
    range_start = 0
    range_end = NUM_TRAINERS
    special_range_names = {
        "none": default,
        "full": range_end,
    }

class TrainersanityWhitelist(OptionSet):
    """
    Specify the possible trainers which can be trainersanity locations.
    This has precedence over the trainersanity blacklist.
    """
    display_name = "Trainersanity Whitelist"
    valid_keys = in_game_trainer_labels

    def to_const_names(self) -> Set[str]:
        return {trainer_name_to_trainer_const_name[v] for v in self.value}

class TrainersanityBlacklist(OptionSet):
    """
    Specify the trainers which cannot be trainersanity locations.
    The whitelist has precedence over this.
    """
    display_name = "Trainersanity Blacklist"
    valid_keys = in_game_trainer_labels

    def to_const_names(self) -> Set[str]:
        return {trainer_name_to_trainer_const_name[v] for v in self.value}

class TrainersanityRequired(OptionSet):
    """
    Specify trainers which must be trainersanity locations.
    Has precedence over the whitelist and blacklist.
    """
    display_name = "Trainersanity Required"
    valid_keys = in_game_trainer_labels

    def to_const_names(self) -> Set[str]:
        return {trainer_name_to_trainer_const_name[v] for v in self.value}

class DexsanityCount(NamedRange):
    """
    How many dexsanity locations there will be.
    """
    display_name = "Dexsanity Count"
    default = 0
    range_start = 0
    range_end = 493
    special_range_names = {
        "none": default,
        "full": range_end,
    }

class DexsanityMode(Choice):
    """
    The dexsanity mode.

    Options:
    - noreq: no items are required to trigger dexsanity locations.
    - req: the Pokedex (or National Dex for non-regional species) is required
           to trigger dexsanity locations.
    - req_noprompt: same as req, but when you initially get the Pokedex
                    or National Dex, do not prompt for each already seen
                    dexsanity species.
    """
    display_name = "Dexsanity Mode"
    default = 1
    option_noreq = 1
    option_req = 2
    option_req_noprompt = 3

class InLogicEvolutionMethods(OptionSet):
    """
    Evolution methods that are in logic.
    Valid keys:
    - level: all species which require a specific level to evolve.
    - happiness: all species which require happiness to evolve.
    - use_item: all species which require a specific item to evolve. This includes trade evolutions (item is linking cord).
    - held_item: all species which require a held item to evolve.
    - time: all species which require being evolved at certain times.
    - location: all species which require being evolved at certain locations.
    - mildly_annoying: the secondary evolution of nincada, leveling up with a certain species in the party, those requiring certain genders.
    - highly_annoying: the evolutions of tyrogue, wurmple, and feebas.

    For species whose evolutions intersect multiple categories, all categories are required for their evolution to be in logic. For example, time and held_item must be specified for happiny's evolution to be in logic. level and mildly_annoying must be specified for the evolution of nincada into shedinja.
    """
    display_name = "In-Logic Evolution Methods"
    default = {"level", "use_item", "held_item", "time", "location", "happiness"}
    valid_keys = {"level", "happiness", "use_item", "held_item", "time", "location", "mildly_annoying", "highly_annoying"}

    cached_methods: Optional[Set[str]] = None

    def methods(self) -> Set[str]:
        if self.cached_methods is not None:
            return self.cached_methods
        ret = set()
        if "level" in self:
            ret |= {
                "level",
                "level_ninjask",
            }
            if "mildly_annoying" in self:
                ret |= {
                    "level_shedinja",
                    "level_male",
                    "level_female",
                }
            if "highly_annoying" in self:
                ret |= {
                    "level_atk_gt_def",
                    "level_atk_eq_def",
                    "level_atk_lt_def",
                    "level_pid_low",
                    "level_pid_high",
                }


        if "time" in self and "held_item" in self:
            ret |= {
                "level_with_held_item_day",
                "level_with_held_item_night",
            }

        if "mildly_annoying" in self:
            ret.add("level_species_in_party")

        if "highly_annoying" in self:
            ret.add("level_beauty")

        if "happiness" in self:
            ret.add("level_happiness")
            if "time" in self:
                ret |= {
                    "level_happiness_day",
                    "level_happiness_night",
                }

        if "use_item" in self:
            ret |= {
                "use_item",
                "trade",
                #"level_know_move",
            }
            if "held_item" in self:
                ret.add("trade_with_held_item")
            if "mildly_annoying" in self:
                ret |= {
                    "use_item_male",
                    "use_item_female",
                }

        if "location" in self:
            ret |= {
                "level_magnetic_field",
                "level_moss_rock",
                "level_ice_rock",
            }

        self.cached_methods = ret
        return ret

class DexsanityWhitelist(SpeciesBlacklist):
    """
    Specify the possible species which can be dexsanity locations.
    This has precedence over the dexsanity blacklist.

    The species names should be entered entirely in lowercase.
    Spaces should be replaced by underscores. For example,
    Mr. Mime would be mr_mime.

    legendaries, all lowercase, will be interpreted as allowing all legendary
    species.
    """
    display_name = "Dexsanity Whitelist"
    valid_keys = list(species) + ["legendaries"]

class DexsanityBlacklist(SpeciesBlacklist):
    """
    Specify the species which cannot be dexsanity locations.
    The whitelist has precedence over this.

    The species names should be entered entirely in lowercase.
    Spaces should be replaced by underscores. For example,
    Mr. Mime would be mr_mime.

    legendaries, all lowercase, will be interpreted as banning all legendary
    species.
    """
    display_name = "Dexsanity Blacklist"
    valid_keys = list(species) + ["legendaries"]

class DexsanityRequired(SpeciesBlacklist):
    """
    Specify the species which must be dexsanity locations.
    This has precedence over the whitelist and blacklist.

    The species names should be entered entirely in lowercase.
    Spaces should be replaced by underscores. For example,
    Mr. Mime would be mr_mime.

    legendaries, all lowercase, will be interpreted as banning all legendary
    species.
    """
    display_name = "Dexsanity Required"
    valid_keys = list(species) + ["legendaries"]

class ItemNotificationsMask(OptionSet):
    """
    Which types of items should in-game notifications be shown for.
    Valid options are all, progression, useful, and trap.

    This option can also be modified in the in-game options menu.
    """
    display_name = "Item Notifications Mask"
    valid_keys = ["progression", "useful", "trap", "all"]
    default = {"progression", "useful"}
    
    def to_mask(self) -> int:
        mask = 0
        for index, key in enumerate(self.valid_keys):
            if key in self:
                mask |= 1 << index
        return mask

class PokemonHgssDeathLink(DeathLink):
    __doc__ = DeathLink.__doc__ + "\n\n    In Pokémon HeartGold and SoulSilver, blacking out sends a death and receiving a death causes you to black out.\n" # type: ignore

class DeathLinkGroup(FreeText):
    """
    The death link group to use. Death links are only sent within groups.
    To interface with games which do not support groups, use the empty group "".
    """
    default = ""
    display_name = "Death Link Group"


class TMHMCompatibility(Choice):
    """
    Add TM/HM compatibility to all species.

    Choices:
    - none: the compatibility is unaffected
    - hms: all species will be compatible with all HMs (and TM70 Flash)
    - all: all species will be compatible with all TMs and HMs
    """
    display_name = "TM/HM Compatibility"
    option_none = 0
    option_hms = 1
    option_all = 2
    default = option_none

YES_NO_SHUFFLE = Literal["yes"] | Literal["no"] | Literal["shuffle"]

class MoveRandomization(OptionDict):
    """
    Randomize properties of moves.
    Each of the options can take one of three values: "no", "yes", "shuffle".
    """
    visibility = Visibility(0)
    default = {
        "type": "no",
        "accuracy": "no",
        "pp": "no",
        "priority": "no",
    }

    type: YES_NO_SHUFFLE
    accuracy: YES_NO_SHUFFLE
    pp: YES_NO_SHUFFLE
    priority: YES_NO_SHUFFLE

    def __getattr__(self, name: str) -> Any:
        if name in MoveRandomization.default:
            v = self.get(name, MoveRandomization.default[name])
            if isinstance(v, bool):
                return "yes" if v else "no"
            else:
                return v
        else:
            raise AttributeError(name, self)

class AddHMReader(Choice):
    """
    Add the HM Reader item. The HM Reader is an item that lets you use field moves without teaching them.

    Options:
    - no: Don't add the HM Reader item.
    - itempool: Add the HM Reader item to the itempool.
    - precollected: Start with the HM Reader item.
    """
    option_no = 0
    option_itempool = 1
    option_precollected = 2
    default = option_no
    display_name = "Add HM Reader"

class HMReaderMode(Choice):
    """
    Mode for the HM Reader. The HM Reader is an item that letse you use field moves without teaching them.

    Options:
    - req_mon: require a Pokemon in your party to which you can teach the move, in order for the HM reader to use it.
    - noreq_mon: do not require a Pokemon in your party to which you can teach the move.
    """
    option_req_mon = 0
    option_noreq_mon = 1
    default = option_req_mon
    display_name = "HM Reader Mode"

class RandomizeFlyItems(OptionSet):
    """
    Add fly locations to the pool.

    Options:
    - kanto
    - johto
    - pokemon_league
    - mount_silver
    """
    valid_keys = {"kanto", "johto", "pokemon_league", "mount_silver"}
    default = set()
    display_name = "Randomize Fly Locations"

class RequireFlyItemsForFlight(Toggle):
    """
    Require the fly location item to fly to a certain location.
    If this is false, then simply visiting the location will be sufficient.
    """
    display_name = "Require Fly Location Items for Flight"

class RandomizePokegearCards(Toggle):
    """
    Randomize the cards available for the Pokegear.
    """
    display_name = "Randomize Pokegear Cards"

class RequireRestoredPowerForMagnetTrain(DefaultOnToggle):
    """
    In addition to the pass, the magnet train will require power to be restored
    before it is operational (as it is in vanilla gameplay).
    """
    display_name = "Require Restored Power for Magnet Train"

class BlueReturnViridianBadgeRequirement(Range):
    """
    The number of Kanto League Badges required for Blue to agree to return to the Viridian City Gym.
    """
    display_name = "Badges for Blue Viridian"
    range_start = 0
    range_end = 7
    default = 7

class MossyRockLocations(RegionEvoRequirement):
    """
    Where mossy rocks appear. In vanilla, mossy rocks are used to evolve Eevee into Leafeon.

    Options:
    - option_kanto: a mossy rock will appear in Viridian Forest.
    - option_johto: a mossy rock will appear in Ilex Forest.
    - option_both: both of the above will apply.
    """
    option_kanto = 1
    option_johto = 2
    option_both = 3
    default = option_both
    display_name = "Mossy Rock Locations"

class IcyRockLocations(RegionEvoRequirement):
    """
    Where icy rocks appear. In vanilla, icy rocks are used to evolve Eevee into Glaceon.

    Options:
    - option_kanto: an icy rock will appear in Seafoam Islands.
    - option_johto: an icy rock will appear in Ice Path.
    - option_both: both of the above will apply.
    """
    option_kanto = 1
    option_johto = 2
    option_both = 3
    default = option_both
    display_name = "Icy Rock Locations"

class MagneticFieldLocations(RegionEvoRequirement):
    """
    Where magnetic fields are present. In vanilla, magnetic fields are used to evolve certain species.

    Options:
    - option_kanto: a magnetic field will be present in the grass outside the power plant.
    - option_johto: a magnetic field will be present in the Ruins of Alph.
    - option_both: both of the above will apply.
    """
    option_kanto = 1
    option_johto = 2
    option_both = 3
    default = option_both
    display_name = "Magnetic Field Locations"

class FastFishing(Toggle):
    """
    Fishing is faster.
    """
    display_name = "Fast Fishing"

slot_data_options: Sequence[str] = [
    "goal",
    "version",

    "death_link",
    "death_link_group",
    "remote_items",

    "hms",
    "badges",
    "overworlds",
    "hiddens",
    "npc_gifts",
    "key_items",
    "rods",
    "running_shoes",
    "bicycle",
    "pokedex",
    "time_items",
    "sound_items",
    "pokegear_card",
    
    "remove_badge_requirements",
    "visibility_hm_logic",
    "dowsing_machine_logic",
    "reusable_tms",
    "ap_items_shop_in_ap_helper",

    "require_restored_power_for_magnet_train",
    "blue_return_viridian_badge_requirement",

    "hm_reader",
    "hm_reader_mode",
    "tmhm_compatibility",

    "randomize_fly_items",
    "require_fly_items_for_flight",

    "randomize_starters",
    "require_two_level_evolution_starters",
    "starter_whitelist",
    "starter_blacklist",
    "randomize_intro_mon",

    "randomize_encounters",
    "in_logic_encounters",
    "encounter_species_blacklist",
    "dexsanity",
    "dexsanity_mode",
    "dexsanity_whitelist",
    "dexsanity_blacklist",
    "dexsanity_required",
    "in_logic_evolution_methods",
    "mossy_rock_locations",
    "icy_rock_locations",
    "magnetic_field_locations",

    "trainersanity",
    "trainersanity_whitelist",
    "trainersanity_blacklist",
    "trainersanity_required",
    "randomize_trainer_parties",
    "trainer_party_blacklist",

    "start_inventory_from_pool",

    "master_repel",
]

@dataclass
class PokemonHgssOptions(PerGameCommonOptions):
    version: Version
    goal: Goal

    death_link: PokemonHgssDeathLink
    death_link_group: DeathLinkGroup
    remote_items: RemoteItems

    hms: RandomizeHms
    badges: RandomizeBadges
    overworlds: RandomizeOverworlds
    hiddens: RandomizeHiddenItems
    npc_gifts: RandomizeNpcGifts
    key_items: RandomizeKeyItems
    rods: RandomizeRods
    running_shoes: RandomizeRunningShoes
    bicycle: RandomizeBicycle
    pokedex: RandomizePokedex
    time_items: RandomizeTimeItems
    sound_items: RandomizeSoundsItems
    pokegear_card: RandomizePokegearCards
    
    remove_badge_requirements: RemoveBadgeRequirement
    visibility_hm_logic: VisibilityHmLogic
    dowsing_machine_logic: DowsingMachineLogic
    reusable_tms: ReusableTms
    ap_items_shop_in_ap_helper: APItemsShopInAPHelper

    require_restored_power_for_magnet_train: RequireRestoredPowerForMagnetTrain
    blue_return_viridian_badge_requirement: BlueReturnViridianBadgeRequirement

    randomize_fly_items: RandomizeFlyItems
    require_fly_items_for_flight: RequireFlyItemsForFlight

    hm_reader: AddHMReader
    hm_reader_mode: HMReaderMode
    tmhm_compatibility: TMHMCompatibility

    randomize_starters: RandomizeStarters
    require_two_level_evolution_starters: RequireTwoLevelEvolutionStarters
    starter_whitelist: StarterWhitelist
    starter_blacklist: StarterBlacklist
    randomize_intro_mon: RandomizeMarillInIntro

    randomize_encounters: RandomizeEncounters
    in_logic_encounters: InLogicEncounters
    encounter_species_blacklist: EncounterSpeciesBlacklist
    dexsanity: DexsanityCount
    dexsanity_mode: DexsanityMode
    dexsanity_whitelist: DexsanityWhitelist
    dexsanity_blacklist: DexsanityBlacklist
    dexsanity_required: DexsanityRequired
    in_logic_evolution_methods: InLogicEvolutionMethods
    move_randomization: MoveRandomization
    mossy_rock_locations: MossyRockLocations
    icy_rock_locations: IcyRockLocations
    magnetic_field_locations: MagneticFieldLocations

    trainersanity: TrainersanityCount
    trainersanity_whitelist: TrainersanityWhitelist
    trainersanity_blacklist: TrainersanityBlacklist
    trainersanity_required: TrainersanityRequired
    randomize_trainer_parties: RandomizeTrainerParties
    trainer_party_blacklist: TrainerPartyBlacklist

    game_options: GameOptions
    blind_trainers: BlindTrainers
    hm_cut_ins: HMCutIns
    fps60: FPS60
    normalize_encounters: NormalizeEncounters
    instant_text: InstantText
    hold_a_to_advance: HoldAToAdvance
    always_catch: AlwaysCatch
    guaranteed_escape: GuaranteedEscape
    talk_trainers_without_fight: TalkTrainersWithoutFight
    exp_multiplier: ExpMultiplier
    item_notifications_mask: ItemNotificationsMask
    fast_fishing: FastFishing

    master_repel: AddMasterRepel

    start_inventory_from_pool: StartInventoryPool

    def requires_badge(self, hm: str) -> bool:
        return "all" not in self.remove_badge_requirements and hm.lower() not in self.remove_badge_requirements

    def validate(self) -> None:
        game_opts = self.game_options
        if game_opts.text_speed not in {"fast", "slow", "mid"}:
            raise OptionError(f"invalid text speed: \"{game_opts.text_speed}")
        if game_opts.sound not in {"mono", "stereo"}:
            raise OptionError(f"invalid sound: \"{game_opts.sound}\"")
        if game_opts.battle_scene not in {False, "off", True, "on"}:
            raise OptionError(f"invalid battle scene: \"{game_opts.battle_scene}\"")
        if game_opts.battle_style not in {"set", "shift"}:
            raise OptionError(f"invalid battle style: \"{game_opts.battle_style}\"")
        if game_opts.button_mode not in {"l=a", "normal"}:
            raise OptionError(f"invalid button mode: \"{game_opts.button_mode}\"")
        text_frame = game_opts.text_frame
        if game_opts.text_frame not in set(range(1, 21)) | {"random"}:
            raise OptionError(f"invalid text frame: \"{text_frame}\"")
        if game_opts.received_items_notification not in {"none", "nothing", "message", "jingle"}:
            raise OptionError(f"invalid received items notification: \"{game_opts.received_items_notification}\"")
        self.exp_multiplier.to_bytes()

        if self.move_randomization.keys() - MoveRandomization.default.keys():
            raise OptionError(f"unknown move randomization keys: {self.move_randomization.keys() - MoveRandomization.default.keys()}")
        else:
            for k, v in self.move_randomization.items():
                if not isinstance(v, bool) and v not in {"no", "yes", "shuffle"}:
                    raise OptionError(f"invalid move randomization choice for {k}: {v}")

        required_mons = {
            "oddish", "magikarp", "chansey",
        }
        required_mons |= self.dexsanity_required.blacklist()
        if self.version == Version.option_heartgold:
            required_mons |= {"marill", "jigglypuff", "growlithe"}
        else:
            required_mons |= {"staryu", "lickitung", "vulpix"}
        if self.randomize_encounters:
            required_mons.add("pichu")

        if not self.randomize_encounters:
            in_logic_encounter_mons = expand_set_via_evolutions({slot.species
                for rd in regions.values()
                if rd.encounters \
                for type in encounter_types
                if type != "rock_smash" or type in self.in_logic_encounters.methods() and type in rd.accessible_encounters
                for slot in getattr(encounters[rd.encounters], type)
                if slot.in_logic(self.version, self.in_logic_encounters.methods())
            }, self.in_logic_evolution_methods.methods())
        else:
            in_logic_encounter_mons = expand_set_via_evolutions(
                species.keys() - self.encounter_species_blacklist, self.in_logic_evolution_methods.methods()
            )
        if required_mons - in_logic_encounter_mons:
            raise OptionError(f"invalid encounter options: required species {required_mons - in_logic_encounter_mons} are inaccessible")
        possible_dexs = in_logic_encounter_mons - self.dexsanity_required.blacklist()
        if self.dexsanity_whitelist.value:
            possible_dexs &= self.dexsanity_whitelist.blacklist()
        else:
            possible_dexs -= self.dexsanity_blacklist.blacklist()
        if len(possible_dexs) + len(self.dexsanity_required.blacklist()) < self.dexsanity.value:
            raise OptionError(f"invalid encounter options: cannot add enough species to fulfill dexsanity value. maximum possible dexsanity species: {len(possible_dexs) + len(self.dexsanity_required.blacklist())}")
        if self.randomize_starters:
            if 0 < len(self.starter_whitelist.value) < 3:
                raise OptionError(f"starter whitelist must contain at least three values")
            elif len(self.starter_whitelist.value) == 0:
                species_set = having_two_level_evos if self.require_two_level_evolution_starters else species.keys()
                if len(species_set - self.starter_blacklist.blacklist()) < 3:
                    raise OptionError(f"starter blacklist too restrictive")

        if 0 < len(self.trainersanity_whitelist.value):
            if len(self.trainersanity_whitelist.value | self.trainersanity_required.value) < self.trainersanity.value:
                raise OptionError("trainersanity whitelist does not have enough trainers")
        elif len((set(in_game_trainer_labels) - self.trainersanity_blacklist.value) | self.trainersanity_required.value) < self.trainersanity.value:
            raise OptionError("trainersanity blacklist is too restrictive")
        if len(self.trainersanity_required.value) > self.trainersanity.value:
            raise OptionError(f"more trainersanity locations are required ({len(self.trainersanity_required.value)}) than alloted ({self.trainersanity.value})")

    def save_options(self) -> MutableMapping[str, Any]:
        return self.as_dict(*slot_data_options)

    def load_options(self, slot_data: Mapping[str, Any]) -> None:
        for key in slot_data_options:
            if isinstance(getattr(self, key), OptionSet):
                getattr(self, key).value = frozenset(slot_data[key])
            else:
                getattr(self, key).value = slot_data[key]

OPTION_GROUPS = [
    OptionGroup(
        "Item Shuffles",
        [
            RandomizeOverworlds,
            RandomizeHiddenItems,
            RandomizeNpcGifts,
            RandomizeKeyItems,
            RandomizeHms,
            RandomizeBadges,
            RandomizeRods,
            RandomizeBicycle,
            RandomizeRunningShoes,
            RandomizePokedex,
            RandomizeTimeItems,
            RandomizeSoundsItems,
            RandomizeFlyItems,
            RandomizePokegearCards,
        ],
    ),
    OptionGroup(
        "Roadblocks",
        [
            RequireRestoredPowerForMagnetTrain,
            BlueReturnViridianBadgeRequirement,
        ],
    ),
    OptionGroup(
        "Logic Tweaks",
        [
            VisibilityHmLogic,
            DowsingMachineLogic,
        ],
    ),
    OptionGroup(
        "Starters",
        [
            RandomizeStarters,
            RequireTwoLevelEvolutionStarters,
            StarterWhitelist,
            StarterBlacklist,
            RandomizeMarillInIntro,
        ],
    ),
    OptionGroup(
        "Pokémon",
        [
            RandomizeEncounters,
            InLogicEncounters,
            EncounterSpeciesBlacklist,
            DexsanityCount,
            DexsanityMode,
            DexsanityBlacklist,
            DexsanityWhitelist,
            DexsanityRequired,
            InLogicEvolutionMethods,
            APItemsShopInAPHelper,
            ReusableTms,
            MoveRandomization,
            MossyRockLocations,
            IcyRockLocations,
            MagneticFieldLocations,
        ],
    ),
    OptionGroup(
        "Trainers",
        [
            TrainersanityCount,
            TrainersanityWhitelist,
            TrainersanityBlacklist,
            TrainersanityRequired,
            RandomizeTrainerParties,
            TrainerPartyBlacklist,
        ],
    ),
    OptionGroup(
        "HMs",
        [
            RemoveBadgeRequirement,
            TMHMCompatibility,
            AddHMReader,
            HMReaderMode,
        ],
    ),
    OptionGroup(
        "Quality of Life",
        [
            GameOptions,
            BlindTrainers,
            HMCutIns,
            FPS60,
            NormalizeEncounters,
            InstantText,
            HoldAToAdvance,
            AlwaysCatch,
            GuaranteedEscape,
            TalkTrainersWithoutFight,
            ExpMultiplier,
            AddMasterRepel,
            ItemNotificationsMask,
            RequireFlyItemsForFlight,
            FastFishing,
        ],
    ),
]
