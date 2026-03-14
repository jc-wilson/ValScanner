from core.http_session import SharedSession
from core.valorant_uuid import UUIDHandler
import asyncio
import json

async def map_instalock_agent(map_uuid, handler):
    session = SharedSession.get()

    with open("agent_selection/map_agent_selection.json", "r", encoding="utf-8") as a:
        agent_selection = json.load(a)

    for maps in agent_selection:
        if maps == map_uuid:
            agent_uuid = maps["agent_uuid"]
            await asyncio.sleep(6)
            await session.post(
                f"https://glz-{handler.region}-1.{handler.shard}.a.pvp.net/pregame/v1/matches/{handler.in_match}/lock/{agent_uuid}",
                headers=handler.match_id_header
            )
        else:
            print("not in match")