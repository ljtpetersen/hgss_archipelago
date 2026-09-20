# data_gen_templates/rules.py
#
# Copyright (C) 2025-2026 James Petersen <m@jamespetersen.ca>
# Licensed under MIT. See LICENSE

from typing import Tuple, TYPE_CHECKING
from BaseClasses import CollectionState
from collections.abc import Callable, Mapping, MutableMapping, MutableSequence, Sequence
from rule_builder.rules import Has, HasAll, HasAny, Rule, True_, False_, HasFromListUnique, Or, And
import operator

from . import Hm, items, locations, species

if TYPE_CHECKING:
    from ..options import PokemonHgssOptions

def create_hm_badge_rule(hm: Hm) -> Rule:
    badge_item = hm.badge_item()
    if badge_item is not None:
        return Has(badge_item)
    else:
        return True_()

class Rules:
    exit_rules: Mapping[Tuple[str, str], Rule]
    location_rules: Mapping[str, Rule]
    encounter_type_rules: Mapping[str, Rule]
    location_type_rules: Mapping[str, Rule]
    common_rules: MutableMapping[str, Callable[..., Rule] | Rule]
    trainer_rules: Mapping[str, Rule]
    opts: "PokemonHgssOptions"
    cached_enc_accessibility_rules: MutableMapping[frozenset[str], Rule]
    
    def __init__(self, common_rules: MutableMapping[str, Callable[..., Rule] | Rule], opts: "PokemonHgssOptions"):
        self.opts = opts
        self.common_rules = common_rules
        self.cached_enc_accessibility_rules = {}
        BADGES = tuple(item.label for item in items.items.values() if "badges" in item.group)
        JOHTO_BADGES = tuple(item.label for item in items.items.values() if "johto_badges" in item.group)
        KANTO_BADGES = tuple(item.label for item in items.items.values() if "kanto_badges" in item.group)
        def badges(n: int) -> Rule:
            return HasFromListUnique(*BADGES, count=n)
        def johto_badges(n: int) -> Rule:
            return HasFromListUnique(*JOHTO_BADGES, count=n)
        def kanto_badges(n: int) -> Rule:
            return HasFromListUnique(*KANTO_BADGES, count=n)
        self.common_rules["badges"] = badges
        self.common_rules["johto_badges"] = johto_badges
        self.common_rules["kanto_badges"] = kanto_badges

    def fill_rules(self):
        # TEMPLATE: COMMON_RULES
        self.exit_rules = {
            # TEMPLATE: EXIT_RULES
        }
        self.location_rules = {
            # TEMPLATE: LOCATION_RULES
        }
        self.location_type_rules = {
            # TEMPLATE: LOCATION_TYPE_RULES
        }
        self.encounter_type_rules = {
            # TEMPLATE: ENCOUNTER_TYPE_RULES
        }
        self.trainer_rules = {
            # TEMPLATE: TRAINER_RULES
        }

    def get_enc_accessibility_rule(self, accessibility: Sequence[str]) -> Rule:
        nmd = frozenset(acc for acc in accessibility if acc in self.encounter_type_rules)
        if nmd in self.cached_enc_accessibility_rules:
            return self.cached_enc_accessibility_rules[nmd]
        if len(nmd) == 0:
            rule = True_()
        else:
            rule = Or(*[self.encounter_type_rules[acc] for acc in accessibility if acc in self.encounter_type_rules])
        self.cached_enc_accessibility_rules[nmd] = rule
        return rule

    def get_pevo_rule(self, pevo: species.PreEvolution, options: "PokemonHgssOptions") -> Rule | None:
        mthd = pevo.method
        reqd_items = [f"mon_{pevo.species}"]
        if mthd.startswith("trade"):
            reqd_items.append(items.items["linking_cord"].label)
        if mthd.endswith("day"):
            reqd_items.append(items.items["daytime"].label)
        elif mthd.endswith("night"):
            reqd_items.append(items.items["nighttime"].label)
        if pevo.item is not None:
            reqd_items.append(pevo.item)
            if not ((options.reusable_tms if pevo.item.startswith("TM") else pevo.item in items.reusable_evo_items) or options.ap_items_shop_in_ap_helper):
                reqd_items.append("event_goldenrod_store")
        elif pevo.other_species is not None:
            reqd_items.append(f"mon_{pevo.other_species}")
        if mthd == "level_magnetic_field":
            reqd_items.append("event_magnetic_field")
        elif mthd == "level_moss_rock":
            reqd_items.append("event_moss_rock")
        elif mthd == "level_ice_rock":
            reqd_items.append("event_ice_rock")
        if mthd in {"level_atk_gt_def", "level_atk_eq_def", "level_atk_lt_def"}:
            reqd_items.append("event_vitamins")
        if "beauty" in mthd or "happiness" in mthd:
            reqd_items.append("event_beauty")

        return HasAll(*reqd_items)

    def get_mon_rule(self, mon: str) -> Rule:
        return Has(f"mon_{mon}")

    def get_once_mon_rule(self, mon: str) -> Rule:
        return Has(f"once_mon_{mon}")
