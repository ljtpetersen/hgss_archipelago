# client.py
#
# Copyright (C) 2026 James Petersen <m@jamespetersen.ca>
# Licensed under MIT. See LICENSE

from collections import deque
from collections.abc import Iterable, Mapping, Set, Sequence
from dataclasses import dataclass
from itertools import batched, chain
from NetUtils import ClientStatus, NetworkItem
from Options import Toggle
from struct import pack_into, unpack_from
import time
from typing import Any, Optional, TYPE_CHECKING, Tuple

import Utils

from .apnds import rom as ndsrom

from .data.event_checks import event_checks
from .data.locations import FlagCheck, LocationCheck, LocationTable, locations, VarCheck
from .data.trainers import trainers, trainer_id_to_trainer_const_name, TrainerCheck
from .data.species import regional_mons, species_id_to_const_name
from .items import get_item_classification
from .locations import raw_id_to_const_name
from .options import Goal, RemoteItems

import worlds._bizhawk as bizhawk
from worlds._bizhawk.client import BizHawkClient

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext, BizHawkClientCommandProcessor

def version_int(version: str) -> int:
    major, minor, rev = (int(s) for s in version.split('.'))
    return (major << 16) | (minor << 8) | rev

AP_MAGIC = b' AP '

prev_version_data: "VersionData" = None # type: ignore

@dataclass(frozen=True)
class VersionData:
    savedata_ptr_offset: int
    vars_flags_offset_in_save: int
    vars_offset_in_vars_flags: int
    vars_flags_size: int
    flags_offset_in_vars_flags: int
    ap_save_offset: int
    recv_item_count_offset_in_ap_save: int
    deathlink_tx_offset: int
    num_blacked_out_offset_in_ap_save: int
    pokedex_offset_in_save: int
    pokedex_size: int
    trainersanity_flags_offset_in_ap_save: int
    trainersanity_flags_count: int
    player_pos_offset: int
    recv_state_offset: int
    remote_item_queue_offset: int
    remote_item_queue_size: int
    remote_item_queue_flags_offset_in_queue: int

    def __post_init__(self) -> None:
        global prev_version_data
        prev_version_data = self

AP_VERSION_DATA: Mapping[int, VersionData] = {
    version_int("0.0.1"): VersionData(
        savedata_ptr_offset=16,
        deathlink_tx_offset=21,
        player_pos_offset=24,
        recv_state_offset=20,
        remote_item_queue_offset=40,
        remote_item_queue_size=64,
        remote_item_queue_flags_offset_in_queue=136,

        vars_flags_offset_in_save=0xDF4,
        vars_offset_in_vars_flags=0,
        vars_flags_size=1112,
        flags_offset_in_vars_flags=736,

        ap_save_offset=0x17FC,
        num_blacked_out_offset_in_ap_save=0,
        recv_item_count_offset_in_ap_save=4,
        trainersanity_flags_offset_in_ap_save=8,
        trainersanity_flags_count=740,

        pokedex_offset_in_save=0x12D4,
        pokedex_size=832,
    ),
    version_int("0.0.2"): prev_version_data,
    version_int("0.0.3"): prev_version_data,
    version_int("0.0.4"): prev_version_data,
    version_int("0.0.5"): prev_version_data,
}

@dataclass(frozen=True)
class VarsFlags:
    flags: bytes
    vars: bytes
    trainersanity_flags: bytes

    def is_checked(self, check: LocationCheck) -> bool:
        if isinstance(check, FlagCheck):
            return self.get_flag(check.id) ^ check.invert
        elif isinstance(check, VarCheck):
            var = self.get_var(check.id)
            if var is not None:
                return check.op(var, check.value)
            else:
                return False
        elif isinstance(check, TrainerCheck):
            return self.get_trainersanity_flag(check.id)
        else:
            return False

    def get_trainersanity_flag(self, flag_id: int) -> bool:
        if flag_id // 8 < len(self.trainersanity_flags):
            return self.trainersanity_flags[flag_id // 8] & (1 << (flag_id & 7)) != 0
        else:
            return False

    def get_flag(self, flag_id: int) -> bool:
        if flag_id > 0 and flag_id // 8 < len(self.flags):
            return self.flags[flag_id // 8] & (1 << (flag_id & 7)) != 0
        else:
            return False

    def get_var(self, var_id: int) -> int | None:
        if var_id - 0x4000 < len(self.vars) // 2:
            var_id -= 0x4000
            return int.from_bytes(self.vars[2 * var_id:2 * (var_id + 1)], byteorder='little')

@dataclass(frozen=True)
class Pokedex:
    data: bytes

    def has_caught_dexsanity(self, id: int, req: bool) -> bool:
        if req:
            if not self.has_regular():
                return False
            if not self.has_national() and species_id_to_const_name[id] not in regional_mons:
                return False
        return self.has_caught(id)

    def has_caught(self, id: int):
        id -= 1
        return (self.data[4 + (id >> 3)] & (1 << (id & 7))) != 0

    def has_seen(self, id: int):
        id -= 1
        return (self.data[68 + (id >> 3)] & (1 << (id & 7))) != 0

    def has_regular(self) -> bool:
        return self.data[822] != 0

    def has_national(self) -> bool:
        return self.data[823] != 0

def dex_bytearray_to_seq(data: bytearray | bytes) -> Sequence[int]:
    return [v
        for v in range(1, 494)
        if (data[(v - 1) >> 3] & (1 << ((v - 1) & 7))) != 0
    ]

def seq_int_bytes(data: Iterable[int], len_per: int) -> bytes:
    return b''.join(v.to_bytes(len_per, 'little') for v in data)

def pack_nibbles(data: Iterable[int]) -> bytes:
    return b''.join((v0 & 0xF | v1 << 4 & 0xF0).to_bytes(1, 'little') for v0, v1 in batched(data, n=2))

@dataclass(frozen=True)
class RemoteItemQueue:
    size: int
    front: int
    back: int

    @staticmethod
    def from_bytes(size: int, data: bytes) -> "RemoteItemQueue":
        return RemoteItemQueue(size, *unpack_from("<2I", data))

    def amount_in_queue(self) -> int:
        if self.front >= self.back:
            return self.front - self.back
        else:
            return self.size + self.front - self.back

    def remaining_capacity(self) -> int:
        return self.size - self.amount_in_queue() - 1

    def get_writes(self, queue_addr: int, new_values: Sequence[NetworkItem], present_queue_flags: bytes, player: int) -> Sequence[Tuple[int, bytes, str]]:
        def item_flags(item: NetworkItem) -> int:
            if item.location <= 0:
                return get_item_classification(item.item).as_flag() | 8
            elif item.player == player:
                return 0
            else:
                return item.flags | 8

        new_front = (self.front + len(new_values)) & (self.size - 1)
        ret = [(queue_addr, new_front.to_bytes(4, 'little'), "ARM9 System Bus")]
        if new_front < self.front:
            first_upper = self.size - self.front
            if first_upper < len(new_values):
                ret.append((queue_addr + 8, seq_int_bytes((v.item for v in new_values[first_upper:]), 2), "ARM9 System Bus"))
                if len(new_values) - first_upper & 1 == 0:
                    ret.append((queue_addr + 8 + self.size * 2, pack_nibbles(item_flags(v) for v in new_values[first_upper:]), "ARM9 System Bus"))
                else:
                    ret.append((queue_addr + 8 + self.size * 2, pack_nibbles(chain((item_flags(v) for v in new_values[first_upper:]), [present_queue_flags[(len(new_values) - first_upper) // 2] >> 4])), "ARM9 System Bus"))
        else:
            first_upper = new_front - self.front
        if first_upper > 0:
            ret.append((queue_addr + 8 + self.front * 2, seq_int_bytes((v.item for v in new_values[:first_upper]), 2), "ARM9 System Bus"))
            item_flag_seq = []
            if self.front & 1 != 0:
                item_flag_seq.append(present_queue_flags[self.front // 2])
            item_flag_seq.extend(item_flags(v) for v in new_values[:first_upper])
            if self.front + first_upper & 1 != 0:
                item_flag_seq.append(present_queue_flags[(self.front + first_upper) // 2] >> 4)
            ret.append((queue_addr + 8 + self.size * 2 + self.front // 2, pack_nibbles(item_flag_seq), "ARM9 System Bus"))
        return ret

class PokemonHgssClient(BizHawkClient):
    game = "Pokemon HeartGold and SoulSilver"
    system = "NDS"
    patch_suffix = (".apheartgold", ".apsoulsilver")
    ap_struct_address: int = 0
    rom_version: int = 0
    goal_check: LocationCheck
    local_checked_locations: Set[int]
    expected_header: bytes

    death_counter: Optional[int]
    previous_death_link: float
    ignore_next_death_link: bool

    notify_setup_complete: bool

    player_name: str | None

    death_link_group: str
    death_link_state: bool
    loaded_death_link: bool

    debug_queue: deque[Mapping[str, Any]]

    def __init__(self):
        super().__init__()

        self.player_name = None

    def initialize_client(self):
        self.local_checked_locations = set()
        self.expected_header = AP_MAGIC * 3 + self.rom_version.to_bytes(length=4, byteorder='little')
        self.death_counter = None
        self.previous_death_link = 0
        self.ignore_next_death_link = False

        self.notify_setup_complete = False

        self.loaded_death_link = False
        self.death_link_group = ""
        self.death_link_state = False

        self.debug_queue = deque()

    async def get_slot_name_and_remote_items(self, ctx: "BizHawkClientContext") -> Tuple[str | None, bool]:
        remote_items: bool = False
        try:
            header = ndsrom.Header((await bizhawk.read(ctx.bizhawk_ctx, [(0, 0x4000, "ROM")]))[0])
            fatb_offset = header.get_le(ndsrom.HeaderField.FATB_ROMOFFSET)
            fatb_size = header.get_le(ndsrom.HeaderField.FATB_BSIZE)
            fatb = (await bizhawk.read(ctx.bizhawk_ctx, [(fatb_offset, fatb_size, "ROM")]))[0]
            fntb_offset = header.get_le(ndsrom.HeaderField.FNTB_ROMOFFSET)
            fntb_size = header.get_le(ndsrom.HeaderField.FNTB_BSIZE)
            fntb = (await bizhawk.read(ctx.bizhawk_ctx, [(fntb_offset, fntb_size, "ROM")]))[0]
            filename_id_map = ndsrom.get_filename_id_map(fntb)
            ap_bin_id = filename_id_map["/ap.bin"]
            ap_bin_start, = unpack_from("<I", fatb, ap_bin_id * 8)
            ap_bin_bytes = (await bizhawk.read(ctx.bizhawk_ctx, [(ap_bin_start, 97, "ROM")]))[0]
            name_end = ap_bin_bytes[:64].find(b'\0')
            remote_items = ap_bin_bytes[64] != 0
            if name_end != -1:
                player_name = ap_bin_bytes[:name_end].decode()
            else:
                player_name = ap_bin_bytes[:64].decode()

            return (player_name, remote_items)
        except UnicodeDecodeError:
            return (None, remote_items)
        except bizhawk.RequestFailedError:
            return (None, remote_items)

    async def validate_rom(self, ctx: "BizHawkClientContext") -> bool:
        from CommonClient import logger
        def remove_commands():
            for command in ["death_link_state", "death_link_group", "game_debug"]:
                if command in ctx.command_processor.commands:
                    del ctx.command_processor.commands[command]

        try:
            rom_name_bytes = (await bizhawk.read(ctx.bizhawk_ctx, [(0, 12, "ROM")]))[0]
            rom_name = bytes([byte for byte in rom_name_bytes if byte != 0]).decode("ascii")
            if rom_name == "POKEMON HG" or rom_name == "POKEMON SS":
                logger.info("ERROR: You appear to be running an unpatched version of Pokémon Platinum. "
                            "You need to generate a patch file and use it to create a patched ROM.")
                remove_commands()
                return False
            elif rom_name.startswith("TRB HGAP") or rom_name.startswith("TRB SSAP"):
                version_bytes = (await bizhawk.read(ctx.bizhawk_ctx, [(0x1000, 4, "ROM")]))[0]
                version = int.from_bytes(version_bytes, 'little')
                if version in AP_VERSION_DATA:
                    self.rom_version = version
                else:
                    logger.info("ERROR: The patch file used to create this ROM is not compatible with "
                                "this client. Double-check your client version against the version being "
                                "by the generator.")
                    remove_commands()
                    return False
            else:
                remove_commands()
                return False
        except UnicodeDecodeError:
            remove_commands()
            return False
        except bizhawk.RequestFailedError:
            remove_commands()
            return False

        self.player_name, remote_items = await self.get_slot_name_and_remote_items(ctx)
        ctx.game = self.game
        if remote_items:
            ctx.items_handling = 0b011
        else:
            ctx.items_handling = 0b001
        self.want_slot_data = True
        self.watcher_timeout = 0.125

        self.initialize_client()

        return True

    async def get_struct_addr(self, ctx: "BizHawkClientContext") -> None:
        from os import environ
        try:
            assert ctx.slot_data is not None
            if "HGSS_DEV_ENV" in environ:
                cands = set()
                import pkgutil
                for name in ["hg_us", "ss_us"]:
                    xmap_bytes = pkgutil.get_data(__name__, f"roms/{name}.xMAP")
                    assert xmap_bytes is not None
                    cands.add(parse_ap_struct_address(xmap_bytes.decode("utf-8").split("\n")))
            else:
                cands = ctx.slot_data["possible_ap_struct_addresses"]
            for addr in cands:
                if 0x2000000 < addr and addr < 0x2400000:
                    header = (await bizhawk.read(ctx.bizhawk_ctx, [(addr, 16, "ARM9 System Bus")]))[0]
                    if header == self.expected_header:
                        self.ap_struct_address = addr
                        print(f"found ap struct at addr {addr:X}")
        except bizhawk.RequestFailedError:
            pass

    async def game_watcher(self, ctx: "BizHawkClientContext") -> None:
        if ctx.server is None or ctx.server.socket.closed or ctx.slot_data is None:
            return

        version_data = AP_VERSION_DATA[self.rom_version]

        if self.ap_struct_address == 0:
            await self.get_struct_addr(ctx)
            return

        self.goal_check = event_checks[Goal.name_lookup[ctx.slot_data["goal"]]]

        if "remote_items" in ctx.slot_data and ctx.slot_data["remote_items"] != RemoteItems.option_off and not ctx.items_handling & 0b010: # type: ignore
            ctx.items_handling = 0b011
            Utils.async_start(ctx.send_msgs([{
                "cmd": "ConnectUpdate",
                "items_handling": ctx.items_handling
            }]))

        if not self.loaded_death_link:
            self.loaded_death_link = True
            if ctx.slot_data.get("death_link", Toggle.option_false) != Toggle.option_true:
                self.death_link_group = ""
                self.death_link_state = False
            else:
                self.death_link_group = ctx.slot_data.get("death_link_group", "")
                self.death_link_state = True
            ctx.command_processor.commands["death_link_state"] = cmd_death_link_state
            ctx.command_processor.commands["death_link_group"] = cmd_death_link_group
            ctx.command_processor.commands["game_debug"] = cmd_game_debug

        try:
            ap_struct_guard = (self.ap_struct_address, self.expected_header, "ARM9 System Bus")
            guards: Mapping[str, Tuple[int, bytes, str]] = {}
            guards["AP STRUCT VALID"] = ap_struct_guard

            actual_header = (await bizhawk.read(ctx.bizhawk_ctx, [(ap_struct_guard[0], 16, "ARM9 System Bus")]))[0]
            if actual_header != self.expected_header:
                self.ap_struct_address = 0
                return

            read_result = await bizhawk.guarded_read(
                ctx.bizhawk_ctx,
                [
                    (self.ap_struct_address + version_data.savedata_ptr_offset, 4, "ARM9 System Bus"),
                ],
                [guards["AP STRUCT VALID"]]
            )

            if read_result is None:
                return

            guards["SAVEDATA PTR"] = (self.ap_struct_address + version_data.savedata_ptr_offset, read_result[0], "ARM9 System Bus")

            await self.handle_death_link(ctx, guards, version_data)

            savedata_ptr = int.from_bytes(guards["SAVEDATA PTR"][1], byteorder='little')

            read_result = await bizhawk.guarded_read(
                ctx.bizhawk_ctx,
                [
                    (savedata_ptr + version_data.ap_save_offset + version_data.recv_item_count_offset_in_ap_save, 4, "ARM9 System Bus"),
                    (self.ap_struct_address + version_data.recv_state_offset, 1, "ARM9 System Bus"),
                    (self.ap_struct_address + version_data.remote_item_queue_offset, 8, "ARM9 System Bus"),
                    (self.ap_struct_address + version_data.remote_item_queue_offset + version_data.remote_item_queue_flags_offset_in_queue, version_data.remote_item_queue_size // 2, "ARM9 System Bus"),
                ],
                [guards["AP STRUCT VALID"], guards["SAVEDATA PTR"]]
            )

            if read_result is None:
                return

            recv_item_count = int.from_bytes(read_result[0], byteorder='little')
            recv_state = read_result[1][0]
            remote_item_queue = RemoteItemQueue.from_bytes(version_data.remote_item_queue_size, read_result[2])
            amount_in_queue = remote_item_queue.amount_in_queue()
            if recv_state == 1 \
                and recv_item_count + amount_in_queue < len(ctx.items_received) \
                and remote_item_queue.remaining_capacity() > 0:
                start_idx = recv_item_count + amount_in_queue
                await bizhawk.guarded_write(
                    ctx.bizhawk_ctx,
                    remote_item_queue.get_writes(
                        self.ap_struct_address + version_data.remote_item_queue_offset,
                        [v for v in ctx.items_received[start_idx:start_idx + remote_item_queue.remaining_capacity()]],
                        read_result[3],
                        ctx.slot),
                    [
                        guards["AP STRUCT VALID"],
                        guards["SAVEDATA PTR"],
                    ]
                )

            read_result = await bizhawk.guarded_read(
                ctx.bizhawk_ctx,
                [
                    (savedata_ptr + version_data.vars_flags_offset_in_save, version_data.vars_flags_size, "ARM9 System Bus"),
                    (savedata_ptr + version_data.pokedex_offset_in_save, version_data.pokedex_size, "ARM9 System Bus"),
                    (savedata_ptr + version_data.ap_save_offset + version_data.trainersanity_flags_offset_in_ap_save, (version_data.trainersanity_flags_count + 7) // 8, "ARM9 System Bus"),
                ],
                [guards["AP STRUCT VALID"], guards["SAVEDATA PTR"]],
            )
            if read_result is None:
                return
            vars_flags_bytes = read_result[0]
            vars_bytes = vars_flags_bytes[version_data.vars_offset_in_vars_flags:version_data.flags_offset_in_vars_flags]
            flags_bytes = vars_flags_bytes[version_data.flags_offset_in_vars_flags:]

            vars_flags = VarsFlags(flags=flags_bytes, vars=vars_bytes, trainersanity_flags=read_result[2])
            pokedex = Pokedex(data=read_result[1])

            local_checked_locations = set()
            game_clear = vars_flags.is_checked(self.goal_check)

            for k in ctx.missing_locations:
                if k >> 16 == LocationTable.DEX:
                    if pokedex.has_caught_dexsanity(k & 0xFFFF, ctx.slot_data["dexsanity_mode"] >= 2):
                        local_checked_locations.add(k)
                elif k >> 16 == LocationTable.TRAINERS:
                    trainer = trainers[trainer_id_to_trainer_const_name[k & 0xFFFF]]
                    if vars_flags.is_checked(trainer.get_check()):
                        local_checked_locations.add(k)
                else:
                    loc = locations[raw_id_to_const_name[k]]
                    if vars_flags.is_checked(loc.check):
                        local_checked_locations.add(k)

            if local_checked_locations != self.local_checked_locations:
                await ctx.check_locations(local_checked_locations)

                self.local_checked_locations = local_checked_locations


            vf_bytearr = bytearray(vars_flags_bytes)
            wrote = False
            old_queue = deque(self.debug_queue)
            to_print = []
            while len(self.debug_queue) > 0:
                data = self.debug_queue.popleft()
                match data["operation"]:
                    case "flag_check":
                        to_print.append(f"flag {data['id_str']} is {'set' if vars_flags.get_flag(data['id']) else 'cleared'}")
                    case "flag_set":
                        to_print.append(f"setting flag {data['id_str']}")
                        flag = data["id"]
                        print(f"{flag // 8}, {len(flags_bytes)}")
                        if flag // 8 < len(flags_bytes):
                            print(f"old: {vf_bytearr[version_data.flags_offset_in_vars_flags + flag // 8]:08b}")
                            vf_bytearr[version_data.flags_offset_in_vars_flags + flag // 8] |= 1 << (flag & 7)
                            print(f"new: {vf_bytearr[version_data.flags_offset_in_vars_flags + flag // 8]:08b}")
                            wrote = True
                    case "flag_clear":
                        to_print.append(f"clearing flag {data['id_str']}")
                        flag = data["id"]
                        if flag // 8 < len(flags_bytes):
                            vf_bytearr[version_data.flags_offset_in_vars_flags + flag // 8] &= ~(1 << (flag & 7))
                    case "var_check":
                        to_print.append(f"variable {data['id_str']}'s value is {vars_flags.get_var(data['id'])}")
                    case "var_set":
                        to_print.append(f"setting variable {data['id_str']}")
                        var = data["id"]
                        if var - 0x4000 < len(vars_bytes) // 2:
                            pack_into("<H", vf_bytearr, (var - 0x4000) * 2, data["value"])
                            wrote = True

            if wrote:
                print("writing changed debug")
                if await bizhawk.guarded_write(
                    ctx.bizhawk_ctx,
                    [(savedata_ptr + version_data.vars_flags_offset_in_save, bytes(vf_bytearr), "ARM9 System Bus")],
                    [
                        guards["AP STRUCT VALID"],
                        guards["SAVEDATA PTR"],
                        (savedata_ptr + version_data.vars_flags_offset_in_save, vars_flags_bytes, "ARM9 System Bus"),
                    ]
                ):
                    from CommonClient import logger
                    for v in to_print:
                        logger.info(v)
                else:
                    self.debug_queue = old_queue
            else:
                from CommonClient import logger
                for v in to_print:
                    logger.info(v)

            if not ctx.finished_game and game_clear:
                ctx.finished_game = True
                await ctx.send_msgs([{
                    "cmd": "StatusUpdate",
                    "status": ClientStatus.CLIENT_GOAL,
                }])

        except bizhawk.RequestFailedError:
            pass

    def on_package(self, ctx: "BizHawkClientContext", cmd: str, args: dict[str, Any]) -> None:
        super().on_package(ctx, cmd, args)
        
        from CommonClient import logger

        if cmd == "Bounced":
            tags = args.get("tags", [])
            if self.death_link_group and "DeathLink" + self.death_link_group in tags and ctx.last_death_link != args["data"]["time"]:
                ctx.last_death_link = max(args["data"]["time"], ctx.last_death_link)
                text = args["data"].get("cause", "")
                if text:
                    logger.info("DeathLink: " + text)
                else:
                    logger.info("DeathLink: Received from " + args["data"]["source"])

    async def handle_death_link(self, ctx: "BizHawkClientContext", guards: Mapping[str, Tuple[int, bytes, str]], version_data: VersionData) -> None:
        if not self.death_link_state:
            old_tags = ctx.tags.copy()
            ctx.tags = {t for t in ctx.tags if not t.startswith("DeathLink")}
            if old_tags != ctx.tags and ctx.server and not ctx.server.socket.closed:
                await ctx.send_msgs([{"cmd": "ConnectUpdate", "tags": ctx.tags}])
            return

        if "DeathLink" + self.death_link_group not in ctx.tags:
            old_tags = ctx.tags.copy()
            ctx.tags = {t for t in ctx.tags if not t.startswith("DeathLink")}
            ctx.tags.add("DeathLink" + self.death_link_group)
            if old_tags != ctx.tags and ctx.server and not ctx.server.socket.closed:
                await ctx.send_msgs([{"cmd": "ConnectUpdate", "tags": ctx.tags}])
            self.previous_death_link = ctx.last_death_link

        if self.previous_death_link < ctx.last_death_link:
            self.previous_death_link = ctx.last_death_link
            if self.ignore_next_death_link:
                self.ignore_next_death_link = False
            else:
                if await bizhawk.guarded_write(
                    ctx.bizhawk_ctx,
                    [(self.ap_struct_address + version_data.deathlink_tx_offset, b'\x01', "ARM9 System Bus")],
                    [guards["AP STRUCT VALID"]],
                ):
                    return

        savedata_ptr = int.from_bytes(guards["SAVEDATA PTR"][1], byteorder='little')
        res = await bizhawk.guarded_read(
            ctx.bizhawk_ctx,
            [
                (savedata_ptr + version_data.ap_save_offset + version_data.num_blacked_out_offset_in_ap_save, 4, "ARM9 System Bus"),
            ],
            [guards["AP STRUCT VALID"], guards["SAVEDATA PTR"]]
        )
        if res is None:
            return

        num_blacked_out = int.from_bytes(res[0], 'little')
        if self.death_counter is None:
            self.death_counter = num_blacked_out
        elif num_blacked_out > self.death_counter:
            if ctx.server and ctx.server.socket:
                from CommonClient import logger
                logger.info("DeathLink: Sending death to your friends...")
                ctx.last_death_link = time.time()
                await ctx.send_msgs([{
                    "cmd": "Bounce",
                    "tags": ["DeathLink" + self.death_link_group],
                    "data": {
                        "time": ctx.last_death_link,
                        "source": ctx.player_names[ctx.slot],
                        "cause": f"{ctx.player_names[ctx.slot]} is out of usable POKéMON! " # type: ignore
                                 f"{ctx.player_names[ctx.slot]} blacked out!", # type: ignore
                    },
                }])
            self.ignore_next_death_link = True
            self.death_counter = num_blacked_out

    async def set_auth(self, ctx: "BizHawkClientContext") -> None:
        if self.player_name is not None:
            ctx.auth = self.player_name

def cmd_death_link_state(self: "BizHawkClientCommandProcessor", state: str | None = None) -> None:
    """Change the death link state. Enter the command without any arguments to print the current state. States are on or off."""
    from CommonClient import logger

    handler: PokemonHgssClient = self.ctx.client_handler # type: ignore
    assert isinstance(handler, PokemonHgssClient)
    if state is None:
        logger.info("Current death link state: " + ("on" if handler.death_link_state else "off"))
    elif state.lower() == "on":
        handler.death_link_state = True
        logger.info("Death link state set to on")
    elif state.lower() == "off":
        handler.death_link_state = False
        logger.info("Death link state set to off")

def cmd_death_link_group(self: "BizHawkClientCommandProcessor", group: str | None = None) -> None:
    """Change the death link group. Enter the comand without any arguments to print the current group. Use "" as the argument for the default group."""
    from CommonClient import logger

    handler: PokemonHgssClient = self.ctx.client_handler # type: ignore
    assert isinstance(handler, PokemonHgssClient)
    if group is None:
        logger.info(f"Current death link group: \"{handler.death_link_group}\"")
    else:
        handler.death_link_group = group
        logger.info(f"Set death link group to \"{group}\"")

HEXNUMS = {chr(ord('A') + i) for i in range(6)} | {chr(ord('a') + i) for i in range(6)} | {chr(ord('0') + i) for i in range(10)}

def parse_ap_struct_address(xmap: Sequence[str]) -> int:
    for l in xmap:
        if "gAP" not in l:
            continue
        if all(c in HEXNUMS for c in l[2:10]):
            return int(l[2:10], 16)
    raise ValueError("ap global not present in xmap")

def parse_int_including_base(s: str) -> int:
    s = s.lower().strip()
    if s.startswith("0x"):
        return int(s[2:], 16)
    elif s.startswith("0o"):
        return int(s[2:], 8)
    elif s.startswith("0b"):
        return int(s[2:], 2)
    else:
        return int(s)

def cmd_game_debug(self: "BizHawkClientCommandProcessor", *args) -> None:
    """Game debug. Enter without arguments to print the usage."""
    from CommonClient import logger

    handler: PokemonHgssClient = self.ctx.client_handler # type: ignore

    assert isinstance(handler, PokemonHgssClient)
    if len(args) == 0:
        logger.info("/game_debug [flag/var id] [flag: check/set/clear, var: check/set] [var set value]")
        return
    try:
        id = parse_int_including_base(args[0])
    except ValueError:
        logger.error("first parameter of game debug is not an integer")
        return
    if id < 0x4000:
        # flag
        if len(args) == 1:
            handler.debug_queue.append({"operation": "flag_check", "id": id, "id_str": args[0]})
        elif len(args) != 2:
            logger.error("unexpected extra parameter(s) passed to game debug")
        else:
            op = args[1].lower().strip()
            if op in {"check", "set", "clear"}:
                handler.debug_queue.append({"operation": "flag_" + op, "id": id, "id_str": args[0]})
            else:
                logger.error("unexpected flag operation: " + args[1].strip())
    else:
        # var
        if len(args) == 1:
            handler.debug_queue.append({"operation": "var_check", "id": id, "id_str": args[0]})
        elif len(args) != 2:
            if args[1].lower().strip() == "set":
                try:
                    handler.debug_queue.append({"operation": "var_set", "id": id, "value": parse_int_including_base(args[2]), "id_str": args[0]})
                except ValueError:
                    logger.error("parameter of game debug variable set is not an integer")
            else:
                logger.error("unexpected extra parameter(s) passed to game debug")
        else:
            if args[1].lower().strip() == "check":
                handler.debug_queue.append({"operation": "var_check", "id": id, "id_str": args[0]})
            else:
                logger.error("unexpected variable operation: " + args[1].strip())
