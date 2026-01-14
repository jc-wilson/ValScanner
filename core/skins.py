import requests
from core.valorant_uuid import UUIDHandler

class SkinHandler:
    def __init__(self):
        self.uuid_handler = UUIDHandler()
        self.uuid_handler.skin_uuid_function()
        self.converted_skins = {}
        self.skins = None

    def get_skins(self, match_uuid, match_id_header):
        self.skins = requests.get(
            f"https://glz-eu-1.eu.a.pvp.net/core-game/v1/matches/{match_uuid}/loadouts",
            headers=match_id_header
        ).json()

        try:
            if self.skins["httpStatus"] != 200:
                self.skins = False
                self.skins_pre = requests.get(
                    f"https://glz-eu-1.eu.a.pvp.net/pregame/v1/matches/{match_uuid}/loadouts",
                    headers=match_id_header
                ).json()
        except KeyError:
            pass

    def convert_skins(self, puuid):
        skin_uuids = []
        skins = []
        if self.skins:
            for player in self.skins["Loadouts"]:
                if player["Loadout"]["Subject"] == puuid:
                    for weapons in player["Loadout"]["Items"]:
                        skin_uuids.append(player["Loadout"]["Items"][weapons]["Sockets"]["3ad1b2b2-acdb-4524-852f-954a76ddae0a"]["Item"]["ID"])

        elif self.skins_pre:
            for player in self.skins_pre["Loadouts"]:
                if player["Subject"] == puuid:
                    for weapons in player["Items"]:
                        skin_uuids.append(player["Items"][weapons]["Sockets"]["3ad1b2b2-acdb-4524-852f-954a76ddae0a"]["Item"]["ID"])

        self.converted_skins[puuid] = skin_uuids

    def assign_skins(self, puuid, match_uuid, match_id_header):
        if not self.skins:
            self.get_skins(match_uuid, match_id_header)
        self.convert_skins(puuid)
        return {
            "Classic": self.converted_skins[puuid][1],
            "Bandit": self.converted_skins[puuid][3],
            "Shorty": self.converted_skins[puuid][4],
            "Frenzy": self.converted_skins[puuid][5],
            "Ghost": self.converted_skins[puuid][0],
            "Sheriff": self.converted_skins[puuid][16],

            "Stinger": self.converted_skins[puuid][19],
            "Spectre": self.converted_skins[puuid][6],

            "Bucky": self.converted_skins[puuid][11],
            "Judge": self.converted_skins[puuid][17],

            "Bulldog": self.converted_skins[puuid][14],
            "Guardian": self.converted_skins[puuid][7],
            "Phantom": self.converted_skins[puuid][18],
            "Vandal": self.converted_skins[puuid][12],

            "Marshal": self.converted_skins[puuid][15],
            "Outlaw": self.converted_skins[puuid][9],
            "Operator": self.converted_skins[puuid][13],

            "Ares": self.converted_skins[puuid][8],
            "Odin": self.converted_skins[puuid][10],

            "Knife": self.converted_skins[puuid][2],
        }