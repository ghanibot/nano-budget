import tempfile
from nano_budget import Budget, BudgetExceededError, estimate_cost


def make_budget():
    return Budget(path=tempfile.mkdtemp())


def test_record_and_total():
    b = make_budget()
    b.record("nano-agent", input_tokens=1000, output_tokens=500,
             model="claude-haiku-4-5-20251001", provider="anthropic", agent_id="ceo")
    b.record("nano-tools", input_tokens=200, output_tokens=100,
             model="claude-haiku-4-5-20251001", provider="anthropic", agent_id="ceo")
    t = b.total()
    assert t["input_tokens"] == 1200
    assert t["output_tokens"] == 600
    assert t["calls"] == 2
    assert t["cost_usd"] > 0
    print(f"PASS: record + total (cost=${t['cost_usd']:.6f})")


def test_by_source():
    b = make_budget()
    b.record("nano-agent", input_tokens=500, output_tokens=200, model="gpt-4o-mini", provider="openai")
    b.record("nano-tools", input_tokens=100, output_tokens=50, model="gpt-4o-mini", provider="openai")
    b.record("nano-eval",  input_tokens=300, output_tokens=150, model="gpt-4o-mini", provider="openai")
    rows = b.by_source()
    sources = [r["source"] for r in rows]
    assert "nano-agent" in sources
    assert "nano-tools" in sources
    assert "nano-eval" in sources
    print("PASS: by_source")


def test_by_agent():
    b = make_budget()
    b.record("nano-agent", input_tokens=500, output_tokens=200, model="groq", agent_id="ceo")
    b.record("nano-agent", input_tokens=200, output_tokens=100, model="groq", agent_id="finance")
    rows = b.by_agent()
    ids = [r["agent_id"] for r in rows]
    assert "ceo" in ids
    assert "finance" in ids
    print("PASS: by_agent")


def test_estimate():
    cost = Budget.estimate("claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
    assert abs(cost - (0.80 + 4.00)) < 0.01  # $0.80 input + $4.00 output
    free_cost = Budget.estimate("llama3.2", 999999, 999999, "ollama")
    assert free_cost == 0.0
    print(f"PASS: estimate (haiku 1M+1M = ${cost:.2f})")


def test_budget_limit():
    b = make_budget()
    b.set_limit("global", limit_usd=0.000001)  # tiny limit
    try:
        b.record("nano-agent", input_tokens=10000, output_tokens=5000,
                 model="claude-opus-4-7", provider="anthropic")
        assert False, "Should have raised BudgetExceededError"
    except BudgetExceededError as e:
        assert "global" in str(e)
        print(f"PASS: budget limit enforcement ({e})")


def test_remaining():
    b = make_budget()
    b.set_limit("global", limit_usd=1.0)
    b.record("nano-agent", input_tokens=100, output_tokens=50,
             model="gpt-4o-mini", provider="openai")
    r = b.remaining("global")
    assert r["limit_usd"] == 1.0
    assert r["remaining_usd"] < 1.0
    assert r["used_usd"] > 0
    print(f"PASS: remaining (used ${r['used_usd']:.6f} of ${r['limit_usd']})")


if __name__ == "__main__":
    test_record_and_total()
    test_by_source()
    test_by_agent()
    test_estimate()
    test_budget_limit()
    test_remaining()
    print("\nAll tests passed")
