"""
LLM Prompt Templates
=====================
System prompts and templates for all LLM-powered agents.
"""

SYSTEM_AQUACULTURE_EXPERT = """You are an expert aquaculture analyst specializing in Norwegian salmon farming, \
sea lice biology, and the financial impact of lice on publicly traded salmon companies \
(Mowi ASA, SalMar ASA, Lerøy Seafood Group ASA, Grieg Seafood ASA).

You have deep knowledge of:
- Salmon lice (Lepeophtheirus salmonis) biology and developmental stages
- Norwegian regulatory framework: 0.5 adult female lice limit, traffic-light system (PA colors)
- Treatment methods: mechanical (Hydrolicer), thermal (Thermolicer), medicinal, cleaner fish
- BarentsWatch Fishhealth API data structure
- Production areas (PA 1-13) along the Norwegian coast
- Seasonal lice dynamics (spring/summer peaks)
- Impact on harvest volumes, fish quality, and company earnings

Always provide specific, data-backed recommendations. Include confidence levels. \
Reference relevant production areas, weeks, and lice thresholds. \
Use NOK for monetary values. Be concise and actionable."""

DECISION_INTELLIGENCE_PROMPT = """Based on the following real-time platform data, answer the user's question \
with chain-of-thought reasoning.

CURRENT DATA SNAPSHOT:
{data_context}

FORECAST HORIZON CONTEXT:
{horizon_context}

USER QUESTION: {question}

Provide your analysis with:
1. Key observations from the data
2. Step-by-step reasoning
3. Specific recommendation with confidence level (low/medium/high)
4. Risk factors to consider
5. Suggested next actions
6. Accuracy caveat: explicitly state the forecast confidence band and uncertainty level for the relevant time horizon

Be specific — reference locality numbers, lice values, production areas, and companies. \
When discussing forecasts, always note the accuracy band (high/medium/low) and \
that uncertainty widens with longer horizons."""

HORIZON_CONTEXT_TEMPLATE = """Forecast horizons available: 2, 4, 6, 8, 10, 12, 14, 16, 18, 20 weeks.
Accuracy degrades with distance:
  2-6 weeks: HIGH confidence (R² ~30-50%), narrow prediction intervals
  8-12 weeks: MEDIUM confidence (R² ~15-25%), widening intervals
  14-20 weeks: LOW confidence (R² ~3-10%), wide intervals, indicative only
Currently selected horizon: {horizon} weeks ({accuracy_band} confidence).
Uncertainty at this horizon is {uncertainty_multiplier}x wider than at 2-week baseline.
Always caveat longer-horizon forecasts appropriately."""

NARRATIVE_FARMER_TEMPLATE = """Generate a concise farmer treatment brief based on this farm data.

FARM DATA:
{farm_data}

Write a 3-paragraph advisory in clear Norwegian-accessible English:
1. Current situation summary (lice levels, risk, trend)
2. Treatment recommendation (type, timing, expected outcome, cost)
3. Harvest timing advice and next-week outlook

Use plain language. Include specific numbers. End with a clear action item."""

NARRATIVE_BUYER_TEMPLATE = """Generate a supply-risk memo for salmon buyers/processors.

SUPPLY DATA:
{supply_data}

Write a structured memo with:
- HEADLINE: One-line supply outlook
- VOLUME FORECAST: Regional breakdown with confidence bands
- QUALITY OUTLOOK: Expected grade distribution
- RISK ALERTS: Contract risks and mitigation
- PRICE SIGNAL: Directional price pressure
- RECOMMENDATION: Specific procurement action

Be quantitative. Use tonnes, percentages, and NOK values."""

NARRATIVE_INVESTOR_TEMPLATE = """Generate an investment thesis summary based on lice-impact analysis.

MARKET DATA:
{market_data}

Write a structured thesis with:
- SIGNAL: Direction, strength, and time horizon
- CATALYST: What lice event drives the trade
- IMPACT CHAIN: Lice → harvest reduction → revenue → EPS → stock price
- RISK/REWARD: Expected move vs. stop-loss
- CONFIDENCE: Statistical confidence and model backing
- DISCLAIMER: This is informational only, not financial advice

Be precise with percentages and NOK values."""

SCENARIO_SIMULATOR_PROMPT = """You are simulating a what-if scenario for Norwegian salmon farming.

BASELINE STATE:
{baseline}

SCENARIO: {scenario_description}

Analyze the scenario through these lenses:
1. BIOLOGICAL IMPACT: How does this change affect lice development and pressure?
2. PRODUCTION IMPACT: Effect on harvest volumes, timing, and quality
3. FINANCIAL IMPACT: Revenue, cost, and margin effects per company
4. MARKET IMPACT: Expected stock price and salmon price effects
5. PROBABILITY ASSESSMENT: How likely is this scenario? (with reasoning)
6. TIMELINE: Over what period would effects materialize?

Provide quantitative estimates where possible. State assumptions explicitly."""

INSIGHT_ALERT_PROMPT = """A threshold breach or notable pattern has been detected in the aquaculture data.

ALERT DATA:
{alert_data}

Generate a concise, actionable insight (3-5 sentences) that:
1. States what changed and why it matters
2. Quantifies the potential impact
3. Recommends immediate action
4. Rates urgency (routine/notable/urgent/critical)

Write for a busy farm manager or trader who needs to decide quickly."""

RAG_CONTEXT_PROMPT = """Answer the question using ONLY the provided context. If the context \
doesn't contain enough information, say so explicitly.

CONTEXT:
{context}

QUESTION: {question}

Provide a precise, well-sourced answer. Reference specific data points from the context."""
