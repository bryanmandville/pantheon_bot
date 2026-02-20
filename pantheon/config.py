"""Application configuration — loads from .env file."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All config loaded from environment variables / .env file."""

    # Google AI Studio (primary LLM)
    google_ai_api_key: str = ""
    google_ai_model: str = "gemini-2.5-pro"

    # Cloud quick-answer model (lighter/faster)
    cloud_fast_model: str = "gemini-2.5-flash"

    # Ollama (memory backend)
    ollama_base_url: str = "https://pantheon.tailaae160.ts.net"
    ollama_model: str = "qwen2.5:3b"

    # Qdrant (mem0 vector store)
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Telegram
    telegram_bot_token: str = ""

    # Embedding model (for future use)
    embedding_model: str = "nomic-embed-text"

    # Scheduler
    heartbeat_interval_minutes: int = 30

    # Paths (relative to project root)
    project_root: Path = Path(__file__).parent.parent
    prompts_dir: Path = Path(__file__).parent.parent / "prompts"
    schedules_dir: Path = Path(__file__).parent.parent / "schedules"
    agents_dir: Path = Path(__file__).parent.parent / "agents"

    # Context management
    max_context_messages: int = 20  # Keep last N messages before truncating

    # Shell allowlist
    # Shell allowlist
    shell_allowlist: list[str] = [
        "ls", "cat", "echo", "date", "uptime", "df", "free",
        "whoami", "hostname", "uname", "ps", "top", "htop",
        "ping", "curl", "wget", "docker", "systemctl",
        "list", # Added for list files support
    ]

    model_config = {
        "env_file": str(Path(__file__).parent.parent / ".env"), 
        "env_file_encoding": "utf-8",
        "extra": "allow"
    }

    def model_post_init(self, __context):
        """Load allowlist from file or create it if missing."""
        allowlist_path = self.project_root / "SHELL_ALLOWLIST"
        if allowlist_path.exists():
            content = allowlist_path.read_text(encoding="utf-8")
            # Filter out empty lines and comments
            lines = [
                line.strip() 
                for line in content.splitlines() 
                if line.strip() and not line.strip().startswith("#")
            ]
            if lines:
                self.shell_allowlist = lines
        else:
            # Create file with defaults
            content = "# APEX Shell Allowlist\n# Add one command per line\n" + "\n".join(self.shell_allowlist)
            allowlist_path.write_text(content, encoding="utf-8")


settings = Settings()
