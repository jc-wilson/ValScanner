import asyncio
import json
import math

import aiohttp

from core.detection import MatchDetectionHandler
from core.http_session import SharedSession
from core.local_api import LockfileHandler, RiotClientNotReady


PARTY_QUEUEING_STATES = {
    "MATCHMAKING",
    "STARTING_MATCHMAKING",
    "MATCHMADE_GAME_STARTING",
}


class QueueSnipeService:
    def __init__(self, party_tracker, status_callback=None):
        self.party_tracker = party_tracker
        self.status_callback = status_callback
        self._selected_friend = None
        self._enabled = False
        self._last_presence_signature = None
        self._last_applied_queue_id = None
        self._sync_task = None
        self._resync_requested = False
        self._seed_presence_requested = False
        self._local_party_cache = {}
        self._local_self_puuid = ""

    def _debug(self, message):
        print(f"[QueueSnipe] {message}")

    @property
    def enabled(self):
        return self._enabled

    @property
    def selected_friend(self):
        return dict(self._selected_friend) if isinstance(self._selected_friend, dict) else None

    @staticmethod
    def normalize_friend(friend_data):
        if not isinstance(friend_data, dict):
            return None

        puuid = str(friend_data.get("puuid", "") or "").strip()
        if not puuid:
            return None

        game_name = str(friend_data.get("game_name", "") or friend_data.get("gameName", "") or "").strip()
        game_tag = str(friend_data.get("game_tag", "") or friend_data.get("gameTag", "") or "").strip()
        display_name = str(friend_data.get("display_name", "") or friend_data.get("displayName", "") or "").strip()
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
            "pid": str(friend_data.get("pid", "") or friend_data.get("PID", "") or "").strip(),
        }

    async def fetch_friends(self):
        self._debug("fetch_friends called")
        try:
            friends_payload = await self._request_local_chat_json(
                "/chat/v4/friends",
                "Friends request",
                retries=1,
            )
        except RuntimeError as exc:
            fallback_friends = self._fallback_friends_from_presence()
            if fallback_friends:
                self._debug(
                    f"Friends request failed, falling back to {len(fallback_friends)} XMPP presence entries: {exc}"
                )
                return fallback_friends
            raise
        self._debug(f"friends payload type={type(friends_payload).__name__}")
        if isinstance(friends_payload, dict):
            self._debug(f"friends payload keys={list(friends_payload.keys())[:20]}")

        if isinstance(friends_payload, dict):
            iterable = friends_payload.get("friends") or friends_payload.get("Friends") or friends_payload.values()
        else:
            iterable = friends_payload or []

        friends = []
        skipped_entries = 0
        for index, entry in enumerate(iterable):
            normalized = self.normalize_friend(entry)
            if normalized is not None:
                friends.append(normalized)
                if index < 5:
                    self._debug(
                        f"normalized friend[{index}] display_name={normalized.get('display_name')} "
                        f"puuid={normalized.get('puuid')} pid={normalized.get('pid')}"
                    )
            else:
                skipped_entries += 1
                if skipped_entries <= 5:
                    self._debug(f"skipped friend entry[{index}]={self._format_response_preview(entry, limit=260)}")

        friends.sort(key=lambda item: (item["display_name"].lower(), item["puuid"].lower()))
        self._debug(f"parsed {len(friends)} friends, skipped {skipped_entries}")
        return friends

    async def seed_local_presence(self):
        self._debug("seed_local_presence called")
        presence_payload = await self._request_local_chat_json(
            "/chat/v4/presences",
            "Presence request",
            retries=1,
        )
        self._debug(f"presence payload type={type(presence_payload).__name__}")
        if isinstance(presence_payload, dict):
            self._debug(f"presence payload keys={list(presence_payload.keys())[:20]}")

        if isinstance(presence_payload, dict):
            presences = (
                presence_payload.get("presences")
                or presence_payload.get("Presences")
                or presence_payload.get("friends")
                or presence_payload.get("Friends")
                or presence_payload.values()
            )
        else:
            presences = presence_payload or []

        return self.party_tracker.seed_presences(presences)

    def set_enabled(self, enabled):
        enabled = bool(enabled)
        self._debug(f"set_enabled called enabled={enabled} selected_friend={self._selected_friend}")
        if self._enabled == enabled:
            if enabled and self._selected_friend:
                self.schedule_sync(seed_presence=True)
            return

        self._enabled = enabled
        self._last_presence_signature = None
        if not enabled:
            self._cancel_sync_task()
            return

        if self._selected_friend:
            self.schedule_sync(seed_presence=True)

    def set_selected_friend(self, friend_data):
        normalized = self.normalize_friend(friend_data)
        self._debug(f"set_selected_friend called normalized={normalized}")
        self._selected_friend = normalized
        self._last_presence_signature = None
        if not self._selected_friend:
            self._cancel_sync_task()
            return

        if self._enabled:
            self.schedule_sync(seed_presence=True)

    def handle_presence_update(self):
        if not self._enabled or not self._selected_friend:
            return
        self._debug("handle_presence_update scheduling sync")
        self.schedule_sync(seed_presence=False)

    def handle_local_json_api_event(self, event_data, self_puuid=""):
        if not isinstance(event_data, dict):
            return

        if self_puuid:
            self._local_self_puuid = str(self_puuid).strip()

        uri = str(event_data.get("uri", "") or "").strip()
        if "/parties/v1/" not in uri:
            return

        payload = event_data.get("data")
        self._debug(
            f"handle_local_json_api_event uri={uri} payload={self._format_response_preview(payload, limit=260)}"
        )

        if "/parties/v1/players/" in uri:
            if isinstance(payload, dict):
                current_party_id = str(payload.get("CurrentPartyID", "") or "").strip()
                if current_party_id:
                    self._local_party_cache["party_id"] = current_party_id
                    self._debug(f"cached local party_id from websocket={current_party_id}")
            return

        if "/parties/v1/parties/" in uri and isinstance(payload, dict):
            party_id = self._extract_party_id_from_uri(uri)
            if party_id:
                self._local_party_cache["party_id"] = party_id

            matchmaking_data = payload.get("MatchmakingData") or {}
            state = str(payload.get("State", "") or "").strip().upper()
            queue_id = str(matchmaking_data.get("QueueID", "") or "").strip()
            if party_id:
                self._local_party_cache.update(
                    {
                        "party_id": party_id,
                        "queue_id": queue_id,
                        "state": state,
                        "is_queueing": bool(queue_id and state in PARTY_QUEUEING_STATES),
                    }
                )
                self._debug(
                    f"updated local party cache from websocket party_id={party_id} "
                    f"queue_id={queue_id} state={state}"
                )

    def set_local_self_puuid(self, puuid):
        self._local_self_puuid = str(puuid or "").strip()

    def schedule_sync(self, seed_presence=False):
        if not self._enabled or not self._selected_friend:
            return

        self._debug(
            f"schedule_sync seed_presence={seed_presence} in_flight={self._sync_task is not None and not self._sync_task.done()}"
        )
        self._seed_presence_requested = self._seed_presence_requested or bool(seed_presence)
        if self._sync_task is not None and not self._sync_task.done():
            self._resync_requested = True
            return

        loop = asyncio.get_running_loop()
        self._sync_task = loop.create_task(self._sync_loop())

    async def _sync_loop(self):
        try:
            while True:
                seed_presence = self._seed_presence_requested
                self._seed_presence_requested = False
                self._resync_requested = False
                self._debug(f"_sync_loop iteration seed_presence={seed_presence}")

                if seed_presence:
                    try:
                        await self.seed_local_presence()
                    except Exception as exc:
                        self._report_status(f"Queue snipe presence seed failed: {exc}")

                await self._sync_selected_friend_queue()
                if not self._resync_requested:
                    break
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._report_status(f"Queue snipe sync failed: {exc}")
        finally:
            self._sync_task = None

    async def _sync_selected_friend_queue(self):
        if not self._enabled or not self._selected_friend:
            return

        presence = self.party_tracker.get_presence(puuid=self._selected_friend.get("puuid"))
        if presence is None and self._selected_friend.get("display_name"):
            presence = self.party_tracker.get_presence(riot_id=self._selected_friend.get("display_name"))
        self._debug(f"_sync_selected_friend_queue presence={self._format_response_preview(presence, limit=320)}")

        signature = self._build_presence_signature(presence)
        if signature == self._last_presence_signature:
            self._debug("presence signature unchanged; skipping queue sync")
            return
        self._last_presence_signature = signature

        if not presence:
            self._debug("no presence cached for selected friend")
            return

        if presence.get("is_queueing") and presence.get("queue_id"):
            self._debug(f"friend queue detected queue_id={presence.get('queue_id')}")
            await self._sync_to_queue(str(presence.get("queue_id")))
            return

        self._debug("friend not queueing; leaving current queue if needed")
        await self._leave_current_queue()

    def _build_presence_signature(self, presence):
        if not isinstance(presence, dict):
            return None
        return (
            presence.get("puuid"),
            presence.get("party_id"),
            presence.get("queue_id"),
            presence.get("party_state"),
            presence.get("session_loop_state"),
            presence.get("queue_entry_time"),
            bool(presence.get("is_queueing")),
        )

    async def _sync_to_queue(self, queue_id):
        self._debug(f"_sync_to_queue queue_id={queue_id}")
        context = await self._get_current_party_context()
        if not context or not context.get("party_id"):
            self._debug("no current party context available")
            return

        party_id = context["party_id"]
        current_queue_id = context.get("queue_id", "")
        is_queueing = bool(context.get("is_queueing"))
        self._debug(
            f"party context party_id={party_id} current_queue_id={current_queue_id} "
            f"is_queueing={is_queueing} state={context.get('state')}"
        )

        if is_queueing and current_queue_id == queue_id:
            self._last_applied_queue_id = queue_id
            return

        if is_queueing and current_queue_id and current_queue_id != queue_id:
            await self._post_party_action(context, f"/parties/v1/parties/{party_id}/matchmaking/leave", "Leave queue")
            is_queueing = False

        if current_queue_id != queue_id:
            await self._post_party_action(
                context,
                f"/parties/v1/parties/{party_id}/queue",
                "Change queue",
                json_body={"queueId": queue_id},
            )

        if not is_queueing or current_queue_id != queue_id:
            await self._post_party_action(context, f"/parties/v1/parties/{party_id}/matchmaking/join", "Join queue")

        self._last_applied_queue_id = queue_id

    async def _leave_current_queue(self):
        self._debug("_leave_current_queue called")
        context = await self._get_current_party_context()
        if not context or not context.get("party_id"):
            self._debug("no party context while leaving queue")
            self._last_applied_queue_id = None
            return

        if not context.get("is_queueing"):
            self._debug("current party is not queueing")
            self._last_applied_queue_id = None
            return

        try:
            await self._post_party_action(
                context,
                f"/parties/v1/parties/{context['party_id']}/matchmaking/leave",
                "Leave queue",
            )
        except RuntimeError as exc:
            if not self._is_expected_leave_error(exc):
                raise

        self._last_applied_queue_id = None

    def shutdown(self):
        self._enabled = False
        self._selected_friend = None
        self._last_presence_signature = None
        self._last_applied_queue_id = None
        self._cancel_sync_task()

    async def _get_local_client_context(self):
        self._debug("_get_local_client_context called via LockfileHandler")
        handler = LockfileHandler()
        ready = await handler.lockfile_data_function(retries=1, raise_on_failure=True)
        if not ready or not handler.port or not handler.password:
            raise RiotClientNotReady("Riot local client is not ready.")

        self._debug(f"local client context ready port={handler.port}")
        return {
            "port": handler.port,
            "auth": aiohttp.BasicAuth("riot", handler.password),
            "puuid": str(handler.puuid or "").strip(),
        }

    async def _request_local_chat_json(self, path, context, retries=1, retry_delay=1):
        try:
            local_context = await self._get_local_client_context()
        except RiotClientNotReady as exc:
            raise RuntimeError(self._format_local_client_error(exc)) from exc

        session = SharedSession.get()
        last_error = None
        for attempt in range(max(retries, 1)):
            self._debug(
                f"{context} attempt {attempt + 1}/{max(retries, 1)} url=https://127.0.0.1:{local_context['port']}{path}"
            )
            try:
                self._debug(f"{context} using aiohttp.BasicAuth for local chat request")
                async with session.get(
                    f"https://127.0.0.1:{local_context['port']}{path}",
                    auth=local_context["auth"],
                    ssl=False,
                ) as resp:
                    self._debug(f"{context} response status={resp.status}")
                    result = await self._read_json_response(
                        resp,
                        context,
                        friendly_message=self._format_chat_not_ready_message(resp),
                    )
                    self._debug(f"{context} succeeded with parsed type={type(result).__name__}")
                    return result
            except aiohttp.ClientError as exc:
                last_error = exc
                self._debug(f"{context} aiohttp error={exc!r}")
                if attempt < retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                raise RuntimeError(f"{context} failed: {exc}") from exc

        if last_error is not None:
            raise RuntimeError(f"{context} failed: {last_error}")
        raise RuntimeError(f"{context} failed.")

    async def _get_current_party_context(self):
        self._debug("_get_current_party_context called")
        handler = MatchDetectionHandler()
        if not await handler.puuid_shard_header_getter():
            self._debug("puuid_shard_header_getter returned False")
            return None

        self._local_self_puuid = str(handler.user_puuid or self._local_self_puuid or "").strip()
        presence_context = self._build_self_presence_context(handler)
        if presence_context is not None:
            self._debug(f"using self presence context {presence_context}")
            return presence_context

        session = SharedSession.get()
        party_id = ""
        try:
            party_player = await self._request_json(
                session,
                "GET",
                f"https://glz-{handler.region}-1.{handler.shard}.a.pvp.net/parties/v1/players/{handler.user_puuid}",
                "Party player request",
                headers=handler.match_id_header,
            )
            party_id = str(party_player.get("CurrentPartyID", "") or "").strip()
            if party_id:
                self._local_party_cache["party_id"] = party_id
        except RuntimeError as exc:
            self._debug(f"Party player request failed, checking websocket cache: {exc}")
            party_id = str(self._local_party_cache.get("party_id", "") or "").strip()

        if not party_id:
            self._debug("no local party_id available from API or websocket cache")
            return self._build_cached_party_context(handler)

        try:
            party_data = await self._request_json(
                session,
                "GET",
                f"https://glz-{handler.region}-1.{handler.shard}.a.pvp.net/parties/v1/parties/{party_id}",
                "Party request",
                headers=handler.match_id_header,
            )
        except RuntimeError as exc:
            self._debug(f"Party request failed, checking websocket cache: {exc}")
            return self._build_cached_party_context(handler, party_id=party_id)

        matchmaking_data = party_data.get("MatchmakingData") or {}
        state = str(party_data.get("State", "") or "").strip().upper()
        queue_id = str(matchmaking_data.get("QueueID", "") or "").strip()
        self._local_party_cache.update(
            {
                "party_id": party_id,
                "queue_id": queue_id,
                "state": state,
                "is_queueing": bool(queue_id and state in PARTY_QUEUEING_STATES),
            }
        )

        context = {
            "headers": handler.match_id_header,
            "region": handler.region,
            "shard": handler.shard,
            "party_id": party_id,
            "queue_id": queue_id,
            "is_queueing": bool(queue_id and state in PARTY_QUEUEING_STATES),
            "state": state,
        }
        self._debug(f"_get_current_party_context returning {context}")
        return context

    async def _post_party_action(self, context, path, request_name, json_body=None):
        session = SharedSession.get()
        url = f"https://glz-{context['region']}-1.{context['shard']}.a.pvp.net{path}"
        self._debug(f"{request_name} POST {url} json_body={json_body}")
        return await self._request_json(
            session,
            "POST",
            url,
            request_name,
            headers=context["headers"],
            json_body=json_body,
        )

    async def _request_json(self, session, method, url, context, headers=None, json_body=None, retries=3):
        for attempt in range(retries):
            self._debug(f"{context} {method} attempt {attempt + 1}/{retries} url={url}")
            async with session.request(method, url, headers=headers, json=json_body) as resp:
                self._debug(f"{context} response status={resp.status}")
                if resp.status == 429 and attempt < retries - 1:
                    retry_after = self._get_retry_after_seconds(resp)
                    self._debug(f"{context} rate limited retry_after={retry_after}")
                    await asyncio.sleep(retry_after)
                    continue
                return await self._read_json_response(resp, context)

    async def _read_json_response(self, resp, context, friendly_message=None):
        body = await resp.text()
        self._debug(f"{context} body={self._format_response_preview(body, limit=320)}")

        if resp.status >= 400:
            if friendly_message:
                raise RuntimeError(friendly_message)
            preview = self._format_response_preview(body)
            raise RuntimeError(f"{context} failed with HTTP {resp.status}: {preview}")

        if not body.strip():
            return {}

        try:
            return json.loads(body)
        except json.JSONDecodeError:
            preview = self._format_response_preview(body)
            raise RuntimeError(f"{context} returned invalid JSON: {preview}")

    def _get_retry_after_seconds(self, resp, default_seconds=2):
        retry_after = resp.headers.get("Retry-After")
        if retry_after is None:
            return default_seconds

        try:
            return max(1, math.ceil(float(retry_after)))
        except (TypeError, ValueError):
            return default_seconds

    def _format_response_preview(self, body, limit=180):
        preview = " ".join(str(body or "").split())
        if len(preview) > limit:
            return f"{preview[:limit]}..."
        return preview or "<empty>"

    def _format_local_client_error(self, exc):
        message = str(exc or "").strip()
        lowered = message.lower()
        if "refused" in lowered or "cannot connect" in lowered or "not ready" in lowered:
            return (
                "Riot's local API isn't ready yet. Wait for Riot Client to finish starting, "
                "then try Queue Snipe again."
            )
        return message or "Riot's local API isn't ready yet."

    def _format_chat_not_ready_message(self, resp):
        if resp.status != 503:
            return None
        return "Riot chat isn't connected yet. Wait a few seconds, then try Queue Snipe again."

    def _build_cached_party_context(self, handler, party_id=""):
        cached_party_id = str(party_id or self._local_party_cache.get("party_id", "") or "").strip()
        if not cached_party_id:
            return None

        queue_id = str(self._local_party_cache.get("queue_id", "") or "").strip()
        state = str(self._local_party_cache.get("state", "") or "").strip().upper()
        context = {
            "headers": handler.match_id_header,
            "region": handler.region,
            "shard": handler.shard,
            "party_id": cached_party_id,
            "queue_id": queue_id,
            "is_queueing": bool(self._local_party_cache.get("is_queueing")) or bool(queue_id and state in PARTY_QUEUEING_STATES),
            "state": state,
        }
        self._debug(f"using cached local party context {context}")
        return context

    def _build_self_presence_context(self, handler):
        local_puuid = str(handler.user_puuid or self._local_self_puuid or "").strip()
        if not local_puuid:
            return None

        presence = self.party_tracker.get_presence(puuid=local_puuid)
        if not isinstance(presence, dict):
            return None

        party_id = str(presence.get("party_id", "") or "").strip()
        if not party_id:
            return None

        queue_id = str(presence.get("queue_id", "") or "").strip()
        state = str(presence.get("party_state", "") or "").strip().upper()
        return {
            "headers": handler.match_id_header,
            "region": handler.region,
            "shard": handler.shard,
            "party_id": party_id,
            "queue_id": queue_id,
            "is_queueing": bool(presence.get("is_queueing")) or bool(queue_id and state in PARTY_QUEUEING_STATES),
            "state": state,
        }

    def _extract_party_id_from_uri(self, uri):
        marker = "/parties/v1/parties/"
        if marker not in uri:
            return ""
        suffix = uri.split(marker, 1)[1]
        return suffix.split("/", 1)[0].strip()

    def _fallback_friends_from_presence(self):
        local_puuid = ""
        try:
            handler = LockfileHandler()
            local_puuid = str(handler.puuid or "").strip()
        except Exception:
            local_puuid = ""

        fallback_friends = [
            friend
            for friend in self.party_tracker.get_known_friends()
            if str(friend.get("puuid", "") or "").strip() and str(friend.get("puuid", "") or "").strip() != local_puuid
        ]
        self._debug(f"presence fallback friend count={len(fallback_friends)}")
        for index, friend in enumerate(fallback_friends[:5]):
            self._debug(
                f"presence fallback[{index}] display_name={friend.get('display_name')} "
                f"puuid={friend.get('puuid')} pid={friend.get('pid')}"
            )
        return fallback_friends

    def _is_expected_leave_error(self, exc):
        message = str(exc or "").lower()
        return "queue" in message and ("not" in message or "resource not found" in message or "invalid party state" in message)

    def _report_status(self, message):
        if self.status_callback:
            try:
                self.status_callback(message)
            except Exception:
                pass
        print(message)

    def _cancel_sync_task(self):
        if self._sync_task is not None and not self._sync_task.done():
            self._sync_task.cancel()
        self._sync_task = None
        self._resync_requested = False
        self._seed_presence_requested = False
