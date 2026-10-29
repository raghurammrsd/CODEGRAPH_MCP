from pathlib import Path

from codegraph.context import get_context
from codegraph.indexing.indexer import Indexer


def test_get_context_budget_tokens() -> None:
    repo = Path(".")
    indexer = Indexer(repo)
    with indexer.session() as con:
        # Test default max_tokens vs strict budget_tokens
        pkt_normal = get_context(con, repo, query="Indexer.index", max_tokens=10000)
        assert pkt_normal is not None

        pkt_budget = get_context(con, repo, query="Indexer.index", budget_tokens=1200)
        assert pkt_budget is not None
        assert pkt_budget.budget is not None
        assert pkt_budget.budget["budget_limit"] <= 1200
        assert pkt_budget.budget["selected_tokens"] <= 1200
