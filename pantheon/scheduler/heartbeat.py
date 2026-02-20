"""Heartbeat scheduler — periodic task runner from HEARTBEAT.md."""

from __future__ import annotations

import asyncio
import logging

from pantheon.config import settings
from pantheon.core.conversation import Conversation

log = logging.getLogger(__name__)


class HeartbeatScheduler:
    """Runs HEARTBEAT.md checklist on a configurable interval."""

    def __init__(self, conversation: Conversation):
        self.conversation = conversation
        self.interval_minutes = settings.heartbeat_interval_minutes
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        """Start the heartbeat loop as a background task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        log.info("Heartbeat started (every %dm)", self.interval_minutes)

    def stop(self) -> None:
        """Stop the heartbeat loop."""
        self._running = False
        if self._task:
            self._task.cancel()

    async def _loop(self) -> None:
        """Main heartbeat loop."""
        while self._running:
            try:
                await asyncio.sleep(self.interval_minutes * 60)
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Heartbeat tick failed: %s", e, exc_info=True)

    async def _tick(self) -> None:
        """Execute one heartbeat tick."""
        heartbeat_file = settings.schedules_dir / "HEARTBEAT.md"
        if not heartbeat_file.exists():
            log.warning("HEARTBEAT.md not found, skipping tick")
            return

        content = heartbeat_file.read_text(encoding="utf-8")
        prompt = (
            "HEARTBEAT CHECK. Read and follow this checklist strictly. "
            "If nothing needs attention, respond HEARTBEAT_OK.\n\n"
            f"{content}"
        )

        log.info("Heartbeat tick — sending checklist to APEX")
        response = await self.conversation.send_headless(prompt)

        if "HEARTBEAT_OK" in response:
            log.info("Heartbeat: OK")
        else:
            log.warning("Heartbeat alert: %s", response[:200])
            # TODO: Route alerts to Telegram notification
            await self._route_alert(response)

    async def _route_alert(self, alert: str) -> None:
        """Route a heartbeat alert to the appropriate channel."""
        try:
            from pantheon.channels.telegram import send_notification
            await send_notification(f"⚠️ Heartbeat Alert:\n{alert}")
        except Exception as e:
            log.error("Failed to route heartbeat alert: %s", e)
