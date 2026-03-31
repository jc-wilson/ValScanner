from html import escape
from urllib.parse import quote
import time

from PySide6.QtWidgets import (
    QApplication, QMainWindow,
    QVBoxLayout, QGridLayout, QHBoxLayout, QWidget, QLabel, QPushButton,
    QComboBox, QFrame, QSplitter, QScrollArea, QDialog,
    QGraphicsDropShadowEffect, QSizePolicy, QProgressBar, QCheckBox,
    QGraphicsOpacityEffect, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, QSize, QPropertyAnimation, Property, QEasingCurve, QUrl, QPoint
from PySide6.QtGui import QPixmap, QIcon, QFontDatabase, QFont, QColor, QPainter, QCloseEvent, QDesktopServices, QCursor
from PySide6.QtNetwork import QLocalServer, QLocalSocket
import sys
import os
import random
import asyncio
import qasync
import websockets
import ssl
import base64
import json
import requests
from core.app_state import APP_STATE_VERSION, load_app_state, save_app_state
from core.api_client import ValoRank
from core.dodge_button import dodge
from core.instalock_agent import instalock_agent
from core.map_instalock_agent import map_instalock_agent
from core.valorant_uuid import UUIDHandler
from core.local_api import LockfileHandler
from core.owned_agents import OwnedAgents
from core.owned_skins import OwnedSkins
from core.player_loadout import PlayerLoadout
from core.http_session import SharedSession
from core.party_tracker import PartyTracker
from core.presence_mode import (
    PRESENCE_MODE_ONLINE,
    PRESENCE_MODE_OFFLINE,
    normalize_presence_mode,
)
from core.queue_snipe import QueueSnipeService
from core.startup_coordinator import AppStartupCoordinator
from core.asset_loader import (
    ensure_skin_asset_files,
    ensure_buddy_asset_files,
    load_skin_pixmap,
    load_buddy_pixmap,
)

CURRENT_VERSION = "1.10"
UPDATE_CHECK_URL = "https://ValScanner.com/version.json"
WEBSITE_URL = "https://ValScanner.com/"
APP_INSTANCE_KEY = "ValScanner.SingleInstance"
MAP_AGENT_SELECTION_RELATIVE_PATH = os.path.join("agent_selection", "map_agent_selection.json")
MAP_SPECIFIC_ROLE_TOKENS = {"Random", "Duelist", "Initiator", "Controller", "Sentinel"}
MAP_DISPLAY_NAMES = {
    "12452a9d-48c3-0b02-e7eb-0381c3520404": "Kasbah",
    "1c18ab1f-420d-0d8b-71d0-77ad3c439115": "Corrode",
    "224b0a95-48b9-f703-1bd8-67aca101a61f": "Abyss",
    "2bee0dc9-4ffe-519b-1cbd-7fbe763a6047": "Haven",
    "2c09d728-42d5-30d8-43dc-96a05cc7ee9d": "Drift",
    "2c9d57ec-4431-9c5e-2939-8f9ef6dd5cba": "Bind",
    "2fb9a4fd-47b8-4e7d-a969-74b4046ebd53": "Breeze",
    "2fe4ed3a-450a-948b-6d6b-e89a78e680a9": "Lotus",
    "690b3ed2-4dff-945b-8223-6da834e30d24": "District",
    "7eaecc1b-4337-bbf6-6ab9-04b8f06b3319": "Ascent",
    "92584fbe-486a-b1b2-9faa-39b0f486b498": "Sunset",
    "b529448b-4d60-346e-e89e-00a4c527a405": "Fracture",
    "d6336a5a-428f-c591-98db-c8a291159134": "Piazza",
    "d960549e-485c-e861-8d71-aa9d1aed12a2": "Split",
    "de28aa9b-4cbe-1003-320e-6cb3ec309557": "Glitch",
    "e2ad5c54-4114-a870-9641-8ea21279579a": "Icebox",
    "fd267378-4d1d-484f-ff52-77821ed10dc2": "Pearl",
}
# Edit these lists to move maps between popup sections.
MAP_SECTION_MAPS = {
    "Competitive": [
        "b529448b-4d60-346e-e89e-00a4c527a405",
        "2fe4ed3a-450a-948b-6d6b-e89a78e680a9",
        "2bee0dc9-4ffe-519b-1cbd-7fbe763a6047",
        "2c9d57ec-4431-9c5e-2939-8f9ef6dd5cba",
        "2fb9a4fd-47b8-4e7d-a969-74b4046ebd53",
        "d960549e-485c-e861-8d71-aa9d1aed12a2",
        "fd267378-4d1d-484f-ff52-77821ed10dc2",
    ],
    "Standard": [
        "224b0a95-48b9-f703-1bd8-67aca101a61f",
        "7eaecc1b-4337-bbf6-6ab9-04b8f06b3319",
        "92584fbe-486a-b1b2-9faa-39b0f486b498",
        "1c18ab1f-420d-0d8b-71d0-77ad3c439115",
        "e2ad5c54-4114-a870-9641-8ea21279579a",
    ],
    "Team Deathmatch": [
        "2c09d728-42d5-30d8-43dc-96a05cc7ee9d",
        "690b3ed2-4dff-945b-8223-6da834e30d24",
        "12452a9d-48c3-0b02-e7eb-0381c3520404",
        "d6336a5a-428f-c591-98db-c8a291159134",
        "de28aa9b-4cbe-1003-320e-6cb3ec309557",
    ],
}
MAP_SECTION_ORDER = ["Competitive", "Standard", "Team Deathmatch"]
DEFAULT_THEME_NAME = "midnight"
THEME_COLOR_KEYS = (
    "main",
    "window",
    "panel",
    "card",
    "card_alt",
    "border",
    "border_soft",
    "text",
    "muted",
    "accent",
    "accent_hover",
    "accent_pressed",
    "teal",
    "teal_hover",
    "red",
    "red_hover",
    "red_pressed",
    "gold",
    "cyan",
)
THEME_DEFINITIONS = {
    "midnight": {
        "label": "WWTB",
        "swatch_a": "#e5d989",
        "swatch_b": "#517f95",
        "main": "#111823",
        "window": "#0a1018",
        "panel": "#0f1722",
        "card": "#131d2a",
        "card_alt": "#182536",
        "border": "#27384d",
        "border_soft": "#203043",
        "text": "#eef4ff",
        "muted": "#93a4bb",
        "accent": "#4da3ff",
        "accent_hover": "#6ab4ff",
        "accent_pressed": "#347fda",
        "teal": "#46d7b0",
        "teal_hover": "#63e4c0",
        "red": "#c65a61",
        "red_hover": "#d87077",
        "red_pressed": "#ad4951",
        "gold": "#f0b35a",
        "cyan": "#7ae6ff",
    },
    "sandstorm": {
        "label": "Depth",
        "swatch_a": "#246EA1",
        "swatch_b": "#010000",
        "main": "#246EA1",
        "window": "#0E2C40",
        "panel": "#164766",
        "card": "#1D5881",
        "card_alt": "#2A73A7",
        "border": "#6D9BBC",
        "border_soft": "#3B6C8D",
        "text": "#F3FAFF",
        "muted": "#BDD3E2",
        "accent": "#010000",
        "accent_hover": "#343333",
        "accent_pressed": "#000000",
        "teal": "#63D8CA",
        "teal_hover": "#83E5D9",
        "red": "#CF6677",
        "red_hover": "#E07E8D",
        "red_pressed": "#B14E60",
        "gold": "#E7C46E",
        "cyan": "#9EDFFF",
    },
    "amethyst": {
        "label": "Nebula",
        "swatch_a": "#b48cff",
        "swatch_b": "#4f7dca",
        "main": "#150f24",
        "window": "#0d0818",
        "panel": "#1d1533",
        "card": "#261b40",
        "card_alt": "#342457",
        "border": "#63498b",
        "border_soft": "#492f6a",
        "text": "#f8f0ff",
        "muted": "#c7b2e6",
        "accent": "#ffc14d",
        "accent_hover": "#ffd16e",
        "accent_pressed": "#e09c24",
        "teal": "#63e6d0",
        "teal_hover": "#82efdd",
        "red": "#d86c96",
        "red_hover": "#ea84ab",
        "red_pressed": "#ba4f79",
        "gold": "#efc16f",
        "cyan": "#7fd7ff",
    },
    "emberglass": {
        "label": "Storm",
        "swatch_a": "#485A63",
        "swatch_b": "#939494",
        "main": "#485A63",
        "window": "#1D2428",
        "panel": "#2B363B",
        "card": "#3A484F",
        "card_alt": "#6D7B82",
        "border": "#919CA1",
        "border_soft": "#596A72",
        "text": "#F5F7F8",
        "muted": "#C5CCCF",
        "accent": "#939494",
        "accent_hover": "#A9A9A9",
        "accent_pressed": "#767676",
        "teal": "#69C8BE",
        "teal_hover": "#86D7CE",
        "red": "#C96D72",
        "red_hover": "#D98489",
        "red_pressed": "#A9575C",
        "gold": "#D6B06D",
        "cyan": "#9FD3E1",
    },
    "bailey": {
        "label": "Bailey",
        "swatch_a": "#7ea67f",
        "swatch_b": "#c79a4b",
        "main": "#507153",
        "window": "#243326",
        "panel": "#344c37",
        "card": "#3f5a42",
        "card_alt": "#49694c",
        "border": "#79977b",
        "border_soft": "#5d775f",
        "text": "#f6fbf3",
        "muted": "#c4d3c2",
        "accent": "#c79a4b",
        "accent_hover": "#d7ac61",
        "accent_pressed": "#a97e37",
        "teal": "#68c39a",
        "teal_hover": "#7dd3aa",
        "red": "#be6b61",
        "red_hover": "#cf8075",
        "red_pressed": "#9f544c",
        "gold": "#d6ae5d",
        "cyan": "#86c8be",
    },
    "glacier": {
        "label": "Bloom",
        "swatch_a": "#BA5478",
        "swatch_b": "#424242",
        "main": "#BA5478",
        "window": "#241018",
        "panel": "#703248",
        "card": "#8A4060",
        "card_alt": "#A54C6C",
        "border": "#D698AE",
        "border_soft": "#8C5069",
        "text": "#FFF5F8",
        "muted": "#E6C0CF",
        "accent": "#424242",
        "accent_hover": "#686868",
        "accent_pressed": "#282828",
        "teal": "#78C7A0",
        "teal_hover": "#93D5B2",
        "red": "#D5576F",
        "red_hover": "#E37287",
        "red_pressed": "#B24259",
        "gold": "#F0B768",
        "cyan": "#A7DCE8",
    },
    "rosewood": {
        "label": "Citrus",
        "swatch_a": "#EE9B2E",
        "swatch_b": "#FBD7AC",
        "main": "#EE9B2E",
        "window": "#FFF4E7",
        "panel": "#F7D19A",
        "card": "#FBE2BE",
        "card_alt": "#FFF0DA",
        "border": "#D99839",
        "border_soft": "#E8BC78",
        "text": "#2C1A07",
        "muted": "#7E5A2D",
        "accent": "#FBD7AC",
        "accent_hover": "#FCE2C2",
        "accent_pressed": "#E7BE8E",
        "teal": "#76CDB3",
        "teal_hover": "#93DAC4",
        "red": "#CD6D4A",
        "red_hover": "#DE8461",
        "red_pressed": "#AF5638",
        "gold": "#D69A2C",
        "cyan": "#6BB6D2",
    },
    "horizon": {
        "label": "Forest",
        "swatch_a": "#355834",
        "swatch_b": "#F0ECE4",
        "main": "#355834",
        "window": "#F7F3ED",
        "panel": "#D7E2D0",
        "card": "#E6EEDF",
        "card_alt": "#F0F5EC",
        "border": "#668062",
        "border_soft": "#A8BAA1",
        "text": "#1E2A1C",
        "muted": "#596C56",
        "accent": "#F0ECE4",
        "accent_hover": "#F6F3EE",
        "accent_pressed": "#D8D3CA",
        "teal": "#70A996",
        "teal_hover": "#8ABAA9",
        "red": "#B05C4F",
        "red_hover": "#C47466",
        "red_pressed": "#92473D",
        "gold": "#BEA367",
        "cyan": "#6FA6B3",
    },
}
THEME_ORDER = tuple(THEME_DEFINITIONS.keys())
THEME_MAIN = ""
THEME_WINDOW = ""
THEME_PANEL = ""
THEME_CARD = ""
THEME_CARD_ALT = ""
THEME_BORDER = ""
THEME_BORDER_SOFT = ""
THEME_TEXT = ""
THEME_MUTED = ""
THEME_ACCENT = ""
THEME_ACCENT_HOVER = ""
THEME_ACCENT_PRESSED = ""
THEME_TEAL = ""
THEME_TEAL_HOVER = ""
THEME_RED = ""
THEME_RED_HOVER = ""
THEME_RED_PRESSED = ""
THEME_GOLD = ""
THEME_CYAN = ""
INITIAL_ASSET_GROUPS = ("agents", "ranks", "maps")
SPECIAL_BUDDY_UUID = "a57aa3d0-4ad0-b06a-6c54-338cb3ea6b41"


def normalize_theme_name(theme_name):
    normalized = str(theme_name or DEFAULT_THEME_NAME).strip().lower()
    return normalized if normalized in THEME_DEFINITIONS else DEFAULT_THEME_NAME


def get_theme_definition(theme_name=None):
    return THEME_DEFINITIONS[normalize_theme_name(theme_name)]


def apply_theme_palette(theme_name=None):
    palette = get_theme_definition(theme_name)
    for color_key in THEME_COLOR_KEYS:
        globals()[f"THEME_{color_key.upper()}"] = palette[color_key]
    return normalize_theme_name(theme_name)


apply_theme_palette(DEFAULT_THEME_NAME)


def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def get_agent_asset_path(agent_name):
    filename = str(agent_name).replace("/", "_")
    return resource_path(os.path.join("assets", "agents", f"{filename}.png"))

def discover_map_asset_uuids():
    maps_dir = resource_path(os.path.join("assets", "maps"))
    if not os.path.isdir(maps_dir):
        return []

    map_uuids = []
    for file_name in os.listdir(maps_dir):
        stem, ext = os.path.splitext(file_name)
        if ext.lower() == ".png":
            map_uuids.append(stem)
    return sorted(map_uuids)

def get_map_selection_path():
    return resource_path(MAP_AGENT_SELECTION_RELATIVE_PATH)

def get_map_display_name(map_uuid):
    return MAP_DISPLAY_NAMES.get(map_uuid, map_uuid)


def get_clean_skin_name(raw_name):
    if isinstance(raw_name, list):
        raw_name = raw_name[0] if raw_name else "Unknown Skin"

    skin_name = str(raw_name or "Unknown Skin").strip()
    level_index = skin_name.find("Level")
    if level_index >= 0:
        return skin_name[:level_index - 1].strip()

    variant_index = skin_name.find("Variant")
    if variant_index >= 0:
        return skin_name[:variant_index - 2].strip()

    return skin_name


class InstantTooltipMixin:
    _tooltip_popup = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._instant_tooltip_text = ""

    def set_instant_tooltip(self, text):
        self._instant_tooltip_text = str(text or "")

    @classmethod
    def _get_tooltip_popup(cls):
        if cls._tooltip_popup is None:
            cls._tooltip_popup = InstantTooltipPopup()
        return cls._tooltip_popup

    def _show_instant_tooltip(self):
        if self._instant_tooltip_text:
            self._get_tooltip_popup().show_text(self._instant_tooltip_text)

    def enterEvent(self, event):
        self.setCursor(Qt.PointingHandCursor)
        self._show_instant_tooltip()
        super().enterEvent(event)

    def mouseMoveEvent(self, event):
        if self._instant_tooltip_text:
            self._show_instant_tooltip()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._get_tooltip_popup().hide()
        super().leaveEvent(event)


class InstantTooltipButton(InstantTooltipMixin, QPushButton):
    pass


class InstantTooltipFrame(InstantTooltipMixin, QFrame):
    pass


class InstantTooltipProgressBar(InstantTooltipMixin, QProgressBar):
    pass


class InstantTooltipLabel(InstantTooltipMixin, QLabel):
    pass


class InstantTooltipPopup(QLabel):
    def __init__(self):
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setMargin(0)
        self.setContentsMargins(8, 4, 8, 4)
        self.apply_theme_styles()

    def apply_theme_styles(self):
        self.setStyleSheet(
            f"background-color: {THEME_WINDOW};"
            f"color: {THEME_TEXT};"
            f"border: 1px solid {THEME_BORDER};"
            "border-radius: 4px;"
            "font-size: 12px;"
        )

    def show_text(self, text):
        self.setText(str(text))
        self.adjustSize()

        cursor_pos = QCursor.pos()
        target_pos = cursor_pos + QPoint(14, 20)
        screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        if screen is not None:
            geometry = screen.availableGeometry()
            x = min(target_pos.x(), geometry.right() - self.width() - 4)
            y = min(target_pos.y(), geometry.bottom() - self.height() - 4)
            x = max(geometry.left() + 4, x)
            y = max(geometry.top() + 4, y)
            target_pos = QPoint(x, y)

        self.move(target_pos)
        self.show()
        self.raise_()


class PlayerRowContentFrame(QFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._party_overlay = None

    def set_party_overlay(self, overlay):
        if self._party_overlay is not None:
            self._party_overlay.setParent(None)
            self._party_overlay.deleteLater()
            self._party_overlay = None

        if overlay is None:
            return

        overlay.setParent(self)
        overlay.show()
        overlay.raise_()
        self._party_overlay = overlay
        self._position_party_overlay()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_party_overlay()

    def _position_party_overlay(self):
        if self._party_overlay is None:
            return
        x_pos = max(0, self.width() - self._party_overlay.width())
        self._party_overlay.move(x_pos, 0)
        self._party_overlay.raise_()

def get_map_sections(map_uuids):
    section_map_uuids = []
    assigned = set()
    available = set(map_uuids)

    for section_name in MAP_SECTION_ORDER:
        configured = [map_uuid for map_uuid in MAP_SECTION_MAPS.get(section_name, []) if map_uuid in available]
        assigned.update(configured)
        section_map_uuids.append((section_name, configured))

    leftovers = [map_uuid for map_uuid in map_uuids if map_uuid not in assigned]
    for index, (section_name, configured) in enumerate(section_map_uuids):
        if section_name == "Standard":
            section_map_uuids[index] = (section_name, configured + leftovers)
            leftovers = []
            break

    if leftovers:
        section_map_uuids.append(("Unassigned", leftovers))

    return section_map_uuids

def ensure_map_agent_selection_data():
    map_uuids = discover_map_asset_uuids()
    state_data = load_app_state(map_uuids=map_uuids)
    return dict(state_data.get("map_agent_selection", {}))


class StartupLoadingWindow(QDialog):
    def __init__(self):
        super().__init__(None)
        self.setWindowTitle("ValScanner Loading")
        self.setModal(False)
        self.setWindowFlags(
            Qt.Dialog
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(320, 220)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("startupLoadingCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(0)

        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        logo_pixmap = QPixmap(resource_path("assets/logoone.png"))
        if not logo_pixmap.isNull():
            self.logo_label.setPixmap(
                logo_pixmap.scaled(132, 132, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        self.logo_label.setMinimumHeight(132)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("loadingBar")
        self.progress_bar.setRange(0, len(INITIAL_ASSET_GROUPS))
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setFixedWidth(132)

        card_layout.addWidget(self.logo_label, alignment=Qt.AlignCenter)
        card_layout.addSpacing(28)
        card_layout.addWidget(self.progress_bar, alignment=Qt.AlignHCenter)

        outer_layout.addWidget(card)

        self.apply_theme_styles()

    def apply_theme_styles(self):
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: transparent;
            }}
            QFrame#startupLoadingCard {{
                background: transparent;
                border: none;
            }}
            QProgressBar#loadingBar {{
                border: none;
                border-radius: 4px;
                background: {THEME_CARD};
            }}
            QProgressBar#loadingBar::chunk {{
                border-radius: 4px;
                background-color: {THEME_ACCENT};
            }}
            """
        )

    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = self.frameGeometry()
        geometry.moveCenter(screen.availableGeometry().center())
        self.move(geometry.topLeft())

    def update_progress(self, loaded_count, total_count):
        total = max(total_count, 1)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(min(loaded_count, total))


class VariantSelectorPopup(QDialog):
    def __init__(self, weapon, variants_list, skin_pixmap_resolver, uuid_handler, callback, parent=None):
        super().__init__(parent)
        self.weapon = weapon
        self.variants_list = variants_list
        self.skin_pixmap_resolver = skin_pixmap_resolver
        self.uuid_handler = uuid_handler
        self.callback = callback

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(1200, 800)

        container = QWidget(self)
        container.setObjectName("popupCard")
        container.setFixedSize(1200, 800)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(38, 38, 38, 38)
        main_layout.setSpacing(20)

        title = QLabel("Select Variant")
        title.setObjectName("title")
        main_layout.addWidget(title, alignment=Qt.AlignCenter)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        grid = QGridLayout(self.scroll_content)
        grid.setSpacing(20)
        grid.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        self.tile_width = 240
        self.tile_height = 150

        for index, variant_id in enumerate(self.variants_list):
            row = index // 4
            column = index % 4
            grid.addWidget(self.build_variant_tile(variant_id), row, column)

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area, 1)

        close_btn = QPushButton("Close")
        close_btn.setFixedSize(120, 50)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        main_layout.addWidget(close_btn, alignment=Qt.AlignRight)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 180))
        container.setGraphicsEffect(shadow)

        self.setStyleSheet(f"""
            #popupCard {{ background-color: {THEME_MAIN}; border-radius: 22px; border: 1px solid {THEME_BORDER_SOFT}; }}
            #title {{ color: {THEME_TEXT}; font-size: 26px; font-weight: 600; margin-bottom: 20px;}}
            #skinLabel {{ color: {THEME_MUTED}; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; }}
            #skinTile {{ background-color: {THEME_CARD}; border-radius: 18px; border: 1px solid {THEME_BORDER_SOFT}; }}
            #skinTile:hover {{ border: 1px solid {THEME_ACCENT}; background-color: {THEME_CARD_ALT}; }}
            #skinPreview {{ background-color: {THEME_WINDOW}; border-radius: 12px; border: 1px dashed {THEME_BORDER_SOFT}; }}
            #skinPreview[empty="true"] {{ color: {THEME_MUTED}; font-size: 11px; letter-spacing: 1px; }}
            QPushButton {{ background-color: {THEME_CARD_ALT}; border: none; color: {THEME_TEXT}; font-size: 18px; font-weight: 700; border-radius: 16px; }}
            QPushButton:hover {{ background-color: {THEME_ACCENT}; }}
            QToolTip {{ background-color: {THEME_WINDOW}; color: {THEME_TEXT}; border: 1px solid {THEME_BORDER}; border-radius: 4px; padding: 4px 8px; font-size: 12px; }}
            QScrollBar:vertical {{ background: transparent; width: 14px; margin: 0px; }}
            QScrollBar::handle:vertical {{ background: {THEME_BORDER}; min-height: 32px; border-radius: 7px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ background: none; height: 0px; }}
        """)

    def build_variant_tile(self, variant_id):
        tile = InstantTooltipButton()
        tile.setObjectName("skinTile")
        tile.setFixedSize(self.tile_width, self.tile_height)
        tile.setCursor(Qt.PointingHandCursor)

        tile.clicked.connect(lambda _, vid=variant_id: self.on_variant_clicked(vid))

        tile_layout = QVBoxLayout(tile)
        tile_layout.setContentsMargins(15, 15, 15, 15)
        tile_layout.setSpacing(10)
        tile_layout.setAlignment(Qt.AlignCenter)

        preview = QLabel()
        preview.setObjectName("skinPreview")
        preview.setAlignment(Qt.AlignCenter)
        preview.setMinimumSize(150, 88)
        preview.setProperty("empty", "false")
        preview.setAttribute(Qt.WA_TransparentForMouseEvents)

        pixmap = None
        clean_id = str(variant_id).strip()
        resolved_name = "Unknown Variant"

        if clean_id:
            if callable(self.skin_pixmap_resolver):
                pixmap = self.skin_pixmap_resolver(clean_id)

            if self.uuid_handler:
                try:
                    raw_name = self.uuid_handler.skin_converter(clean_id)
                    resolved_name = str(raw_name[0]) if isinstance(raw_name, list) else str(raw_name)
                except Exception:
                    pass

            tile.set_instant_tooltip(str(resolved_name))

            skin_label = QLabel(str(resolved_name))
            skin_label.setObjectName("skinLabel")
            skin_label.setAlignment(Qt.AlignCenter | Qt.AlignBottom)
            skin_label.setAttribute(Qt.WA_TransparentForMouseEvents)
            tile_layout.addWidget(skin_label)

        if pixmap:
            scaled_skin = pixmap.scaled(150, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            preview.setPixmap(scaled_skin)
        else:
            preview.setText("No Image")
            preview.setProperty("empty", "true")

        preview.style().unpolish(preview)
        preview.style().polish(preview)

        tile_layout.addWidget(preview)
        return tile

    def on_variant_clicked(self, variant_id):
        self.callback(self.weapon, variant_id)
        self.accept()


class SkinSelectorPopup(QDialog):
    def __init__(self, weapon, owned_skins_list, owned_variants_list, skin_pixmap_resolver, uuid_handler, callback, parent=None):
        super().__init__(parent)
        self.weapon = weapon
        self.skin_pixmap_resolver = skin_pixmap_resolver
        self.uuid_handler = uuid_handler
        self.callback = callback

        self.owned_variants = [variant for sublist in owned_variants_list.values() for variant in sublist]
        self.owned_skins_list = owned_skins_list.copy()

        for index, skin in enumerate(self.owned_skins_list):
            self.owned_skins_list[index] = uuid_handler.level_uuid_to_skin_uuid(skin)

        self.owned_skins_list = list(dict.fromkeys(self.owned_skins_list))
        self.used_skins = []

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(1200, 800)

        container = QWidget(self)
        container.setObjectName("popupCard")
        container.setFixedSize(1200, 800)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(38, 38, 38, 38)
        main_layout.setSpacing(20)

        title = QLabel(f"Owned {self.weapon} Skins")
        title.setObjectName("title")
        main_layout.addWidget(title, alignment=Qt.AlignCenter)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        grid = QGridLayout(self.scroll_content)
        grid.setSpacing(20)
        grid.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        self.tile_width = 240
        self.tile_height = 150

        seen_skin_names = set()
        grid_index = 0

        for skin_id in self.owned_skins_list:
            clean_id = str(skin_id).strip()

            base_name = "Unknown Skin"
            if self.uuid_handler:
                try:
                    raw_name = self.uuid_handler.skin_converter(clean_id)
                    if isinstance(raw_name, list):
                        raw_name = str(raw_name[0]) if raw_name else "Unknown Skin"

                    name_str = str(raw_name)
                    idx_level = name_str.find("Level")
                    if idx_level >= 0:
                        base_name = name_str[0:(idx_level - 1)].strip()
                    else:
                        idx_variant = name_str.find("Variant")
                        if idx_variant >= 0:
                            base_name = name_str[0:(idx_variant - 2)].strip()
                        else:
                            base_name = name_str.strip()
                except Exception:
                    pass

            if base_name in seen_skin_names:
                continue

            seen_skin_names.add(base_name)

            row = grid_index // 4
            column = grid_index % 4

            grid.addWidget(self.build_skin_tile(clean_id, base_name), row, column)
            self.used_skins.append(clean_id)
            grid_index += 1

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area, 1)

        close_btn = QPushButton("Close")
        close_btn.setFixedSize(120, 50)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        main_layout.addWidget(close_btn, alignment=Qt.AlignRight)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 180))
        container.setGraphicsEffect(shadow)

        self.setStyleSheet(f"""
            #popupCard {{ background-color: {THEME_MAIN}; border-radius: 22px; border: 1px solid {THEME_BORDER_SOFT}; }}
            #title {{ color: {THEME_TEXT}; font-size: 26px; font-weight: 600; margin-bottom: 20px;}}
            #skinLabel {{ color: {THEME_MUTED}; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; }}
            #skinTile {{ background-color: {THEME_CARD}; border-radius: 18px; border: 1px solid {THEME_BORDER_SOFT}; }}
            #skinTile:hover {{ border: 1px solid {THEME_ACCENT}; background-color: {THEME_CARD_ALT}; }}
            #skinPreview {{ background-color: {THEME_WINDOW}; border-radius: 12px; border: 1px dashed {THEME_BORDER_SOFT}; }}
            #skinPreview[empty="true"] {{ color: {THEME_MUTED}; font-size: 11px; letter-spacing: 1px; }}
            QPushButton {{ background-color: {THEME_CARD_ALT}; border: none; color: {THEME_TEXT}; font-size: 18px; font-weight: 700; border-radius: 16px; }}
            QPushButton:hover {{ background-color: {THEME_ACCENT}; }}
            QToolTip {{ background-color: {THEME_WINDOW}; color: {THEME_TEXT}; border: 1px solid {THEME_BORDER}; border-radius: 4px; padding: 4px 8px; font-size: 12px; }}
            QScrollBar:vertical {{ background: transparent; width: 14px; margin: 0px; }}
            QScrollBar::handle:vertical {{ background: {THEME_BORDER}; min-height: 32px; border-radius: 7px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ background: none; height: 0px; }}
        """)

    def build_skin_tile(self, clean_id, resolved_name):
        tile = InstantTooltipButton()
        tile.setObjectName("skinTile")
        tile.setFixedSize(self.tile_width, self.tile_height)
        tile.setCursor(Qt.PointingHandCursor)

        tile.clicked.connect(lambda _, sid=clean_id: self.on_skin_clicked(sid))

        tile_layout = QVBoxLayout(tile)
        tile_layout.setContentsMargins(15, 15, 15, 15)
        tile_layout.setSpacing(10)
        tile_layout.setAlignment(Qt.AlignCenter)

        preview = QLabel()
        preview.setObjectName("skinPreview")
        preview.setAlignment(Qt.AlignCenter)
        preview.setMinimumSize(150, 88)
        preview.setProperty("empty", "false")
        preview.setAttribute(Qt.WA_TransparentForMouseEvents)

        pixmap = None

        if clean_id:
            if callable(self.skin_pixmap_resolver):
                pixmap = self.skin_pixmap_resolver(clean_id)

            tile.set_instant_tooltip(str(resolved_name))

            skin_label = QLabel(str(resolved_name))
            skin_label.setObjectName("skinLabel")
            skin_label.setAlignment(Qt.AlignCenter | Qt.AlignBottom)
            skin_label.setAttribute(Qt.WA_TransparentForMouseEvents)
            tile_layout.addWidget(skin_label)

        if pixmap:
            scaled_skin = pixmap.scaled(150, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            preview.setPixmap(scaled_skin)
        else:
            preview.setText("No Skin Image")
            preview.setProperty("empty", "true")

        preview.style().unpolish(preview)
        preview.style().polish(preview)

        tile_layout.addWidget(preview)
        return tile

    def on_skin_clicked(self, clean_id):
        variants = self.uuid_handler.variant_finder(clean_id, self.owned_variants)

        if variants:
            popup = VariantSelectorPopup(self.weapon, variants, self.skin_pixmap_resolver, self.uuid_handler,
                                         self.on_variant_selected, self)
            popup.exec()
        else:
            self.callback(self.weapon, clean_id)
            self.accept()

    def on_variant_selected(self, weapon, variant_id):
        self.callback(weapon, variant_id)
        self.accept()


class LoadoutsPopup(QDialog):
    WEAPON_ORDER = [
        "Classic", "Bandit", "Shorty", "Frenzy", "Ghost", "Sheriff",
        "Stinger", "Spectre",
        "Bucky", "Judge",
        "Bulldog", "Guardian", "Phantom", "Vandal",
        "Marshal", "Outlaw", "Operator",
        "Ares", "Odin",
        "Knife",
    ]

    def __init__(self, skins, all_skins, skin_pixmap_resolver, buddy_pixmap_resolver, uuid_handler, parent=None):
        super().__init__(parent)
        self.skins = skins.get("Skins", {})
        self.buddies = skins.get("Buddies", {})
        self.owned_skins = all_skins
        self.skin_pixmap_resolver = skin_pixmap_resolver
        self.buddy_pixmap_resolver = buddy_pixmap_resolver
        self.uuid_handler = uuid_handler

        self.current_preset = None

        self.weapon_list_indices = {
            "Odin": 0,
            "Ares": 1,
            "Vandal": 2,
            "Bulldog": 3,
            "Phantom": 4,
            "Judge": 5,
            "Bucky": 6,
            "Frenzy": 7,
            "Classic": 8,
            "Ghost": 9,
            "Sheriff": 10,
            "Shorty": 11,
            "Operator": 12,
            "Guardian": 13,
            "Marshal": 14,
            "Spectre": 15,
            "Stinger": 16,
            "Knife": 17,
            "Outlaw": 18,
            "Bandit": 19
        }

        self.selected_skins_list = [None] * 20

        for weapon, idx in self.weapon_list_indices.items():
            skin_val = self.skins.get(weapon)
            if isinstance(skin_val, list) and len(skin_val) > 0:
                self.selected_skins_list[idx] = skin_val[0]
            else:
                self.selected_skins_list[idx] = skin_val

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(1920, 1080)

        container = QWidget(self)
        container.setObjectName("popupCard")
        container.setFixedSize(1920, 1080)

        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(38, 38, 38, 38)
        main_layout.setSpacing(20)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setAlignment(Qt.AlignTop)

        self.title_label = QLabel("Your Loadout")
        self.title_label.setObjectName("title")
        left_layout.addWidget(self.title_label, alignment=Qt.AlignCenter)

        self.grid = QGridLayout()
        self.grid.setSpacing(20)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        self.tile_width = 240
        self.tile_height = 150

        self.populate_grid()
        left_layout.addLayout(self.grid)

        self.preset_actions_layout = QHBoxLayout()
        self.preset_actions_layout.setContentsMargins(0, 20, 0, 0)
        self.preset_actions_layout.addStretch()

        self.cancel_preset_btn = QPushButton("Cancel")
        self.cancel_preset_btn.setObjectName("presetCancelBtn")
        self.cancel_preset_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_preset_btn.setFixedSize(120, 40)
        self.cancel_preset_btn.clicked.connect(self.cancel_current_preset_changes)
        self.cancel_preset_btn.hide()

        self.save_preset_btn = QPushButton("Save")
        self.save_preset_btn.setObjectName("presetSaveBtn")
        self.save_preset_btn.setCursor(Qt.PointingHandCursor)
        self.save_preset_btn.setFixedSize(120, 40)
        self.save_preset_btn.clicked.connect(self.save_current_preset)
        self.save_preset_btn.hide()

        self.apply_preset_btn = QPushButton("Apply")
        self.apply_preset_btn.setObjectName("presetApplyBtn")
        self.apply_preset_btn.setCursor(Qt.PointingHandCursor)
        self.apply_preset_btn.setFixedSize(120, 40)
        self.apply_preset_btn.clicked.connect(self.apply_current_loadout_changes)
        self.apply_preset_btn.hide()

        self.preset_actions_layout.addWidget(self.cancel_preset_btn)
        self.preset_actions_layout.addWidget(self.save_preset_btn)
        self.preset_actions_layout.addWidget(self.apply_preset_btn)
        self.preset_actions_layout.addStretch()

        left_layout.addLayout(self.preset_actions_layout)

        right_panel = QWidget()
        right_panel.setFixedWidth(400)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setAlignment(Qt.AlignTop)

        presets_card = QFrame()
        presets_card.setObjectName("presetsCard")
        presets_layout = QVBoxLayout(presets_card)
        presets_layout.setContentsMargins(15, 15, 15, 15)
        presets_layout.setSpacing(10)

        presets_header = QHBoxLayout()
        presets_title = QLabel("Presets")
        presets_title.setObjectName("title")

        add_preset_btn = QPushButton("New Preset")
        add_preset_btn.setCursor(Qt.PointingHandCursor)
        add_preset_btn.setObjectName("accentButton")
        add_preset_btn.clicked.connect(self.show_add_preset_input)

        presets_header.addWidget(presets_title)
        presets_header.addStretch()
        presets_header.addWidget(add_preset_btn)
        presets_layout.addLayout(presets_header)

        self.add_preset_widget = QWidget()
        add_preset_layout = QHBoxLayout(self.add_preset_widget)
        add_preset_layout.setContentsMargins(0, 0, 0, 0)
        add_preset_layout.setSpacing(8)

        self.preset_name_input = QLineEdit()
        self.preset_name_input.setPlaceholderText("Preset Name...")
        self.preset_name_input.setObjectName("presetInput")

        submit_btn = QPushButton("Save")
        submit_btn.setCursor(Qt.PointingHandCursor)
        submit_btn.setObjectName("submitBtn")
        submit_btn.clicked.connect(self.submit_new_preset)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.clicked.connect(self.hide_add_preset_input)

        add_preset_layout.addWidget(self.preset_name_input)
        add_preset_layout.addWidget(submit_btn)
        add_preset_layout.addWidget(cancel_btn)
        self.add_preset_widget.hide()

        presets_layout.addWidget(self.add_preset_widget)

        self.presets_scroll = QScrollArea()
        self.presets_scroll.setWidgetResizable(True)
        self.presets_scroll.setFrameShape(QFrame.NoFrame)
        self.presets_list_widget = QWidget()
        self.presets_list_layout = QVBoxLayout(self.presets_list_widget)
        self.presets_list_layout.setAlignment(Qt.AlignTop)
        self.presets_list_layout.setContentsMargins(0, 0, 0, 0)
        self.presets_list_layout.setSpacing(8)
        self.presets_scroll.setWidget(self.presets_list_widget)

        presets_layout.addWidget(self.presets_scroll)

        right_layout.addWidget(presets_card, 1)

        close_btn = QPushButton("Close")
        close_btn.setFixedSize(120, 50)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        right_layout.addWidget(close_btn, alignment=Qt.AlignRight | Qt.AlignBottom)

        main_layout.addWidget(left_panel, 3)
        main_layout.addWidget(right_panel, 1)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 180))
        container.setGraphicsEffect(shadow)

        self.setStyleSheet(f"""
            #popupCard {{ background-color: {THEME_MAIN}; border-radius: 22px; border: 1px solid {THEME_BORDER_SOFT}; }}
            #presetsCard {{ background-color: {THEME_CARD}; border-radius: 18px; border: 1px solid {THEME_BORDER_SOFT}; }}
            #title {{ color: {THEME_TEXT}; font-size: 26px; font-weight: 600; margin-bottom: 20px;}}
            #skinLabel {{ color: {THEME_MUTED}; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; }}
            QPushButton#skinTile {{ background-color: {THEME_CARD}; border-radius: 18px; border: 1px solid {THEME_BORDER_SOFT}; }}
            QPushButton#skinTile:hover {{ border: 1px solid {THEME_ACCENT}; background-color: {THEME_CARD_ALT}; }}
            #skinPreview {{ background-color: {THEME_WINDOW}; border-radius: 12px; border: 1px dashed {THEME_BORDER_SOFT}; }}
            #skinPreview[empty="true"] {{ color: {THEME_MUTED}; font-size: 11px; letter-spacing: 1px; }}
            QPushButton {{ background-color: {THEME_CARD_ALT}; border: none; color: {THEME_TEXT}; font-size: 18px; font-weight: 700; border-radius: 16px; }}
            QPushButton:hover {{ background-color: {THEME_ACCENT}; }}
            QPushButton#accentButton {{ background-color: {THEME_ACCENT}; border-radius: 8px; font-size: 14px; padding: 6px 12px; }}
            QPushButton#accentButton:hover {{ background-color: {THEME_ACCENT_HOVER}; }}
            #presetInput {{ background-color: {THEME_WINDOW}; border: 1px solid {THEME_BORDER}; color: {THEME_TEXT}; font-size: 14px; padding: 0 10px; border-radius: 8px; height: 36px; }}
            QPushButton#submitBtn {{ background-color: {THEME_TEAL}; color: #071018; border-radius: 8px; font-size: 14px; font-weight: bold; padding: 6px 12px; }}
            QPushButton#submitBtn:hover {{ background-color: {THEME_TEAL_HOVER}; }}
            QPushButton#cancelBtn {{ background-color: {THEME_RED}; color: {THEME_TEXT}; border-radius: 8px; font-size: 14px; font-weight: bold; padding: 6px 12px; }}
            QPushButton#cancelBtn:hover {{ background-color: {THEME_RED_HOVER}; }}
            QPushButton#presetSaveBtn {{ background-color: {THEME_TEAL}; color: #071018; border-radius: 8px; font-size: 16px; font-weight: bold; }}
            QPushButton#presetSaveBtn:hover {{ background-color: {THEME_TEAL_HOVER}; }}
            QPushButton#presetCancelBtn {{ background-color: {THEME_RED}; color: {THEME_TEXT}; border-radius: 8px; font-size: 16px; font-weight: bold; }}
            QPushButton#presetCancelBtn:hover {{ background-color: {THEME_RED_HOVER}; }}
            QPushButton#presetApplyBtn {{ background-color: {THEME_TEAL}; color: #071018; font-size: 13px; border-radius: 8px; padding: 6px 12px; font-weight: 600; }}
            QPushButton#presetApplyBtn:hover {{ background-color: {THEME_TEAL_HOVER}; }}
            QToolTip {{ background-color: {THEME_WINDOW}; color: {THEME_TEXT}; border: 1px solid {THEME_BORDER}; border-radius: 4px; padding: 4px 8px; font-size: 12px; }}
            #presetRow {{ background-color: {THEME_CARD_ALT}; border-radius: 14px; border: 1px solid {THEME_BORDER_SOFT}; }}
            #presetRow:hover {{ border: 1px solid {THEME_ACCENT}; background-color: {THEME_CARD}; }}
            #presetRowSelected {{ background-color: {THEME_PANEL}; border-radius: 14px; border: 1px solid {THEME_ACCENT}; }}
            #presetName {{ color: {THEME_TEXT}; font-weight: 600; font-size: 16px; }}
            QPushButton#presetDelBtn {{ background-color: {THEME_RED_PRESSED}; font-size: 13px; border-radius: 8px; padding: 6px 12px; font-weight: 600; }}
            QPushButton#presetDelBtn:hover {{ background-color: {THEME_RED}; }}
        """)

        self.loadouts_dir = resource_path("loadouts")
        os.makedirs(self.loadouts_dir, exist_ok=True)

        current_loadout_path = os.path.join(self.loadouts_dir, "Current Loadout.json")
        try:
            with open(current_loadout_path, 'w') as f:
                json.dump(self.selected_skins_list, f)
        except Exception:
            pass

        self.load_existing_presets()
        self.apply_preset("Current Loadout")

    def load_existing_presets(self):
        if not os.path.exists(self.loadouts_dir):
            return

        self.create_preset_row("Current Loadout")

        for filename in os.listdir(self.loadouts_dir):
            if filename.endswith(".json"):
                preset_name = filename[:-5]
                if preset_name != "Current Loadout":
                    self.create_preset_row(preset_name)

    def save_current_preset(self):
        if not self.current_preset:
            return
        filepath = os.path.join(self.loadouts_dir, f"{self.current_preset}.json")
        try:
            with open(filepath, 'w') as f:
                json.dump(self.selected_skins_list, f)
        except Exception:
            pass

    def apply_current_loadout_changes(self):
        filepath = os.path.join(self.loadouts_dir, "Current Loadout.json")
        try:
            with open(filepath, 'w') as f:
                json.dump(self.selected_skins_list, f)
        except Exception:
            pass
        self.push_preset_to_game("Current Loadout")

    def cancel_current_preset_changes(self):
        if not self.current_preset:
            return
        self.apply_preset(self.current_preset)

    def push_preset_to_game(self, name):
        import asyncio
        asyncio.create_task(self._push_preset_to_game_async(name))

    async def _push_preset_to_game_async(self, name):
        filepath = os.path.join(self.loadouts_dir, f"{name}.json")
        try:
            import json
            with open(filepath, 'r') as f:
                preset_data = json.load(f)

            try:
                from core.player_loadout import modify_loadout
                func = modify_loadout
            except ImportError:
                from core.player_loadout import PlayerLoadout
                func = PlayerLoadout().modify_loadout

            import inspect
            result = func(preset_data, self.owned_skins, self.uuid_handler)
            if inspect.isawaitable(result):
                await result

            if name != "Current Loadout":
                import asyncio
                await asyncio.sleep(1)

                from core.owned_skins import OwnedSkins
                handler = OwnedSkins()
                current_skins_data = await handler.sort_current_loadout()
                skins_dict = current_skins_data.get("Skins", {})

                new_current_loadout = [None] * 20
                for weapon, idx in self.weapon_list_indices.items():
                    skin_val = skins_dict.get(weapon)
                    if isinstance(skin_val, list) and len(skin_val) > 0:
                        new_current_loadout[idx] = skin_val[0]
                    else:
                        new_current_loadout[idx] = skin_val

                current_filepath = os.path.join(self.loadouts_dir, "Current Loadout.json")
                with open(current_filepath, 'w') as f:
                    json.dump(new_current_loadout, f)

                if self.current_preset == "Current Loadout":
                    self.apply_preset("Current Loadout")

        except Exception as e:
            pass

    def highlight_selected_preset(self, selected_name):
        for i in range(self.presets_list_layout.count()):
            widget = self.presets_list_layout.itemAt(i).widget()
            if widget:
                name_label = widget.findChild(QLabel, "presetName")
                if name_label:
                    if name_label.text() == selected_name:
                        widget.setObjectName("presetRowSelected")
                    else:
                        widget.setObjectName("presetRow")
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)

    def apply_preset(self, name):
        filepath = os.path.join(self.loadouts_dir, f"{name}.json")
        try:
            with open(filepath, 'r') as f:
                preset_data = json.load(f)
            self.selected_skins_list = preset_data
            for weapon, idx in self.weapon_list_indices.items():
                if idx < len(preset_data):
                    self.skins[weapon] = preset_data[idx]
            self.populate_grid()

            self.current_preset = name
            self.cancel_preset_btn.show()

            if name == "Current Loadout":
                self.save_preset_btn.hide()
                self.apply_preset_btn.show()
                self.apply_preset_btn.setStyleSheet("font-size: 16px;")
            else:
                self.save_preset_btn.show()
                self.apply_preset_btn.hide()
                self.apply_preset_btn.setStyleSheet("")

            self.title_label.setText(name)
            self.highlight_selected_preset(name)
        except Exception:
            pass

    def delete_preset(self, name, row_widget):
        filepath = os.path.join(self.loadouts_dir, f"{name}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
        row_widget.setParent(None)
        row_widget.deleteLater()

        if self.current_preset == name:
            self.apply_preset("Current Loadout")

    def populate_grid(self):
        for i in reversed(range(self.grid.count())):
            widget = self.grid.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        for index, weapon in enumerate(self.WEAPON_ORDER):
            row = index // 5
            column = index % 5
            self.grid.addWidget(self.build_skin_tile(weapon, self.skins.get(weapon)), row, column)

    def update_equipped_skin(self, weapon, new_skin_id):
        self.skins[weapon] = new_skin_id

        if hasattr(self, 'weapon_list_indices') and weapon in self.weapon_list_indices:
            idx = self.weapon_list_indices[weapon]
            if isinstance(new_skin_id, list) and len(new_skin_id) > 0:
                self.selected_skins_list[idx] = new_skin_id[0]
            else:
                self.selected_skins_list[idx] = new_skin_id

        self.populate_grid()

    def build_skin_tile(self, weapon, skin_id):
        tile = InstantTooltipButton()
        tile.setObjectName("skinTile")
        tile.setFixedSize(self.tile_width, self.tile_height)
        tile.setCursor(Qt.PointingHandCursor)
        tile.clicked.connect(lambda _, w=weapon: self.show_owned_skins_popup(w))

        tile_layout = QVBoxLayout(tile)
        tile_layout.setContentsMargins(15, 15, 15, 15)
        tile_layout.setSpacing(10)
        tile_layout.setAlignment(Qt.AlignCenter)

        preview = QLabel()
        preview.setObjectName("skinPreview")
        preview.setAlignment(Qt.AlignCenter)
        preview.setMinimumSize(150, 88)
        preview.setProperty("empty", "false")
        preview.setAttribute(Qt.WA_TransparentForMouseEvents)

        canvas = QPixmap(150, 88)
        canvas.fill(Qt.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        pixmap = None

        if skin_id:
            if isinstance(skin_id, list):
                skin_id = skin_id[0]

            if callable(self.skin_pixmap_resolver):
                pixmap = self.skin_pixmap_resolver(skin_id)

            if self.uuid_handler:
                try:
                    skin_name = self.uuid_handler.skin_converter(skin_id)
                    if isinstance(skin_name, list):
                        skin_name = str(skin_name[0]) if skin_name else "Unknown Skin"
                    tile.set_instant_tooltip(str(skin_name))
                    skin_name = get_clean_skin_name(skin_name)

                    skin_label = QLabel(str(skin_name))
                    skin_label.setObjectName("skinLabel")
                    skin_label.setAlignment(Qt.AlignCenter | Qt.AlignBottom)
                    skin_label.setAttribute(Qt.WA_TransparentForMouseEvents)
                    tile_layout.addWidget(skin_label)
                except Exception:
                    pass

        if pixmap:
            scaled_skin = pixmap.scaled(150, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x_skin = (150 - scaled_skin.width()) // 2
            y_skin = (88 - scaled_skin.height()) // 2
            painter.drawPixmap(x_skin, y_skin, scaled_skin)
        else:
            painter.setPen(QColor(THEME_MUTED))
            font = painter.font()
            font.setPixelSize(11)
            font.setLetterSpacing(QFont.AbsoluteSpacing, 1)
            painter.setFont(font)
            painter.drawText(canvas.rect(), Qt.AlignCenter, "No Skin")
            preview.setProperty("empty", "true")

        buddy_id = self.buddies.get(weapon)
        if buddy_id and callable(self.buddy_pixmap_resolver):
            if isinstance(buddy_id, list):
                buddy_id = buddy_id[0]
            elif isinstance(buddy_id, dict):
                buddy_id = buddy_id.get("CharmID", buddy_id.get("CharmLevelID", ""))

            buddy_pixmap = self.buddy_pixmap_resolver(buddy_id)

            if buddy_pixmap:
                scaled_buddy = buddy_pixmap.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x_buddy = 5
                y_buddy = 88 - scaled_buddy.height() - 5
                painter.drawPixmap(x_buddy, y_buddy, scaled_buddy)

        painter.end()
        preview.setPixmap(canvas)

        preview.style().unpolish(preview)
        preview.style().polish(preview)

        tile_layout.addWidget(preview)
        return tile

    def show_owned_skins_popup(self, weapon):
        owned_skins_dict = self.owned_skins.get("Skins", {})
        weapon_skins = owned_skins_dict.get(weapon, [])
        owned_variants_list = self.owned_skins.get("Variants", [])

        popup = SkinSelectorPopup(weapon, weapon_skins, owned_variants_list, self.skin_pixmap_resolver, self.uuid_handler,
                                  self.update_equipped_skin, self)
        popup.exec()

    def show_add_preset_input(self):
        self.add_preset_widget.show()
        self.preset_name_input.setFocus()

    def hide_add_preset_input(self):
        self.add_preset_widget.hide()
        self.preset_name_input.clear()

    def submit_new_preset(self):
        name = self.preset_name_input.text().strip()
        name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_'))
        if name and name != "Current Loadout":
            filepath = os.path.join(self.loadouts_dir, f"{name}.json")
            with open(filepath, 'w') as f:
                json.dump(self.selected_skins_list, f)

            exists = False
            for i in range(self.presets_list_layout.count()):
                widget = self.presets_list_layout.itemAt(i).widget()
                if widget and widget.findChild(QLabel, "presetName") and widget.findChild(QLabel,
                                                                                          "presetName").text() == name:
                    exists = True
                    break

            if not exists:
                self.create_preset_row(name)
            self.apply_preset(name)
        self.hide_add_preset_input()

    def create_preset_row(self, name):
        row = QFrame()
        row.setObjectName("presetRow")
        row.setCursor(Qt.PointingHandCursor)

        def on_click(event):
            if event.button() == Qt.LeftButton:
                self.apply_preset(name)

        row.mousePressEvent = on_click

        layout = QHBoxLayout(row)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(10)

        name_label = QLabel(name)
        name_label.setObjectName("presetName")
        name_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        layout.addWidget(name_label)
        layout.addStretch()

        if name != "Current Loadout":
            apply_btn = QPushButton("Apply")
            apply_btn.setObjectName("presetApplyBtn")
            apply_btn.setCursor(Qt.PointingHandCursor)
            apply_btn.clicked.connect(lambda _, n=name: self.push_preset_to_game(n))

            del_btn = QPushButton("Delete")
            del_btn.setObjectName("presetDelBtn")
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.clicked.connect(lambda _, n=name, r=row: self.delete_preset(n, r))

            layout.addWidget(apply_btn)
            layout.addWidget(del_btn)

        self.presets_list_layout.addWidget(row)


class AgentPopup(QDialog):
    def __init__(self, agents_list, owned_agents_list, agent_icons, callback, parent=None):
        super().__init__(parent)
        self.callback = callback
        self.agent_icons = agent_icons
        self.owned_agents_list = owned_agents_list

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)

        container = QWidget()
        container.setObjectName("popupCard")

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(16)

        header = QVBoxLayout()
        header.setSpacing(6)
        header.setAlignment(Qt.AlignCenter)

        title = QLabel("Select Agent")
        title.setTextFormat(Qt.PlainText)
        title.setObjectName("title")
        header.addWidget(title, alignment=Qt.AlignCenter)

        subtitle = QLabel("Choose an agent to instalock")
        subtitle.setObjectName("subtitle")
        header.addWidget(subtitle, alignment=Qt.AlignCenter)

        main_layout.addLayout(header)

        self.tile_width = 120
        self.tile_height = 120
        columns = 6

        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        if len(agents_list) > 4:
            main_agents = agents_list[:-4]
            bottom_agents = agents_list[-4:]
        else:
            main_agents = agents_list
            bottom_agents = []

        current_row = -1
        for index, agent in enumerate(main_agents):
            row = index // columns
            column = index % columns
            grid.addWidget(self.build_agent_tile(agent), row, column)
            current_row = row

        if bottom_agents:
            bottom_row = current_row + 1
            start_col = (columns - len(bottom_agents)) // 2
            for i, agent in enumerate(bottom_agents):
                grid.addWidget(self.build_agent_tile(agent), bottom_row, start_col + i)
            current_row = bottom_row

        exit_row = current_row + 1
        grid.addWidget(self.build_exit_tile(columns), exit_row, 0, 1, columns)

        main_layout.addLayout(grid)

        outer = QVBoxLayout(self)
        outer.addWidget(container)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 180))
        container.setGraphicsEffect(shadow)

        self.setStyleSheet(f"""
            #popupCard {{
                background-color: {THEME_MAIN};
                border-radius: 22px;
                border: 1px solid {THEME_BORDER_SOFT};
            }}
            #title {{ color: {THEME_TEXT}; font-size: 22px; font-weight: 600; }}
            #subtitle {{ color: {THEME_MUTED}; font-size: 14px; }}
            #agentLabel {{
                color: {THEME_MUTED}; font-size: 12px; letter-spacing: 1px;
                text-transform: uppercase;
            }}
            #agentTile {{
                background-color: {THEME_CARD};
                border-radius: 18px;
                border: 1px solid {THEME_BORDER_SOFT};
            }}
            #agentTile:hover {{
                border: 1px solid {THEME_ACCENT};
                background-color: {THEME_CARD_ALT};
            }}
            #agentTileDisabled {{
                background-color: {THEME_WINDOW};
                border-radius: 18px;
                border: 1px solid {THEME_BORDER_SOFT};
            }}
            #exitTile {{
                background-color: {THEME_CARD_ALT};
                border-radius: 18px;
                border: 1px solid {THEME_BORDER_SOFT};
            }}
            #exitTile QPushButton {{
                background-color: {THEME_CARD};
                border: none; color: {THEME_TEXT}; font-size: 28px;
                font-weight: 700; border-radius: 16px;
            }}
            #exitTile QPushButton:hover {{
                background-color: {THEME_RED};
            }}
        """)

    def build_agent_tile(self, agent_name):
        tile = QPushButton()

        is_owned = agent_name in self.owned_agents_list

        if is_owned:
            tile.setObjectName("agentTile")
            tile.setCursor(Qt.PointingHandCursor)
        else:
            tile.setObjectName("agentTileDisabled")
            tile.setEnabled(False)

        tile.setFixedSize(self.tile_width, self.tile_height)

        layout = QVBoxLayout(tile)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        if agent_name in self.agent_icons:
            icon_label.setPixmap(
                self.agent_icons[agent_name].scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            icon_label.setText("?")
            icon_label.setStyleSheet(f"color: {THEME_MUTED}; font-size: 24px;")

        name_label = QLabel(agent_name)
        name_label.setObjectName("agentLabel")
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        layout.addWidget(icon_label)
        layout.addWidget(name_label)

        if not is_owned:
            opacity_effect = QGraphicsOpacityEffect()
            opacity_effect.setOpacity(0.3)
            tile.setGraphicsEffect(opacity_effect)

        tile.clicked.connect(lambda _, a=agent_name: self.on_select(a))
        return tile

    def build_exit_tile(self, cols):
        tile = QFrame()
        tile.setObjectName("exitTile")

        full_width = (self.tile_width * cols) + (16 * (cols - 1))
        tile.setFixedSize(full_width, 60)

        layout = QVBoxLayout(tile)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setAlignment(Qt.AlignCenter)

        exit_button = QPushButton("X")
        exit_button.setFixedSize(96, 40)
        exit_button.setCursor(Qt.PointingHandCursor)
        exit_button.clicked.connect(self.close)
        layout.addWidget(exit_button, alignment=Qt.AlignCenter)

        return tile

    def on_select(self, agent_name):
        self.callback(agent_name)
        self.accept()


class FriendSelectionPopup(QDialog):
    def __init__(self, friends_list, callback, parent=None):
        super().__init__(parent)
        self.callback = callback
        self.friends_list = list(friends_list or [])
        self.filtered_friends = list(self.friends_list)

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(520, 640)

        container = QWidget()
        container.setObjectName("popupCard")

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(26, 26, 26, 22)
        main_layout.setSpacing(14)

        header = QVBoxLayout()
        header.setSpacing(6)
        header.setAlignment(Qt.AlignCenter)

        title = QLabel("Queue Snipe")
        title.setObjectName("title")
        header.addWidget(title, alignment=Qt.AlignCenter)

        subtitle = QLabel("Select a friend to mirror their queue")
        subtitle.setObjectName("subtitle")
        header.addWidget(subtitle, alignment=Qt.AlignCenter)
        main_layout.addLayout(header)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search friends")
        self.search_input.textChanged.connect(self.on_search_text_changed)
        main_layout.addWidget(self.search_input)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(10)
        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area, 1)

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedHeight(42)
        close_btn.clicked.connect(self.close)
        main_layout.addWidget(close_btn)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.addWidget(container)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 180))
        container.setGraphicsEffect(shadow)

        self.setStyleSheet(f"""
            #popupCard {{
                background-color: {THEME_MAIN};
                border-radius: 22px;
                border: 1px solid {THEME_BORDER_SOFT};
            }}
            #title {{ color: {THEME_TEXT}; font-size: 22px; font-weight: 600; }}
            #subtitle {{ color: {THEME_MUTED}; font-size: 14px; }}
            QLineEdit {{
                background-color: {THEME_CARD_ALT};
                border-radius: 12px;
                padding: 10px 12px;
                color: {THEME_TEXT};
                border: 1px solid {THEME_BORDER};
            }}
            QLineEdit:focus {{
                border: 1px solid {THEME_ACCENT};
            }}
            QPushButton#friendRow {{
                background-color: {THEME_CARD};
                border-radius: 16px;
                border: 1px solid {THEME_BORDER_SOFT};
                text-align: left;
            }}
            QPushButton#friendRow:hover {{
                border: 1px solid {THEME_ACCENT};
                background-color: {THEME_CARD_ALT};
            }}
            QLabel#friendName {{
                color: {THEME_TEXT};
                font-size: 15px;
                font-weight: 700;
            }}
            QLabel#friendMeta {{
                color: {THEME_MUTED};
                font-size: 12px;
            }}
            QLabel#friendEmptyState {{
                color: {THEME_MUTED};
                font-style: italic;
                padding: 18px 6px;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 12px;
                margin: 6px 0 6px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {THEME_BORDER};
                border-radius: 6px;
                min-height: 36px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {THEME_ACCENT};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)

        self.populate_friend_rows()

    def on_search_text_changed(self, value):
        query = str(value or "").strip().lower()
        if not query:
            self.filtered_friends = list(self.friends_list)
        else:
            self.filtered_friends = [
                friend for friend in self.friends_list
                if query in friend.get("display_name", "").lower()
                or query in friend.get("puuid", "").lower()
            ]
        self.populate_friend_rows()

    def populate_friend_rows(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not self.filtered_friends:
            empty_label = QLabel("No friends match your search.")
            empty_label.setObjectName("friendEmptyState")
            empty_label.setAlignment(Qt.AlignCenter)
            self.scroll_layout.addWidget(empty_label)
            self.scroll_layout.addStretch(1)
            return

        for friend in self.filtered_friends:
            self.scroll_layout.addWidget(self.build_friend_row(friend))
        self.scroll_layout.addStretch(1)

    def build_friend_row(self, friend):
        row = QPushButton()
        row.setObjectName("friendRow")
        row.setCursor(Qt.PointingHandCursor)
        row.setMinimumHeight(76)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(16, 14, 16, 14)
        row_layout.setSpacing(12)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)

        name_label = QLabel(friend.get("display_name", friend.get("puuid", "Unknown")))
        name_label.setObjectName("friendName")
        name_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        name_label.setWordWrap(False)

        text_layout.addWidget(name_label)
        row_layout.addLayout(text_layout, 1)

        pick_label = QLabel("Select")
        pick_label.setObjectName("friendMeta")
        pick_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        row_layout.addWidget(pick_label, alignment=Qt.AlignVCenter)

        row.clicked.connect(lambda _, selected_friend=friend: self.on_select(selected_friend))
        return row

    def on_select(self, friend):
        self.callback(friend)
        self.accept()


class MapAgentPopup(QDialog):
    def __init__(self, agent_options, owned_agents_list, agent_icons, map_icons, uuid_handler, selection_data,
                 save_callback, parent=None):
        super().__init__(parent)
        self.agent_options = agent_options
        self.owned_agents_list = owned_agents_list or []
        self.agent_icons = agent_icons or {}
        self.map_icons = map_icons or {}
        self.uuid_handler = uuid_handler
        self.selection_data = dict(selection_data or {})
        self.save_callback = save_callback
        self.selection_buttons = {}

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)

        screen = QApplication.primaryScreen()
        available_geometry = screen.availableGeometry() if screen is not None else None
        outer_margin = 18
        popup_width = 1520
        popup_height = 960
        if available_geometry is not None:
            popup_width = min(popup_width, available_geometry.width() - 40)
            popup_height = min(popup_height, max(720, available_geometry.height() - 60))

        container_width = popup_width - (outer_margin * 2)
        container_height = popup_height - (outer_margin * 2)

        self.setFixedSize(popup_width, popup_height)

        container = QWidget(self)
        container.setObjectName("popupCard")
        container.setFixedSize(container_width, container_height)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(30, 30, 30, 24)
        main_layout.setSpacing(18)

        header = QVBoxLayout()
        header.setSpacing(6)
        header.setAlignment(Qt.AlignCenter)

        title = QLabel("Map Specific")
        title.setObjectName("title")
        header.addWidget(title, alignment=Qt.AlignCenter)

        subtitle = QLabel("Choose an agent or role for each map")
        subtitle.setObjectName("subtitle")
        header.addWidget(subtitle, alignment=Qt.AlignCenter)

        main_layout.addLayout(header)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("background: transparent; border: none;")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(6, 6, 6, 6)
        scroll_layout.setSpacing(24)

        all_map_uuids = discover_map_asset_uuids()
        for section_name, section_maps in get_map_sections(all_map_uuids):
            scroll_layout.addWidget(self.build_section(section_name, section_maps))
        scroll_layout.addStretch(1)

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area, 1)

        close_btn = QPushButton("X")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedHeight(44)
        close_btn.clicked.connect(self.close)
        main_layout.addWidget(close_btn)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(outer_margin, outer_margin, outer_margin, outer_margin)
        outer.addWidget(container)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 180))
        container.setGraphicsEffect(shadow)

        self.setStyleSheet(f"""
            #popupCard {{
                background-color: {THEME_MAIN};
                border-radius: 22px;
                border: 1px solid {THEME_BORDER_SOFT};
            }}
            #title {{ color: {THEME_TEXT}; font-size: 22px; font-weight: 600; }}
            #subtitle {{ color: {THEME_MUTED}; font-size: 14px; }}
            #mapSection {{
                background-color: {THEME_CARD};
                border-radius: 20px;
                border: 1px solid {THEME_BORDER_SOFT};
            }}
            #mapSectionTitle {{
                color: {THEME_TEXT};
                font-size: 16px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }}
            #mapCard {{
                background-color: {THEME_PANEL};
                border-radius: 18px;
                border: 1px solid {THEME_BORDER_SOFT};
            }}
            #mapPreview {{
                background-color: {THEME_WINDOW};
                border-radius: 14px;
                border: 1px solid {THEME_BORDER};
            }}
            #mapName {{
                color: {THEME_TEXT};
                font-size: 14px;
                font-weight: 600;
                letter-spacing: 0.4px;
            }}
            QPushButton#mapSelectionButton {{
                background-color: {THEME_CARD_ALT};
                border-radius: 18px;
                border: 1px solid {THEME_BORDER};
                padding: 0px;
            }}
            QPushButton#mapSelectionButton[selected="true"] {{
                border: 1px solid {THEME_ACCENT};
                background-color: {THEME_PANEL};
            }}
            QPushButton#mapSelectionButton:hover {{
                border: 1px solid {THEME_ACCENT};
                background-color: {THEME_CARD};
            }}
            QPushButton {{
                background-color: {THEME_CARD_ALT};
                border: none;
                color: {THEME_TEXT};
                font-size: 14px;
                font-weight: 700;
                border-radius: 14px;
                padding: 10px 18px;
            }}
            QPushButton:hover {{
                background-color: {THEME_ACCENT};
            }}
            QScrollBar:vertical {{ background: transparent; width: 14px; margin: 4px 0px 4px 0px; }}
            QScrollBar::handle:vertical {{ background: {THEME_BORDER}; min-height: 32px; border-radius: 7px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ background: none; height: 0px; }}
        """)

    def build_section(self, title_text, map_uuids):
        section = QFrame()
        section.setObjectName("mapSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(16)

        title = QLabel(title_text)
        title.setObjectName("mapSectionTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(18)
        grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        columns = 4
        for index, map_uuid in enumerate(map_uuids):
            row = index // columns
            column = index % columns
            grid.addWidget(self.build_map_card(map_uuid), row, column)

        layout.addLayout(grid)
        return section

    def build_map_card(self, map_uuid):
        card = QFrame()
        card.setObjectName("mapCard")
        card.setFixedSize(324, 264)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        preview = QLabel()
        preview.setObjectName("mapPreview")
        preview.setFixedSize(292, 132)
        preview.setAlignment(Qt.AlignCenter)

        pixmap = self.map_icons.get(map_uuid)
        if pixmap is None or pixmap.isNull():
            preview_path = resource_path(os.path.join("assets", "maps", f"{map_uuid}.png"))
            pixmap = QPixmap(preview_path)
            if not pixmap.isNull():
                self.map_icons[map_uuid] = pixmap

        if pixmap is not None and not pixmap.isNull():
            preview.setPixmap(pixmap.scaled(292, 132, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))

        name_label = QLabel(get_map_display_name(map_uuid))
        name_label.setObjectName("mapName")
        name_label.setAlignment(Qt.AlignCenter)

        button = QPushButton()
        button.setObjectName("mapSelectionButton")
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedSize(72, 72)
        button.clicked.connect(lambda _, m=map_uuid: self.open_agent_picker(m))

        self.selection_buttons[map_uuid] = button
        self.refresh_selection_button(map_uuid)

        layout.addWidget(name_label, alignment=Qt.AlignCenter)
        layout.addWidget(preview, alignment=Qt.AlignCenter)
        layout.addSpacing(12)
        layout.addWidget(button, alignment=Qt.AlignCenter)
        return card

    def refresh_selection_button(self, map_uuid):
        button = self.selection_buttons.get(map_uuid)
        if button is None:
            return

        selection_value = str(self.selection_data.get(map_uuid, "") or "")
        icon_pixmap, tooltip, is_selected = self.resolve_selection_icon(selection_value)

        button.setProperty("selected", "true" if is_selected else "false")
        button.setIcon(QIcon(icon_pixmap))
        button.setIconSize(QSize(48, 48))
        button.setText("")
        button.setToolTip(tooltip)
        button.style().unpolish(button)
        button.style().polish(button)
        button.update()

    def resolve_selection_icon(self, selection_value):
        if not selection_value:
            return self.build_placeholder_icon(), "Select agent", False

        if selection_value == "Random":
            return self.build_text_icon("R"), "Random", True

        if selection_value in MAP_SPECIFIC_ROLE_TOKENS:
            pixmap = self.lookup_agent_pixmap(selection_value)
            if pixmap is not None:
                return pixmap, selection_value, True
            return self.build_text_icon(selection_value[:1]), selection_value, True

        agent_name = self.uuid_handler.agent_converter(selection_value)
        if isinstance(agent_name, list):
            agent_name = agent_name[0] if agent_name else ""
        agent_name = str(agent_name or "")
        pixmap = self.lookup_agent_pixmap(agent_name)
        if pixmap is not None:
            return pixmap, agent_name or "Selected agent", True
        return self.build_text_icon("?"), agent_name or "Selected agent", True

    def lookup_agent_pixmap(self, agent_name):
        if not agent_name:
            return None

        pixmap = self.agent_icons.get(agent_name)
        if pixmap is not None and not pixmap.isNull():
            return pixmap

        icon_path = get_agent_asset_path(agent_name)
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                self.agent_icons[agent_name] = pixmap
                return pixmap
        return None

    def build_text_icon(self, text):
        canvas = QPixmap(56, 56)
        canvas.fill(Qt.transparent)

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(THEME_CARD_ALT))
        painter.setPen(QColor(THEME_ACCENT))
        painter.drawRoundedRect(4, 4, 48, 48, 14, 14)
        painter.setPen(QColor(THEME_TEXT))
        font = painter.font()
        font.setPointSize(18)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(canvas.rect(), Qt.AlignCenter, text)
        painter.end()
        return canvas

    def build_placeholder_icon(self):
        canvas = QPixmap(56, 56)
        canvas.fill(Qt.transparent)

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(THEME_WINDOW))
        painter.setPen(QColor(THEME_BORDER))
        painter.drawRoundedRect(4, 4, 48, 48, 14, 14)
        painter.setPen(QColor(THEME_MUTED))
        painter.drawLine(28, 17, 28, 39)
        painter.drawLine(17, 28, 39, 28)
        painter.end()
        return canvas

    def open_agent_picker(self, map_uuid):
        popup = AgentPopup(
            self.agent_options,
            self.owned_agents_list,
            self.agent_icons,
            lambda agent_name, m=map_uuid: self.on_agent_selected(m, agent_name),
            self,
        )
        popup.exec()

    def on_agent_selected(self, map_uuid, agent_name):
        if agent_name in MAP_SPECIFIC_ROLE_TOKENS:
            stored_value = agent_name
        else:
            stored_value = self.uuid_handler.agent_converter_reversed(agent_name)
            stored_value = str(stored_value or "")

        self.selection_data[map_uuid] = stored_value
        self.save_callback(map_uuid, stored_value)
        self.refresh_selection_button(map_uuid)


class ThemePopup(QDialog):
    def __init__(self, current_theme_name, callback, parent=None):
        super().__init__(parent)
        self.callback = callback
        self.current_theme_name = normalize_theme_name(current_theme_name)
        self.theme_buttons = {}

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)

        container = QWidget()
        container.setObjectName("popupCard")

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(30, 30, 30, 26)
        main_layout.setSpacing(18)

        header = QVBoxLayout()
        header.setSpacing(6)
        header.setAlignment(Qt.AlignCenter)

        title = QLabel("Themes")
        title.setObjectName("title")
        header.addWidget(title, alignment=Qt.AlignCenter)

        main_layout.addLayout(header)

        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        columns = 4
        for index, theme_name in enumerate(THEME_ORDER):
            row = index // columns
            column = index % columns
            grid.addWidget(self.build_theme_tile(theme_name), row, column)

        main_layout.addLayout(grid)

        close_btn = QPushButton("X")
        close_btn.setObjectName("exitTile")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedHeight(52)
        close_btn.clicked.connect(self.close)
        main_layout.addWidget(close_btn)

        outer = QVBoxLayout(self)
        outer.addWidget(container)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 180))
        container.setGraphicsEffect(shadow)

        self.apply_theme_styles()
        self.resize(760, 420)

    def build_theme_tile(self, theme_name):
        theme_definition = get_theme_definition(theme_name)

        tile = QPushButton()
        tile.setObjectName("themeTile")
        tile.setCursor(Qt.PointingHandCursor)
        tile.setFixedSize(156, 126)
        tile.clicked.connect(lambda _, t=theme_name: self.select_theme(t))

        layout = QVBoxLayout(tile)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        swatch = QLabel()
        swatch.setFixedSize(54, 54)
        swatch.setAttribute(Qt.WA_TransparentForMouseEvents)
        swatch.setStyleSheet(
            f"""
            background: qlineargradient(
                x1: 0, y1: 1, x2: 1, y2: 0,
                stop: 0 {theme_definition["swatch_a"]},
                stop: 0.49 {theme_definition["swatch_a"]},
                stop: 0.5 {theme_definition["swatch_b"]},
                stop: 1 {theme_definition["swatch_b"]}
            );
            border-radius: 27px;
            border: 2px solid rgba(255, 255, 255, 0.18);
            """
        )

        accent_dot = QLabel(swatch)
        accent_dot.setFixedSize(16, 16)
        accent_dot.move(34, 34)
        accent_dot.setStyleSheet(
            f"background-color: {theme_definition['accent']};"
            "border-radius: 8px;"
            "border: 2px solid rgba(7, 16, 24, 0.28);"
        )

        name_label = QLabel(theme_definition["label"])
        name_label.setObjectName("themeName")
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        palette_label = QLabel(theme_definition["accent"].upper())
        palette_label.setObjectName("themeMeta")
        palette_label.setAlignment(Qt.AlignCenter)
        palette_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        layout.addWidget(swatch, alignment=Qt.AlignCenter)
        layout.addWidget(name_label, alignment=Qt.AlignCenter)
        layout.addWidget(palette_label, alignment=Qt.AlignCenter)

        self.theme_buttons[theme_name] = tile
        return tile

    def apply_theme_styles(self):
        self.setStyleSheet(f"""
            #popupCard {{
                background-color: {THEME_MAIN};
                border-radius: 22px;
                border: 1px solid {THEME_BORDER_SOFT};
            }}
            #title {{ color: {THEME_TEXT}; font-size: 22px; font-weight: 600; }}
            #subtitle {{ color: {THEME_MUTED}; font-size: 14px; }}
            QPushButton#themeTile {{
                background-color: {THEME_CARD};
                border-radius: 18px;
                border: 1px solid {THEME_BORDER_SOFT};
                padding: 0px;
            }}
            QPushButton#themeTile:hover {{
                border: 1px solid {THEME_ACCENT};
                background-color: {THEME_CARD_ALT};
            }}
            QPushButton#themeTile[selected="true"] {{
                border: 1px solid {THEME_ACCENT};
                background-color: {THEME_PANEL};
            }}
            #themeName {{
                color: {THEME_TEXT};
                font-size: 13px;
                font-weight: 700;
                letter-spacing: 0.4px;
            }}
            #themeMeta {{
                color: {THEME_MUTED};
                font-size: 11px;
                letter-spacing: 1.2px;
                text-transform: uppercase;
            }}
            QPushButton#exitTile {{
                background-color: {THEME_CARD_ALT};
                border: 1px solid {THEME_BORDER_SOFT};
                color: {THEME_TEXT};
                font-size: 24px;
                font-weight: 700;
                border-radius: 16px;
                padding: 0px;
            }}
            QPushButton#exitTile:hover {{
                background-color: {THEME_RED};
            }}
            QPushButton {{
                background-color: {THEME_CARD_ALT};
                border: none;
                color: {THEME_TEXT};
                font-size: 14px;
                font-weight: 700;
                border-radius: 14px;
                padding: 10px 18px;
            }}
            QPushButton:hover {{
                background-color: {THEME_ACCENT};
            }}
        """)
        self.refresh_selection_styles()

    def refresh_selection_styles(self):
        for theme_name, button in self.theme_buttons.items():
            button.setProperty("selected", "true" if theme_name == self.current_theme_name else "false")
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def select_theme(self, theme_name):
        normalized_theme_name = normalize_theme_name(theme_name)
        self.current_theme_name = normalized_theme_name
        self.callback(normalized_theme_name)
        self.refresh_selection_styles()


class ToolsPopup(QDialog):
    def __init__(
        self,
        queue_snipe_label,
        queue_snipe_button,
        queue_snipe_switch,
        presence_mode_label,
        presence_mode_switch,
        themes_button,
        loadouts_button,
        parent=None,
    ):
        super().__init__(parent)
        self.queue_snipe_label = queue_snipe_label
        self.queue_snipe_button = queue_snipe_button
        self.queue_snipe_switch = queue_snipe_switch
        self.presence_mode_label = presence_mode_label
        self.presence_mode_switch = presence_mode_switch
        self.themes_button = themes_button
        self.loadouts_button = loadouts_button

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)

        container = QWidget()
        container.setObjectName("popupCard")

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(28, 28, 28, 24)
        main_layout.setSpacing(16)

        header = QVBoxLayout()
        header.setSpacing(6)
        header.setAlignment(Qt.AlignCenter)

        title = QLabel("Tools")
        title.setObjectName("title")
        header.addWidget(title, alignment=Qt.AlignCenter)

        subtitle = QLabel("Secondary controls and utilities")
        subtitle.setObjectName("subtitle")
        header.addWidget(subtitle, alignment=Qt.AlignCenter)
        main_layout.addLayout(header)

        queue_snipe_row = QFrame()
        queue_snipe_row.setObjectName("toolsRow")
        queue_snipe_layout = QHBoxLayout(queue_snipe_row)
        queue_snipe_layout.setContentsMargins(16, 14, 16, 14)
        queue_snipe_layout.setSpacing(12)
        queue_snipe_layout.addWidget(self.queue_snipe_label)
        queue_snipe_layout.addWidget(self.queue_snipe_button, 1)
        queue_snipe_layout.addWidget(self.queue_snipe_switch)
        main_layout.addWidget(queue_snipe_row)

        presence_row = QFrame()
        presence_row.setObjectName("toolsRow")
        presence_layout = QHBoxLayout(presence_row)
        presence_layout.setContentsMargins(16, 14, 16, 14)
        presence_layout.setSpacing(12)
        presence_layout.addWidget(self.presence_mode_label)
        presence_layout.addStretch(1)
        presence_layout.addWidget(self.presence_mode_switch)
        main_layout.addWidget(presence_row)

        utilities_row = QFrame()
        utilities_row.setObjectName("toolsRow")
        utilities_layout = QVBoxLayout(utilities_row)
        utilities_layout.setContentsMargins(16, 14, 16, 14)
        utilities_layout.setSpacing(12)

        utilities_label = QLabel("Utilities")
        utilities_label.setObjectName("sectionLabel")
        utilities_layout.addWidget(utilities_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.addWidget(self.themes_button)
        button_row.addWidget(self.loadouts_button)
        utilities_layout.addLayout(button_row)
        main_layout.addWidget(utilities_row)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("popupCloseButton")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedHeight(44)
        close_btn.clicked.connect(self.close)
        main_layout.addWidget(close_btn)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.addWidget(container)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 180))
        container.setGraphicsEffect(shadow)

        self.apply_theme_styles()
        self.resize(560, 360)

    def apply_theme_styles(self):
        self.setStyleSheet(f"""
            #popupCard {{
                background-color: {THEME_MAIN};
                border-radius: 22px;
                border: 1px solid {THEME_BORDER_SOFT};
            }}
            #title {{ color: {THEME_TEXT}; font-size: 22px; font-weight: 600; }}
            #subtitle {{ color: {THEME_MUTED}; font-size: 14px; }}
            QFrame#toolsRow {{
                background-color: {THEME_CARD};
                border-radius: 18px;
                border: 1px solid {THEME_BORDER_SOFT};
            }}
            QLabel#sectionLabel {{
                color: {THEME_MUTED};
                font-size: 12px;
                letter-spacing: 1.6px;
                text-transform: uppercase;
                font-weight: 700;
            }}
            QPushButton {{
                background-color: {THEME_CARD_ALT};
                border-radius: 14px;
                padding: 10px 18px;
                color: {THEME_TEXT};
                border: 1px solid {THEME_BORDER};
                font-weight: 600;
                letter-spacing: 0.6px;
            }}
            QPushButton:hover {{
                background-color: {THEME_BORDER};
            }}
            QPushButton:pressed {{
                background-color: {THEME_PANEL};
            }}
            QPushButton:disabled {{
                background-color: {THEME_WINDOW};
                color: #607086;
                border: 1px solid {THEME_BORDER_SOFT};
            }}
            QPushButton#secondaryButton {{
                background-color: {THEME_CARD_ALT};
            }}
            QPushButton#secondaryButton:hover {{
                background-color: {THEME_BORDER};
            }}
            QPushButton#popupCloseButton {{
                background-color: {THEME_PANEL};
                border: 1px solid {THEME_BORDER_SOFT};
            }}
            QPushButton#popupCloseButton:hover {{
                background-color: {THEME_CARD_ALT};
                border: 1px solid {THEME_ACCENT};
            }}
        """)

        for button in (
            self.queue_snipe_button,
            self.themes_button,
            self.loadouts_button,
        ):
            button.setFixedHeight(42)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def open_near(self, anchor_widget):
        self.adjustSize()
        if anchor_widget is not None:
            anchor_rect = anchor_widget.rect()
            anchor_bottom_left = anchor_widget.mapToGlobal(
                QPoint(anchor_rect.left(), anchor_rect.bottom() + 10)
            )
            x = anchor_bottom_left.x() - max(0, (self.width() - anchor_widget.width()) // 2)
            y = anchor_bottom_left.y()

            parent_window = anchor_widget.window()
            parent_geometry = parent_window.frameGeometry() if parent_window is not None else None

            anchor_center = anchor_widget.mapToGlobal(anchor_rect.center())
            screen = QApplication.screenAt(anchor_center)
            if screen is None and parent_window is not None and parent_window.windowHandle() is not None:
                screen = parent_window.windowHandle().screen()

            bounds = screen.availableGeometry() if screen is not None else None
            if parent_geometry is not None and not parent_geometry.isNull():
                if bounds is None:
                    bounds = parent_geometry
                else:
                    bounds = bounds.intersected(parent_geometry)
                    if bounds.isNull():
                        bounds = screen.availableGeometry()

            if bounds is not None and not bounds.isNull():
                x = max(bounds.left() + 12, min(x, bounds.right() - self.width() - 12))
                y = max(bounds.top() + 12, min(y, bounds.bottom() - self.height() - 12))

            self.move(x, y)

        self.open()


class WeaponPopup(QDialog):
    WEAPON_ORDER = [
        "Classic", "Bandit", "Shorty", "Frenzy", "Ghost", "Sheriff",
        "Stinger", "Spectre",
        "Bucky", "Judge",
        "Bulldog", "Guardian", "Phantom", "Vandal",
        "Marshal", "Outlaw", "Operator",
        "Ares", "Odin",
        "Knife",
    ]

    def __init__(self, player_name, skins, skin_pixmap_resolver, buddy_pixmap_resolver, uuid_handler, parent=None):
        super().__init__(parent)

        self.skins = skins or {}
        self.skin_pixmap_resolver = skin_pixmap_resolver
        self.buddy_pixmap_resolver = buddy_pixmap_resolver
        self.uuid_handler = uuid_handler
        player_display = player_name or "Unknown"

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)

        container = QWidget()
        container.setObjectName("popupCard")

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(38, 38, 38, 38)
        main_layout.setSpacing(20)

        header = QVBoxLayout()
        header.setSpacing(8)
        header.setAlignment(Qt.AlignCenter)

        title = QLabel(f"{player_display}'s Loadout")
        title.setTextFormat(Qt.PlainText)
        title.setObjectName("title")
        header.addWidget(title, alignment=Qt.AlignCenter)

        main_layout.addLayout(header)

        self.tile_width = 300
        self.tile_height = 167
        columns = 5

        grid = QGridLayout()
        grid.setSpacing(20)
        grid.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        current_row = 0
        for index, weapon in enumerate(self.WEAPON_ORDER):
            row = index // columns
            column = index % columns
            grid.addWidget(self.build_skin_tile(weapon, self.skins.get(weapon)), row, column)
            current_row = row

        exit_row = current_row + 1
        grid.addWidget(self.build_exit_tile(), exit_row, 0, 1, 5)

        main_layout.addLayout(grid)

        outer = QVBoxLayout(self)
        outer.addWidget(container)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 180))
        container.setGraphicsEffect(shadow)

        self.setStyleSheet(f"""
            #popupCard {{
                background-color: {THEME_MAIN};
                border-radius: 22px;
                border: 1px solid {THEME_BORDER_SOFT};
            }}
            #title {{ color: {THEME_TEXT}; font-size: 22px; font-weight: 600; }}
            #subtitle {{ color: {THEME_MUTED}; font-size: 14px; }}
            #weaponLabel {{
                color: {THEME_MUTED}; font-size: 12px; letter-spacing: 1px;
                text-transform: uppercase;
            }}
            #skinLabel {{
                color: {THEME_TEXT}; font-size: 12px; font-weight: 600; letter-spacing: 1px;
                text-transform: uppercase;
            }}
            #skinTile {{
                background-color: {THEME_CARD};
                border-radius: 18px;
                border: 1px solid {THEME_BORDER_SOFT};
            }}
            #skinTile:hover {{
                border: 1px solid {THEME_ACCENT};
                background-color: {THEME_CARD_ALT};
            }}
            #skinPreview {{
                background-color: {THEME_WINDOW};
                border-radius: 12px;
                border: 1px dashed {THEME_BORDER_SOFT};
            }}
            #skinPreview[empty="true"] {{
                color: {THEME_MUTED}; font-size: 11px; letter-spacing: 1px;
            }}
            #exitTile {{
                background-color: {THEME_CARD_ALT};
                border-radius: 18px;
                border: 1px solid {THEME_BORDER_SOFT};
            }}
            #exitTile:hover {{
                background-color: {THEME_RED};
            }}
            QToolTip {{
                background-color: {THEME_WINDOW}; color: {THEME_TEXT};
                border: 1px solid {THEME_BORDER};
                border-radius: 4px; padding: 4px 8px; font-size: 12px;
            }}
        """)

        self.resize(1200, 750)

    def build_skin_tile(self, weapon, skin_data):
        tile = InstantTooltipFrame()
        tile.setObjectName("skinTile")
        tile.setFixedSize(self.tile_width, self.tile_height)

        tile_layout = QVBoxLayout(tile)
        tile_layout.setContentsMargins(15, 15, 15, 15)
        tile_layout.setSpacing(10)
        tile_layout.setAlignment(Qt.AlignCenter)

        preview = QLabel()
        preview.setObjectName("skinPreview")
        preview.setAlignment(Qt.AlignCenter)
        preview.setMinimumSize(250, 120)
        preview.setProperty("empty", "false")

        skin_id = skin_data
        buddy_id = None
        if isinstance(skin_data, list):
            skin_id = skin_data[0] if len(skin_data) > 0 else None
            buddy_id = skin_data[1] if len(skin_data) > 1 else None

        pixmap = self.skin_pixmap_resolver(skin_id) if skin_id and callable(self.skin_pixmap_resolver) else None

        if skin_id:
            if self.uuid_handler:
                try:
                    skin_name = self.uuid_handler.skin_converter(skin_id)
                    if isinstance(skin_name, list):
                        skin_name = str(skin_name[0]) if skin_name else "Unknown Skin"
                    tile.set_instant_tooltip(str(skin_name))
                    skin_name = get_clean_skin_name(skin_name)

                    skin_label = QLabel(str(skin_name))
                    skin_label.setObjectName("skinLabel")
                    skin_label.setAlignment(QtCore.Qt.AlignCenter | Qt.AlignBottom)
                    tile_layout.addWidget(skin_label)
                except Exception:
                    pass

                canvas = QPixmap(250, 120)
                canvas.fill(Qt.transparent)
                painter = QPainter(canvas)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setRenderHint(QPainter.SmoothPixmapTransform)

                if pixmap:
                    scaled_skin = pixmap.scaled(250, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    x_skin = (250 - scaled_skin.width()) // 2
                    y_skin = (120 - scaled_skin.height()) // 2
                    painter.drawPixmap(x_skin, y_skin, scaled_skin)

                    buddy_pixmap = self.buddy_pixmap_resolver(buddy_id) if buddy_id and callable(self.buddy_pixmap_resolver) else None
                    if buddy_pixmap:
                        scaled_buddy = buddy_pixmap.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        x_buddy = 5
                        y_buddy = 120 - scaled_buddy.height() - 5
                        painter.drawPixmap(x_buddy, y_buddy, scaled_buddy)

                    preview.setPixmap(canvas)
                else:
                    preview.setText("No Skin")
                    preview.setProperty("empty", "true")
                painter.end()

        preview.style().unpolish(preview)
        preview.style().polish(preview)

        tile_layout.addWidget(preview)
        return tile

    def build_exit_tile(self):
        tile = QPushButton("X")
        tile.setObjectName("exitTile")

        full_width = (self.tile_width * 5) + (20 * 4)
        tile.setFixedSize(full_width, (int(self.tile_height / 2)))

        layout = QVBoxLayout(tile)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        tile.setCursor(Qt.PointingHandCursor)
        tile.clicked.connect(self.close)

        return tile


class ToggleSwitch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 22)
        self.setCursor(Qt.PointingHandCursor)
        self._position = 3.0
        self.animation = QPropertyAnimation(self, b"position")
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.setDuration(150)
        self.stateChanged.connect(self.setup_animation)

    @Property(float)
    def position(self):
        return self._position

    @position.setter
    def position(self, pos):
        self._position = pos
        self.update()

    def setup_animation(self, value):
        self.animation.stop()
        if value:
            self.animation.setEndValue(21.0)
        else:
            self.animation.setEndValue(3.0)
        self.animation.start()

    def hitButton(self, pos):
        return self.contentsRect().contains(pos)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)

        if self.isChecked():
            p.setBrush(QColor(THEME_ACCENT))
        else:
            p.setBrush(QColor(THEME_CARD_ALT))

        p.drawRoundedRect(0, 0, self.width(), self.height(), 11, 11)

        p.setBrush(QColor(THEME_TEXT))
        p.drawEllipse(int(self._position), 3, 16, 16)
        p.end()


class ValorantStatsWindow(QMainWindow):
    MAX_VISIBLE_PLAYER_ROWS = 5
    MIN_PLAYER_ROW_HEIGHT = 156

    def __init__(self, players=None):
        super().__init__()

        self.valo_rank = ValoRank()
        self.dodge_game = dodge()
        self.uuid_handler = UUIDHandler()
        self.uuid_handler.agent_uuid_function()
        self.uuid_handler.skin_uuid_function()
        self.uuid_handler.season_uuid_function()
        self.owned_agent_handler = OwnedAgents()

        font_path = resource_path("assets/fonts/Inter-UI-Regular.otf")
        print("Loading font from:", font_path)

        font_id = QFontDatabase.addApplicationFont(font_path)
        font_families = QFontDatabase.applicationFontFamilies(font_id)

        if font_families:
            app_font = QFont(font_families[0], 11)
            QApplication.setFont(app_font)
            print(f"Loaded font: {font_families[0]}")
        else:
            print("Failed to load custom font, falling back to default.")

        self.setWindowTitle("ValScanner")
        self.setMinimumSize(1500, 860)
        self.setWindowIcon(QIcon(resource_path("assets/logoone.png")))

        self.map_asset_uuids = discover_map_asset_uuids()
        persisted_state = load_app_state(map_uuids=self.map_asset_uuids)
        initial_theme_name = normalize_theme_name(persisted_state.get("selected_theme"))
        self.current_theme_name = apply_theme_palette(initial_theme_name)
        initial_presence_mode = PRESENCE_MODE_ONLINE
        initial_agent = str(persisted_state.get("selected_standard_agent", "Random") or "Random")
        initial_auto_lock_enabled = bool(persisted_state.get("auto_lock_enabled", False))
        initial_map_lock_enabled = bool(persisted_state.get("map_lock_enabled", False))
        initial_queue_snipe_enabled = False
        initial_queue_snipe_friend = None
        self.presence_mode = initial_presence_mode
        self._suspend_agent_lock_state_save = True

        self.agent_label = QLabel("Agent")
        self.agent_label.setObjectName("sectionLabel")

        self.agent_select_btn = QPushButton(initial_agent)
        self.agent_select_btn.setObjectName("agentSelectButton")
        self.agent_select_btn.setCursor(Qt.PointingHandCursor)
        self.agent_select_btn.setMinimumWidth(110)
        self.agent_select_btn.clicked.connect(self.open_agent_popup)
        self.agent = self.uuid_handler.agent_converter_reversed(initial_agent)

        self.lock_agent_button = QPushButton("Lock Agent")
        self.lock_agent_button.setCursor(Qt.PointingHandCursor)
        self.lock_agent_button.clicked.connect(self.instalock_agent)
        self.lock_agent_button.setObjectName("accentButton")

        self.auto_lock_label = QLabel("Auto-Lock")
        self.auto_lock_label.setObjectName("sectionLabel")
        self.auto_lock_switch = ToggleSwitch()
        self.auto_lock_switch.setChecked(initial_auto_lock_enabled)
        self.auto_lock_switch.toggled.connect(self.on_auto_lock_toggled)

        self.map_lock_label = QLabel("Map Specific")
        self.map_lock_label.setObjectName("sectionLabel")
        self.map_lock_switch = ToggleSwitch()
        self.map_lock_switch.setChecked(initial_map_lock_enabled)
        self.map_lock_switch.setEnabled(False)
        self.map_lock_switch.toggled.connect(self.on_map_lock_toggled)

        self.queue_snipe_label = QLabel("Queue Snipe")
        self.queue_snipe_label.setObjectName("sectionLabel")
        self.queue_snipe_selected_friend = initial_queue_snipe_friend
        self.queue_snipe_button = QPushButton(self.get_queue_snipe_button_text(initial_queue_snipe_friend))
        self.queue_snipe_button.setCursor(Qt.PointingHandCursor)
        self.queue_snipe_button.setObjectName("secondaryButton")
        self.queue_snipe_button.setMinimumWidth(180)
        self.queue_snipe_button.clicked.connect(self.open_queue_snipe_popup)
        self.queue_snipe_switch = ToggleSwitch()
        self.queue_snipe_switch.setChecked(initial_queue_snipe_enabled)
        self.queue_snipe_switch.setEnabled(initial_queue_snipe_friend is not None)
        self.queue_snipe_switch.toggled.connect(self.on_queue_snipe_toggled)

        self.presence_mode_label = QLabel("Appear Offline")
        self.presence_mode_label.setObjectName("sectionLabel")
        self.presence_mode_switch = ToggleSwitch()
        self.presence_mode_switch.setChecked(initial_presence_mode == PRESENCE_MODE_OFFLINE)
        self.presence_mode_switch.toggled.connect(self.on_presence_mode_toggled)

        self.loadouts_button = QPushButton("Loadouts")
        self.loadouts_button.setCursor(Qt.PointingHandCursor)
        self.loadouts_button.clicked.connect(self.open_user_loadouts)
        self.loadouts_button.setObjectName("secondaryButton")

        self.themes_button = QPushButton("Themes")
        self.themes_button.setCursor(Qt.PointingHandCursor)
        self.themes_button.clicked.connect(self.open_theme_popup)
        self.themes_button.setObjectName("secondaryButton")

        self.load_more_matches_button = QPushButton("Load More Games (5)")
        self.load_more_matches_button.setCursor(Qt.PointingHandCursor)
        self.load_more_matches_button.clicked.connect(self.run_load_more_matches_button)
        self.load_more_matches_button.setObjectName("secondaryButton")

        self.dodge_button = QPushButton("Dodge Game")
        self.dodge_button.setCursor(Qt.PointingHandCursor)
        self.dodge_button.clicked.connect(self.run_dodge_button)
        self.dodge_button.setObjectName("dodgeButton")

        self.edit_loadouts_button = QPushButton("Edit Loadouts")
        self.edit_loadouts_button.setCursor(Qt.PointingHandCursor)
        self.edit_loadouts_button.setObjectName("editloadoutsButton")

        self.refresh_button = QPushButton()
        self.refresh_button.setIcon(QIcon(resource_path("assets/refresh.png")))
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.setObjectName("refreshButton")
        self.refresh_button.clicked.connect(self.run_valo_stats)

        self.tools_button = QPushButton("Tools")
        self.tools_button.setCursor(Qt.PointingHandCursor)
        self.tools_button.setObjectName("secondaryButton")
        self.tools_button.clicked.connect(self.open_tools_popup)

        self.gamemode_chip, self.gamemode_value = self.build_meta_chip("Gamemode")
        self.server_chip, self.server_value = self.build_meta_chip("Server")
        self.status_value = QLabel("Initializing...")
        self.status_value.setObjectName("sectionLabel")
        header_button_height = 38
        refresh_button_size = 40
        header_chip_height = 58
        agent_block_height = 54

        self.gamemode_chip.setFixedHeight(header_chip_height)
        self.server_chip.setFixedHeight(header_chip_height)
        self.agent_select_btn.setFixedHeight(header_button_height)
        self.lock_agent_button.setFixedHeight(header_button_height)
        self.themes_button.setFixedHeight(header_button_height)
        self.loadouts_button.setFixedHeight(header_button_height)
        self.dodge_button.setFixedHeight(header_button_height)
        self.load_more_matches_button.setFixedHeight(header_button_height)
        self.queue_snipe_button.setFixedHeight(header_button_height)
        self.tools_button.setFixedHeight(header_button_height)
        self.refresh_button.setIconSize(QSize(28, 28))
        self.refresh_button.setFixedSize(refresh_button_size, refresh_button_size)

        self.agent_icons = None
        self.rank_icons = None
        self.buddy_icons = {}
        self.map_icons = None
        self.skin_icons = {}
        self._current_player_skin_ids = set()
        self._current_player_buddy_ids = set()
        self._player_cosmetic_prefetch_generation = 0
        self._player_cosmetic_prefetch_task = None
        self.map_agent_selection = dict(persisted_state.get("map_agent_selection", {}))
        self.last_standard_agent_text = initial_agent
        self.last_standard_agent_value = self.resolve_standard_agent_value(initial_agent)

        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        self.header_frame = header_frame

        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(18, 15, 18, 14)
        header_layout.setSpacing(14)

        header_layout.addWidget(self.gamemode_chip, alignment=Qt.AlignVCenter)
        header_layout.addWidget(self.server_chip, alignment=Qt.AlignVCenter)

        agent_block = QFrame()
        agent_block.setObjectName("agentBlock")
        agent_block.setFixedHeight(agent_block_height)
        agent_layout = QHBoxLayout(agent_block)
        agent_layout.setContentsMargins(11, 8, 11, 8)
        agent_layout.setSpacing(10)
        agent_layout.addWidget(self.agent_label)
        agent_layout.addWidget(self.agent_select_btn)
        agent_layout.addWidget(self.lock_agent_button)
        agent_layout.addWidget(self.auto_lock_label)
        agent_layout.addWidget(self.auto_lock_switch)
        agent_layout.addWidget(self.map_lock_label)
        agent_layout.addWidget(self.map_lock_switch)

        header_layout.addWidget(agent_block, alignment=Qt.AlignVCenter)

        header_layout.addStretch(1)

        header_layout.addWidget(self.dodge_button, alignment=Qt.AlignVCenter)
        header_layout.addWidget(self.load_more_matches_button, alignment=Qt.AlignVCenter)
        header_layout.addWidget(self.tools_button, alignment=Qt.AlignVCenter)

        header_layout.addWidget(self.refresh_button, alignment=Qt.AlignVCenter)

        left_panel, self.left_scroll_area, self.left_layout = self.build_team_panel("red")
        right_panel, self.right_scroll_area, self.right_layout = self.build_team_panel("blue")

        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setHandleWidth(4)
        main_splitter.setSizes([750, 750])

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        layout.addWidget(header_frame)
        layout.addWidget(main_splitter, 1)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.apply_theme()
        self.finalize_initial_header_metrics()
        self.lock_header_height()
        self.load_players(players or [])
        QTimer.singleShot(0, self.sync_startup_theme_metrics)
        QTimer.singleShot(0, self.refresh_player_row_heights)

        self.startup_coordinator = AppStartupCoordinator(self.set_status_message)
        self.startup_coordinator.mitm_service.set_presence_mode(self.presence_mode)
        self.party_tracker = PartyTracker.get()
        self.party_tracker.subscribe(self.on_party_data_updated)
        self.queue_snipe_service = QueueSnipeService(self.party_tracker)
        self._queue_snipe_presence_callback = self.queue_snipe_service.handle_presence_update
        self.party_tracker.subscribe(self._queue_snipe_presence_callback)
        self.party_detection_enabled = True
        self.party_group_colours = [
            ("#f7a15d", "rgba(247, 161, 93, 0.2)"),
            ("#5dc2ff", "rgba(93, 194, 255, 0.2)"),
            ("#7de38d", "rgba(125, 227, 141, 0.2)"),
            ("#d58bff", "rgba(213, 139, 255, 0.2)"),
            ("#ffe06b", "rgba(255, 224, 107, 0.2)"),
        ]
        self.party_icon = QPixmap(resource_path("assets/group.png"))
        self._party_refresh_scheduled = False
        self.startup_task = None
        self._startup_bootstrapped = False
        self.ws_task = None
        self._agent_icons_task = None
        self._rank_icons_task = None
        self._map_icons_task = None
        self._close_requested = False
        self._allow_native_close = False
        self._final_shutdown_started = False
        self._background_helper_active = False
        self._background_helper_task = None
        self._async_loop = asyncio.get_event_loop_policy().get_event_loop()
        self._activation_server = None
        self._activation_server_name = None
        self._loading_window = None
        self._loaded_asset_groups = set()
        self._initial_assets_ready = asyncio.Event()
        self._initial_window_ready = False
        self._queue_snipe_popup_dialog = None
        self._tools_popup_dialog = ToolsPopup(
            self.queue_snipe_label,
            self.queue_snipe_button,
            self.queue_snipe_switch,
            self.presence_mode_label,
            self.presence_mode_switch,
            self.themes_button,
            self.loadouts_button,
            self,
        )

        self.refreshed_pregame = None
        self.refreshed_game = None
        self.instalocked_match_id = None
        self.last_update = None

        self.seen_prematch_ids = set()
        self.seen_match_ids = set()
        self.last_seen = None

        self.puuid = None

        self._latency_start_time = None
        self.apply_restored_agent_lock_state(initial_auto_lock_enabled, initial_map_lock_enabled)
        self.apply_restored_queue_snipe_state(initial_queue_snipe_enabled, initial_queue_snipe_friend)
        self.apply_restored_presence_mode(initial_presence_mode)
        self._suspend_agent_lock_state_save = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_player_row_heights()

    def finalize_initial_header_metrics(self):
        self.ensurePolished()
        central_widget = self.centralWidget()
        if central_widget is not None:
            central_widget.ensurePolished()
            if central_widget.layout() is not None:
                central_widget.layout().activate()

        if hasattr(self, "header_frame") and self.header_frame is not None:
            self.header_frame.ensurePolished()
            if self.header_frame.layout() is not None:
                self.header_frame.layout().activate()
            self.header_frame.adjustSize()

    def lock_header_height(self):
        if not hasattr(self, "header_frame") or self.header_frame is None:
            return
        stable_height = max(
            self.header_frame.sizeHint().height(),
            self.header_frame.minimumSizeHint().height(),
        )
        self.header_frame.setFixedHeight(stable_height)

    def sync_startup_theme_metrics(self):
        self.apply_selected_theme(self.current_theme_name, persist=False, refresh_players=False)
        self.finalize_initial_header_metrics()
        self.lock_header_height()
        self.refresh_player_row_heights()

    def set_status_message(self, message):
        self.status_value.setText(message)

    def show_loading_window(self):
        self.hide()
        if self._loading_window is None:
            self._loading_window = StartupLoadingWindow()
        self._loading_window.update_progress(len(self._loaded_asset_groups), len(INITIAL_ASSET_GROUPS))
        self._loading_window.show()
        self._loading_window.raise_()
        self._loading_window.activateWindow()

    def hide_loading_window(self):
        if self._loading_window is None:
            return
        self._loading_window.hide()

    def _mark_asset_group_loaded(self, asset_group):
        self._loaded_asset_groups.add(asset_group)
        if self._loading_window is not None:
            self._loading_window.update_progress(len(self._loaded_asset_groups), len(INITIAL_ASSET_GROUPS))
        if len(self._loaded_asset_groups) >= len(INITIAL_ASSET_GROUPS):
            self._initial_assets_ready.set()

    async def wait_for_initial_assets(self):
        await self._initial_assets_ready.wait()

    def finish_initial_window_setup(self):
        if self._initial_window_ready:
            return
        self._initial_window_ready = True
        self.hide_loading_window()
        self.show()
        self.raise_()
        self.activateWindow()

    def attach_activation_server(self, activation_server, server_name):
        self._activation_server = activation_server
        self._activation_server_name = server_name
        if self._activation_server is None:
            return
        self._activation_server.newConnection.connect(self._handle_activation_connections)
        self._handle_activation_connections()

    def _handle_activation_connections(self):
        if self._activation_server is None:
            return
        while self._activation_server.hasPendingConnections():
            socket = self._activation_server.nextPendingConnection()
            if socket is None:
                continue
            socket.readyRead.connect(lambda sock=socket: self._process_activation_socket(sock))
            socket.disconnected.connect(socket.deleteLater)
            self._process_activation_socket(socket)

    def _process_activation_socket(self, socket):
        if socket is None:
            return
        socket.readAll()
        if self._async_loop.is_closed():
            self._async_loop = asyncio.get_event_loop_policy().get_event_loop()
        self._async_loop.create_task(self.restore_from_activation())
        socket.disconnectFromServer()

    async def restore_from_activation(self):
        if self._background_helper_task and not self._background_helper_task.done():
            self._background_helper_task.cancel()
        self._background_helper_task = None
        self._background_helper_active = False
        self._close_requested = False
        self._final_shutdown_started = False

        if not self._initial_window_ready:
            self.show_loading_window()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()

        self.start_asset_tasks()
        self.start_websocket_listener()
        self.queue_snipe_service.set_selected_friend(self.queue_snipe_selected_friend)
        self.queue_snipe_service.set_enabled(self.queue_snipe_switch.isChecked())
        await self.refresh_data()

    def start_runtime_tasks(self):
        loop = asyncio.get_running_loop()

        if self._startup_bootstrapped:
            self.start_asset_tasks()
            return

        if self.startup_task is None:
            self.startup_task = loop.create_task(self.bootstrap_startup())

    def start_asset_tasks(self):
        loop = asyncio.get_running_loop()

        if self._agent_icons_task is None:
            from core.asset_loader import download_and_cache_agent_icons

            self._agent_icons_task = loop.create_task(download_and_cache_agent_icons())
            self._agent_icons_task.add_done_callback(
                lambda task: QTimer.singleShot(0, lambda: self._on_agents_loaded(task))
            )

        if self._rank_icons_task is None:
            from core.asset_loader import download_and_cache_rank_icons

            self._rank_icons_task = loop.create_task(download_and_cache_rank_icons())
            self._rank_icons_task.add_done_callback(
                lambda task: QTimer.singleShot(0, lambda: self._on_ranks_loaded(task))
            )

        if self._map_icons_task is None:
            from core.asset_loader import download_and_cache_map_icons

            self._map_icons_task = loop.create_task(download_and_cache_map_icons())
            self._map_icons_task.add_done_callback(
                lambda task: QTimer.singleShot(0, lambda: self._on_maps_loaded(task))
            )

    def start_websocket_listener(self):
        if self.ws_task is None or self.ws_task.done():
            loop = asyncio.get_running_loop()
            self.ws_task = loop.create_task(self.websocket_listener())

    def set_party_detection_enabled(self, enabled):
        self.party_detection_enabled = bool(enabled)
        self.valo_rank.set_party_detection_enabled(self.party_detection_enabled)
        if not self.party_detection_enabled and self.valo_rank.frontend_data:
            if self.party_tracker.clear_party_metadata(self.valo_rank.frontend_data):
                self.safe_load_players(self.valo_rank.frontend_data)

    def on_party_data_updated(self):
        if not self.party_detection_enabled:
            return
        if self._party_refresh_scheduled:
            return
        self._party_refresh_scheduled = True
        QTimer.singleShot(0, self.apply_live_party_updates)

    def apply_live_party_updates(self):
        self._party_refresh_scheduled = False
        if not self.party_detection_enabled:
            return
        if not getattr(self.valo_rank, "frontend_data", None):
            return
        if self.valo_rank.apply_party_metadata():
            self.safe_load_players(self.valo_rank.frontend_data)

    async def bootstrap_startup(self):
        try:
            started = await self.startup_coordinator.initialize()
            if not started and self.startup_coordinator.restart_required:
                await self.prompt_restart_for_party_detection()
            else:
                self.show_loading_window()
                self.set_party_detection_enabled(self.startup_coordinator.party_detection_enabled)
                self.start_websocket_listener()
                self.queue_snipe_service.set_selected_friend(self.queue_snipe_selected_friend)
                self.queue_snipe_service.set_enabled(self.queue_snipe_switch.isChecked())
                await self.refresh_data()
        finally:
            self._startup_bootstrapped = True
            self.show_loading_window()
            self.start_asset_tasks()

    async def prompt_restart_for_party_detection(self):
        running = ", ".join(self.startup_coordinator.running_processes) or "Riot Client / Valorant"
        prompt = QMessageBox()
        prompt.setWindowTitle("Restart Riot Client")
        prompt.setIcon(QMessageBox.Question)
        prompt.setText("Party detection needs Riot Client to restart before startup can finish.")
        prompt.setInformativeText(
            f"Currently running: {running}\n\n"
            "Pressing Yes will close Valorant and Riot Client, then launch Valorant for you.\n\n"
            "Pressing No will keep ValScanner open, but party detection will stay disabled until ValScanner is restarted."
        )
        prompt.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        prompt.setDefaultButton(QMessageBox.Yes)
        prompt.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        prompt.setWindowModality(Qt.ApplicationModal)
        QTimer.singleShot(0, prompt.raise_)
        QTimer.singleShot(0, prompt.activateWindow)
        answer = prompt.exec()
        self.show_loading_window()
        if answer == QMessageBox.Yes:
            await self.startup_coordinator.restart_riot_client()
            self.set_party_detection_enabled(True)
        else:
            await self.startup_coordinator.disable_party_detection()
            self.set_party_detection_enabled(False)
            self.set_status_message("Party detection is disabled for this session.")

        self.start_websocket_listener()
        self.queue_snipe_service.set_selected_friend(self.queue_snipe_selected_friend)
        self.queue_snipe_service.set_enabled(self.queue_snipe_switch.isChecked())
        await self.refresh_data()

    def closeEvent(self, event: QCloseEvent):
        if self._allow_native_close:
            event.accept()
            return

        event.ignore()
        if self._close_requested:
            return

        self._close_requested = True
        asyncio.create_task(self.request_close())

    async def request_close(self):
        shutdown_result = await self.startup_coordinator.shutdown_for_app_exit(allow_background=True)
        if shutdown_result.get("background_helper"):
            self.enter_background_helper_mode(shutdown_result.get("running_processes", []))
            return

        await self.finalize_shutdown()

    def enter_background_helper_mode(self, running_processes):
        self._background_helper_active = True
        self._close_requested = False
        self.set_status_message("ValScanner will finish closing after Riot Client exits.")
        if hasattr(self, "queue_snipe_service") and self.queue_snipe_service:
            self.queue_snipe_service.shutdown()

        if self.ws_task and not self.ws_task.done():
            self.ws_task.cancel()
        self.ws_task = None

        if self.startup_task and not self.startup_task.done():
            self.startup_task.cancel()
        self.startup_task = None

        if self._agent_icons_task and not self._agent_icons_task.done():
            self._agent_icons_task.cancel()
        self._agent_icons_task = None

        if self._rank_icons_task and not self._rank_icons_task.done():
            self._rank_icons_task.cancel()
        self._rank_icons_task = None

        if self._map_icons_task and not self._map_icons_task.done():
            self._map_icons_task.cancel()
        self._map_icons_task = None

        if self._player_cosmetic_prefetch_task and not self._player_cosmetic_prefetch_task.done():
            self._player_cosmetic_prefetch_task.cancel()
        self._player_cosmetic_prefetch_task = None

        running = ", ".join(running_processes) or "Riot Client / Valorant"
        QMessageBox.information(
            self,
            "Closing In Background",
            f"ValScanner will stay in the background until {running} exits so Riot social features keep working.",
        )
        self.hide()

        if self._background_helper_task is None or self._background_helper_task.done():
            loop = asyncio.get_running_loop()
            self._background_helper_task = loop.create_task(self.wait_for_background_shutdown())

    async def wait_for_background_shutdown(self):
        try:
            await SharedSession.close()
            await self.startup_coordinator.wait_for_riot_processes_to_exit()
            await self.finalize_shutdown()
        except asyncio.CancelledError:
            pass

    async def finalize_shutdown(self):
        if self._final_shutdown_started:
            return

        self._final_shutdown_started = True
        self._background_helper_active = False

        await SharedSession.close()
        self._cancel_runtime_tasks()

        if hasattr(self, 'party_tracker') and self.party_tracker:
            self.party_tracker.unsubscribe(self.on_party_data_updated)
            if hasattr(self, "_queue_snipe_presence_callback") and self._queue_snipe_presence_callback:
                self.party_tracker.unsubscribe(self._queue_snipe_presence_callback)
        if hasattr(self, 'queue_snipe_service') and self.queue_snipe_service:
            self.queue_snipe_service.shutdown()
        if hasattr(self, 'startup_coordinator') and self.startup_coordinator:
            await self.startup_coordinator.shutdown()
        if self._activation_server is not None:
            self._activation_server.close()
            if self._activation_server_name:
                QLocalServer.removeServer(self._activation_server_name)
            self._activation_server = None

        self._allow_native_close = True
        app = QApplication.instance()
        if app is not None:
            app.quit()
        else:
            self.close()

    def _cancel_runtime_tasks(self):
        current_task = asyncio.current_task()
        task_names = (
            'startup_task',
            'ws_task',
            '_agent_icons_task',
            '_rank_icons_task',
            '_map_icons_task',
            '_player_cosmetic_prefetch_task',
            '_background_helper_task',
        )
        for task_name in task_names:
            task = getattr(self, task_name, None)
            if task is None or task.done() or task is current_task:
                continue
            task.cancel()
            setattr(self, task_name, None)

    def ensure_local_agent_icons(self, agent_names=None):
        if self.agent_icons is None:
            self.agent_icons = {}

        source_names = agent_names or self.owned_agent_handler.agents
        for item in source_names:
            if item not in self.agent_icons:
                icon_path = get_agent_asset_path(item)
                if os.path.exists(icon_path):
                    self.agent_icons[item] = QPixmap(icon_path)

    def get_map_specific_agent_options(self):
        agent_options = list(self.owned_agent_handler.agents)
        self.ensure_local_agent_icons(agent_options)
        return agent_options

    async def init_agents(self):
        await self.owned_agent_handler.owned_agents_func()
        self.ensure_local_agent_icons(self.owned_agent_handler.combo or self.owned_agent_handler.agents)

    def resolve_standard_agent_value(self, agent_name):
        if agent_name in MAP_SPECIFIC_ROLE_TOKENS:
            return agent_name
        return self.uuid_handler.agent_converter_reversed(agent_name)

    def get_queue_snipe_button_text(self, friend_data=None):
        normalized_friend = QueueSnipeService.normalize_friend(friend_data)
        if normalized_friend is None:
            return "Queue Snipe"
        return normalized_friend.get("display_name", "Queue Snipe")

    def build_agent_lock_state_payload(self):
        return {
            "version": APP_STATE_VERSION,
            "selected_theme": self.current_theme_name,
            "presence_mode": self.presence_mode,
            "selected_standard_agent": self.last_standard_agent_text or "Random",
            "auto_lock_enabled": self.auto_lock_switch.isChecked(),
            "map_lock_enabled": self.map_lock_switch.isChecked(),
            "queue_snipe_enabled": self.queue_snipe_switch.isChecked() and self.queue_snipe_selected_friend is not None,
            "queue_snipe_selected_friend": dict(self.queue_snipe_selected_friend) if self.queue_snipe_selected_friend else None,
            "map_agent_selection": dict(self.map_agent_selection or {}),
        }

    def persist_agent_lock_state(self):
        if getattr(self, "_suspend_agent_lock_state_save", False):
            return

        normalized_state = save_app_state(
            self.build_agent_lock_state_payload(),
            map_uuids=self.map_asset_uuids,
        )
        self.current_theme_name = normalize_theme_name(normalized_state.get("selected_theme"))
        self.presence_mode = normalize_presence_mode(normalized_state.get("presence_mode"))
        self.map_agent_selection = dict(normalized_state.get("map_agent_selection", {}))
        self.queue_snipe_selected_friend = QueueSnipeService.normalize_friend(
            normalized_state.get("queue_snipe_selected_friend")
        )
        if hasattr(self, "queue_snipe_button"):
            self.queue_snipe_button.setText(self.get_queue_snipe_button_text(self.queue_snipe_selected_friend))
        if hasattr(self, "queue_snipe_switch"):
            self.queue_snipe_switch.setEnabled(self.queue_snipe_selected_friend is not None)
        if hasattr(self, "presence_mode_switch"):
            self.presence_mode_switch.blockSignals(True)
            self.presence_mode_switch.setChecked(self.presence_mode == PRESENCE_MODE_OFFLINE)
            self.presence_mode_switch.blockSignals(False)

    def apply_restored_agent_lock_state(self, auto_lock_enabled, map_lock_enabled):
        self.auto_lock_switch.blockSignals(True)
        self.auto_lock_switch.setChecked(bool(auto_lock_enabled))
        self.auto_lock_switch.blockSignals(False)

        self.map_lock_switch.blockSignals(True)
        self.map_lock_switch.setChecked(bool(map_lock_enabled))
        self.map_lock_switch.blockSignals(False)

        if self.map_lock_switch.isChecked():
            self.agent_select_btn.setText("Map Specific")
        else:
            self.restore_standard_agent_selection()

        self.on_auto_lock_toggled(self.auto_lock_switch.isChecked())
        self.on_map_lock_toggled(self.map_lock_switch.isChecked())

    def apply_restored_queue_snipe_state(self, queue_snipe_enabled, selected_friend):
        self.queue_snipe_selected_friend = QueueSnipeService.normalize_friend(selected_friend)
        self.queue_snipe_button.setText(self.get_queue_snipe_button_text(self.queue_snipe_selected_friend))
        self.queue_snipe_switch.setEnabled(self.queue_snipe_selected_friend is not None)
        self.queue_snipe_switch.blockSignals(True)
        self.queue_snipe_switch.setChecked(bool(queue_snipe_enabled) and self.queue_snipe_selected_friend is not None)
        self.queue_snipe_switch.blockSignals(False)
        self.queue_snipe_service.set_selected_friend(self.queue_snipe_selected_friend)
        self.queue_snipe_service.set_enabled(self.queue_snipe_switch.isChecked())

    def apply_restored_presence_mode(self, presence_mode):
        self.presence_mode = normalize_presence_mode(presence_mode)
        self.presence_mode_switch.blockSignals(True)
        self.presence_mode_switch.setChecked(self.presence_mode == PRESENCE_MODE_OFFLINE)
        self.presence_mode_switch.blockSignals(False)
        if hasattr(self, "startup_coordinator") and self.startup_coordinator:
            self.startup_coordinator.mitm_service.set_presence_mode(self.presence_mode)

    def set_standard_agent_selection(self, agent_name):
        self.last_standard_agent_text = agent_name
        self.last_standard_agent_value = self.resolve_standard_agent_value(agent_name)
        if agent_name not in MAP_SPECIFIC_ROLE_TOKENS:
            self.agent = self.last_standard_agent_value

        if not self.map_lock_switch.isChecked():
            self.agent_select_btn.setText(agent_name)
        self.persist_agent_lock_state()

    def restore_standard_agent_selection(self):
        restored_text = self.last_standard_agent_text or "Random"
        self.agent_select_btn.setText(restored_text)
        if restored_text not in MAP_SPECIFIC_ROLE_TOKENS:
            self.agent = self.last_standard_agent_value or self.uuid_handler.agent_converter_reversed(restored_text)

    def on_auto_lock_toggled(self, checked):
        self.map_lock_switch.setEnabled(bool(checked))
        if checked:
            self.persist_agent_lock_state()
            return

        if self.map_lock_switch.isChecked():
            self.map_lock_switch.blockSignals(True)
            self.map_lock_switch.setChecked(False)
            self.map_lock_switch.blockSignals(False)
        self.restore_standard_agent_selection()
        self.persist_agent_lock_state()

    def on_map_lock_toggled(self, checked):
        if checked and not self.auto_lock_switch.isChecked():
            self.map_lock_switch.blockSignals(True)
            self.map_lock_switch.setChecked(False)
            self.map_lock_switch.blockSignals(False)
            self.persist_agent_lock_state()
            return

        if checked:
            self.agent_select_btn.setText("Map Specific")
        else:
            self.restore_standard_agent_selection()
        self.persist_agent_lock_state()

    def save_map_agent_selection(self, map_uuid, selection_value):
        self.map_agent_selection[map_uuid] = str(selection_value or "")
        self.persist_agent_lock_state()

    def on_queue_snipe_toggled(self, checked):
        if checked and self.queue_snipe_selected_friend is None:
            self.queue_snipe_switch.blockSignals(True)
            self.queue_snipe_switch.setChecked(False)
            self.queue_snipe_switch.blockSignals(False)
            return

        self.queue_snipe_service.set_enabled(bool(checked))
        self.persist_agent_lock_state()

    def on_queue_snipe_friend_selected(self, friend_data):
        self.queue_snipe_selected_friend = QueueSnipeService.normalize_friend(friend_data)
        self.queue_snipe_button.setText(self.get_queue_snipe_button_text(self.queue_snipe_selected_friend))
        self.queue_snipe_switch.setEnabled(self.queue_snipe_selected_friend is not None)
        self.queue_snipe_service.set_selected_friend(self.queue_snipe_selected_friend)
        self.persist_agent_lock_state()

    def on_presence_mode_toggled(self, checked):
        self.presence_mode = PRESENCE_MODE_OFFLINE if checked else "online"
        if hasattr(self, "startup_coordinator") and self.startup_coordinator:
            self.startup_coordinator.mitm_service.set_presence_mode(self.presence_mode)
        self.persist_agent_lock_state()

    def open_queue_snipe_popup(self):
        print("[QueueSnipeUI] open_queue_snipe_popup clicked")
        active_popup = getattr(self, "_queue_snipe_popup_dialog", None)
        if active_popup is not None:
            print("[QueueSnipeUI] popup already open; focusing existing dialog")
            active_popup.raise_()
            active_popup.activateWindow()
            return

        if not self.queue_snipe_button.isEnabled():
            print("[QueueSnipeUI] queue_snipe_button is disabled; ignoring click")
            return

        self.queue_snipe_button.setEnabled(False)
        print("[QueueSnipeUI] starting async friends fetch")
        asyncio.create_task(self._open_queue_snipe_popup_async())

    async def _open_queue_snipe_popup_async(self):
        print("[QueueSnipeUI] _open_queue_snipe_popup_async started")
        try:
            friends = await self.queue_snipe_service.fetch_friends()
        except Exception as exc:
            error_message = str(exc)
            print(f"[QueueSnipeUI] friends fetch failed error={error_message}")
            QTimer.singleShot(0, lambda message=error_message: self._show_queue_snipe_error(message))
            return

        print(f"[QueueSnipeUI] friends fetch succeeded count={len(friends)}")
        QTimer.singleShot(0, lambda current_friends=friends: self._show_queue_snipe_popup(current_friends))

    def _show_queue_snipe_popup(self, friends):
        print(f"[QueueSnipeUI] showing queue snipe popup with {len(friends)} friends")
        self.queue_snipe_button.setEnabled(True)
        self._queue_snipe_popup_dialog = FriendSelectionPopup(friends, self.on_queue_snipe_friend_selected, self)
        self._queue_snipe_popup_dialog.finished.connect(
            lambda *_: setattr(self, "_queue_snipe_popup_dialog", None)
        )
        self._queue_snipe_popup_dialog.open()

    def _show_queue_snipe_error(self, message):
        print(f"[QueueSnipeUI] showing queue snipe error message={message}")
        self.queue_snipe_button.setEnabled(True)
        error_box = QMessageBox(self)
        error_box.setWindowTitle("Friends Unavailable")
        error_box.setIcon(QMessageBox.Warning)
        error_box.setText("ValScanner couldn't load your friends list.")
        error_box.setInformativeText(str(message or "Unknown error."))
        error_box.setStandardButtons(QMessageBox.Ok)
        error_box.setAttribute(Qt.WA_DeleteOnClose, True)
        error_box.open()

    def open_agent_popup(self):
        active_popup = getattr(self, "_map_agent_popup_dialog", None) or getattr(self, "_agent_popup_dialog", None)
        if active_popup is not None:
            active_popup.raise_()
            active_popup.activateWindow()
            return

        if self.map_lock_switch.isChecked():
            agent_options = self.get_map_specific_agent_options()
            self.open_map_agent_popup(agent_options, agent_options)
            return

        asyncio.create_task(self._open_agent_popup_async())

    async def _open_agent_popup_async(self):
        await self.init_agents()
        combo_list = self.owned_agent_handler.agents if getattr(self.owned_agent_handler, "combo", None) else ["Random"]
        owned_list = self.owned_agent_handler.combo or ["Random"]
        QTimer.singleShot(0, lambda cl=combo_list, ol=owned_list: self._show_standard_agent_popup(cl, ol))

    def _show_standard_agent_popup(self, combo_list, owned_list):
        self._agent_popup_dialog = AgentPopup(
            combo_list,
            owned_list,
            getattr(self, "agent_icons", {}),
            self.on_agent_selected,
            self,
        )
        self._agent_popup_dialog.finished.connect(lambda *_: setattr(self, "_agent_popup_dialog", None))
        self._agent_popup_dialog.open()

    def open_map_agent_popup(self, combo_list, owned_list):
        self.map_agent_selection = ensure_map_agent_selection_data()
        self._map_agent_popup_dialog = MapAgentPopup(
            combo_list,
            owned_list,
            getattr(self, "agent_icons", {}),
            getattr(self, "map_icons", {}),
            self.uuid_handler,
            self.map_agent_selection,
            self.save_map_agent_selection,
            self,
        )
        self._map_agent_popup_dialog.finished.connect(lambda *_: setattr(self, "_map_agent_popup_dialog", None))
        self._map_agent_popup_dialog.open()

    def open_user_loadouts(self):
        if self.loadouts_button.isEnabled():
            self.loadouts_button.setEnabled(False)
            asyncio.create_task(self._open_user_loadouts_async())

    def open_tools_popup(self):
        tools_popup = getattr(self, "_tools_popup_dialog", None)
        if tools_popup is None:
            return

        if tools_popup.isVisible():
            tools_popup.raise_()
            tools_popup.activateWindow()
            return

        tools_popup.apply_theme_styles()
        tools_popup.open_near(self.tools_button)

    def open_theme_popup(self):
        active_popup = getattr(self, "_theme_popup_dialog", None)
        if active_popup is not None:
            active_popup.raise_()
            active_popup.activateWindow()
            return

        self._theme_popup_dialog = ThemePopup(self.current_theme_name, self.on_theme_selected, self)
        self._theme_popup_dialog.finished.connect(lambda *_: setattr(self, "_theme_popup_dialog", None))
        self._theme_popup_dialog.open()

    def on_theme_selected(self, theme_name):
        self.apply_selected_theme(theme_name)

    def apply_selected_theme(self, theme_name, persist=True, refresh_players=True):
        normalized_theme_name = normalize_theme_name(theme_name)
        self.current_theme_name = apply_theme_palette(normalized_theme_name)
        self.apply_theme()

        tooltip_popup = InstantTooltipMixin._tooltip_popup
        if tooltip_popup is not None:
            tooltip_popup.apply_theme_styles()

        loading_window = getattr(self, "_loading_window", None)
        if loading_window is not None:
            loading_window.apply_theme_styles()

        if hasattr(self, "auto_lock_switch"):
            self.auto_lock_switch.update()
        if hasattr(self, "map_lock_switch"):
            self.map_lock_switch.update()
        if hasattr(self, "queue_snipe_switch"):
            self.queue_snipe_switch.update()

        if persist:
            self.persist_agent_lock_state()

        current_popup = getattr(self, "_theme_popup_dialog", None)
        if current_popup is not None:
            current_popup.current_theme_name = self.current_theme_name
            current_popup.apply_theme_styles()

        tools_popup = getattr(self, "_tools_popup_dialog", None)
        if tools_popup is not None:
            tools_popup.apply_theme_styles()

        if refresh_players:
            self.load_players(getattr(self.valo_rank, "frontend_data", None) or {})

    async def _open_user_loadouts_async(self):
        try:
            handler = OwnedSkins()
            fetch_task = await handler.sort_current_loadout()
            fetch_task2 = await handler.sort_owned_items()
            loadout_skin_ids, loadout_buddy_ids = self._collect_loadout_cosmetic_ids(fetch_task.get("Skins", {}))
            await ensure_skin_asset_files(loadout_skin_ids)
            await ensure_buddy_asset_files(loadout_buddy_ids)

            self.loadouts_popup = LoadoutsPopup(
                fetch_task,
                fetch_task2,
                self.get_skin_pixmap,
                self.get_buddy_pixmap,
                self.uuid_handler,
                self,
            )
            self.loadouts_popup.finished.connect(lambda: self.loadouts_button.setEnabled(True))
            self.loadouts_popup.open()

        except Exception as e:
            self.loadouts_button.setEnabled(True)
            print(e)

    def on_agent_selected(self, agent_name):
        self.set_standard_agent_selection(agent_name)

    async def websocket_listener(self):
        while True:
            try:
                handler = LockfileHandler()
                ready = await handler.lockfile_data_function(retries=1)
                if not ready or not handler.port or not handler.password:
                    await self.startup_coordinator.ensure_riot_with_mitm()
                    self.set_status_message("Waiting for Riot Client and Valorant...")
                    await asyncio.sleep(5)
                    continue

                self.puuid = handler.puuid
                self.queue_snipe_service.set_local_self_puuid(self.puuid)

                auth = base64.b64encode(f"riot:{handler.password}".encode()).decode()
                headers = {"Authorization": f"Basic {auth}"}
                url = f"wss://127.0.0.1:{handler.port}"

                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

                print(f"Connecting to WebSocket on port {handler.port}...")

                async with websockets.connect(url, additional_headers=headers, ssl=ssl_context) as ws:
                    self.set_status_message("Connected to Riot Client. Waiting for match data...")
                    print("WebSocket Connected!")
                    self.queue_snipe_service.set_selected_friend(self.queue_snipe_selected_friend)
                    self.queue_snipe_service.set_enabled(self.queue_snipe_switch.isChecked())
                    await ws.send(json.dumps([5, "OnJsonApiEvent"]))

                    while True:
                        msg = await ws.recv()
                        if not msg:
                            continue

                        data = json.loads(msg)
                        if isinstance(data, list) and len(data) == 3 and data[0] == 8:
                            event_data = data[2]
                            uri = event_data.get("uri", "")
                            self.queue_snipe_service.handle_local_json_api_event(event_data, self.puuid)

                            if "/pregame/v1/matches" in uri:
                                prematch_id = uri[-36:]

                                if prematch_id in self.seen_prematch_ids:
                                    continue
                                self.seen_prematch_ids.add(prematch_id)

                                if self.auto_lock_switch.isChecked() and self.map_lock_switch.isChecked():
                                    self.run_valo_stats(prematch_id=prematch_id, map_instalock=True)
                                    self.last_seen = None
                                elif self.auto_lock_switch.isChecked():
                                    self.run_valo_stats(prematch_id=prematch_id)
                                    self.last_seen = None
                                    await asyncio.sleep(6.66)
                                    self.instalock_agent()
                                else:
                                    self.run_valo_stats(prematch_id=prematch_id)
                                    self.last_seen = None

                            elif "/core-game/v1/matches" in uri:
                                match_id = uri[-36:]

                                try:
                                    if match_id != prematch_id:
                                        continue
                                except Exception:
                                    continue

                                if match_id in self.seen_match_ids:
                                    continue

                                self.seen_match_ids.add(match_id)
                                print(match_id)
                                self.run_valo_stats(match_id=match_id)
                                self.last_seen = None

            except Exception as e:
                print(f"WebSocket error: {e}")
                self.set_status_message("Waiting for Riot Client and Valorant...")
                await asyncio.sleep(5)

    def _on_maps_loaded(self, task):
        try:
            self.map_icons = task.result()
        except Exception as exc:
            print(f"Map icon load failed: {exc}")
            self.map_icons = {}
        finally:
            self._mark_asset_group_loaded("maps")

    def _on_agents_loaded(self, task):
        try:
            self.agent_icons = task.result()
        except Exception as exc:
            print(f"Agent icon load failed: {exc}")
            self.agent_icons = {}
        finally:
            self._mark_asset_group_loaded("agents")

    def _on_ranks_loaded(self, task):
        try:
            self.rank_icons = task.result()
        except Exception as exc:
            print(f"Rank icon load failed: {exc}")
            self.rank_icons = {}
        finally:
            self._mark_asset_group_loaded("ranks")

    @staticmethod
    def normalize_asset_id(asset_id):
        return str(asset_id or "").strip().lower()

    def _collect_loadout_cosmetic_ids(self, loadout_skins):
        skin_ids = set()
        buddy_ids = set()
        if not isinstance(loadout_skins, dict):
            return skin_ids, buddy_ids

        for skin_data in loadout_skins.values():
            skin_id = skin_data
            buddy_id = None
            if isinstance(skin_data, list):
                skin_id = skin_data[0] if len(skin_data) > 0 else None
                buddy_id = skin_data[1] if len(skin_data) > 1 else None

            normalized_skin = self.normalize_asset_id(skin_id)
            if normalized_skin:
                skin_ids.add(normalized_skin)

            if isinstance(buddy_id, dict):
                buddy_id = buddy_id.get("CharmID", buddy_id.get("CharmLevelID", ""))
            elif isinstance(buddy_id, list):
                buddy_id = buddy_id[0] if buddy_id else None

            normalized_buddy = self.normalize_asset_id(buddy_id)
            if normalized_buddy:
                buddy_ids.add(normalized_buddy)

        return skin_ids, buddy_ids

    def collect_current_player_cosmetic_ids(self, players):
        skin_ids = set()
        buddy_ids = set()
        player_iterable = players.values() if isinstance(players, dict) else (players or [])
        for player in player_iterable:
            player_skin_ids, player_buddy_ids = self._collect_loadout_cosmetic_ids(player.get("skins") or {})
            skin_ids.update(player_skin_ids)
            buddy_ids.update(player_buddy_ids)
        return skin_ids, buddy_ids

    def get_skin_pixmap(self, asset_id, allow_load=True):
        normalized_id = self.normalize_asset_id(asset_id)
        if not normalized_id:
            return None

        pixmap = self.skin_icons.get(normalized_id)
        if pixmap is not None and not pixmap.isNull():
            return pixmap
        if not allow_load:
            return None

        pixmap = load_skin_pixmap(normalized_id)
        if pixmap is None:
            return None
        self.skin_icons[normalized_id] = pixmap
        return pixmap

    def get_buddy_pixmap(self, asset_id, allow_load=True):
        normalized_id = self.normalize_asset_id(asset_id)
        if not normalized_id:
            return None

        pixmap = self.buddy_icons.get(normalized_id)
        if pixmap is not None and not pixmap.isNull():
            return pixmap
        if not allow_load:
            return None

        pixmap = load_buddy_pixmap(normalized_id)
        if pixmap is None:
            return None
        self.buddy_icons[normalized_id] = pixmap
        return pixmap

    async def _prefetch_player_cosmetics(self, generation, skin_ids, buddy_ids):
        try:
            await ensure_skin_asset_files(skin_ids)
            await ensure_buddy_asset_files(buddy_ids)

            loaded_skin_icons = {}
            loaded_buddy_icons = {}

            for index, asset_id in enumerate(sorted(skin_ids)):
                if generation != self._player_cosmetic_prefetch_generation:
                    return
                pixmap = load_skin_pixmap(asset_id)
                if pixmap is not None:
                    loaded_skin_icons[asset_id] = pixmap
                if index % 20 == 0:
                    await asyncio.sleep(0)

            for index, asset_id in enumerate(sorted(buddy_ids)):
                if generation != self._player_cosmetic_prefetch_generation:
                    return
                pixmap = load_buddy_pixmap(asset_id)
                if pixmap is not None:
                    loaded_buddy_icons[asset_id] = pixmap
                if index % 20 == 0:
                    await asyncio.sleep(0)

            if generation != self._player_cosmetic_prefetch_generation:
                return

            self.skin_icons = {
                asset_id: pixmap for asset_id, pixmap in self.skin_icons.items()
                if asset_id in skin_ids and pixmap is not None and not pixmap.isNull()
            }
            self.skin_icons.update(loaded_skin_icons)

            self.buddy_icons = {
                asset_id: pixmap for asset_id, pixmap in self.buddy_icons.items()
                if asset_id in buddy_ids and pixmap is not None and not pixmap.isNull()
            }
            self.buddy_icons.update(loaded_buddy_icons)

            if getattr(self.valo_rank, "frontend_data", None):
                self.safe_load_players(self.valo_rank.frontend_data)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"Player cosmetic prefetch failed: {exc}")

    def schedule_player_cosmetic_prefetch(self, players):
        skin_ids, buddy_ids = self.collect_current_player_cosmetic_ids(players)
        cache_is_ready = (
            skin_ids == self._current_player_skin_ids
            and buddy_ids == self._current_player_buddy_ids
            and skin_ids.issubset(self.skin_icons.keys())
            and buddy_ids.issubset(self.buddy_icons.keys())
        )
        if cache_is_ready:
            return

        self._current_player_skin_ids = set(skin_ids)
        self._current_player_buddy_ids = set(buddy_ids)

        if self._player_cosmetic_prefetch_task and not self._player_cosmetic_prefetch_task.done():
            self._player_cosmetic_prefetch_task.cancel()
        self._player_cosmetic_prefetch_task = None

        if not skin_ids and not buddy_ids:
            self.skin_icons = {}
            self.buddy_icons = {}
            return

        self._player_cosmetic_prefetch_generation += 1
        loop = asyncio.get_running_loop()
        self._player_cosmetic_prefetch_task = loop.create_task(
            self._prefetch_player_cosmetics(
                self._player_cosmetic_prefetch_generation,
                skin_ids,
                buddy_ids,
            )
        )

    def open_skin_popup(self, player_name, skins):
        popup = WeaponPopup(
            player_name,
            skins,
            self.get_skin_pixmap,
            self.get_buddy_pixmap,
            self.uuid_handler,
            self,
        )
        popup.exec()

    def build_meta_chip(self, label_text):
        chip = QFrame()
        chip.setObjectName("metaChip")
        layout = QVBoxLayout(chip)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        label = QLabel(label_text)
        label.setObjectName("metaLabel")
        value = QLabel("Unknown")
        value.setObjectName("metaValue")

        layout.addWidget(label)
        layout.addWidget(value)

        return chip, value

    def build_team_panel(self, colour_key):
        panel = QFrame()
        panel.setObjectName("compactPanel")
        panel.setProperty("teamColor", colour_key)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(15, 15, 15, 15)
        panel_layout.setSpacing(12)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        scroll_area.setWidget(content)
        panel_layout.addWidget(scroll_area)

        return panel, scroll_area, content_layout

    def get_visible_player_row_height(self, scroll_area, layout, player_count):
        visible_rows = min(max(player_count, 1), self.MAX_VISIBLE_PLAYER_ROWS)
        viewport_height = scroll_area.viewport().height()
        if viewport_height <= 0:
            return self.MIN_PLAYER_ROW_HEIGHT

        margins = layout.contentsMargins()
        available_height = (
            viewport_height
            - margins.top()
            - margins.bottom()
            - (max(visible_rows - 1, 0) * layout.spacing())
        )
        return max(self.MIN_PLAYER_ROW_HEIGHT, available_height // visible_rows)

    def refresh_player_row_heights(self):
        self.update_team_row_heights(self.left_scroll_area, self.left_layout)
        self.update_team_row_heights(self.right_scroll_area, self.right_layout)

    def update_team_row_heights(self, scroll_area, layout):
        player_rows = [
            layout.itemAt(index).widget()
            for index in range(layout.count())
            if isinstance(layout.itemAt(index).widget(), QFrame)
        ]
        if not player_rows:
            return

        row_height = self.get_visible_player_row_height(scroll_area, layout, len(player_rows))
        for row in player_rows:
            row.setFixedHeight(row_height)

    def clear_layout(self, layout):
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())

    def build_tracker_url(self, riot_id):
        safe_text = quote(str(riot_id), safe="")
        return (
            "https://tracker.gg/valorant/profile/riot/"
            f"{safe_text}"
        )

    def create_stat_widget(self, title, value):
        wrapper = QFrame()
        wrapper.setObjectName("compactStat")
        wrapper.setMinimumWidth(75)
        wrapper.setMaximumWidth(75)
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(2)

        title_label = QLabel(title.upper())
        title_label.setObjectName("compactStatTitle")
        value_label = QLabel(value)
        value_label.setObjectName("compactStatValue")
        layout.addWidget(title_label, alignment=Qt.AlignCenter)
        layout.addWidget(value_label, alignment=Qt.AlignCenter)
        return wrapper, value_label

    def create_skin_button(self, player):
        skins = player.get("skins") or {}
        button = QPushButton()
        button.setCursor(Qt.PointingHandCursor)
        button.setObjectName("compactSkinButton")

        button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

        if skins:
            player_name = str(player.get("name", "Unknown"))
            button.clicked.connect(
                lambda _, name=player_name, data=skins: self.open_skin_popup(name, data)
            )

            vandal_data = skins.get("Vandal")
            phantom_data = skins.get("Phantom")

            vandal_id = vandal_data[0] if isinstance(vandal_data, list) and len(vandal_data) > 0 else vandal_data
            phantom_id = phantom_data[0] if isinstance(phantom_data, list) and len(phantom_data) > 0 else phantom_data

            v_pixmap = self.get_skin_pixmap(vandal_id, allow_load=False) if vandal_id else None
            p_pixmap = self.get_skin_pixmap(phantom_id, allow_load=False) if phantom_id else None

            canvas = QPixmap(140, 28)
            canvas.fill(Qt.transparent)
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)

            if v_pixmap:
                scaled_v = v_pixmap.scaled(65, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x_v = (65 - scaled_v.width()) // 2
                y_v = (28 - scaled_v.height()) // 2
                painter.drawPixmap(x_v, y_v, scaled_v)
            else:
                painter.setPen(QColor(THEME_MUTED))
                painter.drawText(0, 0, 65, 28, Qt.AlignCenter, "-")

            if p_pixmap:
                scaled_p = p_pixmap.scaled(65, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x_p = 75 + (65 - scaled_p.width()) // 2
                y_p = (28 - scaled_p.height()) // 2
                painter.drawPixmap(x_p, y_p, scaled_p)
            else:
                painter.setPen(QColor(THEME_MUTED))
                painter.drawText(75, 0, 65, 28, Qt.AlignCenter, "-")

            painter.end()

            button.setIcon(QIcon(canvas))
            button.setIconSize(QSize(140, 28))
            button.setFixedWidth(160)
        else:
            button.setText("Loadout unavailable")
            button.setEnabled(False)

        return button

    def extract_buddy_id_from_skin_data(self, skin_data):
        buddy_id = None
        if isinstance(skin_data, list):
            buddy_id = skin_data[1] if len(skin_data) > 1 else None

        if isinstance(buddy_id, dict):
            return buddy_id.get("CharmID", buddy_id.get("CharmLevelID", ""))
        if isinstance(buddy_id, list):
            return buddy_id[0] if buddy_id else None
        return buddy_id

    def player_has_buddy_equipped(self, player, buddy_uuid):
        target_buddy_id = self.normalize_asset_id(buddy_uuid)
        if not target_buddy_id:
            return False

        for skin_data in (player.get("skins") or {}).values():
            equipped_buddy_id = self.normalize_asset_id(
                self.extract_buddy_id_from_skin_data(skin_data)
            )
            if equipped_buddy_id == target_buddy_id:
                return True
        return False

    def create_buddy_indicator(self, buddy_uuid, reference_button):
        buddy_pixmap = self.get_buddy_pixmap(buddy_uuid)
        if buddy_pixmap is None or buddy_pixmap.isNull():
            return None

        reference_button.ensurePolished()
        target_height = max(
            reference_button.sizeHint().height(),
            reference_button.minimumSizeHint().height(),
            28,
        )

        scaled_buddy = buddy_pixmap.scaled(
            target_height,
            target_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        indicator = QLabel()
        indicator.setObjectName("buddyIndicator")
        indicator.setAlignment(Qt.AlignCenter)
        indicator.setPixmap(scaled_buddy)
        indicator.setFixedSize(scaled_buddy.size())
        indicator.setToolTip(buddy_uuid)
        return indicator

    def build_party_overlay(self, player):
        group_index = player.get("party_group_index")
        if group_index is None:
            return None

        border_color, _background_color = self.party_group_colours[group_index % len(self.party_group_colours)]
        overlay = QFrame()
        overlay.setFixedSize(32, 22)
        overlay.setToolTip(str(player.get("party_group_label", "Party")))
        overlay.setStyleSheet(
            "background: transparent;"
        )

        face = QFrame(overlay)
        face.setGeometry(0, 0, 32, 22)
        face.setStyleSheet(
            f"background-color: {border_color};"
            "border-top-right-radius: 12px;"
            "border-bottom-left-radius: 10px;"
            "border-bottom-right-radius: 0px;"
            "border-top-left-radius: 6px;"
        )

        icon_label = QLabel(overlay)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setGeometry(6, 2, 20, 18)

        if self.party_icon.isNull():
            icon_label.setText("P")
            icon_label.setStyleSheet(
                "color: #071222;"
                "font-size: 11px;"
                "font-weight: 900;"
            )
        else:
            tinted = self.party_icon.scaled(14, 14, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            canvas = QPixmap(20, 18)
            canvas.fill(Qt.transparent)
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawPixmap((20 - tinted.width()) // 2, (18 - tinted.height()) // 2, tinted)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(canvas.rect(), QColor("#071222"))
            painter.end()
            icon_label.setPixmap(canvas)
        icon_label.raise_()
        return overlay

    def create_player_row(self, player):
        row = QFrame()
        if player.get("puuid") == self.puuid:
            row.setObjectName("compactRowUser")
        else:
            row.setObjectName("compactRow")
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row.setMinimumHeight(self.MIN_PLAYER_ROW_HEIGHT)

        outer_layout = QVBoxLayout(row)
        outer_layout.setContentsMargins(12, 4, 4, 9)
        outer_layout.setSpacing(0)

        content_frame = PlayerRowContentFrame()
        content_layout = QGridLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(18)

        icon_wrapper = QFrame()
        icon_wrapper.setFixedSize(138, 138)

        icon_layout = QGridLayout(icon_wrapper)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setSpacing(0)

        agent_icon_label = QLabel()
        agent_icon_label.setObjectName("compactAgentIcon")
        agent_icon_label.setAlignment(Qt.AlignCenter)
        agent_icon_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        agent_name = str(player.get("agent", "Unknown"))
        agent_icon = self.agent_icons.get(agent_name)

        if agent_icon:
            agent_icon_label.setPixmap(agent_icon)
        else:
            agent_icon_label.setText(agent_name)

        level_value = player.get("level", "N/A")
        level_label = QLabel(f"{level_value}")
        level_label.setObjectName("playerLevelBadge")
        level_label.setAlignment(Qt.AlignCenter)
        icon_layout.addWidget(agent_icon_label, 0, 0)
        icon_layout.addWidget(level_label, 0, 0, Qt.AlignBottom | Qt.AlignLeft)

        row_layout.addWidget(icon_wrapper)

        info_column = QVBoxLayout()
        info_column.setContentsMargins(0, 0, 0, 0)
        info_column.setSpacing(6)

        name_row = QHBoxLayout()
        name_row.setSpacing(12)

        player_name = str(player.get("name", "Unknown"))

        name_label = QLabel()
        name_label.setObjectName("playerName")
        name_label.setTextFormat(Qt.RichText)
        name_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        name_label.setOpenExternalLinks(True)
        name_label.setText(
            f"<a href='{self.build_tracker_url(player_name)}' style='text-decoration: none;'>{escape(player_name)}</a>"
        )
        name_row.addWidget(name_label)

        vtl_label = QLabel()
        vtl_label.setTextFormat(Qt.RichText)
        vtl_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        vtl_label.setOpenExternalLinks(True)
        vtl_url = f"https://vtl.lol/id/{player.get('puuid')}"
        vtl_label.setText(f"<a href='{vtl_url}' style='text-decoration: none; font-size: 13px;'>🔗</a>")
        vtl_label.setToolTip("View on VTL.lol")
        name_row.addWidget(vtl_label)

        name_row.addStretch()

        info_column.addLayout(name_row)

        meta_bar = QHBoxLayout()
        meta_bar.setSpacing(12)

        agent_badge = QLabel(agent_name)
        agent_badge.setObjectName("agentBadge")

        skin_button = self.create_skin_button(player)
        meta_bar.addWidget(skin_button)
        if self.player_has_buddy_equipped(player, SPECIAL_BUDDY_UUID):
            buddy_indicator = self.create_buddy_indicator(SPECIAL_BUDDY_UUID, skin_button)
            if buddy_indicator is not None:
                meta_bar.addWidget(buddy_indicator, 0, Qt.AlignVCenter)
        meta_bar.addStretch(1)

        rank_icon_label = QLabel()
        rank_icon_label.setObjectName("compactRankIcon")
        rank_icon_label.setFixedSize(32, 32)
        rank_icon_label.setAlignment(Qt.AlignCenter)

        rank_name = str(player.get("rank", "Unknown"))
        rank_icon = self.rank_icons.get(rank_name)
        if rank_icon:
            rank_icon_label.setPixmap(
                rank_icon.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            rank_icon_label.setText(rank_name if rank_name not in ("[]", "") else "N/A")

        rank_text = QLabel(rank_name if rank_name not in ("[]", "") else "N/A")
        rank_text.setObjectName("metaValue")

        rr_value = str(player.get("rr", "N/A"))
        rr_label = QLabel("RR N/A" if rr_value == "N/A" else f"{rr_value} RR")
        rr_label.setObjectName("metaAux")

        peak_icon_label = QLabel()
        peak_icon_label.setObjectName("compactRankIcon")
        peak_icon_label.setFixedSize(32, 32)
        peak_icon_label.setAlignment(Qt.AlignCenter)

        peak_name = str(player.get("peak_rank", "Unknown"))
        peak_icon = self.rank_icons.get(peak_name)
        if peak_icon:
            peak_icon_label.setPixmap(
                peak_icon.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        elif peak_name == "[]":
            peak_icon_label.setText("N/A")
        else:
            peak_icon_label.setText(peak_name)

        peak_text = QLabel(peak_name if peak_name not in ("[]", "") else "N/A")
        peak_text.setObjectName("metaValue")

        peak_act_value = str(player.get("peak_act", "N/A"))
        peak_act_label = QLabel(
            peak_act_value if peak_act_value not in ("[]", "") else "Act N/A"
        )
        peak_act_label.setObjectName("metaAux")

        meta_bar.addStretch(1)

        rating_changes = player.get("rating_change", [])
        for change in rating_changes:
            text_val = str(change).replace("-", "")

            circle_label = QLabel(text_val)
            circle_label.setFixedSize(32, 32)
            circle_label.setAlignment(Qt.AlignCenter)

            try:
                val = float(change)
                if val > 0:
                    bg_color = THEME_TEAL
                    text_color = "#000000"
                elif val < 0:
                    bg_color = THEME_RED
                    text_color = THEME_TEXT
                else:
                    bg_color = "#7f7f7f"
                    text_color = THEME_TEXT
            except (ValueError, TypeError):
                bg_color = "#7f7f7f"
                text_color = THEME_TEXT

            circle_label.setStyleSheet(
                f"background-color: {bg_color}; color: {text_color}; border-radius: 16px; font-weight: 700; font-size: 11px;")

        info_column.addLayout(meta_bar)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(5)

        matches_value = str(player.get("matches", 0))
        matches_widget, _ = self.create_stat_widget("Games", matches_value)
        stats_row.addWidget(matches_widget)

        wl_value = str(player.get("wl", "N/A"))
        wl_widget, wl_label = self.create_stat_widget("W/L", wl_value)
        self.apply_stat_colour(wl_label, wl_value, "wl")
        stats_row.addWidget(wl_widget)

        acs_value = str(player.get("acs", "N/A"))
        acs_widget, acs_label = self.create_stat_widget("ACS", acs_value)
        self.apply_stat_colour(acs_label, acs_value, "acs")
        stats_row.addWidget(acs_widget)

        kd_value = str(player.get("kd", "N/A"))
        kd_widget, kd_label = self.create_stat_widget("KD", kd_value)
        self.apply_stat_colour(kd_label, kd_value, "kd")
        stats_row.addWidget(kd_widget)

        hs_raw = player.get("hs", "N/A")
        hs_value = f"{hs_raw}%" if str(hs_raw) not in ("N/A", "[]") else str(hs_raw)
        hs_widget, hs_label = self.create_stat_widget("HS", hs_value)
        self.apply_stat_colour(hs_label, str(hs_raw), "hs")
        stats_row.addWidget(hs_widget)

        stats_row.addStretch()

        info_column.addLayout(stats_row)
        row_layout.addLayout(info_column, 1)

        rank_area_layout = QHBoxLayout()
        rank_area_layout.setSpacing(30)

        left_rank_col = QVBoxLayout()
        left_rank_col.setContentsMargins(0, 0, 0, 0)
        left_rank_col.setAlignment(Qt.AlignCenter)
        left_rank_col.setSpacing(36)

        rating_changes_row = QHBoxLayout()
        rating_changes_row.setAlignment(Qt.AlignCenter)
        rating_changes_row.setSpacing(4)

        rating_changes = player.get("rating_change", [])[:3]
        for change in rating_changes:
            text_val = str(change).replace("-", "")

            circle_label = QLabel(text_val)
            circle_label.setFixedSize(34, 34)
            circle_label.setAlignment(Qt.AlignCenter)

            try:
                val = float(change)
                if val > 0:
                    bg_color = THEME_TEAL
                    text_color = "#000000"
                elif val < 0:
                    bg_color = THEME_RED
                    text_color = THEME_TEXT
                else:
                    bg_color = "#7f7f7f"
                    text_color = THEME_TEXT
            except (ValueError, TypeError):
                bg_color = "#7f7f7f"
                text_color = THEME_TEXT

            circle_label.setStyleSheet(
                f"background-color: {bg_color}; color: {text_color}; border-radius: 16px; font-weight: 700; font-size: 11px;"
            )
            rating_changes_row.addWidget(circle_label)

        left_rank_col.addLayout(rating_changes_row)

        left_rank_col.addSpacing(12)

        peak_row = QHBoxLayout()
        peak_row.setAlignment(Qt.AlignCenter)
        peak_row.setSpacing(8)

        peak_act_value = str(player.get("peak_act", "N/A"))
        peak_act_label = QLabel(peak_act_value if peak_act_value not in ("[]", "") else "N/A")
        peak_act_label.setAlignment(Qt.AlignCenter)
        peak_act_label.setStyleSheet("color: #8b96b6; font-size: 16px; font-weight: bold;")
        peak_row.addWidget(peak_act_label)

        peak_icon_label = QLabel()
        peak_icon_label.setAlignment(Qt.AlignCenter)
        peak_name = str(player.get("peak_rank", "Unknown"))
        peak_icon = self.rank_icons.get(peak_name)

        if peak_icon:
            peak_icon_label.setPixmap(
                peak_icon.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            peak_row.addWidget(peak_icon_label)
        elif peak_name not in ("[]", ""):
            peak_icon_label.setText(peak_name)
            peak_icon_label.setStyleSheet(f"color: {THEME_MUTED}; font-size: 16px; font-weight: bold;")
            peak_row.addWidget(peak_icon_label)

        left_rank_col.addLayout(peak_row)

        rank_area_layout.addLayout(left_rank_col)

        right_rank_col = QVBoxLayout()
        right_rank_col.setAlignment(Qt.AlignCenter)
        right_rank_col.setContentsMargins(0, 0, 0, 0)
        right_rank_col.setSpacing(6)

        current_rank_icon_label = QLabel()
        current_rank_icon_label.setAlignment(Qt.AlignCenter)
        current_rank_icon_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        rank_name = str(player.get("rank", "Unknown"))
        rank_icon = self.rank_icons.get(rank_name)

        if rank_icon:
            current_rank_icon_label.setPixmap(
                rank_icon.scaled(115, 115, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            current_rank_icon_label.setText(rank_name if rank_name not in ("[]", "") else "N/A")
            current_rank_icon_label.setStyleSheet(f"color: {THEME_MUTED}; font-size: 14px; font-weight: bold;")

        right_rank_col.addWidget(current_rank_icon_label, 1)

        rr_value_str = str(player.get("rr", "N/A"))
        try:
            rr_val = int(rr_value_str)
        except ValueError:
            rr_val = 0

        if rr_val >= 100:
            rr_widget = InstantTooltipLabel(f"{rr_value_str} RR")
            rr_widget.setAlignment(Qt.AlignCenter)
            rr_widget.setCursor(Qt.PointingHandCursor)
            rr_widget.set_instant_tooltip(f"{rr_value_str} RR")
            rr_widget.setFixedWidth(108)
            rr_widget.setStyleSheet(
                f"color: {THEME_ACCENT}; font-size: 14px; font-weight: 700;"
            )
        else:
            rr_widget = InstantTooltipProgressBar()
            rr_widget.setRange(0, 100)
            rr_widget.setValue(max(0, min(rr_val, 100)))
            rr_widget.setTextVisible(False)
            rr_widget.setFixedHeight(7)
            rr_widget.setFixedWidth(108)
            rr_widget.set_instant_tooltip(f"{rr_value_str} RR")
            rr_widget.setStyleSheet(
                f"QProgressBar {{ background-color: {THEME_CARD_ALT}; border-radius: 3px; border: none; }}"
                f" QProgressBar::chunk {{ background-color: {THEME_ACCENT}; border-radius: 3px; }}"
            )

        right_rank_col.addWidget(rr_widget, 0, Qt.AlignHCenter | Qt.AlignBottom)

        rank_area_layout.addLayout(right_rank_col)

        row_layout.addLayout(rank_area_layout)
        content_layout.addLayout(row_layout, 0, 0)

        content_frame.set_party_overlay(self.build_party_overlay(player))

        outer_layout.addWidget(content_frame)
        return row
    def apply_stat_colour(self, label, value, category):
        colour = None
        try:
            if category == "wl":
                val = float(str(value).replace("%", ""))
                if val < 47:
                    colour = "red"
                elif val < 53:
                    colour = "gold"
                elif val < 60:
                    colour = "limegreen"
                else:
                    colour = "cyan"
            elif category == "acs":
                val = float(value)
                if val < 200:
                    colour = "red"
                elif val < 225:
                    colour = "gold"
                elif val < 250:
                    colour = "limegreen"
                else:
                    colour = "cyan"
            elif category == "kd":
                val = float(value)
                if val < 0.9:
                    colour = "red"
                elif val < 1.1:
                    colour = "gold"
                elif val < 1.25:
                    colour = "limegreen"
                else:
                    colour = "cyan"
            elif category == "hs":
                val = float(value)
                if val < 20:
                    colour = "red"
                elif val < 30:
                    colour = "gold"
                elif val < 40:
                    colour = "limegreen"
                else:
                    colour = "cyan"
        except (TypeError, ValueError):
            colour = None

        if colour:
            label.setStyleSheet(f"color: {colour};")

    def apply_theme(self):
        base_style = (
            f"QMainWindow {{"
            f" background-color: {THEME_WINDOW};"
            f"}}"
            f"QWidget {{"
            f" color: {THEME_TEXT};"
            f" font-size: 13px;"
            f"}}"
            f"QFrame#headerFrame {{"
            f" background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            f"  stop:0 {THEME_MAIN}, stop:1 {THEME_PANEL});"
            f" border-radius: 22px;"
            f" border: 1px solid {THEME_BORDER};"
            f" padding: 3px;"
            f"}}"
            f"QProgressBar#loadingBar {{"
            f" border: none; background: {THEME_CARD};"
            f"}}"
            f"QProgressBar#loadingBar::chunk {{"
            f" background-color: {THEME_ACCENT};"
            f"}}"
            f"QLabel#sectionLabel {{"
            f" color: {THEME_MUTED};"
            f" font-size: 12px;"
            f" letter-spacing: 1.6px;"
            f" text-transform: uppercase;"
            f" font-weight: 700;"
            f"}}"
            f"QFrame#agentBlock {{"
            f" background-color: {THEME_MAIN};"
            f" border-radius: 16px;"
            f" border: 1px solid {THEME_BORDER_SOFT};"
            f"}}"
            f"QFrame#metaChip {{"
            f" background-color: {THEME_PANEL};"
            f" border-radius: 14px;"
            f" border: 1px solid {THEME_BORDER_SOFT};"
            f" min-width: 160px;"
            f"}}"
            f"QFrame#compactPanel {{"
            f" background-color: {THEME_MAIN};"
            f" border-radius: 22px;"
            f" border: 1px solid {THEME_BORDER_SOFT};"
            f"}}"
            f"QFrame#compactRow {{"
            f" background-color: {THEME_CARD};"
            f" border-radius: 16px;"
            f" border: 1px solid {THEME_BORDER_SOFT};"
            f"}}"
            f"QFrame#compactRow:hover {{"
            f" border: 1px solid {THEME_BORDER};"
            f"}}"
            f"QFrame#compactRowUser {{"
            f" background-color: {THEME_CARD_ALT};"
            f" border-radius: 16px;"
            f" border: 1px solid {THEME_ACCENT};"
            f"}}"
            f"QFrame#compactRowUser:hover {{"
            f" border: 1px solid {THEME_ACCENT_HOVER};"
            f" background-color: {THEME_PANEL};"
            f"}}"
            f"QLabel#agentBadge {{"
            f" background-color: {THEME_PANEL};"
            f" color: {THEME_ACCENT_HOVER};"
            f" border-radius: 12px;"
            f" padding: 3px 8px;"
            f" font-size: 11px;"
            f" letter-spacing: 1.2px;"
            f" text-transform: uppercase;"
            f" font-weight: 700;"
            f"}}"
            f"QLabel#metaLabel {{"
            f" color: {THEME_MUTED};"
            f" font-size: 12px;"
            f" letter-spacing: 1.6px;"
            f" text-transform: uppercase;"
            f"}}"
            f"QLabel#metaValue {{"
            f" font-size: 16px;"
            f" font-weight: 700;"
            f" color: {THEME_TEXT};"
            f"}}"
            f"QLabel#metaAux {{"
            f" color: {THEME_MUTED};"
            f" font-size: 12px;"
            f"}}"
            f"QLabel#playerName {{"
            f" font-size: 18px;"
            f" font-weight: 700;"
            f" color: {THEME_TEXT};"
            f"}}"
            f"QLabel#playerName a {{"
            f" color: inherit;"
            f" text-decoration: none;"
            f"}}"
            f"QLabel#playerName a:hover {{"
            f" color: {THEME_CYAN};"
            f"}}"
            f"QLabel#playerLevelBadge {{"
            f" background-color: {THEME_CYAN};"
            f" color: #04111a;"
            f" font-size: 16px;"
            f" font-weight: 700;"
            f" padding: 1px 4px;"
            f" border-radius: 4px;"
            f" margin: 2px;"
            f"}}"
            f"QLabel#emptyState {{"
            f" color: {THEME_MUTED};"
            f" font-style: italic;"
            f" letter-spacing: 0.6px;"
            f"}}"
            f"QFrame#compactStat {{"
            f" background-color: {THEME_CARD_ALT};"
            f" border-radius: 12px;"
            f" padding: 4px 6px;"
            f"}}"
            f"QLabel#compactStatTitle {{"
            f" color: {THEME_MUTED};"
            f" font-size: 10px;"
            f" letter-spacing: 1.2px;"
            f" text-transform: uppercase;"
            f"}}"
            f"QLabel#compactStatValue {{"
            f" font-size: 14px;"
            f" font-weight: 600;"
            f" color: {THEME_TEXT};"
            f"}}"
            f"QLabel#compactStatValue[style*=color] {{"
            f" font-weight: 700;"
            f"}}"
            f"QScrollArea {{"
            f" background: transparent;"
            f" border: none;"
            f"}}"
            f"QScrollArea > QWidget > QWidget {{"
            f" background: transparent;"
            f"}}"
            f"QPushButton {{"
            f" background-color: {THEME_CARD_ALT};"
            f" border-radius: 14px;"
            f" padding: 9px 17px;"
            f" color: {THEME_TEXT};"
            f" border: 1px solid {THEME_BORDER};"
            f" font-weight: 600;"
            f" letter-spacing: 0.6px;"
            f"}}"
            f"QPushButton:hover {{"
            f" background-color: {THEME_BORDER};"
            f"}}"
            f"QPushButton:pressed {{"
            f" background-color: {THEME_PANEL};"
            f"}}"
            f"QPushButton:disabled {{"
            f" background-color: {THEME_WINDOW};"
            f" color: #607086;"
            f" border: 1px solid {THEME_BORDER_SOFT};"
            f"}}"
            f"QPushButton#accentButton {{"
            f" background-color: {THEME_ACCENT};"
            f" border: none;"
            f"}}"
            f"QPushButton#accentButton:hover {{"
            f" background-color: {THEME_ACCENT_HOVER};"
            f"}}"
            f"QPushButton#accentButton:pressed {{"
            f" background-color: {THEME_ACCENT_PRESSED};"
            f"}}"
            f"QPushButton#secondaryButton {{"
            f" background-color: {THEME_CARD};"
            f"}}"
            f"QPushButton#dodgeButton {{"
            f" background-color: {THEME_RED};"
            f" border: none;"
            f"}}"
            f"QPushButton#dodgeButton:hover {{"
            f" background-color: {THEME_RED_HOVER};"
            f"}}"
            f"QPushButton#dodgeButton:pressed {{"
            f" background-color: {THEME_RED_PRESSED};"
            f"}}"
            f"QPushButton#refreshButton {{"
            f" background-color: {THEME_CARD};"
            f" border-radius: 20px;"
            f" border: 1px solid {THEME_BORDER};"
            f" padding: 5px;"
            f"}}"
            f"QPushButton#refreshButton:hover {{"
            f" background-color: {THEME_CARD_ALT};"
            f"}}"
            f"QPushButton#compactSkinButton {{"
            f" background-color: {THEME_PANEL};"
            f" border-radius: 12px;"
            f" padding: 4px 10px;"
            f" border: 1px solid {THEME_BORDER_SOFT};"
            f" font-size: 11px;"
            f" letter-spacing: 0.4px;"
            f" color: {THEME_TEXT};"
            f"}}"
            f"QPushButton#compactSkinButton:hover {{"
            f" background-color: {THEME_CARD_ALT};"
            f" border: 1px solid {THEME_ACCENT};"
            f"}}"
            f"QPushButton#agentSelectButton {{"
            f" background-color: {THEME_CARD_ALT};"
            f" border-radius: 12px;"
            f" padding: 8px 12px;"
            f" border: 1px solid {THEME_BORDER};"
            f" font-weight: 600;"
            f" letter-spacing: 0.5px;"
            f" color: {THEME_TEXT};"
            f" text-align: left;"
            f"}}"
            f"QPushButton#agentSelectButton:hover {{"
            f" border: 1px solid {THEME_ACCENT};"
            f" background-color: {THEME_CARD};"
            f"}}"
            f"QComboBox {{"
            f" background-color: {THEME_CARD_ALT};"
            f" border-radius: 12px;"
            f" padding: 8px 12px;"
            f" border: 1px solid {THEME_BORDER};"
            f" font-weight: 600;"
            f" letter-spacing: 0.5px;"
            f"}}"
            f"QComboBox::drop-down {{"
            f" border: none;"
            f" width: 24px;"
            f"}}"
            f"QComboBox::down-arrow {{"
            f" image: none;"
            f"}}"
            f"QScrollBar:vertical {{"
            f" background: transparent;"
            f" width: 14px;"
            f" margin: 18px 6px 18px 6px;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f" background: {THEME_BORDER};"
            f" min-height: 32px;"
            f" border-radius: 7px;"
            f"}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{"
            f" background: none;"
            f" height: 0px;"
            f"}}"
            f"QScrollBar:horizontal {{"
            f" background: transparent;"
            f" height: 14px;"
            f" margin: 6px 18px 6px 18px;"
            f"}}"
            f"QScrollBar::handle:horizontal {{"
            f" background: {THEME_BORDER};"
            f" min-width: 32px;"
            f" border-radius: 7px;"
            f"}}"
            f"QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{"
            f" background: none;"
            f" width: 0px;"
            f"}}"
        )

        self.setStyleSheet(base_style)

    def instalock_agent(self):
        if self.lock_agent_button.isEnabled():
            self.lock_agent_button.setEnabled(False)
            asyncio.create_task(self.instalock_agent_async())

    async def instalock_agent_async(self):
        try:
            await self.init_agents()
            current_text = self.agent_select_btn.text()
            if current_text == "Map Specific":
                current_map_id = None
                if isinstance(getattr(self.valo_rank, "pip", None), dict):
                    current_map_id = self.valo_rank.pip.get("MapID")
                if current_map_id:
                    await map_instalock_agent(current_map_id, self.valo_rank.handler, delay_seconds=0)
                return

            if current_text == "Random":
                rand_agent = random.randint(0, (len(self.owned_agent_handler.all_agents) - 1))
                agents = self.owned_agent_handler.all_agents
                self.agent = self.uuid_handler.agent_converter_reversed(agents[rand_agent])
            elif current_text == "Duelist":
                rand_agent = random.randint(0, (len(self.owned_agent_handler.owned_duelists) - 1))
                agents = self.owned_agent_handler.owned_duelists
                self.agent = self.uuid_handler.agent_converter_reversed(agents[rand_agent])
            elif current_text == "Initiator":
                rand_agent = random.randint(0, (len(self.owned_agent_handler.owned_initiators) - 1))
                agents = self.owned_agent_handler.owned_initiators
                self.agent = self.uuid_handler.agent_converter_reversed(agents[rand_agent])
            elif current_text == "Controller":
                rand_agent = random.randint(0, (len(self.owned_agent_handler.owned_controllers) - 1))
                agents = self.owned_agent_handler.owned_controllers
                self.agent = self.uuid_handler.agent_converter_reversed(agents[rand_agent])
            elif current_text == "Sentinel":
                rand_agent = random.randint(0, (len(self.owned_agent_handler.owned_sentinels) - 1))
                agents = self.owned_agent_handler.owned_sentinels
                self.agent = self.uuid_handler.agent_converter_reversed(agents[rand_agent])
            await instalock_agent(self.agent, self.valo_rank.handler)
        finally:
            self.lock_agent_button.setEnabled(True)

    def safe_load_players(self, data):
        QTimer.singleShot(0, lambda: self.load_players(data))

    def run_dodge_button(self):
        if self.dodge_button.isEnabled():
            self.dodge_button.setEnabled(False)
            asyncio.create_task(self._dodge_async())

    async def _dodge_async(self):
        try:
            await self.dodge_game.dodge_func(self.valo_rank.handler)
        finally:
            self.dodge_button.setEnabled(True)

    def run_valo_stats(self, prematch_id=None, match_id=None, party_id=None, map_instalock=None):
        asyncio.create_task(
            self.refresh_data(
                prematch_id=prematch_id,
                match_id=match_id,
                party_id=party_id,
                map_instalock=map_instalock
            )
        )

    def run_load_more_matches_button(self):
        if self.load_more_matches_button.isEnabled():
            self.load_more_matches_button.setEnabled(False)
            asyncio.create_task(self.run_load_more_matches())

    async def run_load_more_matches(self):
        self.refresh_button.setEnabled(False)
        try:
            await self.valo_rank.load_more_matches()
            self.safe_load_players(self.valo_rank.frontend_data)
        finally:
            self.refresh_button.setEnabled(True)
            self.load_more_matches_button.setEnabled(True)

    async def refresh_data(self, prematch_id=None, match_id=None, party_id=None, map_instalock=None):
        if not self.refresh_button.isEnabled():
            return

        self.refresh_button.setEnabled(False)
        try:
            print("Fetching latest Valorant stats...")
            handler = LockfileHandler()
            ready = await handler.lockfile_data_function(retries=1)
            if not ready:
                await self.startup_coordinator.ensure_riot_with_mitm()
                self.safe_load_players({})
                self.update_metadata()
                return
            if prematch_id or match_id or map_instalock:
                await self.valo_rank.valo_stats(prematch_id=prematch_id, match_id=match_id, map_instalock=map_instalock)
            elif party_id:
                await self.valo_rank.lobby_load(party_id=party_id)
            else:
                await self.valo_rank.valo_stats()
            print("? Data fetched. Refreshing table...")
            self.safe_load_players(self.valo_rank.frontend_data)
            self.update_metadata()
        except Exception as exc:
            print(f"Refresh failed: {exc}")
            QMessageBox.warning(
                self,
                "Refresh Failed",
                f"ValScanner couldn't refresh player data.\n\n{exc}",
            )
        finally:
            self.refresh_button.setEnabled(True)

    def load_players(self, players):
        self.left_players = []
        self.right_players = []
        self.schedule_player_cosmetic_prefetch(players)

        if not players:
            self.populate_team_layout(self.left_scroll_area, self.left_layout, [], "You will start on Defense...")
            self.populate_team_layout(self.right_scroll_area, self.right_layout, [], "You will start on Attack...")
            self.update_metadata()
            return

        player_iterable = players.values() if isinstance(players, dict) else players
        for i, player in enumerate(player_iterable):
            is_deathmatch = len(self.valo_rank.gs) > 0 and self.valo_rank.gs[0] == "Deathmatch"

            if is_deathmatch:
                if str(i / 2)[2] == "0":
                    self.left_players.append(player)
                else:
                    self.right_players.append(player)
            else:
                team = player.get("team")
                if team == "Red":
                    self.left_players.append(player)
                elif team == "Blue":
                    self.right_players.append(player)

        self.populate_team_layout(
            self.left_scroll_area, self.left_layout, self.left_players, "You will start on Defense..."
        )
        self.populate_team_layout(
            self.right_scroll_area, self.right_layout, self.right_players, "You will start on Attack..."
        )
        self.update_metadata()
        QTimer.singleShot(0, self.refresh_player_row_heights)

    def populate_team_layout(self, scroll_area, layout, players, empty_message):
        self.clear_layout(layout)
        if not players:
            layout.addStretch(1)
            placeholder = QLabel(empty_message)
            placeholder.setObjectName("emptyState")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            layout.addWidget(placeholder)
            layout.addStretch(1)
            return

        for player in players:
            layout.addWidget(self.create_player_row(player))
        layout.addStretch(1)
        self.update_team_row_heights(scroll_area, layout)

    def update_metadata(self):
        gamemode = "Unknown"
        server = "Unknown"

        gs = getattr(self.valo_rank, "gs", None)
        if isinstance(gs, (list, tuple)):
            if len(gs) > 0 and gs[0]:
                gamemode = str(gs[0])
            if len(gs) > 1 and gs[1]:
                server = str(gs[1])

        self.gamemode_value.setText(gamemode)
        self.server_value.setText(server)

class UpdatePopup(QDialog):
    def __init__(self, latest_version, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)

        container = QWidget(self)
        container.setObjectName("popupCard")
        container.setFixedSize(400, 200)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(16)

        title = QLabel("Update Available!")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        msg = QLabel(f"Version {latest_version} is available.\nYou are currently on version {CURRENT_VERSION}.")
        msg.setObjectName("subtitle")
        msg.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(msg)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        update_btn = QPushButton("Download Update")
        update_btn.setObjectName("accentButton")
        update_btn.setCursor(Qt.PointingHandCursor)
        update_btn.setFixedSize(160, 40)
        update_btn.clicked.connect(self.open_website)

        close_btn = QPushButton("Later")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(100, 40)
        close_btn.clicked.connect(self.close)

        btn_layout.addStretch()
        btn_layout.addWidget(update_btn)
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()

        main_layout.addLayout(btn_layout)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.addWidget(container)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 180))
        container.setGraphicsEffect(shadow)

        self.setStyleSheet(f"""
            #popupCard {{
                background-color: {THEME_MAIN};
                border-radius: 22px;
                border: 1px solid {THEME_BORDER_SOFT};
            }}
            #title {{ color: {THEME_TEXT}; font-size: 22px; font-weight: 600; }}
            #subtitle {{ color: {THEME_MUTED}; font-size: 14px; }}
            QPushButton {{
                background-color: {THEME_CARD_ALT};
                border: none; color: {THEME_TEXT}; font-size: 14px;
                font-weight: 700; border-radius: 12px;
            }}
            QPushButton:hover {{ background-color: {THEME_BORDER}; }}
            QPushButton#accentButton {{
                background-color: {THEME_ACCENT};
            }}
            QPushButton#accentButton:hover {{
                background-color: {THEME_ACCENT_HOVER};
            }}
        """)

    def open_website(self):
        QDesktopServices.openUrl(QUrl(WEBSITE_URL))
        self.accept()

def check_for_updates():
    try:
        response = requests.get(UPDATE_CHECK_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            latest_version = data.get("tag_name", CURRENT_VERSION).replace("v", "")
            if latest_version != CURRENT_VERSION:
                popup = UpdatePopup(latest_version)
                popup.exec()
    except Exception:
        pass


def notify_existing_instance(server_name):
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if not socket.waitForConnected(250):
        return False
    socket.write(b"show")
    socket.flush()
    socket.waitForBytesWritten(250)
    socket.disconnectFromServer()
    return True


def create_activation_server(server_name):
    activation_server = QLocalServer()
    if activation_server.listen(server_name):
        return activation_server
    QLocalServer.removeServer(server_name)
    if activation_server.listen(server_name):
        return activation_server
    raise RuntimeError(f"Unable to listen for single-instance activation on {server_name}")


async def main():
    check_for_updates()

    window = ValorantStatsWindow([])
    await window.startup_coordinator.ensure_riot_with_mitm()
    await window.bootstrap_startup()
    await window.wait_for_initial_assets()
    window.finish_initial_window_setup()
    return window


if __name__ == "__main__":
    from PySide6 import QtCore

    if notify_existing_instance(APP_INSTANCE_KEY):
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(resource_path("assets/logoone.png")))
    activation_server = create_activation_server(APP_INSTANCE_KEY)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = loop.run_until_complete(main())
    window.attach_activation_server(activation_server, APP_INSTANCE_KEY)
    with loop:
        loop.run_forever()





