from flaskr.services import performance


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
