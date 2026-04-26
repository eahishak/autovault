import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional
from app.models import User


def _strong_password(form, field):
    pw = field.data
    if not re.search(r'[A-Z]', pw):
        raise ValidationError('Password must include at least one uppercase letter.')
    if not re.search(r'[0-9]', pw):
        raise ValidationError('Password must include at least one number.')


class RegistrationForm(FlaskForm):
    name = StringField('Full name', validators=[DataRequired(), Length(2, 120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=254)])
    role = SelectField('I want to', choices=[('buyer', 'Buy a car'), ('seller', 'Sell a car')])
    location = StringField('City, State', validators=[Optional(), Length(max=120)])
    password = PasswordField('Password', validators=[
        DataRequired(), Length(8, 128), _strong_password
    ])
    confirm = PasswordField('Confirm password', validators=[
        DataRequired(), EqualTo('password', message='Passwords must match.')
    ])
    agree = BooleanField('I agree to the terms', validators=[DataRequired()])

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError('That email is already registered.')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Keep me signed in')


class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])


class ResetPasswordForm(FlaskForm):
    password = PasswordField('New password', validators=[
        DataRequired(), Length(8, 128), _strong_password
    ])
    confirm = PasswordField('Confirm password', validators=[
        DataRequired(), EqualTo('password')
    ])


class EditProfileForm(FlaskForm):
    name = StringField('Full name', validators=[DataRequired(), Length(2, 120)])
    location = StringField('City, State', validators=[Optional(), Length(max=120)])
    phone = StringField('Phone', validators=[Optional(), Length(max=30)])
    bio = TextAreaField('About me', validators=[Optional(), Length(max=1000)])
    avatar_url = StringField('Profile photo URL', validators=[Optional(), Length(max=500)])

    def validate_avatar_url(self, field):
        if field.data and not field.data.startswith(('http://', 'https://')):
            raise ValidationError('Must be a valid URL.')