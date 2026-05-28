import json
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
import urllib3

from core.SharedValues import localhostChatHost

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

"""This class crates an HTTP proxy to intercept the communication between the riot client and the riot server
    For that it creates a HTTP server using HTTPServer which is using the IP onto which the riot client was modified (127.0.0.1:35479)
    It then receives the request sent by the riot client to the riot server (first two are update requests), proxies them to their original goal and sends them back to the client
    After logging in, the riot client sends a request to get the chat settings, in which we find  the relevant hosts and:

    - Change the chat.port to 35478
    - Change the chat.host and affinities to a localhost DNS name with a valid certificate

    We then send back the modified response back to the riot client"""


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
        self.server = HTTPServer((self.host, self.http_port), handler)

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

        if handler.path.startswith('/api/v1/config/player') and response.status_code == 200:
            data = self.patch_client_config(json.loads(response.text))
            if 'chat.affinities' in data:
                handler.wfile.write(json.dumps(data).encode('utf-8'))
            else:
                handler.wfile.write(response.content)
        else:
            handler.wfile.write(response.content)

    def patch_client_config(self, data: dict) -> dict:
        if 'chat.affinities' not in data:
            return data

        original_host = data.get('chat.host')
        original_port = data.get('chat.port')
        if original_host is None and isinstance(data.get('chat.affinities'), dict):
            original_host = next(iter(data['chat.affinities'].values()), None)

        if original_host is not None and original_port is not None:
            self.upstream_chat_host = original_host
            self.upstream_chat_port = original_port
            self.affinityMappings = [{
                'localHost': localhostChatHost,
                'riotHost': original_host,
                'riotPort': original_port,
            }]

        for region in list(data['chat.affinities'].keys()):
            data['chat.affinities'][region] = localhostChatHost

        data['chat.port'] = self.xmpp_port
        data['chat.host'] = localhostChatHost
        return data

    def get_upstream_chat_endpoint(self):
        if self.upstream_chat_host is None or self.upstream_chat_port is None:
            return None, None
        return self.upstream_chat_host, self.upstream_chat_port
