import threading
from contextlib import contextmanager
from datetime import datetime

import oracledb
import pytest
from fastapi.testclient import TestClient

from main import FeatureRequest, app, make_binds


def payload(**overrides):
    return dict(app_number='test', fio='  TEST Person  ',
                phone_num='8 (999) 111-11-11', date='12.02.2026', **overrides)


class FakeDB:
    def __init__(self):
        self.row = (0,) * 15
        self.fail = False
        self.calls = []

    @contextmanager
    def acquire(self):
        if self.fail:
            raise oracledb.Error('simulated outage')
        yield self

    @contextmanager
    def cursor(self):
        yield self

    def execute(self, sql, binds):
        self.calls.append((sql, binds))

    def fetchone(self):
        return self.row


@pytest.fixture
def client():
    app.state.api_key = 'test-key'
    app.state.pool = FakeDB()
    app.state.db_slots = threading.BoundedSemaphore(2)
    # No lifespan: unit tests never open a real Oracle connection.
    yield TestClient(app)


def post(client, body=None, key='test-key'):
    return client.post('/v1/customer-features', json=body or payload(),
                       headers={'X-API-Key': key})


def test_inclusive_dates_and_original_identity_values():
    binds = make_binds(FeatureRequest(**payload()))
    assert binds['d1'] == datetime(2026, 2, 12)
    assert binds['d7'] == datetime(2026, 2, 6)
    assert binds['d30'] == datetime(2026, 1, 14)
    assert binds['end_date'] == datetime(2026, 2, 13)
    assert binds['fio'] == '  TEST Person  '
    assert binds['phone'] == '8 (999) 111-11-11'


def test_missing_customer_returns_fifteen_false_flags(client):
    response = post(client)
    assert response.status_code == 200
    result = response.json()
    assert result.pop('app_number') == 'test'
    assert len(result) == 15
    assert all(value is False for value in result.values())
    assert len(app.state.pool.calls) == 1


def test_credit_and_guarantee_mapping(client):
    app.state.pool.row = (0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 0, 0, 1, 1, 1)
    result = post(client).json()
    assert result['has_mirlada_1day_ago'] is False
    assert result['has_mirlada_7day_ago_cred'] is True
    assert result['has_mirlada_7day_ago_cred_car'] is True
    assert result['has_mirlada_30day_ago_auto_care'] is False
    assert result['has_guarant_1day_ago'] is True


def test_auth_rejection_does_not_query_database(client):
    assert post(client, key='wrong').status_code == 401
    assert not app.state.pool.calls


def test_outage_returns_503_and_releases_slot(client):
    app.state.pool.fail = True
    assert post(client).status_code == 503
    app.state.pool.fail = False
    assert post(client).status_code == 200


def test_overload_returns_503(client):
    slots = app.state.db_slots
    slots.acquire()
    slots.acquire()
    try:
        response = post(client)
        assert response.status_code == 503
        assert response.headers['Retry-After'] == '1'
        assert not app.state.pool.calls
    finally:
        slots.release()
        slots.release()


def test_invalid_request_does_not_echo_personal_data(client):
    body = payload()
    body['date'] = '31.02.2026'
    response = post(client, body)
    assert response.status_code == 422
    assert body['fio'] not in response.text
    assert body['phone_num'] not in response.text


def test_cache_days_is_ignored():
    first = FeatureRequest(**payload(cache_days=1))
    second = FeatureRequest(**payload(cache_days=100))
    assert make_binds(first) == make_binds(second)
