"""
tests/conftest.py

Shared pytest fixtures for the AutoVault test suite.
Uses in-memory SQLite and disables CSRF.

Session pattern: we use a single scoped session per test function bound
to a savepoint so that rollback leaves the DB clean after every test.
"""

import uuid
import pytest
from app import create_app
from app.extensions import db as _db


# ─── App ──────────────────────────────────────────────────────────────────────

@pytest.fixture(scope='session')
def app():
    application = create_app('testing')
    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    return app.test_client()


# ─── DB isolation per test ────────────────────────────────────────────────────

@pytest.fixture(scope='function', autouse=True)
def db_session(app):
    """
    Each test gets a clean state via a nested transaction (SAVEPOINT).
    Works correctly with Flask-SQLAlchemy's scoped session.
    """
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()

        # Bind the scoped session to this connection
        _db.session.configure(bind=connection)

        # Start a savepoint so we can roll back without closing the transaction
        _db.session.begin_nested()

        yield _db.session

        _db.session.rollback()
        _db.session.remove()
        transaction.rollback()
        connection.close()

        # Rebind session to engine for next test
        _db.session.configure(bind=_db.engine)


# ─── User fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def buyer(app, db_session):
    from app.models import User
    email = f'buyer-{uuid.uuid4().hex[:8]}@test.com'
    u = User(name='Test Buyer', email=email, role='buyer', location='New York, NY')
    u.set_password('Buyer1234!')
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def seller(app, db_session):
    from app.models import User
    email = f'seller-{uuid.uuid4().hex[:8]}@test.com'
    u = User(name='Test Seller', email=email, role='seller',
             location='Los Angeles, CA', is_verified=True)
    u.set_password('Seller1234!')
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def admin_user(app, db_session):
    from app.models import User
    # Reuse the seeded admin to avoid duplicate email constraint
    existing = User.query.filter_by(role='admin').first()
    if existing:
        return existing
    email = f'admin-{uuid.uuid4().hex[:8]}@test.com'
    u = User(name='Test Admin', email=email, role='admin', is_verified=True)
    u.set_password('Admin1234!')
    db_session.add(u)
    db_session.flush()
    return u


# ─── Car fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def active_car(app, db_session, seller):
    from app.models import Car
    slug = f'2022-toyota-camry-{uuid.uuid4().hex[:6]}'
    car = Car(
        seller_id=seller.id,
        make='Toyota', model='Camry', year=2022,
        price=2_500_000, mileage=18000,
        condition='Used', body_type='Sedan',
        fuel_type='Gasoline', transmission='Automatic',
        city='Los Angeles', state='CA',
        status='active', slug=slug,
        primary_image_url='https://images.unsplash.com/photo-1621007947382-bb3c3994e3fb?w=800',
    )
    db_session.add(car)
    db_session.flush()
    return car


@pytest.fixture
def archived_car(app, db_session, seller):
    from app.models import Car
    from app.utils import utcnow
    from datetime import timedelta
    slug = f'2019-honda-civic-{uuid.uuid4().hex[:6]}'
    car = Car(
        seller_id=seller.id,
        make='Honda', model='Civic', year=2019,
        price=1_800_000, mileage=45000,
        condition='Used', body_type='Sedan',
        fuel_type='Gasoline', transmission='Automatic',
        city='San Diego', state='CA',
        status='archived', slug=slug,
        created_at=utcnow() - timedelta(days=45),
    )
    db_session.add(car)
    db_session.flush()
    return car


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def login(client, email, password):
    return client.post('/login',
                       data={'email': email, 'password': password},
                       follow_redirects=True)


def logout(client):
    return client.get('/logout', follow_redirects=True)


@pytest.fixture
def logged_in_buyer(client, buyer):
    login(client, buyer.email, 'Buyer1234!')
    yield client
    logout(client)


@pytest.fixture
def logged_in_seller(client, seller):
    login(client, seller.email, 'Seller1234!')
    yield client
    logout(client)


@pytest.fixture
def logged_in_admin(client, admin_user):
    login(client, admin_user.email, 'Admin1234!')
    yield client
    logout(client)