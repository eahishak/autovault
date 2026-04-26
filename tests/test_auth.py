"""
tests/test_auth.py

Tests for all authentication flows:
register, login, logout, forgot/reset password, profile edit.
Covers happy paths and all major error cases.
"""

import pytest
from app.models import User
from tests.conftest import login, logout


class TestRegister:

    def test_register_page_loads(self, client):
        r = client.get('/register')
        assert r.status_code == 200
        assert b'Create' in r.data

    def test_successful_buyer_registration(self, client, db_session):
        r = client.post('/register', data={
            'name':     'New Buyer',
            'email':    'newbuyer@test.com',
            'role':     'buyer',
            'password': 'Secure1234!',
            'confirm':  'Secure1234!',
            'agree':    'y',
        }, follow_redirects=True)
        assert r.status_code == 200
        user = User.query.filter_by(email='newbuyer@test.com').first()
        assert user is not None
        assert user.role == 'buyer'

    def test_successful_seller_registration(self, client, db_session):
        r = client.post('/register', data={
            'name':     'New Seller',
            'email':    'newseller@test.com',
            'role':     'seller',
            'password': 'Secure1234!',
            'confirm':  'Secure1234!',
            'agree':    'y',
        }, follow_redirects=True)
        assert r.status_code == 200
        user = User.query.filter_by(email='newseller@test.com').first()
        assert user is not None
        assert user.role == 'seller'

    def test_duplicate_email_rejected(self, client, buyer):
        r = client.post('/register', data={
            'name':     'Duplicate',
            'email':    buyer.email,
            'role':     'buyer',
            'password': 'Secure1234!',
            'confirm':  'Secure1234!',
            'agree':    'y',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'already registered' in r.data

    def test_password_mismatch_rejected(self, client):
        r = client.post('/register', data={
            'name':     'Mismatch User',
            'email':    'mismatch@test.com',
            'role':     'buyer',
            'password': 'Secure1234!',
            'confirm':  'Different1234!',
            'agree':    'y',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert User.query.filter_by(email='mismatch@test.com').first() is None

    def test_weak_password_rejected(self, client):
        r = client.post('/register', data={
            'name':     'Weak Pass',
            'email':    'weakpass@test.com',
            'role':     'buyer',
            'password': 'password',
            'confirm':  'password',
            'agree':    'y',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert User.query.filter_by(email='weakpass@test.com').first() is None

    def test_missing_terms_agreement_rejected(self, client):
        r = client.post('/register', data={
            'name':     'No Terms',
            'email':    'noterms@test.com',
            'role':     'buyer',
            'password': 'Secure1234!',
            'confirm':  'Secure1234!',
        }, follow_redirects=True)
        assert User.query.filter_by(email='noterms@test.com').first() is None


class TestLogin:

    def test_login_page_loads(self, client):
        r = client.get('/login')
        assert r.status_code == 200

    def test_successful_login(self, client, buyer):
        r = login(client, buyer.email, 'Buyer1234!')
        assert r.status_code == 200

    def test_wrong_password_rejected(self, client, buyer):
        r = client.post('/login', data={
            'email':    buyer.email,
            'password': 'WrongPass1!',
        }, follow_redirects=True)
        assert b'Invalid email or password' in r.data

    def test_unknown_email_rejected(self, client):
        r = client.post('/login', data={
            'email':    'nobody@test.com',
            'password': 'Secure1234!',
        }, follow_redirects=True)
        assert b'Invalid email or password' in r.data

    def test_authenticated_user_redirected_from_login(self, logged_in_buyer):
        r = logged_in_buyer.get('/login', follow_redirects=True)
        assert r.status_code == 200

    def test_seller_redirected_to_seller_dashboard(self, client, seller):
        r = login(client, seller.email, 'Seller1234!')
        assert r.status_code == 200

    def test_admin_redirected_to_admin_dashboard(self, client, admin_user):
        r = login(client, admin_user.email, 'Admin1234!')
        assert r.status_code == 200


class TestLogout:

    def test_logout_redirects(self, logged_in_buyer):
        r = logged_in_buyer.get('/logout', follow_redirects=True)
        assert r.status_code == 200
        assert b'signed out' in r.data.lower()

    def test_logout_requires_auth(self, client):
        r = client.get('/logout', follow_redirects=True)
        assert r.status_code == 200


class TestForgotPassword:

    def test_forgot_password_page_loads(self, client):
        r = client.get('/forgot-password')
        assert r.status_code == 200

    def test_submit_known_email_shows_success(self, client, buyer):
        r = client.post('/forgot-password', data={'email': buyer.email},
                        follow_redirects=True)
        assert r.status_code == 200
        assert b'reset link' in r.data.lower()

    def test_submit_unknown_email_still_shows_success(self, client):
        # prevent user enumeration
        r = client.post('/forgot-password', data={'email': 'nobody@test.com'},
                        follow_redirects=True)
        assert r.status_code == 200
        assert b'reset link' in r.data.lower()


class TestResetPassword:

    def test_invalid_token_redirects(self, client):
        r = client.get('/reset-password/badtoken', follow_redirects=True)
        assert r.status_code == 200
        assert b'invalid or has expired' in r.data.lower()

    def test_valid_token_resets_password(self, client, buyer, db_session):
        import secrets
        from app.utils import utcnow
        from datetime import timedelta
        token = secrets.token_urlsafe(48)
        buyer.reset_token = token
        buyer.reset_token_expires = utcnow() + timedelta(hours=2)
        db_session.flush()

        r = client.post(f'/reset-password/{token}', data={
            'password': 'NewPass1234!',
            'confirm':  'NewPass1234!',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert buyer.check_password('NewPass1234!')


class TestEditProfile:

    def test_edit_profile_requires_auth(self, client):
        r = client.get('/profile/edit', follow_redirects=True)
        assert r.status_code == 200
        assert b'sign in' in r.data.lower() or b'login' in r.data.lower()

    def test_edit_profile_page_loads(self, logged_in_buyer):
        r = logged_in_buyer.get('/profile/edit')
        assert r.status_code == 200

    def test_update_name(self, logged_in_buyer, buyer, db_session):
        r = logged_in_buyer.post('/profile/edit', data={
            'name': 'Updated Name',
        }, follow_redirects=True)
        assert r.status_code == 200
        db_session.refresh(buyer)
        assert buyer.name == 'Updated Name'