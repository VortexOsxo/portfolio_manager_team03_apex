"""Portfolio performance calculations: unrealized P&L, realized P&L, day change.

Pure functions - no DB or HTTP access. Callers pass in transaction rows and
live market data they've already fetched.
"""


def compute_avg_cost(transactions):
    """Weighted average cost per share for each ticker, keyed by ticker.

    Only BUY rows (amount > 0) count toward average cost - under the average-cost
    method, selling shares doesn't change the average cost of what's left.
    """
    cost_totals = {}
    share_totals = {}
    for tx in transactions:
        if tx['amount'] <= 0:
            continue
        ticker = tx['ticker']
        amount = float(tx['amount'])
        cost_totals[ticker] = cost_totals.get(ticker, 0) + amount * float(tx['cost_basis'])
        share_totals[ticker] = share_totals.get(ticker, 0) + amount

    return {
        ticker: cost_totals[ticker] / share_totals[ticker]
        for ticker in cost_totals
        if share_totals[ticker] > 0
    }


def unrealized_pnl(amount_held, avg_cost, current_price):
    """Unrealized $ and % gain/loss on an open position."""
    if avg_cost is None or current_price is None or not amount_held:
        return {"pnl": None, "pnl_pct": None}

    pnl = (current_price - avg_cost) * float(amount_held)
    pnl_pct = (current_price / avg_cost - 1) * 100 if avg_cost else None
    return {
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
    }


def realized_pnl(transactions, avg_cost_by_ticker):
    """Lifetime realized $ P&L per ticker from sells, keyed by ticker.

    Approximate: matches each sell against the ticker's overall average buy
    cost rather than a date-sliced FIFO lot, since average cost doesn't
    change over time in this model.
    """
    totals = {}
    for tx in transactions:
        if tx['amount'] >= 0:
            continue
        ticker = tx['ticker']
        avg_cost = avg_cost_by_ticker.get(ticker)
        if avg_cost is None:
            continue
        sold_amount = -float(tx['amount'])
        sale_price = float(tx['cost_basis'])
        totals[ticker] = totals.get(ticker, 0) + (sale_price - avg_cost) * sold_amount

    return {ticker: round(value, 2) for ticker, value in totals.items()}


def day_change(amount_held, day_change_per_share, day_change_pct):
    """Today's $ move on a position (shares x Yahoo's per-share change), and its %."""
    if day_change_per_share is None or not amount_held:
        return {"value": None, "pct": day_change_pct}

    return {
        "value": round(float(amount_held) * day_change_per_share, 2),
        "pct": day_change_pct,
    }
