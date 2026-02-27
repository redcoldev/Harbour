# Minimal strategy-led case flow design

This is a **lean** design that avoids a large table explosion while still supporting:
- per-client default strategy
- bulk-imported cases auto-starting on that strategy
- status/sub-status derived from strategy progress (instead of stored manually)
- full notes/audit trail for letters, SMS, email, and voice API actions

## Keep and reuse existing tables
- `clients`
- `cases`
- `notes`

## New tables (minimum)

### 1) `strategies`
Stores the complete path definition in JSON so we avoid a separate steps table.

```sql
CREATE TABLE IF NOT EXISTS strategies (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    is_default INTEGER DEFAULT 0,
    version INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    definition_json JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (client_id, name, version)
);
```

`definition_json` shape (example):
```json
{
  "start_status": "Open",
  "steps": [
    {"idx": 1, "code": "LETTER_1", "channel": "letter", "offset_days": 0, "status": "Pre-Legal", "substatus": "L1 Sent"},
    {"idx": 2, "code": "SMS_1", "channel": "sms", "offset_days": 3, "status": "Pre-Legal", "substatus": "SMS Sent"},
    {"idx": 3, "code": "EMAIL_1", "channel": "email", "offset_days": 7, "status": "Pre-Legal", "substatus": "Email Sent"}
  ]
}
```

### 2) `case_strategy`
Single runtime row per case that tracks where it currently is in the strategy.

```sql
CREATE TABLE IF NOT EXISTS case_strategy (
    case_id INTEGER PRIMARY KEY REFERENCES cases(id) ON DELETE CASCADE,
    strategy_id INTEGER NOT NULL REFERENCES strategies(id),
    step_index INTEGER DEFAULT 0,
    next_action_date DATE,
    last_executed_at TIMESTAMP,
    paused INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Minimal changes to existing tables

### `clients`
Add a default strategy pointer:

```sql
ALTER TABLE clients
ADD COLUMN IF NOT EXISTS default_strategy_id INTEGER REFERENCES strategies(id);
```

### `cases`
Keep legacy `status/substatus/next_action_date` for compatibility during transition, but treat them as cache/UI fields only.

## Event/audit logging with no new tables
Use the existing `notes` table for all execution records:
- `type='Strategy'` for step movement
- `type='SMS' | 'Email' | 'Letter' | 'Voice'` for outbound actions
- store provider IDs and payload summaries in `note`

This keeps auditability without adding separate provider log tables.

## How to derive status/sub-status (no manual case status entry)
At read time:
1. load `case_strategy.step_index`
2. fetch step from `strategies.definition_json.steps[step_index]`
3. display `step.status` and `step.substatus`

At execution time:
1. send API call (SMS/email/voice/letter service)
2. write result in `notes`
3. increment `step_index`
4. compute/set `next_action_date`

## Bulk import flow (minimal)
For each imported case:
1. insert into `cases`
2. resolve `clients.default_strategy_id`
3. insert `case_strategy(case_id, strategy_id, step_index=0, next_action_date=today)`
4. write one `notes` row: `type='Strategy'`, `note='Case entered strategy <name> at step 0'`

## Why this is the smallest practical model
- only **2 new tables** (`strategies`, `case_strategy`)
- no dedicated steps table (steps are JSON)
- no dedicated provider-event table (reuse `notes`)
- supports visual builder later by editing JSON definition

## Suggested transition sequence
1. add new tables + `clients.default_strategy_id`
2. backfill one default strategy per client
3. create `case_strategy` rows for existing cases
4. change UI to read status/sub-status from strategy runtime
5. deprecate manual status edits once stable
