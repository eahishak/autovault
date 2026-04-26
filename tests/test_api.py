"""
tests/test_api.py

Tests for all /api/* JSON endpoints.
Covers search, car grid, favorites toggle, notifications,
AJAX message send, message polling, and car comparison.
"""

import json
import pytest
from app.models import Favorite, Notification


class TestSearchAPI:

    def test_search_returns_json(self, client, active_car):
        r = client.get('/api/search?q=Toyota')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert 'results' in data

    def test_search_too_short_returns_empty(self, client):
        r = client.get('/api/search?q=T')
        data = json.loads(r.data)
        assert data['results'] == []

    def test_search_no_query_returns_empty(self, client):
        r = client.get('/api/search')
        data = json.loads(r.data)
        assert data['results'] == []

    def test_search_finds_matching_make(self, client, active_car):
        r = client.get('/api/search?q=Toyota')
        data = json.loads(r.data)
        labels = [item['label'] for item in data['results']]
        assert any('Toyota' in label for label in labels)

    def test_search_returns_url_in_results(self, client, active_car):
        r = client.get('/api/search?q=Toyota')
        data = json.loads(r.data)
        if data['results']:
            assert 'url' in data['results'][0]

    def test_search_result_limit_respected(self, client, active_car):
        r = client.get('/api/search?q=a&limit=3')
        data = json.loads(r.data)
        assert len(data['results']) <= 3


class TestCarsAPI:

    def test_cars_returns_json(self, client, active_car):
        r = client.get('/api/cars')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert 'cars' in data
        assert 'total' in data

    def test_cars_html_format_returns_html_field(self, client, active_car):
        r = client.get('/api/cars?format=html')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert 'html' in data
        assert 'total' in data

    def test_cars_filter_by_make(self, client, active_car):
        r = client.get('/api/cars?make=Toyota')
        data = json.loads(r.data)
        for car in data['cars']:
            assert car['make'] == 'Toyota'

    def test_cars_archived_not_in_results(self, client, archived_car):
        r = client.get('/api/cars')
        data = json.loads(r.data)
        ids = [c['id'] for c in data['cars']]
        assert archived_car.id not in ids

    def test_cars_pagination(self, client):
        r = client.get('/api/cars?page=1')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data['page'] == 1


class TestFavoritesAPI:

    def test_favorites_requires_auth(self, client, active_car):
        r = client.post('/api/favorites',
                        data=json.dumps({'car_id': active_car.id}),
                        content_type='application/json')
        assert r.status_code in (401, 302)

    def test_toggle_favorite_adds(self, logged_in_buyer, active_car, db_session, buyer):
        r = logged_in_buyer.post('/api/favorites',
                                 data=json.dumps({'car_id': active_car.id}),
                                 content_type='application/json')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data['favorited'] is True
        assert Favorite.query.filter_by(user_id=buyer.id, car_id=active_car.id).first() is not None

    def test_toggle_favorite_removes(self, logged_in_buyer, active_car, db_session, buyer):
        fav = Favorite(user_id=buyer.id, car_id=active_car.id)
        db_session.add(fav)
        db_session.flush()

        r = logged_in_buyer.post('/api/favorites',
                                 data=json.dumps({'car_id': active_car.id}),
                                 content_type='application/json')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data['favorited'] is False

    def test_favorite_nonexistent_car_returns_404(self, logged_in_buyer):
        r = logged_in_buyer.post('/api/favorites',
                                 data=json.dumps({'car_id': 99999}),
                                 content_type='application/json')
        assert r.status_code == 404

    def test_missing_car_id_returns_400(self, logged_in_buyer):
        r = logged_in_buyer.post('/api/favorites',
                                 data=json.dumps({}),
                                 content_type='application/json')
        assert r.status_code == 400


class TestNotificationsAPI:

    def test_notifications_requires_auth(self, client):
        r = client.get('/api/notifications')
        assert r.status_code in (401, 302)

    def test_notifications_returns_list(self, logged_in_buyer):
        r = logged_in_buyer.get('/api/notifications')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert 'notifications' in data
        assert isinstance(data['notifications'], list)

    def test_notifications_include_required_fields(self, logged_in_buyer,
                                                    db_session, buyer):
        notif = Notification(
            user_id=buyer.id,
            type='new_message',
            title='Test notif',
            body='Body text',
        )
        db_session.add(notif)
        db_session.flush()

        r = logged_in_buyer.get('/api/notifications')
        data = json.loads(r.data)
        assert len(data['notifications']) >= 1
        first = data['notifications'][0]
        assert 'title' in first
        assert 'type' in first
        assert 'is_read' in first


class TestMessagesSendAPI:

    def test_ajax_send_requires_auth(self, client, active_car, seller):
        r = client.post('/api/messages/send',
                        data=json.dumps({
                            'car_id': active_car.id,
                            'receiver_id': seller.id,
                            'content': 'Hello',
                        }),
                        content_type='application/json')
        assert r.status_code in (401, 302)

    def test_ajax_send_creates_message(self, logged_in_buyer, db_session,
                                       active_car, seller):
        r = logged_in_buyer.post('/api/messages/send',
                                 data=json.dumps({
                                     'car_id': active_car.id,
                                     'receiver_id': seller.id,
                                     'content': 'AJAX test message',
                                 }),
                                 content_type='application/json')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data['ok'] is True

    def test_ajax_send_missing_fields_returns_400(self, logged_in_buyer):
        r = logged_in_buyer.post('/api/messages/send',
                                 data=json.dumps({'car_id': 1}),
                                 content_type='application/json')
        assert r.status_code == 400


class TestMessagesPollAPI:

    def test_poll_requires_auth(self, client, active_car, seller):
        r = client.get(f'/api/messages/poll?car_id={active_car.id}&other_id={seller.id}')
        assert r.status_code in (401, 302)

    def test_poll_returns_empty_for_no_messages(self, logged_in_buyer, active_car, seller):
        r = logged_in_buyer.get(
            f'/api/messages/poll?car_id={active_car.id}&other_id={seller.id}&since_id=0'
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data['messages'] == []


class TestCompareAPI:

    def test_compare_returns_json(self, client, active_car):
        r = client.get(f'/api/compare?ids={active_car.id}')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert 'cars' in data

    def test_compare_limits_to_three(self, client, db_session, seller):
        from tests.conftest import active_car as ac_fixture
        cars = []
        for i in range(4):
            car = Car(
                seller_id=seller.id,
                make='Test', model=f'Car{i}', year=2020,
                price=1_000_000, mileage=10000,
                condition='Used', body_type='Sedan',
                fuel_type='Gasoline', transmission='Automatic',
                city='NYC', state='NY', status='active',
                slug=f'test-car-{i}-cmp',
            )
            db_session.add(car)
            db_session.flush()
            cars.append(car)

        ids = '&'.join(f'ids={c.id}' for c in cars)
        r = client.get(f'/api/compare?{ids}')
        data = json.loads(r.data)
        assert len(data['cars']) <= 3

    def test_compare_excludes_archived_cars(self, client, archived_car):
        r = client.get(f'/api/compare?ids={archived_car.id}')
        data = json.loads(r.data)
        assert all(c['id'] != archived_car.id for c in data['cars'])


# avoid import issue
from app.models import Car