from html import escape
from urllib.parse import quote

from PySide6.QtWidgets import (
    QApplication, QMainWindow,
    QVBoxLayout, QGridLayout, QHBoxLayout, QWidget, QLabel, QPushButton,
    QComboBox, QFrame, QSplitter, QScrollArea, QStackedWidget, QToolButton,
    QButtonGroup, QDialog, QGraphicsDropShadowEffect, QSizePolicy, QProgressBar
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QPixmap, QIcon, QFontDatabase, QFont, QColor
import sys
import os
import random
import asyncio
import qasync
from core.api_client import ValoRank
from core.dodge_button import dodge
from core.instalock_agent import instalock_agent
from core.valorant_uuid import UUIDHandler

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller .exe"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

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

    def __init__(self, player_name, skins, skin_icons, parent=None):
        super().__init__(parent)

        self.skins = skins or {}
        self.skin_icons = skin_icons or {}
        player_display = player_name or "Unknown"

        self.setWindowFlags(
            Qt.Dialog |
            Qt.FramelessWindowHint |
            Qt.Popup
        )

        self.setAttribute(Qt.WA_TranslucentBackground)

        container = QWidget()
        container.setObjectName("popupCard")

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(16)

        header = QVBoxLayout()
        header.setSpacing(6)
        header.setAlignment(Qt.AlignCenter)

        title = QLabel(f"{player_display}'s Loadout")
        title.setTextFormat(Qt.PlainText)
        title.setObjectName("title")
        header.addWidget(title, alignment=Qt.AlignCenter)

        subtitle = QLabel("Selected weapon skins")
        subtitle.setObjectName("subtitle")
        header.addWidget(subtitle, alignment=Qt.AlignCenter)

        main_layout.addLayout(header)

        self.tile_width = 170
        self.tile_height = 120

        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        columns = 4

        for index, weapon in enumerate(self.WEAPON_ORDER):
            row = index // columns
            column = index % columns
            grid.addWidget(self.build_skin_tile(weapon, self.skins.get(weapon)), row, column)

        exit_tile_index = len(self.WEAPON_ORDER)
        exit_row = exit_tile_index // columns
        exit_col = exit_tile_index % columns
        grid.addWidget(self.build_exit_tile(), exit_row, exit_col)

        main_layout.addLayout(grid)

        outer = QVBoxLayout(self)
        outer.addWidget(container)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 180))
        container.setGraphicsEffect(shadow)

        self.setStyleSheet("""
            #popupCard {
                background-color: #1a1f2e;
                border-radius: 22px;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            #title {
                color: #e3e8ff;
                font-size: 22px;
                font-weight: 600;
            }
            #subtitle {
                color: #a0abcc;
                font-size: 14px;
            }
            #weaponLabel {
                color: #8c95b4;
                font-size: 12px;
                letter-spacing: 1px;
                text-transform: uppercase;
            }
            #skinTile {
                background-color: #13192a;
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 0.05);
                min-width: 150px;
                min-height: 110px;
            }
            #skinTile:hover {
                border: 1px solid rgba(77, 108, 255, 0.6);
                background-color: #192139;
            }
            #skinPreview {
                background-color: rgba(7, 10, 19, 0.6);
                border-radius: 12px;
                border: 1px dashed rgba(255, 255, 255, 0.08);
            }
            #skinPreview[empty="true"] {
                color: #8c95b4;
                font-size: 11px;
                letter-spacing: 1px;
            }
            #exitTile {
                background-color: #1f2436;
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            #exitTile QPushButton {
                background-color: rgba(255, 255, 255, 0.06);
                border: none;
                color: #f4f6ff;
                font-size: 28px;
                font-weight: 700;
                border-radius: 16px;
            }
            #exitTile QPushButton:hover {
                background-color: rgba(255, 87, 107, 0.35);
            }
        """)

        self.resize(960, 540)

    def build_skin_tile(self, weapon, skin_id):
        tile = QFrame()
        tile.setObjectName("skinTile")
        tile.setFixedSize(self.tile_width, self.tile_height)

        tile_layout = QVBoxLayout(tile)
        tile_layout.setContentsMargins(12, 12, 12, 12)
        tile_layout.setSpacing(8)
        tile_layout.setAlignment(Qt.AlignCenter)

        weapon_label = QLabel(weapon)
        weapon_label.setObjectName("weaponLabel")
        weapon_label.setAlignment(Qt.AlignCenter)
        tile_layout.addWidget(weapon_label)

        preview = QLabel()
        preview.setObjectName("skinPreview")
        preview.setAlignment(Qt.AlignCenter)
        preview.setMinimumSize(120, 70)
        preview.setProperty("empty", "false")

        pixmap = None
        if skin_id:
            if hasattr(self, "skin_icons"):
                pixmap = self.skin_icons.get(str(skin_id))
            else:
                pixmap = None

        if pixmap:
            preview.setPixmap(
                pixmap.scaled(120, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            preview.setText("No Preview")
            preview.setProperty("empty", "true")

        preview.style().unpolish(preview)
        preview.style().polish(preview)

        tile_layout.addWidget(preview)
        return tile

    def build_exit_tile(self):
        tile = QFrame()
        tile.setObjectName("exitTile")
        tile.setFixedSize(self.tile_width, self.tile_height)

        layout = QVBoxLayout(tile)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        label = QLabel("Close")
        label.setObjectName("weaponLabel")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        exit_button = QPushButton("×")
        exit_button.setFixedSize(96, 48)
        exit_button.clicked.connect(self.close)
        layout.addWidget(exit_button, alignment=Qt.AlignCenter)

        return tile

class ValorantStatsWindow(QMainWindow):
    def __init__(self, players=None):
        super().__init__()

        self.valo_rank = ValoRank()
        self.dodge_game = dodge()
        self.uuid_handler = UUIDHandler()
        self.uuid_handler.agent_uuid_function()

        font_path = resource_path("assets/fonts/proximanova_regular.ttf")
        print("🔍 Loading font from:", font_path)

        font_id = QFontDatabase.addApplicationFont(font_path)
        font_families = QFontDatabase.applicationFontFamilies(font_id)

        if font_families:
            app_font = QFont(font_families[0], 11)
            QApplication.setFont(app_font)
            print(f"✅ Loaded font: {font_families[0]}")
        else:
            print("⚠️ Failed to load custom font, falling back to default.")

        self.setWindowTitle("Who Will They Be")
        self.setMinimumSize(1200, 720)
        self.setWindowIcon(QIcon(resource_path("assets/logoone.png")))

        # Instalock agent list
        self.agent_label = QLabel("Agent")
        self.agent_label.setObjectName("sectionLabel")
        self.combo = QComboBox()
        self.combo.currentTextChanged.connect(self.on_selection_changed)
        self.combo.addItems([
            "Random", "Astra", "Breach", "Brimstone", "Chamber", "Clove", "Cypher",
            "Deadlock", "Fade", "Gekko", "Harbor", "Iso", "Jett", "KAY/O",
            "Killjoy", "Neon", "Omen", "Phoenix", "Raze", "Reyna", "Sage",
            "Skye", "Sova", "Tejo", "Veto", "Viper", "Vyse", "Waylay", "Yoru"
        ])
        self.combo.setCurrentIndex(0)
        self.combo.setMinimumWidth(200)
        self.agent = self.uuid_handler.agent_converter_reversed(self.combo.currentText())

        # Primary actions
        self.lock_agent_button = QPushButton("Lock Agent")
        self.lock_agent_button.clicked.connect(self.instalock_agent)
        self.lock_agent_button.setObjectName("accentButton")

        self.load_more_matches_button = QPushButton("Load More Matches (10)")
        self.load_more_matches_button.clicked.connect(self.run_load_more_matches_button)
        self.load_more_matches_button.setObjectName("secondaryButton")

        self.dodge_button = QPushButton("Dodge Game")
        self.dodge_button.clicked.connect(self.run_dodge_button)
        self.dodge_button.setObjectName("dodgeButton")

        self.refresh_button = QPushButton()
        self.refresh_button.setIcon(QIcon(resource_path("assets/refresh.png")))
        self.refresh_button.setObjectName("refreshButton")
        self.refresh_button.setIconSize(QSize(52, 52))
        self.refresh_button.setFixedSize(52, 52)
        self.refresh_button.clicked.connect(self.run_valo_stats)

        # Meta display chips
        self.gamemode_chip, self.gamemode_value = self.build_meta_chip("Gamemode")
        self.server_chip, self.server_value = self.build_meta_chip("Server")

        # View toggle control
        self.view_toggle = self.build_view_toggle()
        self.view_mode = "cards"

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setObjectName("loadingBar")
        self.progress_bar.hide()

        # Preload assets
        from core.asset_loader import download_and_cache_agent_icons
        self.agent_icons = download_and_cache_agent_icons()

        from core.asset_loader import download_and_cache_rank_icons
        self.rank_icons = download_and_cache_rank_icons()

        from core.asset_loader import download_and_cache_skins
        task = asyncio.create_task(download_and_cache_skins())
        task.add_done_callback(self._on_skins_loaded)

        # ─────────────── Layout ───────────────
        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(18, 15, 18, 14)
        header_layout.setSpacing(14)

        title_row = QHBoxLayout()
        title_row.setSpacing(18)

        title_block = QVBoxLayout()
        title_block.setSpacing(4)
        chip_row = QHBoxLayout()
        chip_row.setSpacing(12)
        chip_row.addWidget(self.gamemode_chip)
        chip_row.addWidget(self.server_chip)
        chip_row.addStretch(1)
        title_block.addLayout(chip_row)

        title_row.addLayout(title_block, stretch=1)
        title_row.addWidget(self.view_toggle, alignment=Qt.AlignVCenter)
        title_row.addWidget(self.refresh_button, alignment=Qt.AlignVCenter)
        header_layout.addLayout(title_row)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(14)

        agent_block = QFrame()
        agent_block.setObjectName("agentBlock")
        agent_layout = QHBoxLayout(agent_block)
        agent_layout.setContentsMargins(11, 8, 11, 8)
        agent_layout.setSpacing(10)
        agent_layout.addWidget(self.agent_label)
        agent_layout.addWidget(self.combo)
        agent_layout.addWidget(self.lock_agent_button)

        controls_row.addWidget(agent_block, stretch=0)
        controls_row.addStretch(1)
        controls_row.addWidget(self.dodge_button)
        controls_row.addWidget(self.load_more_matches_button)
        header_layout.addLayout(controls_row)

        # Views
        left_card_panel, self.card_left_layout = self.build_card_team_panel("red")
        right_card_panel, self.card_right_layout = self.build_card_team_panel("blue")

        card_splitter = QSplitter(Qt.Horizontal)
        card_splitter.addWidget(left_card_panel)
        card_splitter.addWidget(right_card_panel)
        card_splitter.setChildrenCollapsible(False)
        card_splitter.setOpaqueResize(True)
        card_splitter.setHandleWidth(4)
        card_splitter.setSizes([750, 750])

        # Compact Panel Splitter (Using QSplitter so users can adjust width)
        left_compact_panel, self.compact_left_layout = self.build_compact_team_panel("red")
        right_compact_panel, self.compact_right_layout = self.build_compact_team_panel("blue")

        compact_splitter = QSplitter(Qt.Horizontal)
        compact_splitter.addWidget(left_compact_panel)
        compact_splitter.addWidget(right_compact_panel)
        compact_splitter.setChildrenCollapsible(False)
        compact_splitter.setHandleWidth(4)
        compact_splitter.setSizes([750, 750])

        self.view_stack = QStackedWidget()
        self.view_stack.addWidget(card_splitter)
        self.view_stack.addWidget(compact_splitter)

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        layout.addWidget(header_frame)
        layout.addWidget(self.progress_bar) # Added Progress Bar here
        layout.addWidget(self.view_stack, 1)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.apply_theme()
        self.set_view_mode("compact")

        # Populate players if initial data provided
        if players:
            self.load_players(players)

    # ---------------------------------------------------------
    # Utility setup methods
    # ---------------------------------------------------------
    def _on_skins_loaded(self, task):
        self.skin_icons = task.result()
        self.safe_load_players(self.valo_rank.frontend_data)

    def open_skin_popup(self, player_name, skins):
        popup = WeaponPopup(player_name, skins, getattr(self, "skin_icons", {}), self)
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

    def build_view_toggle(self):
        container = QFrame()
        container.setObjectName("viewToggle")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(6)

        button_group = QButtonGroup(container)
        button_group.setExclusive(True)

        options = [
            ("Expanded", "cards"),
            ("Compact", "compact"),
        ]

        self.view_buttons = {}
        for index, (text, mode) in enumerate(options):
            button = QToolButton()
            button.setObjectName("viewToggleButton")
            button.setText(text)
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            layout.addWidget(button)
            button_group.addButton(button, index)
            button.clicked.connect(lambda checked, m=mode: self.set_view_mode(m))
            self.view_buttons[mode] = button

        self.view_button_group = button_group
        return container

    def set_view_mode(self, mode):
        if not hasattr(self, "view_stack"):
            return

        index = 0 if mode == "cards" else 1
        if mode not in ("cards", "compact"):
            return

        self.view_stack.setCurrentIndex(index)
        self.view_mode = mode

        if hasattr(self, "view_buttons"):
            for key, button in self.view_buttons.items():
                button.blockSignals(True)
                button.setChecked(key == mode)
                button.blockSignals(False)

    def build_card_team_panel(self, colour_key):
        panel = QFrame()
        panel.setObjectName("teamPanel")
        panel.setProperty("teamColor", colour_key)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(15, 12, 15, 15)
        panel_layout.setSpacing(12)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)
        content_layout.setAlignment(Qt.AlignTop)

        scroll_area.setWidget(content)
        panel_layout.addWidget(scroll_area)
        return panel, content_layout

    def build_compact_team_panel(self, colour_key):
        panel = QFrame()
        panel.setObjectName("compactPanel")
        panel.setProperty("teamColor", colour_key)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(15, 12, 15, 15)
        panel_layout.setSpacing(12)

        # Added Scroll Area here for Compact view too
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        content_layout.setAlignment(Qt.AlignTop)

        scroll_area.setWidget(content)
        panel_layout.addWidget(scroll_area)

        return panel, content_layout

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
            f"{safe_text}/overview?platform=pc&playlist=competitive&season=4c4b8cff-43eb-13d3-8f14-96b783c90cd2"
        )

    def create_stat_widget(self, title, value):
        wrapper = QFrame()
        wrapper.setObjectName("statWidget")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title_label = QLabel(title.upper())
        title_label.setObjectName("statTitle")
        value_label = QLabel(value)
        value_label.setObjectName("statValue")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return wrapper, value_label

    def create_compact_stat(self, title, value):
        wrapper = QFrame()
        wrapper.setObjectName("compactStat")
        # Added minimum width to prevent disappearing when resized
        wrapper.setMinimumWidth(65)
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

    def create_skin_button(self, player, compact=False):
        skins = player.get("skins") or {}
        button = QPushButton()
        button.setCursor(Qt.PointingHandCursor)
        button.setObjectName("compactSkinButton" if compact else "skinButton")

        if compact:
            button.setFixedHeight(32)
            button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

        if skins:
            if compact:
                button.setText("SKINS")
            else:
                button.setText("SKINS")
            player_name = str(player.get("name", "Unknown"))
            button.clicked.connect(
                lambda _, name=player_name, data=skins: self.open_skin_popup(name, data)
            )
        else:
            button.setText("Loadout unavailable")
            button.setEnabled(False)

        return button

    def create_player_card(self, player):
        card = QFrame()
        card.setObjectName("playerCard")
        card.setMinimumHeight(0)

        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(24)

        agent_icon_label = QLabel()
        agent_icon_label.setObjectName("agentIcon")
        agent_icon_label.setFixedSize(64, 64)
        agent_icon_label.setAlignment(Qt.AlignCenter)

        agent_name = str(player.get("agent", "Unknown"))
        agent_icon = self.agent_icons.get(agent_name)
        if agent_icon:
            agent_icon_label.setPixmap(
                agent_icon.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            agent_icon_label.setText(agent_name)
        card_layout.addWidget(agent_icon_label)

        info_column = QVBoxLayout()
        info_column.setContentsMargins(0, 0, 0, 0)
        info_column.setSpacing(12)

        # Name and level row
        name_row = QHBoxLayout()
        name_row.setSpacing(12)

        player_name = str(player.get("name", "Unknown"))
        name_label = QLabel()
        name_label.setObjectName("playerName")
        name_label.setTextFormat(Qt.RichText)
        name_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        name_label.setOpenExternalLinks(True)
        name_label.setText(
            f"<a href='{self.build_tracker_url(player_name)}'>{escape(player_name)}</a>"
        )
        name_row.addWidget(name_label, 1)

        level_value = player.get("level", "N/A")
        level_label = QLabel(f"Lv. {level_value}")
        level_label.setObjectName("playerLevel")
        name_row.addWidget(level_label, alignment=Qt.AlignRight)
        info_column.addLayout(name_row)

        # Rank and peak information
        meta_row = QHBoxLayout()
        meta_row.setSpacing(20)

        rank_container = QVBoxLayout()
        rank_container.setSpacing(6)
        rank_title = QLabel("Rank")
        rank_title.setObjectName("metaTitle")
        rank_container.addWidget(rank_title)

        rank_display = QHBoxLayout()
        rank_display.setSpacing(10)

        rank_icon_label = QLabel()
        rank_icon_label.setObjectName("rankIcon")
        rank_icon_label.setFixedSize(44, 44)
        rank_icon_label.setAlignment(Qt.AlignCenter)

        rank_name = str(player.get("rank", "Unknown"))
        rank_icon = self.rank_icons.get(rank_name)
        if rank_icon:
            rank_icon_label.setPixmap(
                rank_icon.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            rank_icon_label.setText(rank_name if rank_name not in ("[]", "") else "N/A")
        rank_display.addWidget(rank_icon_label)

        rank_text = QLabel(rank_name if rank_name not in ("[]", "") else "N/A")
        rank_text.setObjectName("metaValue")
        rank_display.addWidget(rank_text)

        rr_value = str(player.get("rr", "N/A"))
        rr_label = QLabel("RR N/A" if rr_value == "N/A" else f"{rr_value} RR")
        rr_label.setObjectName("metaAux")
        rank_display.addWidget(rr_label)

        rank_display.addStretch(1)
        rank_container.addLayout(rank_display)
        meta_row.addLayout(rank_container)

        peak_container = QVBoxLayout()
        peak_container.setSpacing(6)
        peak_title = QLabel("Peak Rank")
        peak_title.setObjectName("metaTitle")
        peak_container.addWidget(peak_title)

        peak_display = QHBoxLayout()
        peak_display.setSpacing(10)

        peak_icon_label = QLabel()
        peak_icon_label.setObjectName("peakIcon")
        peak_icon_label.setFixedSize(44, 44)
        peak_icon_label.setAlignment(Qt.AlignCenter)

        peak_name = str(player.get("peak_rank", "Unknown"))
        peak_icon = self.rank_icons.get(peak_name)
        if peak_icon:
            peak_icon_label.setPixmap(
                peak_icon.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        elif peak_name == "[]":
            peak_icon_label.setText("N/A")
        else:
            peak_icon_label.setText(peak_name)
        peak_display.addWidget(peak_icon_label)

        peak_text = QLabel(peak_name if peak_name not in ("[]", "") else "N/A")
        peak_text.setObjectName("metaValue")
        peak_display.addWidget(peak_text)

        peak_display.addStretch(1)
        peak_container.addLayout(peak_display)
        meta_row.addLayout(peak_container)

        info_column.addLayout(meta_row)

        stats_grid = QGridLayout()
        stats_grid.setHorizontalSpacing(24)
        stats_grid.setVerticalSpacing(10)

        matches_value = str(player.get("matches", 0))
        matches_widget, _ = self.create_stat_widget("Matches", matches_value)
        stats_grid.addWidget(matches_widget, 0, 0)

        wl_value = str(player.get("wl", "N/A"))
        wl_widget, wl_label = self.create_stat_widget("W/L", wl_value)
        self.apply_stat_colour(wl_label, wl_value, "wl")
        stats_grid.addWidget(wl_widget, 0, 1)

        acs_value = str(player.get("acs", "N/A"))
        acs_widget, acs_label = self.create_stat_widget("ACS", acs_value)
        self.apply_stat_colour(acs_label, acs_value, "acs")
        stats_grid.addWidget(acs_widget, 0, 2)

        kd_value = str(player.get("kd", "N/A"))
        kd_widget, kd_label = self.create_stat_widget("KD", kd_value)
        self.apply_stat_colour(kd_label, kd_value, "kd")
        stats_grid.addWidget(kd_widget, 1, 0)

        hs_raw = player.get("hs", "N/A")
        hs_value = f"{hs_raw}%" if str(hs_raw) not in ("N/A", "[]") else str(hs_raw)
        hs_widget, hs_label = self.create_stat_widget("HS", hs_value)
        self.apply_stat_colour(hs_label, str(hs_raw), "hs")
        stats_grid.addWidget(hs_widget, 1, 1)

        peak_act_value = str(player.get("peak_act", "N/A"))
        peak_act_widget, _ = self.create_stat_widget("Peak Act", peak_act_value)
        stats_grid.addWidget(peak_act_widget, 1, 2)

        info_column.addLayout(stats_grid)

        skin_button = self.create_skin_button(player)
        info_column.addWidget(skin_button, alignment=Qt.AlignLeft)
        card_layout.addLayout(info_column, 1)

        return card

    def create_compact_player_row(self, player):
        row = QFrame()
        row.setObjectName("compactRow")

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 9, 12, 9)
        row_layout.setSpacing(18)

        agent_icon_label = QLabel()
        agent_icon_label.setObjectName("compactAgentIcon")
        agent_icon_label.setFixedSize(48, 48)
        agent_icon_label.setAlignment(Qt.AlignCenter)

        agent_name = str(player.get("agent", "Unknown"))
        agent_icon = self.agent_icons.get(agent_name)
        if agent_icon:
            agent_icon_label.setPixmap(
                agent_icon.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            agent_icon_label.setText(agent_name)

        row_layout.addWidget(agent_icon_label)

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
            f"<a href='{self.build_tracker_url(player_name)}'>{escape(player_name)}</a>"
        )
        # Added minimum width for name so it doesn't vanish
        name_label.setMinimumWidth(100)
        name_row.addWidget(name_label, 1)

        level_value = player.get("level", "N/A")
        level_label = QLabel(f"Lv. {level_value}")
        level_label.setObjectName("playerLevel")
        name_row.addWidget(level_label, alignment=Qt.AlignRight)

        info_column.addLayout(name_row)

        meta_bar = QHBoxLayout()
        meta_bar.setSpacing(12)

        agent_badge = QLabel(agent_name)
        agent_badge.setObjectName("agentBadge")
        meta_bar.addWidget(agent_badge)

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
        meta_bar.addWidget(rank_icon_label)

        rank_text = QLabel(rank_name if rank_name not in ("[]", "") else "N/A")
        rank_text.setObjectName("metaValue")
        meta_bar.addWidget(rank_text)

        rr_value = str(player.get("rr", "N/A"))
        rr_label = QLabel("RR N/A" if rr_value == "N/A" else f"{rr_value} RR")
        rr_label.setObjectName("metaAux")
        meta_bar.addWidget(rr_label)

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
        meta_bar.addWidget(peak_icon_label)

        peak_text = QLabel(peak_name if peak_name not in ("[]", "") else "N/A")
        peak_text.setObjectName("metaValue")
        meta_bar.addWidget(peak_text)

        peak_act_value = str(player.get("peak_act", "N/A"))
        peak_act_label = QLabel(
            peak_act_value if peak_act_value not in ("[]", "") else "Act N/A"
        )
        peak_act_label.setObjectName("metaAux")
        meta_bar.addWidget(peak_act_label)

        skin_button = self.create_skin_button(player, compact=True)
        meta_bar.addWidget(skin_button)

        meta_bar.addStretch(1)
        info_column.addLayout(meta_bar)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)

        matches_value = str(player.get("matches", 0))
        matches_widget, _ = self.create_compact_stat("Matches", matches_value)
        stats_row.addWidget(matches_widget)

        wl_value = str(player.get("wl", "N/A"))
        wl_widget, wl_label = self.create_compact_stat("W/L", wl_value)
        self.apply_stat_colour(wl_label, wl_value, "wl")
        stats_row.addWidget(wl_widget)

        acs_value = str(player.get("acs", "N/A"))
        acs_widget, acs_label = self.create_compact_stat("ACS", acs_value)
        self.apply_stat_colour(acs_label, acs_value, "acs")
        stats_row.addWidget(acs_widget)

        kd_value = str(player.get("kd", "N/A"))
        kd_widget, kd_label = self.create_compact_stat("KD", kd_value)
        self.apply_stat_colour(kd_label, kd_value, "kd")
        stats_row.addWidget(kd_widget)

        hs_raw = player.get("hs", "N/A")
        hs_value = f"{hs_raw}%" if str(hs_raw) not in ("N/A", "[]") else str(hs_raw)
        hs_widget, hs_label = self.create_compact_stat("HS", hs_value)
        self.apply_stat_colour(hs_label, str(hs_raw), "hs")
        stats_row.addWidget(hs_widget)

        info_column.addLayout(stats_row)

        row_layout.addLayout(info_column, 1)

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
            "QMainWindow {"
            " background-color: #05070c;"
            "}"
            "QWidget {"
            " color: #f4f6ff;"
            " font-size: 13px;"
            "}"
            "QFrame#headerFrame {"
            " background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            "  stop:0 #101626, stop:1 #070a11);"
            " border-radius: 22px;"
            " border: 1px solid rgba(63, 76, 107, 0.45);"
            " padding: 3px;"
            "}"
            "QProgressBar#loadingBar {"
            " border: none; background: rgba(255,255,255,0.05);"
            "}"
            "QProgressBar#loadingBar::chunk {"
            " background-color: #355cff;"
            "}"
            "QLabel#appTitle {"
            " font-size: 24px;"
            " font-weight: 800;"
            " letter-spacing: 1.4px;"
            "}"
            "QLabel#headerLogo {"
            " min-height: 96px;"
            "}"
            "QLabel#sectionLabel {"
            " color: #9aa4c4;"
            " font-size: 12px;"
            " letter-spacing: 1.6px;"
            " text-transform: uppercase;"
            " font-weight: 700;"
            "}"
            "QFrame#agentBlock {"
            " background-color: rgba(13, 19, 30, 0.92);"
            " border-radius: 16px;"
            " border: 1px solid rgba(63, 76, 107, 0.35);"
            "}"
            "QFrame#metaChip {"
            " background-color: rgba(15, 22, 35, 0.88);"
            " border-radius: 14px;"
            " border: 1px solid rgba(63, 76, 107, 0.35);"
            " min-width: 160px;"
            "}"
            "QFrame#viewToggle {"
            " background-color: rgba(18, 27, 42, 0.9);"
            " border-radius: 18px;"
            " border: 1px solid rgba(63, 76, 107, 0.4);"
            "}"
            "QToolButton#viewToggleButton {"
            " background: transparent;"
            " border: none;"
            " color: #8f9abd;"
            " font-weight: 600;"
            " padding: 6px 14px;"
            " border-radius: 14px;"
            "}"
            "QToolButton#viewToggleButton:hover {"
            " background-color: rgba(53, 92, 255, 0.15);"
            " color: #c7d3ff;"
            "}"
            "QToolButton#viewToggleButton:checked {"
            " background-color: #355cff;"
            " color: #ffffff;"
            "}"
            "QFrame#teamPanel, QFrame#compactPanel {"
            " background-color: rgba(11, 15, 25, 0.92);"
            " border-radius: 22px;"
            " border: 1px solid rgba(63, 76, 107, 0.35);"
            "}"
            "QFrame#compactRow {"
            " background-color: rgba(13, 18, 30, 0.92);"
            " border-radius: 16px;"
            " border: 1px solid rgba(63, 76, 107, 0.3);"
            "}"
            "QFrame#compactRow:hover {"
            " border: 1px solid rgba(86, 104, 138, 0.6);"
            "}"
            "QLabel#agentBadge {"
            " background-color: rgba(53, 92, 255, 0.18);"
            " color: #a7bbff;"
            " border-radius: 12px;"
            " padding: 3px 8px;"
            " font-size: 11px;"
            " letter-spacing: 1.2px;"
            " text-transform: uppercase;"
            " font-weight: 700;"
            "}"
            "QLabel#metaLabel {"
            " color: #7e8aa7;"
            " font-size: 12px;"
            " letter-spacing: 1.6px;"
            " text-transform: uppercase;"
            "}"
            "QLabel#metaValue {"
            " font-size: 16px;"
            " font-weight: 700;"
            " color: #f7f8ff;"
            "}"
            "QLabel#metaAux {"
            " color: #8b96b6;"
            " font-size: 12px;"
            "}"
            "QLabel#metaTitle {"
            " color: #7e8aa7;"
            " font-size: 11px;"
            " letter-spacing: 1.2px;"
            " text-transform: uppercase;"
            "}"
            "QLabel#playerName {"
            " font-size: 18px;"
            " font-weight: 700;"
            " color: #f7f8ff;"
            "}"
            "QLabel#playerName a {"
            " color: inherit;"
            " text-decoration: none;"
            "}"
            "QLabel#playerName a:hover {"
            " color: #6bc2ff;"
            "}"
            "QLabel#playerLevel {"
            " color: #9aa4c4;"
            " font-size: 13px;"
            " font-weight: 600;"
            " letter-spacing: 0.8px;"
            "}"
            "QLabel#emptyState {"
            " color: #7e8aa7;"
            " font-style: italic;"
            " letter-spacing: 0.6px;"
            "}"
            "QFrame#playerCard {"
            " background-color: rgba(13, 18, 30, 0.92);"
            " border-radius: 18px;"
            " border: 1px solid rgba(63, 76, 107, 0.35);"
            "}"
            "QFrame#playerCard:hover {"
            " border: 1px solid rgba(86, 104, 138, 0.65);"
            "}"
            "QFrame#compactStat {"
            " background-color: rgba(20, 28, 44, 0.82);"
            " border-radius: 12px;"
            " padding: 6px 9px;"
            "}"
            "QFrame#statWidget {"
            " background-color: rgba(20, 28, 44, 0.85);"
            " border-radius: 12px;"
            " padding: 9px 11px;"
            "}"
            "QLabel#statTitle {"
            " color: #7e8aa7;"
            " font-size: 11px;"
            " letter-spacing: 1.2px;"
            " text-transform: uppercase;"
            "}"
            "QLabel#statValue {"
            " font-size: 16px;"
            " font-weight: 600;"
            " color: #f4f6ff;"
            "}"
            "QLabel#compactStatTitle {"
            " color: #7e8aa7;"
            " font-size: 10px;"
            " letter-spacing: 1.2px;"
            " text-transform: uppercase;"
            "}"
            "QLabel#compactStatValue {"
            " font-size: 14px;"
            " font-weight: 600;"
            " color: #f4f6ff;"
            "}"
            "QLabel#compactStatValue[style*=color] {"
            " font-weight: 700;"
            "}"
            "QScrollArea {"
            " background: transparent;"
            " border: none;"
            "}"
            "QScrollArea > QWidget > QWidget {"
            " background: transparent;"
            "}"
            "QPushButton {"
            " background-color: #162133;"
            " border-radius: 14px;"
            " padding: 9px 17px;"
            " color: #f4f6ff;"
            " border: 1px solid rgba(86, 104, 138, 0.6);"
            " font-weight: 600;"
            " letter-spacing: 0.6px;"
            "}"
            "QPushButton:hover {"
            " background-color: #1e2c44;"
            "}"
            "QPushButton:pressed {"
            " background-color: #121b2b;"
            "}"
            "QPushButton:disabled {"
            " background-color: #0d121c;"
            " color: #5d6577;"
            " border: 1px solid #151b29;"
            "}"
            "QPushButton#accentButton {"
            " background-color: #355cff;"
            " border: none;"
            "}"
            "QPushButton#accentButton:hover {"
            " background-color: #4668ff;"
            "}"
            "QPushButton#accentButton:pressed {"
            " background-color: #2a4bd1;"
            "}"
            "QPushButton#secondaryButton {"
            " background-color: rgba(26, 41, 64, 0.85);"
            "}"
            "QPushButton#dodgeButton {"
            " background-color: #b94a48;"
            " border: none;"
            "}"
            "QPushButton#dodgeButton:hover {"
            " background-color: #c55b59;"
            "}"
            "QPushButton#dodgeButton:pressed {"
            " background-color: #a14341;"
            "}"
            "QPushButton#refreshButton {"
            " background-color: rgba(26, 39, 60, 0.85);"
            " border-radius: 26px;"
            " border: 1px solid rgba(86, 104, 138, 0.6);"
            " padding: 9px;"
            "}"
            "QPushButton#refreshButton:hover {"
            " background-color: rgba(44, 63, 95, 0.95);"
            "}"
            "QPushButton#skinButton {"
            " background-color: rgba(18, 27, 42, 0.9);"
            " border-radius: 12px;"
            " text-align: left;"
            " padding: 8px 14px;"
            " border: 1px solid rgba(86, 104, 138, 0.45);"
            " font-size: 12px;"
            " letter-spacing: 0.4px;"
            " color: #dfe6ff;"
            "}"
            "QPushButton#skinButton:hover {"
            " background-color: rgba(30, 43, 65, 0.95);"
            " border: 1px solid rgba(128, 151, 196, 0.7);"
            "}"
            "QPushButton#compactSkinButton {"
            " background-color: rgba(18, 27, 42, 0.9);"
            " border-radius: 12px;"
            " padding: 4px 10px;"
            " border: 1px solid rgba(86, 104, 138, 0.45);"
            " font-size: 11px;"
            " letter-spacing: 0.4px;"
            " color: #dfe6ff;"
            "}"
            "QPushButton#compactSkinButton:hover {"
            " background-color: rgba(30, 43, 65, 0.95);"
            " border: 1px solid rgba(128, 151, 196, 0.7);"
            "}"
            "QComboBox {"
            " background-color: rgba(23, 34, 52, 0.85);"
            " border-radius: 12px;"
            " padding: 8px 12px;"
            " border: 1px solid rgba(86, 104, 138, 0.6);"
            " font-weight: 600;"
            " letter-spacing: 0.5px;"
            "}"
            "QComboBox::drop-down {"
            " border: none;"
            " width: 24px;"
            "}"
            "QComboBox::down-arrow {"
            " image: none;"
            "}"
            "QScrollBar:vertical {"
            " background: transparent;"
            " width: 14px;"
            " margin: 18px 6px 18px 6px;"
            "}"
            "QScrollBar::handle:vertical {"
            " background: rgba(66, 86, 124, 0.8);"
            " min-height: 32px;"
            " border-radius: 7px;"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            " background: none;"
            " height: 0px;"
            "}"
            "QScrollBar:horizontal {"
            " background: transparent;"
            " height: 14px;"
            " margin: 6px 18px 6px 18px;"
            "}"
            "QScrollBar::handle:horizontal {"
            " background: rgba(66, 86, 124, 0.8);"
            " min-width: 32px;"
            " border-radius: 7px;"
            "}"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {"
            " background: none;"
            " width: 0px;"
            "}"
        )

        self.setStyleSheet(base_style)

    def on_selection_changed(self, text):
        self.agent = self.uuid_handler.agent_converter_reversed(text)

    def instalock_agent(self):
        self.lock_agent_button.setEnabled(False)
        try:
            if self.combo.currentText() == "Random":
                rand_agent = random.randint(0, 28)
                agents = [
                    "Astra", "Breach", "Brimstone", "Chamber", "Clove", "Cypher",
                    "Deadlock", "Fade", "Gekko", "Harbor", "Iso", "Jett", "KAY/O",
                    "Killjoy", "Neon", "Omen", "Phoenix", "Raze", "Reyna", "Sage",
                    "Skye", "Sova", "Tejo", "Veto", "Viper", "Vyse", "Waylay", "Yoru"
                ]
                self.agent = self.uuid_handler.agent_converter_reversed(agents[rand_agent])
            instalock_agent(self.agent)
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
            await self.dodge_game.dodge_func()
        finally:
            self.dodge_button.setEnabled(True)

    def run_valo_stats(self):
        asyncio.create_task(self.refresh_data())

    def run_load_more_matches_button(self):
        if self.load_more_matches_button.isEnabled():
            self.load_more_matches_button.setEnabled(False)
            asyncio.create_task(self.run_load_more_matches())

    async def run_load_more_matches(self):
        self.refresh_button.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)
        try:
            await self.valo_rank.load_more_matches()
            self.safe_load_players(self.valo_rank.frontend_data)
        finally:
            self.refresh_button.setEnabled(True)
            self.load_more_matches_button.setEnabled(True)
            self.progress_bar.hide()

    async def refresh_data(self):
        if not self.refresh_button.isEnabled():
            return

        self.refresh_button.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0) # Indeterminate mode
        try:
            print("Fetching latest Valorant stats...")
            await self.valo_rank.valo_stats()
            print("✅ Data fetched. Refreshing table...")
            self.safe_load_players(self.valo_rank.frontend_data)
            self.update_metadata()
        finally:
            self.refresh_button.setEnabled(True)
            self.progress_bar.hide()

    # ---------------------------------------------------------
    # Main data-loading logic (two-column layout)
    # ---------------------------------------------------------
    def load_players(self, players):
        self.left_players = []
        self.right_players = []

        if not players:
            self.populate_card_layout(self.card_left_layout, [], "Waiting for Red team...")
            self.populate_card_layout(self.card_right_layout, [], "Waiting for Blue team...")
            self.populate_compact_layout(self.compact_left_layout, [], "Waiting for Red team...")
            self.populate_compact_layout(self.compact_right_layout, [], "Waiting for Blue team...")
            self.update_metadata()
            return

        player_iterable = players.values() if isinstance(players, dict) else players
        for i, player in enumerate(player_iterable):
            if self.valo_rank.gs[0] == "Deathmatch":
                print(str(i/2)[2])
                if str(i/2)[2] == "0":
                    self.left_players.append(player)
                else:
                    self.right_players.append(player)
            else:
                team = player.get("team")
                if team == "Red":
                    self.left_players.append(player)
                elif team == "Blue":
                    self.right_players.append(player)

        self.populate_card_layout(self.card_left_layout, self.left_players, "Waiting for Red team...")
        self.populate_card_layout(self.card_right_layout, self.right_players, "Waiting for Blue team...")
        self.populate_compact_layout(self.compact_left_layout, self.left_players, "Waiting for Red team...")
        self.populate_compact_layout(self.compact_right_layout, self.right_players, "Waiting for Blue team...")
        self.update_metadata()

    def populate_card_layout(self, layout, players, empty_message):
        self.clear_layout(layout)
        if not players:
            placeholder = QLabel(empty_message)
            placeholder.setObjectName("emptyState")
            placeholder.setAlignment(Qt.AlignCenter)
            layout.addWidget(placeholder)
            return

        for player in players:
            layout.addWidget(self.create_player_card(player))

    def populate_compact_layout(self, layout, players, empty_message):
        self.clear_layout(layout)
        if not players:
            placeholder = QLabel(empty_message)
            placeholder.setObjectName("emptyState")
            placeholder.setAlignment(Qt.AlignCenter)
            layout.addWidget(placeholder)
            return

        for player in players:
            layout.addWidget(self.create_compact_player_row(player))

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


# ---------------------------------------------------------
# Async entry point for qasync
# ---------------------------------------------------------
async def main():
    window = ValorantStatsWindow([])
    window.show()
    asyncio.create_task(window.refresh_data())
    return window


if __name__ == "__main__":
    from PySide6 import QtCore
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("assets/logoone.png")))
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = loop.run_until_complete(main())
    with loop:
        loop.run_forever()