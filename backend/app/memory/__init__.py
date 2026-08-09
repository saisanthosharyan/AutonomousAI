"""
Memory package.

Currently this package exposes only the MemoryManager.

Future implementations (MemoryStore, MemoryRetriever,
MemoryRanker, Vector Memory, etc.) can be added later
without changing the public API.
"""

from .memory_manager import MemoryManager

__all__ = [
    "MemoryManager",
]