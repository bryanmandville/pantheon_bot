"""Conversation manager — message history, context assembly, tool loop."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from google.genai import types

from pantheon.config import settings
from pantheon.core import llm
from pantheon.core.prompt import build_system_prompt, build_memory_context
from pantheon.core.tools import execute_tool, get_tool_declarations

log = logging.getLogger(__name__)


class Conversation:
    """Manages a conversation session with APEX.

    Handles:
    - System prompt assembly (re-read each turn)
    - Memory injection
    - Message history with truncation
    - Tool call loops (call → execute → feed result → repeat)
    """

    def __init__(self, memory_store=None):
        self.history: list[types.Content] = []
        self.memory_store = memory_store

    async def send(self, user_message: str, tool_hooks: dict[str, Any] | None = None) -> str:
        """Process a user message and return APEX's response.

        Args:
            user_message: The user's input.
            tool_hooks: Optional callbacks for "on_tool_start" and "on_tool_end".
        """
        # Add user message to history
        self.history.append(llm.build_user_content(user_message))

        # Build fresh system prompt (re-reads files each time)
        system_prompt = build_system_prompt()

        # Inject relevant memories
        memory_context = ""
        if self.memory_store:
            try:
                memories = await asyncio.to_thread(self.memory_store.search, user_message)
                memory_context = build_memory_context(memories)
            except Exception as e:
                log.warning("Memory search failed: %s", e)

        # Assemble system instruction
        system_instruction = system_prompt
        if memory_context:
            system_instruction = f"{system_prompt}\n\n---\n\n{memory_context}"

        # Build messages list
        messages = list(self._truncated_history())

        # Only send tools when the message looks actionable
        tools = self._should_use_tools(user_message)

        # Tool call loop — max 5 iterations to prevent infinite loops
        for _ in range(5):
            response = await llm.chat(
                messages,
                system_instruction=system_instruction,
                tools=tools if tools else None,
            )

            if llm.has_tool_calls(response):
                # Append the model's response (preserves thought signatures)
                model_content = llm.get_model_response_content(response)
                messages.append(model_content)

                # Execute each tool call and build function response parts
                tool_calls = llm.extract_tool_calls(response)
                response_parts = []

                for tc in tool_calls:
                    tool_name = tc.name
                    tool_args = dict(tc.args) if tc.args else {}

                    log.info("Tool call: %s(%s)", tool_name, tool_args)
                    
                    # Notify start hook
                    if tool_hooks and "on_tool_start" in tool_hooks:
                        await tool_hooks["on_tool_start"](tool_name, tool_args)

                    result = await execute_tool(tool_name, tool_args)
                    
                    # Notify end hook
                    if tool_hooks and "on_tool_end" in tool_hooks:
                        await tool_hooks["on_tool_end"](tool_name, result)

                    response_parts.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={"result": result},
                        )
                    )

                # Send all function responses in one Content message
                messages.append(
                    types.Content(role="user", parts=response_parts)
                )
            else:
                # Final text response
                content = llm.extract_content(response)
                self.history.append(llm.build_model_content(content))

                # Fire-and-forget memory save
                asyncio.create_task(self._maybe_save_memory(user_message, content))

                return content

        # If we exhausted tool loops, return last content
        content = llm.extract_content(response)
        self.history.append(llm.build_model_content(content))
        return content or "I got stuck in a tool loop. Try rephrasing."

    async def send_headless(self, prompt: str) -> str:
        """Send a prompt without adding to conversation history.

        Used by heartbeat/cron — doesn't pollute the user's conversation.
        """
        system_prompt = build_system_prompt()
        messages = [llm.build_user_content(prompt)]
        tools = get_tool_declarations()

        for _ in range(5):
            response = await llm.chat(
                messages,
                system_instruction=system_prompt,
                tools=tools if tools else None,
            )

            if llm.has_tool_calls(response):
                model_content = llm.get_model_response_content(response)
                messages.append(model_content)

                tool_calls = llm.extract_tool_calls(response)
                response_parts = []

                for tc in tool_calls:
                    tool_name = tc.name
                    tool_args = dict(tc.args) if tc.args else {}
                    result = await execute_tool(tool_name, tool_args)
                    response_parts.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={"result": result},
                        )
                    )

                messages.append(
                    types.Content(role="user", parts=response_parts)
                )
            else:
                return llm.extract_content(response)

        return llm.extract_content(response) or ""

    def _should_use_tools(self, message: str) -> list[dict[str, Any]] | None:
        """Return all available tools unconditionally."""
        from pantheon.core.tools import get_tool_declarations
        declarations = get_tool_declarations()
        return declarations if declarations else None

    def _truncated_history(self) -> list[types.Content]:
        """Return recent history, truncated to fit context limits."""
        max_msgs = settings.max_context_messages
        if len(self.history) <= max_msgs:
            return list(self.history)
        return list(self.history[-max_msgs:])

    async def _maybe_save_memory(self, user_msg: str, assistant_msg: str) -> None:
        """Save conversation exchange to memory if it seems worth remembering."""
        if not self.memory_store:
            return

        if not self._should_memorize(user_msg):
            return

        try:
            combined = f"User: {user_msg}\nAPEX: {assistant_msg}"
            await asyncio.to_thread(self.memory_store.add, combined)
        except Exception as e:
            log.warning("Failed to save memory: %s", e)

    def _should_memorize(self, user_msg: str) -> bool:
        """Heuristic: only save statements, not questions or commands."""
        msg = user_msg.lower().strip()

        if len(msg) < 10:
            return False

        question_starters = (
            "who ", "what ", "where ", "when ", "why ", "how ",
            "is ", "are ", "can ", "do ", "does ", "will ",
        )
        if msg.startswith(question_starters):
            return False

        if msg.startswith(("/", "reset", "clear", "help", "quit", "exit")):
            return False

        return True

    def clear(self) -> None:
        """Clear conversation history."""
        self.history.clear()

    async def reset(self) -> None:
        """Full session reset — clear history."""
        self.history.clear()
