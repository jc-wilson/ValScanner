import os
import sys
import re
import requests
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from core.http_session import SharedSession

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
        icon_url = map["listViewIcon"]
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
