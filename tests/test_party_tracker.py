import base64
import json
import unittest

from core.party_tracker import PartyTracker


def encode_b64_json(payload):
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def make_private_jwt(private_payload):
    header = encode_b64_json({"alg": "none", "typ": "JWT"}).rstrip("=")
    payload = encode_b64_json({"private": encode_b64_json(private_payload)}).rstrip("=")
    return f"{header}.{payload}."


def make_presence_stanza(game_name, game_tag, puuid, payload):
    encoded_payload = encode_b64_json(payload)
    return (
        f"<presence from='{puuid}@ares.pvp.net/RC-123' to='self@ares.pvp.net/client'>"
        f"<games><valorant><p>{encoded_payload}</p></valorant></games>"
        f"<id name='{game_name}' tagline='{game_tag}' /></presence>"
    )


def make_presence_stanza_without_id(puuid, payload):
    encoded_payload = encode_b64_json(payload)
    return (
        f"<presence from='{puuid}@ares.pvp.net/RC-123' to='self@ares.pvp.net/client'>"
        f"<games><valorant><p>{encoded_payload}</p></valorant></games>"
        "</presence>"
    )


def make_roster_stanza(*items):
    return (
        "<iq type='result' id='roster-1'>"
        "<query xmlns='jabber:iq:riotgames:roster'>"
        + "".join(items)
        + "</query></iq>"
    )


class PartyTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tracker = PartyTracker()

    def test_fragmented_presence_chunk_is_combined_and_queue_state_is_decoded(self):
        stanza = make_presence_stanza(
            "QueueBuddy",
            "EUW",
            "friend-puuid",
            {
                "partyId": "party-1",
                "privateJwt": make_private_jwt(
                    {
                        "partyId": "party-1",
                        "queueId": "competitive",
                        "partyState": "MATCHMAKING",
                        "sessionLoopState": "MENUS",
                    }
                ),
            },
        )

        halfway = len(stanza) // 2
        self.assertFalse(self.tracker.feed_chunk(1, stanza[:halfway]))
        self.assertTrue(self.tracker.feed_chunk(1, stanza[halfway:]))

        presence = self.tracker.get_presence(puuid="friend-puuid")
        self.assertEqual(presence["queue_id"], "competitive")
        self.assertTrue(presence["is_queueing"])
        self.assertEqual(presence["party_id"], "party-1")

    def test_repeated_identical_presence_does_not_retrigger(self):
        stanza = make_presence_stanza(
            "QueueBuddy",
            "EUW",
            "friend-puuid",
            {
                "partyId": "party-1",
                "queueId": "competitive",
                "partyState": "MATCHMAKING",
                "sessionLoopState": "MENUS",
            },
        )

        self.assertTrue(self.tracker.feed_chunk(1, stanza))
        self.assertFalse(self.tracker.feed_chunk(1, stanza))

    def test_queue_stop_updates_presence_state(self):
        start_stanza = make_presence_stanza(
            "QueueBuddy",
            "EUW",
            "friend-puuid",
            {
                "partyId": "party-1",
                "queueId": "competitive",
                "partyState": "MATCHMAKING",
                "sessionLoopState": "MENUS",
            },
        )
        stop_stanza = make_presence_stanza(
            "QueueBuddy",
            "EUW",
            "friend-puuid",
            {
                "partyId": "party-1",
                "queueId": "",
                "partyState": "DEFAULT",
                "sessionLoopState": "MENUS",
            },
        )

        self.assertTrue(self.tracker.feed_chunk(1, start_stanza))
        self.assertTrue(self.tracker.feed_chunk(1, stop_stanza))

        presence = self.tracker.get_presence(puuid="friend-puuid")
        self.assertFalse(presence["is_queueing"])
        self.assertEqual(presence["queue_id"], "")
        self.assertEqual(presence["party_state"], "DEFAULT")

    def test_invalid_private_jwt_falls_back_to_base_payload(self):
        stanza = make_presence_stanza(
            "QueueBuddy",
            "EUW",
            "friend-puuid",
            {
                "partyId": "party-1",
                "privateJwt": "not-a-jwt",
            },
        )

        self.assertTrue(self.tracker.feed_chunk(1, stanza))
        presence = self.tracker.get_presence(puuid="friend-puuid")
        self.assertEqual(presence["party_id"], "party-1")
        self.assertEqual(presence["queue_id"], "")

    def test_non_valorant_stanza_is_ignored(self):
        stanza = (
            "<presence from='friend@ares.pvp.net/RC-123'>"
            "<games><keystone><p>ignored</p></keystone></games>"
            "<id name='QueueBuddy' tagline='EUW' /></presence>"
        )

        self.assertFalse(self.tracker.feed_chunk(1, stanza))
        self.assertIsNone(self.tracker.get_presence(riot_id="QueueBuddy#EUW"))

    def test_get_known_friends_returns_sorted_unique_entries(self):
        first = make_presence_stanza(
            "QueueBuddy",
            "EUW",
            "friend-puuid",
            {
                "partyId": "party-1",
                "queueId": "competitive",
                "partyState": "MATCHMAKING",
                "sessionLoopState": "MENUS",
            },
        )
        second = make_presence_stanza(
            "Alpha",
            "NA1",
            "friend-two",
            {
                "partyId": "party-2",
                "queueId": "",
                "partyState": "DEFAULT",
                "sessionLoopState": "MENUS",
            },
        )

        self.assertTrue(self.tracker.feed_chunk(1, first))
        self.assertTrue(self.tracker.feed_chunk(1, second))

        friends = self.tracker.get_known_friends()
        self.assertEqual([friend["display_name"] for friend in friends], ["Alpha#NA1", "QueueBuddy#EUW"])
        self.assertEqual(friends[0]["puuid"], "friend-two")
        self.assertEqual(friends[1]["puuid"], "friend-puuid")

    def test_roster_iq_items_are_added_to_known_friends(self):
        stanza = make_roster_stanza(
            "<item jid='friend-one@ares.pvp.net' name='Bravo' tagline='EUW' subscription='both' />",
            "<item jid='friend-two@ares.pvp.net' game_name='Alpha' game_tag='NA1' subscription='both' />",
        )

        self.assertTrue(self.tracker.feed_chunk(1, stanza))

        friends = self.tracker.get_known_friends()
        self.assertEqual([friend["display_name"] for friend in friends], ["Alpha#NA1", "Bravo#EUW"])
        self.assertEqual(friends[0]["puuid"], "friend-two")
        self.assertEqual(friends[1]["puuid"], "friend-one")

    def test_roster_iq_nested_identity_tags_are_added_to_known_friends(self):
        stanza = make_roster_stanza(
            (
                "<item jid='friend-three@ares.pvp.net' subscription='both'>"
                "<id name='Charlie' tagline='AP' />"
                "</item>"
            ),
        )

        self.assertTrue(self.tracker.feed_chunk(1, stanza))

        friends = self.tracker.get_known_friends()
        self.assertEqual(len(friends), 1)
        self.assertEqual(friends[0]["display_name"], "Charlie#AP")
        self.assertEqual(friends[0]["puuid"], "friend-three")

    def test_presence_without_inline_id_uses_roster_identity(self):
        roster = make_roster_stanza(
            (
                "<item jid='friend-four@ares.pvp.net' subscription='both'>"
                "<id name='Delta' tagline='EUW' />"
                "</item>"
            ),
        )
        stanza = make_presence_stanza_without_id(
            "friend-four",
            {
                "partyId": "party-4",
                "queueId": "competitive",
                "partyState": "MATCHMAKING",
                "sessionLoopState": "MENUS",
            },
        )

        self.assertTrue(self.tracker.feed_chunk(1, roster))
        self.assertTrue(self.tracker.feed_chunk(1, stanza))

        presence = self.tracker.get_presence(puuid="friend-four")
        self.assertEqual(presence["display_name"], "Delta#EUW")
        self.assertEqual(presence["queue_id"], "competitive")
        self.assertTrue(presence["is_queueing"])


if __name__ == "__main__":
    unittest.main()
