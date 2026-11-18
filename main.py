import logging
import os
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import date as Date
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Annotated

import oracledb
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field, field_validator

logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger('dss-dwh')

GROUPS = (
    ('mirlada', 'has_mirlada', ''),
    ('cred', 'has_mirlada', '_cred'),
    ('cred_car', 'has_mirlada', '_cred_car'),
    ('auto_care', 'has_mirlada', '_auto_care'),
    ('guarant', 'has_guarant', ''),
)
DAYS = (1, 7, 30)
FLAG_NAMES = tuple(
    f'{prefix}_{days}day_ago{suffix}'
    for _, prefix, suffix in GROUPS for days in DAYS
)
# Only program constants are interpolated; request values use Oracle binds.
FEATURE_SQL = 'SELECT ' + ', '.join(
    f'NVL(MAX(CASE WHEN event_day >= :d{days} THEN {column} ELSE 0 END), 0)'
    for column, _, _ in GROUPS for days in DAYS
) + """
    FROM app.mv_customer_day
    WHERE name_key = LOWER(TRIM(:fio))
      AND phone_key = REGEXP_REPLACE(:phone, '^8', '7')
      AND event_day >= :d30 AND event_day < :end_date
"""


class FeatureRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    app_number: str = Field(min_length=1, max_length=100)
    fio: str = Field(min_length=1, max_length=200)
    phone_num: str = Field(min_length=1, max_length=100)
    as_of: Date = Field(alias='date')
    cache_days: int | None = None

    @field_validator('fio', 'phone_num')
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('Empty value')
        return value

    @field_validator('as_of', mode='before')
    @classmethod
    def parse_date(cls, value):
        if isinstance(value, str):
            for fmt in ('%d.%m.%Y', '%Y-%m-%d'):
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    pass
            raise ValueError('Use DD.MM.YYYY or YYYY-MM-DD')
        return value

    @field_validator('as_of')
    @classmethod
    def date_range(cls, value: Date) -> Date:
        if value < Date.min + timedelta(days=29) or value == Date.max:
            raise ValueError('Date outside supported range')
        return value


class FeatureResponse(BaseModel):
    app_number: str
    has_mirlada_1day_ago: bool
    has_mirlada_7day_ago: bool
    has_mirlada_30day_ago: bool
    has_mirlada_1day_ago_cred: bool
    has_mirlada_7day_ago_cred: bool
    has_mirlada_30day_ago_cred: bool
    has_mirlada_1day_ago_cred_car: bool
    has_mirlada_7day_ago_cred_car: bool
    has_mirlada_30day_ago_cred_car: bool
    has_mirlada_1day_ago_auto_care: bool
    has_mirlada_7day_ago_auto_care: bool
    has_mirlada_30day_ago_auto_care: bool
    has_guarant_1day_ago: bool
    has_guarant_7day_ago: bool
    has_guarant_30day_ago: bool


def make_binds(payload: FeatureRequest) -> dict:
    day = datetime.combine(payload.as_of, time.min)
    return {
        'fio': payload.fio, 'phone': payload.phone_num,
        'd1': day, 'd7': day - timedelta(days=6),
        'd30': day - timedelta(days=29),
        'end_date': day + timedelta(days=1),
    }


def read_secret(variable: str, default: str) -> str:
    value = Path(os.getenv(variable, default)).read_text('utf-8').rstrip('\r\n')
    if not value:
        raise RuntimeError(f'Empty secret: {variable}')
    return value


@asynccontextmanager
async def lifespan(app: FastAPI):
    password = read_secret('ORACLE_PASSWORD_FILE', '/run/secrets/oracle_password')
    app.state.api_key = read_secret('API_KEY_FILE', '/run/secrets/customer_api_key')
    app.state.db_slots = threading.BoundedSemaphore(2)
    app.state.pool = oracledb.create_pool(
        user=os.environ['ORACLE_USER'], password=password,
        dsn=os.environ['ORACLE_DSN'], min=1, max=2, increment=1,
        getmode=oracledb.POOL_GETMODE_TIMEDWAIT, wait_timeout=2000,
        tcp_connect_timeout=5, retry_count=0,
    )
    try:
        yield
    finally:
        app.state.pool.close(force=True)


app = FastAPI(title='dss-dwh', version='1.0.0', lifespan=lifespan)
key_header = APIKeyHeader(name='X-API-Key', auto_error=False)


def require_key(
    request: Request,
    supplied: Annotated[str | None, Depends(key_header)],
) -> None:
    if supplied is None or not secrets.compare_digest(
        supplied.encode(), request.app.state.api_key.encode()
    ):
        raise HTTPException(401, 'Invalid API key')


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Do not echo personal data from invalid request bodies.
    return JSONResponse(status_code=422, content={
        'detail': 'Invalid request',
        'errors': [{'loc': list(e['loc']), 'type': e['type']} for e in exc.errors()],
    })


def query(request: Request, sql: str, binds: dict | None = None):
    slots = request.app.state.db_slots
    if not slots.acquire(blocking=False):
        raise HTTPException(503, 'Service busy', headers={'Retry-After': '1'})
    try:
        with request.app.state.pool.acquire() as connection:
            connection.call_timeout = 3000  # Per round trip, not HTTP timeout.
            with connection.cursor() as cursor:
                cursor.execute(sql, binds or {})
                return cursor.fetchone()
    except oracledb.Error as exc:
        error = exc.args[0] if exc.args else None
        logger.error('Oracle failure code=%s', getattr(error, 'full_code', 'UNKNOWN'))
        raise HTTPException(503, 'Data source unavailable') from None
    finally:
        slots.release()


@app.get('/health/live')
async def live():
    return {'status': 'ok'}


@app.get('/health/ready', dependencies=[Depends(require_key)])
def ready(request: Request):
    query(request, 'SELECT 1 FROM app.mv_customer_day WHERE ROWNUM = 1')
    return {'status': 'ready'}


@app.post('/v1/customer-features', response_model=FeatureResponse,
          dependencies=[Depends(require_key)])
def features(payload: FeatureRequest, request: Request):
    row = query(request, FEATURE_SQL, make_binds(payload))
    if row is None or len(row) != len(FLAG_NAMES):
        raise HTTPException(500, 'Unexpected database result')
    return FeatureResponse(
        app_number=payload.app_number,
        **{name: bool(value) for name, value in zip(FLAG_NAMES, row)},
    )
