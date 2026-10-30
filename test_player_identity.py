"""Offline regressions for peak-act labels and XMPP identity boundaries."""

import base64
import json
import unittest

from core.party_tracker import PartyTracker
from core.valorant_uuid import UUIDHandler


class SeasonLabelTests(unittest.TestCase):
    def setUp(self):
        self.handler = UUIDHandler()

    def convert(self, title=None, asset_path=""):
        self.handler.season_uuids = {"data": [
            {"uuid": "act", "title": title, "assetPath": asset_path},
        ]}
        return self.handler.season_converter("act").upper()

    def test_year_prefix_survives_every_act(self):
        for year in (25, 26, 27):
            for act, roman in enumerate(("I", "II", "III", "IV", "V", "VI"), 1):
                with self.subTest(year=year, act=act):
                    self.assertEqual(self.convert(f"V{year} // ACT {roman}"), f"V{year}A{act}")

    def test_legacy_episode_titles(self):
        for episode, roman in enumerate(("I", "II", "III", "IV", "V", "VI"), 1):
            with self.subTest(episode=episode):
                self.assertEqual(self.convert(f"EPISODE {roman} // ACT III"), f"E{episode}A3")

    def test_legacy_asset_path_and_unknown_season(self):
        self.assertEqual(self.convert(asset_path="ShooterGame/Content/Seasons/Season_Episode1_Act1_DataAsset"), "E1A1")
        self.assertEqual(self.handler.season_converter("missing"), "Unranked")


class PlayerIdentityTests(unittest.TestCase):
    @staticmethod
    def payload():
        return base64.b64encode(json.dumps({"partyId": "current-party"}).encode()).decode()

    def presence(self, puuid, name="", extra=""):
        identity = f"<id name='{name}' tagline='REAL'/>" if name else ""
        return (f"<presence from='{puuid}@eu.pvp.net'>"
                f"{extra}{identity}<valorant><p>{self.payload()}</p></valorant></presence>")

    @staticmethod
    def player(puuid):
        return {"puuid": puuid, "name": "Placeholder", "xmpp_name_resolved": False}

    def assert_name(self, tracker, puuid, expected):
        player = self.player(puuid)
        tracker.enrich_frontend_data({puuid: player})
        self.assertEqual(player["name"], expected)

    def test_self_closing_roster_item_cannot_take_next_players_name(self):
        tracker = PartyTracker()
        tracker.feed_chunk(1, """<iq><query xmlns='jabber:iq:riotgames:roster'>
            <item jid='self@eu.pvp.net' name='Me' tagline='SELF'/>
            <item jid='previous-player@eu.pvp.net'><id name='PreviousPlayer' tagline='OLD'/></item>
            <item jid='friend@eu.pvp.net' name='Friend' tagline='FRIEND'/>
            </query></iq>""")
        self.assert_name(tracker, "self", "Me#SELF")
        self.assert_name(tracker, "previous-player", "PreviousPlayer#OLD")
        self.assert_name(tracker, "friend", "Friend#FRIEND")

    def test_presence_roster_items_keep_separate_identities(self):
        tracker = PartyTracker()
        tracker.feed_chunk(1, self.presence("room@ares-parties", extra="""
            <item jid='self@eu.pvp.net' name='Me' tagline='SELF'/>
            <item jid='previous-player@eu.pvp.net'><id name='PreviousPlayer' tagline='OLD'/></item>
            """))
        self.assert_name(tracker, "self", "Me#SELF")
        self.assert_name(tracker, "previous-player", "PreviousPlayer#OLD")

    def test_previous_message_cannot_supply_current_presence_identity(self):
        tracker = PartyTracker()
        tracker.feed_chunk(1, "<message><id name='PreviousPlayer' tagline='OLD'/></message>")
        tracker.feed_chunk(1, self.presence("self"))
        self.assert_name(tracker, "self", "Placeholder")
        self.assertFalse(tracker._presence_by_puuid["self"]["game_name"])

    def test_self_closing_presence_cannot_supply_next_players_subject(self):
        tracker = PartyTracker()
        tracker.feed_chunk(1, "<presence from='previous-player@eu.pvp.net'/>" + self.presence("self", "Me"))
        self.assert_name(tracker, "self", "Me#REAL")
        self.assertIsNone(tracker._get_player_metadata_by_puuid("previous-player"))

    def test_fragmented_and_batched_stanzas_keep_player_mapping(self):
        xml = ("<message><id name='Old' tagline='OLD'/></message>"
               + self.presence("self", "Me") + self.presence("other", "Other"))
        for split in range(len(xml) + 1):
            with self.subTest(split=split):
                tracker = PartyTracker()
                tracker.feed_chunk(1, xml[:split])
                tracker.feed_chunk(1, xml[split:])
                self.assert_name(tracker, "self", "Me#REAL")
                self.assert_name(tracker, "other", "Other#REAL")

    def test_socket_buffers_are_isolated(self):
        tracker = PartyTracker()
        xml = self.presence("other", "Other")
        tracker.feed_chunk(1, xml[:30])
        tracker.feed_chunk(2, self.presence("self", "Me"))
        tracker.feed_chunk(1, xml[30:])
        self.assert_name(tracker, "self", "Me#REAL")
        self.assert_name(tracker, "other", "Other#REAL")


if __name__ == "__main__":
    unittest.main()
