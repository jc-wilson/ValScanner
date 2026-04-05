import json
import os
import sys
import tempfile

from core.presence_mode import DEFAULT_PRESENCE_MODE, normalize_presence_mode

APP_STATE_VERSION = 4
APP_STATE_RELATIVE_PATH = os.path.join("agent_selection", "app_state.json")
LEGACY_MAP_SELECTION_RELATIVE_PATH = os.path.join("agent_selection", "map_agent_selection.json")
DEFAULT_THEME_NAME = "midnight"
VALID_THEME_NAMES = {
    "midnight",
    "sandstorm",
    "amethyst",
    "emberglass",
    "bailey",
    "glacier",
    "rosewood",
    "horizon",
    "liquidglass",
}


def get_external_path(relative_path, base_path=None):
    if base_path is not None:
        return os.path.join(os.fspath(base_path), relative_path)

    if getattr(sys, "frozen", False):
        root_path = os.path.dirname(sys.executable)
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_path = os.path.abspath(os.path.join(current_dir, ".."))

    return os.path.join(root_path, relative_path)


def discover_map_asset_uuids(base_path=None):
    maps_dir = get_external_path(os.path.join("assets", "maps"), base_path=base_path)
    if not os.path.isdir(maps_dir):
        return []

    map_uuids = []
    for file_name in os.listdir(maps_dir):
        stem, ext = os.path.splitext(file_name)
        if ext.lower() == ".png":
            map_uuids.append(stem)
    return sorted(map_uuids)


def get_app_state_path(base_path=None):
    return get_external_path(APP_STATE_RELATIVE_PATH, base_path=base_path)


def get_legacy_map_selection_path(base_path=None):
    return get_external_path(LEGACY_MAP_SELECTION_RELATIVE_PATH, base_path=base_path)


def default_app_state(map_uuids=None, base_path=None):
    normalized_map_uuids = list(map_uuids) if map_uuids is not None else discover_map_asset_uuids(base_path=base_path)
    return {
        "version": APP_STATE_VERSION,
        "selected_theme": DEFAULT_THEME_NAME,
        "presence_mode": DEFAULT_PRESENCE_MODE,
        "selected_standard_agent": "Random",
        "auto_lock_enabled": False,
        "map_lock_enabled": False,
        "queue_snipe_enabled": False,
        "queue_snipe_selected_friend": None,
        "map_agent_selection": {
            map_uuid: ""
            for map_uuid in normalized_map_uuids
        },
    }


def _coerce_map_uuids(map_uuids=None, base_path=None, existing_selection=None):
    normalized_map_uuids = list(map_uuids) if map_uuids is not None else discover_map_asset_uuids(base_path=base_path)
    if normalized_map_uuids:
        return normalized_map_uuids

    if isinstance(existing_selection, dict):
        return sorted(str(key) for key in existing_selection.keys())

    return []


def _normalize_map_agent_selection(selection_data, map_uuids):
    raw_selection = selection_data if isinstance(selection_data, dict) else {}
    normalized = {}
    for map_uuid in map_uuids:
        normalized[map_uuid] = str(raw_selection.get(map_uuid, "") or "")
    return normalized


def _normalize_selected_theme(theme_name):
    normalized_theme = str(theme_name or DEFAULT_THEME_NAME).strip().lower()
    if normalized_theme in VALID_THEME_NAMES:
        return normalized_theme
    return DEFAULT_THEME_NAME


def _normalize_queue_snipe_friend(friend_data):
    if not isinstance(friend_data, dict):
        return None

    puuid = str(friend_data.get("puuid", "") or "").strip()
    if not puuid:
        return None

    game_name = str(friend_data.get("game_name", "") or "").strip()
    game_tag = str(friend_data.get("game_tag", "") or "").strip()
    display_name = str(friend_data.get("display_name", "") or "").strip()
    if not display_name:
        if game_name and game_tag:
            display_name = f"{game_name}#{game_tag}"
        else:
            display_name = game_name or str(friend_data.get("name", "") or "").strip() or puuid

    return {
        "puuid": puuid,
        "game_name": game_name,
        "game_tag": game_tag,
        "display_name": display_name,
        "pid": str(friend_data.get("pid", "") or "").strip(),
    }


def normalize_app_state(state_data, map_uuids=None, base_path=None):
    raw_state = state_data if isinstance(state_data, dict) else {}
    normalized_map_uuids = _coerce_map_uuids(
        map_uuids=map_uuids,
        base_path=base_path,
        existing_selection=raw_state.get("map_agent_selection"),
    )
    normalized_queue_snipe_friend = _normalize_queue_snipe_friend(raw_state.get("queue_snipe_selected_friend"))
    normalized_state = {
        "version": APP_STATE_VERSION,
        "selected_theme": _normalize_selected_theme(raw_state.get("selected_theme")),
        "presence_mode": normalize_presence_mode(raw_state.get("presence_mode")),
        "selected_standard_agent": str(raw_state.get("selected_standard_agent", "Random") or "Random"),
        "auto_lock_enabled": bool(raw_state.get("auto_lock_enabled", False)),
        "map_lock_enabled": bool(raw_state.get("map_lock_enabled", False)),
        "queue_snipe_enabled": bool(raw_state.get("queue_snipe_enabled", False)),
        "queue_snipe_selected_friend": normalized_queue_snipe_friend,
        "map_agent_selection": _normalize_map_agent_selection(
            raw_state.get("map_agent_selection"),
            normalized_map_uuids,
        ),
    }

    if not normalized_state["auto_lock_enabled"]:
        normalized_state["map_lock_enabled"] = False
    if normalized_state["queue_snipe_selected_friend"] is None:
        normalized_state["queue_snipe_enabled"] = False

    return normalized_state


def _load_json_file(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _load_legacy_map_selection(map_uuids=None, base_path=None):
    legacy_path = get_legacy_map_selection_path(base_path=base_path)
    if not os.path.exists(legacy_path):
        return {}

    try:
        legacy_data = _load_json_file(legacy_path)
    except (OSError, json.JSONDecodeError):
        return {}

    normalized_map_uuids = _coerce_map_uuids(
        map_uuids=map_uuids,
        base_path=base_path,
        existing_selection=legacy_data,
    )
    return _normalize_map_agent_selection(legacy_data, normalized_map_uuids)


def save_app_state(state_data, map_uuids=None, base_path=None):
    state_path = get_app_state_path(base_path=base_path)
    os.makedirs(os.path.dirname(state_path), exist_ok=True)

    normalized_state = normalize_app_state(state_data, map_uuids=map_uuids, base_path=base_path)

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=os.path.dirname(state_path),
        delete=False,
    ) as temp_file:
        json.dump(normalized_state, temp_file, indent=2)
        temp_path = temp_file.name

    os.replace(temp_path, state_path)
    return normalized_state


def load_app_state(map_uuids=None, base_path=None):
    state_path = get_app_state_path(base_path=base_path)
    raw_state = None
    write_back = False

    if os.path.exists(state_path):
        try:
            raw_state = _load_json_file(state_path)
        except (OSError, json.JSONDecodeError):
            raw_state = default_app_state(map_uuids=map_uuids, base_path=base_path)
            write_back = True
    else:
        raw_state = default_app_state(map_uuids=map_uuids, base_path=base_path)
        raw_state["map_agent_selection"] = _load_legacy_map_selection(
            map_uuids=map_uuids,
            base_path=base_path,
        )
        write_back = True

    normalized_state = normalize_app_state(raw_state, map_uuids=map_uuids, base_path=base_path)
    if normalized_state != raw_state:
        write_back = True

    if write_back:
        normalized_state = save_app_state(normalized_state, map_uuids=map_uuids, base_path=base_path)

    return normalized_state


def load_map_agent_selection(map_uuids=None, base_path=None):
    state_data = load_app_state(map_uuids=map_uuids, base_path=base_path)
    return dict(state_data.get("map_agent_selection", {}))
