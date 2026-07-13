"""Memory Layer memory system.

Manages AI-Lab system memory with four types:
- SESSION: Short-term session context (TTL auto-expire)
- EPISODIC: Long-term event history (SQLite)
- SEMANTIC: Structured concept relations (SQLite)
- DECISION: Decision reasoning chains (SQLite, append-only)

Consolidation Engine manages memory lifecycle:
- ImportanceScorer: Composite importance scoring
- MemoryDecay: Time-based decay calculation
- ConsolidationPolicy: Policy decisions (retain/compress/promote/delete)
- ConsolidationEngine: Background periodic consolidation execution

Storage layer provides persistent backends:
- SQLiteEpisodicStore / SQLiteSemanticStore / SQLiteDecisionStore
- VectorStore: Vector search abstraction interface (reserved)
"""

from core.memory.consolidation import ConsolidationEngine, ConsolidationResult
from core.memory.decay import DecayConfig, MemoryDecay
from core.memory.decision import DecisionMemory
from core.memory.episodic import EpisodicMemory
from core.memory.importance import ImportanceConfig, ImportanceScorer
from core.memory.manager import MemoryManager, get_manager, reset_manager
from core.memory.models import MemoryFilter, MemoryItem, MemoryQuery, MemoryType
from core.memory.policy import ConsolidationAction, ConsolidationPolicy, ConsolidationThresholds, PolicyDecision
from core.memory.protocol import MemoryStore
from core.memory.semantic import SemanticMemory
from core.memory.session import SessionMemory
from core.memory.storage import SQLiteDecisionStore, SQLiteEpisodicStore, SQLiteSemanticStore, VectorStore

__all__ = [
    "MemoryManager", "get_manager", "reset_manager",
    "MemoryItem", "MemoryType", "MemoryQuery", "MemoryFilter",
    "MemoryStore",
    "SessionMemory",
    "EpisodicMemory",
    "SemanticMemory",
    "DecisionMemory",
    "SQLiteEpisodicStore", "SQLiteSemanticStore", "SQLiteDecisionStore", "VectorStore",
    "ConsolidationEngine", "ConsolidationResult", "ConsolidationAction",
    "ConsolidationPolicy", "ConsolidationThresholds", "PolicyDecision",
    "ImportanceScorer", "ImportanceConfig",
    "MemoryDecay", "DecayConfig",
]
