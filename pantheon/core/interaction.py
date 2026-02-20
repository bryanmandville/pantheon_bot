"""Interaction abstraction — handle user confirmations across CLI/Telegram."""

from __future__ import annotations

import asyncio
import sys
from abc import ABC, abstractmethod
from contextvars import ContextVar
from typing import Optional

# Global context var to hold the current interaction provider
_interaction_provider: ContextVar[Optional["InteractionProvider"]] = ContextVar(
    "interaction_provider", default=None
)


class InteractionProvider(ABC):
    """Abstract base class for user interactions."""

    @abstractmethod
    async def confirm(self, message: str) -> bool:
        """Ask the user for confirmation (yes/no)."""
    @abstractmethod
    async def request_info(self, message: str, is_secret: bool = False) -> str | None:
        """Ask the user for string input, optionally obscuring the typing."""
        pass


class CLIInteractionProvider(InteractionProvider):
    """CLI implementation — uses stdin/stdout."""

    async def confirm(self, message: str) -> bool:
        """Ask for confirmation via CLI input."""
        loop = asyncio.get_event_loop()
        try:
            # Note: The CLI spinner should be paused by tool hooks before this runs
            prompt = f"\n{message} [y/N] "
            response = await loop.run_in_executor(None, input, prompt)
            return response.strip().lower() == "y"
        except Exception:
            return False

    async def request_info(self, message: str, is_secret: bool = False) -> str | None:
        """Ask for info via CLI input."""
        import getpass
        loop = asyncio.get_event_loop()
        try:
            prompt = f"\n{message} "
            if is_secret:
                response = await loop.run_in_executor(None, getpass.getpass, prompt)
            else:
                response = await loop.run_in_executor(None, input, prompt)
            return response.strip() if response else None
        except Exception:
            return None


def get_interaction() -> InteractionProvider:
    """Get the current interaction provider or fallback to CLI."""
    provider = _interaction_provider.get()
    if not provider:
        return CLIInteractionProvider()
    return provider


def set_interaction(provider: InteractionProvider) -> None:
    """Set the interaction provider for the current context."""
    _interaction_provider.set(provider)
