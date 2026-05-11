from __future__ import annotations
import os
from typing import Any, Dict, List, Optional

from nano_budget.pricing import estimate_cost
from nano_budget.store.sqlite import BudgetStore


class BudgetExceededError(Exception):
    def __init__(self, scope: str, used: float, limit: float):
        self.scope = scope
        self.used = used
        self.limit = limit
        super().__init__(f"Budget exceeded for '{scope}': ${used:.6f} / ${limit:.6f}")


class Budget:
    """
    nano-budget: track token + cost spending across ALL nano-eco components.

    Every nano-eco project (agent, tools, eval, memory, flow) calls
    budget.record() when it uses tokens. Budget aggregates everything
    into one SQLite store with full drill-down by source/agent/model/session.

    Usage:
        budget = Budget()

        # Record a call from any component
        budget.record("nano-agent", input_tokens=150, output_tokens=80,
                      model="claude-haiku-4-5-20251001", provider="anthropic",
                      agent_id="ceo", session_id="session_abc")

        # Get totals
        print(budget.total())           # all time
        print(budget.today())           # today only
        print(budget.by_source())       # breakdown by component
        print(budget.by_agent())        # breakdown by agent
    """

    def __init__(self, path: str = "~/.nano-budget"):
        resolved = os.environ.get("NANO_BUDGET_PATH", path)
        self._store = BudgetStore(resolved)

    # ── Recording ─────────────────────────────────────────────────────────────

    def record(
        self,
        source: str,                    # "nano-agent", "nano-tools", "nano-eval", etc.
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = "",
        provider: str = "",
        agent_id: str = "",
        session_id: str = "",
        cost_usd: Optional[float] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Record token usage from any nano-eco component.
        Returns cost_usd of this call.
        """
        if cost_usd is None:
            cost_usd = estimate_cost(model, input_tokens, output_tokens, provider)

        self._store.record(
            source=source,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            agent_id=agent_id,
            session_id=session_id,
            provider=provider,
            model=model,
            meta=meta,
        )

        # Check budgets
        self._check_budget("global", agent_id, session_id)
        if agent_id:
            self._check_budget(f"agent:{agent_id}", agent_id, session_id)
        if session_id:
            self._check_budget(f"session:{session_id}", agent_id, session_id)

        return cost_usd

    # ── Totals ────────────────────────────────────────────────────────────────

    def total(self) -> Dict[str, Any]:
        return self._store.totals()

    def today(self) -> Dict[str, Any]:
        import datetime
        since = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        return self._store.totals(since_ts=since)

    def session(self, session_id: str) -> Dict[str, Any]:
        return self._store.totals(session_id=session_id)

    def agent(self, agent_id: str) -> Dict[str, Any]:
        return self._store.totals(agent_id=agent_id)

    def source(self, source: str) -> Dict[str, Any]:
        return self._store.totals(source=source)

    # ── Breakdowns ────────────────────────────────────────────────────────────

    def by_source(self, today_only: bool = False) -> List[Dict[str, Any]]:
        since = self._today_ts() if today_only else 0.0
        return self._store.by_source(since_ts=since)

    def by_agent(self, today_only: bool = False) -> List[Dict[str, Any]]:
        since = self._today_ts() if today_only else 0.0
        return self._store.by_agent(since_ts=since)

    def by_model(self, today_only: bool = False) -> List[Dict[str, Any]]:
        since = self._today_ts() if today_only else 0.0
        return self._store.by_model(since_ts=since)

    # ── Budget Limits ─────────────────────────────────────────────────────────

    def set_limit(
        self,
        scope: str = "global",          # "global", "agent:ceo", "session:xyz"
        limit_usd: Optional[float] = None,
        limit_tokens: Optional[int] = None,
        alert_at: float = 0.8,
    ) -> None:
        """Set a spending limit. Raises BudgetExceededError when exceeded."""
        self._store.set_budget(scope, limit_usd=limit_usd,
                               limit_tokens=limit_tokens, alert_at=alert_at)

    def remaining(self, scope: str = "global") -> Dict[str, Any]:
        budget = self._store.get_budget(scope)
        if not budget:
            return {"scope": scope, "no_limit": True}

        agent_id = scope.split(":", 1)[1] if scope.startswith("agent:") else ""
        session_id = scope.split(":", 1)[1] if scope.startswith("session:") else ""
        used = self._store.totals(agent_id=agent_id, session_id=session_id)

        result: Dict[str, Any] = {"scope": scope, "used_usd": used["cost_usd"],
                                   "used_tokens": used["total_tokens"]}
        if budget["limit_usd"]:
            result["limit_usd"] = budget["limit_usd"]
            result["remaining_usd"] = round(budget["limit_usd"] - used["cost_usd"], 6)
            result["pct_used"] = round(used["cost_usd"] / budget["limit_usd"] * 100, 1)
        if budget["limit_tokens"]:
            result["limit_tokens"] = budget["limit_tokens"]
            result["remaining_tokens"] = budget["limit_tokens"] - used["total_tokens"]
        return result

    def _check_budget(self, scope: str, agent_id: str, session_id: str) -> None:
        budget = self._store.get_budget(scope)
        if not budget:
            return
        aid = agent_id if scope.startswith("agent:") else ""
        sid = session_id if scope.startswith("session:") else ""
        used = self._store.totals(agent_id=aid, session_id=sid)

        if budget["limit_usd"] and used["cost_usd"] > budget["limit_usd"]:
            raise BudgetExceededError(scope, used["cost_usd"], budget["limit_usd"])
        if budget["limit_tokens"] and used["total_tokens"] > budget["limit_tokens"]:
            raise BudgetExceededError(scope, used["total_tokens"], budget["limit_tokens"])

    def _today_ts(self) -> float:
        import datetime
        return datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()

    # ── Estimate (no LLM call needed) ─────────────────────────────────────────

    @staticmethod
    def estimate(model: str, input_tokens: int, output_tokens: int, provider: str = "") -> float:
        return estimate_cost(model, input_tokens, output_tokens, provider)
