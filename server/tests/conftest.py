from unittest.mock import MagicMock, patch

import pytest

from flaskr import create_app


@pytest.fixture
def app():
    app = create_app()
    # TESTING=True alone also flips on PROPAGATE_EXCEPTIONS, which makes an
    # unhandled exception raise straight through client.get()/post() instead
    # of coming back as the 500 response a real deployment would return.
    # Explicitly forcing it off here so route tests can characterize actual
    # HTTP behavior instead of catching a raised exception in the test.
    app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_db_conn():
    """Patches flaskr.services.database.get_db_connection.

    Every write path in database.py (buy_holding, sell_holding,
    update_account_balance's standalone branch via write_query) goes through
    this single function, so patching it here covers all of them. Defaults
    fetchone/fetchall to harmless empty values; override per-test as needed,
    e.g. `mock_db_conn.return_value.cursor.return_value.fetchone.return_value = (Decimal("100.00"),)`.
    """
    with patch("flaskr.services.database.get_db_connection") as mock_get_conn:
        cursor = mock_get_conn.return_value.cursor.return_value
        cursor.fetchone.return_value = None
        cursor.fetchall.return_value = []
        yield mock_get_conn


@pytest.fixture
def mock_yahoo():
    """Patches YahooFinanceStock everywhere it's bound (database.py and stocks_bp.py
    each imported their own reference, so patching the source module alone
    wouldn't reach them) with one shared MagicMock class so a test can
    configure return values in a single place.
    """
    mock_cls = MagicMock()
    mock_cls.return_value.get_info.return_value = {
        "stock_ticker": "AAPL",
        "company_name": "Apple Inc.",
        "current_price": 150.0,
        "day_change": 1.5,
        "day_change_pct": 1.0,
    }
    mock_cls.return_value.get_price_on_date.return_value = 150.0
    mock_cls.return_value.get_daily_values.return_value = {}
    mock_cls.get_daily_values_for_tickers.return_value = {}
    mock_cls.get_market_trading_days.return_value = []

    with patch("flaskr.services.database.YahooFinanceStock", mock_cls), \
         patch("flaskr.blueprints.stocks_bp.YahooFinanceStock", mock_cls):
        yield mock_cls
