"""
tests/test_admin.py

Tests for the admin blueprint.
Verifies all routes return 403 for non-admins
and correct behavior for admin users.
"""

import pytest
from app.models import Car, User


ADMIN_ROUTES = [
    '/admin/',
    '/admin/users',
    '/admin/listings',
    '/admin/stats',
]


class TestAdminAccess:

    def test_admin_routes_require_auth(self, client):
        for route in ADMIN_ROUTES:
            r = client.get(route, follow_redirects=True)
            assert r.status_code == 200
            assert (b'sign in' in r.data.lower() or
                    b'login' in r.data.lower() or
                    b'403' in r.data)

    def test_buyer_gets_403_on_admin(self, logged_in_buyer):
        r = logged_in_buyer.get('/admin/')
        assert r.status_code == 403

    def test_seller_gets_403_on_admin(self, logged_in_seller):
        r = logged_in_seller.get('/admin/')
        assert r.status_code == 403

    def test_admin_can_access_dashboard(self, logged_in_admin):
        r = logged_in_admin.get('/admin/')
        assert r.status_code == 200

    def test_admin_can_access_users_page(self, logged_in_admin):
        r = logged_in_admin.get('/admin/users')
        assert r.status_code == 200

    def test_admin_can_access_listings_page(self, logged_in_admin):
        r = logged_in_admin.get('/admin/listings')
        assert r.status_code == 200

    def test_admin_can_access_stats_page(self, logged_in_admin):
        r = logged_in_admin.get('/admin/stats')
        assert r.status_code == 200


class TestAdminDashboard:

    def test_dashboard_shows_stats(self, logged_in_admin, active_car, buyer):
        r = logged_in_admin.get('/admin/')
        assert r.status_code == 200
        assert b'Users' in r.data or b'users' in r.data
        assert b'Listings' in r.data or b'listings' in r.data


class TestAdminUserManagement:

    def test_users_page_lists_users(self, logged_in_admin, buyer, seller):
        r = logged_in_admin.get('/admin/users')
        assert r.status_code == 200
        assert buyer.name.encode() in r.data or buyer.email.encode() in r.data

    def test_filter_users_by_role(self, logged_in_admin, buyer, seller):
        r = logged_in_admin.get('/admin/users?role=buyer')
        assert r.status_code == 200

    def test_search_users_by_name(self, logged_in_admin, buyer):
        r = logged_in_admin.get(f'/admin/users?q={buyer.name[:5]}')
        assert r.status_code == 200

    def test_toggle_verified(self, logged_in_admin, buyer, db_session):
        was_verified = buyer.is_verified
        r = logged_in_admin.post(f'/admin/users/{buyer.id}/toggle-verified',
                                 follow_redirects=True)
        assert r.status_code == 200
        db_session.refresh(buyer)
        assert buyer.is_verified != was_verified

    def test_delete_user(self, logged_in_admin, db_session):
        user_to_delete = User(
            name='Deletable User',
            email='deleteme@test.com',
            role='buyer',
        )
        user_to_delete.set_password('Pass1234!')
        db_session.add(user_to_delete)
        db_session.flush()
        user_id = user_to_delete.id

        r = logged_in_admin.post(f'/admin/users/{user_id}/delete',
                                 follow_redirects=True)
        assert r.status_code == 200
        assert User.query.get(user_id) is None

    def test_admin_cannot_delete_own_account(self, logged_in_admin, admin_user):
        r = logged_in_admin.post(f'/admin/users/{admin_user.id}/delete',
                                 follow_redirects=True)
        assert r.status_code == 200
        assert User.query.get(admin_user.id) is not None


class TestAdminListingManagement:

    def test_listings_page_shows_cars(self, logged_in_admin, active_car):
        r = logged_in_admin.get('/admin/listings')
        assert r.status_code == 200

    def test_filter_listings_by_status(self, logged_in_admin, active_car, archived_car):
        r = logged_in_admin.get('/admin/listings?status=active')
        assert r.status_code == 200
        r2 = logged_in_admin.get('/admin/listings?status=archived')
        assert r2.status_code == 200

    def test_archive_listing(self, logged_in_admin, active_car, db_session):
        r = logged_in_admin.post(f'/admin/listings/{active_car.id}/archive',
                                 follow_redirects=True)
        assert r.status_code == 200
        db_session.refresh(active_car)
        assert active_car.status == 'archived'
        assert active_car.archived_at is not None

    def test_toggle_featured(self, logged_in_admin, active_car, db_session):
        was_featured = active_car.is_featured
        r = logged_in_admin.post(f'/admin/listings/{active_car.id}/feature',
                                 follow_redirects=True)
        assert r.status_code == 200
        db_session.refresh(active_car)
        assert active_car.is_featured != was_featured

    def test_delete_listing(self, logged_in_admin, active_car, db_session):
        car_id = active_car.id
        r = logged_in_admin.post(f'/admin/listings/{car_id}/delete',
                                 follow_redirects=True)
        assert r.status_code == 200
        assert Car.query.get(car_id) is None

    def test_non_admin_cannot_archive(self, logged_in_seller, active_car):
        r = logged_in_seller.post(f'/admin/listings/{active_car.id}/archive')
        assert r.status_code == 403

    def test_non_admin_cannot_delete_listing(self, logged_in_buyer, active_car):
        r = logged_in_buyer.post(f'/admin/listings/{active_car.id}/delete')
        assert r.status_code == 403