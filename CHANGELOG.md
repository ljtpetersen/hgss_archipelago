# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.7] - TBD
### Added
* The tide state of the Lake of Rage is now reported in the player position bounce packet.
* There are now item groups containing all HMs and Field Moves.
* The names of notable TMs and HMs now contain the name of the move in addition to the TM/HM number.
* TMs and HMs can now be hinted for by either move name (i.e. "Surf", "Flash") or TM/HM number (i.e. "HM03", "TM70").
### Changed
* Ilex Forest - Item from Charcoal Maker now logically requires clearing Slowpoke Well to look better on the PopTracker.
* Improved clarity and consistency of the names of many locations.
* When patching, patches generated with compatible previous versions may use the new base patches.
* Standardized Fly Region item names with FireRed/LeafGreen.
* Improved clarity of Fly Region location names.
### Fixed
* Fixed the Fly Region for Safari Zone Gate being shuffled with Kanto fly unlocks instead of Johto.
* Fixed the hidden item on Route 30 missing a rule requiring the player to deliver the Mystery Egg or use Cut.
* Fixed some Fly Region locations having incorrect access rules.
* Ariana now shows up in the Radio Tower before defeating Archer.
* Team Rocket no longer overrides the radio.
* Hold A to advance now works properly for certain locations.
* Night fishing now depends on AP time rather than emulator time.
* Fly Region logic connections now accurately reflect the exact maps you fly to.
* Fixed flag clearing with `/game_debug`.
* Fixed Route 2 North encounters incorrectly not being in logic.
* Fixed certain location names being inaccurate descriptions.
* Fixed the logic for Cinnabar Gym incorrectly connecting it to the west side of Seafoam Islands instead of east.
* Blue now leaves Cinnabar Island correctly if you talk to him after defeating Red.
* Prof. Oak now appears in Olivine if you defeat Red before clearing the Pokémon League.
* The Pokémon League event is not set if you defeat Red.
* The rules are now adjusted for defeating Red instead of clearing the Pokémon League.
* The Battle Frontier fly exit now accounts for obtaining the vanilla fly region from the trainer house.
* Ho-Oh no longer appears after clearing the Pokémon League in HeartGold.
* Fixed the logic for the hidden item in Cliff Edge Gate incorrectly requiring the roadblock to be removed.
* Fixed the logic for the catching tutorial gift not requiring the player to deliver the Mystery Egg.
* Fixed various encounter labels unnecessarily or inaccurately specifying cardinal directions.
* Fixed the unused water encounter tables in Cerulean Cave 2F being in logic.
* Kanto battle music now plays even if the player has not yet reached Vermilion.
* The correct Pokémon name is buffered when using field moves.
* The rival in the Pokémon League will be present on every week day.

## [0.0.6] - 2026-09-02
### Added
* Event, position, species tracking to the client.
### Fixed
* Fixed a part of the setup guide mentioning Platinum instead of HeartGold/SoulSilver.
* Removed references to Pokémon Platinum in a few places.
* Night fishing encounters are now properly handled.
* HM accessibility is now properly checked.
* NPCs in Goldenrod Tunnel B1F are now accessible during the Team Rocket Radio Tower Event.
* Trainers in S.S. Aqua that originally disappeared after the first voyage now remain.
* OOL encounters in slot data are now filled correctly.
* Seeds with unrandomized badges now generate properly.

## [0.0.5] - 2026-08-30
### Added
* `game_debug` client command.
### Fixed
* Removed holdovers from Platinum in some option descriptions.
* Fixed `legendaries` blacklist shorthand not working.
* Fixed various minor typographical errors in some option descriptions.
* Fixed description of `dexsanity_required` inaccurately describing the effect of the `legendaries` keyword.
* Requirement of using Cut to access Route 14 - Item from Woman in Grass Patch after Showing Chansey has been added.
* Fixed issues relating to New Bark East exit.
* Fixed Kimono Girls' trainersanity locations.
* Fixed S.S. Anne softlock if initially travelling from Vermilion.
* Fixed the crash with the "SET TIME" menu when within the starting room, before receiving the starting items.
* Fixed issues relating to Copycat and the Lost Item.
* Fixed issues regarding receiving the Clear/Tidal bell in the rooms containing to their legendaries.
* Fixed issue with Ethan/Lyra's theme after the catching tutorial.
* Fixed hardlock when talking to NPC in Fuchsia Pokémon Center.
* Fixed S.S. Ticket location in Prof. Elm's lab.

## [0.0.4] - 2026-08-26
### Fixed
* Corrected logic rules on connections between Viridian Forest, Route 2, and Pewter City.
* Client now supports proper versions.
* TM moves for species learnsets are properly obtained.

## [0.0.3] - 2026-08-25
### Fixed
* Requirement of defeating the league to travel upwards through the Route 40 Battle Frontier gatehouse has been added.
* Requirement of obtaining the Mystery Egg to reach the northwest part of Route 30 has been added.
* Logic can now expect obtaining Escape Ropes from Celadon Department Store.
* Logic can now expect obtaining Vitamins from Celadon Department Store and Safari Zone Gate.
* Corrected the description of the `icy_rock_locations` option to mention Seafoam Islands and Ice Path.
* Requirement of using Surf to reach Cerulean City - Hidden Item in Water Near Cerulean Cave has been added.
* Correct remote items option is now loaded in client.
* Mr. Pokémon now checks for the Red Scale itself, instead of the location where it is received.
* The magnet train stations now respect the `require_restored_power_for_magnet_train` option.

## [0.0.2] - 2026-08-23
### Fixed
* Necessary options are properly added to slot data for UT regen.

## [0.0.1] - 2026-08-23
The first release of this project.

[0.0.6]: https://github.com/ljtpetersen/apnds/compare/v0.0.5...v0.0.6
[0.0.5]: https://github.com/ljtpetersen/apnds/compare/v0.0.4...v0.0.5
[0.0.4]: https://github.com/ljtpetersen/apnds/compare/v0.0.3...v0.0.4
[0.0.3]: https://github.com/ljtpetersen/apnds/compare/v0.0.2...v0.0.3
[0.0.2]: https://github.com/ljtpetersen/apnds/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/ljtpetersen/platinum_archipelago/releases/tag/v0.0.1

