"""Pantheon main entrypoint — bootstraps APEX and starts the selected channel."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from pantheon.config import settings

# Configure logging placeholder (will be set in run())
log = logging.getLogger("pantheon")


async def start(mode: str, no_schedulers: bool = False) -> None:
    """Bootstrap APEX and start the selected communication channel."""

    # 1. Initialize memory store (eagerly connect to Qdrant)
    log.debug("Initializing memory store (Ollama + Qdrant)...")
    from pantheon.memory.mem0_store import MemoryStore
    memory_store = MemoryStore()
    await asyncio.to_thread(memory_store.initialize)

    # Wire memory into builtin memory tools
    from pantheon.builtin_tools.memory_tools import set_memory_store
    set_memory_store(memory_store)

    # 2. Discover all tools
    log.debug("Discovering tools...")
    from pantheon.core.tools import discover_all_tools
    discover_all_tools()

    from pantheon.core.tools import get_all_tools
    log.debug("Registered %d tools", len(get_all_tools()))

    # 3. Create conversation engine
    from pantheon.core.conversation import Conversation
    conversation = Conversation(memory_store=memory_store)

    # 4. Verify Gemini API key is present
    if not settings.google_ai_api_key:
        log.warning(
            "GOOGLE_AI_API_KEY not set! Add it to .env. "
            "APEX will fail on first message."
        )
    else:
        log.info("Gemini model: %s", settings.google_ai_model)

    # 5. Start schedulers (background tasks)
    heartbeat = None
    cron = None
    
    if not no_schedulers:
        from pantheon.scheduler.heartbeat import HeartbeatScheduler
        from pantheon.scheduler.cron import CronScheduler

        heartbeat = HeartbeatScheduler(conversation)
        cron = CronScheduler(conversation)

        heartbeat.start()
        cron.start()
    else:
        log.info("Schedulers disabled for this session.")

    # 6. Start the selected channel
    try:
        if mode == "cli":
            from pantheon.channels.cli import run_cli
            await run_cli(conversation)

        elif mode == "telegram":
            from pantheon.channels.telegram import setup_telegram, start_polling
            setup_telegram(conversation)
            await start_polling()

        elif mode == "both":
            from pantheon.channels.telegram import setup_telegram, start_polling
            from pantheon.channels.cli import run_cli

            setup_telegram(conversation)

            # Run both concurrently
            await asyncio.gather(
                start_polling(),
                run_cli(conversation),
            )
        else:
            log.error("Unknown mode: %s", mode)
            sys.exit(1)

    except asyncio.CancelledError:
        log.info("Tasks cancelled.")
    finally:
        # Cleanup
        if heartbeat and cron:
            log.info("Stopping schedulers...")
            heartbeat.stop()
            cron.stop()


def run() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="APEX — Pantheon AI Assistant (Gemini 2.5 Pro)",
    )
    parser.add_argument(
        "--mode",
        choices=["cli", "telegram", "both"],
        default="cli",
        help="Communication channel to start (default: cli)",
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Enable debug logging (httpx, qdrant, etc.)",
    )
    args = parser.parse_args()

    # Configure logging
    log_level = logging.INFO if args.debug else logging.WARNING
    
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )

    if not args.debug:
        # In production, show pantheon info logs but valid warnings from others
        logging.getLogger("pantheon").setLevel(logging.INFO)
    else:
        # In debug, show everything
        logging.getLogger().setLevel(logging.INFO)

    try:
        asyncio.run(start(args.mode))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log.error("Fatal error: %s", e, exc_info=True)
        sys.exit(1)
    finally:
        log.info("Goodbye.")


if __name__ == "__main__":
    run()
