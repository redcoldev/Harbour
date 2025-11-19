# =============================================================================
#  AUTH ROUTES - LOGIN / LOGOUT / USER MANAGEMENT
#  Everything to do with who is logged in
#  • Flask-Login setup
#  • Login page & validation
#  • Logout
#  • User class & user loader
# =============================================================================

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user, LoginManager, UserMixin
from extensions import get_db
import bcrypt

# Blueprint for all auth-related routes
auth_bp = Blueprint('auth', __name__)

# Flask-Login setup
login_manager = LoginManager()
login_manager.login_view = 'auth.login'  # redirect to this route if not logged in

# User class - represents a logged-in person
class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

# Tell Flask-Login how to load a user from the session
@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id, username, role FROM users WHERE id = %s", (user_id,))
    row = c.fetchone()
    if row:
        return User(row['id'], row['username'], row['role'])
    return None

# Attach login_manager to the app when the blueprint loads
@auth_bp.record_once
def on_load(state):
    login_manager.init_app(state.app)

# =============================================================================
#  ROUTES
# =============================================================================

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        c = db.cursor()
        c.execute("SELECT id, username, password_hash, role FROM users WHERE username = %s", (username,))
        user = c.fetchone()
        if user and bcrypt.checkpw(password.encode(), user['password_hash']):
            login_user(User(user['id'], user['username'], user['role']))
            return redirect(url_for('case.dashboard'))  # main page after login
        flash('Invalid username or password')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
