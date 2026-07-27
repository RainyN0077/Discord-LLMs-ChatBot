from datetime import datetime
from typing import Any, Dict, Optional


class AppContext:
    """Application-level singleton holding all global service references.

    This replaces module-level global variables in state.py with a managed
    singleton, enabling cleaner test isolation and future multi-worker support.
    """

    _instance: Optional["AppContext"] = None

    def __init__(self) -> None:
        self.bot_manager: Any = None
        self.astrbot_process_manager: Any = None
        self.memory_cutoffs: Dict[int, datetime] = {}
        self.bot_tasks: Dict[str, Any] = {}
        self.usage_tracker: Any = None

    @classmethod
    def get(cls) -> "AppContext":
        """Return the singleton AppContext instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Clear the singleton — primarily for test teardown."""
        cls._instance = None
