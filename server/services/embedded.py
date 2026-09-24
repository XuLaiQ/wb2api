"""Lifecycle manager for the embedded Go gateway.

The gateway and the management API use different runtimes, so they remain two
processes. They are owned by one application entrypoint and share the same
configuration, account directory and data volume.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from .. import config

logger = logging.getLogger(__name__)

_process: asyncio.subprocess.Process | None = None
_monitor: asyncio.Task | None = None
_log_handle = None
_lock = asyncio.Lock()
_stopping = False


def _command() -> tuple[str, ...]:
    binary = config.WB2API_BINARY
    if not binary.is_file():
        raise FileNotFoundError(
            f'未找到内置 Go 网关 {binary}。请先执行 `go -C gateway build -o {binary.name} ./cmd/server`。'
        )
    return (str(binary), '-config', str(config.UPSTREAM_CONFIG))


def running() -> bool:
    return _process is not None and _process.returncode is None


async def start() -> None:
    """Start the Go gateway once and monitor unexpected exits."""
    global _process, _monitor, _log_handle, _stopping
    async with _lock:
        if running():
            return
        command = _command()
        config.WB2API_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        _log_handle = config.WB2API_LOG_FILE.open('a', encoding='utf-8', buffering=1)
        _stopping = False
        try:
            _process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(config.ROOT),
                env=dict(os.environ),
                stdout=_log_handle,
                stderr=asyncio.subprocess.STDOUT,
            )
        except Exception:
            _log_handle.close()
            _log_handle = None
            raise
        _monitor = asyncio.create_task(_watch(_process))
        logger.info('内置 Go 网关已启动（pid=%s，配置=%s）', _process.pid, config.UPSTREAM_CONFIG)


async def _watch(process: asyncio.subprocess.Process) -> None:
    global _process, _monitor, _log_handle
    code = await process.wait()
    handle = _log_handle
    _log_handle = None
    if handle is not None:
        handle.close()
    if _process is process:
        _process = None
    if _stopping:
        return
    logger.error('内置 Go 网关已退出（exit=%s），1 秒后自动重启', code)
    await asyncio.sleep(1)
    try:
        await start()
    except Exception:
        logger.exception('内置 Go 网关自动重启失败')


async def stop() -> None:
    """Stop the child process and its monitor during application shutdown."""
    global _process, _monitor, _log_handle, _stopping
    async with _lock:
        _stopping = True
        process = _process
        monitor = _monitor
        _process = None
        _monitor = None
        if monitor is not None and monitor is not asyncio.current_task():
            monitor.cancel()
        if process is not None and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=8)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        if _log_handle is not None:
            _log_handle.close()
            _log_handle = None
        if monitor is not None and monitor is not asyncio.current_task():
            try:
                await monitor
            except asyncio.CancelledError:
                pass
        logger.info('内置 Go 网关已停止')


async def restart() -> tuple[bool, str]:
    """Restart the embedded gateway after a config or account change."""
    try:
        await stop()
        await start()
        return True, '内置 workbuddy2api 已重启'
    except Exception as exc:  # noqa: BLE001
        logger.exception('内置 Go 网关重启失败')
        return False, f'内置 workbuddy2api 重启失败：{exc}'
