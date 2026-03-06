from html import escape
from urllib.parse import quote
import time

from PySide6.QtWidgets import (
    QApplication, QMainWindow,
    QVBoxLayout, QGridLayout, QHBoxLayout, QWidget, QLabel, QPushButton,
    QComboBox, QFrame, QSplitter, QScrollArea, QDialog,
    QGraphicsDropShadowEffect, QSizePolicy, QProgressBar, QCheckBox,
    QGraphicsOpacityEffect, QLineEdit
)
from PySide6.QtCore import Qt, QTimer, QSize, QPropertyAnimation, Property, QEasingCurve
from PySide6.QtGui import QPixmap, QIcon, QFontDatabase, QFont, QColor, QPainter, QCloseEvent
import sys
import os
import random
import asyncio
import qasync
import websockets
import ssl
import base64
import json
from core.api_client import ValoRank
from core.dodge_button import dodge
from core.instalock_agent import instalock_agent
from core.valorant_uuid import UUIDHandler
from core.local_api import LockfileHandler
from core.owned_agents import OwnedAgents
from core.owned_skins import OwnedSkins
from core.player_loadout import PlayerLoadout
from core.http_session import SharedSession


def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


class VariantSelectorPopup(QDialog):
    def __init__(self, weapon, variants_list, skin_icons, uuid_handler, callback, parent=None):
        super().__init__(parent)
        self.weapon = weapon
        self.variants_list = variants_list
        self.skin_icons = skin_icons
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

        self.setStyleSheet("""
            #popupCard { background-color: #1a1f2e; border-radius: 22px; border: 1px solid rgba(255, 255, 255, 0.05); }
            #title { color: #e3e8ff; font-size: 26px; font-weight: 600; margin-bottom: 20px;}
            #skinLabel { color: #8c95b4; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; }
            #skinTile { background-color: #13192a; border-radius: 18px; border: 1px solid rgba(255, 255, 255, 0.05); }
            #skinTile:hover { border: 1px solid rgba(77, 108, 255, 0.6); background-color: #192139; }
            #skinPreview { background-color: rgba(7, 10, 19, 0.6); border-radius: 12px; border: 1px dashed rgba(255, 255, 255, 0.08); }
            #skinPreview[empty="true"] { color: #8c95b4; font-size: 11px; letter-spacing: 1px; }
            QPushButton { background-color: rgba(255, 255, 255, 0.06); border: none; color: #f4f6ff; font-size: 18px; font-weight: 700; border-radius: 16px; }
            QPushButton:hover { background-color: rgba(255, 87, 107, 0.35); }
            QToolTip { background-color: #0b0f19; color: #f4f6ff; border: 1px solid rgba(77, 108, 255, 0.3); border-radius: 4px; padding: 4px 8px; font-size: 12px; }
            QScrollBar:vertical { background: transparent; width: 14px; margin: 0px 0px 0px 0px; }
            QScrollBar::handle:vertical { background: rgba(66, 86, 124, 0.8); min-height: 32px; border-radius: 7px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { background: none; height: 0px; }
        """)

    def build_variant_tile(self, variant_id):
        tile = QPushButton()
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
            if hasattr(self, "skin_icons"):
                pixmap = self.skin_icons.get(clean_id.lower()) or self.skin_icons.get(clean_id.upper())

            if self.uuid_handler:
                try:
                    raw_name = self.uuid_handler.skin_converter(clean_id)
                    resolved_name = str(raw_name[0]) if isinstance(raw_name, list) else str(raw_name)
                except Exception:
                    pass

            tile.setToolTip(str(resolved_name))

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
    def __init__(self, weapon, owned_skins_list, owned_variants_list, skin_icons, uuid_handler, callback, parent=None):
        super().__init__(parent)
        self.weapon = weapon
        self.skin_icons = skin_icons
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

        self.setStyleSheet("""
            #popupCard { background-color: #1a1f2e; border-radius: 22px; border: 1px solid rgba(255, 255, 255, 0.05); }
            #title { color: #e3e8ff; font-size: 26px; font-weight: 600; margin-bottom: 20px;}
            #skinLabel { color: #8c95b4; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; }
            #skinTile { background-color: #13192a; border-radius: 18px; border: 1px solid rgba(255, 255, 255, 0.05); }
            #skinTile:hover { border: 1px solid rgba(77, 108, 255, 0.6); background-color: #192139; }
            #skinPreview { background-color: rgba(7, 10, 19, 0.6); border-radius: 12px; border: 1px dashed rgba(255, 255, 255, 0.08); }
            #skinPreview[empty="true"] { color: #8c95b4; font-size: 11px; letter-spacing: 1px; }
            QPushButton { background-color: rgba(255, 255, 255, 0.06); border: none; color: #f4f6ff; font-size: 18px; font-weight: 700; border-radius: 16px; }
            QPushButton:hover { background-color: rgba(255, 87, 107, 0.35); }
            QToolTip { background-color: #0b0f19; color: #f4f6ff; border: 1px solid rgba(77, 108, 255, 0.3); border-radius: 4px; padding: 4px 8px; font-size: 12px; }
            QScrollBar:vertical { background: transparent; width: 14px; margin: 0px 0px 0px 0px; }
            QScrollBar::handle:vertical { background: rgba(66, 86, 124, 0.8); min-height: 32px; border-radius: 7px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { background: none; height: 0px; }
        """)

    def build_skin_tile(self, clean_id, resolved_name):
        tile = QPushButton()
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
            if hasattr(self, "skin_icons"):
                pixmap = self.skin_icons.get(str(clean_id).lower()) or self.skin_icons.get(str(clean_id).upper())

            tile.setToolTip(str(resolved_name))

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
            popup = VariantSelectorPopup(self.weapon, variants, self.skin_icons, self.uuid_handler,
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

    def __init__(self, skins, all_skins, skin_icons, buddy_icons, uuid_handler, parent=None):
        super().__init__(parent)
        self.skins = skins.get("Skins", {})
        self.buddies = skins.get("Buddies", {})
        self.owned_skins = all_skins
        self.skin_icons = skin_icons or {}
        self.buddy_icons = buddy_icons or {}
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

        self.setStyleSheet("""
            #popupCard { background-color: #1a1f2e; border-radius: 22px; border: 1px solid rgba(255, 255, 255, 0.05); }
            #presetsCard { background-color: #13192a; border-radius: 18px; border: 1px solid rgba(255, 255, 255, 0.05); }
            #title { color: #e3e8ff; font-size: 26px; font-weight: 600; margin-bottom: 20px;}
            #skinLabel { color: #8c95b4; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; }
            QPushButton#skinTile { background-color: #13192a; border-radius: 18px; border: 1px solid rgba(255, 255, 255, 0.05); }
            QPushButton#skinTile:hover { border: 1px solid rgba(77, 108, 255, 0.6); background-color: #192139; }
            #skinPreview { background-color: rgba(7, 10, 19, 0.6); border-radius: 12px; border: 1px dashed rgba(255, 255, 255, 0.08); }
            #skinPreview[empty="true"] { color: #8c95b4; font-size: 11px; letter-spacing: 1px; }
            QPushButton { background-color: rgba(255, 255, 255, 0.06); border: none; color: #f4f6ff; font-size: 18px; font-weight: 700; border-radius: 16px; }
            QPushButton:hover { background-color: rgba(255, 87, 107, 0.35); }
            QPushButton#accentButton { background-color: #355cff; border-radius: 8px; font-size: 14px; padding: 6px 12px; }
            QPushButton#accentButton:hover { background-color: #4668ff; }
            #presetInput { background-color: rgba(7, 10, 19, 0.6); border: 1px solid rgba(86, 104, 138, 0.6); color: #f4f6ff; font-size: 14px; padding: 0 10px; border-radius: 8px; height: 36px; }
            QPushButton#submitBtn { background-color: #32e2b2; color: #000; border-radius: 8px; font-size: 14px; font-weight: bold; padding: 6px 12px; }
            QPushButton#submitBtn:hover { background-color: #40f2c0; }
            QPushButton#cancelBtn { background-color: #ff4654; color: #fff; border-radius: 8px; font-size: 14px; font-weight: bold; padding: 6px 12px; }
            QPushButton#cancelBtn:hover { background-color: #ff5e6a; }
            QPushButton#presetSaveBtn { background-color: #32e2b2; color: #000; border-radius: 8px; font-size: 16px; font-weight: bold; }
            QPushButton#presetSaveBtn:hover { background-color: #40f2c0; }
            QPushButton#presetCancelBtn { background-color: #ff4654; color: #fff; border-radius: 8px; font-size: 16px; font-weight: bold; }
            QPushButton#presetCancelBtn:hover { background-color: #ff5e6a; }
            QPushButton#presetApplyBtn { background-color: #32e2b2; color: #000; font-size: 13px; border-radius: 8px; padding: 6px 12px; font-weight: 600; }
            QPushButton#presetApplyBtn:hover { background-color: #40f2c0; }
            QToolTip { background-color: #0b0f19; color: #f4f6ff; border: 1px solid rgba(77, 108, 255, 0.3); border-radius: 4px; padding: 4px 8px; font-size: 12px; }
            #presetRow { background-color: rgba(26, 41, 64, 0.5); border-radius: 14px; border: 1px solid rgba(255, 255, 255, 0.05); }
            #presetRow:hover { border: 1px solid rgba(77, 108, 255, 0.4); background-color: rgba(36, 51, 74, 0.6); }
            #presetRowSelected { background-color: rgba(13, 19, 30, 0.9); border-radius: 14px; border: 1px solid rgba(77, 108, 255, 0.4); }
            #presetName { color: #e3e8ff; font-weight: 600; font-size: 16px; }
            QPushButton#presetDelBtn { background-color: #ff2c2c; font-size: 13px; border-radius: 8px; padding: 6px 12px; font-weight: 600; }
            QPushButton#presetDelBtn:hover { background-color: #ff4545; }
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
            result = func(preset_data, self.uuid_handler)
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
        tile = QPushButton()
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

            if hasattr(self, "skin_icons"):
                pixmap = self.skin_icons.get(str(skin_id).lower())

            if self.uuid_handler:
                try:
                    skin_name = self.uuid_handler.skin_converter(skin_id)
                    if isinstance(skin_name, list):
                        skin_name = str(skin_name[0]) if skin_name else "Unknown Skin"
                    tile.setToolTip(str(skin_name))

                    index = str(skin_name).find("Level")
                    if index >= 0:
                        skin_name = str(skin_name)[0:(index - 1)]
                    else:
                        index2 = str(skin_name).find("Variant")
                        if index2 >= 0:
                            skin_name = str(skin_name)[0:(index2 - 2)]

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
            painter.setPen(QColor("#8c95b4"))
            font = painter.font()
            font.setPixelSize(11)
            font.setLetterSpacing(QFont.AbsoluteSpacing, 1)
            painter.setFont(font)
            painter.drawText(canvas.rect(), Qt.AlignCenter, "No Skin")
            preview.setProperty("empty", "true")

        buddy_id = self.buddies.get(weapon)
        if buddy_id and hasattr(self, "buddy_icons"):
            if isinstance(buddy_id, list):
                buddy_id = buddy_id[0]
            elif isinstance(buddy_id, dict):
                buddy_id = buddy_id.get("CharmID", buddy_id.get("CharmLevelID", ""))

            buddy_pixmap = self.buddy_icons.get(str(buddy_id).lower())

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

        popup = SkinSelectorPopup(weapon, weapon_skins, owned_variants_list, self.skin_icons, self.uuid_handler,
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
        columns = 7

        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        if len(agents_list) > 5:
            main_agents = agents_list[:-5]
            bottom_agents = agents_list[-5:]
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

        self.setStyleSheet("""
            #popupCard {
                background-color: #1a1f2e;
                border-radius: 22px;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            #title { color: #e3e8ff; font-size: 22px; font-weight: 600; }
            #subtitle { color: #a0abcc; font-size: 14px; }
            #agentLabel {
                color: #8c95b4; font-size: 12px; letter-spacing: 1px;
                text-transform: uppercase;
            }
            #agentTile {
                background-color: #13192a;
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            #agentTile:hover {
                border: 1px solid rgba(77, 108, 255, 0.6);
                background-color: #192139;
            }
            #agentTileDisabled {
                background-color: #0d111c;
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 0.02);
            }
            #exitTile {
                background-color: #1f2436;
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            #exitTile QPushButton {
                background-color: rgba(255, 255, 255, 0.06);
                border: none; color: #f4f6ff; font-size: 28px;
                font-weight: 700; border-radius: 16px;
            }
            #exitTile QPushButton:hover {
                background-color: rgba(255, 87, 107, 0.35);
            }
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
            icon_label.setStyleSheet("color: #8c95b4; font-size: 24px;")

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

        exit_button = QPushButton("×")
        exit_button.setFixedSize(96, 40)
        exit_button.setCursor(Qt.PointingHandCursor)
        exit_button.clicked.connect(self.close)
        layout.addWidget(exit_button, alignment=Qt.AlignCenter)

        return tile

    def on_select(self, agent_name):
        self.callback(agent_name)
        self.accept()


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

    def __init__(self, player_name, skins, skin_icons, buddy_icons, uuid_handler, parent=None):
        super().__init__(parent)

        self.skins = skins or {}
        self.skin_icons = skin_icons or {}
        self.buddy_icons = buddy_icons or {}
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

        subtitle = QLabel("Selected weapon skins")
        subtitle.setObjectName("subtitle")
        header.addWidget(subtitle, alignment=Qt.AlignCenter)

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

        self.setStyleSheet("""
            #popupCard {
                background-color: #1a1f2e;
                border-radius: 22px;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            #title { color: #e3e8ff; font-size: 22px; font-weight: 600; }
            #subtitle { color: #a0abcc; font-size: 14px; }
            #weaponLabel {
                color: #8c95b4; font-size: 12px; letter-spacing: 1px;
                text-transform: uppercase;
            }
            #skinLabel {
                color: #d1d1d1; font-size: 12px; font-weight: 600; letter-spacing: 1px;
                text-transform: uppercase;
            }
            #skinTile {
                background-color: #13192a;
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 0.05);
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
                color: #8c95b4; font-size: 11px; letter-spacing: 1px;
            }
            #exitTile {
                background-color: #1f2436;
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            #exitTile:hover {
                background-color: rgba(255, 87, 107, 0.35);
            }
            QToolTip {
                background-color: #0b0f19; color: #f4f6ff;
                border: 1px solid rgba(77, 108, 255, 0.3);
                border-radius: 4px; padding: 4px 8px; font-size: 12px;
            }
        """)

        self.resize(1200, 750)

    def build_skin_tile(self, weapon, skin_data):
        tile = QFrame()
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

        pixmap = self.skin_icons.get(str(skin_id)) if skin_id else None

        if skin_id:
            if self.uuid_handler:
                try:
                    skin_name = self.uuid_handler.skin_converter(skin_id)
                    if isinstance(skin_name, list):
                        skin_name = str(skin_name[0]) if skin_name else "Unknown Skin"
                    tile.setToolTip(str(skin_name))

                    index = str(skin_name).find("Level")
                    if index >= 0:
                        skin_name = str(skin_name)[0:(index - 1)]
                    else:
                        index2 = str(skin_name).find("Variant")
                        if index2 >= 0:
                            skin_name = str(skin_name)[0:(index2 - 2)]

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

                    buddy_pixmap = self.buddy_icons.get(str(buddy_id).lower()) if buddy_id else None
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
            p.setBrush(QColor("#355cff"))
        else:
            p.setBrush(QColor("#162133"))

        p.drawRoundedRect(0, 0, self.width(), self.height(), 11, 11)

        p.setBrush(QColor("#f4f6ff"))
        p.drawEllipse(int(self._position), 3, 16, 16)
        p.end()


class ValorantStatsWindow(QMainWindow):
    def __init__(self, players=None):
        super().__init__()

        self.valo_rank = ValoRank()
        self.dodge_game = dodge()
        self.uuid_handler = UUIDHandler()
        self.uuid_handler.agent_uuid_function()
        self.uuid_handler.skin_uuid_function()
        self.uuid_handler.season_uuid_function()
        self.owned_agent_handler = OwnedAgents()

        font_path = resource_path("assets/fonts/unicons-line.ttf")
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
        self.setMinimumSize(1500, 860)
        self.setWindowIcon(QIcon(resource_path("assets/logoone.png")))

        self.agent_label = QLabel("Agent")
        self.agent_label.setObjectName("sectionLabel")

        initial_agent = "Random"
        self.agent_select_btn = QPushButton(initial_agent)
        self.agent_select_btn.setObjectName("agentSelectButton")
        self.agent_select_btn.setCursor(Qt.PointingHandCursor)
        self.agent_select_btn.setMinimumWidth(100)
        self.agent_select_btn.clicked.connect(self.open_agent_popup)
        self.agent = self.uuid_handler.agent_converter_reversed(initial_agent)

        self.lock_agent_button = QPushButton("Lock Agent")
        self.lock_agent_button.setCursor(Qt.PointingHandCursor)
        self.lock_agent_button.clicked.connect(self.instalock_agent)
        self.lock_agent_button.setObjectName("accentButton")

        self.auto_lock_label = QLabel("Auto-Lock")
        self.auto_lock_label.setObjectName("sectionLabel")
        self.auto_lock_switch = ToggleSwitch()
        self.auto_lock_switch.setChecked(False)

        self.loadouts_button = QPushButton("Loadouts")
        self.loadouts_button.setCursor(Qt.PointingHandCursor)
        self.loadouts_button.clicked.connect(self.open_user_loadouts)
        self.loadouts_button.setObjectName("secondaryButton")

        self.load_more_matches_button = QPushButton("Load More Matches (5)")
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
        self.refresh_button.setIconSize(QSize(52, 52))
        self.refresh_button.setFixedSize(52, 52)
        self.refresh_button.clicked.connect(self.run_valo_stats)

        self.gamemode_chip, self.gamemode_value = self.build_meta_chip("Gamemode")
        self.server_chip, self.server_value = self.build_meta_chip("Server")

        self.agent_icons = None
        self.rank_icons = None
        self.buddy_icons = None

        from core.asset_loader import download_and_cache_buddies
        task2 = asyncio.create_task(download_and_cache_buddies())
        task2.add_done_callback(self._on_buddies_loaded)

        from core.asset_loader import download_and_cache_skins
        task = asyncio.create_task(download_and_cache_skins())
        task.add_done_callback(self._on_skins_loaded)

        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")

        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(18, 15, 18, 14)
        header_layout.setSpacing(14)

        header_layout.addWidget(self.gamemode_chip, alignment=Qt.AlignVCenter)
        header_layout.addWidget(self.server_chip, alignment=Qt.AlignVCenter)

        agent_block = QFrame()
        agent_block.setObjectName("agentBlock")
        agent_layout = QHBoxLayout(agent_block)
        agent_layout.setContentsMargins(11, 8, 11, 8)
        agent_layout.setSpacing(10)
        agent_layout.addWidget(self.agent_label)
        agent_layout.addWidget(self.agent_select_btn)
        agent_layout.addWidget(self.lock_agent_button)
        agent_layout.addWidget(self.auto_lock_label)
        agent_layout.addWidget(self.auto_lock_switch)

        header_layout.addWidget(agent_block, alignment=Qt.AlignVCenter)

        header_layout.addStretch(1)

        header_layout.addWidget(self.loadouts_button, alignment=Qt.AlignVCenter)
        header_layout.addWidget(self.dodge_button, alignment=Qt.AlignVCenter)
        header_layout.addWidget(self.load_more_matches_button, alignment=Qt.AlignVCenter)

        header_layout.addWidget(self.refresh_button, alignment=Qt.AlignVCenter)

        left_panel, self.left_layout = self.build_team_panel("red")
        right_panel, self.right_layout = self.build_team_panel("blue")

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

        if players:
            self.load_players(players)

        self.ws_task = asyncio.create_task(self.websocket_listener())

        self.refreshed_pregame = None
        self.refreshed_game = None
        self.instalocked_match_id = None
        self.last_update = None

        self.seen_prematch_ids = set()
        self.seen_match_ids = set()
        self.last_seen = None

        self._latency_start_time = None

    def closeEvent(self, event: QCloseEvent):
        if not getattr(self, "_is_shutting_down", False):
            self._is_shutting_down = True
            event.ignore()
            asyncio.create_task(self.shutdown_app())
        else:
            event.accept()

    async def shutdown_app(self):
        from core.http_session import SharedSession
        await SharedSession.close()

        if hasattr(self, 'ws_task') and self.ws_task:
            self.ws_task.cancel()

        self.close()

    async def init_agents(self):
        await self.owned_agent_handler.owned_agents_func()

        from core.asset_loader import download_and_cache_agent_icons
        self.agent_icons = await download_and_cache_agent_icons()

        from core.asset_loader import download_and_cache_rank_icons
        self.rank_icons = await download_and_cache_rank_icons()

        if self.owned_agent_handler.combo:
            initial_agent = self.owned_agent_handler.combo[-5]
            self.agent_select_btn.setText(initial_agent)
            self.agent = self.uuid_handler.agent_converter_reversed(initial_agent)

            for item in self.owned_agent_handler.combo:
                if item not in self.agent_icons:
                    icon_path = resource_path(f"assets/agents/{item}.png")
                    if os.path.exists(icon_path):
                        self.agent_icons[item] = QPixmap(icon_path)

    def open_agent_popup(self):
        combo_list = self.owned_agent_handler.agents if getattr(self.owned_agent_handler, "combo", None) else ["Random"]
        owned_list = self.owned_agent_handler.combo
        popup = AgentPopup(combo_list, owned_list, getattr(self, "agent_icons", {}), self.on_agent_selected, self)
        popup.exec()

    def open_user_loadouts(self):
        if self.loadouts_button.isEnabled():
            self.loadouts_button.setEnabled(False)
            asyncio.create_task(self._open_user_loadouts_async())

    async def _open_user_loadouts_async(self):
        try:
            handler = OwnedSkins()
            fetch_task = await handler.sort_current_loadout()
            fetch_task2 = await handler.sort_owned_items()

            self.loadouts_popup = LoadoutsPopup(fetch_task, fetch_task2, getattr(self, "skin_icons", {}),
                                                getattr(self, "buddy_icons", {}), self.uuid_handler, self)
            self.loadouts_popup.finished.connect(lambda: self.loadouts_button.setEnabled(True))
            self.loadouts_popup.open()

        except Exception as e:
            self.loadouts_button.setEnabled(True)
            print(e)

    def on_agent_selected(self, agent_name):
        self.agent_select_btn.setText(agent_name)
        self.agent = self.uuid_handler.agent_converter_reversed(agent_name)

    async def websocket_listener(self):
        while True:
            try:
                handler = LockfileHandler()
                await handler.lockfile_data_function()

                if not handler.port or not handler.password:
                    await asyncio.sleep(5)
                    continue

                auth = base64.b64encode(f"riot:{handler.password}".encode()).decode()
                headers = {"Authorization": f"Basic {auth}"}
                url = f"wss://127.0.0.1:{handler.port}"

                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

                print(f"Connecting to WebSocket on port {handler.port}...")

                async with websockets.connect(url, additional_headers=headers, ssl=ssl_context) as ws:
                    print("WebSocket Connected!")
                    await ws.send(json.dumps([5, "OnJsonApiEvent"]))

                    while True:
                        msg = await ws.recv()
                        if not msg:
                            continue

                        data = json.loads(msg)
                        if isinstance(data, list) and len(data) == 3 and data[0] == 8:
                            event_data = data[2]
                            uri = event_data.get("uri", "")

                            if "/pregame/v1/matches" in uri:
                                prematch_id = uri[-36:]

                                if prematch_id in self.seen_prematch_ids:
                                    continue
                                self.seen_prematch_ids.add(prematch_id)

                                self.run_valo_stats(prematch_id=prematch_id)

                                self.last_seen = None

                                if self.auto_lock_switch.isChecked():
                                    await asyncio.sleep(6.75)
                                    self.instalock_agent()

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
                await asyncio.sleep(5)

    def _on_skins_loaded(self, task):
        self.skin_icons = task.result()
        self.safe_load_players(self.valo_rank.frontend_data)

    def _on_buddies_loaded(self, task):
        self.buddy_icons = task.result()

    def open_skin_popup(self, player_name, skins):
        popup = WeaponPopup(
            player_name,
            skins,
            getattr(self, "skin_icons", {}),
            getattr(self, "buddy_icons", {}),
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
        panel_layout.setContentsMargins(15, 12, 15, 15)
        panel_layout.setSpacing(12)

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
            f"{safe_text}/overview?platform=pc&playlist=competitive&season=3ea2b318-423b-cf86-25da-7cbb0eefbe2d"
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

        button.setFixedHeight(32)
        button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        button.setText("SKINS")

        if skins:
            player_name = str(player.get("name", "Unknown"))
            button.clicked.connect(
                lambda _, name=player_name, data=skins: self.open_skin_popup(name, data)
            )
        else:
            button.setText("Loadout unavailable")
            button.setEnabled(False)

        return button

    def create_player_row(self, player):
        row = QFrame()
        row.setObjectName("compactRow")
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 9, 12, 9)
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
        vtl_label.setText(f"<a href='{vtl_url}' style='text-decoration: none; font-size: 16px;'>🔗</a>")
        vtl_label.setToolTip("View on VTL.lol")
        name_row.addWidget(vtl_label)

        skin_button = self.create_skin_button(player)
        name_row.addWidget(skin_button)
        name_row.addStretch(1)

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
                    bg_color = "#32e2b2"
                    text_color = "#000000"
                elif val < 0:
                    bg_color = "#ff4654"
                    text_color = "#ffffff"
                else:
                    bg_color = "#7f7f7f"
                    text_color = "#ffffff"
            except (ValueError, TypeError):
                bg_color = "#7f7f7f"
                text_color = "#ffffff"

            circle_label.setStyleSheet(
                f"background-color: {bg_color}; color: {text_color}; border-radius: 16px; font-weight: 700; font-size: 11px;")

        info_column.addLayout(meta_bar)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(5)

        matches_value = str(player.get("matches", 0))
        matches_widget, _ = self.create_stat_widget("Match", matches_value)
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
        rank_area_layout.setSpacing(12)

        left_rank_col = QVBoxLayout()
        left_rank_col.setContentsMargins(0, 0, 0, 0)

        rating_changes_row = QHBoxLayout()
        rating_changes_row.setAlignment(Qt.AlignRight | Qt.AlignTop)
        rating_changes_row.setSpacing(2)

        rating_changes = player.get("rating_change", [])
        for change in rating_changes:
            text_val = str(change).replace("-", "")

            circle_label = QLabel(text_val)
            circle_label.setFixedSize(28, 28)
            circle_label.setAlignment(Qt.AlignCenter)

            try:
                val = float(change)
                if val > 0:
                    bg_color = "#32e2b2"
                    text_color = "#000000"
                elif val < 0:
                    bg_color = "#ff4654"
                    text_color = "#ffffff"
                else:
                    bg_color = "#7f7f7f"
                    text_color = "#ffffff"
            except (ValueError, TypeError):
                bg_color = "#7f7f7f"
                text_color = "#ffffff"

            circle_label.setStyleSheet(
                f"background-color: {bg_color}; color: {text_color}; border-radius: 14px; font-weight: 700; font-size: 10px;"
            )
            rating_changes_row.addWidget(circle_label)

        left_rank_col.addLayout(rating_changes_row)
        left_rank_col.addStretch(1)

        peak_row = QHBoxLayout()
        peak_row.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        peak_row.setSpacing(4)

        peak_icon_label = QLabel()
        peak_name = str(player.get("peak_rank", "Unknown"))
        peak_icon = self.rank_icons.get(peak_name)

        if peak_icon:
            peak_icon_label.setPixmap(
                peak_icon.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            peak_row.addWidget(peak_icon_label)

        peak_act_value = str(player.get("peak_act", "N/A"))
        peak_act_label = QLabel(peak_act_value if peak_act_value not in ("[]", "") else "N/A")
        peak_act_label.setStyleSheet("color: #8b96b6; font-size: 30px;")
        peak_row.addWidget(peak_act_label)

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
                rank_icon.scaled(130, 130, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            current_rank_icon_label.setText(rank_name if rank_name not in ("[]", "") else "N/A")
            current_rank_icon_label.setStyleSheet("color: #8c95b4; font-size: 14px; font-weight: bold;")

        right_rank_col.addWidget(current_rank_icon_label, 1)

        rr_value_str = str(player.get("rr", "N/A"))
        try:
            rr_val = int(rr_value_str)
        except ValueError:
            rr_val = 0

        rr_bar = QProgressBar()
        rr_bar.setRange(0, 100)
        rr_bar.setValue(rr_val)
        rr_bar.setTextVisible(False)
        rr_bar.setFixedHeight(7)
        rr_bar.setFixedWidth(108)
        rr_bar.setToolTip(f"{rr_value_str} RR")
        rr_bar.setStyleSheet(
            "QProgressBar { background-color: rgba(255, 255, 255, 0.05); border-radius: 3px; border: none; } QProgressBar::chunk { background-color: #355cff; border-radius: 3px; }")

        right_rank_col.addWidget(rr_bar, 0, Qt.AlignHCenter | Qt.AlignBottom)

        rank_area_layout.addLayout(right_rank_col)

        row_layout.addLayout(rank_area_layout)

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
            "QFrame#compactPanel {"
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
            "QLabel#playerLevelBadge {"
            " background-color: #5dd8fc;"
            " color: #000000;"
            " font-size: 16px;"
            " font-weight: 700;"
            " padding: 1px 4px;"
            " border-radius: 4px;"
            " margin: 2px;"
            "}"
            "QLabel#emptyState {"
            " color: #7e8aa7;"
            " font-style: italic;"
            " letter-spacing: 0.6px;"
            "}"
            "QFrame#compactStat {"
            " background-color: rgba(20, 28, 44, 0.82);"
            " border-radius: 12px;"
            " padding: 6px 9px;"
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
            "QPushButton#agentSelectButton {"
            " background-color: rgba(23, 34, 52, 0.85);"
            " border-radius: 12px;"
            " padding: 8px 12px;"
            " border: 1px solid rgba(86, 104, 138, 0.6);"
            " font-weight: 600;"
            " letter-spacing: 0.5px;"
            " color: #f4f6ff;"
            " text-align: left;"
            "}"
            "QPushButton#agentSelectButton:hover {"
            " border: 1px solid rgba(128, 151, 196, 0.7);"
            " background-color: rgba(30, 45, 65, 0.95);"
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

    def instalock_agent(self):
        if self.lock_agent_button.isEnabled():
            self.lock_agent_button.setEnabled(False)
            asyncio.create_task(self.instalock_agent_async())

    async def instalock_agent_async(self):
        try:
            current_text = self.agent_select_btn.text()
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

    def run_valo_stats(self, prematch_id=None, match_id=None, party_id=None):
        if prematch_id:
            asyncio.create_task(self.refresh_data(prematch_id=prematch_id))
        elif match_id:
            asyncio.create_task(self.refresh_data(match_id=match_id))
        elif party_id:
            asyncio.create_task(self.refresh_data(party_id=party_id))
        else:
            asyncio.create_task(self.refresh_data())

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

    async def refresh_data(self, prematch_id=None, match_id=None, party_id=None):
        if not self.refresh_button.isEnabled():
            return

        self.refresh_button.setEnabled(False)
        try:
            print("Fetching latest Valorant stats...")
            if prematch_id:
                await self.valo_rank.valo_stats(prematch_id=prematch_id)
            elif match_id:
                await self.valo_rank.valo_stats(match_id=match_id)
            elif party_id:
                await self.valo_rank.lobby_load(party_id=party_id)
            else:
                await self.valo_rank.valo_stats()
            print("✅ Data fetched. Refreshing table...")
            self.safe_load_players(self.valo_rank.frontend_data)
            self.update_metadata()
        finally:
            self.refresh_button.setEnabled(True)

    def load_players(self, players):
        self.left_players = []
        self.right_players = []

        if not players:
            self.populate_team_layout(self.left_layout, [], "Waiting for Attacking team...")
            self.populate_team_layout(self.right_layout, [], "Waiting for Defending team...")
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

        self.populate_team_layout(self.left_layout, self.left_players, "Waiting for Attacking team...")
        self.populate_team_layout(self.right_layout, self.right_players, "Waiting for Defending team...")
        self.update_metadata()

    def populate_team_layout(self, layout, players, empty_message):
        self.clear_layout(layout)
        if not players:
            placeholder = QLabel(empty_message)
            placeholder.setObjectName("emptyState")
            placeholder.setAlignment(Qt.AlignCenter)
            layout.addWidget(placeholder)
            return

        for player in players:
            layout.addWidget(self.create_player_row(player))

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


async def main():
    window = ValorantStatsWindow([])
    window.show()
    await window.init_agents()
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