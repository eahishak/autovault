import secrets
from datetime import timedelta
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message as MailMessage
from app.auth import auth
from app.auth.forms import (RegistrationForm, LoginForm, ForgotPasswordForm,
                             ResetPasswordForm, EditProfileForm)
from app.models import User
from app.extensions import db, mail
from app.utils import utcnow


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            name=form.name.data.strip(),
            email=form.email.data.lower().strip(),
            role=form.role.data,
            location=form.location.data.strip() if form.location.data else None,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=False)
        flash(f'Welcome to AutoVault, {user.name}!', 'success')
        return redirect(url_for('dashboard.buyer' if user.role == 'buyer' else 'dashboard.seller'))
    return render_template('auth/register.html', form=form)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            user.last_seen = utcnow()
            db.session.commit()
            nxt = request.args.get('next')
            # basic open-redirect guard
            if nxt and nxt.startswith('/') and not nxt.startswith('//'):
                return redirect(nxt)
            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            if user.is_seller:
                return redirect(url_for('dashboard.seller'))
            return redirect(url_for('dashboard.buyer'))
        flash('Invalid email or password.', 'danger')
    return render_template('auth/login.html', form=form)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('main.index'))


@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user:
            token = secrets.token_urlsafe(48)
            user.reset_token = token
            user.reset_token_expires = utcnow() + timedelta(hours=2)
            db.session.commit()
            _send_reset_email(user, token)
        # always show success to prevent user enumeration
        flash('If that email is registered, a reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/forgot_password.html', form=form)


@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_expires or user.reset_token_expires < utcnow():
        flash('That reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()
        flash('Password updated. You can now sign in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', form=form, token=token)


@auth.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    from flask import request as _req
    form = EditProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.name = form.name.data.strip()
        current_user.location = form.location.data.strip() if form.location.data else None
        current_user.phone = form.phone.data.strip() if form.phone.data else None
        current_user.bio = form.bio.data.strip() if form.bio.data else None

        # Handle avatar: base64 upload takes priority over URL
        avatar_data = _req.form.get('avatar_data', '').strip()
        avatar_url  = form.avatar_url.data.strip() if form.avatar_url.data else None

        if avatar_data == 'REMOVE':
            current_user.avatar_url = None
        elif avatar_data and avatar_data.startswith('data:image/'):
            # Store base64 directly as the avatar_url (data URI)
            current_user.avatar_url = avatar_data
        elif avatar_url:
            current_user.avatar_url = avatar_url
        # else: no change to avatar

        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('auth.edit_profile'))
    return render_template('auth/edit_profile.html', form=form)


def _send_reset_email(user, token):
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    try:
        msg = MailMessage(
            subject='Reset your AutoVault password',
            recipients=[user.email],
            html=render_template('auth/email/reset_password.html',
                                 user=user, reset_url=reset_url)
        )
        mail.send(msg)
    except Exception as e:
        current_app.logger.warning(f'Failed to send reset email: {e}')