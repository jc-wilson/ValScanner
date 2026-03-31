import tempfile
import unittest

from core.app_state import load_app_state, normalize_app_state, save_app_state
from core.presence_mode import PRESENCE_MODE_OFFLINE, PRESENCE_MODE_ONLINE


class AppStateTests(unittest.TestCase):
    def test_normalize_queue_snipe_requires_selected_friend(self):
        normalized = normalize_app_state(
            {
                "queue_snipe_enabled": True,
                "queue_snipe_selected_friend": None,
            },
            map_uuids=["map-a"],
        )

        self.assertFalse(normalized["queue_snipe_enabled"])
        self.assertIsNone(normalized["queue_snipe_selected_friend"])

    def test_save_and_load_queue_snipe_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            save_app_state(
                {
                    "selected_theme": "midnight",
                    "presence_mode": PRESENCE_MODE_OFFLINE,
                    "selected_standard_agent": "Random",
                    "auto_lock_enabled": False,
                    "map_lock_enabled": False,
                    "queue_snipe_enabled": True,
                    "queue_snipe_selected_friend": {
                        "puuid": "friend-puuid",
                        "game_name": "QueueBuddy",
                        "game_tag": "EUW",
                        "display_name": "QueueBuddy#EUW",
                        "pid": "RC-123",
                    },
                    "map_agent_selection": {"map-a": ""},
                },
                map_uuids=["map-a"],
                base_path=temp_dir,
            )

            loaded = load_app_state(map_uuids=["map-a"], base_path=temp_dir)

        self.assertEqual(loaded["presence_mode"], PRESENCE_MODE_OFFLINE)
        self.assertTrue(loaded["queue_snipe_enabled"])
        self.assertEqual(
            loaded["queue_snipe_selected_friend"],
            {
                "puuid": "friend-puuid",
                "game_name": "QueueBuddy",
                "game_tag": "EUW",
                "display_name": "QueueBuddy#EUW",
                "pid": "RC-123",
            },
        )

    def test_normalize_invalid_presence_mode_falls_back_to_online(self):
        normalized = normalize_app_state(
            {
                "presence_mode": "stealth",
            },
            map_uuids=["map-a"],
        )

        self.assertEqual(normalized["presence_mode"], PRESENCE_MODE_ONLINE)

    def test_default_presence_mode_is_online(self):
        normalized = normalize_app_state({}, map_uuids=["map-a"])

        self.assertEqual(normalized["presence_mode"], PRESENCE_MODE_ONLINE)


if __name__ == "__main__":
    unittest.main()
