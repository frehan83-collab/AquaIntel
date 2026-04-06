"""
Multi-Agent LLM Swarm — Supervisor + Shared-State Architecture
===============================================================
Based on 2026 best practices from LangGraph, CrewAI, AutoGen, and OpenAI Swarm.

Architecture:
  Supervisor Agent (Orchestrator)
    ├── Farm Optimizer Agent
    ├── Supply-Chain Coordinator Agent
    ├── Market Hedger Agent
    ├── Regulatory Forecaster Agent
    ├── Narrative & Reporting Agent
    └── Self-Improvement Agent

Collaboration Protocols:
  1. Hierarchical routing (primary) — Supervisor decomposes and assigns
  2. Peer-to-peer debate — for high-uncertainty cases (confidence < 0.5)
  3. Swarm-mode parallel — for Monte Carlo simulations
  4. Post-cycle reflection — mandatory after every run

All agents share a Knowledge Graph (SharedMemory) and write observations,
predictions, and conflicts in real time.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field

import numpy as np
import structlog

from core.llm.client import llm_client
from core.twin.shared_memory import shared_memory, MemoryNode, AgentMessage
from core.twin.digital_twin import DigitalTwinEngine

log = structlog.get_logger(__name__)


# ══════════════════════════════════════════════════════════════════════
# AGENT DEFINITIONS — Role, Goal, Backstory, Tools
# ══════════════════════════════════════════════════════════════════════

@dataclass
class AgentSpec:
    name: str
    role: str
    goal: str
    backstory: str
    tools: list[str]
    system_prompt: str


AGENT_SPECS: dict[str, AgentSpec] = {
    "farm_optimizer": AgentSpec(
        name="farm_optimizer",
        role="Senior Aquaculture Biologist & Operations Optimizer",
        goal="Minimize lice impact and treatment costs while maximizing fish welfare and growth across all farms.",
        backstory=(
            "You have 20 years of experience managing salmon farms across Norway. "
            "You understand lice biology at the stage level (sessile → motile → adult), "
            "the tradeoffs between mechanical, thermal, and medicinal treatments, "
            "and how cleaner fish interact with lice populations. You think in terms of "
            "production cycles, degree-days, and regulatory compliance windows."
        ),
        tools=["twin_state", "lice_forecasts", "treatment_history", "cleaner_fish_data"],
        system_prompt=(
            "You are the Farm Optimizer in a multi-agent aquaculture intelligence system. "
            "Analyze per-farm lice data, biomass state, and treatment history. "
            "Recommend: (1) which farms need treatment and when, (2) treatment type "
            "(mechanical/thermal/medicinal/cleaner-fish), (3) harvest timing adjustments, "
            "(4) cleaner-fish deployment. Always quantify cost vs benefit in NOK. "
            "Flag any conflicts with other agents' recommendations."
        ),
    ),
    "supply_coordinator": AgentSpec(
        name="supply_coordinator",
        role="Supply Chain Director & Volume Planner",
        goal="Ensure smooth, predictable supply of salmon to processors and exporters, avoiding gluts and shortfalls.",
        backstory=(
            "You coordinate harvest schedules across multiple companies and production areas. "
            "You know that Norwegian processors need predictable weekly volumes (30-35kt HOG). "
            "Lice-driven treatment delays, forced early harvests, and quality downgrades "
            "all disrupt supply. You balance immediate farm needs against contract commitments."
        ),
        tools=["twin_state", "supply_forecasts", "contract_data", "regional_capacity"],
        system_prompt=(
            "You are the Supply Chain Coordinator. Analyze production forecasts and "
            "farm optimizer recommendations to project weekly/monthly harvest volumes by "
            "production area. Flag: (1) supply shortfall risks, (2) contract breach probability, "
            "(3) quality grade shifts, (4) recommended harvest schedule adjustments. "
            "Coordinate with Farm Optimizer to align treatment timing with supply needs."
        ),
    ),
    "market_hedger": AgentSpec(
        name="market_hedger",
        role="Quantitative Analyst & Commodity Trader",
        goal="Translate production risk into market positioning advice for salmon futures and equities.",
        backstory=(
            "You are a quant with deep knowledge of Oslo Bors salmon equities (MOWI, SALM, LSG, GSF), "
            "Fish Pool salmon futures, and the statistical relationship between lice events and "
            "stock/commodity price movements. You think in terms of expected moves, confidence "
            "intervals, and risk/reward ratios."
        ),
        tools=["twin_state", "harvest_impacts", "price_correlations", "signal_history"],
        system_prompt=(
            "You are the Market Hedger. Given production forecasts and supply chain impacts, "
            "generate: (1) directional views on salmon spot/forward prices, (2) equity impact "
            "estimates (MOWI/SALM/LSG/GSF), (3) suggested hedging strategies with entry/exit. "
            "Always include confidence level and the disclaimer: 'Not financial advice. "
            "All signals require explicit user consent before execution.' "
            "Coordinate with Supply Coordinator on volume estimates."
        ),
    ),
    "regulatory_forecaster": AgentSpec(
        name="regulatory_forecaster",
        role="Regulatory Affairs Specialist & Policy Analyst",
        goal="Predict regulatory changes and ensure proactive compliance across all operations.",
        backstory=(
            "You track Norwegian aquaculture regulations obsessively — the 0.5 lice limit, "
            "traffic-light system (PA colors), Mattilsynet enforcement patterns, treatment "
            "restrictions, and ESG reporting requirements. You understand that a PA color "
            "downgrade from green to yellow, or yellow to red, can cost companies millions "
            "in lost growth permits."
        ),
        tools=["twin_state", "lice_trends", "pa_color_history", "regulation_database"],
        system_prompt=(
            "You are the Regulatory Forecaster. Analyze current lice levels and trends by "
            "production area to predict: (1) which PAs are at risk of traffic-light color change, "
            "(2) probability and timeline of regulatory enforcement actions, (3) compliance gaps "
            "at specific farms, (4) impact of potential new regulations. "
            "Alert the Farm Optimizer about compliance deadlines."
        ),
    ),
    "narrative_reporter": AgentSpec(
        name="narrative_reporter",
        role="Communications Director & Report Writer",
        goal="Produce clear, stakeholder-specific reports that translate complex multi-agent analysis into actionable briefings.",
        backstory=(
            "You are an expert at translating technical aquaculture and financial analysis "
            "into clear language for different audiences: farm managers want action items, "
            "buyers want volume/quality forecasts, investors want risk/return metrics, "
            "regulators want compliance data."
        ),
        tools=["swarm_results", "twin_state", "all_agent_outputs"],
        system_prompt=(
            "You are the Narrative Reporter. After all other agents have completed their analysis, "
            "synthesize their findings into stakeholder-specific briefings: "
            "(1) Farmer brief: treatment actions + harvest timing, "
            "(2) Buyer memo: supply volume + quality + contract risk, "
            "(3) Investor summary: market signals + risk/reward, "
            "(4) Regulatory report: compliance status + PA risk. "
            "Include accuracy caveats and horizon-specific confidence levels."
        ),
    ),
    "self_improvement": AgentSpec(
        name="self_improvement",
        role="Machine Learning Engineer & Platform Architect",
        goal="Continuously improve prediction accuracy and platform capabilities by learning from outcomes.",
        backstory=(
            "You monitor the platform's prediction accuracy, identify systematic errors, "
            "and propose concrete improvements. You have access to all historical predictions "
            "and their actual outcomes. You think in terms of MAE, R², bias, and feature importance."
        ),
        tools=["prediction_history", "accuracy_metrics", "model_parameters"],
        system_prompt=(
            "You are the Self-Improvement Agent. Run post-cycle reflection: "
            "(1) Compare recent predictions vs actual outcomes, "
            "(2) Identify systematic biases by company/PA/season, "
            "(3) Propose specific parameter adjustments or new covariates, "
            "(4) Rate each proposal by expected improvement and implementation effort. "
            "Only auto-apply trivial fixes; flag everything else for human review."
        ),
    ),
}


# ══════════════════════════════════════════════════════════════════════
# SUPERVISOR AGENT
# ══════════════════════════════════════════════════════════════════════

SUPERVISOR_PROMPT = """You are the Supervisor Agent orchestrating a multi-agent aquaculture intelligence system.

YOUR AGENTS:
{agent_roster}

SHARED KNOWLEDGE:
{shared_context}

TASK: {task}

Your job:
1. DECOMPOSE the task into sub-tasks for specific agents
2. ASSIGN each sub-task to the best agent (by role and tools)
3. SPECIFY the execution order (which agents run in parallel, which sequentially)
4. After receiving results, IDENTIFY conflicts between agents
5. If conflicts exist, trigger a DEBATE between the conflicting agents
6. SYNTHESIZE the final plan with ranked actions and confidence scores

Respond in JSON:
{{
  "plan": [
    {{"agent": "agent_name", "task": "specific sub-task", "depends_on": [], "parallel": true/false}},
    ...
  ],
  "reasoning": "why this decomposition",
  "expected_conflicts": ["potential disagreements to watch for"]
}}"""


class SupervisorAgent:
    """Central orchestrator that decomposes tasks and coordinates the swarm."""

    def __init__(self) -> None:
        self.execution_log: list[dict] = []

    async def plan(self, task: str) -> list[dict]:
        """Decompose a task into agent assignments."""
        roster = "\n".join(
            f"- {spec.name} ({spec.role}): {spec.goal}"
            for spec in AGENT_SPECS.values()
        )

        context = shared_memory.get_context_for_agent("supervisor")

        prompt = SUPERVISOR_PROMPT.format(
            agent_roster=roster,
            shared_context=context[:2000],
            task=task,
        )

        resp = await llm_client.complete(
            prompt=prompt,
            system="You are a supervisor agent coordinating an aquaculture intelligence swarm. Be precise and structured.",
            max_tokens=1500,
            temperature=0.2,
        )

        # Parse plan
        try:
            start = resp.content.find("{")
            end = resp.content.rfind("}") + 1
            if start >= 0 and end > start:
                plan_data = json.loads(resp.content[start:end])
                plan = plan_data.get("plan", [])
            else:
                plan = [{"agent": "farm_optimizer", "task": task, "depends_on": [], "parallel": False}]
        except json.JSONDecodeError:
            plan = [{"agent": "farm_optimizer", "task": task, "depends_on": [], "parallel": False}]

        self.execution_log.append({
            "time": dt.datetime.now(dt.UTC).isoformat(),
            "type": "plan",
            "task": task,
            "assignments": len(plan),
        })

        return plan


# ══════════════════════════════════════════════════════════════════════
# SPECIALIZED AGENT RUNNER
# ══════════════════════════════════════════════════════════════════════

class SpecializedAgent:
    """Runs a single specialized agent with shared memory access."""

    def __init__(self, spec: AgentSpec) -> None:
        self.spec = spec

    async def execute(self, task: str, twin_context: str) -> dict:
        """Execute the agent's task and write results to shared memory."""
        # Build context from shared memory
        shared_ctx = shared_memory.get_context_for_agent(self.spec.name)

        prompt = f"""ROLE: {self.spec.role}
GOAL: {self.spec.goal}
BACKSTORY: {self.spec.backstory}

DIGITAL TWIN STATE:
{twin_context[:2000]}

SHARED KNOWLEDGE FROM OTHER AGENTS:
{shared_ctx[:1500]}

YOUR TASK: {task}

Respond with:
1. OBSERVATIONS: Key data points you noticed
2. ANALYSIS: Your reasoning
3. ACTIONS: JSON array of recommended actions:
   [{{"action": "...", "target": "...", "priority": "critical|high|medium|low",
     "expected_impact": "...", "confidence": 0.0-1.0, "rationale": "..."}}]
4. CONFLICTS: Any disagreements with other agents' conclusions
5. CONFIDENCE: Your overall confidence in this analysis (0-100%)"""

        resp = await llm_client.complete(
            prompt=prompt,
            system=self.spec.system_prompt,
            max_tokens=2000,
            temperature=0.3,
        )

        # Parse actions — handle markdown code blocks and nested JSON
        actions = self._parse_actions(resp.content)

        # Write to shared memory
        shared_memory.write(MemoryNode(
            id=f"{self.spec.name}_{dt.datetime.now(dt.UTC).strftime('%H%M%S')}",
            agent=self.spec.name,
            category="observation",
            subject=task[:50],
            content={
                "full_response": resp.content[:1000],
                "actions": actions,
                "task": task,
            },
            confidence=self._extract_confidence(resp.content),
        ))

        # Update agent state
        shared_memory.set_agent_state(self.spec.name, {
            "status": "completed",
            "last_task": task,
            "actions_count": len(actions),
        })

        # Send broadcast message
        shared_memory.send_message(AgentMessage(
            from_agent=self.spec.name,
            to_agent="*",
            msg_type="response",
            content=f"Completed analysis: {len(actions)} actions recommended",
            data={"actions": actions},
        ))

        return {
            "agent": self.spec.name,
            "role": self.spec.role,
            "response": resp.content,
            "actions": actions,
            "tokens": resp.input_tokens + resp.output_tokens,
            "cost_usd": resp.cost_usd,
        }

    @staticmethod
    def _parse_actions(content: str) -> list[dict]:
        """Robustly extract action JSON from LLM response, handling markdown."""
        import re

        # Strip markdown code blocks
        cleaned = re.sub(r'```json\s*', '', content)
        cleaned = re.sub(r'```\s*', '', cleaned)

        # Try all JSON arrays in the text
        for match in re.finditer(r'\[[\s\S]*?\]', cleaned):
            try:
                candidate = json.loads(match.group())
                if isinstance(candidate, list) and len(candidate) > 0:
                    # Verify it looks like action objects
                    if isinstance(candidate[0], dict) and any(
                        k in candidate[0] for k in ("action", "target", "priority")
                    ):
                        return candidate
            except (json.JSONDecodeError, ValueError):
                continue

        # Fallback: try to find individual action objects
        actions = []
        for match in re.finditer(r'\{[^{}]*"action"[^{}]*\}', cleaned):
            try:
                obj = json.loads(match.group())
                actions.append(obj)
            except (json.JSONDecodeError, ValueError):
                continue

        return actions

    @staticmethod
    def _extract_confidence(text: str) -> float:
        """Extract confidence percentage from agent response."""
        import re
        matches = re.findall(r'(?:confidence|Confidence)[:\s]*(\d+)\s*%', text)
        if matches:
            return min(float(matches[-1]) / 100, 1.0)
        return 0.5


# ══════════════════════════════════════════════════════════════════════
# DEBATE PROTOCOL
# ══════════════════════════════════════════════════════════════════════

async def run_debate(
    agent_a: str,
    agent_b: str,
    topic: str,
    context: str,
) -> dict:
    """
    Peer-to-peer debate between two agents on a contested topic.
    Each agent makes a case, then a resolution is synthesized.
    """
    spec_a = AGENT_SPECS[agent_a]
    spec_b = AGENT_SPECS[agent_b]

    # Agent A argues
    resp_a = await llm_client.complete(
        prompt=f"As {spec_a.role}, argue your position on: {topic}\nContext: {context}",
        system=spec_a.system_prompt,
        max_tokens=800,
    )

    # Agent B responds
    resp_b = await llm_client.complete(
        prompt=(
            f"As {spec_b.role}, respond to this argument from {spec_a.role}:\n"
            f'"{resp_a.content[:500]}"\n\nTopic: {topic}\nContext: {context}'
        ),
        system=spec_b.system_prompt,
        max_tokens=800,
    )

    # Resolution by supervisor
    resolution = await llm_client.complete(
        prompt=(
            f"Two experts disagree on: {topic}\n\n"
            f"{spec_a.role} argues: {resp_a.content[:400]}\n\n"
            f"{spec_b.role} argues: {resp_b.content[:400]}\n\n"
            f"Synthesize the best decision, noting which expert's view should dominate and why."
        ),
        system="You are a neutral arbiter. Make the best decision based on evidence.",
        max_tokens=600,
    )

    # Log to shared memory
    shared_memory.flag_conflict(agent_a, agent_b, topic, "Debate triggered")
    shared_memory.resolve_conflict(-1, resolution.content[:200])

    shared_memory.send_message(AgentMessage(
        from_agent="supervisor",
        to_agent="*",
        msg_type="resolution",
        content=f"Debate resolved on '{topic}': {resolution.content[:200]}",
    ))

    return {
        "topic": topic,
        "agent_a": {"name": agent_a, "argument": resp_a.content},
        "agent_b": {"name": agent_b, "argument": resp_b.content},
        "resolution": resolution.content,
    }


# ══════════════════════════════════════════════════════════════════════
# REFLECTION PROTOCOL
# ══════════════════════════════════════════════════════════════════════

async def run_reflection(swarm_results: list[dict]) -> dict:
    """
    Post-cycle reflection: analyze the swarm's outputs for quality and consistency.
    """
    summary = "\n".join(
        f"{r['agent']}: {len(r.get('actions', []))} actions, "
        f"response length={len(r.get('response', ''))}"
        for r in swarm_results
    )

    all_actions = []
    for r in swarm_results:
        for a in r.get("actions", []):
            all_actions.append(f"[{r['agent']}] {a.get('action', '')} ({a.get('priority', '')})")

    resp = await llm_client.complete(
        prompt=(
            f"REFLECTION: Analyze this swarm cycle for quality and consistency.\n\n"
            f"Agents that ran:\n{summary}\n\n"
            f"All recommended actions:\n" + "\n".join(all_actions[:20]) + "\n\n"
            f"Check for: (1) contradictions, (2) missing perspectives, "
            f"(3) unrealistic recommendations, (4) confidence calibration issues. "
            f"Provide a brief quality assessment and any corrections needed."
        ),
        system="You are a quality reviewer for a multi-agent system. Be critical but constructive.",
        max_tokens=800,
    )

    shared_memory.write(MemoryNode(
        id=f"reflection_{dt.datetime.now(dt.UTC).strftime('%H%M%S')}",
        agent="supervisor",
        category="reflection",
        subject="cycle_quality",
        content={"assessment": resp.content, "agents_reviewed": len(swarm_results)},
        confidence=0.8,
        ttl_hours=48,
    ))

    return {"assessment": resp.content, "actions_reviewed": len(all_actions)}


# ══════════════════════════════════════════════════════════════════════
# SWARM ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════

@dataclass
class SwarmResult:
    """Complete output from a swarm run."""
    scenario: str
    generated_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    supervisor_plan: list[dict] = field(default_factory=list)
    agent_results: list[dict] = field(default_factory=list)
    debates: list[dict] = field(default_factory=list)
    reflection: dict = field(default_factory=dict)
    collaboration_log: list[dict] = field(default_factory=list)
    total_actions: int = 0
    total_cost_usd: float = 0.0
    total_tokens: int = 0


class AgentSwarm:
    """Full swarm orchestrator with supervisor pattern."""

    def __init__(self, twin: DigitalTwinEngine) -> None:
        self.twin = twin
        self.supervisor = SupervisorAgent()
        self.agents = {
            name: SpecializedAgent(spec)
            for name, spec in AGENT_SPECS.items()
        }

    async def run_swarm(
        self,
        scenario: str = "Optimize current operations",
        agents_to_run: list[str] | None = None,
    ) -> SwarmResult:
        """Run the full supervisor → agents → debate → reflection cycle."""
        log.info("swarm.start", scenario=scenario)
        result = SwarmResult(scenario=scenario)

        # Build twin context
        twin_ctx = json.dumps(self.twin.get_summary(), indent=2, default=str)

        # ── Step 1: Supervisor decomposes task ───────────────────────
        plan = await self.supervisor.plan(scenario)
        result.supervisor_plan = plan

        shared_memory.send_message(AgentMessage(
            from_agent="supervisor",
            to_agent="*",
            msg_type="request",
            content=f"New task: {scenario}. Assigned {len(plan)} sub-tasks.",
        ))

        # ── Step 2: Execute agents (respecting dependencies) ────────
        selected = agents_to_run or [p["agent"] for p in plan]
        # Deduplicate while preserving order
        seen = set()
        selected = [a for a in selected if a not in seen and not seen.add(a)]

        for agent_name in selected:
            agent = self.agents.get(agent_name)
            if not agent:
                continue

            # Find task for this agent from plan
            agent_task = scenario  # default
            for p in plan:
                if p.get("agent") == agent_name:
                    agent_task = p.get("task", scenario)
                    break

            try:
                agent_result = await agent.execute(agent_task, twin_ctx)
                result.agent_results.append(agent_result)
                result.total_cost_usd += agent_result.get("cost_usd", 0)
                result.total_tokens += agent_result.get("tokens", 0)
            except Exception as exc:
                log.warning("swarm.agent_error", agent=agent_name, error=str(exc))
                result.agent_results.append({
                    "agent": agent_name,
                    "error": str(exc),
                    "actions": [],
                })

        # ── Step 3: Detect conflicts and run debates ─────────────────
        conflicts = self._detect_conflicts(result.agent_results)
        for conflict in conflicts[:2]:  # max 2 debates per cycle
            debate = await run_debate(
                conflict["agent_a"],
                conflict["agent_b"],
                conflict["topic"],
                twin_ctx[:1000],
            )
            result.debates.append(debate)

        # ── Step 4: Post-cycle reflection ────────────────────────────
        if result.agent_results:
            result.reflection = await run_reflection(result.agent_results)

        # ── Aggregate ────────────────────────────────────────────────
        result.total_actions = sum(
            len(r.get("actions", [])) for r in result.agent_results
        )
        result.collaboration_log = shared_memory.get_collaboration_log(50)

        log.info(
            "swarm.done",
            agents=len(result.agent_results),
            actions=result.total_actions,
            debates=len(result.debates),
            cost=f"${result.total_cost_usd:.3f}",
        )

        return result

    async def run_monte_carlo(
        self,
        scenario: str,
        n_simulations: int = 100,
        horizon_weeks: int = 12,
    ) -> dict:
        """Run Monte Carlo through the digital twin (no LLM calls)."""
        log.info("swarm.monte_carlo", n=n_simulations, horizon=horizon_weeks)

        results = []
        for i in range(n_simulations):
            forked = self.twin.fork()

            treat_prob = np.random.uniform(0.1, 0.5)
            temp_delta = np.random.normal(0, 0.5)
            treat_locs = [
                ln for ln, t in forked.items()
                if t.lice.adult_female > 0.3 and np.random.random() < treat_prob
            ]

            sim = self.twin.simulate_step(forked, weeks=horizon_weeks, interventions={
                "treat_localities": treat_locs,
                "treatment_type": np.random.choice(["mechanical", "thermal"]),
                "temp_delta_c": temp_delta,
            })

            avg_lice = np.mean([t.lice.adult_female for t in sim.values()])
            total_biomass = sum(t.estimated_biomass_tonnes for t in sim.values())
            above = sum(1 for t in sim.values() if t.lice.adult_female > 0.5)

            results.append({
                "avg_lice": avg_lice,
                "total_biomass": total_biomass,
                "above_threshold": above,
                "treatments": len(treat_locs),
            })

        lice_arr = np.array([r["avg_lice"] for r in results])
        bio_arr = np.array([r["total_biomass"] for r in results])

        return {
            "n_simulations": n_simulations,
            "horizon_weeks": horizon_weeks,
            "avg_lice_mean": round(float(np.mean(lice_arr)), 4),
            "avg_lice_p5": round(float(np.percentile(lice_arr, 5)), 4),
            "avg_lice_p95": round(float(np.percentile(lice_arr, 95)), 4),
            "biomass_mean": round(float(np.mean(bio_arr)), 0),
            "biomass_p5": round(float(np.percentile(bio_arr, 5)), 0),
            "biomass_p95": round(float(np.percentile(bio_arr, 95)), 0),
            "prob_crisis": round(float(np.mean(lice_arr > 0.5)), 3),
            "avg_treatments": round(float(np.mean([r["treatments"] for r in results])), 1),
        }

    @staticmethod
    def _detect_conflicts(results: list[dict]) -> list[dict]:
        """Detect contradictions between agent recommendations."""
        conflicts = []

        # Check for treat vs don't-treat conflicts
        treat_recs = {}
        for r in results:
            for action in r.get("actions", []):
                target = action.get("target", "")
                act = action.get("action", "").lower()

                if "treat" in act or "harvest" in act:
                    key = target
                    if key in treat_recs:
                        if treat_recs[key]["agent"] != r["agent"]:
                            conflicts.append({
                                "agent_a": treat_recs[key]["agent"],
                                "agent_b": r["agent"],
                                "topic": f"Conflicting recommendations for {target}",
                            })
                    treat_recs[key] = {"agent": r["agent"], "action": act}

        return conflicts
