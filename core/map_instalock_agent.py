import asyncio
import json
import os
import random
import sys

from core.http_session import SharedSession
from core.owned_agents import OwnedAgents
from core.valorant_uuid import UUIDHandler

MAP_AGENT_SELECTION_RELATIVE_PATH = os.path.join("agent_selection", "map_agent_selection.json")
MAP_SELECTION_TOKENS = {"Random", "Duelist", "Initiator", "Controller", "Sentinel"}


def get_external_path(relative_path):
    if getattr(sys, "frozen", False):
        base_path = os.path.dirname(sys.executable)
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.abspath(os.path.join(current_dir, ".."))

    return os.path.join(base_path, relative_path)


def load_map_agent_selection():
    selection_path = get_external_path(MAP_AGENT_SELECTION_RELATIVE_PATH)
    if not os.path.exists(selection_path):
        print(f"Map-specific auto-lock: selection file missing at {selection_path}")
        return {}

    try:
        with open(selection_path, "r", encoding="utf-8") as file:
            loaded = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Map-specific auto-lock: failed to load selection file: {exc}")
        return {}

    return loaded if isinstance(loaded, dict) else {}


async def normalize_map_identifier(map_identifier):
    normalized_identifier = str(map_identifier or "").strip()
    if not normalized_identifier:
        return ""

    if len(normalized_identifier) == 36 and normalized_identifier.count("-") == 4:
        return normalized_identifier.lower()

    uuid_handler = UUIDHandler()
    await uuid_handler.map_uuid_function()
    map_payload = getattr(uuid_handler, "map_uuids", {}) or {}

    for map_data in map_payload.get("data", []):
        candidates = {
            str(map_data.get("uuid", "")).strip().lower(),
            str(map_data.get("mapUrl", "")).strip().lower(),
            str(map_data.get("assetPath", "")).strip().lower(),
        }
        if normalized_identifier.lower() in candidates:
            return str(map_data.get("uuid", "")).strip().lower()

    return normalized_identifier.lower()


async def resolve_selection_to_agent_uuid(selection_value):
    selection_value = str(selection_value or "")
    if not selection_value:
        return None

    if selection_value in MAP_SELECTION_TOKENS:
        owned_agent_handler = OwnedAgents()
        await owned_agent_handler.owned_agents_func()

        if selection_value == "Random":
            pool = owned_agent_handler.all_agents
        elif selection_value == "Duelist":
            pool = owned_agent_handler.owned_duelists
        elif selection_value == "Initiator":
            pool = owned_agent_handler.owned_initiators
        elif selection_value == "Controller":
            pool = owned_agent_handler.owned_controllers
        else:
            pool = owned_agent_handler.owned_sentinels

        if not pool:
            print(f"Map-specific auto-lock: no owned agents available for token '{selection_value}'")
            return None

        uuid_handler = UUIDHandler()
        uuid_handler.agent_uuid_function()
        return uuid_handler.agent_converter_reversed(random.choice(pool))

    if len(selection_value) == 36 and selection_value.count("-") == 4:
        return selection_value

    uuid_handler = UUIDHandler()
    uuid_handler.agent_uuid_function()
    resolved = uuid_handler.agent_converter_reversed(selection_value)
    return resolved or None


async def map_instalock_agent(map_uuid, handler, delay_seconds=6.5):
    if not map_uuid:
        print("Map-specific auto-lock: missing map identifier from pregame payload")
        return False
    if not getattr(handler, "in_match", None):
        print("Map-specific auto-lock: handler has no active pregame match id")
        return False
    if not getattr(handler, "match_id_header", None):
        print("Map-specific auto-lock: missing Riot auth headers")
        return False

    normalized_map_uuid = await normalize_map_identifier(map_uuid)
    agent_selection = load_map_agent_selection()
    selection_value = agent_selection.get(normalized_map_uuid, "")
    if not selection_value:
        print(
            f"Map-specific auto-lock: no saved selection for map '{map_uuid}' "
            f"(normalized to '{normalized_map_uuid}')"
        )
        return False

    agent_uuid = await resolve_selection_to_agent_uuid(selection_value)
    if not agent_uuid:
        print(
            f"Map-specific auto-lock: saved selection '{selection_value}' could not be resolved "
            f"for map '{normalized_map_uuid}'"
        )
        return False

    if delay_seconds and delay_seconds > 0:
        await asyncio.sleep(delay_seconds)

    session = SharedSession.get()
    response = await session.post(
        f"https://glz-{handler.region}-1.{handler.shard}.a.pvp.net/pregame/v1/matches/{handler.in_match}/lock/{agent_uuid}",
        headers=handler.match_id_header,
    )
    print(
        f"Map-specific auto-lock: attempted lock for map '{normalized_map_uuid}' with agent '{agent_uuid}', "
        f"status={getattr(response, 'status', 'unknown')}"
    )
    return 200 <= getattr(response, "status", 0) < 300
