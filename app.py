# =============================================================================
#  MAIN APP ENTRY POINT - app.py
#  This file is now TINY and CLEAN. It only creates the app and registers blueprints
# =============================================================================

from flask import Flask, request
import traceback
from extensions import get_db, close_db, money, format_date
from routes.auth import auth_bp
from routes.client import client_bp
from routes.case import case_bp
from routes.reports import reports_bp
from routes.admin import admin_bp




def _show_exception_on_screen(error):
    tb = traceback.format_exc()
    if tb.strip() == 'NoneType: None':
        tb = ''.join(traceback.format_exception(type(error), error, error.__traceback__))

    html = f"""
    <html>
      <head><title>Harbour Error</title></head>
      <body style="font-family: Arial; background:#fff6f6; color:#333; padding:20px;">
        <h2 style="color:#b00020; margin-top:0;">Application Error</h2>
        <p><strong>Path:</strong> {request.method} {request.path}</p>
        <p><strong>Error:</strong> {type(error).__name__}: {error}</p>
        <h3>Traceback</h3>
        <pre style="white-space:pre-wrap; background:#fff; border:1px solid #f0c0c0; padding:12px; border-radius:6px;">{tb}</pre>
      </body>
    </html>
    """
    return html, 500

def create_app():
    app = Flask(__name__)
    app.secret_key = 'supersecretkey'  # TODO: move to env var

    app.teardown_appcontext(close_db)

    app.register_blueprint(auth_bp)
    app.register_blueprint(client_bp)
    app.register_blueprint(case_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp)

    app.jinja_env.filters['money'] = money
    app.jinja_env.filters['format_date'] = format_date

    # Always show full crash details on screen for debugging in this environment.
    app.register_error_handler(Exception, _show_exception_on_screen)

    return app


# This is what Gunicorn needs — the app object at module level
app = create_app()


if __name__ == '__main__':
    app.run(debug=True)
