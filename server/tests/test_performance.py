from datetime import datetime

from flaskr.services import performance
from flaskr.services.performance import compute_portfolio_values, get_tickers_for_range


def tx(ticker, amount, cost_basis, transaction_date, tr_id):
    return {
        "tr_id": tr_id,
        "ticker": ticker,
        "amount": amount,
        "cost_basis": cost_basis,
        "transaction_date": transaction_date,
    }


class TestComputePositions:
    def test_single_buy_sets_avg_cost(self):
        transactions = [tx("AAPL", 10, 100, "2024-01-01", 1)]

        avg_cost, realized = performance.compute_positions(transactions)

        assert avg_cost == {"AAPL": 100.0}
        assert realized == {}

    def test_two_buys_blend_into_weighted_average(self):
        transactions = [
            tx("AAPL", 10, 100, "2024-01-01", 1),
            tx("AAPL", 10, 120, "2024-01-02", 2),
        ]

        avg_cost, realized = performance.compute_positions(transactions)

        assert avg_cost == {"AAPL": 110.0}
        assert realized == {}

    def test_partial_sell_realizes_gain_and_keeps_avg_cost(self):
        transactions = [
            tx("AAPL", 10, 100, "2024-01-01", 1),
            tx("AAPL", 10, 120, "2024-01-02", 2),
            tx("AAPL", -5, 150, "2024-01-03", 3),
        ]

        avg_cost, realized = performance.compute_positions(transactions)

        assert avg_cost == {"AAPL": 110.0}
        assert realized == {"AAPL": 200.0}

    def test_fully_sold_position_drops_out_of_avg_cost(self):
        transactions = [
            tx("AAPL", 10, 100, "2024-01-01", 1),
            tx("AAPL", 10, 120, "2024-01-02", 2),
            tx("AAPL", -5, 150, "2024-01-03", 3),
            tx("AAPL", -15, 130, "2024-01-04", 4),
        ]

        avg_cost, realized = performance.compute_positions(transactions)

        assert avg_cost == {}
        assert realized == {"AAPL": 500.0}

    def test_tickers_are_tracked_independently(self):
        transactions = [
            tx("AAPL", 10, 100, "2024-01-01", 1),
            tx("MSFT", 5, 200, "2024-01-01", 2),
        ]

        avg_cost, realized = performance.compute_positions(transactions)

        assert avg_cost == {"AAPL": 100.0, "MSFT": 200.0}
        assert realized == {}

    def test_out_of_order_input_is_sorted_before_processing(self):
        # Same transactions as test_partial_sell_realizes_gain_and_keeps_avg_cost,
        # but handed in scrambled - the function must sort by (date, tr_id) itself.
        transactions = [
            tx("AAPL", -5, 150, "2024-01-03", 3),
            tx("AAPL", 10, 120, "2024-01-02", 2),
            tx("AAPL", 10, 100, "2024-01-01", 1),
        ]

        avg_cost, realized = performance.compute_positions(transactions)

        assert avg_cost == {"AAPL": 110.0}
        assert realized == {"AAPL": 200.0}

    def test_no_transactions_returns_empty(self):
        avg_cost, realized = performance.compute_positions([])

        assert avg_cost == {}
        assert realized == {}


class TestComputeRealizedLots:
    def test_no_sells_returns_empty(self):
        transactions = [tx("AAPL", 10, 100, "2024-01-01", 1)]

        assert performance.compute_realized_lots(transactions) == []

    def test_partial_sell_emits_one_lot(self):
        transactions = [
            tx("AAPL", 10, 100, "2024-01-01", 1),
            tx("AAPL", 10, 120, "2024-01-02", 2),
            tx("AAPL", -5, 150, "2024-01-03", 3),
        ]

        lots = performance.compute_realized_lots(transactions)

        assert lots == [
            {
                "ticker": "AAPL",
                "date": "2024-01-03",
                "shares": 5.0,
                "avg_cost": 110.0,
                "sale_price": 150.0,
                "pnl": 200.0,
            }
        ]

    def test_multiple_sells_emit_separate_lots_in_chronological_order(self):
        transactions = [
            tx("AAPL", 10, 100, "2024-01-01", 1),
            tx("AAPL", -4, 150, "2024-01-02", 2),
            tx("AAPL", -6, 90, "2024-01-03", 3),
        ]

        lots = performance.compute_realized_lots(transactions)

        assert [lot["date"] for lot in lots] == ["2024-01-02", "2024-01-03"]
        assert lots[0]["pnl"] == 200.0
        assert lots[1]["pnl"] == -60.0

    def test_out_of_order_input_is_sorted_before_processing(self):
        transactions = [
            tx("AAPL", -5, 150, "2024-01-03", 3),
            tx("AAPL", 10, 120, "2024-01-02", 2),
            tx("AAPL", 10, 100, "2024-01-01", 1),
        ]

        lots = performance.compute_realized_lots(transactions)

        assert lots == [
            {
                "ticker": "AAPL",
                "date": "2024-01-03",
                "shares": 5.0,
                "avg_cost": 110.0,
                "sale_price": 150.0,
                "pnl": 200.0,
            }
        ]


class TestUnrealizedPnl:
    def test_gain(self):
        result = performance.unrealized_pnl(10, 100, 150)

        assert result == {"pnl": 500.0, "pnl_pct": 50.0}

    def test_loss(self):
        result = performance.unrealized_pnl(10, 150, 100)

        assert result == {"pnl": -500.0, "pnl_pct": -33.33}

    def test_missing_avg_cost_returns_none(self):
        assert performance.unrealized_pnl(10, None, 150) == {"pnl": None, "pnl_pct": None}

    def test_missing_current_price_returns_none(self):
        assert performance.unrealized_pnl(10, 100, None) == {"pnl": None, "pnl_pct": None}

    def test_zero_amount_held_returns_none(self):
        assert performance.unrealized_pnl(0, 100, 150) == {"pnl": None, "pnl_pct": None}

    def test_zero_avg_cost_computes_pnl_but_not_pct(self):
        # avg_cost of 0 makes the % meaningless (division by zero), but the $ pnl still holds.
        result = performance.unrealized_pnl(10, 0, 150)

        assert result == {"pnl": 1500.0, "pnl_pct": None}


class TestDayChange:
    def test_normal_change(self):
        result = performance.day_change(10, 2.5, 1.2)

        assert result == {"value": 25.0, "pct": 1.2}

    def test_missing_day_change_per_share_returns_none_value_but_keeps_pct(self):
        result = performance.day_change(10, None, 1.2)

        assert result == {"value": None, "pct": 1.2}

    def test_zero_amount_held_returns_none_value(self):
        result = performance.day_change(0, 2.5, 1.2)

        assert result == {"value": None, "pct": 1.2}


class TestComputePortfolioValues:
    def test_applies_transactions_once_in_chronological_order(self):
        dates = ["2026-01-02", "2026-01-05", "2026-01-06"]
        transactions = [
            {
                "tr_id": 2,
                "ticker": "AAPL",
                "amount": -2,
                "transaction_date": datetime(2026, 1, 6, 11, 0),
            },
            {
                "tr_id": 1,
                "ticker": "AAPL",
                "amount": 5,
                "transaction_date": datetime(2026, 1, 2, 9, 30),
            },
        ]
        ticker_values = {
            "AAPL": {
                "2026-01-02": 100,
                "2026-01-05": 110,
                "2026-01-06": 120,
            },
        }

        values = compute_portfolio_values(dates, transactions, ticker_values)

        assert values == [500.0, 550.0, 360.0]

    def test_combines_multiple_tickers_and_forward_fills_missing_prices(self):
        dates = ["2026-02-02", "2026-02-03"]
        transactions = [
            {
                "tr_id": 1,
                "ticker": "AAPL",
                "amount": 2,
                "transaction_date": "2026-02-02",
            },
            {
                "tr_id": 2,
                "ticker": "MSFT",
                "amount": 3,
                "transaction_date": "2026-02-02",
            },
        ]
        ticker_values = {
            "AAPL": {"2026-02-02": 10, "2026-02-03": 12},
            "MSFT": {"2026-02-02": 20},
        }

        values = compute_portfolio_values(dates, transactions, ticker_values)

        # MSFT has no price for 02-03 (a data gap, not a market holiday), so it
        # holds its last known price (20) instead of dropping to $0 for the day.
        assert values == [80.0, 84.0]

    def test_forward_fill_carries_across_multiple_missing_days(self):
        dates = ["2026-04-01", "2026-04-02", "2026-04-03", "2026-04-04"]
        transactions = [
            {"tr_id": 1, "ticker": "GME", "amount": 4, "transaction_date": "2026-04-01"},
        ]
        ticker_values = {
            # gap on both 04-02 and 04-03; price resumes on 04-04
            "GME": {"2026-04-01": 25, "2026-04-04": 30},
        }

        values = compute_portfolio_values(dates, transactions, ticker_values)

        assert values == [100.0, 100.0, 100.0, 120.0]

    def test_no_forward_fill_before_a_tickers_first_known_price(self):
        dates = ["2026-05-01", "2026-05-02"]
        transactions = [
            {"tr_id": 1, "ticker": "NEWCO", "amount": 1, "transaction_date": "2026-05-01"},
        ]
        ticker_values = {
            # no price at all on the first date - nothing to forward-fill from yet
            "NEWCO": {"2026-05-02": 50},
        }

        values = compute_portfolio_values(dates, transactions, ticker_values)

        assert values == [0.0, 50.0]

    def test_returns_zeroes_before_the_first_transaction(self):
        dates = ["2026-03-02", "2026-03-03"]
        transactions = [
            {
                "tr_id": 1,
                "ticker": "NVDA",
                "amount": 1,
                "transaction_date": "2026-03-03",
            },
        ]
        ticker_values = {
            "NVDA": {"2026-03-02": 180, "2026-03-03": 185},
        }

        values = compute_portfolio_values(dates, transactions, ticker_values)

        assert values == [0.0, 185.0]


class TestGetTickersForRange:
    def test_excludes_positions_closed_before_the_range_and_future_trades(self):
        transactions = [
            {"tr_id": 1, "ticker": "OLD", "amount": 2, "transaction_date": "2025-01-01"},
            {"tr_id": 2, "ticker": "OLD", "amount": -2, "transaction_date": "2025-02-01"},
            {"tr_id": 3, "ticker": "HELD", "amount": 1, "transaction_date": "2025-03-01"},
            {"tr_id": 4, "ticker": "TRADED", "amount": 1, "transaction_date": "2026-01-15"},
            {"tr_id": 5, "ticker": "FUTURE", "amount": 1, "transaction_date": "2027-01-01"},
        ]

        tickers = get_tickers_for_range("2026-01-01", "2026-01-31", transactions)

        assert tickers == ["HELD", "TRADED"]
