import asyncio
import base64
import json
import os
import time
from pathlib import Path

import aiohttp
import urllib3

from core.http_session import SharedSession

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RiotClientNotReady(Exception):
    pass


class LockfileHandler:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LockfileHandler, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.access_token = None
        self.entitlement_token = None
        self.puuid = None
        self.client_version = None
        self.port = None
        self.password = None
        self.exp_time = 0
        self._initialized = True

    def reset_state(self):
        self.access_token = None
        self.entitlement_token = None
        self.puuid = None
        self.client_version = None
        self.port = None
        self.password = None
        self.exp_time = 0

    async def lockfile_data_function(self, retries=1, retry_delay=0, raise_on_failure=False):
        last_error = None
        for attempt in range(max(retries, 1)):
            try:
                if await self._load_lockfile_data():
                    return True
            except RiotClientNotReady as exc:
                last_error = exc
                self.reset_state()
            except Exception as exc:
                last_error = exc
                self.reset_state()

            if attempt < retries - 1 and retry_delay:
                await asyncio.sleep(retry_delay)

        if raise_on_failure and last_error is not None:
            raise RiotClientNotReady(str(last_error)) from last_error
        return False

    async def _load_lockfile_data(self):
        lockfile_loc = rf"{os.getenv('LOCALAPPDATA')}\Riot Games\Riot Client\Config\lockfile"
        lockfile_path = Path(lockfile_loc)
        if not lockfile_path.exists():
            raise RiotClientNotReady("Riot lockfile not found")

        with open(lockfile_path, "r", encoding="utf-8") as lockfile_read:
            lockfile_data = lockfile_read.read().strip()

        parts = lockfile_data.split(":")
        if len(parts) < 5:
            raise RiotClientNotReady("Riot lockfile is malformed")

        self.port = parts[2]
        self.password = parts[3]

        auth = aiohttp.BasicAuth("riot", self.password)
        session = SharedSession.get()

        try:
            async with session.get(
                f"https://127.0.0.1:{self.port}/entitlements/v1/token",
                auth=auth,
                ssl=False,
            ) as tokens_response:
                if tokens_response.status != 200:
                    raise RiotClientNotReady(f"Token endpoint not ready ({tokens_response.status})")
                entitlements = await tokens_response.json()

            async with session.get(
                f"https://127.0.0.1:{self.port}/product-session/v1/external-sessions",
                auth=auth,
                ssl=False,
            ) as session_response:
                if session_response.status != 200:
                    raise RiotClientNotReady(f"Session endpoint not ready ({session_response.status})")
                session_data = await session_response.json()
        except aiohttp.ClientError as exc:
            raise RiotClientNotReady(f"Failed to reach Riot local API: {exc}") from exc

        self.access_token = entitlements.get("accessToken")
        self.entitlement_token = entitlements.get("token")
        self.puuid = entitlements.get("subject")
        self.client_version = session_data.get("host_app", {}).get("version")

        if not all([self.access_token, self.entitlement_token, self.puuid, self.client_version]):
            raise RiotClientNotReady("Riot local API returned incomplete auth data")

        payload_b64 = self.access_token.split('.')[1]
        payload_b64 += '=' * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode('utf-8'))
        self.exp_time = payload.get('exp', 0)
        return True
