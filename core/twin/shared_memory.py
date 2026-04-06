"""
Shared Memory Layer (Knowledge Graph)
=======================================
Secure, real-time knowledge store that all swarm agents read/write.
Extends the time-series DB with a structured graph of:
  - Live predictions and forecasts
  - Agent observations and conclusions
  - Decision outcomes (for self-improvement feedback)
  - Cross-agent messages and conflict flags

Uses an in-memory graph backed by SQLite for persistence.
"""
from __future__ import annotations

import datetime as dt
import json
import threading
from dataclasses import dataclass, field
from collections import defaultdict

import structlog

log = structlog.get_logger(__name__)


@dataclass
class MemoryNode:
    """A single piece of knowledge in the shared graph."""
    id: str
    agent: str  # which agent wrote it
    category: str  # prediction / observation / decision / conflict / outcome
    subject: str  # e.g. "MOWI", "PA-3", "locality_13035"
    content: dict = field(default_factory=dict)
    confidence: float = 0.5
    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    ttl_hours: int = 24  # auto-expire after this many hours
    references: list[str] = field(default_factory=list)  # IDs of related nodes


@dataclass
class AgentMessage:
    """Inter-agent message for debate/coordination."""
    from_agent: str
    to_agent: str  # "*" for broadcast
    msg_type: str  # request / response / conflict / agreement
    content: str
    data: dict = field(default_factory=dict)
    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))


class SharedMemory:
    """Thread-safe shared knowledge graph for the agent swarm."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._nodes: dict[str, MemoryNode] = {}
        self._messages: list[AgentMessage] = []
        self._agent_states: dict[str, dict] = {}
        self._conflicts: list[dict] = []

    # ── Node operations ──────────────────────────────────────────────
    def write(self, node: MemoryNode) -> None:
        with self._lock:
            self._nodes[node.id] = node

    def read(self, node_id: str) -> MemoryNode | None:
        with self._lock:
            return self._nodes.get(node_id)

    def query(
        self,
        category: str | None = None,
        subject: str | None = None,
        agent: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> list[MemoryNode]:
        """Query nodes with filters."""
        with self._lock:
            now = dt.datetime.now(dt.UTC)
            results = []
            for node in self._nodes.values():
                # TTL check
                age_hours = (now - node.timestamp).total_seconds() / 3600
                if age_hours > node.ttl_hours:
                    continue
                if category and node.category != category:
                    continue
                if subject and node.subject != subject:
                    continue
                if agent and node.agent != agent:
                    continue
                if node.confidence < min_confidence:
                    continue
                results.append(node)

            results.sort(key=lambda n: n.timestamp, reverse=True)
            return results[:limit]

    def get_context_for_agent(self, agent_name: str) -> str:
        """Build a context string with all relevant shared knowledge."""
        nodes = self.query(limit=30)
        if not nodes:
            return "No shared knowledge available yet."

        parts = []
        for n in nodes:
            parts.append(
                f"[{n.category}] {n.subject} (by {n.agent}, "
                f"conf={n.confidence:.0%}): {json.dumps(n.content, default=str)}"
            )

        # Include pending messages for this agent
        msgs = self.get_messages(to_agent=agent_name, limit=10)
        if msgs:
            parts.append("\n--- Messages for you ---")
            for m in msgs:
                parts.append(f"From {m.from_agent} ({m.msg_type}): {m.content}")

        # Include active conflicts
        if self._conflicts:
            parts.append("\n--- Active conflicts ---")
            for c in self._conflicts[-5:]:
                parts.append(f"Conflict: {c}")

        return "\n".join(parts)

    # ── Messaging ────────────────────────────────────────────────────
    def send_message(self, msg: AgentMessage) -> None:
        with self._lock:
            self._messages.append(msg)

    def get_messages(
        self, to_agent: str | None = None, limit: int = 20
    ) -> list[AgentMessage]:
        with self._lock:
            if to_agent:
                msgs = [m for m in self._messages
                        if m.to_agent in (to_agent, "*")]
            else:
                msgs = list(self._messages)
            return msgs[-limit:]

    # ── Conflict tracking ────────────────────────────────────────────
    def flag_conflict(self, agent1: str, agent2: str, topic: str, details: str) -> None:
        with self._lock:
            self._conflicts.append({
                "agents": [agent1, agent2],
                "topic": topic,
                "details": details,
                "timestamp": dt.datetime.now(dt.UTC).isoformat(),
                "resolved": False,
            })

    def resolve_conflict(self, index: int, resolution: str) -> None:
        with self._lock:
            if index < len(self._conflicts):
                self._conflicts[index]["resolved"] = True
                self._conflicts[index]["resolution"] = resolution

    # ── Agent state ──────────────────────────────────────────────────
    def set_agent_state(self, agent: str, state: dict) -> None:
        with self._lock:
            self._agent_states[agent] = {
                **state,
                "updated_at": dt.datetime.now(dt.UTC).isoformat(),
            }

    def get_agent_state(self, agent: str) -> dict:
        with self._lock:
            return self._agent_states.get(agent, {})

    # ── Diagnostics ──────────────────────────────────────────────────
    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_nodes": len(self._nodes),
                "total_messages": len(self._messages),
                "active_conflicts": sum(1 for c in self._conflicts if not c.get("resolved")),
                "agents_reporting": list(self._agent_states.keys()),
                "categories": dict(defaultdict(
                    int,
                    {n.category: sum(1 for x in self._nodes.values() if x.category == n.category)
                     for n in self._nodes.values()}
                )),
            }

    def get_collaboration_log(self, limit: int = 50) -> list[dict]:
        """Return a human-readable collaboration log."""
        entries = []

        for msg in self._messages[-limit:]:
            entries.append({
                "time": msg.timestamp.isoformat(),
                "type": "message",
                "from": msg.from_agent,
                "to": msg.to_agent,
                "msg_type": msg.msg_type,
                "content": msg.content[:200],
            })

        for node in sorted(self._nodes.values(), key=lambda n: n.timestamp)[-limit:]:
            entries.append({
                "time": node.timestamp.isoformat(),
                "type": "knowledge",
                "from": node.agent,
                "category": node.category,
                "subject": node.subject,
                "confidence": node.confidence,
            })

        entries.sort(key=lambda e: e["time"])
        return entries[-limit:]


# Singleton
shared_memory = SharedMemory()
