import logging
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from models import User, Server, Domain, DomainGroup, ServerLog, db
from modules.telegram_notifier import TelegramNotifier

bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@bp.route('/')
def index():
    """Redirect to dashboard if logged in, otherwise show login page."""
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    return redirect(url_for('auth.login'))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            flash('Invalid username or password', 'danger')
            return render_template('login.html')
        
        login_user(user, remember=remember)
        logger.info(f"User {username} logged in")
        
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('auth.dashboard'))
    
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/dashboard')
@login_required
def dashboard():
    """Show the dashboard with system overview."""
    # Get counts
    servers_count = Server.query.count()
    domains_count = Domain.query.count()
    domain_groups_count = DomainGroup.query.count()
    
    # Get servers for status display
    servers = Server.query.all()
    
    # Get domains with NS status
    domains = Domain.query.filter(Domain.expected_nameservers != None).filter(Domain.expected_nameservers != '').all()
    
    # Count domains by NS status
    ns_status_counts = {
        'ok': 0,
        'mismatch': 0,
        'pending': 0
    }
    
    for domain in domains:
        if domain.ns_status == 'ok':
            ns_status_counts['ok'] += 1
        elif domain.ns_status == 'mismatch':
            ns_status_counts['mismatch'] += 1
        else:
            ns_status_counts['pending'] += 1
    
    # Check if Telegram notifications are configured
    telegram_configured = TelegramNotifier.is_configured()
    
    return render_template('dashboard.html',
                         servers_count=servers_count,
                         domains_count=domains_count,
                         domain_groups_count=domain_groups_count,
                         servers=servers,
                         domains=domains,
                         ns_status_counts=ns_status_counts,
                         telegram_configured=telegram_configured)
