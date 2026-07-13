"""Database-level data models."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class MigrationRecord:
    version: str = ""
    applied_at: str = ""
    description: str = ""