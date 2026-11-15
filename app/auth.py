from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app.models import User

auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.redirect_dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password) and user.is_active_account:
            login_user(user)
            return redirect(url_for('auth.redirect_dashboard'))
        else:
            flash('Email atau password salah')

    return render_template('login.html')


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth.route('/redirect-dashboard')
@login_required
def redirect_dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif current_user.role == 'kasir':
        return redirect(url_for('kasir.dashboard'))
    elif current_user.role == 'pajak':
        return redirect(url_for('pajak.dashboard'))
    return redirect(url_for('main.menu'))