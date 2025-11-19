# =============================================================================
#  MAIN APP ENTRY POINT - app.py
#  This file is now TINY and CLEAN. It only creates the app and registers blueprints
# =============================================================================

from flask import Flask
from extensions import get_db, close_db, money, format_date
from routes.auth import auth_bp
from routes.client import client_bp
from routes.case import case_bp
from routes.reports import reports_bp
from routes.admin import admin_bp


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

    return app


# This is what Gunicorn needs — the app object at module level
app = create_app()


if __name__ == '__main__':
    app.run(debug=True)
