"""
tests/test_archive.py
"""

import pytest
from datetime import timedelta
from app.models import Car, Notification
from app.utils import archive_old_listings, utcnow


class TestAutoArchive:

    def test_archive_old_listings_archives_stale_cars(self, app, db_session, seller):
        old_car = Car(
            seller_id=seller.id,
            make='Old', model='Car', year=2018,
            price=1_000_000, mileage=80000,
            condition='Used', body_type='Sedan',
            fuel_type='Gasoline', transmission='Automatic',
            city='Boston', state='MA',
            status='active',
            slug=f'old-car-archive-{utcnow().timestamp()}',
            created_at=utcnow() - timedelta(days=45),
        )
        db_session.add(old_car)
        db_session.flush()

        archived_count = archive_old_listings()
        assert archived_count >= 1
        db_session.refresh(old_car)
        assert old_car.status == 'archived'
        assert old_car.archived_at is not None

    def test_archive_does_not_touch_fresh_listings(self, app, db_session, seller):
        # explicitly set created_at to right now so it is never stale
        fresh_car = Car(
            seller_id=seller.id,
            make='Fresh', model='Car', year=2024,
            price=3_000_000, mileage=100,
            condition='New', body_type='Sedan',
            fuel_type='Electric', transmission='Automatic',
            city='Austin', state='TX',
            status='active',
            slug=f'fresh-car-{utcnow().timestamp()}',
            created_at=utcnow(),          # explicitly NOW — never stale
        )
        db_session.add(fresh_car)
        db_session.flush()

        archive_old_listings()
        db_session.refresh(fresh_car)
        assert fresh_car.status == 'active'

    def test_archive_creates_notification_for_seller(self, app, db_session, seller):
        old_car = Car(
            seller_id=seller.id,
            make='Notify', model='Test', year=2019,
            price=1_200_000, mileage=60000,
            condition='Used', body_type='Sedan',
            fuel_type='Gasoline', transmission='Automatic',
            city='Miami', state='FL',
            status='active',
            slug=f'notify-archive-{utcnow().timestamp()}',
            created_at=utcnow() - timedelta(days=50),
        )
        db_session.add(old_car)
        db_session.flush()

        before = Notification.query.filter_by(
            user_id=seller.id, type='listing_archived').count()
        archive_old_listings()
        after = Notification.query.filter_by(
            user_id=seller.id, type='listing_archived').count()
        assert after > before

    def test_archive_threshold_respects_config(self, app, db_session, seller):
        # TestingConfig sets ARCHIVE_AFTER_DAYS=1
        borderline = Car(
            seller_id=seller.id,
            make='Border', model='Line', year=2021,
            price=2_000_000, mileage=10000,
            condition='Used', body_type='Sedan',
            fuel_type='Gasoline', transmission='Automatic',
            city='Austin', state='TX',
            status='active',
            slug=f'border-line-{utcnow().timestamp()}',
            created_at=utcnow() - timedelta(hours=25),
        )
        db_session.add(borderline)
        db_session.flush()

        archive_old_listings()
        db_session.refresh(borderline)
        assert borderline.status == 'archived'


class TestArchivePage:

    def test_archive_page_loads(self, client):
        r = client.get('/archive')
        assert r.status_code == 200

    def test_archive_page_shows_archived_cars(self, client, archived_car):
        r = client.get('/archive')
        assert r.status_code == 200

    def test_archive_page_pagination(self, client):
        r = client.get('/archive?page=1')
        assert r.status_code == 200


class TestRepostFromArchive:

    def test_repost_makes_listing_active(self, logged_in_seller, archived_car, db_session):
        r = logged_in_seller.post(f'/listings/{archived_car.id}/repost',
                                  follow_redirects=True)
        assert r.status_code == 200
        db_session.refresh(archived_car)
        assert archived_car.status == 'active'

    def test_repost_clears_archived_at(self, logged_in_seller, archived_car, db_session):
        logged_in_seller.post(f'/listings/{archived_car.id}/repost',
                              follow_redirects=True)
        db_session.refresh(archived_car)
        assert archived_car.archived_at is None

    def test_repost_resets_created_at(self, logged_in_seller, archived_car, db_session):
        original_created = archived_car.created_at
        logged_in_seller.post(f'/listings/{archived_car.id}/repost',
                              follow_redirects=True)
        db_session.refresh(archived_car)
        assert archived_car.created_at > original_created

    def test_buyer_cannot_repost_listing(self, logged_in_buyer, archived_car, db_session):
        r = logged_in_buyer.post(f'/listings/{archived_car.id}/repost',
                                 follow_redirects=True)
        assert r.status_code == 403
        db_session.refresh(archived_car)
        assert archived_car.status == 'archived'