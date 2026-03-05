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

        print(f"Current loadout: {self.current_loadout}")

    async def modify_loadout(self, desired_skins, uuid_handler):
        await self.get_loadout()

        for skin in desired_skins:
            self.IDs.append(uuid_handler.loadout_uuid_function(skin))

        self.modified_loadout = self.current_loadout.copy()

        self.modified_loadout.pop("Subject")
        self.modified_loadout.pop("Version")

        for index, gun in enumerate(self.modified_loadout["Guns"]):
            gun["SkinID"] = self.IDs[index][0]
            gun["SkinLevelID"] = self.IDs[index][1]
            gun["ChromaID"] = self.IDs[index][2]

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
