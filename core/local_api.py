import os
import json
import requests
import pathlib
import base64
import urllib3
import re
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Lockfile reading C:\Users\james\AppData\Local\Riot Games\Riot Client\Config

class LockfileHandler:
    def __init__(self):
        self.access_token = []
        self.entitlement_token = []
        self.puuid = []
        self.client_version = []
        self.port = None
        self.password = None

    def lockfile_data_function(self):
        # Finds Lockfile
        lockfile_loc = rf"{os.getenv("LOCALAPPDATA")}\Riot Games\Riot Client\Config\lockfile"
        if os.path.exists(Path(rf'{lockfile_loc}')):
            lockfile_path = Path(rf'{lockfile_loc}')

            # Reads Lockfile
            lockfile_read = open(lockfile_path, "r")
            lockfile_data = lockfile_read.read()
            lockfile_read.close()

            # Finds and defines port and password from lockfile
            lockfile_data_colon_loc = [i for i, x in enumerate(lockfile_data) if x == ":"]
            self.port = lockfile_data[lockfile_data_colon_loc[1] + 1:lockfile_data_colon_loc[2]]
            self.password = lockfile_data[lockfile_data_colon_loc[2] + 1:lockfile_data_colon_loc[3]]

            # Retrieves user's access and entitlement tokens
            tokens_response = requests.get(
                f"https://127.0.0.1:{self.port}/entitlements/v1/token",
                auth=("riot", self.password),
                verify=False
            )

            # Retrives user's client version
            session_response = requests.get(
                f"https://127.0.0.1:{self.port}/product-session/v1/external-sessions",
                auth=("riot", self.password),
                verify=False
            )

            entitlements = tokens_response.json()
            self.access_token = entitlements["accessToken"]
            self.entitlement_token = entitlements["token"]
            self.puuid = entitlements["subject"]

            session = session_response.json()
            self.client_version = session["host_app"]["version"]
        else:
            print("error")
