r"""Offline integration checks for the ValScanner pregame-loadouts roster path.

Run with: .venv\Scripts\python.exe -B -m unittest test_pregame_enemies -v
All Riot requests, account data, and match detection are mocked.
"""

import ast
import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.api_client import ValoRank
from core.party_tracker import PartyTracker
from core.skins import SkinHandler
from core.weapons import WEAPON_IDS


class MockResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status
        self.headers = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def text(self):
        return json.dumps(self.payload)

    async def json(self, **kwargs):
        return copy.deepcopy(self.payload)


class MockRiotSession:
    def __init__(self):
        self.calls = []
        self.loadouts = {"Loadouts": []}
        self.live_loadouts = {"Loadouts": []}
        self.loadouts_status = 200
        self.names_status = 200
        self.names_payload = None
        self.failed_players = set()
        self.failed_details = set()
        self.no_history = set()

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if "/pregame/" in url and url.endswith("/loadouts"):
            return MockResponse(self.loadouts, self.loadouts_status)
        if "/core-game/" in url and url.endswith("/loadouts"):
            return MockResponse(self.live_loadouts)
        if url.endswith("/name-service/v2/players"):
            assert method == "PUT", method
            payload = self.names_payload
            if payload is None:
                payload = [
                    {"Subject": puuid, "GameName": f"Player-{puuid}", "TagLine": "MOCK"}
                    for puuid in kwargs["json"]
                ]
            return MockResponse(payload, self.names_status)
        if "/competitiveupdates?" in url:
            return MockResponse({"Matches": [{"RankedRatingEarned": 17}]})
        if "/mmr/v1/players/" in url:
            puuid = url.rsplit("/", 1)[-1]
            if puuid in self.failed_players:
                return MockResponse({"error": "mock unavailable"}, 503)
            return MockResponse({
                "LatestCompetitiveUpdate": {
                    "SeasonID": "act",
                    "TierAfterUpdate": 13,
                    "RankedRatingAfterUpdate": 42,
                },
                "QueueSkills": {"competitive": {"SeasonalInfoBySeasonID": {
                    "act": {"WinsByTier": {"13": 3}},
                }}},
            })
        if "/match-history/" in url:
            puuid = url.split("/history/", 1)[1].split("?", 1)[0]
            if puuid in self.no_history:
                return MockResponse({"Total": 0, "History": []})
            return MockResponse({"Total": 7, "History": [{"MatchID": f"history-{puuid}"}]})
        if "/match-details/" in url:
            puuid = url.split("/matches/history-", 1)[1]
            if puuid in self.failed_details:
                return MockResponse({"error": "mock details unavailable"}, 503)
            return MockResponse({
                "players": [{
                    "subject": puuid,
                    "accountLevel": 55,
                    "teamId": "Blue",
                    "stats": {"score": 2600, "roundsPlayed": 13, "kills": 15, "deaths": 10},
                }],
                "teams": [{"teamId": "Blue", "won": True}],
                "roundResults": [{"playerStats": [{
                    "subject": puuid,
                    "damage": [{"legshots": 0, "bodyshots": 3, "headshots": 1}],
                }]}],
            })
        raise AssertionError(f"Unexpected request: {method} {url}")

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)


class PregameEnemyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import asyncio

        self.output = io.StringIO()
        self.stdout_patch = redirect_stdout(self.output)
        self.stdout_patch.__enter__()
        self.addCleanup(self.stdout_patch.__exit__, None, None, None)
        self.session = MockRiotSession()
        self.match_id = "mock-match"
        self.phase = "pregame"
        self.ally_team = "Blue"
        self.allies = [f"ally-{index}" for index in range(1, 6)]
        self.enemies = [f"enemy-{index}" for index in range(1, 6)]
        self.pregame = {
            "AllyTeam": {"TeamID": self.ally_team, "Players": [
                {"Subject": puuid, "CharacterID": "ally-agent"} for puuid in self.allies
            ]},
            "EnemyTeam": None,
            "Mode": "/Game/GameModes/Bomb/BombGameMode.BombGameMode_C",
            "GamePodID": "aresriot.aws-rclusterprod-euc1-1.eu-gp-frankfurt-1",
            "IsRanked": True,
        }
        self.set_loadout_players(self.allies + self.enemies)
        self.skin = SkinHandler.__new__(SkinHandler)
        self.skin.skins = None
        self.skin.skins_pre = None
        self.skin.converted_skins = {}
        self.skin.converted_buddies = {}
        self.skin._lock = asyncio.Lock()
        uuid = SimpleNamespace(
            agent_uuid_function=lambda: None,
            season_uuid_function=lambda: None,
            current_season=lambda: "act",
            season_converter=lambda value: "e9a1",
            agent_converter=lambda value: {
                "ally-agent": "Jett", "enemy-agent": "Sova", "live-agent": "Raze",
            }.get(value),
        )
        for target, value in (
            ("core.api_client.UUIDHandler", uuid),
            ("core.api_client.SkinHandler", self.skin),
            ("core.api_client.PartyTracker.get", PartyTracker()),
            ("core.api_client.ValoRank.get_version_from_log", None),
            ("core.api_client.SharedSession.get", self.session),
        ):
            patcher = patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        detection_patch = patch("core.api_client.MatchDetectionHandler", side_effect=self.make_handler)
        detection_patch.start()
        self.addCleanup(detection_patch.stop)
        self.rank = ValoRank()

    def set_loadout_players(self, puuids):
        self.session.loadouts = {"Loadouts": [
            {"Subject": puuid, "Items": self.cosmetics(f"pregame-{puuid}")}
            for puuid in puuids
        ]}

    @staticmethod
    def cosmetics(skin_id):
        return {WEAPON_IDS["Vandal"]: {"Sockets": {
            "3ad1b2b2-acdb-4524-852f-954a76ddae0a": {"Item": {"ID": skin_id}},
        }}}

    def make_handler(self, **kwargs):
        live = None
        pregame = copy.deepcopy(self.pregame) if self.phase == "pregame" else None
        if self.phase == "live":
            enemy_team = "Red" if self.ally_team == "Blue" else "Blue"
            live = {
                "Players": [
                    {"Subject": puuid, "TeamID": self.ally_team if puuid in self.allies else enemy_team,
                     "CharacterID": "live-agent"}
                    for puuid in self.allies + self.enemies
                ],
                "ModeID": "/Game/GameModes/Bomb/BombGameMode.BombGameMode_C",
                "GamePodID": self.pregame["GamePodID"],
            }
        return SimpleNamespace(
            player_info_retrieval=AsyncMock(return_value=True),
            in_match=self.match_id,
            match_id_header={"Authorization": "Bearer SYNTHETIC", "X-Riot-ClientVersion": "mock-version"},
            player_info=live,
            player_info_pre=pregame,
            region="eu",
            shard="eu",
        )

    async def refresh(self):
        return await self.rank.valo_stats(**{
            "prematch_id" if self.phase == "pregame" else "match_id": self.match_id,
        })

    def assert_two_teams(self):
        self.assertEqual(len(self.rank.frontend_data), 10)
        self.assertEqual(len(set(self.rank.cmp)), 10)
        enemy_team = "Red" if self.ally_team == "Blue" else "Blue"
        for puuid in self.allies:
            self.assertEqual(self.rank.frontend_data[puuid]["team"], self.ally_team)
        for puuid in self.enemies:
            self.assertEqual(self.rank.frontend_data[puuid]["team"], enemy_team)

    async def test_loadout_subjects_reveal_five_enemies_and_hydrate_stats(self):
        self.assertTrue(await self.refresh())
        self.assert_two_teams()
        for puuid in self.allies + self.enemies:
            player = self.rank.frontend_data[puuid]
            self.assertEqual(player["name"], f"Player-{puuid}#MOCK")
            self.assertEqual(player["name_source"], "name_service")
            self.assertEqual(player["rank"], "Gold 2")
            self.assertEqual(player["rr"], 42)
            self.assertEqual(player["kd"], "1.5")
            self.assertEqual(player["skins"]["Vandal"][0], f"pregame-{puuid}")
        self.assertEqual(self.rank.ca["enemy-1"], None)
        self.assertEqual(self.rank.frontend_data["enemy-1"]["agent"], "N/A")
        name_request = next(call for call in self.session.calls if "/name-service/" in call[1])
        self.assertEqual(set(name_request[2]["json"]), set(self.allies + self.enemies))

    async def test_red_ally_team_puts_enemies_on_blue(self):
        self.ally_team = "Red"
        self.pregame["AllyTeam"]["TeamID"] = "Red"
        await self.refresh()
        self.assert_two_teams()

    async def test_duplicate_and_malformed_subjects_do_not_create_extra_players(self):
        self.session.loadouts["Loadouts"] += [
            {"Subject": "enemy-1"}, {"Subject": ""}, {}, None, "invalid",
        ]
        await self.refresh()
        self.assert_two_teams()

    async def test_unavailable_loadouts_keep_allies_then_retry_discovers_enemies(self):
        self.session.loadouts_status = 503
        await self.refresh()
        self.assertEqual(set(self.rank.frontend_data), set(self.allies))
        self.session.loadouts_status = 200
        await self.refresh()
        self.assert_two_teams()

    async def test_malformed_loadouts_keep_allies_without_inventing_enemies(self):
        self.session.loadouts = {"unexpected": []}
        await self.refresh()
        self.assertEqual(set(self.rank.frontend_data), set(self.allies))

    async def test_ally_only_loadouts_do_not_invent_enemy_players(self):
        self.set_loadout_players(self.allies)
        await self.refresh()
        self.assertEqual(set(self.rank.frontend_data), set(self.allies))

    async def test_explicit_enemy_team_is_preserved_when_loadouts_fail(self):
        self.pregame["EnemyTeam"] = {"TeamID": "Red", "Players": [
            {"Subject": puuid, "CharacterID": "enemy-agent"} for puuid in self.enemies
        ]}
        self.session.loadouts_status = 403
        await self.refresh()
        self.assert_two_teams()
        self.assertEqual(self.rank.frontend_data["enemy-1"]["agent"], "Sova")

    async def test_agent_identity_is_used_only_when_supplied_by_loadouts(self):
        self.session.loadouts["Loadouts"][5]["CharacterID"] = "enemy-agent"
        await self.refresh()
        self.assertEqual(self.rank.frontend_data["enemy-1"]["agent"], "Sova")
        self.assertEqual(self.rank.frontend_data["enemy-2"]["agent"], "N/A")

    async def test_missing_name_service_uses_stable_enemy_placeholders(self):
        self.session.names_status = 503
        await self.refresh()
        self.assert_two_teams()
        self.assertEqual(self.rank.frontend_data["enemy-1"]["name"], "Enemy 1")
        self.assertEqual(self.rank.frontend_data["enemy-1"]["agent"], "N/A")
        self.session.names_status = 200
        await self.refresh()
        self.assertEqual(self.rank.frontend_data["enemy-1"]["name"], "Player-enemy-1#MOCK")

    async def test_malformed_name_entries_keep_unknown_values(self):
        self.session.names_payload = [None, "bad", {}, {"Subject": "enemy-1"}, {"Subject": "outsider", "GameName": "bad"}]
        await self.refresh()
        self.assert_two_teams()
        self.assertEqual(self.rank.frontend_data["enemy-1"]["name"], "Enemy 1")

    async def test_repeated_refresh_and_load_more_preserve_names_and_enemy_team(self):
        await self.refresh()
        await self.refresh()
        await self.rank.load_more_matches()
        self.assert_two_teams()
        self.assertEqual(self.rank.frontend_data["enemy-1"]["name"], "Player-enemy-1#MOCK")
        self.assertEqual(self.rank.frontend_data["enemy-1"]["team"], "Red")
        self.assertEqual(sum("/name-service/" in url for _, url, _ in self.session.calls), 1)

    async def test_xmpp_resolved_name_survives_refresh(self):
        await self.refresh()
        self.rank.frontend_data["enemy-1"].update(
            name="XMPP#REAL", game_name="XMPP", tag="REAL", name_source="xmpp", xmpp_name_resolved=True,
        )
        await self.refresh()
        self.assertEqual(self.rank.frontend_data["enemy-1"]["name"], "XMPP#REAL")

    async def test_one_stats_failure_keeps_roster_and_can_retry(self):
        self.session.failed_players.add("enemy-1")
        await self.refresh()
        self.assert_two_teams()
        self.assertNotIn("enemy-1", self.rank.used_puuids)
        self.assertEqual(self.rank.frontend_data["enemy-1"]["rank"], "N/A")
        self.assertEqual(self.rank.frontend_data["enemy-2"]["rank"], "Gold 2")
        await self.rank.load_more_matches()
        self.session.failed_players.clear()
        await self.refresh()
        self.assertEqual(self.rank.frontend_data["enemy-1"]["rank"], "Gold 2")

    async def test_players_without_history_keep_enemy_team_and_name(self):
        self.session.no_history = set(self.allies + self.enemies)
        await self.refresh()
        self.assert_two_teams()
        self.assertEqual(self.rank.frontend_data["enemy-1"]["name"], "Player-enemy-1#MOCK")
        self.assertEqual(self.rank.frontend_data["enemy-1"]["matches"], 0)

    async def test_failed_match_details_do_not_poison_player_cache(self):
        self.session.failed_details.add("enemy-1")
        await self.refresh()
        self.assert_two_teams()
        self.assertNotIn("enemy-1", self.rank.used_puuids)
        self.session.failed_details.clear()
        await self.refresh()
        self.assertEqual(self.rank.frontend_data["enemy-1"]["kd"], "1.5")
        self.assertIn("enemy-1", self.rank.used_puuids)

    async def test_transition_to_live_updates_agents_and_invalidates_pregame_skins(self):
        await self.refresh()
        self.phase = "live"
        self.session.live_loadouts = {"Loadouts": [
            {"Loadout": {"Subject": puuid, "Items": self.cosmetics(f"live-{puuid}")}}
            for puuid in self.allies + self.enemies
        ]}
        await self.refresh()
        self.assert_two_teams()
        self.assertIsNone(self.skin.skins_pre)
        self.assertEqual(self.rank.frontend_data["enemy-1"]["agent"], "Raze")
        self.assertEqual(self.rank.frontend_data["enemy-1"]["name"], "Player-enemy-1#MOCK")
        self.assertEqual(self.rank.frontend_data["enemy-1"]["skins"]["Vandal"][0], "live-enemy-1")

    async def test_next_match_drops_previous_opponents(self):
        await self.refresh()
        self.match_id = "next-match"
        self.set_loadout_players(self.allies)
        await self.refresh()
        self.assertEqual(set(self.rank.frontend_data), set(self.allies))
        self.assertTrue(all(puuid not in self.rank.player_teams for puuid in self.enemies))

    async def test_requeue_cannot_assign_previous_opponents_name_to_self(self):
        tracker = self.rank.party_tracker
        tracker.feed_chunk(1, """<iq><query xmlns='jabber:iq:riotgames:roster'>
            <item jid='ally-1@eu.pvp.net' name='Me' tagline='SELF'/>
            <item jid='enemy-1@eu.pvp.net'><id name='PreviousEnemy' tagline='OLD'/></item>
            </query></iq>""")
        await self.refresh()
        self.assertEqual(self.rank.frontend_data["ally-1"]["name"], "Me#SELF")
        self.assertEqual(self.rank.frontend_data["enemy-1"]["name"], "PreviousEnemy#OLD")
        self.match_id = "next-match"
        self.set_loadout_players(self.allies)
        await self.refresh()
        self.assertEqual(self.rank.frontend_data["ally-1"]["name"], "Me#SELF")
        self.assertNotIn("enemy-1", self.rank.frontend_data)

    async def test_automatic_match_detection_uses_same_pregame_path(self):
        self.assertTrue(await self.rank.valo_stats())
        self.assert_two_teams()

    async def test_existing_ui_groups_mock_roster_into_five_rows_per_side(self):
        await self.refresh()
        source = Path(__file__).parent / "frontend" / "QApplication.py"
        tree = ast.parse(source.read_text(encoding="utf-8-sig"))
        window = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ValorantStatsWindow")
        load_players = next(node for node in window.body if isinstance(node, ast.FunctionDef) and node.name == "load_players")
        env = {"QTimer": SimpleNamespace(singleShot=lambda *args: None)}
        exec(compile(ast.Module(body=[load_players], type_ignores=[]), str(source), "exec"), env)
        facade = SimpleNamespace(
            valo_rank=self.rank, schedule_player_cosmetic_prefetch=lambda players: None,
            populate_team_layout=lambda *args: None, update_metadata=lambda: None,
            refresh_player_row_heights=lambda: None, schedule_remote_player_icons_load=lambda: None,
            left_scroll_area=None, right_scroll_area=None, left_layout=None, right_layout=None,
        )
        env["load_players"](facade, self.rank.frontend_data)
        self.assertEqual(len(facade.left_players), 5)
        self.assertEqual(len(facade.right_players), 5)
        self.assertEqual({player["puuid"] for player in facade.left_players}, set(self.enemies))


if __name__ == "__main__":
    unittest.main()
