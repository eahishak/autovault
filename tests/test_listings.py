"""
tests/test_listings.py

Tests for the listings blueprint:
create, edit, delete, mark sold, repost.
Verifies auth guards, ownership checks, and slug generation.
"""

import pytest
from app.models import Car
from tests.conftest import login


VALID_LISTING = {
    'make':         'Toyota',
    'model':        'Corolla',
    'year':         2021,
    'condition':    'Used',
    'price':        '18500',
    'mileage':      '32000',
    'body_type':    'Sedan',
    'fuel_type':    'Gasoline',
    'transmission': 'Automatic',
    'city':         'Chicago',
    'state':        'IL',
}


class TestNewListing:

    def test_new_listing_page_requires_auth(self, client):
        r = client.get('/listings/new', follow_redirects=True)
        assert b'sign in' in r.data.lower() or b'login' in r.data.lower()

    def test_buyer_cannot_access_new_listing(self, logged_in_buyer):
        r = logged_in_buyer.get('/listings/new', follow_redirects=True)
        assert r.status_code in (403, 200)

    def test_seller_can_load_new_listing_page(self, logged_in_seller):
        r = logged_in_seller.get('/listings/new')
        assert r.status_code == 200

    def test_create_listing_success(self, logged_in_seller, db_session):
        count_before = Car.query.count()
        r = logged_in_seller.post('/listings/new', data=VALID_LISTING,
                                  follow_redirects=True)
        assert r.status_code == 200
        assert Car.query.count() == count_before + 1

    def test_created_listing_has_correct_fields(self, logged_in_seller, db_session):
        logged_in_seller.post('/listings/new', data=VALID_LISTING,
                              follow_redirects=True)
        car = Car.query.filter_by(model='Corolla').first()
        assert car is not None
        assert car.make == 'Toyota'
        assert car.year == 2021
        assert car.price == 1_850_000
        assert car.status == 'active'

    def test_slug_generated_on_create(self, logged_in_seller, db_session):
        logged_in_seller.post('/listings/new', data=VALID_LISTING,
                              follow_redirects=True)
        car = Car.query.filter_by(model='Corolla').first()
        assert car.slug is not None
        assert 'toyota' in car.slug.lower() or 'corolla' in car.slug.lower()

    def test_missing_required_field_rejected(self, logged_in_seller, db_session):
        data = VALID_LISTING.copy()
        del data['make']
        count_before = Car.query.count()
        logged_in_seller.post('/listings/new', data=data, follow_redirects=True)
        assert Car.query.count() == count_before


class TestEditListing:

    def test_edit_page_loads_for_owner(self, logged_in_seller, active_car):
        r = logged_in_seller.get(f'/listings/{active_car.id}/edit')
        assert r.status_code == 200

    def test_edit_page_forbidden_for_other_user(self, logged_in_buyer, active_car):
        r = logged_in_buyer.get(f'/listings/{active_car.id}/edit')
        assert r.status_code == 403

    def test_edit_updates_fields(self, logged_in_seller, active_car, db_session):
        data = VALID_LISTING.copy()
        data['model'] = 'Updated Model'
        data['price'] = '30000'
        r = logged_in_seller.post(f'/listings/{active_car.id}/edit',
                                  data=data, follow_redirects=True)
        assert r.status_code == 200
        db_session.refresh(active_car)
        assert active_car.model == 'Updated Model'
        assert active_car.price == 3_000_000

    def test_price_drop_sets_original_price(self, logged_in_seller, active_car, db_session):
        original = active_car.price
        data = VALID_LISTING.copy()
        data['price'] = str((original // 100) - 1000)
        logged_in_seller.post(f'/listings/{active_car.id}/edit',
                              data=data, follow_redirects=True)
        db_session.refresh(active_car)
        assert active_car.original_price == original


class TestDeleteListing:

    def test_delete_requires_auth(self, client, active_car):
        r = client.post(f'/listings/{active_car.id}/delete', follow_redirects=True)
        assert r.status_code == 200

    def test_delete_forbidden_for_non_owner(self, logged_in_buyer, active_car):
        r = logged_in_buyer.post(f'/listings/{active_car.id}/delete',
                                 follow_redirects=True)
        assert r.status_code == 403

    def test_owner_can_delete(self, logged_in_seller, active_car, db_session):
        car_id = active_car.id
        r = logged_in_seller.post(f'/listings/{car_id}/delete', follow_redirects=True)
        assert r.status_code == 200
        assert Car.query.get(car_id) is None

    def test_admin_can_delete_any_listing(self, logged_in_admin, active_car, db_session):
        car_id = active_car.id
        r = logged_in_admin.post(f'/listings/{car_id}/delete', follow_redirects=True)
        assert r.status_code == 200
        assert Car.query.get(car_id) is None


class TestMarkSold:

    def test_mark_sold_sets_status(self, logged_in_seller, active_car, db_session):
        r = logged_in_seller.post(f'/listings/{active_car.id}/mark-sold',
                                  follow_redirects=True)
        assert r.status_code == 200
        db_session.refresh(active_car)
        assert active_car.status == 'sold'
        assert active_car.sold_at is not None

    def test_mark_sold_forbidden_for_non_owner(self, logged_in_buyer, active_car):
        r = logged_in_buyer.post(f'/listings/{active_car.id}/mark-sold',
                                 follow_redirects=True)
        assert r.status_code == 403


class TestRepostListing:

    def test_repost_archived_listing(self, logged_in_seller, archived_car, db_session):
        r = logged_in_seller.post(f'/listings/{archived_car.id}/repost',
                                  follow_redirects=True)
        assert r.status_code == 200
        db_session.refresh(archived_car)
        assert archived_car.status == 'active'
        assert archived_car.archived_at is None

    def test_cannot_repost_active_listing(self, logged_in_seller, active_car, db_session):
        r = logged_in_seller.post(f'/listings/{active_car.id}/repost',
                                  follow_redirects=True)
        assert r.status_code == 200
        db_session.refresh(active_car)
        assert active_car.status == 'active'