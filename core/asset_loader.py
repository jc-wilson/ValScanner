import os
import sys
import re
import requests
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtGui import QPixmap

import os
import sys


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

def download_and_cache_agent_icons(cache_dir=None):
    if cache_dir is None:
        cache_dir = get_external_path("assets/agents")
    os.makedirs(cache_dir, exist_ok=True)

    print("🖼️ Fetching agent list from Valorant API...")
    response = requests.get("https://valorant-api.com/v1/agents")
    response.raise_for_status()
    agents = response.json()["data"]

    icons = {}

    for agent in agents:
        if not agent.get("isPlayableCharacter", False):
            continue

        name = agent["displayName"]
        icon_url = agent.get("displayIconSmall") or agent.get("displayIcon")
        if not icon_url:
            continue

        # 🔧 sanitize filename (replace /, \, :, ?, etc.)
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

    print(f"✅ Loaded {len(icons)} agent icons (cached in {cache_dir})")
    return icons

def download_and_cache_rank_icons(cache_dir=None):
    if cache_dir is None:
        cache_dir = get_external_path("assets/ranks")
    os.makedirs(cache_dir, exist_ok=True)

    print("🖼️ Fetching rank icons from Valorant API...")
    response = requests.get("https://valorant-api.com/v1/competitivetiers")
    response.raise_for_status()
    ranks = response.json()["data"][4]["tiers"]

    icons = {}

    for rank in ranks:
        name = rank["tierName"].capitalize()
        icon_url = rank.get("smallIcon") or rank.get("largeIcon")
        if not icon_url:
            print("failed to retrieve icon url")
            continue

        # 🔧 sanitise filename (replace /, \, :, ?, etc.)
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

    print(f"✅ Loaded {len(icons)} rank icons (cached in {cache_dir})")
    return icons

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

    print("🖼️ Fetching skins + chromas from Valorant API...")
    response = requests.get("https://valorant-api.com/v1/weapons/skins")
    response.raise_for_status()
    skins = response.json()["data"]

    download_jobs = []   # list of (url, path)
    file_map = {}        # uuid → local filepath

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

    print(f"📦 {len(download_jobs)} icons to download (uncached).")
    print(f"🚀 Starting downloads using {threads} threads...")

    # Multithreaded downloads
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [
            executor.submit(download_file, url, path)
            for url, path in download_jobs
        ]

        for i, fut in enumerate(as_completed(futures), 1):
            print(f"✔ {i}/{len(futures)}", end="\r")

    print("\n✅ Download complete. Loading pixmaps...")

    async def load_pixmap(path):
        return await asyncio.to_thread(QPixmap, path)

    # Load images into QPixmap
    pixmaps = {}
    for uuid, file_path in file_map.items():
        if os.path.exists(file_path):
            pixmaps[uuid] = await load_pixmap(file_path)

    print(f"🎉 Loaded {len(pixmaps)} total icons.")
    return pixmaps