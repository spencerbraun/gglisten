"""SQLite storage for transcriptions"""

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from .config import get_config


@dataclass
class Transcription:
    """A stored transcription record"""

    id: int | None
    timestamp: float
    duration: float | None
    text: str
    processed_text: str | None = None
    audio_path: str | None = None
    model: str | None = None
    metadata: dict | None = None


def _get_connection() -> sqlite3.Connection:
    """Get database connection, creating tables if needed"""
    config = get_config()
    config.ensure_dirs()

    conn = sqlite3.connect(str(config.db_path))
    conn.row_factory = sqlite3.Row

    # Create tables if they don't exist
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS transcription (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            duration REAL,
            text TEXT NOT NULL,
            processed_text TEXT,
            audio_path TEXT,
            model TEXT,
            metadata TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_timestamp ON transcription(timestamp DESC);
    """)

    return conn


def save(
    text: str,
    duration: float | None = None,
    audio_path: Path | None = None,
    model: str | None = None,
    metadata: dict | None = None,
) -> int:
    """
    Save a transcription to the database.

    Returns the ID of the saved record.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO transcription (timestamp, duration, text, audio_path, model, metadata)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            time.time(),
            duration,
            text,
            str(audio_path) if audio_path else None,
            model,
            json.dumps(metadata) if metadata else None,
        ),
    )

    conn.commit()
    record_id = cursor.lastrowid
    conn.close()

    return record_id


def get_recent(limit: int = 10) -> list[Transcription]:
    """Get recent transcriptions, newest first"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, timestamp, duration, text, processed_text, audio_path, model, metadata
        FROM transcription
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,),
    )

    results = []
    for row in cursor.fetchall():
        metadata = None
        if row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except json.JSONDecodeError:
                pass

        results.append(Transcription(
            id=row["id"],
            timestamp=row["timestamp"],
            duration=row["duration"],
            text=row["text"],
            processed_text=row["processed_text"],
            audio_path=row["audio_path"],
            model=row["model"],
            metadata=metadata,
        ))

    conn.close()
    return results


def get_by_id(record_id: int) -> Transcription | None:
    """Get a specific transcription by ID"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, timestamp, duration, text, processed_text, audio_path, model, metadata
        FROM transcription
        WHERE id = ?
        """,
        (record_id,),
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    metadata = None
    if row["metadata"]:
        try:
            metadata = json.loads(row["metadata"])
        except json.JSONDecodeError:
            pass

    return Transcription(
        id=row["id"],
        timestamp=row["timestamp"],
        duration=row["duration"],
        text=row["text"],
        processed_text=row["processed_text"],
        audio_path=row["audio_path"],
        model=row["model"],
        metadata=metadata,
    )


def search(query: str, limit: int = 20) -> list[Transcription]:
    """Search transcriptions by text content"""
    conn = _get_connection()
    cursor = conn.cursor()

    # Simple LIKE search (FTS could be added later for better performance)
    cursor.execute(
        """
        SELECT id, timestamp, duration, text, processed_text, audio_path, model, metadata
        FROM transcription
        WHERE text LIKE ? OR processed_text LIKE ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (f"%{query}%", f"%{query}%", limit),
    )

    results = []
    for row in cursor.fetchall():
        metadata = None
        if row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except json.JSONDecodeError:
                pass

        results.append(Transcription(
            id=row["id"],
            timestamp=row["timestamp"],
            duration=row["duration"],
            text=row["text"],
            processed_text=row["processed_text"],
            audio_path=row["audio_path"],
            model=row["model"],
            metadata=metadata,
        ))

    conn.close()
    return results


def update_processed_text(record_id: int, processed_text: str):
    """Update the processed text for a transcription"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE transcription
        SET processed_text = ?
        WHERE id = ?
        """,
        (processed_text, record_id),
    )

    conn.commit()
    conn.close()


def get_latest() -> Transcription | None:
    """Get the most recent transcription"""
    results = get_recent(limit=1)
    return results[0] if results else None
