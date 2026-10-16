# Role: Product Designer (field & mobile experience)

**Type:** contract or full-time, remote-friendly (co-located with a Norwegian or
Chilean producer for at least one week)
**Reports to:** founder (product)

## Why this role exists

The **Operator** plan is where the recurring revenue is: lice forecasting, quota
headroom, treatment decisions and harvest timing — used by people standing on a
feed barge or in a service boat, in gloves, in rain, often with no signal. Today the
experience is a desktop dashboard. The field experience is the product gap.

## What you will own

1. **The operator's daily loop** — design the field/mobile flow for: check lice
   pressure and quota headroom → decide treat-or-hold → log the outcome. The outcome
   log is what feeds treatment efficacy, so it must be fast enough to be honest.
2. **Offline capture with honest sync** — a design where an offline entry is shown
   as *pending* (never silently lost, never shown as synced). This mirrors the
   platform's provenance contract: if the system does not know something, it says so.
3. **Degraded-state design** — every premium/degraded state the platform emits has
   to look deliberate: the 402 upgrade payload, `is_live: false` badges, the
   `degraded`/`synthetic_only` freshness states, and "not yet published" on
   `/accuracy`. Your job is to make honesty look like quality, not like failure.
4. **Two-audience design** — the same numbers serve a producer (act this week) and
   a trader (price this week). Design the framing, not two products.
5. **Design system discipline** — extend the existing component language
   (`GlassCard`, `KPICard`, the `oc_*`/`aquaintel_*` state conventions) rather than
   inventing a parallel one.

## What success looks like (first quarter)

| Metric | Target |
|---|---|
| Field flow usable one-handed in gloves, on a 5-inch screen | validated with ≥ 5 operators |
| Median time to log a treatment outcome | ≤ 30 seconds |
| Offline capture: zero silent losses in a 2-week field trial | verified against the API |
| Operator plan trial→paid conversion | ≥ 30% |
| Degraded/premium states | 100% designed, no raw error strings in UI |

## What you need

- Portfolio showing **field or industrial** products (marine, offshore, agriculture,
  logistics) — not dashboard-only work.
- Comfortable running your own research: you will be on a boat, in a service boat,
  or on a quayside, not only in a workshop room.
- Fluency with data-honesty UX: you can design a state that says "this source is
  degraded" without making the product look broken.
- Ability to work directly in the codebase's design tokens with an engineer
  (React/Next.js + Tailwind-level fluency is expected).

## First 30 days

1. Read `docs/INDICES.md`, `docs/DESIGN_PARTNERS.md`, and the `/indices` and
   `/accuracy` pages; then write a one-page critique of what an operator sees today.
2. Spend at least two days with a producer (a design partner) — watch the morning
   lice/quota review as it actually happens.
3. Prototype the one-handed field flow and test it with ≥ 3 operators.
4. Ship one real page improvement (not a mock) and measure the effect on pilot
   metric recording.

## What we will not ask you to do

- To hide degraded data or make a gap look like a feature.
- To design a "performance fee" flow — it is deferred and must not be advertised.
- To design recommendation/advice language ("you should harvest") — see
  `docs/ADVICE_BOUNDARY.md`; the product presents indicators and their method.
