import aiohttp
import asyncio
from core.valorant_uuid import UUIDHandler


class SkinHandler:
    def __init__(self):
        self.uuid_handler = UUIDHandler()
        self.uuid_handler.skin_uuid_function()
        self.converted_skins = {}
        self.converted_buddies = {}
        self.skins = None
        self.skins_pre = None
        self._lock = asyncio.Lock()

    async def get_skins(self, match_uuid, match_id_header, region, shard, session):
        async with session.get(
                f"https://glz-{region}-1.{shard}.a.pvp.net/core-game/v1/matches/{match_uuid}/loadouts",
                headers=match_id_header
        ) as resp:
            self.skins = await resp.json(content_type=None)

        try:
            if self.skins.get("httpStatus", 200) != 200:
                self.skins = False
                async with session.get(
                        f"https://glz-{region}-1.{shard}.a.pvp.net/pregame/v1/matches/{match_uuid}/loadouts",
                        headers=match_id_header
                ) as resp_pre:
                    self.skins_pre = await resp_pre.json(content_type=None)
        except (KeyError, AttributeError):
            pass

    def convert_skins(self, puuid):
        skin_uuids = []
        buddy_uuids = []
        if self.skins:
            for player in self.skins["Loadouts"]:
                if player["Loadout"]["Subject"] == puuid:
                    for weapons in player["Loadout"]["Items"]:
                        skin_uuids.append(
                            player["Loadout"]["Items"][weapons]["Sockets"]["3ad1b2b2-acdb-4524-852f-954a76ddae0a"][
                                "Item"]["ID"])
                        try:
                            buddy_uuids.append(
                                player["Loadout"]["Items"][weapons]["Sockets"]["dd3bf334-87f3-40bd-b043-682a57a8dc3a"][
                                    "Item"]["ID"])
                        except KeyError:
                            buddy_uuids.append("")

        elif self.skins_pre:
            print(self.skins_pre)
            for player in self.skins_pre["Loadouts"]:
                if player["Subject"] == puuid:
                    for weapons in player["Items"]:
                        skin_uuids.append(
                            player["Items"][weapons]["Sockets"]["3ad1b2b2-acdb-4524-852f-954a76ddae0a"]["Item"]["ID"])
                        try:
                            buddy_uuids.append(
                                player["Items"][weapons]["Sockets"]["dd3bf334-87f3-40bd-b043-682a57a8dc3a"]["Item"]["ID"])
                        except KeyError:
                            buddy_uuids.append("")

        self.converted_skins[puuid] = skin_uuids
        self.converted_buddies[puuid] = buddy_uuids

    async def assign_skins(self, puuid, match_uuid, match_id_header, region, shard, session):
        async with self._lock:
            if not self.skins and not getattr(self, "skins_pre", None):
                await self.get_skins(match_uuid, match_id_header, region, shard, session)

        self.convert_skins(puuid)

        # Helper to safely get index or return default skin UUID if missing
        def get_skin(index):
            try:
                return self.converted_skins[puuid][index]
            except (IndexError, KeyError):
                return None

        def get_buddy(index):
            try:
                return self.converted_buddies[puuid][index]
            except (IndexError, KeyError):
                return None

        return {
            "Classic": [get_skin(1), get_buddy(1)],
            "Bandit": [get_skin(3), get_buddy(3)],
            "Shorty": [get_skin(4), get_buddy(4)],
            "Frenzy": [get_skin(5), get_buddy(5)],
            "Ghost": [get_skin(0), get_buddy(0)],
            "Sheriff": [get_skin(16), get_buddy(16)],

            "Stinger": [get_skin(19), get_buddy(19)],
            "Spectre": [get_skin(6), get_buddy(6)],

            "Bucky": [get_skin(11), get_buddy(11)],
            "Judge": [get_skin(17), get_buddy(17)],

            "Bulldog": [get_skin(14), get_buddy(14)],
            "Guardian": [get_skin(7), get_buddy(7)],
            "Phantom": [get_skin(18), get_buddy(18)],
            "Vandal": [get_skin(12), get_buddy(12)],

            "Marshal": [get_skin(15), get_buddy(15)],
            "Outlaw": [get_skin(9), get_buddy(9)],
            "Operator": [get_skin(13), get_buddy(13)],

            "Ares": [get_skin(8), get_buddy(8)],
            "Odin": [get_skin(10), get_buddy(10)],

            "Knife": [get_skin(2), get_buddy(2)]
        }