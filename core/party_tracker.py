import base64
import json
import re
from typing import Any, Callable


QUEUEING_PRESENCE_STATES = {
    "MATCHMAKING",
    "STARTING_MATCHMAKING",
    "MATCHMADE_GAME_STARTING",
}


def _normalize_riot_id(name: str, tag: str) -> str:
    return f"{name.strip().lower()}#{tag.strip().lower()}"


def _split_riot_id(riot_id: str):
    if "#" not in riot_id:
        return riot_id.strip(), ""
    name, tag = riot_id.rsplit("#", 1)
    return name.strip(), tag.strip()


def _decode_base64_json(encoded_value: str):
    if not encoded_value:
        return None

    try:
        payload_b64 = encoded_value.strip()
        payload_b64 += "=" * (-len(payload_b64) % 4)
        decoded = base64.b64decode(payload_b64).decode("utf-8")
        return json.loads(decoded)
    except Exception:
        return None


def _decode_jwt_payload(token: str):
    if not token or token.count(".") != 2:
        return None

    try:
        _, payload_b64, _ = token.split(".", 2)
        payload_b64 += "=" * (-len(payload_b64) % 4)
        decoded = base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8")
        return json.loads(decoded)
    except Exception:
        return None


class PartyTracker:
    _instance = None

    def __init__(self):
        self._socket_buffers = {}
        self._party_by_riot_id = {}
        self._presence_by_riot_id = {}
        self._presence_by_puuid = {}
        self._known_friends_by_puuid = {}
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

        while True:
            presence_end = buffer.find("</presence>")
            iq_end = buffer.find("</iq>")
            candidates = []
            if presence_end != -1:
                candidates.append(("presence", presence_end + len("</presence>")))
            if iq_end != -1:
                candidates.append(("iq", iq_end + len("</iq>")))
            if not candidates:
                break

            stanza_type, end_index = min(candidates, key=lambda item: item[1])
            stanza = buffer[:end_index]
            buffer = buffer[end_index:]
            if stanza_type == "presence" and self._process_presence_stanza(stanza):
                updated = True
            if stanza_type == "iq" and self._process_roster_stanza(stanza):
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
        player_metadata = {}
        changed = False

        for player in players:
            puuid = str(player.get("puuid", "") or "").strip()
            metadata = self._get_player_metadata_by_puuid(puuid)
            player_metadata[id(player)] = metadata

            if metadata and not player.get("xmpp_name_resolved"):
                game_name = str(metadata.get("game_name", "") or "").strip()
                game_tag = str(metadata.get("game_tag", "") or "").strip()
                if game_name and game_tag:
                    display_name = f"{game_name}#{game_tag}"
                    if player.get("name") != display_name:
                        player["name"] = display_name
                        changed = True
                    if player.get("game_name") != game_name:
                        player["game_name"] = game_name
                        changed = True
                    if player.get("tag") != game_tag:
                        player["tag"] = game_tag
                        changed = True
                    if player.get("name_source") != "xmpp":
                        player["name_source"] = "xmpp"
                        changed = True
                    if player.get("xmpp_name_resolved") is not True:
                        player["xmpp_name_resolved"] = True
                        changed = True

            party_id = metadata.get("party_id") if metadata else None
            if party_id:
                party_to_players.setdefault(party_id, []).append(player)

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

        for player in players:
            metadata = player_metadata.get(id(player))
            party_id = metadata.get("party_id") if metadata else None
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

    def _get_player_metadata_by_puuid(self, puuid: str):
        puuid = str(puuid or "").strip()
        if not puuid:
            return None

        merged = {}
        known_friend = self._known_friends_by_puuid.get(puuid)
        if isinstance(known_friend, dict):
            merged.update(known_friend)

        presence = self._presence_by_puuid.get(puuid)
        if isinstance(presence, dict):
            for key, value in presence.items():
                if value not in (None, ""):
                    merged[key] = value
            for key in ("game_name", "game_tag", "display_name", "normalized_riot_id"):
                value = known_friend.get(key) if isinstance(known_friend, dict) else None
                if value not in (None, ""):
                    merged[key] = value

        return merged or None

    def normalize_display_name(self, display_name: str) -> str:
        name, tag = _split_riot_id(display_name)
        return _normalize_riot_id(name, tag)

    def get_presence(self, puuid=None, riot_id=None):
        if puuid:
            return self._presence_by_puuid.get(str(puuid).strip())
        if riot_id:
            return self._presence_by_riot_id.get(self.normalize_display_name(riot_id))
        return None

    def get_known_friends(self):
        merged = {}

        for friend in self._known_friends_by_puuid.values():
            if not isinstance(friend, dict):
                continue
            puuid = str(friend.get("puuid", "") or "").strip()
            if not puuid:
                continue
            merged[puuid] = {
                "puuid": puuid,
                "game_name": str(friend.get("game_name", "") or "").strip(),
                "game_tag": str(friend.get("game_tag", "") or "").strip(),
                "display_name": str(friend.get("display_name", "") or "").strip(),
                "pid": str(friend.get("pid", "") or "").strip(),
            }

        for presence in self._presence_by_riot_id.values():
            if not isinstance(presence, dict):
                continue

            puuid = str(presence.get("puuid", "") or "").strip()
            display_name = str(presence.get("display_name", "") or "").strip()
            if not puuid or not display_name:
                continue

            merged[puuid] = {
                "puuid": puuid,
                "game_name": str(presence.get("game_name", "") or "").strip(),
                "game_tag": str(presence.get("game_tag", "") or "").strip(),
                "display_name": display_name,
                "pid": str(presence.get("pid", "") or "").strip(),
            }

        friends = [friend for friend in merged.values() if friend.get("display_name")]
        friends.sort(key=lambda item: (item["display_name"].lower(), item["puuid"].lower()))
        return friends

    def seed_presences(self, presence_entries) -> bool:
        if isinstance(presence_entries, dict):
            iterable = presence_entries.values()
        else:
            iterable = presence_entries or []

        updated = False
        for entry in iterable:
            normalized_presence = self._normalize_presence_entry(entry)
            if normalized_presence and self._store_presence(normalized_presence):
                updated = True

        if updated:
            self._notify()
        return updated

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
        payload_match = re.search(r"<p>([^<]+)</p>", stanza)
        from_match = re.search(r"<presence[^>]+from=['\"]([^'\"]+)['\"]", stanza)
        payload = _decode_base64_json(payload_match.group(1)) if payload_match is not None else None

        puuid = ""
        pid = ""
        party_room_id = ""
        if from_match is not None:
            from_value = from_match.group(1)
            if "@" in from_value:
                puuid = from_value.split("@", 1)[0].strip()
                if "ares-parties" in from_value:
                    party_room_id = puuid
                    puuid = ""
            if "/" in from_value:
                pid = from_value.rsplit("/", 1)[-1].strip()

        muc_updated = self._process_presence_roster_items(stanza, payload, party_room_id=party_room_id, pid=pid)
        if not payload:
            return muc_updated

        game_name = ""
        game_tag = ""
        if identity_match is not None:
            game_name = identity_match.group(1)
            game_tag = identity_match.group(2)
        elif puuid:
            known_friend = self._known_friends_by_puuid.get(puuid) or self._presence_by_puuid.get(puuid) or {}
            game_name = str(known_friend.get("game_name", "") or "").strip()
            game_tag = str(known_friend.get("game_tag", "") or "").strip()

        presence = self._build_presence_record(
            payload=payload,
            puuid=puuid,
            game_name=game_name,
            game_tag=game_tag,
            pid=pid,
        )
        if presence is None:
            return False

        party_id = presence.get("party_id")
        normalized = presence.get("normalized_riot_id")
        if party_id and normalized:
            self._party_by_riot_id[normalized] = {
                "party_id": party_id,
                "name": presence.get("game_name", ""),
                "tag": presence.get("game_tag", ""),
            }

        return self._store_presence(presence) or muc_updated

    def _process_presence_roster_items(self, stanza: str, payload, party_room_id="", pid="") -> bool:
        updated = False
        for item_match in re.finditer(r"<item\b([^>]*)>(.*?)</item>", stanza, flags=re.IGNORECASE | re.DOTALL):
            attrs = self._parse_xml_attrs(item_match.group(1))
            friend = self._normalize_roster_item(attrs, item_match.group(2))
            if not friend:
                continue

            if self._store_known_friend(friend):
                updated = True

            presence_payload = dict(payload) if isinstance(payload, dict) else {}
            if party_room_id:
                presence_payload.setdefault("partyId", party_room_id)

            presence = self._build_presence_record(
                payload=presence_payload,
                puuid=friend.get("puuid", ""),
                game_name=friend.get("game_name", ""),
                game_tag=friend.get("game_tag", ""),
                pid=pid,
            )
            if presence and self._store_presence(presence):
                updated = True

        return updated

    def _process_roster_stanza(self, stanza: str) -> bool:
        lowered = stanza.lower()
        if "<iq" not in lowered or "<item" not in lowered or "roster" not in lowered:
            return False

        updated = False
        consumed_spans = []
        for item_match in re.finditer(r"<item\b([^>]*)>(.*?)</item>", stanza, flags=re.IGNORECASE | re.DOTALL):
            consumed_spans.append(item_match.span())
            attrs = self._parse_xml_attrs(item_match.group(1))
            friend = self._normalize_roster_item(attrs, item_match.group(2))
            if friend and self._store_known_friend(friend):
                updated = True

        for item_match in re.finditer(r"<item\b([^>]*)/>", stanza, flags=re.IGNORECASE):
            span = item_match.span()
            if any(start <= span[0] and span[1] <= end for start, end in consumed_spans):
                continue
            attrs = self._parse_xml_attrs(item_match.group(1))
            friend = self._normalize_roster_item(attrs, "")
            if friend and self._store_known_friend(friend):
                updated = True

        return updated

    def _normalize_presence_entry(self, entry):
        if not isinstance(entry, dict):
            return None

        private_payload = (
            entry.get("private")
            or entry.get("Private")
            or entry.get("presence")
            or entry.get("Presence")
        )
        payload = None
        if isinstance(private_payload, dict):
            payload = private_payload
        elif isinstance(private_payload, str):
            payload = _decode_base64_json(private_payload) or _decode_jwt_payload(private_payload)

        if not payload:
            return None

        game_name = str(entry.get("game_name", "") or entry.get("gameName", "") or entry.get("name", "") or "").strip()
        game_tag = str(entry.get("game_tag", "") or entry.get("gameTag", "") or entry.get("tag", "") or "").strip()
        display_name = str(entry.get("game_name_tag_line", "") or entry.get("displayName", "") or "").strip()
        if not game_name and "#" in display_name:
            game_name, game_tag = _split_riot_id(display_name)

        puuid = str(entry.get("puuid", "") or entry.get("subject", "") or entry.get("Subject", "") or "").strip()
        pid = str(entry.get("pid", "") or entry.get("PID", "") or "").strip()
        return self._build_presence_record(
            payload=payload,
            puuid=puuid,
            game_name=game_name,
            game_tag=game_tag,
            pid=pid,
        )

    def _build_presence_record(self, payload: dict[str, Any], puuid="", game_name="", game_tag="", pid=""):
        if not isinstance(payload, dict):
            return None

        merged_payload = dict(payload)
        private_payload = self._extract_private_payload(merged_payload)
        if private_payload:
            merged_payload.update(private_payload)

        party_presence = merged_payload.get("partyPresenceData")
        if isinstance(party_presence, dict):
            for key, value in party_presence.items():
                merged_payload.setdefault(key, value)

        normalized_riot_id = ""
        if game_name or game_tag:
            normalized_riot_id = _normalize_riot_id(game_name, game_tag)

        party_id = str(
            merged_payload.get("partyId")
            or merged_payload.get("party_id")
            or ""
        ).strip()
        queue_id = str(
            merged_payload.get("queueId")
            or merged_payload.get("queueID")
            or merged_payload.get("partyQueueID")
            or ""
        ).strip()
        party_state = str(
            merged_payload.get("partyState")
            or merged_payload.get("party_state")
            or ""
        ).strip().upper()
        session_loop_state = str(
            merged_payload.get("sessionLoopState")
            or merged_payload.get("session_loop_state")
            or ""
        ).strip().upper()
        queue_entry_time = str(
            merged_payload.get("queueEntryTime")
            or merged_payload.get("queue_entry_time")
            or ""
        ).strip()
        is_queueing = self._determine_is_queueing(
            merged_payload,
            queue_id=queue_id,
            party_state=party_state,
            session_loop_state=session_loop_state,
        )

        presence = {
            "puuid": str(puuid or merged_payload.get("subject", "") or merged_payload.get("puuid", "") or "").strip(),
            "pid": str(pid or merged_payload.get("pid", "") or "").strip(),
            "game_name": str(game_name or merged_payload.get("gameName", "") or "").strip(),
            "game_tag": str(game_tag or merged_payload.get("tagLine", "") or merged_payload.get("gameTag", "") or "").strip(),
            "display_name": "",
            "normalized_riot_id": normalized_riot_id,
            "party_id": party_id,
            "queue_id": queue_id,
            "party_state": party_state,
            "session_loop_state": session_loop_state,
            "queue_entry_time": queue_entry_time,
            "is_queueing": is_queueing,
            "raw": merged_payload,
        }

        if presence["game_name"] and presence["game_tag"]:
            presence["display_name"] = f"{presence['game_name']}#{presence['game_tag']}"
        else:
            presence["display_name"] = presence["game_name"] or presence["puuid"]

        if presence["display_name"] and not presence["normalized_riot_id"]:
            presence["normalized_riot_id"] = self.normalize_display_name(presence["display_name"])

        if not presence["party_id"] and not presence["queue_id"] and not presence["normalized_riot_id"] and not presence["puuid"]:
            return None

        return presence

    def _extract_private_payload(self, payload):
        nested_candidates = (
            payload.get("private"),
            payload.get("Private"),
            payload.get("privateJwt"),
            payload.get("privateJWT"),
            payload.get("private_jwt"),
        )

        for candidate in nested_candidates:
            if isinstance(candidate, dict):
                return candidate
            if not isinstance(candidate, str) or not candidate:
                continue

            decoded = _decode_jwt_payload(candidate)
            if isinstance(decoded, dict):
                nested_private = decoded.get("private")
                if isinstance(nested_private, str):
                    nested_private_decoded = _decode_base64_json(nested_private)
                    if isinstance(nested_private_decoded, dict):
                        decoded.update(nested_private_decoded)
                return decoded

            decoded = _decode_base64_json(candidate)
            if isinstance(decoded, dict):
                return decoded

        return None

    def _determine_is_queueing(self, payload, queue_id="", party_state="", session_loop_state=""):
        explicit = payload.get("isQueueing")
        if isinstance(explicit, bool):
            return explicit

        if party_state in QUEUEING_PRESENCE_STATES and queue_id:
            return True

        if session_loop_state == "MENUS" and party_state == "MATCHMAKING":
            return True

        return False

    def _store_presence(self, presence):
        normalized = presence.get("normalized_riot_id") or ""
        puuid = presence.get("puuid") or ""

        current = None
        if puuid and puuid in self._presence_by_puuid:
            current = self._presence_by_puuid.get(puuid)
        elif normalized and normalized in self._presence_by_riot_id:
            current = self._presence_by_riot_id.get(normalized)

        if current and self._presence_signature(current) == self._presence_signature(presence):
            return False

        if normalized:
            self._presence_by_riot_id[normalized] = presence
        if puuid:
            self._presence_by_puuid[puuid] = presence
        return True

    def _store_known_friend(self, friend):
        puuid = str(friend.get("puuid", "") or "").strip()
        if not puuid:
            return False

        current = self._known_friends_by_puuid.get(puuid)
        signature = (
            puuid,
            str(friend.get("game_name", "") or "").strip(),
            str(friend.get("game_tag", "") or "").strip(),
            str(friend.get("display_name", "") or "").strip(),
            str(friend.get("pid", "") or "").strip(),
        )
        if current:
            current_signature = (
                str(current.get("puuid", "") or "").strip(),
                str(current.get("game_name", "") or "").strip(),
                str(current.get("game_tag", "") or "").strip(),
                str(current.get("display_name", "") or "").strip(),
                str(current.get("pid", "") or "").strip(),
            )
            if current_signature == signature:
                return False

        self._known_friends_by_puuid[puuid] = dict(friend)
        return True

    def _normalize_roster_item(self, attrs, inner_xml=""):
        if not isinstance(attrs, dict):
            return None

        nested = self._parse_roster_inner_xml(inner_xml)
        combined = dict(attrs)
        combined.update({key: value for key, value in nested.items() if value})

        jid = str(
            combined.get("jid")
            or combined.get("puuid")
            or combined.get("subject")
            or ""
        ).strip()
        puuid = jid.split("@", 1)[0].strip() if "@" in jid else jid
        if not puuid:
            return None

        game_name = str(
            combined.get("game_name")
            or combined.get("gameName")
            or combined.get("riot_name")
            or combined.get("riotName")
            or combined.get("name")
            or ""
        ).strip()
        game_tag = str(
            combined.get("tagline")
            or combined.get("game_tag")
            or combined.get("gameTag")
            or combined.get("riot_tag")
            or combined.get("riotTag")
            or combined.get("tag")
            or ""
        ).strip()
        display_name = str(
            combined.get("display_name")
            or combined.get("displayName")
            or combined.get("game_name_tag_line")
            or ""
        ).strip()
        if not display_name:
            if game_name and game_tag:
                display_name = f"{game_name}#{game_tag}"
            else:
                display_name = game_name or puuid

        return {
            "puuid": puuid,
            "game_name": game_name,
            "game_tag": game_tag,
            "display_name": display_name,
            "pid": str(combined.get("pid", "") or combined.get("PID", "") or "").strip(),
        }

    def _parse_xml_attrs(self, attrs_text: str):
        attrs = {}
        for key, value in re.findall(r"([:\w-]+)\s*=\s*['\"]([^'\"]*)['\"]", attrs_text or ""):
            attrs[key] = value
        return attrs

    def _parse_roster_inner_xml(self, inner_xml: str):
        if not inner_xml:
            return {}

        parsed = {}

        id_match = re.search(r"<id\b([^>]*)/?>", inner_xml, flags=re.IGNORECASE)
        if id_match:
            parsed.update(self._parse_xml_attrs(id_match.group(1)))

        for tag_name, value in re.findall(r"<([:\w-]+)>([^<]+)</\1>", inner_xml, flags=re.IGNORECASE):
            if value and value.strip():
                parsed[tag_name] = value.strip()

        return parsed

    def _presence_signature(self, presence):
        raw = presence.get("raw") if isinstance(presence, dict) else {}
        raw_signature = json.dumps(raw, sort_keys=True, default=str) if isinstance(raw, dict) else str(raw)
        return (
            presence.get("puuid"),
            presence.get("normalized_riot_id"),
            presence.get("party_id"),
            presence.get("queue_id"),
            presence.get("party_state"),
            presence.get("session_loop_state"),
            presence.get("queue_entry_time"),
            bool(presence.get("is_queueing")),
            raw_signature,
        )

    def _build_party_label(self, index: int) -> str:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if index < len(alphabet):
            suffix = alphabet[index]
        else:
            suffix = f"{(index // len(alphabet)) + 1}{alphabet[index % len(alphabet)]}"
        return f"Party {suffix}"
