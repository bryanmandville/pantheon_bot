# Available Tools

## File Operations
- `read_file(path)` — Read a prompt, schedule, or agent file
- `write_file(path, content)` — Write/overwrite a file
- `append_file(path, content)` — Append content to a file

## Memory
- `search_memory(query)` — Search persistent memory for relevant facts
- `add_memory(content)` — Store a new fact in persistent memory
- `list_memories()` — List all stored memories

## System
- `run_command(command)` — Execute an allowlisted shell command

## Agent Management
- `create_agent(name, description, code)` — Create a new tool script
- `list_agents()` — List available custom tool scripts
- `delete_agent(name)` — Remove a custom tool script

## Quick Answers
- `ask_flash(prompt)` — Ask Gemini Flash for a fast, cheap answer to simple questions
