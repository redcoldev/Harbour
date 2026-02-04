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
        default_interest_rate REAL DEFAULT 0.0
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
        open_date DATE DEFAULT CURRENT_DATE
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
        category TEXT NOT NULL CHECK (
            category IN (
                'Commission', 'Ancillary', 'CCJ', 'defence',
                'Insolvency', 'Enforcement'
            )
        )
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

    conn.commit()
    conn.close()
