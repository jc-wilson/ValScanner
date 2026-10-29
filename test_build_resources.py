"""Offline regressions for first-run preset storage and bundled agent icons."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import build


ROOT = Path(__file__).resolve().parent
OPTIONS = ('Random', 'Duelist', 'Initiator', 'Controller', 'Sentinel')


def check_ui(stage, phase):
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication, QLabel
    from frontend import QApplication as ui

    app = QApplication([])
    # Load the font icons before simulating an executable in a clean folder.
    ui.application_icon()
    installed = stage / 'installed'
    installed.mkdir(exist_ok=True)
    extraction = stage / f'extracted-{phase}'
    extraction.mkdir(exist_ok=True)
    # Even a bundled directory must never attract writes of user data.
    (extraction / 'loadouts').mkdir(exist_ok=True)
    with patch.object(sys, 'frozen', True, create=True), \
         patch.object(sys, 'executable', str(installed / 'app.exe')), \
         patch.object(sys, '_MEIPASS', str(stage if phase == 'icons' else extraction), create=True):
        if phase == 'icons':
            (installed / 'assets' / 'agents').mkdir(parents=True, exist_ok=True)
            for name in OPTIONS:
                path = Path(ui.get_agent_asset_path(name))
                assert path == stage / 'assets' / 'agents' / f'{name}.png'
                assert not QPixmap(str(path)).isNull(), name
            assert Path(ui.resource_path('missing-file')) == installed / 'missing-file'
            return

        class CosmeticNames:
            def uuid_to_weapon(self, value):
                return 'Classic' if value == 'saved-cosmetic' else None

            def skin_converter(self, value):
                return 'Test Classic'

        popup = ui.LoadoutsPopup({'Skins': {}}, {}, None, None, CosmeticNames())
        assert Path(popup.loadouts_dir) == installed / 'loadouts'
        assert Path(ui.get_map_selection_path()) == installed / ui.MAP_AGENT_SELECTION_RELATIVE_PATH
        if phase == 'write':
            popup.selected_skins_list[ui.PRESET_WEAPON_ORDER.index('Classic')] = 'saved-cosmetic'
            popup.preset_name_input.setText('Persistence Check')
            popup.submit_new_preset()
        else:
            rows = popup.findChildren(QLabel, 'presetName')
            assert 'Persistence Check' in {label.text() for label in rows}
            popup.apply_preset('Persistence Check')
            assert popup.skins['Classic'] == 'saved-cosmetic'
        saved = installed / 'loadouts' / 'Persistence Check.json'
        assert json.loads(saved.read_text())[ui.PRESET_WEAPON_ORDER.index('Classic')] == 'saved-cosmetic'
        assert not list((extraction / 'loadouts').iterdir())
        popup.close()
        app.processEvents()


class BuildResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.stage = build.prepare_build()

    def run_ui(self, phase):
        env = os.environ.copy()
        windows = Path(os.environ.get('SystemRoot', r'C:\Windows'))
        env['PATH'] = os.pathsep.join(map(str, (
            Path(sys.executable).parent, Path(sys.base_prefix), windows / 'System32', windows,
        )))
        subprocess.run([sys.executable, str(Path(__file__).resolve()), str(self.stage), phase],
                       cwd=ROOT, env=env, check=True, timeout=30)

    def test_saved_preset_survives_a_new_application_process(self):
        self.run_ui('write')
        self.run_ui('read')

    def test_bundled_role_and_random_icons_load_without_external_caches(self):
        for name in OPTIONS:
            self.assertTrue((self.stage / 'assets' / 'agents' / f'{name}.png').is_file())
        self.assertFalse(list((self.stage / 'assets').glob('logo*')))
        self.run_ui('icons')


if __name__ == '__main__':
    if len(sys.argv) == 3:
        check_ui(Path(sys.argv[1]), sys.argv[2])
    else:
        unittest.main()
