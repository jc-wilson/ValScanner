import base64
import json
import re
from typing import Callable


def _normalize_riot_id(name: str, tag: str) -> str:
    return f"{name.strip().lower()}#{tag.strip().lower()}"


def _split_riot_id(riot_id: str):
    if "#" not in riot_id:
        return riot_id.strip(), ""
    name, tag = riot_id.rsplit("#", 1)
    return name.strip(), tag.strip()


class PartyTracker:
    _instance = None

    def __init__(self):
        self._socket_buffers = {}
        self._party_by_riot_id = {}
        self._callbacks = set()

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def subscribe(self, callback: Callable[[], None]):
        self._callbacks.add(callback)

    def unsubscribe(self, callback: Callable[[], None]):
        self._callbacks.discard(callback)

    def feed_chunk(self, socket_id: int, text: str) -> bool:
        if not text:
            return False

        buffer = self._socket_buffers.get(socket_id, "") + text
        updated = False

        while "</presence>" in buffer:
            end_index = buffer.find("</presence>") + len("</presence>")
            stanza = buffer[:end_index]
            buffer = buffer[end_index:]
            if self._process_presence_stanza(stanza):
                updated = True

        self._socket_buffers[socket_id] = buffer[-20000:]
        if updated:
            self._notify()
        return updated

    def clear_socket(self, socket_id: int):
        self._socket_buffers.pop(socket_id, None)

    def clear_party_metadata(self, frontend_data) -> bool:
        if not frontend_data:
            return False

        players = list(frontend_data.values()) if isinstance(frontend_data, dict) else list(frontend_data)
        changed = False
        for player in players:
            for key in ("party_id", "party_group_label", "party_group_index", "is_partied"):
                if player.get(key) is not None:
                    player[key] = None if key != "is_partied" else False
                    changed = True
        return changed

    def enrich_frontend_data(self, frontend_data) -> bool:
        if not frontend_data:
            return False

        players = list(frontend_data.values()) if isinstance(frontend_data, dict) else list(frontend_data)
        party_to_players = {}
        riot_id_to_player = {}

        for player in players:
            riot_id = str(player.get("name", "")).strip()
            normalized = self.normalize_display_name(riot_id)
            riot_id_to_player[normalized] = player
            metadata = self._party_by_riot_id.get(normalized)
            if metadata:
                party_to_players.setdefault(metadata["party_id"], []).append(player)

        party_labels = {}
        label_index = 0
        for party_id, members in party_to_players.items():
            if len(members) < 2:
                continue
            party_labels[party_id] = {
                "label": self._build_party_label(label_index),
                "index": label_index,
            }
            label_index += 1

        changed = False
        for normalized, player in riot_id_to_player.items():
            metadata = self._party_by_riot_id.get(normalized)
            party_id = metadata["party_id"] if metadata else None
            party_state = party_labels.get(party_id)
            label = party_state["label"] if party_state else None
            group_index = party_state["index"] if party_state else None
            is_partied = label is not None

            if player.get("party_id") != party_id:
                player["party_id"] = party_id
                changed = True
            if player.get("party_group_label") != label:
                player["party_group_label"] = label
                changed = True
            if player.get("party_group_index") != group_index:
                player["party_group_index"] = group_index
                changed = True
            if player.get("is_partied") != is_partied:
                player["is_partied"] = is_partied
                changed = True

        return changed

    def normalize_display_name(self, display_name: str) -> str:
        name, tag = _split_riot_id(display_name)
        return _normalize_riot_id(name, tag)

    def _notify(self):
        for callback in list(self._callbacks):
            try:
                callback()
            except Exception:
                continue

    def _process_presence_stanza(self, stanza: str) -> bool:
        if "<presence" not in stanza or "<valorant>" not in stanza:
            return False

        identity_match = re.search(r"<id\s+name=['\"]([^'\"]+)['\"]\s+tagline=['\"]([^'\"]+)['\"]", stanza)
        if identity_match is None:
            return False

        payload_match = re.search(r"<p>([^<]+)</p>", stanza)
        if payload_match is None:
            return False

        payload = self._decode_presence_payload(payload_match.group(1))
        if not payload:
            return False

        party_id = payload.get("partyId") or payload.get("partyPresenceData", {}).get("partyId")
        if not party_id:
            return False

        normalized = _normalize_riot_id(identity_match.group(1), identity_match.group(2))
        current = self._party_by_riot_id.get(normalized)
        if current and current.get("party_id") == party_id:
            return False

        self._party_by_riot_id[normalized] = {
            "party_id": party_id,
            "name": identity_match.group(1),
            "tag": identity_match.group(2),
        }
        return True

    def _decode_presence_payload(self, encoded_payload: str):
        try:
            payload_b64 = encoded_payload.strip()
            payload_b64 += "=" * (-len(payload_b64) % 4)
            decoded = base64.b64decode(payload_b64).decode("utf-8")
            return json.loads(decoded)
        except Exception:
            return None

    def _build_party_label(self, index: int) -> str:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if index < len(alphabet):
            suffix = alphabet[index]
        else:
            suffix = f"{(index // len(alphabet)) + 1}{alphabet[index % len(alphabet)]}"
        return f"Party {suffix}"