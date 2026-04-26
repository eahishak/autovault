from datetime import datetime, timezone
from flask_login import UserMixin
from sqlalchemy import event
from app.extensions import db, bcrypt, login_manager


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─── User ────────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='buyer')  # buyer | seller | admin
    location = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    bio = db.Column(db.Text)
    avatar_url = db.Column(db.String(500))
    is_verified = db.Column(db.Boolean, default=False)
    reset_token = db.Column(db.String(100), unique=True)
    reset_token_expires = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow)
    last_seen = db.Column(db.DateTime, default=utcnow)

    listings = db.relationship('Car', back_populates='seller',
                               foreign_keys='Car.seller_id', lazy='dynamic',
                               cascade='all, delete-orphan')
    sent_messages = db.relationship('Message', back_populates='sender',
                                    foreign_keys='Message.sender_id', lazy='dynamic')
    received_messages = db.relationship('Message', back_populates='receiver',
                                        foreign_keys='Message.receiver_id', lazy='dynamic')
    favorites = db.relationship('Favorite', back_populates='user',
                                lazy='dynamic', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', back_populates='user',
                                    lazy='dynamic', cascade='all, delete-orphan')
    reviews_given = db.relationship('Review', back_populates='reviewer',
                                    foreign_keys='Review.reviewer_id', lazy='dynamic')
    reviews_received = db.relationship('Review', back_populates='reviewee',
                                       foreign_keys='Review.reviewee_id', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    @property
    def is_seller(self):
        return self.role in ('seller', 'admin')

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def avg_rating(self):
        reviews = self.reviews_received.all()
        if not reviews:
            return None
        return round(sum(r.rating for r in reviews) / len(reviews), 1)

    @property
    def unread_message_count(self):
        return self.received_messages.filter_by(is_read=False).count()

    @property
    def unread_notification_count(self):
        return self.notifications.filter_by(is_read=False).count()

    def __repr__(self):
        return f'<User {self.email}>'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ─── Car ─────────────────────────────────────────────────────────────────────

class Car(db.Model):
    __tablename__ = 'cars'

    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Core identifiers
    make = db.Column(db.String(60), nullable=False, index=True)
    model = db.Column(db.String(60), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    trim = db.Column(db.String(60))
    vin = db.Column(db.String(17), unique=True)

    # Pricing
    price = db.Column(db.Integer, nullable=False, index=True)  # stored in cents
    original_price = db.Column(db.Integer)  # for Price Drop badge

    # Specs
    mileage = db.Column(db.Integer, nullable=False, index=True)
    condition = db.Column(db.String(20), nullable=False)   # new | used | certified
    body_type = db.Column(db.String(30), nullable=False, index=True)
    fuel_type = db.Column(db.String(30), nullable=False, index=True)
    transmission = db.Column(db.String(20), nullable=False)   # automatic | manual | cvt
    drivetrain = db.Column(db.String(10))  # fwd | rwd | awd | 4wd
    engine = db.Column(db.String(60))
    horsepower = db.Column(db.Integer)
    exterior_color = db.Column(db.String(40))
    interior_color = db.Column(db.String(40))
    doors = db.Column(db.Integer)
    seats = db.Column(db.Integer)

    # Location
    city = db.Column(db.String(80), index=True)
    state = db.Column(db.String(40))
    zip_code = db.Column(db.String(10))

    # Content
    description = db.Column(db.Text)
    features = db.Column(db.Text)  # JSON array of feature strings
    primary_image_url = db.Column(db.String(500))
    slug = db.Column(db.String(200), unique=True, index=True)

    # Status
    status = db.Column(db.String(20), nullable=False, default='active', index=True)
    # active | archived | sold | draft
    is_featured = db.Column(db.Boolean, default=False)
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)
    archived_at = db.Column(db.DateTime)
    sold_at = db.Column(db.DateTime)

    seller = db.relationship('User', back_populates='listings', foreign_keys=[seller_id])
    images = db.relationship('CarImage', back_populates='car',
                             cascade='all, delete-orphan', lazy='dynamic')
    messages = db.relationship('Message', back_populates='car',
                               cascade='all, delete-orphan', lazy='dynamic')
    favorites = db.relationship('Favorite', back_populates='car',
                                cascade='all, delete-orphan', lazy='dynamic')

    @property
    def price_dollars(self):
        return self.price / 100

    @property
    def days_listed(self):
        base = self.archived_at or utcnow()
        return (base - self.created_at).days

    @property
    def has_price_drop(self):
        return bool(self.original_price and self.original_price > self.price)

    @property
    def is_new_arrival(self):
        return self.days_listed <= 3

    @property
    def is_low_mileage(self):
        age = datetime.now().year - self.year
        # rough heuristic: under 10k/year
        return self.mileage < (age * 10_000) if age > 0 else self.mileage < 5_000

    @property
    def favorite_count(self):
        return self.favorites.count()

    def __repr__(self):
        return f'<Car {self.year} {self.make} {self.model}>'


# ─── CarImage ─────────────────────────────────────────────────────────────────

class CarImage(db.Model):
    __tablename__ = 'car_images'

    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('cars.id'), nullable=False, index=True)
    url = db.Column(db.String(500), nullable=False)
    caption = db.Column(db.String(200))
    display_order = db.Column(db.Integer, default=0)

    car = db.relationship('Car', back_populates='images')


# ─── Message ─────────────────────────────────────────────────────────────────

class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    car_id = db.Column(db.Integer, db.ForeignKey('cars.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)

    sender = db.relationship('User', back_populates='sent_messages', foreign_keys=[sender_id])
    receiver = db.relationship('User', back_populates='received_messages', foreign_keys=[receiver_id])
    car = db.relationship('Car', back_populates='messages')

    def __repr__(self):
        return f'<Message {self.sender_id}->{self.receiver_id} car={self.car_id}>'


# ─── Favorite ────────────────────────────────────────────────────────────────

class Favorite(db.Model):
    __tablename__ = 'favorites'
    __table_args__ = (db.UniqueConstraint('user_id', 'car_id', name='uq_user_car_fav'),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    car_id = db.Column(db.Integer, db.ForeignKey('cars.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    user = db.relationship('User', back_populates='favorites')
    car = db.relationship('Car', back_populates='favorites')


# ─── Review ──────────────────────────────────────────────────────────────────

class Review(db.Model):
    __tablename__ = 'reviews'
    __table_args__ = (db.UniqueConstraint('reviewer_id', 'reviewee_id', name='uq_review_pair'),)

    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)

    reviewer = db.relationship('User', back_populates='reviews_given', foreign_keys=[reviewer_id])
    reviewee = db.relationship('User', back_populates='reviews_received', foreign_keys=[reviewee_id])


# ─── Notification ─────────────────────────────────────────────────────────────

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    type = db.Column(db.String(40), nullable=False)  # new_message | listing_archived | car_favorited
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text)
    link = db.Column(db.String(300))
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    user = db.relationship('User', back_populates='notifications')