import requests
import time
from core.detection import MatchDetectionHandler

def instalock_agent(agent_uuid):

    handler = MatchDetectionHandler()
    handler.detect_match_handler()

    if handler.in_match:
        lock_agent = requests.post(
            f"https://glz-{handler.region}-1.{handler.shard}.a.pvp.net/pregame/v1/matches/{handler.in_match}/lock/{agent_uuid}",
            headers=handler.match_id_header
        )
    else:
        print("not in match")

