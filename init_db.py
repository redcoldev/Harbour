# init_db.py
import psycopg

def init_db(DATABASE_URL):
    conn = psycopg.connect(DATABASE_URL)
    c = conn.cursor()

    # --- EXISTING TABLES (Preserved with IF NOT EXISTS) ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id SERIAL PRIMARY KEY,
        business_type TEXT NOT NULL,
        business_name TEXT NOT NULL,
        contact_first TEXT,
        contact_last TEXT,
        phone TEXT,
        email TEXT,
        bacs_details TEXT,
        default_interest_rate REAL DEFAULT 0.0,
        lifecycle_state TEXT NOT NULL DEFAULT 'active' CHECK (
            lifecycle_state IN ('active', 'closed', 'archived')
        )
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS cases (
        id SERIAL PRIMARY KEY,
        client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
        debtor_business_type TEXT,
        debtor_business_name TEXT,
        debtor_first TEXT,
        debtor_last TEXT,
        phone TEXT,
        email TEXT,
        postcode TEXT,
        status TEXT DEFAULT 'Open',
        substatus TEXT,
        next_action_date TEXT,
        open_date DATE DEFAULT CURRENT_DATE,
        mode TEXT NOT NULL DEFAULT 'automated' CHECK (
            mode IN ('automated', 'manual', 'legal_hold')
        ),
        lifecycle_state TEXT NOT NULL DEFAULT 'active' CHECK (
            lifecycle_state IN ('active', 'closed', 'archived')
        )
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash BYTEA NOT NULL,
        role TEXT DEFAULT 'user'
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS money (
        id SERIAL PRIMARY KEY,
        case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
        type TEXT NOT NULL,
        amount REAL NOT NULL,
        transaction_date DATE DEFAULT CURRENT_DATE,
        created_by INTEGER NOT NULL REFERENCES users(id),
        description TEXT,
        recoverable INTEGER DEFAULT 0,
        billable INTEGER DEFAULT 0,
        vat_amount REAL DEFAULT 0.0,
        billed INTEGER DEFAULT 0,
        billeddate DATE,
        charge_id INTEGER
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS notes (
        id SERIAL PRIMARY KEY,
        case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
        type TEXT NOT NULL,
        created_by INTEGER NOT NULL REFERENCES users(id),
        note TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Strategy definitions are reusable by any client.
    c.execute("""
    CREATE TABLE IF NOT EXISTS strategies (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        is_active INTEGER DEFAULT 1,
        definition_json JSONB NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Runtime pointer for a case's progress through its chosen strategy.
    c.execute("""
    CREATE TABLE IF NOT EXISTS case_strategy (
        case_id INTEGER PRIMARY KEY REFERENCES cases(id) ON DELETE CASCADE,
        strategy_id INTEGER NOT NULL REFERENCES strategies(id),
        step_index INTEGER DEFAULT 0,
        next_action_date DATE,
        last_executed_at TIMESTAMP,
        paused INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        id SERIAL PRIMARY KEY,
        client_id INTEGER NOT NULL REFERENCES clients(id),
        key TEXT UNIQUE NOT NULL,
        name TEXT,
        active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS case_status_history (
        id SERIAL PRIMARY KEY,
        case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
        old_status TEXT,
        old_substatus TEXT,
        new_status TEXT,
        new_substatus TEXT,
        changed_by INTEGER NOT NULL REFERENCES users(id),
        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        old_next_action_date DATE
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS charges (
        id SERIAL PRIMARY KEY,
        code TEXT NOT NULL,
        description TEXT NOT NULL,
        charge_type TEXT NOT NULL DEFAULT 'flat' CHECK (
            charge_type IN ('flat', 'percent')
        ),
        default_amount REAL,
        percent_rate REAL,
        min_amount REAL,
        max_amount REAL,
        category TEXT NOT NULL CHECK (
            category IN (
                'Commission', 'Ancillary', 'CCJ', 'defence',
                'Insolvency', 'Enforcement'
            )
        ),
        UNIQUE(code)
    )
    """)

    # --- NEW CUSTOM FIELDS TABLES ---

    # 1. Master list of available custom field types
    c.execute("""
    CREATE TABLE IF NOT EXISTS custom_field_definitions (
        id SERIAL PRIMARY KEY,
        field_name TEXT NOT NULL UNIQUE,
        field_type TEXT DEFAULT 'text' -- e.g., 'text', 'date', 'number'
    )
    """)

    # 2. Link table: which clients use which custom fields?
    c.execute("""
    CREATE TABLE IF NOT EXISTS client_custom_field_link (
        client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
        field_id INTEGER REFERENCES custom_field_definitions(id) ON DELETE CASCADE,
        PRIMARY KEY (client_id, field_id)
    )
    """)

    # Explicit slot mapping (1..16) for each client's 4x4 custom field grid.
    c.execute("""
    CREATE TABLE IF NOT EXISTS client_custom_field_slots (
        client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
        slot_no INTEGER NOT NULL CHECK (slot_no BETWEEN 1 AND 16),
        field_id INTEGER NOT NULL REFERENCES custom_field_definitions(id),
        PRIMARY KEY (client_id, slot_no),
        UNIQUE (client_id, field_id)
    )
    """)

    # 3. Data table: the actual values for a specific case
    c.execute("""
    CREATE TABLE IF NOT EXISTS case_custom_values (
        case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
        field_id INTEGER REFERENCES custom_field_definitions(id) ON DELETE CASCADE,
        field_value TEXT,
        PRIMARY KEY (case_id, field_id)
    )
    """)

    # --- SAFE MIGRATIONS (Column checking) ---
    c.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'money' AND column_name = 'note'
    """)
    if c.fetchone():
        c.execute("ALTER TABLE money RENAME COLUMN note TO description")

    # Add missing columns to existing tables if they don't exist
    c.execute("ALTER TABLE money ADD COLUMN IF NOT EXISTS vat_amount REAL DEFAULT 0.0")
    c.execute("ALTER TABLE money ADD COLUMN IF NOT EXISTS billed INTEGER DEFAULT 0")
    c.execute("ALTER TABLE money ADD COLUMN IF NOT EXISTS billeddate DATE")
    c.execute("ALTER TABLE money ADD COLUMN IF NOT EXISTS charge_id INTEGER REFERENCES charges(id)")
    c.execute("ALTER TABLE case_status_history ADD COLUMN IF NOT EXISTS old_next_action_date DATE")
    c.execute("ALTER TABLE clients ADD COLUMN IF NOT EXISTS default_strategy_id INTEGER REFERENCES strategies(id)")
    c.execute("ALTER TABLE clients ADD COLUMN IF NOT EXISTS lifecycle_state TEXT NOT NULL DEFAULT 'active' CHECK (lifecycle_state IN ('active', 'closed', 'archived'))")
    c.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS mode TEXT NOT NULL DEFAULT 'automated' CHECK (mode IN ('automated', 'manual', 'legal_hold'))")
    c.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS lifecycle_state TEXT NOT NULL DEFAULT 'active' CHECK (lifecycle_state IN ('active', 'closed', 'archived'))")
    c.execute("ALTER TABLE charges ADD COLUMN IF NOT EXISTS charge_type TEXT NOT NULL DEFAULT 'flat' CHECK (charge_type IN ('flat', 'percent'))")
    c.execute("ALTER TABLE charges ADD COLUMN IF NOT EXISTS default_amount REAL")
    c.execute("ALTER TABLE charges ADD COLUMN IF NOT EXISTS percent_rate REAL")
    c.execute("ALTER TABLE charges ADD COLUMN IF NOT EXISTS min_amount REAL")
    c.execute("ALTER TABLE charges ADD COLUMN IF NOT EXISTS max_amount REAL")

    # Non-deletion policy: block hard deletes for core entities.
    c.execute("""
    CREATE OR REPLACE FUNCTION prevent_hard_delete()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'Hard delete disabled for %. Use lifecycle_state instead.', TG_TABLE_NAME;
    END;
    $$ LANGUAGE plpgsql;
    """)

    c.execute("DROP TRIGGER IF EXISTS prevent_clients_delete ON clients")
    c.execute("""
    CREATE TRIGGER prevent_clients_delete
    BEFORE DELETE ON clients
    FOR EACH ROW EXECUTE FUNCTION prevent_hard_delete();
    """)

    c.execute("DROP TRIGGER IF EXISTS prevent_cases_delete ON cases")
    c.execute("""
    CREATE TRIGGER prevent_cases_delete
    BEFORE DELETE ON cases
    FOR EACH ROW EXECUTE FUNCTION prevent_hard_delete();
    """)

    conn.commit()
    conn.close()
