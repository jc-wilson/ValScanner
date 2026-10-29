import copy
from core.weapons import weapon_name, preset_to_weapon_skins
from core.http_session import SharedSession
from core.detection import MatchDetectionHandler

class PlayerLoadout:
    def __init__(self):
        self.current_loadout = None
        self.modified_loadout = None

        self.IDs = []

        self.puuid = None
        self.shard = None
        self.header = None

    async def handler_func(self):
        handler = MatchDetectionHandler()
        await handler.puuid_shard_header_getter()

        self.puuid = handler.user_puuid
        self.shard = handler.shard
        self.header = handler.match_id_header

    async def get_loadout(self):
        await self.handler_func()

        session = SharedSession.get()

        async with session.get(
            f"https://pd.{self.shard}.a.pvp.net/personalization/v2/players/{self.puuid}/playerloadout",
            headers=self.header
        ) as resp:
            if resp.status == 200:
                self.current_loadout = await resp.json()

    async def modify_loadout(self, desired_skins, owned_levels, uuid_handler):
        await self.get_loadout()

        if not self.current_loadout:
            return
        owned_levels = [level for levels in owned_levels["Skins"].values() for level in levels]
        selections = preset_to_weapon_skins(desired_skins, uuid_handler)
        self.modified_loadout = copy.deepcopy(self.current_loadout)
        self.modified_loadout.pop("Subject", None)
        self.modified_loadout.pop("Version", None)
        for gun in self.modified_loadout["Guns"]:
            selected = selections.get(weapon_name(gun.get("ID")))
            if not selected:
                continue
            skin_id, level_id, chroma_id = uuid_handler.loadout_uuid_function(selected, owned_levels)
            if skin_id and level_id and chroma_id:
                gun.update(SkinID=skin_id, SkinLevelID=level_id, ChromaID=chroma_id)

        await self.put_loadout()

    async def put_loadout(self):
        session = SharedSession.get()

        async with session.put(
            f"https://pd.{self.shard}.a.pvp.net/personalization/v2/players/{self.puuid}/playerloadout",
            json=self.modified_loadout,
            headers={**self.header, "Content-Type": "application/json"}
        ) as resp:
            if resp.status == 200:
                print("Successfully applied player's loadout")
            else:
                print(f"Error: {resp.status} | Couldn't apply player's loadout")
