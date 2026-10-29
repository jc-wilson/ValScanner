from requests import session

from core.http_session import SharedSession
from core.detection import MatchDetectionHandler
from core.valorant_uuid import UUIDHandler
from core.weapons import WEAPON_ORDER, weapon_name
import asyncio

class OwnedSkins:
    def __init__(self):
        self.owned_items = None

        self.owned_skins_json = None
        self.owned_skins_variants_json = None
        self.owned_buddies_json = None

        self.owned_skins_uuids = []
        self.owned_skins_variants_uuids = []
        self.owned_buddies_uuids = []

        self.puuid = None
        self.shard = None
        self.header = None

        self.current_loadout_json = None

        self.current_loadout_skins = []
        self.current_loadout_buddies = []

        self.owned_items = {
            "Skins": {
                "Classic": [],
                "Bandit": [],
                "Shorty": [],
                "Frenzy": [],
                "Ghost": [],
                "Sheriff": [],

                "Stinger": [],
                "Spectre": [],

                "Bucky": [],
                "Judge": [],

                "Bulldog": [],
                "Guardian": [],
                "Phantom": [],
                "Vandal": [],
                "Warden": [],

                "Marshal": [],
                "Outlaw": [],
                "Operator": [],

                "Ares": [],
                "Odin": [],

                "Knife": []
            },
            "Variants": {
                "Classic": [],
                "Bandit": [],
                "Shorty": [],
                "Frenzy": [],
                "Ghost": [],
                "Sheriff": [],

                "Stinger": [],
                "Spectre": [],

                "Bucky": [],
                "Judge": [],

                "Bulldog": [],
                "Guardian": [],
                "Phantom": [],
                "Vandal": [],
                "Warden": [],

                "Marshal": [],
                "Outlaw": [],
                "Operator": [],

                "Ares": [],
                "Odin": [],

                "Knife": []
            },
            "Buddies": []
        }

    async def handler_func(self):
        handler = MatchDetectionHandler()
        ready = await handler.puuid_shard_header_getter()
        if (
            not ready
            or not handler.user_puuid
            or not handler.match_id_header
            or not handler.shard
            or str(handler.shard).lower() == "none"
        ):
            self.puuid = None
            self.shard = None
            self.header = None
            return False

        self.puuid = handler.user_puuid
        self.shard = handler.shard
        self.header = handler.match_id_header
        return True

    async def get_owned_items(self):
        if not await self.handler_func():
            return

        session = SharedSession.get()

        async with session.get(
            f"https://pd.{self.shard}.a.pvp.net/store/v1/entitlements/{self.puuid}/e7c63390-eda7-46e0-bb7a-a6abdacd2433",
            headers=self.header
        ) as resp:
            if resp.status == 200:
                self.owned_skins_json = await resp.json()
            else:
                print(f"Response code: {resp.status} | Couldn't access user's owned skins")

        async with session.get(
            f"https://pd.{self.shard}.a.pvp.net/store/v1/entitlements/{self.puuid}/3ad1b2b2-acdb-4524-852f-954a76ddae0a",
            headers=self.header
        ) as resp:
            if resp.status == 200:
                self.owned_skins_variants_json = await resp.json()
            else:
                print(f"Response code: {resp.status} | Couldn't access user's owned skin variants")

        async with session.get(
            f"https://pd.{self.shard}.a.pvp.net/store/v1/entitlements/{self.puuid}/dd3bf334-87f3-40bd-b043-682a57a8dc3a",
            headers=self.header
        ) as resp:
            if resp.status == 200:
                self.owned_buddies_json = await resp.json()
            else:
                print(f"Response code: {resp.status} | Couldn't access user's owned buddies")

    async def sort_owned_items(self):
        uuid_handler = UUIDHandler()
        uuid_handler.skin_uuid_function()
        await uuid_handler.buddy_uuid_function()

        await self.get_owned_items()

        for skin in self.owned_skins_json["Entitlements"]:
            self.owned_skins_uuids.append(skin["ItemID"])

        for skin in self.owned_skins_variants_json["Entitlements"]:
            self.owned_skins_variants_uuids.append(skin["ItemID"])

        for buddy in self.owned_buddies_json["Entitlements"]:
            self.owned_buddies_uuids.append(buddy["ItemID"])

        for skin in self.owned_skins_uuids:
            name = uuid_handler.uuid_to_weapon(skin)
            if name:
                self.owned_items["Skins"].setdefault(name, []).append(skin)

        for skin in self.owned_skins_variants_uuids:
            name = uuid_handler.uuid_to_weapon(skin)
            if name:
                self.owned_items["Variants"].setdefault(name, []).append(skin)

        self.owned_items["Buddies"] = self.owned_buddies_uuids

        return self.owned_items

    async def get_current_loadout(self):
        if not await self.handler_func():
            return

        session = SharedSession.get()

        async with session.get(
            f"https://pd.{self.shard}.a.pvp.net/personalization/v2/players/{self.puuid}/playerloadout",
            headers=self.header
        ) as resp:
            if resp.status == 200:
                self.current_loadout_json = await resp.json()

    async def sort_current_loadout(self):
        await self.get_current_loadout()

        skins = {name: None for name in WEAPON_ORDER}
        buddies = {name: None for name in WEAPON_ORDER}
        for gun in (self.current_loadout_json or {}).get("Guns", []):
            name = weapon_name(gun.get("ID"))
            if name:
                skins[name] = gun.get("ChromaID") or gun.get("SkinID")
                buddies[name] = gun.get("CharmLevelID")
        return {"Skins": skins, "Buddies": buddies}
