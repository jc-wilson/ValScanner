import os
import sys
import re
import json
import requests
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from core.http_session import SharedSession

_SKIN_ASSET_INDEX = None
_BUDDY_ASSET_INDEX = None


def get_external_path(relative_path):
    """Always points to the folder NEXT to the .exe, or the Project Root in dev."""
    if getattr(sys, 'frozen', False):
        # If compiled, use the directory where the .exe is sitting
        base_path = os.path.dirname(sys.executable)
    else:
        # If running locally (script is inside core/ or frontend/), go up one level to Project Root
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.abspath(os.path.join(current_dir, ".."))

    return os.path.join(base_path, relative_path)


def _normalize_asset_id(asset_id):
    return str(asset_id or "").strip().lower()


def _load_metadata_json(path, url):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        payload = response.json()
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return payload


def _get_skin_asset_index():
    global _SKIN_ASSET_INDEX
    if _SKIN_ASSET_INDEX is not None:
        return _SKIN_ASSET_INDEX

    payload = _load_metadata_json(
        get_external_path("core/skin_uuids.json"),
        "https://valorant-api.com/v1/weapons/skins",
    )
    index = {}
    for skin in payload.get("data", []):
        skin_uuid = _normalize_asset_id(skin.get("uuid"))
        skin_icon = skin.get("displayIcon") or skin.get("fullRender")
        if skin_uuid and skin_icon:
            index[skin_uuid] = skin_icon

        for chroma in skin.get("chromas", []):
            chroma_uuid = _normalize_asset_id(chroma.get("uuid"))
            chroma_icon = chroma.get("displayIcon") or chroma.get("fullRender") or skin_icon
            if chroma_uuid and chroma_icon:
                index[chroma_uuid] = chroma_icon

        for level in skin.get("levels", []):
            level_uuid = _normalize_asset_id(level.get("uuid"))
            if level_uuid and skin_icon:
                index[level_uuid] = skin_icon

    _SKIN_ASSET_INDEX = index
    return _SKIN_ASSET_INDEX


def _get_buddy_asset_index():
    global _BUDDY_ASSET_INDEX
    if _BUDDY_ASSET_INDEX is not None:
        return _BUDDY_ASSET_INDEX

    payload = _load_metadata_json(
        get_external_path("core/buddy_uuids.json"),
        "https://valorant-api.com/v1/buddies",
    )
    index = {}
    for buddy in payload.get("data", []):
        buddy_icon = buddy.get("displayIcon")
        for level in buddy.get("levels", []):
            buddy_uuid = _normalize_asset_id(level.get("uuid"))
            if buddy_uuid and buddy_icon:
                index[buddy_uuid] = buddy_icon

    _BUDDY_ASSET_INDEX = index
    return _BUDDY_ASSET_INDEX


def skin_asset_path(asset_id, cache_dir=None):
    if cache_dir is None:
        cache_dir = get_external_path("assets/skins")
    return os.path.join(cache_dir, f"{_normalize_asset_id(asset_id)}.png")


def buddy_asset_path(asset_id, cache_dir=None):
    if cache_dir is None:
        cache_dir = get_external_path("assets/buddies")
    return os.path.join(cache_dir, f"{_normalize_asset_id(asset_id)}.png")


def _download_asset_file(url, path):
    try:
        data = requests.get(url, timeout=8).content
        with open(path, "wb") as handle:
            handle.write(data)
        return True
    except Exception:
        return False


def _download_asset_jobs(download_jobs, threads):
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(_download_asset_file, url, path) for url, path in download_jobs]
        for _ in as_completed(futures):
            pass


def _load_pixmap_from_file(path, width=None, height=None):
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return None
    if width is not None and height is not None:
        return pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return pixmap


def _load_local_pixmaps(cache_dir, normalize_keys=False, width=None, height=None):
    pixmaps = {}
    if not os.path.isdir(cache_dir):
        return pixmaps

    valid_extensions = {".png", ".jpg", ".jpeg", ".webp"}
    for entry in os.scandir(cache_dir):
        if not entry.is_file():
            continue

        stem, extension = os.path.splitext(entry.name)
        if extension.lower() not in valid_extensions:
            continue

        key = _normalize_asset_id(stem) if normalize_keys else stem
        if not key:
            continue

        pixmap = _load_pixmap_from_file(entry.path, width=width, height=height)
        if pixmap is not None:
            pixmaps[key] = pixmap

    return pixmaps


async def _fetch_valorant_api_data(url, label):
    try:
        session = SharedSession.get()
        async with session.get(url) as resp:
            if resp.status != 200:
                print(f"Failed to fetch {label} from Valorant API (status {resp.status})")
                return []
            payload = await resp.json(content_type=None)
            return payload.get("data", [])
    except Exception as exc:
        print(f"Failed to fetch {label} from Valorant API: {exc}")
        return []


async def _ensure_asset_files(asset_ids, index_loader, path_builder, label, threads=12):
    normalized_ids = [_normalize_asset_id(asset_id) for asset_id in asset_ids if _normalize_asset_id(asset_id)]
    if not normalized_ids:
        return {}

    os.makedirs(os.path.dirname(path_builder(normalized_ids[0])), exist_ok=True)

    file_map = {}
    missing_ids = []
    for asset_id in dict.fromkeys(normalized_ids):
        path = path_builder(asset_id)
        file_map[asset_id] = path
        if os.path.exists(path):
            continue
        missing_ids.append(asset_id)

    if not missing_ids:
        return file_map

    index = index_loader()
    download_jobs = []
    for asset_id in missing_ids:
        url = index.get(asset_id)
        if url:
            download_jobs.append((url, file_map[asset_id]))

    if download_jobs:
        print(f"Downloading {len(download_jobs)} uncached {label} assets...")
        await asyncio.to_thread(_download_asset_jobs, download_jobs, threads)

    return file_map


async def ensure_skin_asset_files(asset_ids, cache_dir=None, threads=12):
    return await _ensure_asset_files(
        asset_ids,
        _get_skin_asset_index,
        lambda asset_id: skin_asset_path(asset_id, cache_dir),
        "skin",
        threads=threads,
    )


async def ensure_buddy_asset_files(asset_ids, cache_dir=None, threads=12):
    return await _ensure_asset_files(
        asset_ids,
        _get_buddy_asset_index,
        lambda asset_id: buddy_asset_path(asset_id, cache_dir),
        "buddy",
        threads=threads,
    )


def load_skin_pixmap(asset_id, cache_dir=None):
    path = skin_asset_path(asset_id, cache_dir)
    if not os.path.exists(path):
        return None
    return _load_pixmap_from_file(path)


def load_buddy_pixmap(asset_id, cache_dir=None):
    path = buddy_asset_path(asset_id, cache_dir)
    if not os.path.exists(path):
        return None
    return _load_pixmap_from_file(path)


async def download_and_cache_agent_icons(cache_dir=None):
    if cache_dir is None:
        cache_dir = get_external_path("assets/agents")
    os.makedirs(cache_dir, exist_ok=True)

    icons = _load_local_pixmaps(cache_dir, width=134, height=134)
    agents = await _fetch_valorant_api_data("https://valorant-api.com/v1/agents", "agent list")
    if not agents:
        print(f"Loaded {len(icons)} local agent icons (cached in {cache_dir})")
        return icons

    file_map = {}
    download_jobs = []
    for agent in agents:
        if not agent.get("isPlayableCharacter", False):
            continue

        name = agent["displayName"]
        icon_url = agent.get("displayIconSmall") or agent.get("displayIcon")
        if not icon_url:
            continue

        safe_name = re.sub(r'[\\/*?:"<>|]', "_", name)
        file_path = os.path.join(cache_dir, f"{safe_name}.png")
        file_map[name] = file_path

        if name in icons:
            continue
        if os.path.exists(file_path):
            pixmap = _load_pixmap_from_file(file_path, width=134, height=134)
            if pixmap is not None:
                icons[name] = pixmap
            continue

        download_jobs.append((icon_url, file_path))

    if download_jobs:
        print(f"Downloading {len(download_jobs)} uncached agent icons...")
        await asyncio.to_thread(_download_asset_jobs, download_jobs, 12)

    for name, file_path in file_map.items():
        if name in icons or not os.path.exists(file_path):
            continue
        pixmap = _load_pixmap_from_file(file_path, width=134, height=134)
        if pixmap is not None:
            icons[name] = pixmap

    print(f"Loaded {len(icons)} agent icons (cached in {cache_dir})")
    return icons


async def download_and_cache_map_icons(cache_dir=None):
    if cache_dir is None:
        cache_dir = get_external_path("assets/maps")
    os.makedirs(cache_dir, exist_ok=True)

    icons = _load_local_pixmaps(cache_dir, normalize_keys=True)
    maps = await _fetch_valorant_api_data("https://valorant-api.com/v1/maps", "map icons")
    if not maps:
        print(f"Loaded {len(icons)} local map icons (cached in {cache_dir})")
        return icons

    excluded_maps = {
        "1f10dab3-4294-3827-fa35-c2aa00213cf3",
        "5914d1e0-40c4-cfdd-6b88-eba06347686c",
        "a38a3f9a-4042-844c-8970-a3ac2f7ce93d",
        "a264de0f-4a04-9c78-c97a-a6b192ce6e86",
        "a9009649-421f-d5d5-f80c-0cbe02c125bb",
        "ee613ee9-28b7-4beb-9666-08db13bb2244",
    }

    file_map = {}
    download_jobs = []
    for map_data in maps:
        map_uuid = _normalize_asset_id(map_data.get("uuid"))
        if map_uuid in excluded_maps:
            continue

        icon_url = map_data.get("listViewIconTall")
        if not icon_url:
            print("failed to retrieve icon url")
            continue

        safe_name = re.sub(r'[\\/*?:"<>|]', "_", map_uuid)
        file_path = os.path.join(cache_dir, f"{safe_name}.png")
        file_map[map_uuid] = file_path

        if map_uuid in icons:
            continue
        if os.path.exists(file_path):
            pixmap = _load_pixmap_from_file(file_path)
            if pixmap is not None:
                icons[map_uuid] = pixmap
            continue

        download_jobs.append((icon_url, file_path))

    if download_jobs:
        print(f"Downloading {len(download_jobs)} uncached map icons...")
        await asyncio.to_thread(_download_asset_jobs, download_jobs, 12)

    for map_uuid, file_path in file_map.items():
        if map_uuid in icons or not os.path.exists(file_path):
            continue
        pixmap = _load_pixmap_from_file(file_path)
        if pixmap is not None:
            icons[map_uuid] = pixmap

    print(f"Loaded {len(icons)} map icons (cached in {cache_dir})")
    return icons


async def download_and_cache_rank_icons(cache_dir=None):
    if cache_dir is None:
        cache_dir = get_external_path("assets/ranks")
    os.makedirs(cache_dir, exist_ok=True)

    icons = _load_local_pixmaps(cache_dir)
    rank_sets = await _fetch_valorant_api_data("https://valorant-api.com/v1/competitivetiers", "rank icons")
    if not rank_sets:
        print(f"Loaded {len(icons)} local rank icons (cached in {cache_dir})")
        return icons

    if len(rank_sets) <= 4:
        print(f"Loaded {len(icons)} rank icons (cached in {cache_dir})")
        return icons

    ranks = rank_sets[4].get("tiers", [])
    file_map = {}
    download_jobs = []
    for rank in ranks:
        name = rank["tierName"].capitalize()
        icon_url = rank.get("smallIcon") or rank.get("largeIcon")
        if not icon_url:
            print("failed to retrieve icon url")
            continue

        safe_name = re.sub(r'[\\/*?:"<>|]', "_", name)
        file_path = os.path.join(cache_dir, f"{safe_name}.png")
        file_map[name] = file_path

        if name in icons:
            continue
        if os.path.exists(file_path):
            pixmap = _load_pixmap_from_file(file_path)
            if pixmap is not None:
                icons[name] = pixmap
            continue

        download_jobs.append((icon_url, file_path))

    if download_jobs:
        print(f"Downloading {len(download_jobs)} uncached rank icons...")
        await asyncio.to_thread(_download_asset_jobs, download_jobs, 12)

    for name, file_path in file_map.items():
        if name in icons or not os.path.exists(file_path):
            continue
        pixmap = _load_pixmap_from_file(file_path)
        if pixmap is not None:
            icons[name] = pixmap

    print(f"Loaded {len(icons)} rank icons (cached in {cache_dir})")
    return icons


async def download_and_cache_buddies(cache_dir=None, threads=40):
    if cache_dir is None:
        cache_dir = get_external_path("assets/buddies")

    os.makedirs(cache_dir, exist_ok=True)
    pixmaps = _load_local_pixmaps(cache_dir, normalize_keys=True)
    buddies = await _fetch_valorant_api_data("https://valorant-api.com/v1/buddies", "buddies")
    if not buddies:
        print(f"Loaded {len(pixmaps)} total icons.")
        return pixmaps

    download_jobs = []
    file_map = {}
    for buddy in buddies:
        levels = buddy.get("levels", [])
        buddy_uuid = _normalize_asset_id(levels[0].get("uuid") if levels else "")
        base_icon = buddy.get("displayIcon")

        if buddy_uuid and base_icon:
            base_path = buddy_asset_path(buddy_uuid, cache_dir)
            file_map[buddy_uuid] = base_path
            if buddy_uuid not in pixmaps and not os.path.exists(base_path):
                download_jobs.append((base_icon, base_path))

    print(f"{len(download_jobs)} icons to download (uncached).")
    if download_jobs:
        print(f"Starting downloads using {threads} threads...")
        await asyncio.to_thread(_download_asset_jobs, download_jobs, threads)

    print("\nDownload complete. Loading pixmaps...")
    for buddy_uuid, file_path in file_map.items():
        if buddy_uuid in pixmaps or not os.path.exists(file_path):
            continue
        pixmap = _load_pixmap_from_file(file_path)
        if pixmap is not None:
            pixmaps[buddy_uuid] = pixmap

    print(f"Loaded {len(pixmaps)} total icons.")
    return pixmaps


async def download_and_cache_skins(cache_dir=None, threads=40):
    if cache_dir is None:
        cache_dir = get_external_path("assets/skins")

    os.makedirs(cache_dir, exist_ok=True)
    pixmaps = _load_local_pixmaps(cache_dir, normalize_keys=True)
    skins = await _fetch_valorant_api_data("https://valorant-api.com/v1/weapons/skins", "skins + chromas")
    if not skins:
        print(f"Loaded {len(pixmaps)} total icons.")
        return pixmaps

    download_jobs = []
    file_map = {}
    for skin in skins:
        skin_uuid = _normalize_asset_id(skin.get("uuid"))
        base_icon = skin.get("displayIcon") or skin.get("fullRender")

        if skin_uuid and base_icon:
            base_path = skin_asset_path(skin_uuid, cache_dir)
            file_map[skin_uuid] = base_path
            if skin_uuid not in pixmaps and not os.path.exists(base_path):
                download_jobs.append((base_icon, base_path))

        for chroma in skin.get("chromas", []):
            chroma_uuid = _normalize_asset_id(chroma.get("uuid"))
            icon = chroma.get("displayIcon") or chroma.get("fullRender")
            if chroma_uuid and icon:
                chroma_path = skin_asset_path(chroma_uuid, cache_dir)
                file_map[chroma_uuid] = chroma_path
                if chroma_uuid not in pixmaps and not os.path.exists(chroma_path):
                    download_jobs.append((icon, chroma_path))

    print(f"{len(download_jobs)} icons to download (uncached).")
    if download_jobs:
        print(f"Starting downloads using {threads} threads...")
        await asyncio.to_thread(_download_asset_jobs, download_jobs, threads)

    print("\nDownload complete. Loading pixmaps...")
    for skin_uuid, file_path in file_map.items():
        if skin_uuid in pixmaps or not os.path.exists(file_path):
            continue
        pixmap = _load_pixmap_from_file(file_path)
        if pixmap is not None:
            pixmaps[skin_uuid] = pixmap

    print(f"Loaded {len(pixmaps)} total icons.")
    return pixmaps
