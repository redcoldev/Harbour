# routes/client.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from extensions import get_db
import psycopg

client_bp = Blueprint('client', __name__, url_prefix='/client')


def _table_exists(c, table_name):
    c.execute("SELECT to_regclass(%s) IS NOT NULL AS exists", (f"public.{table_name}",))
    row = c.fetchone()
    return bool(row and row['exists'])


def _calculate_case_balance(c, case_id):
    c.execute("SELECT type, amount, recoverable FROM money WHERE case_id = %s", (case_id,))
    balance = 0.0
    for t in c.fetchall():
        amt = float(t['amount'] or 0)
        if t['type'] == 'Payment':
            balance -= amt
        elif t['type'] in ['Invoice', 'Interest']:
            balance += amt
        elif t['type'] == 'Charge' and t['recoverable']:
            balance += amt
    return round(balance, 2)


@client_bp.route('/<int:client_id>')
@login_required
def client_dashboard(client_id):
    db = get_db()
    c = db.cursor()

    c.execute("SELECT * FROM clients WHERE id = %s", (client_id,))
    client = c.fetchone()
    if not client:
        flash("Client not found")
        return redirect(url_for('case.dashboard'))

    c.execute("""
        SELECT s.*, COALESCE(s.debtor_business_name, s.debtor_first || ' ' || s.debtor_last) AS debtor_name
        FROM cases s
        WHERE s.client_id = %s
        ORDER BY s.open_date DESC
    """, (client_id,))
    cases = c.fetchall()

    for case in cases:
        case['balance'] = _calculate_case_balance(c, case['id'])

    c.execute("SELECT * FROM custom_field_definitions ORDER BY field_name")
    all_fields = c.fetchall()

    # Prefer deterministic slot mapping table; fallback to legacy link table.
    linked_field_ids = []
    try:
        if _table_exists(c, 'client_custom_field_slots'):
            c.execute("SELECT field_id FROM client_custom_field_slots WHERE client_id = %s ORDER BY slot_no", (client_id,))
            linked_field_ids = [row['field_id'] for row in c.fetchall()]
    except psycopg.errors.UndefinedTable:
        linked_field_ids = []

    if not linked_field_ids:
        c.execute("SELECT field_id FROM client_custom_field_link WHERE client_id = %s", (client_id,))
        linked_field_ids = [row['field_id'] for row in c.fetchall()]

    return render_template(
        'client_dashboard.html',
        client=client,
        cases=cases,
        all_fields=all_fields,
        linked_field_ids=linked_field_ids,
    )


@client_bp.route('/update_fields', methods=['POST'])
@login_required
def update_fields():
    db = get_db()
    c = db.cursor()
    client_id = request.form.get('client_id')
    selected_field_ids = request.form.getlist('field_ids')

    if len(selected_field_ids) > 16:
        flash("You can only select up to 16 custom fields for a client.")
        return redirect(url_for('client.client_dashboard', client_id=client_id))

    slots_table_exists = _table_exists(c, 'client_custom_field_slots')

    c.execute("DELETE FROM client_custom_field_link WHERE client_id = %s", (client_id,))
    if slots_table_exists:
        try:
            c.execute("DELETE FROM client_custom_field_slots WHERE client_id = %s", (client_id,))
        except psycopg.errors.UndefinedTable:
            slots_table_exists = False

    for idx, f_id in enumerate(selected_field_ids, start=1):
        c.execute("""
            INSERT INTO client_custom_field_link (client_id, field_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (client_id, f_id))
        if slots_table_exists:
            try:
                c.execute("""
                    INSERT INTO client_custom_field_slots (client_id, slot_no, field_id)
                    VALUES (%s, %s, %s)
                """, (client_id, idx, f_id))
            except psycopg.errors.UndefinedTable:
                slots_table_exists = False

    db.commit()
    flash("Client custom fields updated")
    return redirect(url_for('client.client_dashboard', client_id=client_id))


@client_bp.route('/add_client', methods=['POST'])
@login_required
def add_client():
    db = get_db()
    c = db.cursor()
    c.execute('''
        INSERT INTO clients
        (business_type, business_name, contact_first, contact_last, phone, email, bacs_details, default_interest_rate)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ''', (
        request.form['business_type'],
        request.form['business_name'],
        request.form['contact_first'],
        request.form['contact_last'],
        request.form['phone'],
        request.form['email'],
        request.form['bacs_details'],
        request.form.get('default_interest_rate', 0)
    ))
    db.commit()
    flash('Client added')
    return redirect(url_for('case.dashboard'))


@client_bp.route('/<int:client_id>/cases')
@login_required
def client_cases(client_id):
    db = get_db()
    c = db.cursor()

    c.execute("SELECT * FROM clients WHERE id = %s", (client_id,))
    client = c.fetchone()
    if not client:
        flash("Client not found")
        return redirect(url_for('case.dashboard'))

    c.execute("""
        SELECT id, debtor_business_name, debtor_first, debtor_last, status, open_date
        FROM cases
        WHERE client_id = %s
        ORDER BY open_date DESC
    """, (client_id,))
    cases = c.fetchall()

    for case in cases:
        case['balance'] = _calculate_case_balance(c, case['id'])

    return render_template('client_cases.html', client=client, cases=cases)


@client_bp.route('/rename_client', methods=['POST'])
@login_required
def rename_client():
    db = get_db()
    c = db.cursor()
    client_id = request.form.get('target_id')
    case_id = request.form.get('case_id')
    new_name = request.form.get('new_name')
    if client_id and new_name:
        c.execute("UPDATE clients SET business_name = %s WHERE id = %s", (new_name, client_id))
        db.commit()
    return redirect(url_for('case.dashboard', case_id=case_id))
