from core.detection import MatchDetectionHandler
from core.local_api import LockfileHandler
from core.valorant_uuid import UUIDHandler
from core.skins import SkinHandler
from concurrent.futures import ThreadPoolExecutor
import requests
import sys
import os
import math
import time
import asyncio
import json
import aiohttp


class ValoRank:
    def __init__(self):
        self.used_puuids = []
        self.last_match_id = None
        self.frontend_data = {}  # Dictionary of stats for each player
        self.cmp = []  # Current Match PUUIDs
        self.ca = {}  # Current Agent
        self.zero_check = {}  # Total amount of competitive matches a player has that can be loaded
        self.mmr = {}
        self.match_stats = {}
        self.pip = {}  # Duplicate of player_info_pre so that it doesn't get lost when you load into a match
        self.handler = None
        self.start = 5
        self.end = 15
        self.gs = []  # Gamemode and Server
        self.skins = {}
        self.done = 0
        self.uuid_handler = UUIDHandler()
        self.uuid_handler.agent_uuid_function()
        self.skin_handler = SkinHandler()
        self.version_data = requests.get("https://valorant-api.com/v1/version").json()
        self.gamemode_list = {
            "Swiftplay": "Swiftplay",
            "Deathmatch": "Deathmatch",
            "HURM": "Team Deathmatch",
            "Quickbomb": "Spike Rush",
            "Bomb": "Competitive",
        }
        self.ttr = {
            0: "Unranked",
            3: "Iron 1",
            4: "Iron 2",
            5: "Iron 3",
            6: "Bronze 1",
            7: "Bronze 2",
            8: "Bronze 3",
            9: "Silver 1",
            10: "Silver 2",
            11: "Silver 3",
            12: "Gold 1",
            13: "Gold 2",
            14: "Gold 3",
            15: "Platinum 1",
            16: "Platinum 2",
            17: "Platinum 3",
            18: "Diamond 1",
            19: "Diamond 2",
            20: "Diamond 3",
            21: "Ascendant 1",
            22: "Ascendant 2",
            23: "Ascendant 3",
            24: "Immortal 1",
            25: "Immortal 2",
            26: "Immortal 3",
            27: "Radiant"
        }

    # Refreshes frontend
    async def updater_func(self, on_update):
        if on_update:
            on_update(self.frontend_data)
        await asyncio.sleep(0.05)

    async def lobby_load(self):
        try:
            self.handler.in_match
        except:
            self.frontend_data = {}
            if self.handler.party_id.status_code == 200:
                self.handler.party_id = self.handler.party_id.json()
                print(self.handler.party_id["CurrentPartyID"])
                party_info = requests.get(
                    f"https://glz-eu-1.eu.a.pvp.net/parties/v1/parties/{self.handler.party_id['CurrentPartyID']}",
                    headers=self.handler.match_id_header
                ).json()
                pmi = []  # Party Members Info
                print(party_info)
                for player in party_info["Members"]:
                    pmi.append({
                        "puuid": player.get("Subject"),
                        "rank_up": player.get("CompetitiveTier"),  # Rank unpatched
                        "level": player.get("PlayerIdentity")("AccountLevel"),
                        "name": None,
                        "tag": None
                    })
                puuids = []
                for player in pmi:
                    puuids.append(player.get("puuid"))
                nt = requests.put(
                    "https://pd.eu.a.pvp.net/name-service/v2/players",
                    json=[puuids],
                    headers={**self.handler.match_id_header, "Content-Type": "application/json"}
                ).json()

                for index, player in pmi:
                    self.frontend_data[pmi[index]["puuid"]] = {
                        "name": f"{nt[index]['GameName']}#{nt[index]['TagLine']}",
                        "agent": "N/A",
                        "level": player.get("level"),
                        "matches": "N/A",
                        "wl": "N/A",
                        "acs": "N/A",
                        "kd": "N/A",
                        "hs": "N/A",
                        "rank": player.get("rank_up"),
                        "rr": "N/A",
                        "peak_rank": "N/A",
                        "peak_act": "N/A",
                        "team": "Red"
                    }
            else:
                puuid = self.handler.user_puuid
                nt = requests.put(
                    "https://pd.eu.a.pvp.net/name-service/v2/players",
                    json=[puuid],
                    headers={**self.handler.match_id_header, "Content-Type": "application/json"}
                ).json()

                self.frontend_data[puuid] = {
                    "name": f"{nt[0]['GameName']}#{nt[0]['TagLine']}",
                    "agent": "N/A",
                    "level": "N/A",
                    "matches": "N/A",
                    "wl": "N/A",
                    "acs": "N/A",
                    "kd": "N/A",
                    "hs": "N/A",
                    "rank": "N/A",
                    "rr": "N/A",
                    "peak_rank": "N/A",
                    "peak_act": "N/A",
                    "team": "Red"
                }

    # Gamemode and server detection function
    def gs_func(self):
        self.gs = []
        if self.handler.player_info_pre:
            self.gs.append(self.handler.player_info_pre["Mode"])
            self.gs.append(self.handler.player_info_pre["GamePodID"])
        elif self.handler.player_info:
            self.gs.append(self.handler.player_info["ModeID"])
            self.gs.append(self.handler.player_info["GamePodID"])

        if self.gs:
            try:
                word = [word in self.gs[0] for word in self.gamemode_list]
                for i, x in enumerate(word):
                    if x == True:
                        pos = i
                for i, x in enumerate(self.gamemode_list):
                    if i == pos:
                        self.gs[0] = self.gamemode_list[x]
            except:
                self.gs[0] = "Unknown"

            self.gs[1] = self.gs[1][29:-2].capitalize()

            if self.gs[0] == "Competitive":
                if self.handler.player_info_pre:
                    if self.handler.player_info_pre["IsRanked"] == 0:
                        self.gs[0] = "Unrated"

    async def valo_stats(self):
        self.handler = MatchDetectionHandler()
        await asyncio.to_thread(self.handler.player_info_retrieval)

        try:
            current_match_id = self.handler.in_match
        except AttributeError:
            await self.lobby_load()
            return

        if self.last_match_id != current_match_id:
            self.used_puuids = []
            self.last_match_id = current_match_id
            self.frontend_data = {}
            self.cmp = []
            self.ca = {}
            self.zero_check = {}
            self.mmr = {}
            self.match_stats = {}
            self.pip = {}
            self.start = 5
            self.end = 15
            self.gs = []
            self.gs_func()
            self.done = 0
            self.skin_handler.skins = None
            self.skin_handler.skins_pre = None

        if self.handler.player_info_pre:
            self.pip = self.handler.player_info_pre

        if self.handler.player_info:
            if not self.cmp:
                for player in self.handler.player_info["Players"]:
                    self.cmp.append(player.get("Subject"))
            elif len(self.cmp) < 10:
                for player in self.handler.player_info["Players"]:
                    try:
                        if player["TeamID"] != self.pip["AllyTeam"]["TeamID"]:
                            self.cmp.append(player.get("Subject"))
                    except:
                        pass

        elif self.pip:
            if not self.cmp:
                for player in self.pip["AllyTeam"]["Players"]:
                    self.cmp.append(player.get("Subject"))

        if self.cmp:
            if len(self.ca) < 10:
                self.ca = {}
                if self.handler.player_info:
                    for player in self.handler.player_info["Players"]:
                        self.ca[player.get("Subject")] = player.get("CharacterID")
                else:
                    for player in self.pip["AllyTeam"]["Players"]:
                        self.ca[player.get("Subject")] = player.get("CharacterID")

        self.modified_header = self.handler.match_id_header
        self.modified_header["X-Riot-ClientVersion"] = self.version_data["data"]["riotClientVersion"]

        print(self.cmp)

        async def stat_collector(puuid, session):
            if puuid in self.used_puuids:
                return
            else:
                valorant_mmr = None

                async with session.get(f"https://pd.eu.a.pvp.net/mmr/v1/players/{puuid}",
                                       headers=self.modified_header) as resp:
                    valorant_mmr = await resp.json(content_type=None)

                print("valorant_mmr:", valorant_mmr)

                if valorant_mmr["LatestCompetitiveUpdate"]:
                    peak_rank = 0
                    peak_act = None
                    for season in valorant_mmr["QueueSkills"]["competitive"]["SeasonalInfoBySeasonID"]:
                        try:
                            for tier in valorant_mmr["QueueSkills"]["competitive"]["SeasonalInfoBySeasonID"][season][
                                "WinsByTier"]:
                                if int(tier) > peak_rank:
                                    peak_rank = int(tier)
                                    peak_act = season
                        except TypeError:
                            continue

                    peak_act_final = self.uuid_handler.season_uuid_function(peak_act)
                    prefix = peak_act_final[0:2]

                    if prefix in ("e1", "e2", "e3", "e4") and peak_rank > 20:
                        self.mmr[puuid] = {
                            "current_data": {
                                "currenttierpatched": self.ttr[
                                    valorant_mmr["LatestCompetitiveUpdate"]["TierAfterUpdate"]],
                                "ranking_in_tier": valorant_mmr["LatestCompetitiveUpdate"][
                                    "RankedRatingAfterUpdate"]
                            },
                            "highest_rank": {
                                "patched_tier": self.ttr[peak_rank + 3],
                                "peak_act": peak_act_final,
                                "season": peak_act_final
                            }
                        }
                    else:
                        self.mmr[puuid] = {
                            "current_data": {
                                "currenttierpatched": self.ttr[
                                    valorant_mmr["LatestCompetitiveUpdate"]["TierAfterUpdate"]],
                                "ranking_in_tier": valorant_mmr["LatestCompetitiveUpdate"]["RankedRatingAfterUpdate"]
                            },
                            "highest_rank": {
                                "patched_tier": self.ttr[peak_rank],
                                "peak_act": peak_act_final,
                                "season": peak_act_final
                            }
                        }
                else:
                    self.mmr[puuid] = {
                        "current_data": {
                            "currenttierpatched": "Unranked",
                            "ranking_in_tier": 0
                        },
                        "highest_rank": {
                            "patched_tier": "Unranked",
                            "peak_act": "N/A",
                            "season": "N/A"
                        }
                    }

                self.mmr[puuid]["highest_rank"]["season"] = self.mmr[puuid]["highest_rank"]["season"].replace("e10",
                                                                                                              "v25")
                self.mmr[puuid]["highest_rank"]["season"] = self.mmr[puuid]["highest_rank"]["season"].replace("e11",
                                                                                                              "v26")

                self.mmr[puuid]["highest_rank"]["patched_tier"] = self.mmr[puuid]["highest_rank"][
                    "patched_tier"].replace("Unset", "Unranked")
                self.mmr[puuid]["highest_rank"]["patched_tier"] = self.mmr[puuid]["highest_rank"][
                    "patched_tier"].replace("Unrated", "Unranked")

                self.mmr[puuid]["current_data"]["currenttierpatched"] = self.mmr[puuid]["current_data"][
                    "currenttierpatched"].replace("Unset", "Unranked")
                self.mmr[puuid]["current_data"]["currenttierpatched"] = self.mmr[puuid]["current_data"][
                    "currenttierpatched"].replace("Unrated", "Unranked")

                async with session.get(
                        f"https://pd.eu.a.pvp.net/match-history/v1/history/{puuid}?startIndex={0}&endIndex={5}&queue=competitive",
                        headers=self.handler.match_id_header
                ) as resp:
                    riot_matches = await resp.json(content_type=None)

                self.zero_check[puuid] = (riot_matches["Total"])

                if riot_matches["Total"] == 0:
                    async with session.get(
                            f"https://pd.eu.a.pvp.net/match-history/v1/history/{puuid}?startIndex={0}&endIndex={1}",
                            headers=self.handler.match_id_header
                    ) as resp:
                        riot_name = await resp.json(content_type=None)

                    if riot_name["Total"] == 0:
                        async with session.put(
                                "https://pd.eu.a.pvp.net/name-service/v2/players",
                                json=[puuid],
                                headers={**self.handler.match_id_header, "Content-Type": "application/json"}
                        ) as resp:
                            nt = await resp.json(content_type=None)

                        print(
                            f"{nt[0]['GameName']}#{nt[0]['TagLine']} ({self.uuid_handler.agent_converter(self.ca[puuid])}) has not played a game in the last 30 days")

                        if self.handler.player_info:
                            for player in self.handler.player_info["Players"]:
                                if player["Subject"] == puuid:
                                    bor = player["TeamID"]
                        elif self.handler.player_info_pre:
                            bor = self.handler.player_info_pre["AllyTeam"]["TeamID"]

                        self.frontend_data[puuid] = {
                            "name": f"{nt[0]['GameName']}#{nt[0]['TagLine']}",
                            "agent": self.uuid_handler.agent_converter(self.ca[puuid]),
                            "level": "N/A",
                            "matches": 0,
                            "wl": "N/A",
                            "acs": "N/A",
                            "kd": "N/A",
                            "hs": "N/A",
                            "rank": self.mmr[puuid]["current_data"]["currenttierpatched"],
                            "rr": self.mmr[puuid]["current_data"]["ranking_in_tier"],
                            "peak_rank": self.mmr[puuid]["highest_rank"]["patched_tier"],
                            "peak_act": self.mmr[puuid]["highest_rank"]["season"].upper(),
                            "team": bor
                        }
                        self.used_puuids.append(puuid)
                        await self.assign_skins()
                        return

                    match_id_name = riot_name["History"][0]["MatchID"]

                    async with session.get(
                            f"https://pd.eu.a.pvp.net/match-details/v1/matches/{match_id_name}",
                            headers=self.handler.match_id_header
                    ) as resp:
                        match_stats_name = await resp.json(content_type=None)

                    ntl = []  # Name Tag Level
                    for player in match_stats_name["players"]:
                        if player["subject"] == puuid:
                            ntl.append({
                                "name": player.get("gameName"),
                                "tag": player.get("tagLine"),
                                "level": player.get("accountLevel"),
                            })

                    print(
                        f"{ntl[0]['name']}#{ntl[0]['tag']} ({self.uuid_handler.agent_converter(self.ca[puuid])}) has not played competitive in the last 30 days/100 matches")

                    if self.handler.player_info:
                        for player in self.handler.player_info["Players"]:
                            if player["Subject"] == puuid:
                                bor = player["TeamID"]
                    elif self.handler.player_info_pre:
                        bor = self.handler.player_info_pre["AllyTeam"]["TeamID"]

                    self.frontend_data[puuid] = {
                        "name": f"{ntl[0]['name']}#{ntl[0]['tag']}",
                        "agent": self.uuid_handler.agent_converter(self.ca[puuid]),
                        "level": ntl[0]["level"],
                        "matches": 0,
                        "wl": "N/A",
                        "acs": "N/A",
                        "kd": "N/A",
                        "hs": "N/A",
                        "rank": self.mmr[puuid]["current_data"]["currenttierpatched"],
                        "rr": self.mmr[puuid]["current_data"]["ranking_in_tier"],
                        "peak_rank": self.mmr[puuid]["highest_rank"]["patched_tier"],
                        "peak_act": self.mmr[puuid]["highest_rank"]["season"].upper(),
                        "team": bor
                    }
                    self.used_puuids.append(puuid)
                    await self.assign_skins()
                    return

                riot_match_ids = []
                for match in riot_matches["History"]:
                    riot_match_ids.append(match["MatchID"])

                match_urls = []
                for matchID in riot_match_ids:
                    match_urls.append(f"https://pd.eu.a.pvp.net/match-details/v1/matches/{matchID}")

                async def gather_matches():
                    tasks = [self.fetch(session, match_url) for match_url in match_urls]
                    self.match_stats[puuid] = await asyncio.gather(*tasks)

                await gather_matches()
                self.used_puuids.append(puuid)
                await self.calc_stats(puuid)

        async with aiohttp.ClientSession(headers=self.modified_header) as session:
            tasks = [asyncio.create_task(stat_collector(puuid, session)) for puuid in self.cmp]
            await asyncio.gather(*tasks)

        for index, puuid in enumerate(self.cmp):
            self.frontend_data[puuid]["agent"] = self.uuid_handler.agent_converter(self.ca[puuid])

    async def calc_stats(self, puuid):
        stats_list = []
        wl_list = []  # tracks wins and losses
        hs_list = []
        for match in self.match_stats[puuid]:
            for player in match["players"]:
                if player["subject"] == puuid:
                    stats_list.append({
                        "name": player.get("gameName"),
                        "tag": player.get("tagLine"),
                        "stats": player.get("stats"),
                        "level": player.get("accountLevel"),
                        "team": player.get("teamId")
                    })

        for i, match in enumerate(self.match_stats[puuid]):
            for team in match["teams"]:
                if team["teamId"] == stats_list[i]["team"]:
                    wl_list.append(team.get("won"))

        for match in self.match_stats[puuid]:
            for round in match["roundResults"]:
                for player in round["playerStats"]:
                    if player["subject"] == puuid:
                        for round2 in player["damage"]:
                            hs_list.append({
                                "legshots": round2.get("legshots"),
                                "bodyshots": round2.get("bodyshots"),
                                "headshots": round2.get("headshots")
                            })

        team = []
        wins = []
        match_count_wl = 0
        for match in wl_list:
            match_count_wl += 1
        wl = f"{math.floor(sum(wl_list) / len(wl_list) * 100)}%"

        score = 0
        rounds_played = 0
        for match in stats_list:
            score += match["stats"]["score"]
            rounds_played += match["stats"]["roundsPlayed"]
        acs = score / rounds_played

        kills = 0
        deaths = 0
        match_count_kd = 0
        for match in stats_list:
            match_count_kd += 1
            kills += match["stats"]["kills"]
            deaths += match["stats"]["deaths"]
            if deaths == 0:
                deaths += 1
        kd = kills / deaths

        legshots = 0
        bodyshots = 0
        headshots = 0
        for round in hs_list:
            legshots += round["legshots"]
            bodyshots += round["bodyshots"]
            headshots += round["headshots"]
        hs = (headshots / (legshots + bodyshots + headshots)) * 100

        if self.handler.player_info:
            for player in self.handler.player_info["Players"]:
                if player["Subject"] == puuid:
                    bor = player["TeamID"]
        elif self.handler.player_info_pre:
            bor = self.handler.player_info_pre["Teams"][0]["TeamID"]

        if self.mmr[puuid]["current_data"]["currenttierpatched"] == "Unrated":
            self.mmr[puuid]["current_data"]["currenttierpatched"] = "Unranked"
        self.frontend_data[puuid] = {
            "name": f"{stats_list[0]['name']}#{stats_list[0]['tag']}",
            "agent": self.uuid_handler.agent_converter(self.ca[puuid]),
            "level": stats_list[0]['level'],
            "matches": match_count_kd,
            "wl": str(wl),
            "acs": str(acs)[:5],
            "kd": str(kd)[:4],
            "hs": str(hs)[:4],
            "rank": self.mmr[puuid]["current_data"]["currenttierpatched"],
            "rr": self.mmr[puuid]["current_data"]["ranking_in_tier"],
            "peak_rank": self.mmr[puuid]["highest_rank"]["patched_tier"],
            "peak_act": self.mmr[puuid]["highest_rank"]["season"].upper(),
            "team": bor
        }
        await self.assign_skins()

        print(
            f"{stats_list[0]['name']}#{stats_list[0]['tag']}'s ({self.uuid_handler.agent_converter(self.ca[puuid])}) level is {stats_list[0]['level']} | W/L % in last {match_count_kd} matches: {wl} | ACS in the last {match_count_kd} matches: {str(acs)[:5]} | KD in last {match_count_kd} matches: {str(kd)[0:4]} | HS in last {match_count_kd} matches: hs is: {str(hs)[:4]}% | current rank is: {self.mmr[puuid]['current_data']['currenttierpatched']} | current rr is: {self.mmr[puuid]['current_data']['ranking_in_tier']} | highest rank was: {self.mmr[puuid]['highest_rank']['patched_tier']} | peak act was: {self.mmr[puuid]['highest_rank']['season']}")

    async def load_more_matches(self):
        for puuid in self.cmp:
            if self.zero_check[puuid] <= self.start:
                continue
            else:
                self.riot_matches_new = requests.get(
                    f"https://pd.eu.a.pvp.net/match-history/v1/history/{puuid}?startIndex={self.start}&endIndex={self.end}&queue=competitive",
                    headers=self.handler.match_id_header
                ).json()

                if self.riot_matches_new["Total"] == 0:
                    continue

                riot_match_ids_new = []
                for match in self.riot_matches_new["History"]:
                    riot_match_ids_new.append(match["MatchID"])

                match_urls_new = []
                for matchID in riot_match_ids_new:
                    match_urls_new.append(f"https://pd.eu.a.pvp.net/match-details/v1/matches/{matchID}")

                async def gather_matches():
                    async with aiohttp.ClientSession(headers=self.handler.match_id_header) as session:
                        tasks = [self.fetch(session, match_url) for match_url in match_urls_new]
                        self.match_stats[puuid].extend(await asyncio.gather(*tasks))

                await gather_matches()

                await self.calc_stats(puuid)

                print("load more matches finished")

        self.start += 10
        self.end += 10

    async def assign_skins(self, on_update=None):
        if len(self.used_puuids) == len(self.cmp):
            # Create a temporary session for this specific task
            async with aiohttp.ClientSession(headers=self.handler.match_id_header) as session:
                for puuid in self.used_puuids:
                    # We must now AWAIT the result and pass the SESSION
                    self.frontend_data[puuid]["skins"] = await self.skin_handler.assign_skins(
                        puuid,
                        self.handler.in_match,
                        self.handler.match_id_header,
                        session
                    )

    async def fetch(self, session, url, retries=3):
        for attempt in range(retries):
            async with session.get(url) as response:
                if response.status == 200:
                    try:
                        return await response.json(content_type=None)
                    except aiohttp.ContentTypeError:
                        text = await response.text()
                        print(f"⚠️ Unexpected response type at {url}:\n{text[:200]}...")
                        return None
                elif response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", "2"))
                    print(f"🚫 Rate limited (429). Retrying in {retry_after}s... ({attempt + 1}/{retries})")
                    await asyncio.sleep(retry_after)
                else:
                    print(f"❌ Error {response.status} fetching {url}")
                    return None

        print(f"❌ Failed to fetch {url} after {retries} retries.")
        return None