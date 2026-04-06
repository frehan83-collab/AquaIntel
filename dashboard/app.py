"""
OpenClaw Dashboard — Streamlit Application
===========================================
Real-time alerts, exposure heatmaps, signal confirmation UI,
backtest results, and performance metrics.

Run: streamlit run dashboard/app.py
"""
from __future__ import annotations

import os
os.environ["PYTENSOR_FLAGS"] = "device=cpu,floatX=float64,optimizer=fast_compile,cxx="

import datetime as dt

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import select, func

from config.settings import settings
# NOTE: dashboard/app.py intentionally uses the synchronous Session.
# Streamlit's execution model is synchronous — each user interaction re-runs
# the script top-to-bottom in a single thread. Using async would require
# wrapping every DB call in asyncio.run(), adding complexity with no benefit.
# All agents and FastAPI endpoints use async get_async_session() instead.
from core.models import (
    Session, Locality, LiceRecord, CompanyExposure, Signal, Order,
    AuditLog, PerformanceFee, init_db,
)
from execution.execution_agent import ExecutionAgent
from compliance.compliance_agent import ComplianceAgent
from backtest.engine import BacktestEngine

# ── Page Config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="OpenClaw — Lice-Impact Arbitrage",
    page_icon="🦐",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

# ── Sidebar ──────────────────────────────────────────────────────────
st.sidebar.title("OpenClaw")
st.sidebar.caption("Lice-Impact Arbitrage Bot")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Algal Bloom",
        "Digital Twin",
        "AI Chat",
        "Forecast Horizon",
        "Predictions",
        "Scenarios",
        "Farmer Advisory",
        "Supply Chain",
        "Signals & Execution",
        "Exposure Map",
        "Lice Data",
        "Backtest",
        "Compliance",
        "Settings",
    ],
)

st.sidebar.markdown("---")
st.sidebar.markdown(ComplianceAgent.get_attribution())
st.sidebar.markdown("---")
st.sidebar.warning("**Disclaimer**: This is not financial advice. All signals are discretionary.")


# ══════════════════════════════════════════════════════════════════════
# DASHBOARD PAGE
# ══════════════════════════════════════════════════════════════════════
if page == "Dashboard":
    st.title("OpenClaw — Real-Time Dashboard")

    # Key metrics
    with Session() as s:
        total_localities = s.execute(select(func.count(Locality.id))).scalar() or 0
        total_lice_records = s.execute(select(func.count(LiceRecord.id))).scalar() or 0
        pending_signals = s.execute(
            select(func.count(Signal.id)).where(Signal.status == "pending")
        ).scalar() or 0
        executed_orders = s.execute(
            select(func.count(Order.id)).where(Order.status == "filled")
        ).scalar() or 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Localities Tracked", total_localities)
    col2.metric("Lice Records", total_lice_records)
    col3.metric("Pending Signals", pending_signals)
    col4.metric("Executed Orders", executed_orders)

    st.markdown("---")

    # Latest lice data chart
    st.subheader("Recent Lice Levels by Company")

    with Session() as s:
        records = s.execute(
            select(LiceRecord, CompanyExposure.ticker)
            .join(CompanyExposure, LiceRecord.locality_no == CompanyExposure.locality_no)
            .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
            .limit(500)
        ).all()

    if records:
        df = pd.DataFrame([
            {
                "week": f"{r[0].year}-W{r[0].week:02d}",
                "avg_lice": r[0].avg_adult_female_lice or 0,
                "ticker": r[1],
            }
            for r in records
        ])

        avg_by_company = df.groupby(["week", "ticker"])["avg_lice"].mean().reset_index()
        fig = px.line(
            avg_by_company, x="week", y="avg_lice", color="ticker",
            title="Average Adult Female Lice per Company",
            labels={"avg_lice": "Avg Adult Female Lice", "week": "Year-Week"},
        )
        fig.add_hline(y=0.5, line_dash="dash", line_color="red",
                      annotation_text="Regulatory Limit (0.5)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No lice data available yet. Start the data ingestion agent.")

    # Recent signals
    st.subheader("Recent Signals")
    with Session() as s:
        signals = s.execute(
            select(Signal).order_by(Signal.created_at.desc()).limit(10)
        ).scalars().all()

    if signals:
        sig_df = pd.DataFrame([
            {
                "Time": sig.created_at.strftime("%Y-%m-%d %H:%M") if sig.created_at else "",
                "Ticker": sig.ticker,
                "Direction": sig.direction,
                "Strength": f"{sig.strength:.2f}" if sig.strength else "",
                "Status": sig.status,
                "Rationale": (sig.rationale or "")[:100] + "...",
            }
            for sig in signals
        ])
        st.dataframe(sig_df, use_container_width=True)
    else:
        st.info("No signals generated yet.")


# ══════════════════════════════════════════════════════════════════════
# ALGAL BLOOM EARLY WARNING PAGE
# ══════════════════════════════════════════════════════════════════════
elif page == "Algal Bloom":
    st.title("Algal Bloom Early Warning")
    st.caption("Satellite chlorophyll-a monitoring · Copernicus Marine Service")

    from core.bloom.models import BloomRiskAssessment, BloomAlert, ChlorophyllReading

    # ── KPI row ──────────────────────────────────────────────────────
    with Session() as s:
        total_assessed = s.execute(
            select(func.count(func.distinct(BloomRiskAssessment.locality_no)))
        ).scalar() or 0

        critical_count = s.execute(
            select(func.count(func.distinct(BloomRiskAssessment.locality_no)))
            .where(BloomRiskAssessment.risk_level == "CRITICAL")
        ).scalar() or 0

        high_count = s.execute(
            select(func.count(func.distinct(BloomRiskAssessment.locality_no)))
            .where(BloomRiskAssessment.risk_level == "HIGH")
        ).scalar() or 0

        alerts_sent = s.execute(
            select(func.count(BloomAlert.id))
        ).scalar() or 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Localities Monitored", total_assessed)
    k2.metric("CRITICAL", critical_count, delta="Immediate risk" if critical_count > 0 else None,
              delta_color="inverse")
    k3.metric("HIGH", high_count, delta="Active bloom" if high_count > 0 else None,
              delta_color="inverse")
    k4.metric("Alerts Sent", alerts_sent)

    st.markdown("---")

    # ── Risk Map ─────────────────────────────────────────────────────
    st.subheader("Bloom Risk Map")

    with Session() as s:
        # Latest assessment per locality
        subq = (
            select(
                BloomRiskAssessment.locality_no,
                func.max(BloomRiskAssessment.assessed_at).label("latest"),
            )
            .group_by(BloomRiskAssessment.locality_no)
            .subquery()
        )
        risk_data = s.execute(
            select(
                BloomRiskAssessment.locality_no,
                BloomRiskAssessment.risk_level,
                BloomRiskAssessment.risk_score,
                BloomRiskAssessment.chl_a_value,
                BloomRiskAssessment.sst_value,
                Locality.name,
                Locality.latitude,
                Locality.longitude,
            )
            .join(subq, (
                BloomRiskAssessment.locality_no == subq.c.locality_no
            ) & (
                BloomRiskAssessment.assessed_at == subq.c.latest
            ))
            .outerjoin(Locality, BloomRiskAssessment.locality_no == Locality.locality_no)
        ).all()

    if risk_data:
        risk_df = pd.DataFrame(risk_data, columns=[
            "locality_no", "risk_level", "risk_score", "chl_a", "sst",
            "name", "latitude", "longitude",
        ])
        risk_df = risk_df.dropna(subset=["latitude", "longitude"])

        color_map = {"LOW": "#10B981", "ELEVATED": "#F59E0B", "HIGH": "#F97316", "CRITICAL": "#EF4444"}
        risk_df["color"] = risk_df["risk_level"].map(color_map)
        risk_df["size"] = risk_df["risk_score"].clip(lower=10) * 3

        # Plotly scatter map
        fig_map = px.scatter_mapbox(
            risk_df,
            lat="latitude",
            lon="longitude",
            color="risk_level",
            color_discrete_map=color_map,
            size="size",
            hover_name="name",
            hover_data={
                "risk_level": True,
                "risk_score": ":.0f",
                "chl_a": ":.2f",
                "sst": ":.1f",
                "size": False,
                "latitude": ":.3f",
                "longitude": ":.3f",
            },
            mapbox_style="carto-darkmatter",
            zoom=4,
            center={"lat": 64, "lon": 12},
            height=600,
            title="Farm Localities — Bloom Risk Level",
        )
        fig_map.update_layout(
            margin={"r": 0, "t": 40, "l": 0, "b": 0},
            legend_title_text="Risk Level",
        )
        st.plotly_chart(fig_map, use_container_width=True)

        # Risk distribution
        col_a, col_b = st.columns(2)
        with col_a:
            risk_counts = risk_df["risk_level"].value_counts().reindex(
                ["LOW", "ELEVATED", "HIGH", "CRITICAL"], fill_value=0
            )
            fig_bar = px.bar(
                x=risk_counts.index, y=risk_counts.values,
                color=risk_counts.index, color_discrete_map=color_map,
                labels={"x": "Risk Level", "y": "Localities"},
                title="Risk Distribution",
            )
            fig_bar.update_layout(showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_b:
            st.subheader("High Risk Localities")
            danger = risk_df[risk_df["risk_level"].isin(["HIGH", "CRITICAL"])].sort_values(
                "risk_score", ascending=False
            )
            if len(danger) > 0:
                st.dataframe(
                    danger[["name", "locality_no", "risk_level", "risk_score", "chl_a", "sst"]].head(20),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.success("No HIGH or CRITICAL risk localities detected.")

    else:
        st.info("No bloom risk data yet. Waiting for bloom agent to complete first cycle.")

    st.markdown("---")

    # ── Chlorophyll Heatmap ──────────────────────────────────────────
    st.subheader("Satellite Chlorophyll-a Heatmap")

    with Session() as s:
        chl_data = s.execute(
            select(
                ChlorophyllReading.latitude,
                ChlorophyllReading.longitude,
                ChlorophyllReading.chl_a_mg_m3,
            )
            .order_by(ChlorophyllReading.date.desc())
            .limit(10000)
        ).all()

    if chl_data:
        chl_df = pd.DataFrame(chl_data, columns=["latitude", "longitude", "chl_a"])

        fig_heat = px.density_mapbox(
            chl_df,
            lat="latitude",
            lon="longitude",
            z="chl_a",
            radius=8,
            mapbox_style="carto-darkmatter",
            zoom=3.5,
            center={"lat": 64, "lon": 12},
            color_continuous_scale="YlOrRd",
            height=500,
            title="Chlorophyll-a Concentration (mg/m³)",
        )
        fig_heat.update_layout(margin={"r": 0, "t": 40, "l": 0, "b": 0})
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.info("No chlorophyll satellite data available yet.")

    st.markdown("---")

    # ── Alert History ────────────────────────────────────────────────
    st.subheader("Alert History")

    with Session() as s:
        alerts = s.execute(
            select(BloomAlert).order_by(BloomAlert.sent_at.desc()).limit(50)
        ).scalars().all()

    if alerts:
        alert_df = pd.DataFrame([
            {
                "Time": a.sent_at.strftime("%Y-%m-%d %H:%M") if a.sent_at else "",
                "Locality": a.locality_no,
                "Risk": a.risk_level,
                "Channel": a.channel,
                "Status": a.delivery_status,
                "Message": (a.message_text or "")[:80] + "...",
            }
            for a in alerts
        ])
        st.dataframe(alert_df, use_container_width=True, hide_index=True)
    else:
        st.info("No bloom alerts sent yet.")


# ══════════════════════════════════════════════════════════════════════
# DIGITAL TWIN PAGE
# ══════════════════════════════════════════════════════════════════════
elif page == "Digital Twin":
    st.title("Autonomous Agentic Digital Twin")
    st.markdown(
        "Live virtual replica of Norwegian salmon farms with multi-agent LLM swarm optimization."
    )

    from core.twin.digital_twin import digital_twin
    from core.twin.agent_swarm import AgentSwarm

    # Sync twin from DB
    if st.button("Sync Twin from Live Data"):
        with st.spinner("Syncing digital twin from BarentsWatch data..."):
            count = digital_twin.sync_from_db()
            st.success(f"Synced {count} localities into digital twin.")

    # Twin state summary
    summary = digital_twin.get_summary()

    if summary.get("status") == "live" and summary.get("total_localities", 0) > 0:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Twin Localities", summary["total_localities"])
        col2.metric("Avg Lice", f"{summary['national_avg_lice']:.3f}")
        col3.metric("Above Threshold", summary["above_threshold"])
        col4.metric("Total Biomass", f"{summary['total_biomass_tonnes']:,.0f} t")

        # Company breakdown
        st.subheader("Company Twin State")
        if summary.get("companies"):
            comp_df = pd.DataFrame([
                {
                    "Company": tk,
                    "Localities": d["localities"],
                    "Avg Lice": d["avg_lice"],
                    "Max Lice": d["max_lice"],
                    "Biomass (t)": d["total_biomass_t"],
                }
                for tk, d in summary["companies"].items()
                if tk != "unmapped"
            ])
            st.dataframe(comp_df, use_container_width=True)

        st.markdown("---")

        # ── Agent Swarm ──────────────────────────────────────────────
        st.subheader("Multi-Agent LLM Swarm")

        from config.settings import settings as app_s
        if not app_s.openrouter_api_key and not app_s.anthropic_api_key and not app_s.openai_api_key:
            st.warning("Configure an LLM API key to enable the agent swarm.")
        else:
            swarm_scenario = st.text_input(
                "Swarm scenario",
                value="Optimize operations across all farms for the next 4 weeks",
                key="swarm_input",
            )

            agent_options = [
                "farm_optimizer", "supply_coordinator",
                "market_hedger", "regulatory_forecaster", "self_improvement",
            ]
            selected_agents = st.multiselect(
                "Agents to activate",
                agent_options,
                default=["farm_optimizer", "supply_coordinator"],
            )

            col1, col2 = st.columns(2)

            if col1.button("Run Agent Swarm"):
                swarm = AgentSwarm(digital_twin)
                with st.spinner(f"Running supervisor + {len(selected_agents)} agents..."):
                    import asyncio
                    result = asyncio.run(swarm.run_swarm(swarm_scenario, selected_agents))

                # Supervisor plan
                st.subheader("Supervisor Decomposition")
                for step in result.supervisor_plan[:8]:
                    st.markdown(f"- **{step.get('agent', '?')}**: {step.get('task', '?')[:100]}")

                # Agent results
                st.subheader(f"Agent Outputs — {result.total_actions} actions, ${result.total_cost_usd:.3f}")
                for r in result.agent_results:
                    agent_name = r.get("agent", "?")
                    actions = r.get("actions", [])
                    with st.expander(
                        f"{agent_name} ({r.get('role', '')[:40]}) — {len(actions)} actions"
                    ):
                        if actions:
                            for a in actions:
                                pri = a.get("priority", "medium").upper()
                                st.markdown(
                                    f"**[{pri}]** {a.get('action', '')}\n"
                                    f"- Target: {a.get('target', '')}\n"
                                    f"- Impact: {a.get('expected_impact', '')}\n"
                                    f"- Confidence: {a.get('confidence', 0):.0%}"
                                )
                        else:
                            resp_text = r.get("response", "")
                            st.markdown(resp_text[:1500] if resp_text else "No structured actions parsed.")

                # Debates
                if result.debates:
                    st.subheader("Agent Debates")
                    for debate in result.debates:
                        with st.expander(f"Debate: {debate.get('topic', '')}"):
                            st.markdown(f"**Resolution:** {debate.get('resolution', '')[:500]}")

                # Reflection
                if result.reflection:
                    with st.expander("Post-Cycle Reflection"):
                        st.markdown(result.reflection.get("assessment", "")[:1000])

                # Collaboration log
                with st.expander("Collaboration Log"):
                    from core.twin.shared_memory import shared_memory as sm
                    for entry in sm.get_collaboration_log(20):
                        st.text(
                            f"[{entry.get('type', '')}] {entry.get('from', '')} "
                            f"→ {entry.get('content', entry.get('subject', ''))[:80]}"
                        )

                    stats = sm.get_stats()
                    st.json(stats)

            if col2.button("Run Monte Carlo (100 sims)"):
                swarm = AgentSwarm(digital_twin)
                with st.spinner("Running 100 Monte Carlo simulations..."):
                    import asyncio
                    mc = asyncio.run(swarm.run_monte_carlo(
                        swarm_scenario, n_simulations=100, horizon_weeks=12
                    ))

                st.subheader("Monte Carlo Results (12-week horizon)")
                col1, col2, col3 = st.columns(3)
                col1.metric("Avg Lice (mean)", f"{mc['avg_lice_mean']:.3f}")
                col2.metric("P(Crisis)", f"{mc['prob_crisis']:.0%}")
                col3.metric("Avg Treatments", f"{mc['avg_treatments']:.0f}")

                st.markdown(
                    f"**Lice range (90% CI):** {mc['avg_lice_p5']:.3f} – {mc['avg_lice_p95']:.3f}"
                )
                st.markdown(
                    f"**Biomass range:** {mc['biomass_p5']:,.0f} – {mc['biomass_p95']:,.0f} tonnes"
                )

        # ── Simulation ───────────────────────────────────────────────
        st.markdown("---")
        st.subheader("Twin Simulation")
        st.markdown("Fork the twin and simulate interventions.")

        sim_weeks = st.slider("Simulate weeks ahead", 1, 20, 4, key="sim_weeks")
        sim_temp = st.slider("Temperature delta (°C)", -2.0, 3.0, 0.0, 0.5, key="sim_temp")
        sim_treat = st.checkbox("Apply mechanical treatment to all sites above 0.3 lice", key="sim_treat")

        if st.button("Run Simulation"):
            forked = digital_twin.fork()

            interventions = {"temp_delta_c": sim_temp}
            if sim_treat:
                interventions["treat_localities"] = [
                    ln for ln, t in forked.items() if t.lice.adult_female > 0.3
                ]
                interventions["treatment_type"] = "mechanical"

            result = digital_twin.simulate_step(forked, weeks=sim_weeks, interventions=interventions)

            # Compare before/after
            before_lice = [t.lice.adult_female for t in digital_twin.localities.values()]
            after_lice = [t.lice.adult_female for t in result.values()]

            col1, col2 = st.columns(2)
            col1.metric("Current Avg Lice", f"{np.mean(before_lice):.3f}")
            col2.metric(
                f"After {sim_weeks}w Simulation",
                f"{np.mean(after_lice):.3f}",
                delta=f"{np.mean(after_lice) - np.mean(before_lice):+.3f}",
            )

            # Distribution comparison
            fig_sim = go.Figure()
            fig_sim.add_trace(go.Histogram(x=before_lice, name="Current", opacity=0.7, marker_color="#3498db"))
            fig_sim.add_trace(go.Histogram(x=after_lice, name=f"After {sim_weeks}w", opacity=0.7, marker_color="#e74c3c"))
            fig_sim.update_layout(
                title="Lice Distribution: Current vs Simulated",
                xaxis_title="Adult Female Lice",
                barmode="overlay",
            )
            st.plotly_chart(fig_sim, use_container_width=True)

    else:
        st.info("Click 'Sync Twin from Live Data' to initialize the digital twin from the database.")


# ══════════════════════════════════════════════════════════════════════
# AI CHAT PAGE
# ══════════════════════════════════════════════════════════════════════
elif page == "AI Chat":
    st.title("AI Decision Intelligence")
    st.markdown(
        "Ask anything about lice levels, treatment decisions, market impact, "
        "or regulatory context. The AI has access to all live platform data."
    )

    # Check if LLM is configured
    from config.settings import settings as app_settings
    if not app_settings.anthropic_api_key and not app_settings.openai_api_key:
        st.warning(
            "No LLM API key configured. Add `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` "
            "to your `.env` file to enable AI features."
        )
        st.markdown("**Example questions you'll be able to ask:**")
        st.markdown("""
- "Should we treat locality 13035 now or wait?"
- "What's the lice outlook for Mowi this month?"
- "Compare treatment options for farms above 0.3 lice"
- "How does the current lice situation affect salmon prices?"
- "Explain the risk in PA 3 right now"
        """)
    else:
        # Chat interface
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = []

        # Display chat history
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Chat input
        if prompt := st.chat_input("Ask about lice, treatments, markets..."):
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Analyzing platform data..."):
                    import asyncio
                    from core.llm.chat_agent import chat_agent
                    try:
                        response = asyncio.run(chat_agent.ask(prompt))
                    except Exception as e:
                        response = f"Error: {e}"
                    st.markdown(response)

            st.session_state.chat_messages.append({"role": "assistant", "content": response})

        # Sidebar: LLM usage stats
        from core.llm.client import llm_client as llm_c
        usage = llm_c.get_usage_summary()
        if usage["total_calls"] > 0:
            st.sidebar.markdown("---")
            st.sidebar.markdown("**AI Usage**")
            st.sidebar.markdown(f"Calls: {usage['total_calls']}")
            st.sidebar.markdown(f"Cost: ${usage['total_cost_usd']:.2f} / ${usage['budget_usd']:.0f}")

        # Quick action buttons
        st.markdown("---")
        st.markdown("**Quick questions:**")
        col1, col2, col3 = st.columns(3)
        if col1.button("Lice overview"):
            st.session_state["_pending_q"] = "Give me a brief overview of the current lice situation across all companies."
            st.rerun()
        if col2.button("Treatment priorities"):
            st.session_state["_pending_q"] = "Which farms should be prioritized for treatment this week?"
            st.rerun()
        if col3.button("Market impact"):
            st.session_state["_pending_q"] = "How are current lice levels likely to affect salmon stock prices?"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════
# SCENARIOS PAGE
# ══════════════════════════════════════════════════════════════════════
elif page == "Scenarios":
    st.title("What-If Scenario Simulator")
    st.markdown("Simulate the impact of environmental changes, interventions, or regulatory actions.")

    from config.settings import settings as app_settings
    if not app_settings.anthropic_api_key and not app_settings.openai_api_key:
        st.warning("Configure an LLM API key in `.env` to enable scenario simulation.")
    else:
        # Preset scenarios
        st.subheader("Preset Scenarios")
        preset = st.selectbox("Choose a scenario", [
            "Custom...",
            "Sea temperature rises 1°C across all PAs",
            "Sea temperature rises 2°C in PA 3-6",
            "Traffic-light turns red for PA 4",
            "Deploy 20% more cleaner fish in Mowi sites",
            "All farms above 0.3 lice treat simultaneously",
            "Marine heatwave event (3°C anomaly for 4 weeks)",
        ])

        if preset == "Custom...":
            scenario_text = st.text_area(
                "Describe your scenario",
                placeholder="What if sea temperature rises 1.5°C and we reduce cleaner fish by 10%?",
                height=100,
            )
        else:
            scenario_text = preset

        if st.button("Run Scenario") and scenario_text:
            with st.spinner("Running scenario simulation..."):
                import asyncio
                from core.llm.scenarios import scenario_simulator
                try:
                    result = asyncio.run(scenario_simulator.simulate(scenario_text))

                    st.subheader("Scenario Analysis")
                    st.markdown(result.analysis)

                    if result.quantitative_estimates:
                        st.subheader("Quantitative Estimates")
                        for key, val in result.quantitative_estimates.items():
                            st.metric(key.replace("_", " ").title(), val)
                except Exception as e:
                    st.error(f"Scenario simulation failed: {e}")

        # RAG Knowledge Query
        st.markdown("---")
        st.subheader("Knowledge Base Query")
        st.markdown("Ask questions grounded in research papers and regulatory documents.")
        rag_q = st.text_input("Research question", placeholder="How does the Stige model predict lice stages?")
        if rag_q:
            with st.spinner("Searching knowledge base..."):
                import asyncio
                from core.llm.rag import rag_layer
                try:
                    answer = asyncio.run(rag_layer.query(rag_q))
                    st.markdown(answer)
                except Exception as e:
                    st.error(f"RAG query failed: {e}")


# ══════════════════════════════════════════════════════════════════════
# FORECAST HORIZON PAGE
# ══════════════════════════════════════════════════════════════════════
elif page == "Forecast Horizon":
    st.title("Multi-Horizon Forecast Explorer")

    st.info(
        "**Predictability decreases with longer horizons** due to accumulating biological, "
        "environmental, and market variability. Uncertainty bands widen accordingly. "
        "Short horizons (2-6 weeks) offer high confidence; long horizons (14-20 weeks) "
        "are indicative only."
    )

    # Horizon selector
    from core.predictors.medium_term import ALLOWED_HORIZONS, HORIZON_ACCURACY, uncertainty_scale

    col1, col2 = st.columns([1, 2])
    with col1:
        horizon = st.select_slider(
            "Forecast Horizon (weeks ahead)",
            options=ALLOWED_HORIZONS,
            value=4,
        )
        ticker_h = st.selectbox("Company", ["MOWI", "SALM", "LSG", "GSF"], key="horizon_ticker")

    with col2:
        acc = HORIZON_ACCURACY[horizon]
        band_color = {"high": "green", "medium": "orange", "low": "red"}[acc["band"]]
        st.markdown(f"### :{band_color}[{acc['band'].upper()} CONFIDENCE]")
        st.markdown(f"_{acc['label']}_")
        st.metric("Estimated R²", f"{acc['r2_est']:.0%}")
        st.metric("Uncertainty multiplier", f"{uncertainty_scale(horizon):.1f}x vs 2-week baseline")

    if st.button("Generate Forecast", key="gen_horizon"):
        from agents.prediction_agent import PredictionAgent

        with st.spinner(f"Running {horizon}-week forecast for {ticker_h}..."):
            import asyncio

            async def _run_horizon():
                pred = PredictionAgent()
                pred.short_term._use_pymc = False
                pred.short_term._traces = {}

                # Load data and run prediction
                from core.models import Session as S2, LiceRecord, CompanyExposure
                from sqlalchemy import select as sel2

                with S2() as s:
                    locality_nos = s.execute(
                        sel2(CompanyExposure.locality_no).where(CompanyExposure.ticker == ticker_h)
                    ).scalars().all()

                    records = s.execute(
                        sel2(LiceRecord)
                        .where(
                            LiceRecord.locality_no.in_(list(locality_nos)),
                            LiceRecord.avg_adult_female_lice.isnot(None),
                        )
                        .order_by(LiceRecord.year, LiceRecord.week)
                    ).scalars().all()

                if not records:
                    return None

                history = pd.DataFrame([{
                    "year": r.year, "week": r.week,
                    "avg_lice": r.avg_adult_female_lice,
                    "sea_temp": r.sea_temp_c or 8,
                } for r in records])

                weekly = history.groupby(["year", "week"]).agg(
                    avg_lice=("avg_lice", "mean"),
                    sea_temp=("sea_temp", "mean"),
                ).reset_index()

                return pred.medium_term.predict(weekly, ticker_h, horizon)

            forecast = asyncio.run(_run_horizon())

        if forecast and forecast.weekly_forecasts:
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Trend", forecast.trend_direction)
            col2.metric("Peak", f"{forecast.peak_predicted_value:.3f}")
            col3.metric("Confidence", f"{forecast.confidence:.0%}")
            col4.metric("Model", forecast.model_used)

            # ── Expanding cone plot ──────────────────────────────────
            st.subheader(f"{ticker_h} — {horizon}-Week Forecast Cone")

            wf = forecast.weekly_forecasts
            weeks = [f"W{f['week']}" for f in wf]
            predicted = [f["predicted"] for f in wf]
            lo80 = [f["lo80"] for f in wf]
            hi80 = [f["hi80"] for f in wf]
            lo95 = [f["lo95"] for f in wf]
            hi95 = [f["hi95"] for f in wf]
            unc_scales = [f.get("uncertainty_scale", 1.0) for f in wf]
            bands = [f.get("accuracy_band", "medium") for f in wf]

            fig_cone = go.Figure()

            # Color 95% band by accuracy
            band_colors = {
                "high": "rgba(46,204,113,0.10)",
                "medium": "rgba(241,196,15,0.10)",
                "low": "rgba(231,76,60,0.10)",
            }
            band_border = {
                "high": "rgba(46,204,113,0.3)",
                "medium": "rgba(241,196,15,0.3)",
                "low": "rgba(231,76,60,0.3)",
            }

            # 95% band
            fig_cone.add_trace(go.Scatter(
                x=weeks + weeks[::-1],
                y=hi95 + lo95[::-1],
                fill="toself",
                fillcolor="rgba(52,152,219,0.08)",
                line=dict(width=0),
                name="95% CI",
                hoverinfo="skip",
            ))

            # 80% band
            fig_cone.add_trace(go.Scatter(
                x=weeks + weeks[::-1],
                y=hi80 + lo80[::-1],
                fill="toself",
                fillcolor="rgba(52,152,219,0.20)",
                line=dict(width=0),
                name="80% CI",
                hoverinfo="skip",
            ))

            # Point forecast
            fig_cone.add_trace(go.Scatter(
                x=weeks, y=predicted,
                mode="lines+markers",
                name="Forecast",
                line=dict(color="#2c3e50", width=2.5),
                hovertemplate="W%{x}: %{y:.3f} lice<extra></extra>",
            ))

            # Regulatory threshold
            fig_cone.add_hline(y=0.5, line_dash="dash", line_color="red",
                             annotation_text="Regulatory Limit (0.5)")

            # Accuracy zone annotations
            if horizon >= 8:
                fig_cone.add_vrect(
                    x0=weeks[6] if len(weeks) > 6 else weeks[-1],
                    x1=weeks[-1],
                    fillcolor="rgba(231,76,60,0.05)",
                    line_width=0,
                    annotation_text="Lower confidence zone",
                    annotation_position="top right",
                )

            fig_cone.update_layout(
                yaxis_title="Avg Adult Female Lice",
                xaxis_title="Week",
                height=450,
                showlegend=True,
            )
            st.plotly_chart(fig_cone, use_container_width=True)

            # ── Uncertainty scale visualization ──────────────────────
            st.subheader("Uncertainty Scaling by Week")

            unc_df = pd.DataFrame([
                {
                    "Week": f"W{f['week']}",
                    "Horizon (weeks)": f.get("horizon_h", i+1),
                    "Uncertainty Scale": f.get("uncertainty_scale", 1.0),
                    "Band Width (80%)": round(f["hi80"] - f["lo80"], 4),
                    "Band Width (95%)": round(f["hi95"] - f["lo95"], 4),
                    "Accuracy": f.get("accuracy_band", "medium"),
                    "P(>0.5)": f"{f['prob_exceed']:.1%}",
                }
                for i, f in enumerate(wf)
            ])

            fig_unc = go.Figure()
            colors_map = {"high": "#2ecc71", "medium": "#f1c40f", "low": "#e74c3c"}
            bar_colors = [colors_map.get(f.get("accuracy_band", "medium"), "#95a5a6") for f in wf]

            fig_unc.add_trace(go.Bar(
                x=unc_df["Week"],
                y=unc_df["Band Width (80%)"],
                name="80% CI Width",
                marker_color=bar_colors,
                hovertemplate="80% CI width: %{y:.3f}<extra></extra>",
            ))
            fig_unc.update_layout(
                yaxis_title="Prediction Interval Width (lice/fish)",
                height=300,
                title="Widening Uncertainty — Green=High Confidence, Yellow=Medium, Red=Low",
            )
            st.plotly_chart(fig_unc, use_container_width=True)

            # Data table
            st.dataframe(unc_df, use_container_width=True)

            # ── Accuracy disclaimer ──────────────────────────────────
            st.markdown("---")
            acc_final = HORIZON_ACCURACY[horizon]
            st.warning(
                f"**Forecast accuracy at {horizon} weeks: {acc_final['band'].upper()}** "
                f"(est. R² ≈ {acc_final['r2_est']:.0%}). "
                f"{acc_final['label']}. "
                f"Uncertainty is {uncertainty_scale(horizon):.1f}x wider than at 2-week baseline. "
                f"All forecasts are probabilistic — use credible intervals, not point estimates, for decisions."
            )
        else:
            st.warning("Insufficient data to generate forecast for this company.")

    # ── Accuracy reference table ─────────────────────────────────────
    with st.expander("Horizon Accuracy Reference"):
        ref_df = pd.DataFrame([
            {
                "Horizon": f"{h} weeks",
                "Confidence": HORIZON_ACCURACY[h]["band"].upper(),
                "Est. R²": f"{HORIZON_ACCURACY[h]['r2_est']:.0%}",
                "Unc. Scale": f"{uncertainty_scale(h):.1f}x",
                "Guidance": HORIZON_ACCURACY[h]["label"],
            }
            for h in ALLOWED_HORIZONS
        ])
        st.dataframe(ref_df, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════
# PREDICTIONS PAGE
# ══════════════════════════════════════════════════════════════════════
elif page == "Predictions":
    st.title("Lice Prediction Engine")
    st.markdown(
        "**Tiered forecasting**: Short-term (Stige GLM, 1-2 weeks) + "
        "Medium-term (Prophet+LSTM, 2-6 weeks) + Impact Translation"
    )

    # Run predictions on-demand
    ticker_sel = st.selectbox("Company", ["MOWI", "SALM", "LSG", "GSF"])

    if st.button("Run Prediction Pipeline"):
        import asyncio
        from agents.prediction_agent import PredictionAgent

        pred_agent = PredictionAgent()

        with st.spinner("Running infestation pressure + forecasts..."):
            asyncio.run(pred_agent.tick())

        # Display pressure field
        if pred_agent.pressure_field:
            st.subheader("Infestation Pressure Field")
            press_df = pd.DataFrame([
                {
                    "Locality": p.locality_no,
                    "Pressure Index": round(p.pressure_index, 1),
                    "Risk": p.risk_level,
                    "Local": round(p.local_contribution, 3),
                    "External": round(p.external_contribution, 3),
                    "Temp Factor": round(p.temperature_factor, 2),
                }
                for p in pred_agent.pressure_field[:200]
            ])
            col1, col2, col3 = st.columns(3)
            col1.metric("Avg Pressure", f"{press_df['Pressure Index'].mean():.1f}")
            col2.metric("Max Pressure", f"{press_df['Pressure Index'].max():.1f}")
            col3.metric(
                "Critical Sites",
                len(press_df[press_df["Risk"] == "critical"]),
            )

            # Pressure distribution
            fig_press = px.histogram(
                press_df, x="Pressure Index", color="Risk",
                color_discrete_map={
                    "low": "#2ecc71", "moderate": "#f1c40f",
                    "high": "#e67e22", "critical": "#e74c3c",
                },
                title="Infestation Pressure Distribution",
            )
            st.plotly_chart(fig_press, use_container_width=True)

        # Short-term forecasts
        st_forecasts = pred_agent.short_forecasts.get(ticker_sel, [])
        if st_forecasts:
            st.subheader(f"Short-Term Forecast — {ticker_sel} (1-2 weeks)")

            # Prediction cone chart
            w1 = [f for f in st_forecasts if f.horizon_weeks == 1]
            w2 = [f for f in st_forecasts if f.horizon_weeks == 2]

            avg_1w = np.mean([f.pred_adult_female for f in w1]) if w1 else 0
            avg_2w = np.mean([f.pred_adult_female for f in w2]) if w2 else 0
            avg_prob = np.mean([f.prob_exceed_threshold for f in w1]) if w1 else 0

            col1, col2, col3 = st.columns(3)
            col1.metric("1-Week Forecast", f"{avg_1w:.3f} lice")
            col2.metric("2-Week Forecast", f"{avg_2w:.3f} lice")
            col3.metric("P(>0.5 threshold)", f"{avg_prob:.0%}")

            # Trend breakdown
            trends = [f.trend for f in w1]
            trend_counts = pd.Series(trends).value_counts()
            st.bar_chart(trend_counts)

        # Medium-term forecast
        mt_forecast = pred_agent.medium_forecasts.get(ticker_sel)
        if mt_forecast and mt_forecast.weekly_forecasts:
            st.subheader(f"Medium-Term Forecast — {ticker_sel} (4 weeks)")

            col1, col2, col3 = st.columns(3)
            col1.metric("Trend", mt_forecast.trend_direction)
            col2.metric("Peak Predicted", f"{mt_forecast.peak_predicted_value:.3f}")
            col3.metric("Model", mt_forecast.model_used)

            # Prediction cone
            wf = mt_forecast.weekly_forecasts
            weeks = [f"W{f['week']}" for f in wf]
            predicted = [f["predicted"] for f in wf]
            lo80 = [f["lo80"] for f in wf]
            hi80 = [f["hi80"] for f in wf]
            lo95 = [f["lo95"] for f in wf]
            hi95 = [f["hi95"] for f in wf]

            fig_cone = go.Figure()
            # 95% band
            fig_cone.add_trace(go.Scatter(
                x=weeks + weeks[::-1],
                y=hi95 + lo95[::-1],
                fill="toself", fillcolor="rgba(52,152,219,0.1)",
                line=dict(width=0), name="95% CI",
            ))
            # 80% band
            fig_cone.add_trace(go.Scatter(
                x=weeks + weeks[::-1],
                y=hi80 + lo80[::-1],
                fill="toself", fillcolor="rgba(52,152,219,0.25)",
                line=dict(width=0), name="80% CI",
            ))
            # Point forecast
            fig_cone.add_trace(go.Scatter(
                x=weeks, y=predicted,
                mode="lines+markers", name="Forecast",
                line=dict(color="#2c3e50", width=2),
            ))
            # Threshold line
            fig_cone.add_hline(
                y=0.5, line_dash="dash", line_color="red",
                annotation_text="Regulatory Limit",
            )
            fig_cone.update_layout(
                title=f"{ticker_sel} — Lice Forecast Cone",
                yaxis_title="Avg Adult Female Lice",
                xaxis_title="Week",
            )
            st.plotly_chart(fig_cone, use_container_width=True)

        # Harvest impact
        impact = pred_agent.harvest_impacts.get(ticker_sel)
        if impact and impact.total_harvest_reduction_pct > 0:
            st.subheader(f"Harvest Impact — {ticker_sel}")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Harvest Reduction", f"{impact.total_harvest_reduction_pct:.1f}%")
            col2.metric("Revenue Impact", f"NOK {impact.revenue_impact_mnok:.0f}M")
            col3.metric("Expected Stock Move", f"{impact.expected_stock_move_pct:+.1f}%")
            col4.metric("Confidence", f"{impact.confidence:.0%}")

            # Impact breakdown
            breakdown = pd.DataFrame([
                {"Factor": "Growth Reduction", "Impact %": impact.growth_reduction_pct},
                {"Factor": "Treatment Mortality", "Impact %": impact.treatment_mortality_pct},
                {"Factor": "Treatment Cost", "Impact %": impact.treatment_cost_mnok},
                {"Factor": "Regulatory Cut", "Impact %": impact.regulatory_cut_pct},
            ])
            fig_bd = px.bar(
                breakdown, x="Factor", y="Impact %",
                title="Harvest Impact Breakdown",
                color_discrete_sequence=["#e74c3c"],
            )
            st.plotly_chart(fig_bd, use_container_width=True)

            if impact.drivers:
                st.markdown("**Key Drivers:**")
                for d in impact.drivers:
                    st.markdown(f"- {d}")

        # Arbitrage signal
        arb = pred_agent.arb_signals.get(ticker_sel)
        if arb:
            st.subheader(f"Arbitrage Signal — {ticker_sel}")
            color = "#e74c3c" if arb.direction == "SHORT" else "#2ecc71"
            st.markdown(
                f"### :{color}[{arb.direction}] — Strength: {arb.strength:.2f}"
            )
            st.markdown(arb.rationale)
    else:
        st.info("Click 'Run Prediction Pipeline' to generate forecasts from live data.")


# ══════════════════════════════════════════════════════════════════════
# FARMER ADVISORY PAGE
# ══════════════════════════════════════════════════════════════════════
elif page == "Farmer Advisory":
    st.title("Farmer Advisory Module")
    st.markdown("Treatment recommendations, harvest timing, and risk scores per farm.")

    # Get localities with recent data
    with Session() as s:
        latest = s.execute(
            select(LiceRecord.year, LiceRecord.week)
            .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
            .limit(1)
        ).first()

        if latest:
            year, week = latest
            active_locs = s.execute(
                select(LiceRecord.locality_no, LiceRecord.avg_adult_female_lice,
                       LiceRecord.sea_temp_c)
                .where(LiceRecord.year == year, LiceRecord.week == week)
                .where(LiceRecord.avg_adult_female_lice.isnot(None))
                .order_by(LiceRecord.avg_adult_female_lice.desc())
                .limit(50)
            ).all()
        else:
            active_locs = []

    if active_locs:
        from core.valuechain.farmer_advisory import generate_farm_advisory

        # Top-level risk overview
        advisories = []
        for loc_no, lice_val, temp in active_locs:
            adv = generate_farm_advisory(
                locality_no=loc_no,
                current_lice=lice_val or 0,
                sea_temp=temp or 8,
                forecasts_1w=[], forecasts_2w=[],
            )
            advisories.append(adv)

        # Risk distribution
        risk_counts = pd.Series([a.risk_level for a in advisories]).value_counts()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Critical", risk_counts.get("critical", 0))
        col2.metric("High", risk_counts.get("high", 0))
        col3.metric("Moderate", risk_counts.get("moderate", 0))
        col4.metric("Low", risk_counts.get("low", 0))

        # Treatment needs
        need_treatment = [a for a in advisories if a.treatment_needed]
        st.subheader(f"Treatment Needed: {len(need_treatment)} of {len(advisories)} sites")

        if need_treatment:
            treat_df = pd.DataFrame([
                {
                    "Locality": a.locality_no,
                    "Lice": round(a.current_lice, 3),
                    "Risk": a.risk_level,
                    "Score": a.risk_score,
                    "Urgency": a.treatment_urgency,
                    "Recommended": a.recommended_treatment,
                    "Est. Cost": f"NOK {a.estimated_treatment_cost_nok:,.0f}",
                    "Efficacy": f"{a.expected_lice_reduction_pct:.0f}%",
                }
                for a in sorted(need_treatment, key=lambda x: x.risk_score, reverse=True)
            ])
            st.dataframe(treat_df, use_container_width=True)

        # Individual farm details
        st.subheader("Farm Detail")
        selected_loc = st.selectbox(
            "Select locality",
            [a.locality_no for a in advisories],
            format_func=lambda x: f"Locality {x} — {next((a.risk_level for a in advisories if a.locality_no == x), 'unknown')}",
        )
        selected_adv = next((a for a in advisories if a.locality_no == selected_loc), None)
        if selected_adv:
            st.markdown(f"### {selected_adv.summary}")

            col1, col2, col3 = st.columns(3)
            col1.metric("Current Lice", f"{selected_adv.current_lice:.3f}")
            col2.metric("Risk Score", f"{selected_adv.risk_score:.0f}/100")
            col3.metric("Trend", selected_adv.trend)

            if selected_adv.treatment_needed:
                st.warning(
                    f"**Treatment: {selected_adv.treatment_urgency.upper()}** — "
                    f"{selected_adv.recommended_treatment}\n\n"
                    f"Expected efficacy: {selected_adv.expected_lice_reduction_pct:.0f}% | "
                    f"Mortality risk: {selected_adv.expected_mortality_pct:.1f}% | "
                    f"Cost: NOK {selected_adv.estimated_treatment_cost_nok:,.0f}"
                )
                if selected_adv.alternative_treatments:
                    st.info(f"Alternatives: {', '.join(selected_adv.alternative_treatments)}")

            if selected_adv.harvest_advice:
                st.info(f"**Harvest**: {selected_adv.harvest_advice}")
    else:
        st.info("No active localities with lice data. Run the data ingestion agent first.")


# ══════════════════════════════════════════════════════════════════════
# SUPPLY CHAIN PAGE
# ══════════════════════════════════════════════════════════════════════
elif page == "Supply Chain":
    st.title("Supply Chain Intelligence")
    st.markdown("Regional supply forecasts, quality projections, and contract risk alerts for buyers and processors.")

    with Session() as s:
        latest = s.execute(
            select(LiceRecord.year, LiceRecord.week)
            .order_by(LiceRecord.year.desc(), LiceRecord.week.desc())
            .limit(1)
        ).first()

        if latest:
            year, week = latest
            records = s.execute(
                select(LiceRecord, Locality)
                .join(Locality, LiceRecord.locality_no == Locality.locality_no)
                .where(LiceRecord.year == year, LiceRecord.week == week)
                .where(LiceRecord.avg_adult_female_lice.isnot(None))
            ).all()
        else:
            records = []

    if records:
        from core.valuechain.supply_forecast import generate_buyer_intelligence

        # Aggregate by PA
        pa_data: dict[int, dict] = {}
        for lice, loc in records:
            pa = loc.production_area or 0
            if pa < 1 or pa > 13:
                continue
            if pa not in pa_data:
                pa_data[pa] = {"lice_values": [], "temps": []}
            pa_data[pa]["lice_values"].append(lice.avg_adult_female_lice or 0)
            pa_data[pa]["temps"].append(lice.sea_temp_c or 8)

        pa_summary = {}
        for pa, d in pa_data.items():
            arr = np.array(d["lice_values"])
            pa_summary[pa] = {
                "avg_lice": float(np.mean(arr)),
                "pct_above": float(np.mean(arr > 0.5)),
                "treatments": int(np.sum(arr > 0.5)),
                "temp": float(np.mean(d["temps"])),
            }

        intel = generate_buyer_intelligence(pa_summary)

        # Headlines
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Supply (4w)", f"{intel.total_predicted_tonnes:,.0f} t")
        col2.metric("vs Baseline", f"{intel.net_supply_change_pct:+.1f}%")
        col3.metric("Quality Score", f"{intel.overall_quality_score:.0f}/100")
        col4.metric("Price Outlook", intel.price_outlook.upper())

        # Regional breakdown chart
        st.subheader("Regional Supply Forecast (4 weeks)")
        region_df = pd.DataFrame([
            {
                "Region": f.region,
                "Predicted (t)": f.predicted_tonnes,
                "Baseline (t)": f.baseline_tonnes,
                "Change %": f.net_adjustment_pct,
                "Quality": f.avg_quality_score,
                "Risk": f.supply_risk,
                "Price": f.price_pressure,
            }
            for f in intel.regional_forecasts
        ])

        fig_supply = go.Figure()
        fig_supply.add_trace(go.Bar(
            x=region_df["Region"], y=region_df["Baseline (t)"],
            name="Baseline", marker_color="#95a5a6",
        ))
        fig_supply.add_trace(go.Bar(
            x=region_df["Region"], y=region_df["Predicted (t)"],
            name="Predicted", marker_color="#3498db",
        ))
        fig_supply.update_layout(
            title="Supply by Production Area (4-week cumulative)",
            barmode="group", yaxis_title="Tonnes HOG",
        )
        st.plotly_chart(fig_supply, use_container_width=True)

        # Quality distribution
        st.subheader("Quality Grade Forecast")
        quality_df = pd.DataFrame([
            {"Region": f.region, "Superior %": f.pct_superior,
             "Ordinary %": f.pct_ordinary, "Production %": f.pct_production}
            for f in intel.regional_forecasts
        ])
        fig_q = px.bar(
            quality_df.melt(id_vars="Region", var_name="Grade", value_name="Pct"),
            x="Region", y="Pct", color="Grade",
            color_discrete_map={
                "Superior %": "#2ecc71", "Ordinary %": "#f1c40f", "Production %": "#e74c3c"
            },
            title="Expected Quality Distribution",
        )
        st.plotly_chart(fig_q, use_container_width=True)

        # Risks & recommendations
        if intel.key_risks:
            st.subheader("Key Risks")
            for risk in intel.key_risks:
                st.error(risk)

        if intel.recommendations:
            st.subheader("Recommendations")
            for rec in intel.recommendations:
                st.success(rec)

        st.dataframe(region_df, use_container_width=True)
    else:
        st.info("No data available for supply forecasting.")


# ══════════════════════════════════════════════════════════════════════
# SIGNALS & EXECUTION PAGE
# ══════════════════════════════════════════════════════════════════════
elif page == "Signals & Execution":
    st.title("Signal Management & Execution")
    st.warning(
        "**Important**: No order will be placed without your explicit confirmation. "
        "Review each signal carefully before confirming."
    )

    # Pending signals with confirm/reject buttons
    st.subheader("Pending Signals")
    with Session() as s:
        pending = s.execute(
            select(Signal).where(Signal.status == "pending").order_by(Signal.created_at.desc())
        ).scalars().all()

    if pending:
        for sig in pending:
            with st.expander(
                f"{'🔴' if sig.direction == 'SHORT' else '🟢'} "
                f"{sig.ticker} {sig.direction} — Strength: {sig.strength:.2f}"
            ):
                st.write(sig.rationale)
                st.write(f"**Created**: {sig.created_at}")
                st.write(f"**Lice Score**: {sig.lice_score:.3f}")

                col1, col2 = st.columns(2)
                if col1.button(f"Confirm Signal #{sig.id}", key=f"confirm_{sig.id}"):
                    ExecutionAgent.confirm_signal(sig.id)
                    st.success(f"Signal #{sig.id} confirmed! Order will be placed.")
                    st.rerun()

                if col2.button(f"Reject Signal #{sig.id}", key=f"reject_{sig.id}"):
                    ExecutionAgent.reject_signal(sig.id)
                    st.info(f"Signal #{sig.id} rejected.")
                    st.rerun()
    else:
        st.info("No pending signals.")

    # Order history
    st.subheader("Order History")
    with Session() as s:
        orders = s.execute(
            select(Order).order_by(Order.created_at.desc()).limit(50)
        ).scalars().all()

    if orders:
        ord_df = pd.DataFrame([
            {
                "Time": o.created_at.strftime("%Y-%m-%d %H:%M") if o.created_at else "",
                "Ticker": o.ticker,
                "Side": o.side,
                "Qty": o.quantity,
                "Price": o.price,
                "Status": o.status,
                "Broker": o.broker,
                "Consent": "Yes" if o.user_consent else "No",
            }
            for o in orders
        ])
        st.dataframe(ord_df, use_container_width=True)
    else:
        st.info("No orders yet.")


# ══════════════════════════════════════════════════════════════════════
# EXPOSURE MAP PAGE
# ══════════════════════════════════════════════════════════════════════
elif page == "Exposure Map":
    st.title("Company-Locality Exposure Map")

    with Session() as s:
        data = s.execute(
            select(Locality, CompanyExposure.ticker, CompanyExposure.weight)
            .join(CompanyExposure, Locality.locality_no == CompanyExposure.locality_no)
        ).all()

    if data:
        map_df = pd.DataFrame([
            {
                "Locality": d[0].name,
                "Municipality": d[0].municipality,
                "Latitude": d[0].latitude,
                "Longitude": d[0].longitude,
                "Ticker": d[1],
                "Weight": d[2],
                "PA": d[0].production_area,
            }
            for d in data
            if d[0].latitude and d[0].longitude
        ])

        if not map_df.empty:
            fig = px.scatter_mapbox(
                map_df,
                lat="Latitude",
                lon="Longitude",
                color="Ticker",
                size="Weight",
                hover_name="Locality",
                hover_data=["Municipality", "PA"],
                zoom=4,
                center={"lat": 65, "lon": 12},
                title="Farm Localities by Company",
            )
            fig.update_layout(mapbox_style="carto-positron", height=600)
            st.plotly_chart(fig, use_container_width=True)

        # Summary table
        summary = map_df.groupby("Ticker").agg(
            Localities=("Locality", "count"),
            Avg_Weight=("Weight", "mean"),
        ).reset_index()
        st.dataframe(summary, use_container_width=True)
    else:
        st.info("No exposure mapping data. Run the exposure mapper agent first.")


# ══════════════════════════════════════════════════════════════════════
# LICE DATA PAGE
# ══════════════════════════════════════════════════════════════════════
elif page == "Lice Data":
    st.title("Lice Data Explorer")

    with Session() as s:
        records = s.execute(
            select(LiceRecord).order_by(
                LiceRecord.year.desc(), LiceRecord.week.desc()
            ).limit(2000)
        ).scalars().all()

    if records:
        df = pd.DataFrame([
            {
                "Year": r.year,
                "Week": r.week,
                "Locality": r.locality_no,
                "Avg Adult Female": r.avg_adult_female_lice,
                "Avg Mobile": r.avg_mobile_lice,
                "Sea Temp (C)": r.sea_temp_c,
                "Cleaner Fish": r.has_cleaner_fish,
            }
            for r in records
        ])
        st.dataframe(df, use_container_width=True, height=400)

        # Histogram
        fig = px.histogram(
            df, x="Avg Adult Female", nbins=50,
            title="Distribution of Adult Female Lice Counts",
            color_discrete_sequence=["#e74c3c"],
        )
        fig.add_vline(x=0.5, line_dash="dash", line_color="black",
                      annotation_text="Limit")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No lice data available.")


# ══════════════════════════════════════════════════════════════════════
# BACKTEST PAGE
# ══════════════════════════════════════════════════════════════════════
elif page == "Backtest":
    st.title("Backtesting Engine")

    col1, col2, col3 = st.columns(3)
    ticker = col1.selectbox("Ticker", ["MOWI", "SALM", "LSG"])
    year_start = col2.number_input("Start Year", 2018, 2025, 2018)
    year_end = col3.number_input("End Year", 2018, 2025, 2025)

    if st.button("Run Backtest"):
        engine = BacktestEngine()
        sample_data = engine.generate_sample_lice_data(
            years=(year_start, year_end), n_localities=50
        )

        with st.spinner("Running backtest..."):
            result = engine.run(sample_data, ticker=ticker)
            mc = engine.monte_carlo(result, n_simulations=5000)

        # Results
        st.subheader("Backtest Results")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total P&L", f"NOK {result.total_pnl:,.0f}")
        col2.metric("Sharpe Ratio", f"{result.sharpe_ratio:.2f}")
        col3.metric("Win Rate", f"{result.win_rate:.0f}%")
        col4.metric("Max Drawdown", f"{result.max_drawdown:.1f}%")

        # Equity curve
        fig_eq = go.Figure()
        fig_eq.add_trace(go.Scatter(
            y=result.equity_curve, mode="lines", name="Equity",
            line=dict(color="#2ecc71"),
        ))
        fig_eq.update_layout(title="Equity Curve", yaxis_title="Capital (NOK)")
        st.plotly_chart(fig_eq, use_container_width=True)

        # Trades table
        if result.trades:
            st.subheader("Trade Log")
            st.dataframe(pd.DataFrame(result.trades), use_container_width=True)

        # Monte Carlo
        st.subheader("Monte Carlo Simulation")
        col1, col2, col3 = st.columns(3)
        col1.metric("Mean Return", f"{mc.mean_return:.1f}%")
        col2.metric("P(Profitable)", f"{mc.prob_profitable:.0f}%")
        col3.metric("95th Percentile", f"{mc.percentile_95:.1f}%")

        fig_mc = px.histogram(
            x=mc.distribution, nbins=80,
            title="Monte Carlo Return Distribution",
            labels={"x": "Return (%)"},
            color_discrete_sequence=["#3498db"],
        )
        fig_mc.add_vline(x=0, line_dash="dash", line_color="red")
        st.plotly_chart(fig_mc, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════
# COMPLIANCE PAGE
# ══════════════════════════════════════════════════════════════════════
elif page == "Compliance":
    st.title("Compliance & Audit Trail")

    st.markdown(ComplianceAgent.get_disclaimer())

    st.subheader("Audit Log")
    logs = ComplianceAgent.export_audit_log()
    if logs:
        log_df = pd.DataFrame(logs)
        st.dataframe(log_df, use_container_width=True, height=400)
    else:
        st.info("No audit entries yet.")

    # Performance fees
    st.subheader("Performance Fees")
    with Session() as s:
        fees = s.execute(
            select(PerformanceFee).order_by(PerformanceFee.period_start.desc())
        ).scalars().all()

    if fees:
        fee_df = pd.DataFrame([
            {
                "Period": f.period_start.strftime("%Y-%m") if f.period_start else "",
                "Gross Profit": f"NOK {f.gross_profit:,.0f}" if f.gross_profit else "",
                "Fee Rate": f"{f.fee_rate*100:.0f}%",
                "Fee Amount": f"NOK {f.fee_amount:,.0f}" if f.fee_amount else "",
            }
            for f in fees
        ])
        st.dataframe(fee_df, use_container_width=True)
    else:
        st.info("No performance fees calculated yet.")


# ══════════════════════════════════════════════════════════════════════
# SETTINGS PAGE
# ══════════════════════════════════════════════════════════════════════
elif page == "Settings":
    st.title("Configuration")

    st.subheader("Current Settings")
    st.json({
        "broker_mode": settings.broker_mode,
        "poll_interval_minutes": settings.poll_interval_minutes,
        "performance_fee_rate": f"{settings.performance_fee_rate * 100}%",
        "barentswatch_configured": bool(settings.barentswatch_client_id),
        "database_url": settings.database_url.split("///")[-1],
    })

    st.subheader("Agent Health")
    st.info(
        "Agent health monitoring is available when running the full "
        "orchestrator (python main.py). See the API endpoint /api/health."
    )
