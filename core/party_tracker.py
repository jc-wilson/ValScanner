import base64
import json
import re
from typing import Callable

UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}"
)


def _normalize_riot_id(name: str, tag: str) -> str:
    return f"{name.strip().lower()}#{tag.strip().lower()}"


def _normalize_puuid(puuid: str) -> str:
    return str(puuid).strip().lower()


def _split_riot_id(riot_id: str):
    if "#" not in riot_id:
        return riot_id.strip(), ""
    name, tag = riot_id.rsplit("#", 1)
    return name.strip(), tag.strip()


class PartyTracker:
    _instance = None

    def __init__(self):
        self._socket_buffers = {}
        self._party_by_puuid = {}
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
        player_matches = []

        for player in players:
            metadata = self._get_metadata_for_player(player)
            player_matches.append((player, metadata))
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
        for player, metadata in player_matches:
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

    def _get_metadata_for_player(self, player):
        puuid = str(player.get("puuid", "")).strip()
        if puuid:
            metadata = self._party_by_puuid.get(_normalize_puuid(puuid))
            if metadata:
                return metadata

        riot_id = str(player.get("name", "")).strip()
        normalized_riot_id = self.normalize_display_name(riot_id)
        if normalized_riot_id:
            return self._party_by_riot_id.get(normalized_riot_id)
        return None

    def _process_presence_stanza(self, stanza: str) -> bool:
        if "<presence" not in stanza or "<valorant>" not in stanza:
            return False

        identity_match = re.search(r"<id\s+name=['\"]([^'\"]+)['\"]\s+tagline=['\"]([^'\"]+)['\"]", stanza)

        payload_match = re.search(r"<p>([^<]+)</p>", stanza)
        if payload_match is None:
            return False

        payload = self._decode_presence_payload(payload_match.group(1))
        if not payload:
            return False

        party_id = payload.get("partyId") or payload.get("partyPresenceData", {}).get("partyId")
        if not party_id:
            return False

        puuid = self._extract_puuid_from_stanza(stanza, payload)
        normalized_puuid = _normalize_puuid(puuid) if puuid else None
        name = identity_match.group(1) if identity_match else None
        tag = identity_match.group(2) if identity_match else None
        normalized_riot_id = _normalize_riot_id(name, tag) if name and tag else None
        if normalized_puuid is None and normalized_riot_id is None:
            return False

        current = None
        if normalized_puuid:
            current = self._party_by_puuid.get(normalized_puuid)
        if current is None and normalized_riot_id:
            current = self._party_by_riot_id.get(normalized_riot_id)

        effective_puuid = normalized_puuid or (current.get("puuid") if current else None)
        effective_name = name or (current.get("name") if current else None)
        effective_tag = tag or (current.get("tag") if current else None)
        if effective_puuid is None and (effective_name is None or effective_tag is None):
            return False

        if current and current.get("party_id") == party_id and current.get("puuid") == effective_puuid:
            return False

        metadata = {
            "party_id": party_id,
            "puuid": effective_puuid,
            "name": effective_name,
            "tag": effective_tag,
        }
        self._store_metadata(metadata)
        return True

    def _decode_presence_payload(self, encoded_payload: str):
        try:
            payload_b64 = encoded_payload.strip()
            payload_b64 += "=" * (-len(payload_b64) % 4)
            decoded = base64.b64decode(payload_b64).decode("utf-8")
            return json.loads(decoded)
        except Exception:
            return None

    def _store_metadata(self, metadata) -> None:
        if metadata.get("puuid"):
            self._party_by_puuid[metadata["puuid"]] = dict(metadata)
        if metadata.get("name") and metadata.get("tag"):
            normalized_riot_id = _normalize_riot_id(metadata["name"], metadata["tag"])
            self._party_by_riot_id[normalized_riot_id] = dict(metadata)

    def _extract_puuid_from_stanza(self, stanza: str, payload):
        stanza_puuid = self._extract_puuid_from_attribute(stanza, "from")
        if stanza_puuid:
            return stanza_puuid
        return self._extract_puuid_from_payload(payload)

    def _extract_puuid_from_attribute(self, stanza: str, attribute_name: str):
        attribute_match = re.search(rf"{attribute_name}=['\"]([^'\"]+)['\"]", stanza, flags=re.IGNORECASE)
        if attribute_match is None:
            return None
        return self._extract_uuid_like_value(attribute_match.group(1))

    def _extract_puuid_from_payload(self, payload):
        if isinstance(payload, dict):
            for key, value in payload.items():
                normalized_key = str(key).strip().lower()
                if normalized_key in {"puuid", "subject"}:
                    candidate = self._extract_uuid_like_value(value)
                    if candidate:
                        return candidate
                candidate = self._extract_puuid_from_payload(value)
                if candidate:
                    return candidate
        elif isinstance(payload, list):
            for item in payload:
                candidate = self._extract_puuid_from_payload(item)
                if candidate:
                    return candidate
        return None

    def _extract_uuid_like_value(self, value):
        if value is None:
            return None
        match = UUID_PATTERN.search(str(value))
        if match is None:
            return None
        return _normalize_puuid(match.group(0))

    def _build_party_label(self, index: int) -> str:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if index < len(alphabet):
            suffix = alphabet[index]
        else:
            suffix = f"{(index // len(alphabet)) + 1}{alphabet[index % len(alphabet)]}"
        return f"Party {suffix}"