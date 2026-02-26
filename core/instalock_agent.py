import aiohttp

async def instalock_agent(agent_uuid, handler):
    if handler.in_match:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"https://glz-{handler.region}-1.{handler.shard}.a.pvp.net/pregame/v1/matches/{handler.in_match}/lock/{agent_uuid}",
                headers=handler.match_id_header
            )
    else:
        print("not in match")
