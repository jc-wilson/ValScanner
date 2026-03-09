from requests import session

from core.http_session import SharedSession
from core.detection import MatchDetectionHandler
from core.valorant_uuid import UUIDHandler
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
            self.owned_items["Skins"][uuid_handler.uuid_to_weapon(skin)].append(skin)

        for skin in self.owned_skins_variants_uuids:
            self.owned_items["Variants"][uuid_handler.uuid_to_weapon(skin)].append(skin)

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

        uuid_handler = UUIDHandler()
        uuid_handler.skin_uuid_function()
        await uuid_handler.buddy_uuid_function()

        for skin in self.current_loadout_json["Guns"]:
            self.current_loadout_skins.append(skin["ChromaID"])
            try:
                self.current_loadout_buddies.append(skin["CharmLevelID"])
            except KeyError:
                self.current_loadout_buddies.append(None)

        def get_skin(index):
            try:
                return self.current_loadout_skins[index]
            except (IndexError, KeyError):
                return None

        def get_buddy(index):
            try:
                return self.current_loadout_buddies[index]
            except (IndexError, KeyError):
                return None

        return {
            "Skins": {
                "Classic": get_skin(8),
                "Bandit": get_skin(19),
                "Shorty": get_skin(11),
                "Frenzy": get_skin(7),
                "Ghost": get_skin(9),
                "Sheriff": get_skin(10),

                "Stinger": get_skin(16),
                "Spectre": get_skin(15),

                "Bucky": get_skin(6),
                "Judge": get_skin(5),

                "Bulldog": get_skin(3),
                "Guardian": get_skin(13),
                "Phantom": get_skin(4),
                "Vandal": get_skin(2),

                "Marshal": get_skin(14),
                "Outlaw": get_skin(18),
                "Operator": get_skin(12),

                "Ares": get_skin(1),
                "Odin": get_skin(0),

                "Knife": get_skin(17)
            },
            "Buddies": {
                "Classic": get_buddy(8),
                "Bandit": get_buddy(19),
                "Shorty": get_buddy(11),
                "Frenzy": get_buddy(7),
                "Ghost": get_buddy(9),
                "Sheriff": get_buddy(10),

                "Stinger": get_buddy(16),
                "Spectre": get_buddy(15),

                "Bucky": get_buddy(6),
                "Judge": get_buddy(5),

                "Bulldog": get_buddy(3),
                "Guardian": get_buddy(13),
                "Phantom": get_buddy(4),
                "Vandal": get_buddy(2),

                "Marshal": get_buddy(14),
                "Outlaw": get_buddy(18),
                "Operator": get_buddy(12),

                "Ares": get_buddy(1),
                "Odin": get_buddy(0),

                "Knife": get_skin(17)
            }
        }
