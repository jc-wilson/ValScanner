import tempfile
import unittest

from core.app_state import load_app_state, normalize_app_state, save_app_state


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


if __name__ == "__main__":
    unittest.main()
