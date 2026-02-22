import requests
import json

class UUIDHandler:
    def __init__(self):
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
            with open("agent_uuids.json") as a:
                self.agent_uuids = json.load(a)
        except FileNotFoundError:
            self.agent_uuid_request = requests.get("https://valorant-api.com/v1/agents").json()
            print("requested agent uuid information from valorant-api.com")

            with open("agent_uuids.json", "w", encoding="utf-8") as f:
                json.dump(self.agent_uuid_request, f, indent=2)

            with open("agent_uuids.json") as a:
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
            with open("skin_uuids.json") as a:
                self.skin_uuids = json.load(a)
        except FileNotFoundError:
            self.skin_uuid_request = requests.get("https://valorant-api.com/v1/weapons/skins").json()
            print("requested skin uuid information from valorant-api.com")

            with open("skin_uuids.json", "w", encoding="utf-8") as f:
                json.dump(self.skin_uuid_request, f, indent=2)

            with open("skin_uuids.json") as a:
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


    def season_uuid_function(self, season_uuid):
        response = requests.get(f"https://valorant-api.com/v1/seasons/{season_uuid}").json()
        result = None
        print(response)
        if response["status"] != 200:
            result = "Unranked"
        elif response["data"]["title"] == None:
            result = response["data"]["assetPath"]
            result = result[35:-10]
            result = result.replace("_", "")
            result = result.replace("Episode", "e")
            result = result.replace("Act", "a")
        else:
            result = response["data"]["title"]
            result = result.replace("EPISODE", "e")
            result = result.replace("ACT", "a")
            result = result.replace("//", "")
            result = result + " "
            for num in self.rom_to_int:
                if result.find(f" {num} ") > -1:
                    result = result.replace(num, self.rom_to_int[num])
        result = result.replace(" ", "")
        if result == ("525a5"):
            result = "v25a5"
        return result






