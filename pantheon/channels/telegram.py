"""Telegram channel — aiogram bot for APEX."""

from __future__ import annotations

import logging

import asyncio
import uuid
from typing import Dict

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from pantheon.config import settings
from pantheon.core.conversation import Conversation
from pantheon.core.interaction import InteractionProvider, set_interaction

log = logging.getLogger(__name__)

# Module-level references set at startup
_bot: Bot | None = None
_dp: Dispatcher | None = None
_conversation: Conversation | None = None

# Pending confirmations: request_id -> Future[bool]
_pending_confirmations: Dict[str, asyncio.Future[bool]] = {}

# Pending inputs: chat_id -> {"future": Future[str|None], "is_secret": bool, "prompt_msg_id": int}
_pending_inputs: Dict[int, dict] = {}


class TelegramInteractionProvider(InteractionProvider):
    """Telegram implementation — uses Inline Keyboard."""

    def __init__(self, chat_id: int):
        self.chat_id = chat_id

    async def confirm(self, message: str) -> bool:
        """Ask for confirmation via Inline Keyboard."""
        if not _bot:
            return False

        request_id = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        _pending_confirmations[request_id] = future

        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Yes", callback_data=f"confirm:{request_id}:yes"),
            InlineKeyboardButton(text="No", callback_data=f"confirm:{request_id}:no"),
        ]])

        sent_msg = await _bot.send_message(
            self.chat_id,
            f"❓ {message}",
            reply_markup=keyboard
        )

        try:
            # Wait for user click (timeout 60s)
            result = await asyncio.wait_for(future, timeout=60.0)
            return result
        except asyncio.TimeoutError:
            if request_id in _pending_confirmations:
                del _pending_confirmations[request_id]
            # Edit message to show timeout
            try:
                await _bot.edit_message_text(
                    f"❌ {message}\n(Timed out)",
                    chat_id=self.chat_id,
                    message_id=sent_msg.message_id,
                    reply_markup=None
                )
            except Exception:
                pass
            return False
        finally:
             if request_id in _pending_confirmations:
                del _pending_confirmations[request_id]

    async def request_info(self, message: str, is_secret: bool = False) -> str | None:
        """Ask for string info via chat message."""
        if not _bot:
            return None

        # Clean up any existing pending input for this chat
        if self.chat_id in _pending_inputs:
            old_future = _pending_inputs[self.chat_id]["future"]
            if not old_future.done():
                old_future.set_result(None)
            del _pending_inputs[self.chat_id]

        future = asyncio.get_running_loop().create_future()

        prompt_prefix = "🔒 " if is_secret else "❓ "
        prompt_suffix = "\n(Your next message will be read as the answer. If secret, it will be instantly deleted.)" if is_secret else "\n(Your next message will be read as the answer.)"
        
        sent_msg = await _bot.send_message(
            self.chat_id,
            f"{prompt_prefix}{message}{prompt_suffix}"
        )

        _pending_inputs[self.chat_id] = {
            "future": future,
            "is_secret": is_secret,
            "prompt_msg_id": sent_msg.message_id,
        }

        try:
            # Wait for user reply (timeout 300s)
            result = await asyncio.wait_for(future, timeout=300.0)
            
            # Clean up prompt message
            try:
                await _bot.edit_message_text(
                    f"✅ {message}\n(Received)",
                    chat_id=self.chat_id,
                    message_id=sent_msg.message_id,
                )
            except Exception:
                pass
                
            return result
        except asyncio.TimeoutError:
            try:
                await _bot.edit_message_text(
                    f"❌ {message}\n(Timed out waiting for input)",
                    chat_id=self.chat_id,
                    message_id=sent_msg.message_id,
                )
            except Exception:
                pass
            return None
        finally:
            if self.chat_id in _pending_inputs:
                del _pending_inputs[self.chat_id]


async def _handle_callback(callback: CallbackQuery):
    """Handle confirmation clicks."""
    if not callback.data or not callback.data.startswith("confirm:"):
        return

    _, request_id, decision = callback.data.split(":")
    
    if request_id in _pending_confirmations:
        future = _pending_confirmations[request_id]
        if not future.done():
            future.set_result(decision == "yes")
    
    # Update message UI
    text = callback.message.text
    # Strip the ❓ prefix if present (approximate)
    if text.startswith("❓ "):
        text = text[2:]
        
    icon = "✅" if decision == "yes" else "❌"
    new_text = f"{icon} {text}\n(Confirmed: {decision.upper()})"
    
    await callback.message.edit_text(new_text, reply_markup=None)
    await callback.answer()


def setup_telegram(conversation: Conversation) -> tuple[Bot, Dispatcher]:
    """Initialize the Telegram bot and dispatcher."""
    global _bot, _dp, _conversation
    # ... (existing code checks) ...

    if not settings.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")

    _conversation = conversation
    _bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    _dp = Dispatcher()

    # Register handlers
    _dp.message.register(_handle_message, F.text)
    _dp.callback_query.register(_handle_callback, F.data.startswith("confirm:"))

    log.info("Telegram bot initialized")
    return _bot, _dp


async def _handle_message(message: Message) -> None:
    """Handle incoming Telegram messages."""
    if not message.text or not _conversation:
        return

    chat_id = message.chat.id

    # Check for pending inputs
    if chat_id in _pending_inputs:
        pending_info = _pending_inputs[chat_id]
        future = pending_info["future"]
        is_secret = pending_info["is_secret"]

        if not future.done():
            future.set_result(message.text)

        if is_secret and _bot:
            try:
                await _bot.delete_message(chat_id, message.message_id)
            except Exception as e:
                log.warning("Failed to delete secret message: %s", e)
        
        # Don't process this message further, it was an input reply
        return

    # Set interaction provider for this context
    provider = TelegramInteractionProvider(chat_id)
    set_interaction(provider)

    user_text = message.text.strip()
    if not user_text:
        return

    # Handle /reset command
    if user_text.lower() == "/reset":
        await message.answer("Resetting session and re-warming cache...")
        await _conversation.reset()
        await message.answer("Session reset. KV cache re-warmed.")
        return

    log.info("Telegram message from %s: %s", message.from_user.id, user_text[:80])

    try:
        response = await _conversation.send(user_text)

        # Telegram has a 4096 char limit per message
        if len(response) > 4000:
            # Split into chunks
            chunks = [response[i:i + 4000] for i in range(0, len(response), 4000)]
            for chunk in chunks:
                await message.answer(chunk)
        else:
            await message.answer(response)

    except Exception as e:
        log.error("Telegram handler error: %s", e, exc_info=True)
        await message.answer(f"Error: {e}")


async def send_notification(text: str) -> None:
    """Send a proactive notification via Telegram."""
    # ... (existing code) ...
    if not _bot:
        return
    log.info("Notification (no target chat): %s", text[:80])


async def start_polling() -> None:
    """Start the Telegram bot polling loop."""
    if not _bot or not _dp:
        raise RuntimeError("Telegram bot not set up. Call setup_telegram() first.")

    log.info("Starting Telegram bot polling...")
    await _dp.start_polling(_bot)
