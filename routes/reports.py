# =============================================================================
# REPORTS ROUTES – UPDATED FOR NEW report.html
# • Live client search by name/code
# • Uses client_id (backwards compatible with old client_code)
# • Full Excel + PDF export
# =============================================================================
from flask import Blueprint, request, send_file, make_response, render_template
from flask_login import login_required
from extensions import get_db
import pandas as pd
from io import BytesIO
from weasyprint import HTML

reports_bp = Blueprint('reports', __name__)


# ----------------------------------------------------------------------
# 1. The main report page – now with live client search
# ----------------------------------------------------------------------
@reports_bp.route('/report')
@login_required
def report_page():
    client_id = request.args.get('client_id')
    client_code = request.args.get('client_code', '').strip()  # backwards compat
    query = request.args.get('query', '')

    db = get_db()
    c = db.cursor()

    # Load ALL clients for the search dropdown
    c.execute("SELECT id, business_name, code FROM clients ORDER BY business_name")
    all_clients = c.fetchall()

    selected_client = None
    report_html = ""

    # Resolve client_id from either client_id or old client_code param
    if not client_id and client_code:
        c.execute("SELECT id FROM clients WHERE id = %s", (client_code,))
        row = c.fetchone()
        if row:
            client_id = str(row['id'])

    if client_id:
        c.execute("SELECT id, business_name, code FROM clients WHERE id = %s", (client_id,))
        client_row = c.fetchone()
        if client_row:
            selected_client = client_row
            client_name = f"{client_row['business_name']} (ID: {client_row['id']})"

            c.execute("""
                SELECT s.id as case_id,
                       COALESCE(s.debtor_business_name, s.debtor_first || ' ' || s.debtor_last) as debtor,
                       m.type, m.amount
                FROM cases s
                LEFT JOIN money m ON s.id = m.case_id
                WHERE s.client_id = %s
            """, (client_id,))
            rows = c.fetchall()

            cases = {}
            for r in rows:
                case_id = r['case_id']
                if case_id not in cases:
                    cases[case_id] = {
                        'debtor': r['debtor'],
                        'Invoice': 0.0, 'Payment': 0.0, 'Charge': 0.0, 'Interest': 0.0
                    }
                if r['type']:
                    cases[case_id][r['type']] += float(r['amount'] or 0)

            report_html = """
            <table border='1' style='width:100%; border-collapse:collapse; font-family:Arial; font-size:14px; margin-top:20px;'>
                <tr style='background:#ddd;'>
                    <th>Case ID</th><th>Debtor</th><th>Invoice</th><th>Payment</th><th>Charge</th><th>Interest</th><th>Balance</th>
                </tr>
            """
            for case_id, d in cases.items():
                balance = d['Invoice'] + d['Charge'] + d['Interest'] - d['Payment']
                report_html += f"""
                <tr>
                    <td>{case_id}</td><td>{d['debtor']}</td>
                    <td>£{d['Invoice']:.2f}</td><td>£{d['Payment']:.2f}</td>
                    <td>£{d['Charge']:.2f}</td><td>£{d['Interest']:.2f}</td>
                    <td style='font-weight:bold; color:{"red" if balance > 0 else "green"};'>£{balance:.2f}</td>
                </tr>
                """

            grand = {t: sum(c[t] for c in cases.values()) for t in ['Invoice','Payment','Charge','Interest']}
            grand_balance = grand['Invoice'] + grand['Charge'] + grand['Interest'] - grand['Payment']
            report_html += f"""
            <tr style='font-weight:bold; background:#eee;'>
                <td colspan='2'>TOTALS</td>
                <td>£{grand['Invoice']:.2f}</td><td>£{grand['Payment']:.2f}</td>
                <td>£{grand['Charge']:.2f}</td><td>£{grand['Interest']:.2f}</td>
                <td>£{grand_balance:.2f}</td>
            </tr></table>
            """

    return render_template(
        'report.html',
        clients_json=[{'id': str(row['id']), 'business_name': row['business_name'], 'code': row['code'] or ''} for row in all_clients],
        selected_client=selected_client,
        report_html=report_html,
        query=query
    )


# ----------------------------------------------------------------------
# 2. Excel export – now works with client_id OR client_code
# ----------------------------------------------------------------------
@reports_bp.route('/export_excel')
@login_required
def export_excel():
    client_id = request.args.get('client_id') or request.args.get('client_code')
    if not client_id:
        return "No client specified", 400

    db = get_db()
    c = db.cursor()
    c.execute("SELECT id, business_name FROM clients WHERE id = %s", (client_id,))
    client = c.fetchone()
    if not client:
        return "Client not found", 404

    c.execute("""
        SELECT s.id as case_id,
               COALESCE(s.debtor_business_name, s.debtor_first || ' ' || s.debtor_last) as debtor,
               m.type, m.amount
        FROM cases s
        LEFT JOIN money m ON s.id = m.case_id
        WHERE s.client_id = %s
    """, (client_id,))
    rows = c.fetchall()

    cases = {}
    for r in rows:
        case_id = r['case_id']
        if case_id not in cases:
            cases[case_id] = {'debtor': r['debtor'], 'Invoice': 0, 'Payment': 0, 'Charge': 0, 'Interest': 0}
        if r['type']:
            cases[case_id][r['type']] += r['amount']

    df = pd.DataFrame.from_dict(cases, orient='index')
    df = df.reset_index().rename(columns={'index': 'Case ID', 'debtor': 'Debtor'})
    df['Balance'] = df['Invoice'] + df['Charge'] + df['Interest'] - df['Payment']

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Client Report')
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"report_client_{client_id}.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# ----------------------------------------------------------------------
# 3. PDF export – same fix
# ----------------------------------------------------------------------
@reports_bp.route('/export_pdf')
@login_required
def export_pdf():
    client_id = request.args.get('client_id') or request.args.get('client_code')
    if not client_id:
        return "No client specified", 400

    db = get_db()
    c = db.cursor()
    c.execute("SELECT id, business_name FROM clients WHERE id = %s", (client_id,))
    client = c.fetchone()
    if not client:
        return "Client not found", 404

    c.execute("""
        SELECT s.id as case_id, s.debtor_business_name, s.debtor_first, s.debtor_last,
               m.type, m.amount
        FROM cases s
        LEFT JOIN money m ON s.id = m.case_id
        WHERE s.client_id = %s
    """, (client_id,))
    rows = c.fetchall()

    cases = {}
    for r in rows:
        case_id = r['case_id']
        if case_id not in cases:
            debtor = r['debtor_business_name'] or f"{r['debtor_first']} {r['debtor_last']}"
            cases[case_id] = {'debtor': debtor, 'Invoice': 0.0, 'Payment': 0.0, 'Charge': 0.0, 'Interest': 0.0}
        if r['type']:
            cases[case_id][r['type']] += float(r['amount'] or 0)

    html = f"<h1>Client Report: {client['business_name']} (ID: {client['id']})</h1>"
    html += "<table border='1' style='width:100%; border-collapse:collapse; font-family:Arial; font-size:12px;'><tr style='background:#ddd;'><th>Case ID</th><th>Debtor</th><th>Invoice</th><th>Payment</th><th>Charge</th><th>Interest</th><th>Balance</th></tr>"
    for case_id, d in cases.items():
        balance = d['Invoice'] + d['Charge'] + d['Interest'] - d['Payment']
        html += f"<tr><td>{case_id}</td><td>{d['debtor']}</td><td>£{d['Invoice']:.2f}</td><td>£{d['Payment']:.2f}</td><td>£{d['Charge']:.2f}</td><td>£{d['Interest']:.2f}</td><td>£{balance:.2f}</td></tr>"
    grand = {t: sum(c[t] for c in cases.values()) for t in ['Invoice','Payment','Charge','Interest']}
    grand_balance = grand['Invoice'] + grand['Charge'] + grand['Interest'] - grand['Payment']
    html += f"<tr style='font-weight:bold; background:#eee;'><td colspan='2'>TOTALS</td><td>£{grand['Invoice']:.2f}</td><td>£{grand['Payment']:.2f}</td><td>£{grand['Charge']:.2f}</td><td>£{grand['Interest']:.2f}</td><td>£{grand_balance:.2f}</td></tr></table>"

    pdf = HTML(string=html).write_pdf()
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=report_client_{client_id}.pdf'
    return response
