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
            WHERE table_name = %s
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
