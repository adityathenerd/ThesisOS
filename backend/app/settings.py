import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

APP_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///backend/data/thesisos.db"
    provider_mode: str = "fixture"
    crustdata_api_key: str = ""
    max_cases_per_run: int = 10
    cors_origins: tuple[str, ...] = ("http://127.0.0.1:5173", "http://localhost:5173")
    fixture_path: Path = APP_ROOT / "config" / "fixtures.json"
    crustdata_search_config: Path | None = None
    reference_source_config: Path | None = APP_ROOT / "config" / "reference-source.json"

    @classmethod
    def from_environment(cls):
        # Explicit server-only file, process environment wins. Never return its content.
        load_dotenv(APP_ROOT / "config" / ".env", override=False)
        mode = os.getenv("PROVIDER_MODE", "fixture").strip().lower()
        if mode not in {"fixture", "live"}:
            raise ValueError("PROVIDER_MODE must be fixture or live")
        maximum = int(os.getenv("MAX_CASES_PER_RUN", "10"))
        if not 1 <= maximum <= 100:
            raise ValueError("MAX_CASES_PER_RUN must be between 1 and 100")
        return cls(
            database_url=os.getenv("DATABASE_URL", "sqlite:///backend/data/thesisos.db"),
            provider_mode=mode,
            crustdata_api_key=os.getenv("CRUSTDATA_API_KEY", ""),
            max_cases_per_run=maximum,
            cors_origins=tuple(x.strip() for x in os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",") if x.strip()),
            crustdata_search_config=Path(os.environ["CRUSTDATA_SEARCH_CONFIG"]) if os.getenv("CRUSTDATA_SEARCH_CONFIG", "").strip() else None,
        )

    def sqlite_path(self) -> Path:
        if not self.database_url.startswith("sqlite:///"):
            raise ValueError("Only sqlite:/// DATABASE_URL is implemented in this harness; add a state adapter before using PostgreSQL")
        value = self.database_url.removeprefix("sqlite:///")
        if not value or value == ":memory:":
            raise ValueError("Use a persistent SQLite file in DATABASE_URL")
        path = Path(value)
        return path if path.is_absolute() else APP_ROOT / path
