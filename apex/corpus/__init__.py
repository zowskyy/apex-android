"""Local corpus index."""

from .stats import corpus_stats
from .store import CorpusStore

__all__ = ["CorpusStore", "corpus_stats"]
