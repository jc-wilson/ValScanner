import aiohttp
import asyncio
from core.valorant_uuid import UUIDHandler
from core.weapons import WEAPON_ORDER, weapon_name


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
        skins = {}
        buddies = {}
        items = {}
        if self.skins:
            for player in self.skins.get("Loadouts", []):
                loadout = player.get("Loadout", {})
                if loadout.get("Subject") == puuid:
                    items = loadout.get("Items", {})
                    break
        elif self.skins_pre:
            for player in self.skins_pre.get("Loadouts", []):
                if player.get("Subject") == puuid:
                    items = player.get("Items", {})
                    break
        for weapon_id, item in items.items():
            name = weapon_name(weapon_id)
            if not name:
                continue
            sockets = item.get("Sockets", {})
            skins[name] = sockets.get("3ad1b2b2-acdb-4524-852f-954a76ddae0a", {}).get("Item", {}).get("ID")
            buddies[name] = sockets.get("dd3bf334-87f3-40bd-b043-682a57a8dc3a", {}).get("Item", {}).get("ID")
        self.converted_skins[puuid] = skins
        self.converted_buddies[puuid] = buddies

    async def assign_skins(self, puuid, match_uuid, match_id_header, region, shard, session):
        async with self._lock:
            if not self.skins and not getattr(self, "skins_pre", None):
                await self.get_skins(match_uuid, match_id_header, region, shard, session)

        self.convert_skins(puuid)

        return {
            name: [self.converted_skins[puuid].get(name), self.converted_buddies[puuid].get(name)]
            for name in WEAPON_ORDER
        }
