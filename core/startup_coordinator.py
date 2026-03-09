import asyncio

from core.local_api import LockfileHandler
from core.mitm import (
    RiotMitmService,
    get_running_game_processes,
    is_riot_or_valorant_running,
)


class AppStartupCoordinator:
    def __init__(self, status_callback=None, retry_interval=5):
        self.status_callback = status_callback
        self.retry_interval = retry_interval
        self.mitm_service = RiotMitmService()
        self.restart_required = False
        self.party_detection_enabled = True
        self.last_status = "Initializing..."
        self.running_processes = []

    def set_status(self, status):
        self.last_status = status
        if self.status_callback:
            self.status_callback(status)

    async def refresh_running_processes(self):
        self.running_processes = await get_running_game_processes()
        return self.running_processes

    async def initialize(self):
        lockfile_handler = LockfileHandler()
        riot_ready = await lockfile_handler.lockfile_data_function(retries=1)
        already_running = await is_riot_or_valorant_running() or riot_ready

        if already_running:
            await self.refresh_running_processes()
            self.restart_required = True
            self.party_detection_enabled = False
            self.set_status("Party detection requires a Riot Client restart.")
            return False

        self.restart_required = False
        self.party_detection_enabled = True
        self.set_status("Starting party detection...")
        await self.mitm_service.start()
        await self.ensure_riot_started()
        return True

    async def ensure_riot_started(self):
        try:
            started = await self.mitm_service.ensure_riot_started()
        except FileNotFoundError as exc:
            self.set_status(str(exc))
            return False

        if started:
            self.set_status("Waiting for Riot Client and Valorant...")
        else:
            self.set_status("Waiting for Valorant session...")
        return True

    async def restart_riot_client(self):
        self.set_status("Restarting Riot Client and Valorant for party detection...")
        await self.mitm_service.start()
        await self.mitm_service.restart_riot_client()
        self.restart_required = False
        self.party_detection_enabled = True
        self.running_processes = []
        self.set_status("Waiting for Riot Client and Valorant...")
        return True

    async def disable_party_detection(self):
        self.restart_required = False
        self.party_detection_enabled = False
        self.running_processes = []
        await self.mitm_service.stop()
        self.set_status("Party detection disabled for this session.")

    async def wait_before_retry(self):
        await asyncio.sleep(self.retry_interval)

    async def shutdown(self):
        await self.mitm_service.stop()