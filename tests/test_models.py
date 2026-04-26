"""
tests/test_models.py

Unit tests for all SQLAlchemy models.
Covers relationships, computed properties, constraints, and repr methods.
"""

import pytest
from app.models import User, Car, Message, Favorite, Notification, Review, CarImage


class TestUserModel:

    def test_password_hashing(self, buyer):
        assert buyer.check_password('Buyer1234!') is True

    def test_wrong_password_rejected(self, buyer):
        assert buyer.check_password('wrongpassword') is False

    def test_password_hash_not_plaintext(self, buyer):
        assert buyer.password_hash != 'Buyer1234!'
        assert len(buyer.password_hash) > 20

    def test_is_seller_false_for_buyer(self, buyer):
        assert buyer.is_seller is False

    def test_is_seller_true_for_seller(self, seller):
        assert seller.is_seller is True

    def test_is_admin_false_for_seller(self, seller):
        assert seller.is_admin is False

    def test_is_admin_true_for_admin(self, admin_user):
        assert admin_user.is_admin is True

    def test_unread_message_count_default(self, buyer):
        assert buyer.unread_message_count == 0

    def test_unread_notification_count_default(self, buyer):
        assert buyer.unread_notification_count == 0

    def test_avg_rating_none_when_no_reviews(self, seller):
        assert seller.avg_rating is None

    def test_avg_rating_computed(self, db_session, buyer, seller):
        r1 = Review(reviewer_id=buyer.id, reviewee_id=seller.id, rating=4)
        db_session.add(r1)
        db_session.flush()
        assert seller.avg_rating == 4.0

    def test_repr_contains_email(self, buyer):
        # uuid-suffixed email — just check it contains @test.com
        assert '@test.com' in repr(buyer)


class TestCarModel:

    def test_price_dollars_property(self, active_car):
        assert active_car.price_dollars == 25000.0

    def test_days_listed_property(self, active_car):
        assert active_car.days_listed >= 0

    def test_is_new_arrival_fresh_listing(self, active_car):
        assert active_car.is_new_arrival is True

    def test_has_price_drop_false_by_default(self, active_car):
        # original_price is None → no price drop
        assert active_car.original_price is None
        assert active_car.has_price_drop is False

    def test_has_price_drop_true_when_price_reduced(self, active_car):
        active_car.original_price = active_car.price + 100_000
        assert active_car.has_price_drop is True

    def test_is_low_mileage_new_car(self, active_car):
        active_car.year = 2024
        active_car.mileage = 3000
        assert active_car.is_low_mileage is True

    def test_favorite_count_zero_by_default(self, active_car):
        assert active_car.favorite_count == 0

    def test_seller_relationship(self, active_car, seller):
        assert active_car.seller.id == seller.id

    def test_repr(self, active_car):
        assert 'Toyota' in repr(active_car)
        assert 'Camry' in repr(active_car)


class TestMessageModel:

    def test_create_message(self, db_session, buyer, seller, active_car):
        msg = Message(
            sender_id=buyer.id,
            receiver_id=seller.id,
            car_id=active_car.id,
            content='Is this still available?',
        )
        db_session.add(msg)
        db_session.flush()
        assert msg.id is not None
        assert msg.is_read is False

    def test_message_relationships(self, db_session, buyer, seller, active_car):
        msg = Message(
            sender_id=buyer.id,
            receiver_id=seller.id,
            car_id=active_car.id,
            content='Hello',
        )
        db_session.add(msg)
        db_session.flush()
        assert msg.sender.id == buyer.id
        assert msg.receiver.id == seller.id
        assert msg.car.id == active_car.id

    def test_repr(self, db_session, buyer, seller, active_car):
        msg = Message(sender_id=buyer.id, receiver_id=seller.id,
                      car_id=active_car.id, content='Hi')
        db_session.add(msg)
        db_session.flush()
        assert str(buyer.id) in repr(msg)


class TestFavoriteModel:

    def test_create_favorite(self, db_session, buyer, active_car):
        fav = Favorite(user_id=buyer.id, car_id=active_car.id)
        db_session.add(fav)
        db_session.flush()
        assert fav.id is not None

    def test_unique_constraint(self, db_session, buyer, active_car):
        fav1 = Favorite(user_id=buyer.id, car_id=active_car.id)
        fav2 = Favorite(user_id=buyer.id, car_id=active_car.id)
        db_session.add(fav1)
        db_session.flush()
        db_session.add(fav2)
        with pytest.raises(Exception):
            db_session.flush()

    def test_favorite_increments_count(self, db_session, buyer, active_car):
        fav = Favorite(user_id=buyer.id, car_id=active_car.id)
        db_session.add(fav)
        db_session.flush()
        assert active_car.favorite_count == 1


class TestNotificationModel:

    def test_create_notification(self, db_session, buyer):
        notif = Notification(
            user_id=buyer.id,
            type='new_message',
            title='You have a new message',
            body='Someone messaged you',
        )
        db_session.add(notif)
        db_session.flush()
        assert notif.id is not None
        assert notif.is_read is False

    def test_unread_count_increments(self, db_session, buyer):
        assert buyer.unread_notification_count == 0
        notif = Notification(user_id=buyer.id, type='new_message', title='Test')
        db_session.add(notif)
        db_session.flush()
        assert buyer.unread_notification_count == 1


class TestCarImageModel:

    def test_create_car_image(self, db_session, active_car):
        img = CarImage(car_id=active_car.id,
                       url='https://example.com/photo.jpg', display_order=0)
        db_session.add(img)
        db_session.flush()
        assert img.id is not None
        assert active_car.images.count() == 1