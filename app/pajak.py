from flask import Blueprint, render_template
from flask_login import login_required

pajak = Blueprint('pajak', __name__, url_prefix='/pajak')

@pajak.route('/dashboard')
@login_required
def dashboard():
    return "<h1>Dashboard Petugas Pajak</h1>"