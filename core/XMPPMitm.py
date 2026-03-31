import asyncio
import json
import ssl
from datetime import datetime

from core.party_tracker import PartyTracker

"""This class creates connections to the previously in ConfigMITM modified chat-servers and logs the communication between that
    First it creates a local socket to listen for incoming requests on port 35478 (the previously modified port) to determine which chat server to connect to
    As soon as a request comes in, it saves the host it now communicates on (ipv4LocalHost) and finds the relevant chat socket in the mappings to connect to it
    After connecting to the chat socket, it starts logging all the incoming and outgoing traffic"""


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
        self._shutting_down = False

    async def start(self) -> None:
        """Starts the XMPP server to listen to all hosts on port 35478 -> None"""

        print("Starting XMPP server...")
        self.server = await asyncio.start_server(self.handle_client, '0.0.0.0', self.port)
        print('Started XMPP Server!')
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

    async def handle_client(self, client_reader: object, client_writer: object) -> None:
        """Handles incoming connections by connecting to the according chat socket -> None"""

        if self._shutting_down:
            client_writer.close()
            await self._wait_for_close(client_writer)
            return

        server_addr = client_writer.get_extra_info('sockname')
        ipv4LocalHost = server_addr[0]
        peer_addr = client_writer.get_extra_info('peername')
        mapping = next((m for m in self.config_mitm.affinityMappings if m['localHost'] == ipv4LocalHost), None)
        if mapping is None:
            print(f"[XMPPMitm] Unknown host local={ipv4LocalHost} peer={peer_addr}")
            await self.log_message(f'Unknown host {ipv4LocalHost}')
            client_writer.close()
            await client_writer.wait_closed()
            return

        self.socketID += 1
        current_socket_id = self.socketID
        await self.log_message(json.dumps({
            'type': 'open-valorant',
            'time': datetime.now().timestamp(),
            'host': mapping['riotHost'],
            'port': mapping['riotPort'],
            'socketID': current_socket_id,
        }))
        print(
            f"[XMPPMitm] socket={current_socket_id} accepted local={ipv4LocalHost} peer={peer_addr} "
            f"mapped_host={mapping['riotHost']} mapped_port={mapping['riotPort']}"
        )

        try:
            riot_reader, riot_writer = await asyncio.open_connection(
                mapping['riotHost'], mapping['riotPort'], ssl=ssl.create_default_context()
            )
        except Exception as exc:
            await self.log_message(json.dumps({
                'type': 'xmpp-connect-error',
                'time': datetime.now().timestamp(),
                'host': mapping['riotHost'],
                'port': mapping['riotPort'],
                'socketID': current_socket_id,
                'error': str(exc),
            }))
            print(f"[XMPPMitm] socket={current_socket_id} connect failed error={exc}")
            client_writer.close()
            await client_writer.wait_closed()
            return

        print(f"[XMPPMitm] socket={current_socket_id} connected to riot chat")

        outgoing_task = asyncio.create_task(
            self.transfer_data(client_reader, riot_writer, current_socket_id, 'outgoing')
        )
        incoming_task = asyncio.create_task(
            self.transfer_data(riot_reader, client_writer, current_socket_id, 'incoming')
        )
        self._socket_tasks[current_socket_id] = {
            'outgoing': outgoing_task,
            'incoming': incoming_task,
        }

        results = await asyncio.gather(
            outgoing_task,
            incoming_task,
            return_exceptions=True,
        )
        self._consume_task_results(results)

        self.party_tracker.clear_socket(current_socket_id)
        self._socket_tasks.pop(current_socket_id, None)
        await self._close_socket_pair(client_writer, riot_writer)
        print(f"[XMPPMitm] socket={current_socket_id} closed")
        await self._safe_log_message(json.dumps({
            'type': 'close-valorant',
            'time': datetime.now().timestamp(),
            'socketID': current_socket_id,
        }))

    async def transfer_data(self, reader=object, writer=object, socket_id=int, direction=str) -> None:
        """Transfers the data into the necessary direction"""

        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    self._signal_stream_end(writer, socket_id, direction)
                    break
                writer.write(data)
                await writer.drain()
                decoded_text = data.decode(errors='ignore')
                if direction == 'incoming':
                    try:
                        updated = self.party_tracker.feed_chunk(socket_id, decoded_text)
                        if updated:
                            print(f"[XMPPMitm] socket={socket_id} presence cache updated")
                    except Exception as exc:
                        print(f"[XMPPMitm] socket={socket_id} presence parse error={exc!r}")
                await self._safe_log_message(json.dumps({
                    'type': direction,
                    'time': datetime.now().timestamp(),
                    'data': decoded_text,
                    'socketID': socket_id,
                }))
        except asyncio.CancelledError:
            raise
        except (ssl.SSLError, ConnectionError, OSError, asyncio.IncompleteReadError):
            print(f"[XMPPMitm] socket={socket_id} {direction} stream closed")
        except Exception as exc:
            print(f"[XMPPMitm] socket={socket_id} {direction} unexpected transfer error={exc!r}")

    async def log_message(self, message=str) -> None:
        """Logs the messages"""

        await self.log_stream.write(message + '\n')

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
