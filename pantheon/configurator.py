"""Interactive configuration wizard for APEX (.env file)."""

import os
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from rich.text import Text

from pantheon.config import settings

console = Console()

HEADER = """
[bold cyan]██████╗  █████╗ ███╗   ██╗████████╗██╗  ██╗███████╗██████╗ ███╗   ██╗[/bold cyan]
[bold cyan]██╔══██╗██╔══██╗████╗  ██║╚══██╔══╝██║  ██║██╔════╝██╔══██╗████╗  ██║[/bold cyan]
[bold cyan]██████╔╝███████║██╔██╗ ██║   ██║   ███████║█████╗  ██║  ██║██╔██╗ ██║[/bold cyan]
[bold cyan]██╔═══╝ ██╔══██║██║╚██╗██║   ██║   ██╔══██║██╔══╝  ██║  ██║██║╚██╗██║[/bold cyan]
[bold cyan]██║     ██║  ██║██║ ╚████║   ██║   ██║  ██║███████╗██████╔╝██║ ╚████║[/bold cyan]
[bold cyan]╚═╝     ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═════╝ ╚═╝  ╚═══╝[/bold cyan]
[bold green]                                  A I   A G E N T   M E S H[/bold green]
"""

def read_existing_env(env_path: Path) -> dict[str, str]:
    """Read existing .env file into a dictionary."""
    existing = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()
    return existing

def write_env(env_path: Path, config: dict[str, str]) -> None:
    """Write configuration dictionary to .env file."""
    lines = []
    
    # Define sections for neatness
    sections = {
        "Google AI Studio (primary LLM)": ["GOOGLE_AI_API_KEY", "GOOGLE_AI_MODEL", "CLOUD_FAST_MODEL"],
        "Ollama (memory backend)": ["OLLAMA_BASE_URL", "OLLAMA_MODEL"],
        "Qdrant (local vector DB for mem0)": ["QDRANT_HOST", "QDRANT_PORT"],
        "Telegram Bot": ["TELEGRAM_BOT_TOKEN"],
        "Scheduler": ["HEARTBEAT_INTERVAL_MINUTES"],
        "Other Configuration": [] # Fallback for other keys
    }
    
    handled_keys = set()
    
    for section_name, keys in sections.items():
        section_lines = []
        for key in keys:
            if key in config:
                section_lines.append(f"{key}={config[key]}")
                handled_keys.add(key)
        
        if section_lines:
            lines.append(f"# {section_name}")
            lines.extend(section_lines)
            lines.append("")
    
    # Leftover keys (like dynamic ones added by tools, e.g. OPEN_ROUTER_API_KEY)
    leftovers = []
    for key, value in config.items():
        if key not in handled_keys:
            leftovers.append(f"{key}={value}")
    
    if leftovers:
        lines.append("# Dynamic Configuration")
        lines.extend(leftovers)
        lines.append("")
        
    env_path.write_text("\n".join(lines), encoding="utf-8")


def prompt_secret(key: str, existing_val: str, description: str) -> str:
    """Prompt for a secret value, hiding typing but showing if a value exists."""
    console.print(f"\n[bold cyan]{key}[/bold cyan] - [dim]{description}[/dim]")
    
    if existing_val:
        console.print("[green]✓ A value is already set.[/green] [dim](Press Enter to keep existing)[/dim]")
        val = Prompt.ask("New Value", password=True, default="")
        if not val:
            return existing_val
        return val
    else:
        return Prompt.ask("Value", password=True)


def prompt_string(key: str, existing_val: str, default: str, description: str) -> str:
    """Prompt for a string value with a default."""
    console.print(f"\n[bold cyan]{key}[/bold cyan] - [dim]{description}[/dim]")
    current = existing_val if existing_val else default
    val = Prompt.ask("Value", default=current)
    return val


def prompt_int(key: str, existing_val: str, default: int, description: str) -> str:
    """Prompt for an integer value with a default."""
    console.print(f"\n[bold cyan]{key}[/bold cyan] - [dim]{description}[/dim]")
    current = int(existing_val) if existing_val and existing_val.isdigit() else default
    val = IntPrompt.ask("Value", default=current)
    return str(val)


def run_configurator() -> None:
    """Run the interactive configuration wizard."""
    os.system('clear')
    console.print(HEADER)
    
    env_path = settings.project_root / ".env"
    existing = read_existing_env(env_path)
    
    console.print(Panel.fit(
        "[bold]Pantheon Configuration Wizard[/bold]\n"
        "Let's get your environment set up. Press [bold]Enter[/bold] to accept defaults.",
        border_style="cyan"
    ))
    
    new_config = existing.copy()
    
    try:
        # LLM Settings
        new_config["GOOGLE_AI_API_KEY"] = prompt_secret(
            "GOOGLE_AI_API_KEY", 
            existing.get("GOOGLE_AI_API_KEY", ""), 
            "Your Gemini API Key"
        )
        
        new_config["GOOGLE_AI_MODEL"] = prompt_string(
            "GOOGLE_AI_MODEL", 
            existing.get("GOOGLE_AI_MODEL", ""), 
            "gemini-2.5-pro", 
            "Primary advanced chat model"
        )
        
        new_config["CLOUD_FAST_MODEL"] = prompt_string(
            "CLOUD_FAST_MODEL", 
            existing.get("CLOUD_FAST_MODEL", ""), 
            "gemini-2.5-flash", 
            "Fast model for quick tool executions"
        )
        
        # Telegram
        new_config["TELEGRAM_BOT_TOKEN"] = prompt_secret(
            "TELEGRAM_BOT_TOKEN", 
            existing.get("TELEGRAM_BOT_TOKEN", ""), 
            "Telegram Bot Token (from BotFather)"
        )
        
        # Ollama
        new_config["OLLAMA_BASE_URL"] = prompt_string(
            "OLLAMA_BASE_URL", 
            existing.get("OLLAMA_BASE_URL", ""), 
            "http://localhost:11434", 
            "Ollama server URL for local memory processing"
        )
        
        new_config["OLLAMA_MODEL"] = prompt_string(
            "OLLAMA_MODEL", 
            existing.get("OLLAMA_MODEL", ""), 
            "qwen2.5:3b", 
            "Ollama model to use for memory summarization"
        )
        
        # Qdrant
        new_config["QDRANT_HOST"] = prompt_string(
            "QDRANT_HOST", 
            existing.get("QDRANT_HOST", ""), 
            "localhost", 
            "Qdrant vector database host"
        )
        
        new_config["QDRANT_PORT"] = prompt_int(
            "QDRANT_PORT", 
            existing.get("QDRANT_PORT", ""), 
            6333, 
            "Qdrant vector database port"
        )
        
        # Scheduler
        new_config["HEARTBEAT_INTERVAL_MINUTES"] = prompt_int(
            "HEARTBEAT_INTERVAL_MINUTES", 
            existing.get("HEARTBEAT_INTERVAL_MINUTES", ""), 
            30, 
            "How often APEX runs its background health check (minutes)"
        )
        
        # Save
        console.print("\n[bold green]Saving configuration to .env...[/bold green]")
        write_env(env_path, new_config)
        
        console.print(Panel(
            "[bold green]Configuration Complete![/bold green]\n\n"
            "You can now run [bold cyan]pantheon chat[/bold cyan] or [bold cyan]pantheon service start[/bold cyan].",
            border_style="green"
        ))
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Configuration aborted.[/yellow]")
        return
        
if __name__ == "__main__":
    run_configurator()
