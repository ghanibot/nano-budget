from __future__ import annotations
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class BudgetStore:
    def __init__(self, path: str = "~/.nano-budget"):
        db_dir = Path(path).expanduser()
        db_dir.mkdir(parents=True, exist_ok=True)
        self._db = str(db_dir / "budget.db")
        self._conn = sqlite3.connect(self._db, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS usage (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ts              REAL NOT NULL,
                source          TEXT NOT NULL,   -- which nano-eco component
                agent_id        TEXT DEFAULT '',
                session_id      TEXT DEFAULT '',
                provider        TEXT DEFAULT '',
                model           TEXT DEFAULT '',
                input_tokens    INTEGER DEFAULT 0,
                output_tokens   INTEGER DEFAULT 0,
                cost_usd        REAL DEFAULT 0.0,
                meta            TEXT DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_usage_ts     ON usage(ts DESC);
            CREATE INDEX IF NOT EXISTS idx_usage_source ON usage(source);
            CREATE INDEX IF NOT EXISTS idx_usage_agent  ON usage(agent_id);
            CREATE INDEX IF NOT EXISTS idx_usage_session ON usage(session_id);

            CREATE TABLE IF NOT EXISTS budgets (
                scope       TEXT PRIMARY KEY,   -- "global", "agent:ceo", "session:xyz"
                limit_usd   REAL,
                limit_tokens INTEGER,
                alert_at    REAL DEFAULT 0.8,   -- alert when 80% consumed
                created_at  REAL NOT NULL
            );
        """)
        self._conn.commit()

    def record(
        self,
        source: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        agent_id: str = "",
        session_id: str = "",
        provider: str = "",
        model: str = "",
        meta: Optional[Dict] = None,
    ) -> int:
        cur = self._conn.execute(
            """INSERT INTO usage
               (ts, source, agent_id, session_id, provider, model,
                input_tokens, output_tokens, cost_usd, meta)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (time.time(), source, agent_id, session_id, provider, model,
             input_tokens, output_tokens, cost_usd, json.dumps(meta or {}))
        )
        self._conn.commit()
        return cur.lastrowid

    def totals(
        self,
        since_ts: float = 0.0,
        agent_id: str = "",
        session_id: str = "",
        source: str = "",
    ) -> Dict[str, Any]:
        conditions = ["ts >= ?"]
        params: List[Any] = [since_ts]
        if agent_id:
            conditions.append("agent_id = ?"); params.append(agent_id)
        if session_id:
            conditions.append("session_id = ?"); params.append(session_id)
        if source:
            conditions.append("source = ?"); params.append(source)

        where = " AND ".join(conditions)
        row = self._conn.execute(
            f"SELECT SUM(input_tokens) as i, SUM(output_tokens) as o, "
            f"SUM(cost_usd) as c, COUNT(*) as n FROM usage WHERE {where}",
            params
        ).fetchone()

        return {
            "input_tokens":  row["i"] or 0,
            "output_tokens": row["o"] or 0,
            "total_tokens":  (row["i"] or 0) + (row["o"] or 0),
            "cost_usd":      round(row["c"] or 0.0, 6),
            "calls":         row["n"] or 0,
        }

    def by_source(self, since_ts: float = 0.0) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT source,
                      SUM(input_tokens) as i, SUM(output_tokens) as o,
                      SUM(cost_usd) as c, COUNT(*) as n
               FROM usage WHERE ts >= ?
               GROUP BY source ORDER BY c DESC""",
            (since_ts,)
        ).fetchall()
        return [{"source": r["source"], "input_tokens": r["i"], "output_tokens": r["o"],
                 "cost_usd": round(r["c"] or 0, 6), "calls": r["n"]} for r in rows]

    def by_agent(self, since_ts: float = 0.0) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT agent_id,
                      SUM(input_tokens) as i, SUM(output_tokens) as o,
                      SUM(cost_usd) as c, COUNT(*) as n
               FROM usage WHERE ts >= ? AND agent_id != ''
               GROUP BY agent_id ORDER BY c DESC""",
            (since_ts,)
        ).fetchall()
        return [{"agent_id": r["agent_id"], "input_tokens": r["i"], "output_tokens": r["o"],
                 "cost_usd": round(r["c"] or 0, 6), "calls": r["n"]} for r in rows]

    def by_model(self, since_ts: float = 0.0) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT model, provider,
                      SUM(input_tokens) as i, SUM(output_tokens) as o,
                      SUM(cost_usd) as c, COUNT(*) as n
               FROM usage WHERE ts >= ? AND model != ''
               GROUP BY model ORDER BY c DESC""",
            (since_ts,)
        ).fetchall()
        return [{"model": r["model"], "provider": r["provider"], "input_tokens": r["i"],
                 "output_tokens": r["o"], "cost_usd": round(r["c"] or 0, 6), "calls": r["n"]}
                for r in rows]

    def set_budget(self, scope: str, limit_usd: Optional[float] = None,
                   limit_tokens: Optional[int] = None, alert_at: float = 0.8) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO budgets (scope, limit_usd, limit_tokens, alert_at, created_at) VALUES (?,?,?,?,?)",
            (scope, limit_usd, limit_tokens, alert_at, time.time())
        )
        self._conn.commit()

    def get_budget(self, scope: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute("SELECT * FROM budgets WHERE scope=?", (scope,)).fetchone()
        if not row:
            return None
        return dict(row)
