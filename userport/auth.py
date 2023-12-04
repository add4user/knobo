from flask import Blueprint, render_template, request
from werkzeug.security import generate_password_hash
from userport.db import get_user, create_user, get_current_time
from userport.models import UserModel

bp = Blueprint('auth', __name__, url_prefix='/auth')


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

    existing_user = get_user(email)
    if existing_user:
        error = f'User with email {email} already exists'
        return render_template(template_path, error=error)

    current_time = get_current_time()
    new_user = UserModel(first_name=first_name, last_name=last_name, organization=organization, email=email,
                         password=generate_password_hash(password), created=current_time, last_updated=current_time)
    create_user(new_user)

    return render_template(template_path)
