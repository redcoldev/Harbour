# Simplified core model: follow-up questions before schema lock

Thanks for the detailed answers. Based on your direction, this is now the likely shape:

- `case` is the operational center of the dashboard.
- A client can have many cases.
- Cases cannot exist without a client.
- One client has one selected default strategy.
- A case starts from the client strategy but may later enter manual/exception flow.
- Notes are case-only.
- Custom fields are globally defined but selected per client (up to 16) and valued per case.
- Money is a shared transaction ledger filtered by case.
- Charge templates are reusable defaults, not case-owned.
- Cases and clients are never deletable.

The questions below are the ones that matter most to get the **foundations right** and avoid table bolt-ons.

## A) Strategy runtime and manual mode

1. When a case leaves normal strategy flow, should this be a formal state like `mode = automated | manual | legal_hold`?
2. In manual mode, can users still execute the next strategy step occasionally, or is strategy progression fully frozen?
3. Should manual actions (queue handling, installment setup, dispute handling) be represented as:
   - strategy step types, or
   - separate case tasks/events?
4. For your ribbon request (last 3 + next 3 strategy events), do you want:
   - planned events included even if not yet executed,
   - and failed events (e.g., SMS provider error) shown as well?

## B) Custom fields model (client-selected, case-valued)

5. Should each client lock exactly 16 field slots always (4x4), or can they use fewer than 16?
6. If a client changes one slot mapping later, should old case values be preserved against the old field definition for audit/reporting?
7. Can one global custom field be used by many clients at once? (expected yes)
8. Are dropdown options fixed globally, or can each client override options for the same field?
9. Should all custom field values be report-filterable with typed operators (`=`, `>`, `between`, `contains`)?

## C) Money ledger design

10. Do you want an append-only ledger (recommended) where corrections are reversal transactions instead of edits/deletes?
11. Should transaction types be fixed enum values from day one (charge, interest, invoice, payment, refund, adjustment, writeoff)?
12. Do you want the balance always computed from ledger rows (source of truth), rather than storing a mutable case balance?
13. For multi-currency later, is base currency acceptable now with design prepared for currency per transaction?
14. Should exchange rates be snapshot-stored on each FX transaction (future-safe)?

## D) Charge templates vs posted transactions

15. Should a charge template store:
   - flat amount,
   - percent formula,
   - and minimum/maximum caps?
16. When applying a template to a case, should the generated transaction keep a copy of the formula inputs used at that time?
17. Can users override calculated amounts before posting, or must template calculation be strict?

## E) Security, users, teams, and visibility

18. Since case-level restriction is not required, do you still want team ownership for routing/work queues/report slices?
19. Should @mentions notify only within a team by default, or org-wide?
20. Do role levels need hard finance controls (e.g., who can post adjustments/write-offs)?

## F) API and integrations

21. Confirm if we should model two key classes:
   - outbound provider credentials (SMS/email/voice vendors), and
   - optional client-facing API keys later.
22. Do provider actions need retry policy metadata in the DB (attempt count, last error, next retry)?
23. Is a limited retention policy acceptable for verbose provider payload logs to control storage growth?

## G) Non-deletion policy and data lifecycle

24. For "never delete client/case", do you want a strict archive state (`active`, `closed`, `archived`) instead?
25. For notes and transactions, should delete be forbidden for all roles, with correction via follow-up entries only?
26. Do you need immutable audit events only for sensitive actions (finance/permissions), or for all updates?

## H) Decisions to lock immediately (to prevent rework)

Please choose one option in each:

27. **Core pattern:**
   - A) strict relational core + typed extension tables (recommended)
   - B) relational core + heavy JSON fields
28. **Strategy steps storage:**
   - A) JSON definition with runtime pointer (faster delivery)
   - B) normalized strategy_steps table (stronger querying)
29. **Custom fields values storage:**
   - A) typed columns by value type table (recommended for reporting)
   - B) single JSON value column (faster build, weaker reporting)
30. **Finance integrity:**
   - A) append-only ledger (recommended)
   - B) editable transaction rows

---

If you answer these 30 items, we can produce a schema that should survive major future expansion without bolt-on tables.
