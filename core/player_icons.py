from urllib.parse import urljoin, urlparse


PLAYER_ICONS_URL = "https://ValScanner.com/player-icons.json"
PLAYER_ICON_ASSET_BASE_URL = "https://download.valscanner.com/"
PLAYER_ICON_TIMEOUT_SECONDS = 5
DEFAULT_PLAYER_ICON_TOOLTIP = "Player icon"


def normalize_player_puuid(puuid):
    return str(puuid or "").strip().lower()


def resolve_player_icon_url(icon_value, base_url=PLAYER_ICON_ASSET_BASE_URL):
    icon_text = str(icon_value or "").strip()
    if not icon_text:
        return ""

    resolved_url = urljoin(base_url, icon_text)
    parsed_url = urlparse(resolved_url)
    parsed_base_url = urlparse(base_url)

    if parsed_url.scheme != parsed_base_url.scheme:
        return ""
    if parsed_url.netloc.lower() != parsed_base_url.netloc.lower():
        return ""
    if not parsed_url.path or parsed_url.path == "/":
        return ""

    return resolved_url


def normalize_player_icon_rules(payload, base_url=PLAYER_ICON_ASSET_BASE_URL):
    if not isinstance(payload, dict):
        return {}

    normalized_rules = {}
    for raw_puuid, raw_rule in payload.items():
        puuid = normalize_player_puuid(raw_puuid)
        if not puuid or not isinstance(raw_rule, dict):
            continue

        icon_url = resolve_player_icon_url(raw_rule.get("icon"), base_url=base_url)
        if not icon_url:
            continue

        tooltip = raw_rule.get("tooltip")
        if isinstance(tooltip, str) and tooltip.strip():
            tooltip = tooltip.strip()
        else:
            tooltip = DEFAULT_PLAYER_ICON_TOOLTIP

        normalized_rules[puuid] = {
            "icon": icon_url,
            "tooltip": tooltip,
        }

    return normalized_rules
