import aiohttp

class dodge:
    async def dodge_func(self, handler):
        if handler.in_match:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"https://glz-{handler.region}-1.{handler.shard}.a.pvp.net/pregame/v1/matches/{handler.in_match}/quit",
                    headers=handler.match_id_header
                )