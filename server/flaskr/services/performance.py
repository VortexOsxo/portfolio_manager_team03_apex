"""Portfolio performance calculations: unrealized P&L, realized P&L, day change.

Pure functions - no DB or HTTP access. Callers pass in transaction rows and
live market data they've already fetched.
"""


def compute_positions(transactions):
    """Walk transactions in chronological order, tracking running average cost
    per ticker under the average-cost method.

    A buy blends into the average cost of shares currently held; a sell is
    realized against that running average and leaves it unchanged. Processing
    must happen in transaction order, since the average cost after a sell
    followed by a new buy differs from an all-time average across every buy
    ever made.

    Returns (avg_cost_by_ticker, realized_pnl_by_ticker). avg_cost_by_ticker
    only includes tickers with a currently open position.
    """
    ordered = sorted(transactions, key=lambda tx: (tx['transaction_date'], tx.get('tr_id', 0)))

    shares_held = {}
    avg_cost = {}
    realized = {}

    for tx in ordered:
        ticker = tx['ticker']
        amount = float(tx['amount'])
        price = float(tx['cost_basis'])
        held = shares_held.get(ticker, 0.0)
        cost = avg_cost.get(ticker, 0.0)

        if amount > 0:
            held += amount
            cost = (cost * (held - amount) + price * amount) / held
        else:
            sold = -amount
            realized[ticker] = realized.get(ticker, 0) + (price - cost) * sold
            held += amount

        shares_held[ticker] = held
        avg_cost[ticker] = cost

    open_avg_cost = {
        ticker: cost for ticker, cost in avg_cost.items() if shares_held.get(ticker, 0) > 0
    }
    realized = {ticker: round(value, 2) for ticker, value in realized.items()}

    return open_avg_cost, realized


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


def day_change(amount_held, day_change_per_share, day_change_pct):
    """Today's $ move on a position (shares x Yahoo's per-share change), and its %."""
    if day_change_per_share is None or not amount_held:
        return {"value": None, "pct": day_change_pct}

    return {
        "value": round(float(amount_held) * day_change_per_share, 2),
        "pct": day_change_pct,
    }
