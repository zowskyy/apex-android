"""Local corpus index."""

from .stats import corpus_packages, corpus_stats
from .store import CorpusStore

__all__ = ["CorpusStore", "corpus_packages", "corpus_stats"]
