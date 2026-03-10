import asyncio
import json
import subprocess
import threading
from pathlib import Path

from core.ConfigMITM import ConfigMITM
from core.SharedValues import host, port, xmppPort
from core.XMPPMitm import XmppMITM

DEFAULT_RIOT_CLIENT_PATH = Path(r"C:\Riot Games\Riot Client\RiotClientServices.exe")
TRACKED_PROCESS_NAMES = [
    "RiotClientServices.exe",
    "RiotClientUx.exe",
    "VALORANT.exe",
    "VALORANT-Win64-Shipping.exe",
]


class InMemoryLogStream:
    def __init__(self, max_entries: int = 5000):
        self.max_entries = max_entries
        self.entries = []
        self._lock = asyncio.Lock()
        self._closed = False

    async def write(self, message: str) -> None:
        if self._closed:
            return
        async with self._lock:
            self.entries.append(message)
            if len(self.entries) > self.max_entries:
                del self.entries[:-self.max_entries]

    async def flush(self) -> None:
        return

    async def close(self) -> None:
        self._closed = True


async def is_process_running(process_name: str) -> bool:
    try:
        proc = await asyncio.create_subprocess_shell(
            f'tasklist /FI "IMAGENAME eq {process_name}" /NH',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return process_name.encode() in stdout
    except Exception:
        return False


async def is_riot_client_running() -> bool:
    return await is_process_running("RiotClientServices.exe")


async def get_running_game_processes():
    running = []
    for process_name in TRACKED_PROCESS_NAMES:
        if await is_process_running(process_name):
            running.append(process_name)
    return running


async def is_riot_or_valorant_running() -> bool:
    return bool(await get_running_game_processes())


async def start_riot_client(riot_client_path=str, mitm_host=str, http_port=int, wait=False):
    """Starts riot client on the given `host` and `http_port`."""

    command = (
        f'"{riot_client_path}" --client-config-url="http://{mitm_host}:{http_port}" '
        f'--launch-product=valorant --launch-patchline=live'
    )
    process = await asyncio.create_subprocess_shell(command)
    print("Riot Client started!")
    if wait:
        await process.wait()
        print("Riot client closed!")
    return process


class RiotMitmService:
    def __init__(self, riot_client_path=None, mitm_host=host, http_port=port, xmpp_port=xmppPort):
        self.riot_client_path = Path(riot_client_path) if riot_client_path else DEFAULT_RIOT_CLIENT_PATH
        self.host = mitm_host
        self.http_port = http_port
        self.xmpp_port = xmpp_port
        self.config_mitm = None
        self.xmpp_mitm = None
        self._config_thread = None
        self._log_stream = None
        self._started = False
        self._owns_running_session = False
        self._background_hold = False

    async def start(self):
        if self._started:
            return

        self._log_stream = InMemoryLogStream()
        await self._log_stream.write(json.dumps({
            "type": "ValScanner-xmpp-logger-python",
            "version": "1.0.0",
        }) + "\n")

        self.config_mitm = ConfigMITM(host=self.host, http_port=self.http_port, xmpp_port=self.xmpp_port)
        self._config_thread = threading.Thread(target=self.config_mitm.start, daemon=True)
        self._config_thread.start()

        self.xmpp_mitm = XmppMITM(self.xmpp_port, self.config_mitm, self._log_stream)
        await self.xmpp_mitm.start()
        self._started = True

    async def stop(self):
        if self.xmpp_mitm is not None:
            await self.xmpp_mitm.stop()
            self.xmpp_mitm = None

        if self.config_mitm is not None:
            self.config_mitm.stop()
            self.config_mitm = None

        if self._log_stream is not None:
            await self._log_stream.flush()
            await self._log_stream.close()
            self._log_stream = None

        self._started = False
        self._owns_running_session = False
        self._background_hold = False

    def can_reuse_active_session(self) -> bool:
        return self._started and self._owns_running_session

    def mark_background_hold(self, enabled: bool) -> None:
        self._background_hold = bool(enabled)

    async def ensure_riot_started(self):
        if await is_riot_client_running():
            return False

        if not self.riot_client_path.exists():
            raise FileNotFoundError(f"Riot Client not found at {self.riot_client_path}")

        await start_riot_client(str(self.riot_client_path), self.host, self.http_port, wait=False)
        self._owns_running_session = True
        self._background_hold = False
        return True

    async def kill_game_processes(self):
        killed = []
        for process_name in TRACKED_PROCESS_NAMES:
            proc = await asyncio.create_subprocess_shell(
                f'taskkill /F /IM "{process_name}"',
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode == 0:
                killed.append(process_name)
        return killed

    async def restart_riot_client(self):
        await self.kill_game_processes()
        await asyncio.sleep(2)
        self._owns_running_session = False
        self._background_hold = False
        return await self.ensure_riot_started()


async def main():
    service = RiotMitmService()
    try:
        if await is_riot_or_valorant_running():
            print("Riot or Valorant is running, please close it before running this tool")
            return

        await service.start()
        print("Starting Riot Client...")
        await start_riot_client(str(DEFAULT_RIOT_CLIENT_PATH), host, port, wait=True)
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
