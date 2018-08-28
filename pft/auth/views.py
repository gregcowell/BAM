"""Module that handles auth views."""
from flask import render_template, url_for, request, redirect, session, flash,\
    Blueprint
from flask_login import login_required, login_user, logout_user, current_user
from werkzeug.urls import url_parse
from datetime import datetime
from ..database import User, Group, MemberShip
from .forms import (
    LoginForm, RegistrationForm, ChangeEmailForm, ChangePasswordForm,
    PasswordResetForm, PasswordResetRequestForm, DeleteUserForm)
from ..database import db
from ..email import send_email


auth = Blueprint('auth', __name__)


@auth.before_app_request
def before_request():
    """Check user is confirmed before every request."""
    if current_user.is_authenticated:
        # current_user.ping()
        if not current_user.confirmed \
                and request.endpoint \
                and request.blueprint != 'auth' \
                and request.endpoint != 'static':
            return redirect(url_for('auth.unconfirmed'))


@auth.route('/unconfirmed')
def unconfirmed():
    """User is unconfirmed."""
    if current_user.is_anonymous or current_user.confirmed:
        return redirect(url_for('web.home_page'))
    return render_template('auth/unconfirmed.html')


@auth.route('/confirm')
@login_required
def resend_confirmation():
    """Resend account confirmation."""
    token = current_user.generate_confirmation_token()
    send_email(current_user.email, 'Confirm Your Account',
               'auth/mail/confirm', user=current_user, token=token)
    flash('A new confirmation email has been sent to you by email.')
    return redirect(url_for('web.home_page'))


@auth.route('/login', methods=['GET', 'POST'])
def login():
    """Login and return home page."""
    if current_user.is_authenticated:
        return redirect(url_for('web.home_page'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('web.home_page')
            return redirect(next_page)
        flash('Invalid email or password.')
    session['login_time'] = datetime.utcnow()
    return render_template('auth/login.html', form=form)


@auth.route('/logout')
def logout():
    """Log out and return login form."""
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('auth.login'))


@auth.route('/register', methods=['GET', 'POST'])
def register():
    """User registration form."""
    if current_user.is_authenticated:
        return redirect(url_for('web.home_page'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data, password=form.password.data)
        group = Group(name='Group:' + form.email.data)
        group.add_categories_accounts()
        membership = MemberShip(user=user, group=group, active=True)
        db.session.add(user)
        db.session.add(group)
        db.session.add(membership)
        db.session.commit()
        token = user.generate_confirmation_token()
        send_email(
            user.email, 'Confirm Your Account', 'auth/mail/confirm',
            user=user, token=token)
        flash('A confirmation email has been sent to you by email.')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form)


@auth.route('/confirm/<token>')
@login_required
def confirm(token):
    """Confirm account."""
    if current_user.confirmed:
        return redirect(url_for('web.home_page'))
    if current_user.confirm(token):
        db.session.commit()
        flash('You have confirmed your account. Thanks!')
    else:
        flash('The confirmation link is invalid or has expired.')
    return redirect(url_for('web.home_page'))


@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password."""
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.old_password.data):
            current_user.password = form.password.data
            db.session.add(current_user)
            db.session.commit()
            flash('Your password has been updated.')
            return redirect(url_for('web.home_page'))
        else:
            flash('Invalid password.')
    return render_template("auth/change_password.html", form=form)


@auth.route('/reset', methods=['GET', 'POST'])
def password_reset_request():
    """Password reset request."""
    if not current_user.is_anonymous:
        return redirect(url_for('web.home_page'))
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = user.generate_reset_token()
            send_email(user.email, 'Reset Your Password',
                       'auth/mail/reset_password',
                       user=user, token=token,
                       next=request.args.get('next'))
        flash('An email with instructions to reset your password has been '
              'sent to you.')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', form=form)


@auth.route('/reset/<token>', methods=['GET', 'POST'])
def password_reset(token):
    """Password reset."""
    if not current_user.is_anonymous:
        return redirect(url_for('web.home_page'))
    form = PasswordResetForm()
    if form.validate_on_submit():
        if User.reset_password(token, form.password.data):
            db.session.commit()
            flash('Your password has been updated.')
            return redirect(url_for('auth.login'))
        else:
            return redirect(url_for('web.home_page'))
    return render_template('auth/reset_password.html', form=form)


@auth.route('/change_email', methods=['GET', 'POST'])
@login_required
def change_email_request():
    """Change email request."""
    form = ChangeEmailForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.password.data):
            new_email = form.email.data
            token = current_user.generate_email_change_token(new_email)
            send_email(new_email, 'Confirm your email address',
                       'auth/mail/change_email',
                       user=current_user, token=token)
            flash('An email with instructions to confirm your new email '
                  'address has been sent to you.')
            return redirect(url_for('web.home_page'))
        else:
            flash('Invalid email or password.')
    return render_template("auth/change_email.html", form=form)


@auth.route('/change_email/<token>')
@login_required
def change_email(token):
    """Change email."""
    if current_user.change_email(token):
        db.session.commit()
        flash('Your email address has been updated.')
    else:
        flash('Invalid request.')
    return redirect(url_for('web.home_page'))


@auth.route('/delete_user', methods=['GET', 'POST'])
@login_required
def delete_user():
    """Delete user and data."""
    form = DeleteUserForm()
    if form.validate_on_submit():
        if form.yes.data:
            db.session.delete(current_user)
            db.session.commit()
        elif form.no.data:
            pass
        return redirect(url_for('web.home_page'))
    return render_template('auth/delete_user.html', form=form, menu="home")
