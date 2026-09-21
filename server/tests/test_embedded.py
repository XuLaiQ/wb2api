"""Regression tests for the unified FastAPI -> Go gateway lifecycle."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server import config  # noqa: E402
from server.services import embedded  # noqa: E402


class _FakeProcess:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.returncode = None
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def kill(self) -> None:
        self.returncode = -9

    async def wait(self) -> int:
        while self.returncode is None:
            await asyncio.sleep(0.01)
        return self.returncode


class EmbeddedGatewayTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await embedded.stop()
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.binary = root / 'wb2api'
        self.binary.write_bytes(b'gateway')
        self.config_path = root / 'config.json'
        self.config_path.write_text('{}', encoding='utf-8')
        self.log_path = root / 'gateway.log'
        self.patches = [
            mock.patch.object(config, 'ROOT', root),
            mock.patch.object(config, 'WB2API_BINARY', self.binary),
            mock.patch.object(config, 'UPSTREAM_CONFIG', self.config_path),
            mock.patch.object(config, 'WB2API_LOG_FILE', self.log_path),
        ]
        for patcher in self.patches:
            patcher.start()

    async def asyncTearDown(self) -> None:
        await embedded.stop()
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmp.cleanup()

    async def test_start_owns_gateway_process(self) -> None:
        process = _FakeProcess(101)
        with mock.patch.object(
            asyncio, 'create_subprocess_exec', new=mock.AsyncMock(return_value=process),
        ) as spawn:
            await embedded.start()

        spawn.assert_awaited_once()
        args = spawn.await_args.args
        self.assertEqual(args[0], str(self.binary))
        self.assertEqual(args[-2:], ('-config', str(self.config_path)))
        self.assertTrue(embedded.running())

    async def test_restart_replaces_gateway_process(self) -> None:
        processes = [_FakeProcess(101), _FakeProcess(102)]
        with mock.patch.object(
            asyncio, 'create_subprocess_exec',
            new=mock.AsyncMock(side_effect=processes),
        ):
            await embedded.start()
            ok, message = await embedded.restart()

        self.assertTrue(ok, message)
        self.assertTrue(processes[0].terminated)
        self.assertTrue(embedded.running())
        self.assertEqual(processes[1].pid, 102)


if __name__ == '__main__':
    unittest.main()
