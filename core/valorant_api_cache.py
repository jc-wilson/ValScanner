import json
import os
import sys
import tempfile

import aiohttp

from core.http_session import SharedSession


VALORANT_API_JSON_MANIFEST = (
    ("agent_uuids", "core/agent_uuids.json", "https://valorant-api.com/v1/agents"),
    ("season_uuids", "core/season_uuids.json", "https://valorant-api.com/v1/seasons"),
    ("skin_uuids", "core/skin_uuids.json", "https://valorant-api.com/v1/weapons/skins"),
    ("map_uuids", "core/map_uuids.json", "https://valorant-api.com/v1/maps"),
    ("buddy_uuids", "core/buddy_uuids.json", "https://valorant-api.com/v1/buddies"),
)


def cache_path(relative_path, base_path=None):
    if base_path is None:
        if getattr(sys, "frozen", False):
            base_path = os.path.dirname(sys.executable)
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            base_path = os.path.abspath(os.path.join(current_dir, ".."))
    return os.path.join(base_path, relative_path)


def _atomic_write_json(path, payload):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=directory,
            delete=False,
        ) as temp_file:
            temp_path = temp_file.name
            json.dump(payload, temp_file, indent=2)
            temp_file.write("\n")
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


async def _refresh_manifest_entry(session, label, relative_path, url, base_path=None, timeout=10):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status != 200:
                print(f"Skipped Valorant API cache refresh for {label}: status {resp.status}")
                return False
            payload = await resp.json(content_type=None)
    except Exception as exc:
        print(f"Skipped Valorant API cache refresh for {label}: {exc}")
        return False

    try:
        _atomic_write_json(cache_path(relative_path, base_path=base_path), payload)
        return True
    except Exception as exc:
        print(f"Skipped Valorant API cache write for {label}: {exc}")
        return False


async def refresh_valorant_api_jsons(session=None, base_path=None, manifest=None):
    session = session or SharedSession.get()
    manifest = manifest or VALORANT_API_JSON_MANIFEST
    results = {}
    for label, relative_path, url in manifest:
        results[label] = await _refresh_manifest_entry(
            session,
            label,
            relative_path,
            url,
            base_path=base_path,
        )
    return results
