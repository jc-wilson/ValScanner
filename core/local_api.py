import os
import json
import pathlib
import base64
import urllib3
import re
import aiohttp
import time
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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

        self.access_token = []
        self.entitlement_token = []
        self.puuid = []
        self.client_version = []
        self.port = None
        self.password = None
        self.last_fetch_time = 0
        self._initialized = True

    async def lockfile_data_function(self):
        if time.time() - self.last_fetch_time < 2700 and self.access_token:
            return

        lockfile_loc = rf"{os.getenv('LOCALAPPDATA')}\Riot Games\Riot Client\Config\lockfile"
        if os.path.exists(Path(rf'{lockfile_loc}')):
            lockfile_path = Path(rf'{lockfile_loc}')

            with open(lockfile_path, "r") as lockfile_read:
                lockfile_data = lockfile_read.read()

            lockfile_data_colon_loc = [i for i, x in enumerate(lockfile_data) if x == ":"]
            self.port = lockfile_data[lockfile_data_colon_loc[1] + 1:lockfile_data_colon_loc[2]]
            self.password = lockfile_data[lockfile_data_colon_loc[2] + 1:lockfile_data_colon_loc[3]]

            auth = aiohttp.BasicAuth('riot', self.password)

            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
                async with session.get(
                        f"https://127.0.0.1:{self.port}/entitlements/v1/token",
                        auth=auth
                ) as tokens_response:
                    entitlements = await tokens_response.json()

                async with session.get(
                        f"https://127.0.0.1:{self.port}/product-session/v1/external-sessions",
                        auth=auth
                ) as session_response:
                    session_data = await session_response.json()

            self.access_token = entitlements["accessToken"]
            self.entitlement_token = entitlements["token"]
            self.puuid = entitlements["subject"]
            self.client_version = session_data["host_app"]["version"]

            self.last_fetch_time = time.time()
        else:
            print("error")