# What happens now (Phase 1 recode)

You asked: "aren’t you going to recode everything now?"

Short answer: **yes, but safely in phases** so we don't break the app while rebuilding foundations.

## What I changed in this commit (foundation pass)

1. Added formal lifecycle state to clients and cases (`active`, `closed`, `archived`).
2. Added a formal case mode (`automated`, `manual`, `legal_hold`).
3. Added strategy runtime tables:
   - `strategies`
   - `case_strategy`
4. Added client default strategy pointer (`clients.default_strategy_id`).
5. Upgraded charge templates to support flat/percent + caps.
6. Added explicit client custom-field slot table (1..16) for your 4x4 grid.
7. Added DB-level hard-delete protection for clients and cases.

## What this means

- We now have the core structures needed to move from ad-hoc status changes to strategy-driven case flow.
- We can keep building without adding random bolt-on tables.
- Existing features remain usable while we migrate behavior.

## Next implementation phases

## Phase 2 — data migration

- Create default strategy records.
- Backfill each client's `default_strategy_id`.
- Create `case_strategy` rows for all existing cases.
- Populate missing client custom-field slots.

## Phase 3 — app behavior switch

- Case create flow pulls strategy from client by default.
- Case screen ribbon shows last 3 and next 3 strategy events.
- "Manual mode" behavior starts using `cases.mode`.
- Money views compute values from transaction rows.

## Phase 4 — locking and cleanup

- Remove old/manual paths that conflict with strategy flow.
- Add role checks for sensitive money actions.
- Tighten reporting for custom field filters.

## Important

I have **not** done the full UI/route rewrite in one jump yet. This commit creates the right data backbone first.
That avoids a dangerous big-bang rewrite and lets us move fast without breaking core operations.
