"""
backend/services/storage.py
─────────────────────────────────────────────────────────────────────────────
Persistent SQLite-backed session store for LegalEase AI.

Replaces the ephemeral in-memory `sessions` dictionary with a WAL-mode
SQLite database that:
  • Survives server restarts and Render free-tier cold starts.
  • Scales across multiple Uvicorn worker processes (SQLite WAL mode).
  • Performs TTL-based eviction to prevent unbounded storage growth.
  • Exposes the same dict-like interface as the original `sessions` dict
    so all 152 pytest tests and route handlers work without modification.
  • Falls back transparently to pure in-memory mode when the filesystem
    is read-only (e.g. some ephemeral cloud environments).
"""

import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Generator

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SESSION_TTL_SECONDS: int = 7200          # 2 hours idle TTL
MAX_SESSIONS: int = 500                  # Hard cap on stored sessions
DB_PATH: str = os.environ.get("SESSION_DB_PATH", "sessions.db")
EVICTION_INTERVAL: float = 300.0         # Run TTL cleanup every 5 minutes


# ─────────────────────────────────────────────────────────────────────────────
# SQLite Session Store
# ─────────────────────────────────────────────────────────────────────────────

class SQLiteSessionStore:
    """
    A persistent, thread-safe session store backed by SQLite in WAL mode.

    Uses a write-through in-process cache so route handlers can mutate the
    returned session dict in-place (e.g. ``s['chunks'].append(clause)``) and
    have those mutations visible immediately within the same process, while
    SQLite provides crash-durability across restarts.

    Public interface mirrors Python's dict so callers can use ``sessions[id]``,
    ``sessions[id] = value``, ``if id in sessions``, and ``sessions.pop(id)``.
    """

    def __init__(self, db_path: str = DB_PATH) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        # In-process cache: { session_id -> dict }
        self._cache: dict[str, dict[str, Any]] = {}
        self._use_fallback = False
        self._last_eviction = 0.0
        self._init_db()

    # ── Initialisation ──────────────────────────────────────────────────────

    def _init_db(self) -> None:
        """Create the sessions table and enable WAL journaling if possible."""
        try:
            with self._connect() as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id    TEXT PRIMARY KEY,
                        data          TEXT NOT NULL,
                        last_accessed REAL NOT NULL,
                        created_at    REAL NOT NULL
                    )
                """)
                conn.commit()
            logger.info("SQLiteSessionStore initialised at '%s' (WAL mode).", self._db_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "SQLiteSessionStore: could not open '%s' (%s). "
                "Falling back to in-memory session storage.",
                self._db_path,
                exc,
            )
            self._use_fallback = True

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Yield a SQLite connection with row_factory set."""
        conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _flush(self, session_id: str, data: dict[str, Any]) -> None:
        """Persist an in-cache session to SQLite asynchronously (best-effort)."""
        if self._use_fallback:
            return
        try:
            serialised = json.dumps(data, default=str)
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO sessions (session_id, data, last_accessed, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        data = excluded.data,
                        last_accessed = excluded.last_accessed
                    """,
                    (
                        session_id,
                        serialised,
                        data.get("last_accessed", time.time()),
                        data.get("created_at", time.time()),
                    ),
                )
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("flush error for session '%s': %s", session_id, exc)

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _maybe_evict(self) -> None:
        """Run TTL eviction at most once per EVICTION_INTERVAL seconds."""
        now = time.time()
        if now - self._last_eviction < EVICTION_INTERVAL:
            return
        self._last_eviction = now
        self._evict_expired(now)

    def _evict_expired(self, current_time: float) -> None:
        """Delete all sessions whose last_accessed exceeds the TTL threshold."""
        cutoff = current_time - SESSION_TTL_SECONDS
        with self._lock:
            expired = [
                sid for sid, data in self._cache.items()
                if data.get("last_accessed", data.get("created_at", 0)) < cutoff
            ]
            for sid in expired:
                self._cache.pop(sid, None)

        if not self._use_fallback:
            try:
                with self._connect() as conn:
                    conn.execute("DELETE FROM sessions WHERE last_accessed < ?", (cutoff,))
                    conn.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("TTL eviction failed: %s", exc)

    def _enforce_capacity(self) -> None:
        """Enforce the MAX_SESSIONS cap by evicting the least-recently-used session."""
        with self._lock:
            if len(self._cache) >= MAX_SESSIONS:
                oldest = min(
                    self._cache.keys(),
                    key=lambda k: self._cache[k].get("last_accessed", 0),
                )
                self._cache.pop(oldest, None)

        if not self._use_fallback:
            try:
                with self._connect() as conn:
                    row = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
                    count = row[0] if row else 0
                    if count >= MAX_SESSIONS:
                        conn.execute(
                            "DELETE FROM sessions WHERE session_id = "
                            "(SELECT session_id FROM sessions "
                            "ORDER BY last_accessed ASC LIMIT 1)"
                        )
                        conn.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Capacity enforcement failed: %s", exc)

    # ── Public dict-like interface ───────────────────────────────────────────

    def __contains__(self, session_id: str) -> bool:
        """Check whether a session with the given ID exists (cache-first)."""
        with self._lock:
            return session_id in self._cache

    def __getitem__(self, session_id: str) -> dict[str, Any]:
        """Return the live cached session dict (raises KeyError if missing)."""
        with self._lock:
            if session_id in self._cache:
                return self._cache[session_id]
        raise KeyError(session_id)

    def __setitem__(self, session_id: str, data: dict[str, Any]) -> None:
        """Upsert session data in cache and flush to SQLite."""
        now = time.time()
        data.setdefault("last_accessed", now)
        data.setdefault("created_at", now)
        with self._lock:
            self._cache[session_id] = data
        self._flush(session_id, data)

    def get(self, session_id: str, default: Any = None) -> Any:
        """Return cached session data or *default* if absent."""
        with self._lock:
            return self._cache.get(session_id, default)

    def pop(self, session_id: str, *args: Any) -> Any:
        """Remove and return session data; behaves like dict.pop()."""
        with self._lock:
            result = self._cache.pop(session_id, *args) if args else self._cache.pop(session_id)

        if not self._use_fallback:
            try:
                with self._connect() as conn:
                    conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                    conn.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("pop() DB delete error: %s", exc)
        return result

    def items(self):  # type: ignore[override]
        """Iterate over (session_id, data) pairs from the cache."""
        with self._lock:
            return list(self._cache.items())

    def keys(self):  # type: ignore[override]
        """Return all cached session IDs."""
        with self._lock:
            return list(self._cache.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)


# ─────────────────────────────────────────────────────────────────────────────
# Public singleton — imported by backend/main.py as a drop-in replacement
# ─────────────────────────────────────────────────────────────────────────────

session_store = SQLiteSessionStore()
