import aiohttp
from core.detection import MatchDetectionHandler
from core.valorant_uuid import UUIDHandler
from core.http_session import SharedSession
from core.agent_selection import AGENT_NAMES, SELECTION_TOKENS, ROLE_AGENTS

class OwnedAgents:
    def __init__(self):
        # Hush occupies the portrait slot previously used by Random.
        self.agents = [name for name in AGENT_NAMES if name != "Hush"] + ["Hush"] + SELECTION_TOKENS
        self.owned_agents = None
        self.all_agents = ["Brimstone", "Jett", "Phoenix", "Sage", "Sova"]
        self.combo = None

        self.duelists = ROLE_AGENTS["Duelist"]
        self.initiators = ROLE_AGENTS["Initiator"]
        self.controllers = ROLE_AGENTS["Controller"]
        self.sentinels = ROLE_AGENTS["Sentinel"]
        self.refresh_pools()

    def refresh_pools(self):
        self.all_agents = sorted({name for name in self.all_agents if isinstance(name, str) and name in AGENT_NAMES})
        self.combo = self.all_agents + SELECTION_TOKENS
        for role, names in ROLE_AGENTS.items():
            setattr(self, "owned_" + role.lower() + "s", [name for name in names if name in self.all_agents])

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
            self.refresh_pools()
            return False

        session = SharedSession.get()
        async with session.get(
            f"https://pd.{handler.shard}.a.pvp.net/store/v1/entitlements/{handler.user_puuid}/01bb38e1-da47-4e6a-9b3d-945fe4655707",
            headers=handler.match_id_header
        ) as response:
            self.owned_agents = await response.json(content_type=None)

        self.all_agents = ["Brimstone", "Jett", "Phoenix", "Sage", "Sova"]
        for agent in self.owned_agents["Entitlements"]:
            name = uuid_handler.agent_converter(agent["ItemID"])
            if isinstance(name, str) and name in AGENT_NAMES:
                self.all_agents.append(name)
        self.refresh_pools()
        return True
