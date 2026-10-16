# Deep Research Synthesis — April 2026
## 5 Research Agents, 30+ Web Sources, 60 Engine Audit

### Agent Results Summary

**Science Agent** — Audited 10 core engines against peer-reviewed literature:
- CRITICAL: Treatment efficacy inconsistency between decision_engine (78%) and treatment_optimizer (87.5%) — FIXED via shared treatment_constants.py
- CRITICAL: Biomass mortality rate 2x too low (0.00015 vs Mowi Handbook 0.00028) — FIXED
- HIGH: Biomass uses outdated SGR model, should migrate to TGC (Thermal Growth Coefficient)
- HIGH: H2O2 treatment efficacy declined to 40-70% due to resistance — updated in constants
- STRONG: Stige lice model (short_term.py) is state-of-the-art, correctly implements 2025 paper
- STRONG: Feed cost engine validated at 0.1% error vs official Fiskeridirektoratet data

**Data + Competitive Agent** — Mapped 13 data sources, 8 competitors:
- AquaCloud went BANKRUPT January 2026 — their 32 former members need a replacement
- Top 3 data integrations: Fiskeridirektoratet full API (free, 8hrs), EUMOFA (free, 12hrs), Fish Pool Index (free weekly, 6hrs)
- No competitor occupies our position combining bio + market + trading + compliance
- Kontali is analyst-driven ($15-50K/yr); we are algorithmic and real-time at 1/10th cost

**Commercial + Legal Agent** — Priced each engine, audited all data licenses:
- Decision Engine: NOK 5-15K/month per site (treatment decision saves 10-30x subscription)
- Event Impact Model: NOK 15-50K/month (fills Bloomberg gap for aquaculture)
- Efficacy Marketplace: Unique — no competing product exists
- Data licenses: BarentsWatch (NLOD 2.0, GREEN), SSB (CC BY 4.0, GREEN), Copernicus (GREEN), Fish Pool/Euronext (YELLOW — needs license agreement)
- EU AI Act: Limited Risk classification (transparency only, DataProvenance already satisfies)
- GDPR: Privacy policy needed before launch; right-to-erasure needed

**Architecture Agent** — Identified critical scaling bottlenecks:
- CRITICAL: No Gunicorn (single process) — FIXED: Dockerfile now uses 4 Gunicorn workers
- CRITICAL: Async pool had NO config (default 5 connections) — FIXED: pool_size=20, max_overflow=40
- CRITICAL: 47 engine files still use sync Session in async endpoints (RESOLVED — verified 2026-10-16: 0 core files import `sqlalchemy.orm.Session`)
- HIGH: Nginx had no gzip, no caching, no rate limiting — FIXED: full production config
- Scaling roadmap: 100 users = 18hrs work, 500 users = 46hrs, 5000 users = 72hrs

**UX Agent** — Evaluated all major pages against Bloomberg/TradingView/Tufte:
- #1 fix: Attention-funnel layout (hero zone → supporting → detail) on Dashboard
- #2 fix: Farm name search replacing locality number input on Farmer Daily
- #3 fix: Confidence intervals on all prediction surfaces
- Key principle: "Every page should answer 'what should I do?' not just 'what is the data?'"
- Mobile: Auto-route farmers to /farmer-daily, cache last decision card offline

### Top 10 Execution Priorities (from research)
1. ~~Harmonize treatment constants~~ — DONE
2. ~~Fix biomass mortality rate~~ — DONE
3. ~~Gunicorn + async pool tuning~~ — DONE
4. ~~Production nginx config~~ — DONE
5. Farmer Daily: farm name search (replace locality number input)
6. Dashboard: attention-funnel layout with hero alert zone
7. Confidence intervals on forward curves and ML predictions
8. Wire Stige model into treatment_optimizer (replace heuristic)
9. Fiskeridirektoratet full API integration
10. GDPR privacy policy + data licensing attributions
