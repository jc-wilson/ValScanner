import aiohttp

from core.http_session import SharedSession
from core.local_api import LockfileHandler
from core.region_shard import region_shard_func


class MatchDetectionHandler:
    def __init__(self, prematch_id=None, match_id=None):
        self.current_match_id = None
        self.pre_game_match_id = None
        self.player_info = None
        self.player_info_pre = None
        self.party_id = None
        self.user_puuid = None
        self.region_shard = {}
        self.region = None
        self.shard = None
        self.in_match = None
        self.match_id = match_id
        self.prematch_id = prematch_id
        self.match_id_header = None
        self.is_ready = False

    async def puuid_shard_header_getter(self):
        handler = LockfileHandler()
        if not await handler.lockfile_data_function(retries=1):
            return False

        self.region_shard = region_shard_func() or {}
        self.region = self.region_shard.get("region")
        self.shard = self.region_shard.get("shard")
        if not self.region or not self.shard:
            return False

        self.user_puuid = handler.puuid
        self.match_id_header = {
            "X-Riot-ClientPlatform": "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9",
            "X-Riot-ClientVersion": f"{handler.client_version}",
            "X-Riot-Entitlements-JWT": f"{handler.entitlement_token}",
            "Authorization": f"Bearer {handler.access_token}",
        }
        self.is_ready = True
        return True

    async def detect_match_handler(self):
        if not await self.puuid_shard_header_getter():
            return False

        if self.match_id is None and self.prematch_id is None:
            session = SharedSession.get()
            async with session.get(
                f"https://glz-{self.region}-1.{self.shard}.a.pvp.net/core-game/v1/players/{self.user_puuid}",
                headers=self.match_id_header,
            ) as current_match_id_response:
                if current_match_id_response.status == 200:
                    self.current_match_id = await current_match_id_response.json(content_type=None)
                    self.match_id = self.current_match_id.get("MatchID")
                else:
                    async with session.get(
                        f"https://glz-{self.region}-1.{self.shard}.a.pvp.net/pregame/v1/players/{self.user_puuid}",
                        headers=self.match_id_header,
                    ) as pre_game_match_id_response:
                        if pre_game_match_id_response.status == 200:
                            self.pre_game_match_id = await pre_game_match_id_response.json(content_type=None)
                            self.prematch_id = self.pre_game_match_id.get("MatchID")
                        else:
                            async with session.get(
                                f"https://glz-{self.region}-1.{self.shard}.a.pvp.net/parties/v1/players/{self.user_puuid}",
                                headers=self.match_id_header,
                            ) as party_response:
                                if party_response.status == 200:
                                    self.party_id = await party_response.json(content_type=None)
        return True

    async def player_info_retrieval(self):
        if not await self.detect_match_handler():
            return False

        session = SharedSession.get()
        if self.prematch_id:
            async with session.get(
                f"https://glz-{self.region}-1.{self.shard}.a.pvp.net/pregame/v1/matches/{self.prematch_id}",
                headers=self.match_id_header,
            ) as resp:
                if resp.status == 200:
                    self.player_info_pre = await resp.json(content_type=None)
                    self.in_match = self.prematch_id
        elif self.match_id:
            async with session.get(
                f"https://glz-{self.region}-1.{self.shard}.a.pvp.net/core-game/v1/matches/{self.match_id}",
                headers=self.match_id_header,
            ) as resp:
                if resp.status == 200:
                    self.player_info = await resp.json(content_type=None)
                    self.in_match = self.match_id

        return bool(self.player_info or self.player_info_pre or self.party_id)
