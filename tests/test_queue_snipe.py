import base64
import json
import unittest
from unittest.mock import AsyncMock

from core.party_tracker import PartyTracker
from core.queue_snipe import QueueSnipeService


def encode_private_payload(payload):
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def make_presence_entry(queue_id, party_state="MATCHMAKING", session_loop_state="MENUS"):
    return {
        "puuid": "friend-puuid",
        "game_name": "QueueBuddy",
        "game_tag": "EUW",
        "private": encode_private_payload(
            {
                "partyId": "friend-party",
                "queueId": queue_id,
                "partyState": party_state,
                "sessionLoopState": session_loop_state,
            }
        ),
    }


class QueueSnipeServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tracker = PartyTracker()
        self.service = QueueSnipeService(self.tracker)
        self.service.seed_local_presence = AsyncMock(return_value=False)
        self.service._selected_friend = {
            "puuid": "friend-puuid",
            "game_name": "QueueBuddy",
            "game_tag": "EUW",
            "display_name": "QueueBuddy#EUW",
            "pid": "",
        }

    async def wait_for_sync(self):
        if self.service._sync_task is not None:
            await self.service._sync_task

    async def test_friend_start_queue_changes_queue_then_joins(self):
        self.tracker.seed_presences([make_presence_entry("competitive")])
        self.service._get_current_party_context = AsyncMock(
            return_value={
                "party_id": "self-party",
                "queue_id": "",
                "is_queueing": False,
                "region": "eu",
                "shard": "eu",
                "headers": {},
            }
        )
        self.service._post_party_action = AsyncMock(return_value={})

        self.service.set_enabled(True)
        self.service.handle_presence_update()
        await self.wait_for_sync()

        self.service._post_party_action.assert_any_await(
            {
                "party_id": "self-party",
                "queue_id": "",
                "is_queueing": False,
                "region": "eu",
                "shard": "eu",
                "headers": {},
            },
            "/parties/v1/parties/self-party/queue",
            "Change queue",
            json_body={"queueId": "competitive"},
        )
        self.service._post_party_action.assert_any_await(
            {
                "party_id": "self-party",
                "queue_id": "",
                "is_queueing": False,
                "region": "eu",
                "shard": "eu",
                "headers": {},
            },
            "/parties/v1/parties/self-party/matchmaking/join",
            "Join queue",
        )

    async def test_friend_stop_queue_leaves_current_queue(self):
        self.tracker.seed_presences([make_presence_entry("", party_state="DEFAULT")])
        self.service._get_current_party_context = AsyncMock(
            return_value={
                "party_id": "self-party",
                "queue_id": "competitive",
                "is_queueing": True,
                "region": "eu",
                "shard": "eu",
                "headers": {},
            }
        )
        self.service._post_party_action = AsyncMock(return_value={})

        self.service.set_enabled(True)
        self.service.handle_presence_update()
        await self.wait_for_sync()

        self.service._post_party_action.assert_awaited_once_with(
            {
                "party_id": "self-party",
                "queue_id": "competitive",
                "is_queueing": True,
                "region": "eu",
                "shard": "eu",
                "headers": {},
            },
            "/parties/v1/parties/self-party/matchmaking/leave",
            "Leave queue",
        )

    async def test_duplicate_presence_does_not_repeat_actions(self):
        self.tracker.seed_presences([make_presence_entry("competitive")])
        self.service._get_current_party_context = AsyncMock(
            return_value={
                "party_id": "self-party",
                "queue_id": "",
                "is_queueing": False,
                "region": "eu",
                "shard": "eu",
                "headers": {},
            }
        )
        self.service._post_party_action = AsyncMock(return_value={})

        self.service.set_enabled(True)
        self.service.handle_presence_update()
        await self.wait_for_sync()

        first_call_count = self.service._post_party_action.await_count

        self.service.handle_presence_update()
        await self.wait_for_sync()

        self.assertEqual(self.service._post_party_action.await_count, first_call_count)

    async def test_different_existing_queue_leaves_before_switching_and_joining(self):
        self.tracker.seed_presences([make_presence_entry("swiftplay")])
        self.service._get_current_party_context = AsyncMock(
            return_value={
                "party_id": "self-party",
                "queue_id": "competitive",
                "is_queueing": True,
                "region": "eu",
                "shard": "eu",
                "headers": {},
            }
        )
        self.service._post_party_action = AsyncMock(return_value={})

        self.service.set_enabled(True)
        self.service.handle_presence_update()
        await self.wait_for_sync()

        self.assertEqual(
            self.service._post_party_action.await_args_list[0].args[1],
            "/parties/v1/parties/self-party/matchmaking/leave",
        )
        self.assertEqual(
            self.service._post_party_action.await_args_list[1].kwargs["json_body"],
            {"queueId": "swiftplay"},
        )
        self.assertEqual(
            self.service._post_party_action.await_args_list[2].args[1],
            "/parties/v1/parties/self-party/matchmaking/join",
        )

    async def test_presence_seed_failure_does_not_block_queue_sync(self):
        self.tracker.seed_presences([make_presence_entry("competitive")])
        self.service.seed_local_presence = AsyncMock(side_effect=RuntimeError("boom"))
        self.service._get_current_party_context = AsyncMock(
            return_value={
                "party_id": "self-party",
                "queue_id": "",
                "is_queueing": False,
                "region": "eu",
                "shard": "eu",
                "headers": {},
            }
        )
        self.service._post_party_action = AsyncMock(return_value={})

        self.service.set_enabled(True)
        self.service.schedule_sync(seed_presence=True)
        await self.wait_for_sync()

        self.assertGreaterEqual(self.service._post_party_action.await_count, 2)

    async def test_fetch_friends_falls_back_to_presence_cache_when_chat_is_unavailable(self):
        self.tracker.seed_presences([make_presence_entry("competitive")])
        self.service._request_local_chat_json = AsyncMock(
            side_effect=RuntimeError("Riot chat isn't connected yet. Wait a few seconds, then try Queue Snipe again.")
        )

        friends = await self.service.fetch_friends()

        self.assertEqual(len(friends), 1)
        self.assertEqual(friends[0]["display_name"], "QueueBuddy#EUW")
        self.assertEqual(friends[0]["puuid"], "friend-puuid")

    async def test_fetch_friends_fallback_excludes_local_player(self):
        self.tracker.seed_presences(
            [
                make_presence_entry("competitive"),
                {
                    "puuid": "self-puuid",
                    "game_name": "SelfPlayer",
                    "game_tag": "EUW",
                    "private": encode_private_payload(
                        {
                            "partyId": "self-party",
                            "queueId": "",
                            "partyState": "DEFAULT",
                            "sessionLoopState": "MENUS",
                        }
                    ),
                },
            ]
        )
        self.service._request_local_chat_json = AsyncMock(
            side_effect=RuntimeError("Riot chat isn't connected yet. Wait a few seconds, then try Queue Snipe again.")
        )

        from core.local_api import LockfileHandler
        handler = LockfileHandler()
        handler.puuid = "self-puuid"

        friends = await self.service.fetch_friends()

        self.assertEqual(len(friends), 1)
        self.assertEqual(friends[0]["puuid"], "friend-puuid")

    async def test_get_current_party_context_uses_self_presence_before_party_player_request(self):
        self.tracker.seed_presences(
            [
                {
                    "puuid": "self-puuid",
                    "game_name": "SelfPlayer",
                    "game_tag": "EUW",
                    "private": encode_private_payload(
                        {
                            "partyId": "self-party",
                            "queueId": "competitive",
                            "partyState": "MATCHMAKING",
                            "sessionLoopState": "MENUS",
                            "isQueueing": True,
                        }
                    ),
                }
            ]
        )

        from core.queue_snipe import MatchDetectionHandler

        original = MatchDetectionHandler.puuid_shard_header_getter

        async def fake_ready(handler_self):
            handler_self.region = "eu"
            handler_self.shard = "eu"
            handler_self.user_puuid = "self-puuid"
            handler_self.match_id_header = {"Authorization": "Bearer token"}
            return True

        MatchDetectionHandler.puuid_shard_header_getter = fake_ready
        try:
            context = await self.service._get_current_party_context()
        finally:
            MatchDetectionHandler.puuid_shard_header_getter = original

        self.assertEqual(context["party_id"], "self-party")
        self.assertEqual(context["queue_id"], "competitive")
        self.assertTrue(context["is_queueing"])

    async def test_handle_local_json_api_event_populates_cached_party_context(self):
        self.service.handle_local_json_api_event(
            {
                "uri": "/parties/v1/players/self-puuid",
                "data": {"CurrentPartyID": "self-party"},
            },
            "self-puuid",
        )
        self.service.handle_local_json_api_event(
            {
                "uri": "/parties/v1/parties/self-party",
                "data": {
                    "State": "MATCHMAKING",
                    "MatchmakingData": {"QueueID": "swiftplay"},
                },
            },
            "self-puuid",
        )

        self.assertEqual(self.service._local_party_cache["party_id"], "self-party")
        self.assertEqual(self.service._local_party_cache["queue_id"], "swiftplay")
        self.assertTrue(self.service._local_party_cache["is_queueing"])


if __name__ == "__main__":
    unittest.main()
