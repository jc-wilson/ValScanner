import asyncio
import base64
import json
import re
import ssl
from datetime import datetime
from xml.etree import ElementTree

from core.party_tracker import PartyTracker
from core.presence_mode import PRESENCE_MODE_OFFLINE, normalize_presence_mode

"""This class creates connections to the previously in ConfigMITM modified chat-servers and logs the communication between that
    First it creates a local socket to listen for incoming requests on port 35478 (the previously modified port) to determine which chat server to connect to
    As soon as a request comes in, it saves the host it now communicates on (ipv4LocalHost) and finds the relevant chat socket in the mappings to connect to it
    After connecting to the chat socket, it starts logging all the incoming and outgoing traffic"""


XML_ATTR_RE = re.compile(r"([:\w-]+)\s*=\s*(['\"])(.*?)\2", flags=re.DOTALL)
ROSTER_QUERY_RE = re.compile(
    r"(<query\b[^>]*\bxmlns\s*=\s*(['\"])jabber:iq:riotgames:roster\2[^>]*>)",
    flags=re.IGNORECASE,
)
FAKE_PLAYER_PUUID = "41c322a1-b328-495b-a004-5ccd3e45eae8"
FAKE_PLAYER_JID = f"{FAKE_PLAYER_PUUID}@ares.pvp.net"
FAKE_PLAYER_RESOURCE = "RC-ValScanner"
FAKE_PLAYER_ROSTER_ITEM = (
    f"<item jid='{FAKE_PLAYER_JID}' name='ValScanner Offline' subscription='both' puuid='{FAKE_PLAYER_PUUID}'>"
    "<group priority='9999'>ValScanner</group>"
    "<state>online</state>"
    "<id name='ValScanner Offline' tagline='...'/>"
    "<platforms><riot name='ValScanner Offline' tagline='...'/></platforms>"
    "</item>"
)


def _find_tag_end(text: str, start_index: int = 0):
    in_quote = None
    for index in range(start_index, len(text)):
        char = text[index]
        if in_quote:
            if char == in_quote:
                in_quote = None
            continue
        if char in ("'", '"'):
            in_quote = char
            continue
        if char == ">":
            return index
    return -1


def _extract_tag_name(tag_contents: str):
    stripped = str(tag_contents or "").lstrip()
    if not stripped:
        return ""
    if stripped[0] in ("/", "?", "!"):
        stripped = stripped[1:].lstrip()
    tag_name = []
    for char in stripped:
        if char.isspace() or char in ("/", ">"):
            break
        tag_name.append(char)
    return "".join(tag_name)


def _is_self_closing_tag(tag_text: str):
    stripped = str(tag_text or "").rstrip()
    return stripped.endswith("/>")


def _extract_next_xml_fragment(buffer: str):
    if not buffer:
        return None, buffer

    lt_index = buffer.find("<")
    if lt_index == -1:
        return None, buffer
    if lt_index > 0:
        return buffer[:lt_index], buffer[lt_index:]

    if buffer.startswith("<?"):
        end_index = buffer.find("?>")
        if end_index == -1:
            return None, buffer
        return buffer[:end_index + 2], buffer[end_index + 2:]

    if buffer.startswith("<!--"):
        end_index = buffer.find("-->")
        if end_index == -1:
            return None, buffer
        return buffer[:end_index + 3], buffer[end_index + 3:]

    if buffer.startswith("<![CDATA["):
        end_index = buffer.find("]]>")
        if end_index == -1:
            return None, buffer
        return buffer[:end_index + 3], buffer[end_index + 3:]

    start_tag_end = _find_tag_end(buffer, 0)
    if start_tag_end == -1:
        return None, buffer

    if buffer.startswith("</"):
        return buffer[:start_tag_end + 1], buffer[start_tag_end + 1:]

    start_tag_text = buffer[:start_tag_end + 1]
    tag_name = _extract_tag_name(start_tag_text[1:])
    if not tag_name:
        return None, buffer

    if _is_self_closing_tag(start_tag_text) or tag_name == "stream:stream":
        return start_tag_text, buffer[start_tag_end + 1:]

    depth = 1
    search_index = start_tag_end + 1
    while True:
        next_lt = buffer.find("<", search_index)
        if next_lt == -1:
            return None, buffer

        if buffer.startswith("<!--", next_lt):
            comment_end = buffer.find("-->", next_lt)
            if comment_end == -1:
                return None, buffer
            search_index = comment_end + 3
            continue

        if buffer.startswith("<![CDATA[", next_lt):
            cdata_end = buffer.find("]]>", next_lt)
            if cdata_end == -1:
                return None, buffer
            search_index = cdata_end + 3
            continue

        next_tag_end = _find_tag_end(buffer, next_lt)
        if next_tag_end == -1:
            return None, buffer

        next_tag_text = buffer[next_lt:next_tag_end + 1]
        next_tag_name = _extract_tag_name(next_tag_text[1:])
        if next_tag_name == tag_name:
            if next_tag_text.startswith("</"):
                depth -= 1
                if depth == 0:
                    return buffer[:next_tag_end + 1], buffer[next_tag_end + 1:]
            elif not _is_self_closing_tag(next_tag_text):
                depth += 1

        search_index = next_tag_end + 1


def _extract_presence_attrs_text(stanza: str):
    match = re.search(r"<presence\b(.*?)(/?)>", stanza or "", flags=re.IGNORECASE | re.DOTALL)
    if match is None:
        return ""
    return match.group(1) or ""


def _parse_xml_attrs(attrs_text: str):
    return [(key, value) for key, _, value in XML_ATTR_RE.findall(attrs_text or "")]


def _presence_type(stanza: str):
    for key, value in _parse_xml_attrs(_extract_presence_attrs_text(stanza)):
        if key.lower() == "type":
            return str(value or "").strip().lower()
    return ""


def _is_presence_stanza(stanza: str):
    return str(stanza or "").lstrip().startswith("<presence")


def _is_global_presence_stanza(stanza: str):
    if not _is_presence_stanza(stanza):
        return False
    attrs_text = _extract_presence_attrs_text(stanza)
    return re.search(r"\bto\s*=", attrs_text, flags=re.IGNORECASE) is None


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


def _extract_party_client_version(presence_element):
    if presence_element is None:
        return None

    games_element = presence_element.find("games")
    if games_element is None:
        return None

    valorant_element = games_element.find("valorant")
    if valorant_element is None:
        return None

    payload_element = valorant_element.find("p")
    if payload_element is None or not payload_element.text:
        return None

    decoded_payload = _decode_base64_json(payload_element.text)
    if not isinstance(decoded_payload, dict):
        return None

    party_presence_data = decoded_payload.get("partyPresenceData")
    if not isinstance(party_presence_data, dict):
        return None
    version = party_presence_data.get("partyClientVersion")
    if not version:
        return None
    return str(version).strip() or None


def build_offline_presence_stanza(stanza: str):
    try:
        presence = ElementTree.fromstring(stanza)
    except ElementTree.ParseError:
        return stanza

    if presence.tag != "presence":
        return stanza

    presence.attrib.pop("type", None)

    show_element = presence.find("show")
    if show_element is not None:
        show_element.text = "offline"

    status_element = presence.find("status")
    if status_element is not None:
        presence.remove(status_element)

    games_element = presence.find("games")
    if games_element is not None:
        for child in list(games_element):
            games_element.remove(child)

    return ElementTree.tostring(presence, encoding="unicode")


def _inject_fake_player_into_roster(stanza: str):
    if FAKE_PLAYER_JID in stanza:
        return stanza
    match = ROSTER_QUERY_RE.search(stanza or "")
    if match:
        return stanza[:match.end()] + FAKE_PLAYER_ROSTER_ITEM + stanza[match.end():]
    return stanza


def _build_fake_roster_push(remove: bool = False):
    roster_item = (
        f"<item jid='{FAKE_PLAYER_JID}' subscription='remove' />"
        if remove else
        FAKE_PLAYER_ROSTER_ITEM
    )
    return (
        "<iq type='set' id='valscanner-roster-sync'>"
        "<query xmlns='jabber:iq:riotgames:roster'>"
        f"{roster_item}"
        "</query>"
        "</iq>"
    )


def _build_fake_player_presence(version: str | None = None, available: bool = True):
    if not available:
        return f"<presence from='{FAKE_PLAYER_JID}/{FAKE_PLAYER_RESOURCE}' type='unavailable' />"

    safe_version = version or "unknown"
    unix_time_milliseconds = int(datetime.now().timestamp() * 1000)
    encoded_valorant_presence = base64.b64encode(json.dumps({
        "partyPresenceData": {
            "partyId": "00000000-0000-0000-0000-000000000000",
            "partyClientVersion": safe_version,
            "partyState": "DEFAULT",
            "partyOwnerSessionLoopState": "MENUS",
            "queueEntryTime": "0001.01.01-00.00.00",
        },
        "playerPresenceData": {
            "accountLevel": 1,
            "competitiveTier": 0,
        },
        "sessionLoopState": "MENUS",
        "queueId": "",
    }).encode("utf-8")).decode("utf-8")

    return (
        f"<presence from='{FAKE_PLAYER_JID}/{FAKE_PLAYER_RESOURCE}' id='valscanner-fake-presence'>"
        "<games>"
        f"<keystone><st>chat</st><s.t>{unix_time_milliseconds}</s.t><s.p>keystone</s.p><pty/></keystone>"
        f"<valorant><st>chat</st><s.t>{unix_time_milliseconds}</s.t><s.p>valorant</s.p><s.r>PC</s.r><p>{encoded_valorant_presence}</p><pty/></valorant>"
        "</games>"
        "<show>chat</show>"
        "<platform>riot</platform>"
        "<status/>"
        "</presence>"
    )


class XmppMITM:
    def __init__(self, xmpp_port=int, config_mitm=object, log_stream=object):
        self.port = xmpp_port
        self.config_mitm = config_mitm
        self.log_stream = log_stream
        self.socketID = 0
        self.server = None
        self.party_tracker = PartyTracker.get()
        self._serve_task = None
        self._socket_tasks = {}
        self._socket_writers = {}
        self._incoming_buffers = {}
        self._outgoing_buffers = {}
        self._fake_player_inserted = set()
        self._fake_player_visible = set()
        self._shutting_down = False
        self._presence_mode = normalize_presence_mode(None)
        self._last_presence_stanza = ""
        self._valorant_version = None

    async def start(self) -> None:
        """Starts the XMPP server to listen to all hosts on port 35478 -> None"""

        print("Starting XMPP server...")
        self.server = await asyncio.start_server(self.handle_client, "0.0.0.0", self.port)
        print("Started XMPP Server!")
        self._shutting_down = False
        self._serve_task = asyncio.create_task(self.server.serve_forever())

    async def stop(self) -> None:
        self._shutting_down = True

        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

        if self._serve_task is not None:
            self._serve_task.cancel()
            results = await asyncio.gather(self._serve_task, return_exceptions=True)
            self._consume_task_results(results)
            self._serve_task = None

        active_tasks = []
        for tasks in self._socket_tasks.values():
            active_tasks.extend(tasks.values())

        for task in active_tasks:
            task.cancel()

        if active_tasks:
            results = await asyncio.gather(*active_tasks, return_exceptions=True)
            self._consume_task_results(results)

        self._socket_tasks.clear()
        self._socket_writers.clear()
        self._incoming_buffers.clear()
        self._outgoing_buffers.clear()
        self._fake_player_inserted.clear()
        self._fake_player_visible.clear()

    def get_presence_mode(self):
        return self._presence_mode

    def set_presence_mode(self, mode, broadcast=True):
        normalized_mode = normalize_presence_mode(mode)
        changed = normalized_mode != self._presence_mode
        self._presence_mode = normalized_mode

        loop = None

        if broadcast and changed and self._last_presence_stanza:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return normalized_mode
            task = loop.create_task(self._broadcast_presence_update())
            task.add_done_callback(self._consume_background_task_result)

        if broadcast and changed:
            if loop is None:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    return normalized_mode
            task = loop.create_task(self._broadcast_fake_player_state())
            task.add_done_callback(self._consume_background_task_result)

        return normalized_mode

    async def handle_client(self, client_reader: object, client_writer: object) -> None:
        """Handles incoming connections by connecting to the according chat socket -> None"""

        if self._shutting_down:
            client_writer.close()
            await self._wait_for_close(client_writer)
            return

        server_addr = client_writer.get_extra_info("sockname")
        ipv4LocalHost = server_addr[0]
        peer_addr = client_writer.get_extra_info("peername")
        mapping = next((m for m in self.config_mitm.affinityMappings if m["localHost"] == ipv4LocalHost), None)
        if mapping is None:
            print(f"[XMPPMitm] Unknown host local={ipv4LocalHost} peer={peer_addr}")
            await self.log_message(f"Unknown host {ipv4LocalHost}")
            client_writer.close()
            await client_writer.wait_closed()
            return

        self.socketID += 1
        current_socket_id = self.socketID
        await self.log_message(json.dumps({
            "type": "open-valorant",
            "time": datetime.now().timestamp(),
            "host": mapping["riotHost"],
            "port": mapping["riotPort"],
            "socketID": current_socket_id,
        }))
        print(
            f"[XMPPMitm] socket={current_socket_id} accepted local={ipv4LocalHost} peer={peer_addr} "
            f"mapped_host={mapping['riotHost']} mapped_port={mapping['riotPort']}"
        )

        try:
            riot_reader, riot_writer = await asyncio.open_connection(
                mapping["riotHost"], mapping["riotPort"], ssl=ssl.create_default_context()
            )
        except Exception as exc:
            await self.log_message(json.dumps({
                "type": "xmpp-connect-error",
                "time": datetime.now().timestamp(),
                "host": mapping["riotHost"],
                "port": mapping["riotPort"],
                "socketID": current_socket_id,
                "error": str(exc),
            }))
            print(f"[XMPPMitm] socket={current_socket_id} connect failed error={exc}")
            client_writer.close()
            await client_writer.wait_closed()
            return

        print(f"[XMPPMitm] socket={current_socket_id} connected to riot chat")
        self._socket_writers[current_socket_id] = {
            "client": client_writer,
            "riot": riot_writer,
        }

        outgoing_task = asyncio.create_task(
            self.transfer_data(client_reader, riot_writer, current_socket_id, "outgoing")
        )
        incoming_task = asyncio.create_task(
            self.transfer_data(riot_reader, client_writer, current_socket_id, "incoming")
        )
        self._socket_tasks[current_socket_id] = {
            "outgoing": outgoing_task,
            "incoming": incoming_task,
        }

        results = await asyncio.gather(
            outgoing_task,
            incoming_task,
            return_exceptions=True,
        )
        self._consume_task_results(results)

        self.party_tracker.clear_socket(current_socket_id)
        self._incoming_buffers.pop(current_socket_id, None)
        self._outgoing_buffers.pop(current_socket_id, None)
        self._fake_player_inserted.discard(current_socket_id)
        self._fake_player_visible.discard(current_socket_id)
        self._socket_tasks.pop(current_socket_id, None)
        self._socket_writers.pop(current_socket_id, None)
        await self._close_socket_pair(client_writer, riot_writer)
        print(f"[XMPPMitm] socket={current_socket_id} closed")
        await self._safe_log_message(json.dumps({
            "type": "close-valorant",
            "time": datetime.now().timestamp(),
            "socketID": current_socket_id,
        }))

    async def transfer_data(self, reader=object, writer=object, socket_id=int, direction=str) -> None:
        """Transfers the data into the necessary direction"""

        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    if direction == "outgoing":
                        flushed = self.flush_buffered_text(socket_id, direction)
                        if flushed:
                            await self._write_text_fragments(writer, flushed)
                            await self._safe_log_message(json.dumps({
                                "type": direction,
                                "time": datetime.now().timestamp(),
                                "data": "".join(flushed),
                                "socketID": socket_id,
                            }))
                    self._signal_stream_end(writer, socket_id, direction)
                    break

                decoded_text = data.decode(errors="ignore")
                if direction == "incoming":
                    writer.write(data)
                    await writer.drain()
                    self._observe_incoming_text(socket_id, decoded_text)
                    await self._safe_log_message(json.dumps({
                        "type": direction,
                        "time": datetime.now().timestamp(),
                        "data": decoded_text,
                        "socketID": socket_id,
                    }))
                    continue

                fragments = self.process_buffered_text(socket_id, decoded_text, direction)
                if fragments:
                    await self._write_text_fragments(writer, fragments)
                    await self._safe_log_message(json.dumps({
                        "type": direction,
                        "time": datetime.now().timestamp(),
                        "data": "".join(fragments),
                        "socketID": socket_id,
                    }))
        except asyncio.CancelledError:
            raise
        except (ssl.SSLError, ConnectionError, OSError, asyncio.IncompleteReadError):
            print(f"[XMPPMitm] socket={socket_id} {direction} stream closed")
        except Exception as exc:
            print(f"[XMPPMitm] socket={socket_id} {direction} unexpected transfer error={exc!r}")

    def process_buffered_text(self, socket_id: int, text: str, direction: str):
        if not text:
            return []

        buffers = self._outgoing_buffers if direction == "outgoing" else self._incoming_buffers
        buffer = buffers.get(socket_id, "") + text
        fragments = []

        while True:
            fragment, buffer = _extract_next_xml_fragment(buffer)
            if fragment is None:
                break
            rewritten = self._rewrite_fragment(socket_id, fragment, direction)
            if rewritten:
                fragments.append(rewritten)

        buffers[socket_id] = buffer[-20000:]
        return fragments

    def flush_buffered_text(self, socket_id: int, direction: str):
        buffers = self._outgoing_buffers if direction == "outgoing" else self._incoming_buffers
        buffer = buffers.pop(socket_id, "")
        if not buffer:
            return []
        return [self._rewrite_fragment(socket_id, buffer, direction)]

    def process_outgoing_text(self, socket_id: int, text: str):
        return self.process_buffered_text(socket_id, text, "outgoing")

    def process_incoming_text(self, socket_id: int, text: str):
        return self.process_buffered_text(socket_id, text, "incoming")

    def _rewrite_fragment(self, socket_id: int, fragment: str, direction: str):
        if direction == "incoming":
            return self._rewrite_incoming_fragment(socket_id, fragment)
        return self._rewrite_outgoing_fragment(fragment)

    def _rewrite_outgoing_fragment(self, fragment: str):
        if FAKE_PLAYER_PUUID in fragment or FAKE_PLAYER_JID in fragment:
            return ""
        if not _is_presence_stanza(fragment):
            return fragment
        if not _is_global_presence_stanza(fragment):
            return fragment
        return self._apply_presence_mode(fragment, cache_original=True)

    def _rewrite_incoming_fragment(self, socket_id: int, fragment: str):
        return fragment

    def _observe_incoming_text(self, socket_id: int, text: str):
        if not text:
            return

        try:
            updated = self.party_tracker.feed_chunk(socket_id, text)
            if updated:
                print(f"[XMPPMitm] socket={socket_id} presence cache updated")
        except Exception as exc:
            print(f"[XMPPMitm] socket={socket_id} presence parse error={exc!r}")

    def _apply_presence_mode(self, stanza: str, cache_original: bool):
        if cache_original and _presence_type(stanza) != "unavailable":
            self._last_presence_stanza = stanza
            if self._valorant_version is None:
                try:
                    presence_element = ElementTree.fromstring(stanza)
                except ElementTree.ParseError:
                    presence_element = None
                self._valorant_version = _extract_party_client_version(presence_element)
        if self._presence_mode == PRESENCE_MODE_OFFLINE:
            return build_offline_presence_stanza(stanza)
        return stanza

    async def _broadcast_presence_update(self):
        if not self._last_presence_stanza:
            return

        stanza = self._apply_presence_mode(self._last_presence_stanza, cache_original=False)
        if not stanza:
            return

        data = stanza.encode("utf-8")
        for socket_id, writers in list(self._socket_writers.items()):
            riot_writer = writers.get("riot")
            if riot_writer is None:
                continue
            try:
                riot_writer.write(data)
                await riot_writer.drain()
            except Exception as exc:
                print(f"[XMPPMitm] socket={socket_id} presence sync failed error={exc!r}")
                continue

            await self._safe_log_message(json.dumps({
                "type": "presence-mode-sync",
                "time": datetime.now().timestamp(),
                "data": stanza,
                "socketID": socket_id,
                "presenceMode": self._presence_mode,
            }))

    async def _broadcast_fake_player_state(self):
        for socket_id, writers in list(self._socket_writers.items()):
            client_writer = writers.get("client")
            if client_writer is None:
                continue

            payloads = []
            if self._presence_mode == PRESENCE_MODE_OFFLINE:
                if socket_id not in self._fake_player_visible:
                    payloads.append(_build_fake_roster_push(remove=False))
                    self._fake_player_visible.add(socket_id)
                payloads.append(_build_fake_player_presence(version=self._valorant_version, available=True))
            else:
                if socket_id in self._fake_player_visible:
                    payloads.append(_build_fake_player_presence(version=self._valorant_version, available=False))
                    payloads.append(_build_fake_roster_push(remove=True))
                    self._fake_player_visible.discard(socket_id)

            if not payloads:
                continue

            try:
                await self._write_text_fragments(client_writer, payloads)
            except Exception as exc:
                print(f"[XMPPMitm] socket={socket_id} fake player sync failed error={exc!r}")
                continue

            await self._safe_log_message(json.dumps({
                "type": "fake-player-sync",
                "time": datetime.now().timestamp(),
                "data": "".join(payloads),
                "socketID": socket_id,
                "presenceMode": self._presence_mode,
            }))

    async def _write_text_fragments(self, writer, fragments):
        for fragment in fragments:
            writer.write(fragment.encode("utf-8"))
        await writer.drain()

    async def log_message(self, message=str) -> None:
        """Logs the messages"""

        await self.log_stream.write(message + "\n")

    async def _safe_log_message(self, message=str) -> None:
        if self._shutting_down or self.log_stream is None:
            return
        try:
            await self.log_message(message)
        except Exception:
            pass

    async def _close_socket_pair(self, *writers) -> None:
        for writer in writers:
            if writer is None:
                continue
            try:
                writer.close()
            except Exception:
                continue

        await asyncio.gather(
            *(self._wait_for_close(writer) for writer in writers if writer is not None),
            return_exceptions=True,
        )

    async def _wait_for_close(self, writer) -> None:
        try:
            await writer.wait_closed()
        except Exception:
            pass

    def _consume_task_results(self, results) -> None:
        for result in results:
            if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
                print(f"XMPP task error: {result}")

    def _consume_background_task_result(self, task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            print(f"XMPP background task error: {exc}")

    def _signal_stream_end(self, writer, socket_id: int, direction: str) -> None:
        try:
            if writer.can_write_eof():
                writer.write_eof()
                print(f"[XMPPMitm] socket={socket_id} {direction} EOF forwarded")
                return
        except Exception:
            pass

        try:
            writer.close()
            print(f"[XMPPMitm] socket={socket_id} {direction} writer closed")
        except Exception:
            pass
