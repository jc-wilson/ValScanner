import os
import sys
import requests
import json
from core.http_session import SharedSession


def get_external_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.abspath(os.path.join(current_dir, ".."))

    return os.path.join(base_path, relative_path)


class UUIDHandler:
    def __init__(self):
        self.agent_uuids_path = get_external_path("core/agent_uuids.json")
        self.skin_uuids_path = get_external_path("core/skin_uuids.json")
        self.season_uuids_path = get_external_path("core/season_uuids.json")
        self.buddy_uuids_path = get_external_path("core/buddy_uuids.json")

        os.makedirs(os.path.dirname(self.agent_uuids_path), exist_ok=True)

        self.agent_uuid_request = None
        self.rom_to_int = {
            "I": "1",
            "II": "2",
            "III": "3",
            "IV": "4",
            "V": "5",
            "VI": "6"
        }

    def agent_uuid_function(self):
        try:
            with open(self.agent_uuids_path) as a:
                self.agent_uuids = json.load(a)
        except FileNotFoundError:
            self.agent_uuid_request = requests.get("https://valorant-api.com/v1/agents").json()
            print("requested agent uuid information from valorant-api.com")

            with open(self.agent_uuids_path, "w", encoding="utf-8") as f:
                json.dump(self.agent_uuid_request, f, indent=2)

            with open(self.agent_uuids_path) as a:
                self.agent_uuids = json.load(a)

    def agent_converter(self, uuid):
        result = []
        for agent in self.agent_uuids["data"]:
            if agent["uuid"] == uuid.lower():
                result = agent["displayName"]
        return result

    def agent_converter_reversed(self, agent_name):
        result = []
        for agent in self.agent_uuids["data"]:
            if agent["displayName"].lower() == agent_name.lower():
                result = agent["uuid"]
        return result

    def skin_uuid_function(self):
        try:
            with open(self.skin_uuids_path) as a:
                self.skin_uuids = json.load(a)
        except FileNotFoundError:
            self.skin_uuid_request = requests.get("https://valorant-api.com/v1/weapons/skins").json()
            print("requested skin uuid information from valorant-api.com")

            with open(self.skin_uuids_path, "w", encoding="utf-8") as f:
                json.dump(self.skin_uuid_request, f, indent=2)

            with open(self.skin_uuids_path) as a:
                self.skin_uuids = json.load(a)

    def skin_converter(self, skin_uuid):
        result = None
        for skin in self.skin_uuids["data"]:
            if skin["uuid"] == skin_uuid:
                result = skin["displayName"]
                return result
            for chroma in skin["chromas"]:
                if chroma["uuid"] == skin_uuid:
                    result = chroma["displayName"]
                    return result
            for level in skin["levels"]:
                if level["uuid"] == skin_uuid:
                    result = skin["displayName"]
                    return result
        return result

    async def buddy_uuid_function(self):
        try:
            with open(self.buddy_uuids_path, "r", encoding="utf-8") as a:
                self.buddy_uuids = json.load(a)
        except FileNotFoundError:
            print("Requested buddy uuid information from valorant-api.com")
            session = SharedSession.get()
            async with session.get("https://valorant-api.com/v1/buddies") as resp:
                if resp.status == 200:
                    response = await resp.json()

            with open(self.buddy_uuids_path, "w", encoding="utf-8") as f:
                json.dump(response, f, indent=2)

            with open(self.buddy_uuids_path) as a:
                self.buddy_uuids = json.load(a)

    def buddy_converter(self, buddy_uuid):
        result = None
        for buddy in self.buddy_uuids["data"]:
            if buddy["levels"][0]["uuid"] == buddy_uuid:
                result = buddy["displayName"]
                return result
        return result

    def uuid_to_weapon(self, uuid):
        name = self.skin_converter(uuid)
        weapons = [
            "Classic", "Bandit", "Shorty", "Frenzy", "Ghost", "Sheriff",
            "Stinger", "Spectre",
            "Bucky", "Judge",
            "Bulldog", "Guardian", "Phantom", "Vandal",
            "Marshal", "Outlaw", "Operator",
            "Ares", "Odin",
            "Knife",
        ]

        for weapon in weapons:
            if weapon in name:
                return weapon
        return "Knife"

    def level_uuid_to_skin_uuid(self, uuid):
        for skin in self.skin_uuids["data"]:
            for level in skin["levels"]:
                if level["uuid"] == uuid:
                    return skin["chromas"][0]["uuid"]
        return uuid

    def variant_finder(self, uuid, uuid_list):
        variants = []
        for skin in self.skin_uuids["data"]:
            if skin["chromas"][0]["uuid"] == uuid:
                for chroma in skin["chromas"]:
                    if chroma["uuid"] in uuid_list:
                        variants.append(chroma["uuid"])
        if len(variants) >= 1:
            variants.insert(0, uuid)
        return variants

    def loadout_uuid_function(self, uuid, owned_levels):
        for skin in self.skin_uuids["data"]:
            for chroma in skin["chromas"]:
                if chroma["uuid"] == uuid:
                    if skin["levels"][-1]["uuid"] in owned_levels:
                        return [skin["uuid"], skin["levels"][-1]["uuid"], uuid]
                    elif skin["levels"][-2]["uuid"] in owned_levels:
                        return [skin["uuid"], skin["levels"][-2]["uuid"], uuid]
                    elif skin["levels"][-3]["uuid"] in owned_levels:
                        return [skin["uuid"], skin["levels"][-3]["uuid"], uuid]
                    elif skin["levels"][-4]["uuid"] in owned_levels:
                        return [skin["uuid"], skin["levels"][-3]["uuid"], uuid]
                    else:
                        return [skin["uuid"], skin["levels"][0]["uuid"], uuid]
        return ["", "", ""]

    def season_uuid_function(self):
        try:
            with open(self.season_uuids_path, "r", encoding="utf-8") as a:
                self.season_uuids = json.load(a)
        except FileNotFoundError:
            print("Requested season uuid information from valorant-api.com")
            response = requests.get("https://valorant-api.com/v1/seasons").json()

            with open(self.season_uuids_path, "w", encoding="utf-8") as f:
                json.dump(response, f, indent=2)

            self.season_uuids = response

    def season_converter(self, season_uuid):
        season_data = None
        for season in self.season_uuids.get("data", []):
            if season["uuid"] == season_uuid:
                season_data = season
                break

        if not season_data:
            return "Unranked"

        if season_data.get("title") is None:
            result = season_data.get("assetPath", "")
            if len(result) > 35:
                result = result[35:-10]
            result = result.replace("_", "")
            result = result.replace("Episode", "e")
            result = result.replace("Act", "a")
        else:
            result = season_data["title"]
            result = result.replace("EPISODE", "e")
            result = result.replace("ACT", "a")
            result = result.replace("//", "")
            result = result + " "
            for num in self.rom_to_int:
                if result.find(f" {num} ") > -1:
                    result = result.replace(num, self.rom_to_int[num])

        result = result.replace(" ", "")
        if result == "525a5":
            result = "v25a5"

        return result
