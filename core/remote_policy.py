from dataclasses import dataclass

import aiohttp

from core.http_session import SharedSession


KILLSWITCH_URL = "https://ValScanner.com/killswitch.json"
BANLIST_URL = "https://ValScanner.com/banlist.json"
DEFAULT_KILLSWITCH_REASON = "ValScanner is temporarily unavailable."
DEFAULT_BAN_REASON = "This account is not allowed to use ValScanner."
POLICY_TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class PolicyDecision:
    blocked: bool
    reason: str | None = None
    checked: bool = True


def normalize_puuid(puuid):
    if puuid is None:
        return ""
    return str(puuid).strip().lower()


def parse_killswitch_policy(data):
    if not isinstance(data, dict):
        return PolicyDecision(False)

    active = str(data.get("killswitch", "")).strip().lower() == "on"
    if not active:
        return PolicyDecision(False)

    reason = data.get("reason")
    if isinstance(reason, str) and reason.strip():
        reason = reason.strip()
    else:
        reason = DEFAULT_KILLSWITCH_REASON
    return PolicyDecision(True, reason)


def _iter_ban_entries(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def parse_banlist_policy(data, puuid):
    target_puuid = normalize_puuid(puuid)
    if not target_puuid:
        return PolicyDecision(False)

    for entry in _iter_ban_entries(data):
        if not isinstance(entry, dict):
            continue

        if normalize_puuid(entry.get("puuid")) != target_puuid:
            continue

        reason = entry.get("reason")
        if isinstance(reason, str) and reason.strip():
            reason = reason.strip()
        else:
            reason = DEFAULT_BAN_REASON
        return PolicyDecision(True, reason)

    return PolicyDecision(False)


async def fetch_json(url, session=None, timeout=POLICY_TIMEOUT_SECONDS):
    session = session or SharedSession.get()
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        return await response.json()


async def check_killswitch(session=None, url=KILLSWITCH_URL):
    try:
        data = await fetch_json(url, session=session)
    except Exception as exc:
        print(f"Remote killswitch check failed; allowing launch: {exc}")
        return PolicyDecision(False, checked=False)
    return parse_killswitch_policy(data)


async def check_banlist(puuid, session=None, url=BANLIST_URL):
    try:
        data = await fetch_json(url, session=session)
    except Exception as exc:
        print(f"Remote banlist check failed; allowing launch: {exc}")
        return PolicyDecision(False, checked=False)
    return parse_banlist_policy(data, puuid)
