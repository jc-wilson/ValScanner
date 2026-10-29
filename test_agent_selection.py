import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap

from core.agent_selection import AGENT_NAMES, HUSH_UUID, SELECTION_TOKENS, random_agent_pool
from core.app_state import default_app_state, load_app_state, save_app_state
from core.owned_agents import OwnedAgents
from core.valorant_uuid import UUIDHandler
from frontend.QApplication import AgentPopup, MapAgentPopup, ValorantStatsWindow

ROOT = Path(__file__).resolve().parent


class AgentSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_pool_unions_roles_and_agents_without_duplicates_or_unowned_agents(self):
        owned = ["Hush", "Jett", "Sage", "Omen", "Jett", "Unknown"]
        self.assertEqual(random_agent_pool(["Duelist", "Hush", "Controller"], owned), ["Hush", "Jett", "Omen"])
        self.assertEqual(random_agent_pool([], owned), [])
        self.assertEqual(random_agent_pool(["Initiator"], owned), [])
        self.assertEqual(random_agent_pool(["Random"], owned), ["Hush", "Jett", "Omen", "Sage"])

    def test_state_roundtrip_and_old_settings(self):
        self.assertFalse(default_app_state([])["custom_random_enabled"])
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
            saved = save_app_state({"custom_random_enabled": True,
                "custom_random_selections": ["Hush", "Duelist", "Hush", {}, "bad"],
                "selected_theme": "amethyst"}, map_uuids=[], base_path=directory)
            self.assertEqual(saved["custom_random_selections"], ["Hush", "Duelist"])
            self.assertEqual(load_app_state(map_uuids=[], base_path=directory), saved)
            self.assertEqual(saved["selected_theme"], "amethyst")

    def test_hush_resolves_with_stale_metadata_and_has_real_portrait(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
            path = Path(directory) / "agents.json"
            path.write_text(json.dumps({"data": []}))
            handler = UUIDHandler()
            handler.agent_uuids_path = path
            handler.agent_uuid_function()
            self.assertEqual(handler.agent_converter_reversed("Hush"), HUSH_UUID)
            self.assertEqual(handler.agent_converter(HUSH_UUID), "Hush")
        self.assertFalse(QPixmap(str(ROOT / "assets/agents/Hush.png")).isNull())

    def test_ownership_refresh_resets_role_pools(self):
        handler = OwnedAgents()
        handler.all_agents = ["Hush", "Jett", "Jett", [], "Unknown"]
        handler.refresh_pools()
        self.assertEqual(handler.owned_duelists, ["Hush", "Jett"])
        handler.refresh_pools()
        self.assertEqual(handler.owned_duelists, ["Hush", "Jett"])
        handler.all_agents = ["Sage"]
        handler.refresh_pools()
        self.assertEqual(handler.owned_duelists, [])

    def test_popup_multiselect_persists_without_closing_and_toggle_restores_single_pick(self):
        changes, picks = [], []
        handler = OwnedAgents()
        popup = AgentPopup(handler.agents, AGENT_NAMES + SELECTION_TOKENS, {}, picks.append,
            pool_callback=lambda enabled, choices: changes.append((enabled, choices)))
        popup.custom_random_switch.setChecked(True)
        popup.agent_tiles["Hush"].click()
        popup.agent_tiles["Controller"].click()
        self.assertEqual(changes[-1], (True, ["Hush", "Controller"]))
        self.assertEqual(picks, [])
        self.assertTrue(popup.agent_tiles["Hush"].isChecked())
        popup.agent_tiles["Hush"].click()
        self.assertEqual(changes[-1], (True, ["Controller"]))
        popup.agent_tiles["Random"].click()
        self.assertEqual(changes[-1], (True, ["Random"]))
        popup.agent_tiles["Hush"].click()
        self.assertEqual(changes[-1], (True, ["Hush"]))
        popup.custom_random_switch.setChecked(False)
        popup.agent_tiles["Jett"].click()
        self.assertEqual(picks, ["Jett"])
        self.assertFalse(changes[-1][0])
        popup.close()

    def test_popup_layout_hush_replaces_random_and_random_shares_role_row(self):
        handler = OwnedAgents()
        popup = AgentPopup(handler.agents, AGENT_NAMES + SELECTION_TOKENS, {}, lambda _: None)
        popup.show()
        self.app.processEvents()
        hush, random_tile = popup.agent_tiles["Hush"], popup.agent_tiles["Random"]
        self.assertEqual(hush.pos().y(), popup.agent_tiles["Yoru"].pos().y())
        self.assertGreater(random_tile.pos().y(), hush.pos().y())
        self.assertEqual(random_tile.pos().y(), popup.agent_tiles["Duelist"].pos().y())
        popup.close()

    def test_manual_and_auto_lock_path_uses_only_custom_pool_and_skips_empty(self):
        async def run():
            handler = OwnedAgents()
            handler.all_agents = ["Hush", "Jett", "Sage"]
            uuid = UUIDHandler()
            uuid.agent_uuids = {"data": [{"uuid": HUSH_UUID, "displayName": "Hush"}]}
            messages = []
            window = SimpleNamespace(init_agents=AsyncMock(),
                agent_select_btn=SimpleNamespace(text=lambda: "Random"),
                lock_agent_button=SimpleNamespace(setEnabled=lambda _: None),
                owned_agent_handler=handler, uuid_handler=uuid, custom_random_enabled=True,
                custom_random_selections=["Hush"], valo_rank=SimpleNamespace(handler=object()),
                set_status_message=messages.append)
            with patch("frontend.QApplication.instalock_agent", new_callable=AsyncMock) as lock:
                await ValorantStatsWindow.instalock_agent_async(window)
                self.assertEqual(lock.call_args.args[0], HUSH_UUID)
                window.custom_random_selections = []
                await ValorantStatsWindow.instalock_agent_async(window)
                self.assertEqual(lock.await_count, 1)
                self.assertTrue(messages)
        asyncio.run(run())

    def test_map_random_uses_saved_custom_pool(self):
        async def run():
            from core.map_instalock_agent import resolve_selection_to_agent_uuid
            handler = OwnedAgents()
            handler.all_agents = ["Hush", "Jett", "Sage"]
            handler.owned_agents_func = AsyncMock()
            uuid = UUIDHandler()
            uuid.agent_uuids = {"data": [{"uuid": HUSH_UUID, "displayName": "Hush"}]}
            uuid.agent_uuid_function = lambda: None
            with patch("core.map_instalock_agent.OwnedAgents", return_value=handler), \
                 patch("core.map_instalock_agent.UUIDHandler", return_value=uuid), \
                 patch("core.map_instalock_agent.load_app_state", return_value={
                     "custom_random_enabled": True, "custom_random_selections": ["Hush"]}):
                self.assertEqual(await resolve_selection_to_agent_uuid("Random"), HUSH_UUID)
        asyncio.run(run())

    def test_map_picker_custom_toggle_saves_pool_and_sets_map_to_random(self):
        owner = SimpleNamespace(custom_random_enabled=True, custom_random_selections=["Hush"],
            on_custom_random_changed=Mock())
        picker = SimpleNamespace(parent=lambda: owner, agent_options=AGENT_NAMES + SELECTION_TOKENS,
            owned_agents_list=AGENT_NAMES + SELECTION_TOKENS, agent_icons={}, on_agent_selected=Mock())
        with patch("frontend.QApplication.AgentPopup") as popup:
            MapAgentPopup.open_agent_picker(picker, "test-map")
            kwargs = popup.call_args.kwargs
            self.assertTrue(kwargs["custom_random_enabled"])
            kwargs["pool_callback"](True, ["Hush", "Initiator"])
            owner.on_custom_random_changed.assert_called_once_with(True, ["Hush", "Initiator"])
            picker.on_agent_selected.assert_called_once_with("test-map", "Random")


if __name__ == "__main__":
    unittest.main()
