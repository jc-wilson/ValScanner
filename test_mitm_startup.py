"""Local socket regressions; never launch Riot or contact upstream services."""

import asyncio
import errno
import socket
import unittest
from unittest.mock import AsyncMock, patch

from core.mitm import RiotMitmService
from core.startup_coordinator import AppStartupCoordinator


def occupy_port():
    listener = socket.socket()
    if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    listener.bind(('0.0.0.0', 0))
    listener.listen()
    return listener


class MitmStartupTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.certificate = patch('core.mitm.get_localhost_server_ssl_context', return_value=None)
        self.certificate.start()
        self.addCleanup(self.certificate.stop)

    async def test_occupied_ports_use_actual_bound_ports_for_config_and_launch(self):
        with occupy_port() as http, occupy_port() as chat:
            service = RiotMitmService(
                http_port=http.getsockname()[1], xmpp_port=chat.getsockname()[1],
            )
            try:
                await service.start()
                self.assertNotEqual(service.http_port, http.getsockname()[1])
                self.assertNotEqual(service.xmpp_port, chat.getsockname()[1])
                config = service.config_mitm
                self.assertEqual(service.http_port, config.server.server_address[1])
                self.assertEqual(service.xmpp_port, service.xmpp_mitm.server.sockets[0].getsockname()[1])
                data = config.patch_client_config({
                    'chat.affinities': {'eu': 'chat.example.invalid'},
                    'chat.host': 'chat.example.invalid', 'chat.port': 5223,
                })
                self.assertEqual(data['chat.port'], service.xmpp_port)
                with patch('core.mitm.is_riot_client_running', AsyncMock(return_value=False)), \
                     patch.object(type(service.riot_client_path), 'exists', return_value=True), \
                     patch('core.mitm.start_riot_client', AsyncMock()) as launch:
                    await service.ensure_riot_started()
                    self.assertEqual(launch.await_args.args[2], service.http_port)
                original_server = service.xmpp_mitm.server
                await service.start()
                self.assertIs(service.xmpp_mitm.server, original_server)
            finally:
                await service.stop()
            self.assertFalse(service._started)

    async def test_two_instances_can_start_and_stop_independently(self):
        first = RiotMitmService(http_port=0, xmpp_port=0)
        second = None
        try:
            await first.start()
            second = RiotMitmService(http_port=first.http_port, xmpp_port=first.xmpp_port)
            await second.start()
            self.assertNotEqual(first.http_port, second.http_port)
            self.assertNotEqual(first.xmpp_port, second.xmpp_port)
            await second.stop()
            self.assertTrue(first.xmpp_mitm.server.is_serving())
        finally:
            if second:
                await second.stop()
            await first.stop()

    async def test_failure_releases_partial_http_listener_and_allows_retry(self):
        service = RiotMitmService(http_port=0, xmpp_port=0)
        with patch('core.XMPPMitm.asyncio.start_server', AsyncMock(side_effect=PermissionError(errno.EACCES, 'denied'))) as bind:
            with self.assertRaises(PermissionError):
                await asyncio.wait_for(service.start(), timeout=3)
            self.assertEqual(bind.await_count, 1)
        self.assertIsNone(service.config_mitm)
        self.assertIsNone(service.xmpp_mitm)
        self.assertIsNone(service._log_stream)
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', service.http_port))
        try:
            await service.start()
            self.assertTrue(service._started)
        finally:
            await service.stop()

    async def test_windows_asyncio_address_error_falls_back(self):
        service = RiotMitmService(http_port=0, xmpp_port=0)
        real_start = asyncio.start_server
        calls = 0

        async def bind(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                # asyncio can rebuild OSError with errno=10048 and no winerror.
                raise OSError(10048, 'address already in use')
            return await real_start(*args, **kwargs)

        try:
            with patch('core.XMPPMitm.asyncio.start_server', side_effect=bind):
                await service.start()
            self.assertEqual(calls, 2)
            self.assertGreater(service.xmpp_port, 0)
        finally:
            await service.stop()

    async def test_startup_failures_disable_social_features_without_launching_riot(self):
        for method in ('initialize', 'ensure_riot_with_mitm', 'restart_riot_client'):
            with self.subTest(method=method):
                coordinator = AppStartupCoordinator()
                coordinator.mitm_service.start = AsyncMock(side_effect=OSError(10048, 'occupied'))
                coordinator.mitm_service.stop = AsyncMock()
                coordinator.mitm_service.ensure_riot_started = AsyncMock()
                coordinator.mitm_service.restart_riot_client = AsyncMock()
                with patch('core.startup_coordinator.LockfileHandler.lockfile_data_function', AsyncMock(return_value=False)), \
                     patch('core.startup_coordinator.is_riot_or_valorant_running', AsyncMock(return_value=False)):
                    self.assertFalse(await getattr(coordinator, method)())
                self.assertFalse(coordinator.party_detection_enabled)
                self.assertFalse(coordinator.restart_required)
                self.assertIn('unavailable', coordinator.last_status)
                coordinator.mitm_service.ensure_riot_started.assert_not_awaited()
                coordinator.mitm_service.restart_riot_client.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
