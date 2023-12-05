from flask import Blueprint
from flask_login import login_required

bp = Blueprint('dashboard', __name__)


@bp.route('/', methods=['GET'])
@login_required
def index():
    return 'Hello user'
