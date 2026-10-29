import base64
import errno
import json
import socket
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
import urllib3

from core.SharedValues import localhostChatHost

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

GEO_PAS_URL = 'https://riot-geo.pas.si.riotgames.com/pas/v1/service/chat'

"""This class crates an HTTP proxy to intercept the communication between the riot client and the riot server
    For that it creates a HTTP server using HTTPServer which is using the IP onto which the riot client was modified (127.0.0.1:35479)
    It then receives the request sent by the riot client to the riot server (first two are update requests), proxies them to their original goal and sends them back to the client
    After logging in, the riot client sends a request to get the chat settings, in which we find  the relevant hosts and:

    - Change the chat.port to 35478
    - Change the chat.host and affinities to a localhost DNS name with a valid certificate

    We then send back the modified response back to the riot client"""


class LocalHTTPServer(HTTPServer):
    # HTTPServer's SO_REUSEADDR can let two Windows instances share a live port.
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class ConfigMITM:
    def __init__(self, host=str, http_port=int, xmpp_port=int) -> None:
        """Initiates the attributes"""

        self.host = host
        self.http_port = http_port
        self.xmpp_port = xmpp_port
        self._affinityMappingID = 0
        self.affinityMappings = []
        self.upstream_chat_host = None
        self.upstream_chat_port = None
        handler = partial(self.RequestHandler, self)
        try:
            self.server = LocalHTTPServer((self.host, self.http_port), handler)
        except OSError as exc:
            if exc.errno not in (errno.EADDRINUSE, 10048, 10013) and getattr(exc, 'winerror', None) not in (10048, 10013):
                raise
            self.server = LocalHTTPServer((self.host, 0), handler)
        self.http_port = self.server.server_address[1]

    def start(self) -> None:
        """Starts the server -> None"""

        print(f'Starting Riot Client interceptor on {self.host}:{self.http_port}...')
        self.server.serve_forever()

    def stop(self) -> None:
        """Stops the server (not actually using this ever) -> None"""
        self.server.shutdown()
        self.server.server_close()
        print('Server has been stopped.')

    class RequestHandler(BaseHTTPRequestHandler):
        """The request handler class"""

        def __init__(self, config_mitm, *args, **kwargs) -> None:
            """Gets the necessary attributes from BaseHTTPRequestHandler"""

            self.config_mitm = config_mitm
            super().__init__(*args, **kwargs)

        def do_GET(self) -> None:
            """Handles the GET requests"""

            self.config_mitm.handle_request(self)

        def do_POST(self) -> None:
            """Handles the Post requests"""

            self.config_mitm.handle_request(self)

        def log_message(self, format, *args):
            return

    def handle_request(self, handler=object) -> None:
        """Handles the incoming requests"""

        print(f"Request: {handler.log_date_time_string()} {handler.command} {handler.path}")
        headers = {k: v for k, v in handler.headers.items() if k.lower() != 'host'}
        try:
            response = requests.request(
                method=handler.command,
                url=f'https://clientconfig.rpg.riotgames.com{handler.path}',
                headers=headers,
                verify=False,
                timeout=10,
            )
        except requests.RequestException as exc:
            handler.send_response(502)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
            return

        handler.send_response(response.status_code)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()

        if response.status_code == 200:
            try:
                data = json.loads(response.text)
            except (TypeError, json.JSONDecodeError):
                handler.wfile.write(response.content)
                return

            patched = self.patch_client_config(data, headers=headers)
            if patched is not data or 'chat.affinities' in patched:
                handler.wfile.write(json.dumps(patched).encode('utf-8'))
                return

        handler.wfile.write(response.content)

    def patch_client_config(self, data: dict, headers: dict | None = None) -> dict:
        if 'chat.affinities' not in data:
            return data

        affinity_hosts = []
        if isinstance(data.get('chat.affinities'), dict):
            affinity_hosts = [
                host for host in data['chat.affinities'].values()
                if host
            ]

        original_host = data.get('chat.host')
        if original_host is None and affinity_hosts:
            original_host = affinity_hosts[0]
        original_port = data.get('chat.port')

        affinity_host = self._get_affinity_chat_host(data, headers or {})
        if affinity_host:
            original_host = affinity_host

        if original_host is not None and original_port is not None:
            self.upstream_chat_host = original_host
            self.upstream_chat_port = original_port
            self.affinityMappings = [{
                'localHost': localhostChatHost,
                'riotHost': original_host,
                'riotPort': original_port,
            }]
            print(
                f"[ConfigMITM] chat upstream={self.upstream_chat_host}:{self.upstream_chat_port} "
                f"original_chat_host={data.get('chat.host')} affinities={affinity_hosts}"
            )

        for region in list(data['chat.affinities'].keys()):
            data['chat.affinities'][region] = localhostChatHost

        data['chat.port'] = self.xmpp_port
        data['chat.host'] = localhostChatHost
        return data

    def _get_affinity_chat_host(self, data: dict, headers: dict) -> str | None:
        if not data.get('chat.affinity.enabled'):
            return None
        affinities = data.get('chat.affinities')
        if not isinstance(affinities, dict):
            return None

        authorization = None
        for key, value in headers.items():
            if str(key).lower() == 'authorization':
                authorization = value
                break
        if not authorization:
            return None

        try:
            response = requests.get(
                GEO_PAS_URL,
                headers={'Authorization': authorization},
                verify=False,
                timeout=10,
            )
            response.raise_for_status()
            jwt_payload = response.text.split('.')[1]
            jwt_payload += '=' * (-len(jwt_payload) % 4)
            payload = json.loads(base64.urlsafe_b64decode(jwt_payload.encode('utf-8')).decode('utf-8'))
            affinity = payload.get('affinity')
            if affinity in affinities:
                print(f"[ConfigMITM] affinity={affinity} upstream={affinities[affinity]}")
                return affinities[affinity]
        except Exception as exc:
            print(f"[ConfigMITM] affinity lookup failed, using default chat server: {exc}")
        return None

    def get_upstream_chat_endpoint(self):
        if self.upstream_chat_host is None or self.upstream_chat_port is None:
            return None, None
        return self.upstream_chat_host, self.upstream_chat_port
