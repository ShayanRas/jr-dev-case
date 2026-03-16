"""Tests for state reducers."""

from react_agent.state import add_search_results


def test_add_search_results_appends():
    existing = [{"query": "q1", "results": ["r1"]}]
    new = [{"query": "q2", "results": ["r2"]}]
    result = add_search_results(existing, new)
    assert len(result) == 2
    assert result[1]["query"] == "q2"


def test_add_search_results_deduplicates_by_query():
    existing = [{"query": "q1", "results": ["r1"]}]
    new = [{"query": "q1", "results": ["r1_updated"]}]
    result = add_search_results(existing, new)
    assert len(result) == 1
    assert result[0]["results"] == ["r1"]  # keeps original


def test_add_search_results_empty_existing():
    result = add_search_results([], [{"query": "q1", "results": ["r1"]}])
    assert len(result) == 1


def test_add_search_results_empty_new():
    existing = [{"query": "q1", "results": ["r1"]}]
    result = add_search_results(existing, [])
    assert len(result) == 1
