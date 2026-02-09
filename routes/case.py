# case.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import get_db
from datetime import date
import json

@case_bp.route('/test')
def test():
    return "TEST PAGE WORKS"


case_bp = Blueprint('case', __name__)

# ────────────────────────────────────────────────
# SEARCH ENDPOINTS
# ────────────────────────────────────────────────

@case_bp.route('/search')
@login_required
def search():
    q = request.args.get('q', '').strip().lower()
    if len(q) < 2:
        return jsonify([])

    db = get_db()
    c = db.cursor()
    like = f"%{q}%"

    sql = """
        SELECT DISTINCT
            c.id as client_id, c.business_name as client_name,
            s.id as case_id,
            COALESCE(s.debtor_business_name, s.debtor_first || ' ' || s.debtor_last) as debtor_name,
            s.postcode, s.email, s.phone
        FROM cases s
        JOIN clients c ON s.client_id = c.id
        WHERE LOWER(c.business_name) LIKE %s
           OR LOWER(COALESCE(s.debtor_business_name, s.debtor_first || ' ' || s.debtor_last)) LIKE %s
           OR LOWER(s.email || '') LIKE %s
           OR LOWER(s.phone || '') LIKE %s
           OR LOWER(s.postcode || '') LIKE %s
        ORDER BY c.business_name, s.id
        LIMIT 50
    """
    c.execute(sql, (like, like, like, like, like))
    results = [dict(row) for row in c.fetchall()]
    return jsonify(results)


@case_bp.route('/client_search')
@login_required
def client_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    db = get_db()
    c = db.cursor()
    like = f"%{q.lower()}%"
    c.execute("SELECT id, business_name as name FROM clients WHERE LOWER(business_name) LIKE %s ORDER BY business_name LIMIT 20", (like,))
    results = [{'id': r['id'], 'name': r['name']} for r in c.fetchall()]
    return jsonify(results)


# ────────────────────────────────────────────────
# ADD CASE / TRANSACTION / NOTE
# ────────────────────────────────────────────────

@case_bp.route('/add_case', methods=['POST'])
@login_required
def add_case():
    db = get_db()
    c = db.cursor()

    try:
        c.execute('''
            INSERT INTO cases (
                client_id, debtor_business_type, debtor_business_name,
                debtor_first, debtor_last, phone, email, postcode, next_action_date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (
            request.form['client_id'],
            request.form.get('debtor_business_type'),
            request.form.get('debtor_business_name'),
            request.form['debtor_first'],
            request.form['debtor_last'],
            request.form.get('phone'),
            request.form.get('email'),
            request.form.get('postcode', ''),
            request.form.get('next_action_date') or None
        ))
        new_case_id = c.fetchone()['id']
        db.commit()
        flash('Case added successfully', 'success')
        return redirect(url_for('case.dashboard', case_id=new_case_id))
    except Exception as e:
        db.rollback()
        flash(f'Error adding case: {str(e)}', 'danger')
        return redirect(url_for('case.dashboard'))


@case_bp.route('/add_transaction', methods=['POST'])
@login_required
def add_transaction():
    db = get_db()
    c = db.cursor()

    recoverable = 1 if request.form.get('recoverable') else 0
    billable = 1 if request.form.get('billable') else 0

    try:
        c.execute('''
            INSERT INTO money (
                case_id, type, amount, created_by, description,
                transaction_date, recoverable, billable
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            request.form['case_id'],
            request.form['type'],
            request.form['amount'],
            current_user.id,
            request.form.get('note', ''),
            request.form.get('transaction_date') or date.today().isoformat(),
            recoverable,
            billable
        ))
        db.commit()
        flash('Transaction added', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error adding transaction: {str(e)}', 'danger')

    return redirect(url_for('case.dashboard', case_id=request.form['case_id']))


@case_bp.route('/add_note', methods=['POST'])
@login_required
def add_note():
    db = get_db()
    c = db.cursor()

    try:
        c.execute('''
            INSERT INTO notes (case_id, type, note, created_by)
            VALUES (%s, %s, %s, %s)
        ''', (
            request.form['case_id'],
            request.form['type'],
            request.form['note'],
            current_user.id
        ))
        db.commit()
        flash('Note added', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error adding note: {str(e)}', 'danger')

    return redirect(url_for('case.dashboard', case_id=request.form['case_id']))


# ────────────────────────────────────────────────
# GET / EDIT / DELETE TRANSACTION
# ────────────────────────────────────────────────

@case_bp.route('/get_transaction/<int:trans_id>')
@login_required
def get_transaction(trans_id):
    db = get_db()
    c = db.cursor()
    c.execute("""
        SELECT id, type, amount, description, recoverable, billable
        FROM money WHERE id = %s
    """, (trans_id,))
    row = c.fetchone()
    if not row:
        return jsonify({"error": "Transaction not found"}), 404

    return jsonify({
        "id": row["id"],
        "type": row["type"],
        "amount": float(row["amount"]),
        "description": row["description"] or "",
        "recoverable": bool(row["recoverable"]),
        "billable": bool(row["billable"])
    })


@case_bp.route('/edit_transaction', methods=['POST'])
@login_required
def edit_transaction():
    db = get_db()
    c = db.cursor()

    recoverable = 1 if request.form.get('recoverable') else 0
    billable = 1 if request.form.get('billable') else 0

    try:
        c.execute('''
            UPDATE money
            SET amount = %s,
                description = %s,
                recoverable = %s,
                billable = %s
            WHERE id = %s
        ''', (
            request.form['amount'],
            request.form.get('note', ''),
            recoverable,
            billable,
            request.form['trans_id']
        ))
        db.commit()
        flash('Transaction updated', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error updating transaction: {str(e)}', 'danger')

    case_id = request.form.get('case_id')
    if case_id:
        return redirect(url_for('case.dashboard', case_id=case_id))
    return redirect(url_for('case.dashboard'))


@case_bp.route('/delete_transaction/<int:trans_id>', methods=['POST'])
@login_required
def delete_transaction(trans_id):
    db = get_db()
    c = db.cursor()

    c.execute("SELECT case_id FROM money WHERE id = %s", (trans_id,))
    row = c.fetchone()
    if not row:
        if request.is_xhr:
            return jsonify({"error": "Transaction not found"}), 404
        flash("Transaction not found", "danger")
        return redirect(url_for('case.dashboard'))

    case_id = row['case_id']

    try:
        c.execute("DELETE FROM money WHERE id = %s", (trans_id,))
        db.commit()
        flash('Transaction deleted', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error deleting transaction: {str(e)}', 'danger')

    if request.is_xhr or request.headers.get('Accept') == 'application/json':
        return jsonify({"success": True, "case_id": case_id})

    return redirect(url_for('case.dashboard', case_id=case_id))


# ────────────────────────────────────────────────
# EDIT / DELETE NOTE
# ────────────────────────────────────────────────

@case_bp.route('/edit_note', methods=['POST'])
@login_required
def edit_note():
    db = get_db()
    c = db.cursor()

    try:
        c.execute('''
            UPDATE notes
            SET type = %s, note = %s
            WHERE id = %s
        ''', (
            request.form['type'],
            request.form['note'],
            request.form['note_id']
        ))
        db.commit()
        flash('Note updated', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error updating note: {str(e)}', 'danger')

    case_id = request.form.get('case_id')
    if case_id:
        return redirect(url_for('case.dashboard', case_id=case_id))
    return redirect(url_for('case.dashboard'))


@case_bp.route('/delete_note/<int:note_id>', methods=['POST'])
@login_required
def delete_note(note_id):
    db = get_db()
    c = db.cursor()

    c.execute("SELECT case_id FROM notes WHERE id = %s", (note_id,))
    row = c.fetchone()
    if not row:
        if request.is_xhr:
            return jsonify({"error": "Note not found"}), 404
        flash("Note not found", "danger")
        return redirect(url_for('case.dashboard'))

    case_id = row['case_id']

    try:
        c.execute("DELETE FROM notes WHERE id = %s", (note_id,))
        db.commit()
        flash('Note deleted', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error deleting note: {str(e)}', 'danger')

    if request.is_xhr or request.headers.get('Accept') == 'application/json':
        return jsonify({"success": True, "case_id": case_id})

    return redirect(url_for('case.dashboard', case_id=case_id))


# ────────────────────────────────────────────────
# RENAME DEBTOR / CLIENT
# ────────────────────────────────────────────────

@case_bp.route('/rename_debtor', methods=['POST'])
@login_required
def rename_debtor():
    db = get_db()
    c = db.cursor()
    case_id = request.form.get('target_id')
    new_name = request.form.get('new_name', '').strip()

    if case_id and new_name:
        try:
            c.execute("UPDATE cases SET debtor_business_name = %s WHERE id = %s", (new_name, case_id))
            db.commit()
            flash('Debtor name updated', 'success')
        except Exception as e:
            db.rollback()
            flash(f'Error updating debtor name: {str(e)}', 'danger')
    else:
        flash('Invalid request', 'danger')

    return redirect(url_for('case.dashboard', case_id=case_id))


# ────────────────────────────────────────────────
# CUSTOM FIELDS UPDATE
# ────────────────────────────────────────────────

@case_bp.route('/update_custom_fields', methods=['POST'])
@login_required
def update_custom_fields():
    db = get_db()
    c = db.cursor()
    case_id = request.form.get('case_id')

    if not case_id:
        flash('No case selected', 'danger')
        return redirect(url_for('case.dashboard'))

    try:
        for key, value in request.form.items():
            if key.startswith('custom_field_'):
                field_id = key.replace('custom_field_', '')
                # Delete old value
                c.execute("DELETE FROM case_custom_values WHERE case_id = %s AND field_id = %s", (case_id, field_id))
                # Insert new if not empty
                if value and value.strip():
                    c.execute("""
                        INSERT INTO case_custom_values (case_id, field_id, field_value)
                        VALUES (%s, %s, %s)
                    """, (case_id, field_id, value.strip()))

        db.commit()
        flash('Custom fields updated', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error updating custom fields: {str(e)}', 'danger')

    return redirect(url_for('case.dashboard', case_id=case_id))


# ────────────────────────────────────────────────
# MAIN DASHBOARD
# ────────────────────────────────────────────────

@case_bp.route('/')
@case_bp.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    c = db.cursor()

    # All clients (for add case dropdown)
    c.execute("SELECT id, business_name FROM clients ORDER BY business_name")
    clients = c.fetchall()

    # Recent cases
    c.execute("""
        SELECT 
            c.id as client_id, c.business_name,
            s.id as case_id,
            COALESCE(s.debtor_business_name, s.debtor_first || ' ' || s.debtor_last) as debtor,
            s.open_date
        FROM cases s
        JOIN clients c ON s.client_id = c.id
        ORDER BY s.open_date DESC, s.id DESC
        LIMIT 10
    """)
    recent_cases = c.fetchall()

    selected_case = None
    case_client = None
    client_cases = []
    notes = []
    transactions = []
    custom_fields = []
    balance = 0.0
    totals = {'Invoice': 0.0, 'Payment': 0.0, 'Charge': 0.0, 'Interest': 0.0}
    today_str = date.today().isoformat()

    case_id = request.args.get('case_id')
    if case_id:
        try:
            case_id = int(case_id)
            c.execute("SELECT * FROM cases WHERE id = %s", (case_id,))
            selected_case = c.fetchone()

            if selected_case:
                # Client info
                c.execute("SELECT * FROM clients WHERE id = %s", (selected_case['client_id'],))
                case_client = c.fetchone()

                # Custom fields
                c.execute("""
                    SELECT 
                        fd.id as field_id, 
                        fd.field_name, 
                        fd.field_type,
                        cv.field_value
                    FROM client_custom_field_link link
                    JOIN custom_field_definitions fd ON link.field_id = fd.id
                    LEFT JOIN case_custom_values cv 
                        ON cv.field_id = fd.id AND cv.case_id = %s
                    WHERE link.client_id = %s
                    ORDER BY fd.field_name
                """, (case_id, selected_case['client_id']))
                custom_fields = c.fetchall()

                # Other cases for this client + their balances
                c.execute("""
                    SELECT id, debtor_business_name, debtor_first, debtor_last 
                    FROM cases 
                    WHERE client_id = %s 
                    ORDER BY id
                """, (selected_case['client_id'],))
                client_cases_raw = c.fetchall()

                for case_row in client_cases_raw:
                    case_dict = dict(case_row)
                    c.execute("""
                        SELECT type, amount, recoverable 
                        FROM money 
                        WHERE case_id = %s
                    """, (case_row['id'],))
                    money_rows = c.fetchall()

                    case_balance = 0.0
                    for m in money_rows:
                        amt = float(m['amount'])
                        if m['type'] == 'Payment':
                            case_balance -= amt
                        elif m['type'] in ['Invoice', 'Interest']:
                            case_balance += amt
                        elif m['type'] == 'Charge' and m['recoverable']:
                            case_balance += amt

                    case_dict['balance'] = round(case_balance, 2)
                    client_cases.append(case_dict)

                # Notes
                c.execute("""
                    SELECT n.*, u.username 
                    FROM notes n 
                    JOIN users u ON n.created_by = u.id 
                    WHERE n.case_id = %s 
                    ORDER BY n.created_at DESC
                    LIMIT 50
                """, (case_id,))
                notes = c.fetchall()

                # Transactions
                c.execute("""
                    SELECT m.*, u.username 
                    FROM money m 
                    JOIN users u ON m.created_by = u.id 
                    WHERE m.case_id = %s 
                    ORDER BY m.transaction_date ASC, m.id ASC
                """, (case_id,))
                transactions = c.fetchall()

                # Calculate balance & totals
                for t in transactions:
                    amt = float(t['amount'])
                    typ = t['type']
                    totals[typ] += amt

                    if typ == 'Payment':
                        balance -= amt
                    elif typ in ['Invoice', 'Interest']:
                        balance += amt
                    elif typ == 'Charge' and t['recoverable']:
                        balance += amt

        except Exception as e:
            flash(f"Error loading case: {str(e)}", "danger")

    return render_template(
        'dashboard.html',
        clients=clients,
        recent_cases=recent_cases,
        selected_case=selected_case,
        case_client=case_client,
        client_cases=client_cases,
        notes=notes,
        transactions=transactions,
        custom_fields=custom_fields,
        balance=round(balance, 2),
        totals={k: round(v, 2) for k, v in totals.items()},
        today_str=today_str
    )
