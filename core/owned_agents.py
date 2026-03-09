import aiohttp
from core.detection import MatchDetectionHandler
from core.valorant_uuid import UUIDHandler
from core.http_session import SharedSession

class OwnedAgents:
    def __init__(self):
        self.agents = [
            "Astra", "Breach", "Brimstone", "Chamber", "Clove", "Cypher",
            "Deadlock", "Fade", "Gekko", "Harbor", "Iso", "Jett", "KAY/O",
            "Killjoy", "Neon", "Omen", "Phoenix", "Raze", "Reyna", "Sage",
            "Skye", "Sova", "Tejo", "Veto", "Viper", "Vyse", "Waylay", "Yoru",
            "Random", "Duelist", "Initiator", "Controller", "Sentinel"
        ]
        self.owned_agents = None
        self.all_agents = ["Brimstone", "Jett", "Phoenix", "Sage", "Sova"]
        self.combo = None

        self.duelists = ["Iso", "Jett", "Neon", "Phoenix", "Raze", "Reyna", "Waylay", "Yoru"]
        self.initiators = ["Breach", "Fade", "Gekko", "KAY/O", "Skye", "Sova", "Tejo"]
        self.controllers = ["Astra", "Brimstone", "Clove", "Harbor", "Omen", "Viper"]
        self.sentinels = ["Chamber", "Cypher", "Deadlock", "Killjoy", "Sage", "Veto", "Vyse"]

        self.owned_duelists = []
        self.owned_initiators = []
        self.owned_controllers = []
        self.owned_sentinels = []

    async def owned_agents_func(self):
        uuid_handler = UUIDHandler()
        uuid_handler.agent_uuid_function()

        handler = MatchDetectionHandler()
        ready = await handler.puuid_shard_header_getter()
        if (
            not ready
            or not handler.user_puuid
            or not handler.match_id_header
            or not handler.shard
            or str(handler.shard).lower() == "none"
        ):
            self.all_agents.sort()
            self.combo = self.all_agents.copy()
            self.combo.extend(["Random", "Duelist", "Initiator", "Controller", "Sentinel"])
            return False

        session = SharedSession.get()
        async with session.get(
            f"https://pd.{handler.shard}.a.pvp.net/store/v1/entitlements/{handler.user_puuid}/01bb38e1-da47-4e6a-9b3d-945fe4655707",
            headers=handler.match_id_header
        ) as response:
            self.owned_agents = await response.json(content_type=None)

        for agent in self.owned_agents["Entitlements"]:
            self.all_agents.append(uuid_handler.agent_converter(agent["ItemID"]))

        self.all_agents.sort()

        self.combo = self.all_agents.copy()
        self.combo.extend(["Random", "Duelist", "Initiator", "Controller", "Sentinel"])

        for agent in self.duelists:
            if agent in self.all_agents:
                self.owned_duelists.append(agent)

        for agent in self.initiators:
            if agent in self.all_agents:
                self.owned_initiators.append(agent)

        for agent in self.controllers:
            if agent in self.all_agents:
                self.owned_controllers.append(agent)

        for agent in self.sentinels:
            if agent in self.all_agents:
                self.owned_sentinels.append(agent)

        return True
