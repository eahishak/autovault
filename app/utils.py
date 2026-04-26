import json
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from flask import current_app
from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─── Archive Job ──────────────────────────────────────────────────────────────

def archive_old_listings():
    """Move listings older than ARCHIVE_AFTER_DAYS to archived status."""
    from app.models import Car, Notification
    threshold = utcnow() - timedelta(days=current_app.config['ARCHIVE_AFTER_DAYS'])
    stale = Car.query.filter(
        Car.status == 'active',
        Car.created_at <= threshold
    ).all()

    for car in stale:
        car.status = 'archived'
        car.archived_at = utcnow()
        notif = Notification(
            user_id=car.seller_id,
            type='listing_archived',
            title='Your listing was archived',
            body=f'Your {car.year} {car.make} {car.model} listing has been moved to the archive after {current_app.config["ARCHIVE_AFTER_DAYS"]} days.',
            link=f'/archive/{car.id}',
        )
        db.session.add(notif)

    if stale:
        db.session.commit()
    return len(stale)


# ─── Slug ─────────────────────────────────────────────────────────────────────

def slugify(text):
    text = unicodedata.normalize('NFKD', str(text))
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[\s_-]+', '-', text).strip('-')
    return text


def generate_car_slug(year, make, model, car_id):
    base = slugify(f'{year} {make} {model}')
    return f'{base}-{car_id}'


# ─── Formatting ──────────────────────────────────────────────────────────────

def format_price(cents):
    """Return '$24,500' from 2450000."""
    return f'${cents / 100:,.0f}'


def format_mileage(miles):
    return f'{miles:,} mi'


def days_since(dt):
    if dt is None:
        return 0
    return (utcnow() - dt).days


def time_ago(dt):
    if dt is None:
        return ''
    delta = utcnow() - dt
    if delta.days >= 365:
        y = delta.days // 365
        return f'{y}y ago'
    if delta.days >= 30:
        m = delta.days // 30
        return f'{m}mo ago'
    if delta.days >= 1:
        return f'{delta.days}d ago'
    hours = delta.seconds // 3600
    if hours >= 1:
        return f'{hours}h ago'
    minutes = delta.seconds // 60
    return f'{minutes}m ago' if minutes >= 1 else 'just now'


# ─── Seed JSON Parser ─────────────────────────────────────────────────────────

def load_seed_data(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def seed_database(app):
    """Parse seed_data.json and insert cars if DB is empty."""
    import os
    from app.models import Car, User, CarImage
    with app.app_context():
        if Car.query.count() > 0:
            return

        seed_path = os.path.join(os.path.dirname(app.root_path), 'seed_data.json')
        if not os.path.exists(seed_path):
            return

        data = load_seed_data(seed_path)

        # ensure a demo seller exists
        seller = User.query.filter_by(email='demo@autovault.com').first()
        if not seller:
            seller = User(
                name='AutoVault Demo',
                email='demo@autovault.com',
                role='seller',
                location='Los Angeles, CA',
                is_verified=True,
            )
            seller.set_password('Demo1234!')
            db.session.add(seller)
            db.session.flush()

        for entry in data.get('cars', []):
            price_cents = int(float(entry['price']) * 100)
            car = Car(
                seller_id=seller.id,
                make=entry['make'],
                model=entry['model'],
                year=int(entry['year']),
                trim=entry.get('trim'),
                price=price_cents,
                mileage=int(entry['mileage']),
                condition=entry.get('condition', 'used'),
                body_type=entry['body_type'],
                fuel_type=entry['fuel_type'],
                transmission=entry.get('transmission', 'automatic'),
                drivetrain=entry.get('drivetrain'),
                engine=entry.get('engine'),
                horsepower=entry.get('horsepower'),
                exterior_color=entry.get('exterior_color'),
                city=entry.get('city', 'Los Angeles'),
                state=entry.get('state', 'CA'),
                description=entry.get('description', ''),
                features=json.dumps(entry.get('features', [])),
                primary_image_url=entry.get('image_url'),
                status='active',
            )
            db.session.add(car)
            db.session.flush()
            car.slug = generate_car_slug(car.year, car.make, car.model, car.id)

            for url in entry.get('extra_images', []):
                db.session.add(CarImage(car_id=car.id, url=url))

        db.session.commit()


# ─── Monthly Payment Calculator ───────────────────────────────────────────────

def monthly_payment(price_cents, down_payment_cents, apr_percent, term_months):
    principal = (price_cents - down_payment_cents) / 100
    if principal <= 0:
        return 0.0
    monthly_rate = (apr_percent / 100) / 12
    if monthly_rate == 0:
        return round(principal / term_months, 2)
    payment = principal * (monthly_rate * (1 + monthly_rate) ** term_months) / \
              ((1 + monthly_rate) ** term_months - 1)
    return round(payment, 2)