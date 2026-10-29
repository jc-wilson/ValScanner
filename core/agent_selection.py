"""Shared agent roster and random-pool rules for the picker and locking paths."""

ROLE_AGENTS = {
    "Duelist": ["Hush", "Iso", "Jett", "Neon", "Phoenix", "Raze", "Reyna", "Waylay", "Yoru"],
    "Initiator": ["Breach", "Fade", "Gekko", "KAY/O", "Skye", "Sova", "Tejo"],
    "Controller": ["Astra", "Brimstone", "Clove", "Harbor", "Miks", "Omen", "Viper"],
    "Sentinel": ["Chamber", "Cypher", "Deadlock", "Killjoy", "Sage", "Veto", "Vyse"],
}
AGENT_NAMES = sorted(agent for agents in ROLE_AGENTS.values() for agent in agents)
SELECTION_TOKENS = ["Random", *ROLE_AGENTS]
HUSH_UUID = "ddd5a15c-4fbe-42fa-3789-11a55ca5ee04"


def normalize_random_selections(values):
    if not isinstance(values, list):
        return []
    valid = set(AGENT_NAMES + SELECTION_TOKENS)
    return list(dict.fromkeys(value for value in values if isinstance(value, str) and value in valid))


def random_agent_pool(selections, owned_agents):
    """Union selected agents and roles, weighting each owned agent once."""
    selected = set()
    for value in normalize_random_selections(selections):
        if value == "Random":
            selected.update(AGENT_NAMES)
        elif value in ROLE_AGENTS:
            selected.update(ROLE_AGENTS[value])
        else:
            selected.add(value)
    return sorted(selected.intersection(name for name in owned_agents if isinstance(name, str)))
