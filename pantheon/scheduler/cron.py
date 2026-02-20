"""Cron scheduler — scheduled jobs from CRON.md using APScheduler."""

from __future__ import annotations

import logging
import re

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from pantheon.config import settings
from pantheon.core.conversation import Conversation

log = logging.getLogger(__name__)


class CronScheduler:
    """Parses CRON.md and schedules jobs via APScheduler."""

    def __init__(self, conversation: Conversation):
        self.conversation = conversation
        self.scheduler = AsyncIOScheduler()
        self._job_count = 0

    def start(self) -> None:
        """Load jobs from CRON.md and start the scheduler."""
        self._load_jobs()
        if self._job_count > 0:
            self.scheduler.start()
            log.info("Cron scheduler started with %d jobs", self._job_count)
        else:
            log.info("No cron jobs found in CRON.md")

    def stop(self) -> None:
        """Shut down the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def reload(self) -> int:
        """Reload jobs from CRON.md. Returns new job count."""
        # Remove existing jobs
        self.scheduler.remove_all_jobs()
        self._job_count = 0
        self._load_jobs()
        if not self.scheduler.running and self._job_count > 0:
            self.scheduler.start()
        log.info("Cron reloaded: %d jobs", self._job_count)
        return self._job_count

    def _load_jobs(self) -> None:
        """Parse CRON.md and register jobs."""
        cron_file = settings.schedules_dir / "CRON.md"
        if not cron_file.exists():
            return

        content = cron_file.read_text(encoding="utf-8")
        jobs = self._parse_cron_md(content)

        for job in jobs:
            try:
                trigger = CronTrigger.from_crontab(job["cron"])
                self.scheduler.add_job(
                    self._execute_job,
                    trigger=trigger,
                    args=[job["name"], job["prompt"], job.get("notify", "log")],
                    id=f"cron_{job['name']}",
                    replace_existing=True,
                )
                self._job_count += 1
                log.info("Registered cron job: %s (%s)", job["name"], job["cron"])
            except Exception as e:
                log.error("Failed to register cron '%s': %s", job["name"], e)

    def _parse_cron_md(self, content: str) -> list[dict[str, str]]:
        """Parse CRON.md into job definitions.

        Expected format:
        ## Job Name
        - cron: `*/15 * * * *`
        - prompt: "Do something"
        - notify: telegram
        """
        jobs = []
        current_job: dict[str, str] | None = None

        for line in content.splitlines():
            line = line.strip()

            # New job heading
            if line.startswith("## ") and not line.startswith("## Cron"):
                if current_job and "cron" in current_job and "prompt" in current_job:
                    jobs.append(current_job)
                current_job = {"name": line[3:].strip()}
                continue

            if current_job is None:
                continue

            # Parse fields
            if line.startswith("- cron:"):
                match = re.search(r'`([^`]+)`', line)
                if match:
                    current_job["cron"] = match.group(1)

            elif line.startswith("- prompt:"):
                # Extract quoted string or remainder
                match = re.search(r'"([^"]+)"', line)
                if match:
                    current_job["prompt"] = match.group(1)
                else:
                    current_job["prompt"] = line.split(":", 1)[1].strip()

            elif line.startswith("- notify:"):
                current_job["notify"] = line.split(":", 1)[1].strip()

        # Don't forget the last job
        if current_job and "cron" in current_job and "prompt" in current_job:
            jobs.append(current_job)

        return jobs

    async def _execute_job(self, name: str, prompt: str, notify: str) -> None:
        """Execute a cron job — send prompt to APEX headlessly."""
        log.info("Cron executing: %s", name)
        try:
            response = await self.conversation.send_headless(prompt)
            log.info("Cron '%s' result: %s", name, response[:200])

            if notify == "telegram":
                from pantheon.channels.telegram import send_notification
                await send_notification(f"📋 Cron [{name}]:\n{response}")

        except Exception as e:
            log.error("Cron '%s' failed: %s", name, e, exc_info=True)
