# =============================================================================
#  ADMIN ROUTES
#  • /db_structure  – shows all tables/columns (useful for debugging)
#  • API key management (generate, list, revoke)
#  Only logged-in users can access these
# =============================================================================

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from extensions import get_db
import uuid

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/db_structure')
@login_required
def db_structure():
    db = get_db()
    c = db.cursor()

    # Get all tables
    c.execute("""
        SELECT table_name 
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = [row['table_name'] for row in c.fetchall()]

    structure = {}
    for t in tables:
        c.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            ORDER BY ordinal_position
        """, (t,))
        structure[t] = c.fetchall()

    c.execute("""
        SELECT
            tc.table_name AS source_table,
            kcu.column_name AS source_column,
            ccu.table_name AS target_table,
            ccu.column_name AS target_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
        ORDER BY source_table, source_column
    """)
    links = c.fetchall()

    return render_template('db_structure.html', structure=structure, links=links)


@admin_bp.route('/api/db_cleanse', methods=['POST'])
@login_required
def db_cleanse():
    """
    One-click DB cleanup/backfill for migration alignment.
    - Drops legacy tables that are no longer used by app code.
    - Ensures strategy runtime tables exist.
    - Seeds one default strategy if missing.
    - Backfills clients.default_strategy_id and case_strategy rows.
    """
    db = get_db()
    c = db.cursor()

    try:
        # Ensure new runtime tables exist even if init migration wasn't run.
        c.execute("""
            CREATE TABLE IF NOT EXISTS strategies (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                is_active INTEGER DEFAULT 1,
                definition_json JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
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

        # Some older databases may not have custom field tables yet.
        c.execute("""
            CREATE TABLE IF NOT EXISTS custom_field_definitions (
                id SERIAL PRIMARY KEY,
                field_name TEXT NOT NULL UNIQUE,
                field_type TEXT DEFAULT 'text'
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS client_custom_field_slots (
                client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
                slot_no INTEGER NOT NULL CHECK (slot_no BETWEEN 1 AND 16),
                field_id INTEGER NOT NULL REFERENCES custom_field_definitions(id),
                PRIMARY KEY (client_id, slot_no),
                UNIQUE (client_id, field_id)
            )
        """)

        c.execute("ALTER TABLE clients ADD COLUMN IF NOT EXISTS default_strategy_id INTEGER REFERENCES strategies(id)")

        # Seed a baseline strategy so every case can have a runtime row.
        c.execute("SELECT id FROM strategies ORDER BY id LIMIT 1")
        row = c.fetchone()
        if row:
            default_strategy_id = row['id']
            seeded_strategy = False
        else:
            c.execute("""
                INSERT INTO strategies (name, definition_json)
                VALUES (
                    'Default Recovery Strategy',
                    %s::jsonb
                )
                RETURNING id
            """, ('{\"start_status\":\"Open\",\"steps\":[{\"idx\":1,\"code\":\"WELCOME\",\"status\":\"Pre-Legal\",\"substatus\":\"New Case\"},{\"idx\":2,\"code\":\"SMS_1\",\"status\":\"Pre-Legal\",\"substatus\":\"SMS Sent\"},{\"idx\":3,\"code\":\"EMAIL_1\",\"status\":\"Pre-Legal\",\"substatus\":\"Email Sent\"}]}',))
            default_strategy_id = c.fetchone()['id']
            seeded_strategy = True

        c.execute("UPDATE clients SET default_strategy_id = %s WHERE default_strategy_id IS NULL", (default_strategy_id,))
        clients_backfilled = c.rowcount

        c.execute("""
            INSERT INTO case_strategy (case_id, strategy_id, step_index, next_action_date)
            SELECT s.id, COALESCE(c.default_strategy_id, %s), 0, COALESCE(s.next_action_date::date, CURRENT_DATE)
            FROM cases s
            JOIN clients c ON c.id = s.client_id
            LEFT JOIN case_strategy cs ON cs.case_id = s.id
            WHERE cs.case_id IS NULL
        """, (default_strategy_id,))
        case_strategy_backfilled = c.rowcount

        # Drop legacy, unused tables (visible in DB structure and confusing).
        c.execute("DROP TABLE IF EXISTS debtor_tokens")
        c.execute("DROP TABLE IF EXISTS outbound_logs")

        db.commit()
        return jsonify({
            'ok': True,
            'seeded_strategy': seeded_strategy,
            'default_strategy_id': default_strategy_id,
            'clients_backfilled': clients_backfilled,
            'case_strategy_backfilled': case_strategy_backfilled,
            'dropped_tables': ['debtor_tokens', 'outbound_logs']
        })
    except Exception as exc:
        db.rollback()
        return jsonify({'ok': False, 'error': str(exc)}), 500

# =============================================================================
#  API KEY ENDPOINTS (used by the modal in dashboard.html)
# =============================================================================

@admin_bp.route('/api/generate_key', methods=['POST'])
@login_required
def generate_key():
    db = get_db()
    c = db.cursor()
    key = str(uuid.uuid4())
    name = request.json.get('name', 'API Key')
    # Hard-coded client_id = 1 for now (change later if needed)
    c.execute("INSERT INTO api_keys (client_id, key, name) VALUES (1, %s, %s)", (key, name))
    db.commit()
    return jsonify({'key': key})


@admin_bp.route('/api/keys')
@login_required
def list_keys():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id, name FROM api_keys WHERE active = 1")
    keys = [{'id': r['id'], 'name': r['name']} for r in c.fetchall()]
    return jsonify(keys)


@admin_bp.route('/api/revoke_key/<int:key_id>', methods=['POST'])
@login_required
def revoke_key(key_id):
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE api_keys SET active = 0 WHERE id = %s", (key_id,))
    db.commit()
    return '', 204
