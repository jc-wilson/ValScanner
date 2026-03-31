PRESENCE_MODE_ONLINE = "online"
PRESENCE_MODE_OFFLINE = "offline"

VALID_PRESENCE_MODES = {
    PRESENCE_MODE_ONLINE,
    PRESENCE_MODE_OFFLINE,
}

DEFAULT_PRESENCE_MODE = PRESENCE_MODE_ONLINE


def normalize_presence_mode(mode):
    normalized_mode = str(mode or DEFAULT_PRESENCE_MODE).strip().lower()
    if normalized_mode in VALID_PRESENCE_MODES:
        return normalized_mode
    return DEFAULT_PRESENCE_MODE
