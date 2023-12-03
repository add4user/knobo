from flask import Blueprint, render_template
from werkzeug.security import generate_password_hash
from userport.db import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    return render_template('auth/register.html')
