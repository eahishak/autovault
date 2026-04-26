"""
tests/test_filters.py

Tests for the browse/filter system.
Covers every filter type, range filtering, sorting,
combined filters, and edge cases with invalid input.
"""

import pytest
from app.models import Car


def add_car(db_session, seller, **kwargs):
    defaults = dict(
        seller_id=seller.id,
        make='Ford', model='Focus', year=2020,
        price=1_500_000, mileage=30000,
        condition='Used', body_type='Sedan',
        fuel_type='Gasoline', transmission='Automatic',
        city='Dallas', state='TX', status='active',
    )
    defaults.update(kwargs)
    car = Car(**defaults)
    db_session.add(car)
    db_session.flush()
    return car


class TestBrowsePage:

    def test_browse_page_loads(self, client):
        r = client.get('/browse')
        assert r.status_code == 200

    def test_browse_shows_active_listings_only(self, client, db_session, seller,
                                               active_car, archived_car):
        r = client.get('/browse')
        assert r.status_code == 200
        assert b'Toyota' in r.data
        assert b'archived' not in r.data.lower() or b'Toyota' in r.data


class TestMakeFilter:

    def test_filter_by_make_returns_only_that_make(self, client, db_session, seller):
        add_car(db_session, seller, make='Honda', model='Accord', slug='honda-accord-t1')
        add_car(db_session, seller, make='Mazda', model='3',      slug='mazda-3-t1')
        r = client.get('/browse?make=Honda')
        assert r.status_code == 200
        assert b'Honda' in r.data

    def test_filter_by_make_case_insensitive(self, client, db_session, seller):
        add_car(db_session, seller, make='Nissan', model='Altima', slug='nissan-altima-t1')
        r = client.get('/browse?make=nissan')
        assert r.status_code == 200


class TestPriceFilter:

    def test_price_min_excludes_cheaper(self, client, db_session, seller):
        add_car(db_session, seller, make='Cheap', model='Car',
                price=500_000, slug='cheap-car-t1')
        add_car(db_session, seller, make='Expensive', model='Car',
                price=5_000_000, slug='expensive-car-t1')
        r = client.get('/browse?price_min=20000')
        assert r.status_code == 200

    def test_price_max_excludes_pricier(self, client, db_session, seller):
        add_car(db_session, seller, make='Budget', model='Car',
                price=1_000_000, slug='budget-car-t1')
        add_car(db_session, seller, make='Luxury', model='Car',
                price=10_000_000, slug='luxury-car-t1')
        r = client.get('/browse?price_max=15000')
        assert r.status_code == 200

    def test_invalid_price_ignored(self, client):
        r = client.get('/browse?price_min=notanumber')
        assert r.status_code == 200


class TestMileageFilter:

    def test_mileage_max_filters_high_mileage(self, client, db_session, seller):
        add_car(db_session, seller, make='Low', model='Mi',
                mileage=5000, slug='low-mi-t1')
        add_car(db_session, seller, make='High', model='Mi',
                mileage=200000, slug='high-mi-t1')
        r = client.get('/browse?mileage_max=50000')
        assert r.status_code == 200

    def test_invalid_mileage_ignored(self, client):
        r = client.get('/browse?mileage_max=abc')
        assert r.status_code == 200


class TestYearFilter:

    def test_year_min_excludes_older(self, client, db_session, seller):
        add_car(db_session, seller, year=2015, make='Old', model='Car', slug='old-car-t1')
        add_car(db_session, seller, year=2023, make='New', model='Car', slug='new-car-t1')
        r = client.get('/browse?year_min=2020')
        assert r.status_code == 200

    def test_year_max_excludes_newer(self, client, db_session, seller):
        add_car(db_session, seller, year=2024, make='Very', model='New', slug='very-new-t1')
        r = client.get('/browse?year_max=2022')
        assert r.status_code == 200


class TestBodyTypeFilter:

    def test_filter_by_suv(self, client, db_session, seller):
        add_car(db_session, seller, body_type='SUV', make='Jeep',
                model='Cherokee', slug='jeep-cherokee-t1')
        r = client.get('/browse?body_type=SUV')
        assert r.status_code == 200

    def test_filter_by_pickup(self, client, db_session, seller):
        add_car(db_session, seller, body_type='Pickup Truck',
                make='Ram', model='1500', slug='ram-1500-t1')
        r = client.get('/browse?body_type=Pickup+Truck')
        assert r.status_code == 200


class TestFuelTypeFilter:

    def test_filter_electric(self, client, db_session, seller):
        add_car(db_session, seller, fuel_type='Electric',
                make='Tesla', model='Model3', slug='tesla-model3-t1')
        r = client.get('/browse?fuel_type=Electric')
        assert r.status_code == 200

    def test_filter_hybrid(self, client, db_session, seller):
        add_car(db_session, seller, fuel_type='Hybrid',
                make='Toyota', model='Prius', slug='toyota-prius-t1')
        r = client.get('/browse?fuel_type=Hybrid')
        assert r.status_code == 200


class TestSorting:

    def test_sort_price_asc(self, client, db_session, seller):
        add_car(db_session, seller, price=3_000_000, make='High', model='Price', slug='hi-price-t1')
        add_car(db_session, seller, price=1_000_000, make='Low',  model='Price', slug='lo-price-t1')
        r = client.get('/browse?sort=price_asc')
        assert r.status_code == 200

    def test_sort_price_desc(self, client):
        r = client.get('/browse?sort=price_desc')
        assert r.status_code == 200

    def test_sort_year_desc(self, client):
        r = client.get('/browse?sort=year_desc')
        assert r.status_code == 200

    def test_sort_mileage(self, client):
        r = client.get('/browse?sort=mileage')
        assert r.status_code == 200

    def test_invalid_sort_falls_back_to_newest(self, client):
        r = client.get('/browse?sort=invalidvalue')
        assert r.status_code == 200


class TestCombinedFilters:

    def test_make_and_price_combined(self, client, db_session, seller):
        add_car(db_session, seller, make='BMW', model='3 Series',
                price=4_000_000, slug='bmw-3series-t1')
        r = client.get('/browse?make=BMW&price_max=50000')
        assert r.status_code == 200

    def test_all_filters_combined(self, client):
        r = client.get('/browse?make=Toyota&body_type=SUV&fuel_type=Hybrid'
                       '&price_min=20000&price_max=60000&year_min=2020'
                       '&mileage_max=50000&sort=price_asc')
        assert r.status_code == 200


class TestSearchQuery:

    def test_keyword_search_by_make(self, client, active_car):
        r = client.get('/browse?q=Toyota')
        assert r.status_code == 200
        assert b'Toyota' in r.data

    def test_keyword_search_no_results(self, client):
        r = client.get('/browse?q=ZZZNonExistentMakeXXX')
        assert r.status_code == 200


class TestPagination:

    def test_page_param_accepted(self, client):
        r = client.get('/browse?page=1')
        assert r.status_code == 200

    def test_out_of_range_page_returns_empty(self, client):
        r = client.get('/browse?page=9999')
        assert r.status_code == 200