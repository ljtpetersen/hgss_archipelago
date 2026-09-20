# data_gen_templates/trainers.py
#
# Copyright (C) 2026 James Petersen <m@jamespetersen.ca>
# Licensed under MIT. See LICENSE

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .locations import LocationCheck, VarCheck, FlagCheck, LocationTable
from .regions import regions

@dataclass(frozen=True)
class PartyMember:
    species: str
    level: int
    num_moves: int

@dataclass(frozen=True)
class TrainerData:
    id: int
    label: str
    party: Sequence[PartyMember]
    check: LocationCheck | None = None
    parent_region: str | None = None
    requires_national_dex: bool = False
    in_fight_area: bool = False

    def get_raw_id(self) -> int:
        return LocationTable.TRAINERS << 16 | self.id

    def get_check(self) -> LocationCheck:
        if self.check is not None:
            return self.check
        else:
            return TrainerCheck(self.id)

trainers: Mapping[str, TrainerData] = {
    # TEMPLATE: TRAINERS
}

def trainer_party_supporting_starters(name: str) -> Sequence[PartyMember]:
    if name.startswith("rival_silver") or name.startswith("partner_rival"):
        return [memb
            for memb in trainers[name + "_totodile"].party
            if memb in trainers[name + "_cyndaquil"].party and memb in trainers[name + "_chikorita"].party
        ]
    else:
        return trainers[name].party

trainer_id_to_trainer_const_name: Mapping[int, str] = {v.id:k for k, v in trainers.items()}

def get_in_game_trainers() -> Sequence[str]:
    ret = set()
    for data in regions.values():
        ret |= set(data.trainers)
    return list(ret)

def remove_starter_suffix(s: str) -> str:
    return s.removesuffix("_totodile").removesuffix("_cyndaquil").removesuffix("_chikorita")

def add_starter_suffix(s: str) -> str:
    if s.startswith("rival_silver") or s.startswith("partner_rival"):
        return s + "_chikorita"
    else:
        return s

in_game_trainers: Sequence[str] = get_in_game_trainers()

in_game_trainer_labels: Sequence[str] = list({trainers[add_starter_suffix(v)].label for v in in_game_trainers})

trainer_name_to_trainer_const_name: Mapping[str, str] = {v.label:remove_starter_suffix(k) for k, v in trainers.items()}

trainer_raw_id_to_trainer_const_name: Mapping[int, str] = {v.get_raw_id():remove_starter_suffix(k) for k, v in trainers.items()}
