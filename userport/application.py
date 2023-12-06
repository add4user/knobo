from flask import Blueprint, render_template
from flask_login import login_required

bp = Blueprint('application', __name__)


@bp.route('/', methods=['GET'])
@login_required
def uploads_view():
    return render_template('application/uploads.html')
