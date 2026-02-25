import requests
import json
from core.local_api import LockfileHandler
from core.region_shard import region_shard_func


# Match-state check
class MatchDetectionHandler:
    def __init__(self, prematch_id = None, match_id = None):
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

    def detect_match_handler(self):
        handler = LockfileHandler()
        handler.lockfile_data_function()

        self.region_shard = region_shard_func()
        self.region = self.region_shard["region"]
        self.shard = self.region_shard["shard"]

        self.user_puuid = handler.puuid

        self.match_id_header = {
            "X-Riot-ClientPlatform": "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9",
            "X-Riot-ClientVersion": f"{handler.client_version}",
            "X-Riot-Entitlements-JWT": f"{handler.entitlement_token}",
            "Authorization": f"Bearer {handler.access_token}"
        }


        if self.match_id is None and self.prematch_id is None:
            self.pre_game_match_id_response = requests.get(
                f"https://glz-{self.region}-1.{self.shard}.a.pvp.net/pregame/v1/players/{handler.puuid}",
                headers=self.match_id_header
            )

            self.current_match_id_response = requests.get(
                f"https://glz-{self.region}-1.{self.shard}.a.pvp.net/core-game/v1/players/{handler.puuid}",
                headers=self.match_id_header
            )

            if self.current_match_id_response.status_code == 200:
                self.current_match_id = self.current_match_id_response.json()
                self.match_id = self.current_match_id["MatchID"]
            elif self.pre_game_match_id_response.status_code == 200:
                self.pre_game_match_id = self.pre_game_match_id_response.json()
                self.prematch_id = self.pre_game_match_id["MatchID"]
            else:
                print("not in match")
                self.party_id = requests.get(
                    f"https://glz-{self.region}-1.{self.shard}.a.pvp.net/parties/v1/players/{handler.puuid}",
                    headers=self.match_id_header
                )

# Player info retrieval
    def player_info_retrieval(self):
        self.detect_match_handler()
        if self.prematch_id:
            self.pre_game_match_response = requests.get(
                f"https://glz-{self.region}-1.{self.shard}.a.pvp.net/pregame/v1/matches/{self.prematch_id}",
                headers=self.match_id_header
            )
            self.player_info_pre = self.pre_game_match_response.json()
            self.in_match = self.prematch_id
        elif self.match_id:
            self.current_game_match_response = requests.get(
                f"https://glz-{self.region}-1.{self.shard}.a.pvp.net/core-game/v1/matches/{self.match_id}",
                headers=self.match_id_header
            )
            self.player_info = self.current_game_match_response.json()
            self.in_match = self.match_id
