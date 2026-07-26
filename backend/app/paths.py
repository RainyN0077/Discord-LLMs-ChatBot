import os
from pathlib import Path


class DataPaths:
    """Centralised, environment-configurable application data paths.

    Every path can be overridden via its corresponding environment variable.
    When no variable is set the path falls back to a sensible default rooted
    at ``DATA_DIR`` (which itself defaults to ``<cwd>/data``).

    Usage::

        from app.paths import DataPaths

        DataPaths.ensure_dirs()
        db = DataPaths.KNOWLEDGE_DB
    """

    #: Root data directory.  Override with *DATA_DIR* env-var.
    DATA_DIR = Path(os.environ.get("DATA_DIR", Path.cwd() / "data"))

    #: Per-bot configuration sub-directory.
    BOTS_DIR = DATA_DIR / "bots"

    #: Directory for rotating log files.  Override with *LOG_DIR* env-var.
    LOG_DIR = Path(os.environ.get("LOG_DIR", DATA_DIR / "logs"))

    #: Path to the SQLite database that stores knowledge / memory entries.
    #: Override with *KNOWLEDGE_DB* env-var.
    KNOWLEDGE_DB = Path(os.environ.get("KNOWLEDGE_DB", DATA_DIR / "knowledge_base.sqlite"))

    #: Path to the JSON file that stores LLM usage data (token counts, etc.).
    #: Override with *USAGE_FILE* env-var.
    USAGE_FILE = Path(os.environ.get("USAGE_FILE", DATA_DIR / "usage_data.json"))

    #: Path to the global configuration JSON file (merged across all bots).
    CONFIG_FILE = DATA_DIR / "config.json"

    #: Directory containing SQL schema / other scripts.
    #: Override with *SCRIPTS_DIR* env-var.
    SCRIPTS_DIR = Path(os.environ.get("SCRIPTS_DIR", Path(__file__).parent.parent.parent / "scripts"))

    # ------------------------------------------------------------------
    # Directory creation
    # ------------------------------------------------------------------

    @classmethod
    def ensure_dirs(cls) -> None:
        """Create all directories that must exist on disk."""
        for d in (cls.DATA_DIR, cls.BOTS_DIR, cls.LOG_DIR):
            d.mkdir(parents=True, exist_ok=True)
