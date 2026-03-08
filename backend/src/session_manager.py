"""
Session manager with disk persistence.
Each session has its own folder under data/sessions/<session_id>.
"""
from __future__ import annotations

import json
import shutil
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from .config import DATA_DIR

SESSION_METADATA_FILENAME = "session.json"


class SessionStatus(Enum):
    """Possible session states."""

    CREATED = "created"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


@dataclass
class SessionProgress:
    """Progress information for a session."""

    status: SessionStatus = SessionStatus.CREATED
    progress: int = 0
    message: str = "Session creee"
    current_step: str = ""
    total_pages: int = 0
    processed_pages: int = 0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "current_step": self.current_step,
            "total_pages": self.total_pages,
            "processed_pages": self.processed_pages,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionProgress":
        raw_status = data.get("status", SessionStatus.CREATED.value)
        try:
            status = SessionStatus(raw_status)
        except ValueError:
            status = SessionStatus.CREATED

        return cls(
            status=status,
            progress=int(data.get("progress", 0)),
            message=str(data.get("message", "Session creee")),
            current_step=str(data.get("current_step", "")),
            total_pages=int(data.get("total_pages", 0)),
            processed_pages=int(data.get("processed_pages", 0)),
            error=data.get("error"),
        )


@dataclass
class Session:
    """User session."""

    id: str
    vehicle_name: str
    created_at: datetime
    pdf_files: List[str] = field(default_factory=list)
    progress: SessionProgress = field(default_factory=SessionProgress)

    @property
    def session_dir(self) -> Path:
        return DATA_DIR / "sessions" / self.id

    @property
    def pdf_dir(self) -> Path:
        return self.session_dir / "pdfs"

    @property
    def vector_store_dir(self) -> Path:
        return self.session_dir / "vector_store"

    @property
    def metadata_path(self) -> Path:
        return self.session_dir / SESSION_METADATA_FILENAME

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "vehicle_name": self.vehicle_name,
            "created_at": self.created_at.isoformat(),
            "pdf_files": self.pdf_files,
            **self.progress.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        created_at_raw = data.get("created_at")
        try:
            created_at = datetime.fromisoformat(created_at_raw) if created_at_raw else datetime.now()
        except ValueError:
            created_at = datetime.now()

        return cls(
            id=str(data["id"]),
            vehicle_name=str(data.get("vehicle_name", "Vehicule")),
            created_at=created_at,
            pdf_files=list(data.get("pdf_files", [])),
            progress=SessionProgress.from_dict(data),
        )


class SessionManager:
    """In-memory manager backed by disk metadata."""

    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()

        self.sessions_dir = DATA_DIR / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        self._load_sessions_from_disk()
        self._recover_stale_sessions()
        print(f"SessionManager initialized ({len(self.sessions)} sessions loaded)")

    def _recover_stale_sessions(self) -> None:
        """Reset sessions stuck in 'processing' state (e.g. after a crash)."""
        for session in self.sessions.values():
            if session.progress.status == SessionStatus.PROCESSING:
                print(f"Recovering stale session {session.id} (was stuck in processing)")
                session.progress.status = SessionStatus.ERROR
                session.progress.progress = 0
                session.progress.message = "Le traitement a ete interrompu. Veuillez relancer."
                session.progress.error = "Traitement interrompu par un redemarrage du serveur"
                self._save_session_unlocked(session)

    def _save_session_unlocked(self, session: Session) -> None:
        session.session_dir.mkdir(parents=True, exist_ok=True)
        session.pdf_dir.mkdir(parents=True, exist_ok=True)
        session.vector_store_dir.mkdir(parents=True, exist_ok=True)

        with session.metadata_path.open("w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)

    def _load_session_from_disk_unlocked(self, session_id: str) -> Optional[Session]:
        metadata_path = self.sessions_dir / session_id / SESSION_METADATA_FILENAME
        if not metadata_path.exists():
            return None

        try:
            with metadata_path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            session = Session.from_dict(raw)
            self.sessions[session.id] = session
            return session
        except Exception as exc:
            print(f"Failed to load session {session_id}: {exc}")
            return None

    def _load_sessions_from_disk(self) -> None:
        for session_dir in self.sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue
            self._load_session_from_disk_unlocked(session_dir.name)

    def create_session(self, vehicle_name: str) -> Session:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        session = Session(id=session_id, vehicle_name=vehicle_name, created_at=datetime.now())

        with self._lock:
            self.sessions[session_id] = session
            self._save_session_unlocked(session)

        print(f"Session created: {session_id} for {vehicle_name}")
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID, loading from disk if necessary."""
        with self._lock:
            session = self.sessions.get(session_id)
            if session:
                return session
            return self._load_session_from_disk_unlocked(session_id)

    def update_progress(
        self,
        session_id: str,
        status: Optional[SessionStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        current_step: Optional[str] = None,
        total_pages: Optional[int] = None,
        processed_pages: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update session progress."""
        with self._lock:
            session = self.sessions.get(session_id) or self._load_session_from_disk_unlocked(session_id)
            if not session:
                return

            if status is not None:
                session.progress.status = status
            if progress is not None:
                session.progress.progress = progress
            if message is not None:
                session.progress.message = message
            if current_step is not None:
                session.progress.current_step = current_step
            if total_pages is not None:
                session.progress.total_pages = total_pages
            if processed_pages is not None:
                session.progress.processed_pages = processed_pages
            if error is not None:
                session.progress.error = error

            self._save_session_unlocked(session)

    def add_pdf(self, session_id: str, filename: str) -> None:
        """Add an uploaded PDF to the session metadata."""
        with self._lock:
            session = self.sessions.get(session_id) or self._load_session_from_disk_unlocked(session_id)
            if not session:
                return

            session.pdf_files.append(filename)
            self._save_session_unlocked(session)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its files."""
        with self._lock:
            session = self.sessions.get(session_id) or self._load_session_from_disk_unlocked(session_id)
            if not session:
                return False

            if session.session_dir.exists():
                shutil.rmtree(session.session_dir, ignore_errors=True)

            self.sessions.pop(session_id, None)

        print(f"Session deleted: {session_id}")
        return True

    def cleanup_old_sessions(self, max_age_hours: int = 24) -> None:
        """Cleanup sessions older than max_age_hours."""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)

        with self._lock:
            candidates = [s.id for s in self.sessions.values() if s.created_at < cutoff]

        for session_id in candidates:
            self.delete_session(session_id)

        if candidates:
            print(f"Cleanup complete: {len(candidates)} old sessions removed")


# Global singleton
session_manager = SessionManager()

