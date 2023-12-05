from flask import Blueprint, render_template, request
from werkzeug.security import generate_password_hash, check_password_hash
from userport.db import get_user_by_email, create_user, get_current_time, get_user_by_id
from userport.models import UserModel
from flask_login import LoginManager, login_user

bp = Blueprint('auth', __name__, url_prefix='/auth')
login_manager = LoginManager()


@bp.route('/register', methods=['GET', 'POST'])
def register():
    template_path = 'auth/register.html'
    if request.method == 'GET':
        return render_template(template_path)

    first_name = request.form['first-name']
    last_name = request.form['last-name']
    organization = request.form['organization']
    email = request.form['email']
    password = request.form['password']

    error = None
    if not first_name:
        error = 'First name cannot be empty'
    elif not last_name:
        error = 'Last name cannot be empty'
    elif not organization:
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

    current_time = get_current_time()
    new_user = UserModel(first_name=first_name, last_name=last_name, organization=organization, email=email,
                         password=generate_password_hash(password), created=current_time, last_updated=current_time)
    create_user(new_user)

    return render_template('auth/login.html', message='Registration Successful! Please login.')


@login_manager.user_loader
def load_user(user_id: str):
    return get_user_by_id(user_id)


@bp.route('/login', methods=['GET', 'POST'])
def login():
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
    return render_template(template_path, message='Login Successful!')
