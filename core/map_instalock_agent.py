from core.http_session import SharedSession
from core.valorant_uuid import UUIDHandler
import json

async def map_instalock_agent(map_uuid, handler):
    uuid_handler = UUIDHandler()
    await uuid_handler.map_uuid_function()

    session = SharedSession.get()

    agent_selection = uuid_handler.map_uuids

    for map in agent_selection:
        if map["uuid"] == map_uuid:
            agent_uuid = map["agent_uuid"]
            await session.post(
                f"https://glz-{handler.region}-1.{handler.shard}.a.pvp.net/pregame/v1/matches/{handler.in_match}/lock/{agent_uuid}",
                headers=handler.match_id_header
            )
        else:
            print("not in match")