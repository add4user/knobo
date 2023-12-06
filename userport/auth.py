from flask import Blueprint, render_template, request, flash, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from userport.db import get_user_by_email, get_org_by_domain, get_user_by_id, create_user_and_organization_transactionally
from userport.models import UserModel, OrganizationModel
from userport.utils import get_domain_from_email
from flask_login import LoginManager, login_user, logout_user, current_user, AnonymousUserMixin

bp = Blueprint('auth', __name__, url_prefix='/auth')
login_manager = LoginManager()

# We want strong session protection so that if the user's identifier does not match,
# the session is deleted immediately per
# https://flask-login.readthedocs.io/en/latest/#session-protection.
login_manager.session_protection = 'strong'


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if not isinstance(current_user, AnonymousUserMixin):
        # User is logged in already.
        return redirect(url_for('index'))

    template_path = 'auth/register.html'
    if request.method == 'GET':
        return render_template(template_path)

    first_name = request.form['first-name']
    last_name = request.form['last-name']
    organization_name = request.form['organization']
    email = request.form['email']
    password = request.form['password']

    error = None
    if not first_name:
        error = 'First name cannot be empty'
    elif not last_name:
        error = 'Last name cannot be empty'
    elif not organization_name:
        error = 'Organization cannot be empty'
    elif not email:
        error = 'Email Id cannot be empty'
    elif not password:
        error = 'Password cannot be empty'

    if error:
        return render_template(template_path, error=error)

    existing_user = get_user_by_email(email)
    if existing_user:
        error = f'User with email {email} already exists'
        return render_template(template_path, error=error)

    domain: str = get_domain_from_email(email)
    existing_domain = get_org_by_domain(domain)
    if existing_domain:
        # For now we allow only 1 user per domain to register.
        error = f'Domain already registered. Please contact admin.'
        return render_template(template_path, error=error)

    # Create new user and organization.
    new_user = UserModel(first_name=first_name, last_name=last_name,  email=email, org_domain=domain,
                         password=generate_password_hash(password))
    new_org = OrganizationModel(name=organization_name, domain=domain)
    create_user_and_organization_transactionally(
        user_model=new_user, organization_model=new_org)

    flash('Registration Successful! Please login.')
    return redirect(url_for('auth.login'))


@login_manager.user_loader
def load_user(user_id: str):
    return get_user_by_id(user_id)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if not isinstance(current_user, AnonymousUserMixin):
        # User is logged in already.
        return redirect(url_for('index'))

    template_path = 'auth/login.html'
    if request.method == 'GET':
        return render_template(template_path)

    email = request.form['email']
    password = request.form['password']

    error = None
    if not email:
        error = 'Email Id cannot be empty'
    elif not password:
        error = 'Password cannot be empty'

    if error:
        return render_template(template_path, error=error)

    user = get_user_by_email(email)
    if not user or not check_password_hash(pwhash=user.password, password=password):
        error = 'Email or Password is incorrect'

    if error:
        return render_template(template_path, error=error)

    login_user(user)
    return redirect(url_for('index'))


@bp.route('/logout', methods=['GET'])
def logout():
    logout_user()
    flash('Logged out successfully!')
    return redirect(url_for('auth.login'))


@login_manager.unauthorized_handler
def unauthorized():
    flash('Please login first', 'error')
    return redirect(url_for('auth.login'))
