import json
import requests
from core.detection import MatchDetectionHandler
from core.valorant_uuid import UUIDHandler

class OwnedAgents:
    def __init__(self):
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

    def owned_agents_func(self):
        uuid_handler = UUIDHandler()
        uuid_handler.agent_uuid_function()

        handler = MatchDetectionHandler()
        handler.detect_match_handler()

        self.owned_agents = requests.get(f"https://pd.{handler.shard}.a.pvp.net/store/v1/entitlements/{handler.user_puuid}/01bb38e1-da47-4e6a-9b3d-945fe4655707",
                                        headers=handler.match_id_header).json()


        for agent in self.owned_agents["Entitlements"]:
            self.all_agents.append(uuid_handler.agent_converter(agent["ItemID"]))

        self.all_agents.sort()

        print(self.all_agents)

        self.combo = self.all_agents.copy()
        self.combo.insert(0, "Random")
        self.combo.extend(["Random Duelist",
            "Random Initiator", "Random Controller", "Random Sentinel"])

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

        print(self.all_agents)
        print(self.combo)

        print(self.owned_duelists)
        print(self.owned_initiators)
        print(self.owned_controllers)
        print(self.owned_sentinels)


if __name__ == "__main__":
    agents = OwnedAgents()
    agents.owned_agents_func()
