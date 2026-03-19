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


async def _ensure_asset_files(asset_ids, index_loader, path_builder, label, threads=12):
    normalized_ids = [_normalize_asset_id(asset_id) for asset_id in asset_ids if _normalize_asset_id(asset_id)]
    if not normalized_ids:
        return {}

    index = index_loader()
    os.makedirs(os.path.dirname(path_builder(normalized_ids[0])), exist_ok=True)

    file_map = {}
    download_jobs = []
    for asset_id in dict.fromkeys(normalized_ids):
        path = path_builder(asset_id)
        file_map[asset_id] = path
        if os.path.exists(path):
            continue
        url = index.get(asset_id)
        if url:
            download_jobs.append((url, path))

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
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return None
    return pixmap


def load_buddy_pixmap(asset_id, cache_dir=None):
    path = buddy_asset_path(asset_id, cache_dir)
    if not os.path.exists(path):
        return None
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return None
    return pixmap


async def download_and_cache_agent_icons(cache_dir=None):
    if cache_dir is None:
        cache_dir = get_external_path("assets/agents")
    os.makedirs(cache_dir, exist_ok=True)

    print("Fetching agent list from Valorant API...")
    session = SharedSession.get()
    async with session.get("https://valorant-api.com/v1/agents") as resp:
        if resp.status == 200:
            agents = await resp.json(content_type=None)
            agents = agents["data"]
        else:
            print("Failed to fetch agent icons from Valorant API")

    icons = {}

    for agent in agents:
        if not agent.get("isPlayableCharacter", False):
            continue

        name = agent["displayName"]
        icon_url = agent.get("displayIconSmall") or agent.get("displayIcon")
        if not icon_url:
            continue

        safe_name = re.sub(r'[\\/*?:"<>|]', "_", name)
        file_path = os.path.join(cache_dir, f"{safe_name}.png")

        if not os.path.exists(file_path):
            print(f"⬇️ Downloading {name} icon...")
            img_data = requests.get(icon_url).content
            with open(file_path, "wb") as f:
                f.write(img_data)

        pixmap = QPixmap(file_path)

        icons[name] = pixmap.scaled(
            134, 134,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

    print(f"Loaded {len(icons)} agent icons (cached in {cache_dir})")
    return icons

async def download_and_cache_map_icons(cache_dir=None):
    if cache_dir is None:
        cache_dir = get_external_path("assets/maps")
    os.makedirs(cache_dir, exist_ok=True)

    print("Fetching map icons from Valorant API...")
    session = SharedSession.get()
    async with session.get("https://valorant-api.com/v1/maps") as resp:
        if resp.status == 200:
            maps = await resp.json(content_type=None)
            maps = maps["data"]

    icons = {}

    for map in maps:
        if map["uuid"] in ["1f10dab3-4294-3827-fa35-c2aa00213cf3", "5914d1e0-40c4-cfdd-6b88-eba06347686c", "a38a3f9a-4042-844c-8970-a3ac2f7ce93d",
                           "a264de0f-4a04-9c78-c97a-a6b192ce6e86", "a9009649-421f-d5d5-f80c-0cbe02c125bb", "ee613ee9-28b7-4beb-9666-08db13bb2244"]:
            continue
        uuid = map["uuid"]
        icon_url = map["listViewIconTall"]
        if not icon_url:
            print("failed to retrieve icon url")
            continue

        safe_name = re.sub(r'[\\/*?:"<>|]', "_", uuid)
        file_path = os.path.join(cache_dir, f"{safe_name}.png")

        # Download only if not already cached
        if not os.path.exists(file_path):
            print(f"⬇️ Downloading {uuid} icon...")
            img_data = requests.get(icon_url).content
            with open(file_path, "wb") as f:
                f.write(img_data)

        # Load QPixmap from local file
        pixmap = QPixmap(file_path)
        icons[uuid] = pixmap

    print(f"Loaded {len(icons)} rank icons (cached in {cache_dir})")
    return icons

async def download_and_cache_rank_icons(cache_dir=None):
    if cache_dir is None:
        cache_dir = get_external_path("assets/ranks")
    os.makedirs(cache_dir, exist_ok=True)

    print("Fetching rank icons from Valorant API...")
    session = SharedSession.get()
    async with session.get("https://valorant-api.com/v1/competitivetiers") as resp:
        if resp.status == 200:
            ranks = await resp.json(content_type=None)
            ranks = ranks["data"][4]["tiers"]
        else:
            print("Failed to fetch rank icons from Valorant API")

    icons = {}

    for rank in ranks:
        name = rank["tierName"].capitalize()
        icon_url = rank.get("smallIcon") or rank.get("largeIcon")
        if not icon_url:
            print("failed to retrieve icon url")
            continue

        safe_name = re.sub(r'[\\/*?:"<>|]', "_", name)
        file_path = os.path.join(cache_dir, f"{safe_name}.png")

        # Download only if not already cached
        if not os.path.exists(file_path):
            print(f"⬇️ Downloading {name} icon...")
            img_data = requests.get(icon_url).content
            with open(file_path, "wb") as f:
                f.write(img_data)

        # Load QPixmap from local file
        pixmap = QPixmap(file_path)
        icons[name] = pixmap

    print(f"Loaded {len(icons)} rank icons (cached in {cache_dir})")
    return icons

async def download_and_cache_buddies(cache_dir=None, threads=40):
    if cache_dir is None:
        cache_dir = get_external_path("assets/buddies")

    def download_file(url, path):
        try:
            data = requests.get(url, timeout=5).content
            with open(path, "wb") as f:
                f.write(data)
            return True
        except Exception:
            return False

    os.makedirs(cache_dir, exist_ok=True)

    print("Fetching buddies from Valorant API...")
    session = SharedSession.get()

    async with session.get("https://valorant-api.com/v1/buddies") as resp:
        if resp.status == 200:
            buddies = await resp.json()
            buddies = buddies["data"]
        else:
            print("Couldn't retrieve skin icons from valorant-api")

    download_jobs = []  # list of (url, path)
    file_map = {}  # uuid → local filepath

    # Build full download job list
    for buddy in buddies:

        # Base skin icon
        buddy_uuid = buddy["levels"][0]["uuid"]
        base_icon = buddy.get("displayIcon")

        if buddy_uuid and base_icon:
            base_path = os.path.join(cache_dir, f"{buddy_uuid}.png")
            file_map[buddy_uuid] = base_path
            if not os.path.exists(base_path):
                download_jobs.append((base_icon, base_path))

    print(f"{len(download_jobs)} icons to download (uncached).")
    if len(download_jobs) > 0:
        print(f"Starting downloads using {threads} threads...")

    # Multithreaded downloads
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [
            executor.submit(download_file, url, path)
            for url, path in download_jobs
        ]

        for i, fut in enumerate(as_completed(futures), 1):
            print(f"✔ {i}/{len(futures)}", end="\r")

    print("\n✅ Download complete. Loading pixmaps...")

    # Load images into QPixmap directly on the main thread.
    # Avoid yielding here because modal Qt dialogs can spin a nested event loop
    # and trigger qasync task re-entry while this task is still active.
    pixmaps = {}
    for uuid, file_path in file_map.items():
        if os.path.exists(file_path):
            pixmaps[uuid] = QPixmap(file_path)

    print(f"Loaded {len(pixmaps)} total icons.")
    return pixmaps


async def download_and_cache_skins(cache_dir=None, threads=40):
    if cache_dir is None:
        cache_dir = get_external_path("assets/skins")

    def download_file(url, path):
        try:
            data = requests.get(url, timeout=5).content
            with open(path, "wb") as f:
                f.write(data)
            return True
        except Exception:
            return False

    os.makedirs(cache_dir, exist_ok=True)

    print("Fetching skins + chromas from Valorant API...")
    session = SharedSession.get()
    async with session.get("https://valorant-api.com/v1/weapons/skins") as resp:
        if resp.status == 200:
            skins = await resp.json()
            skins = skins["data"]
        else:
            print("Couldn't retrieve skin icons from valorant-api")

    download_jobs = []  # list of (url, path)
    file_map = {}  # uuid → local filepath

    # Build full download job list
    for skin in skins:

        # Base skin icon
        skin_uuid = skin.get("uuid")
        base_icon = skin.get("displayIcon") or skin.get("fullRender")

        if skin_uuid and base_icon:
            base_path = os.path.join(cache_dir, f"{skin_uuid}.png")
            file_map[skin_uuid] = base_path
            if not os.path.exists(base_path):
                download_jobs.append((base_icon, base_path))

        # Chromas
        for chroma in skin.get("chromas", []):
            chroma_uuid = chroma.get("uuid")
            icon = chroma.get("displayIcon") or chroma.get("fullRender")
            if chroma_uuid and icon:
                chroma_path = os.path.join(cache_dir, f"{chroma_uuid}.png")
                file_map[chroma_uuid] = chroma_path
                if not os.path.exists(chroma_path):
                    download_jobs.append((icon, chroma_path))

    print(f"{len(download_jobs)} icons to download (uncached).")
    if len(download_jobs) > 0:
        print(f"Starting downloads using {threads} threads...")

    # Multithreaded downloads
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [
            executor.submit(download_file, url, path)
            for url, path in download_jobs
        ]

        for i, fut in enumerate(as_completed(futures), 1):
            print(f"✔ {i}/{len(futures)}", end="\r")

    print("\n✅ Download complete. Loading pixmaps...")

    # Load images into QPixmap directly on the main thread.
    # Avoid yielding here because modal Qt dialogs can spin a nested event loop
    # and trigger qasync task re-entry while this task is still active.
    pixmaps = {}
    for uuid, file_path in file_map.items():
        if os.path.exists(file_path):
            pixmaps[uuid] = QPixmap(file_path)

    print(f"Loaded {len(pixmaps)} total icons.")
    return pixmaps
