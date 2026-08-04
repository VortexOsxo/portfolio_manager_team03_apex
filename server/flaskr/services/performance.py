"""Portfolio performance calculations: unrealized P&L, realized P&L, day change."""


def compute_positions(transactions):
    """Walk transactions in chronological order, tracking running average cost
    per ticker under the average-cost method. """
    ordered = _sort_transactions(transactions)

    shares_held = {}
    avg_cost = {}
    realized = {}

    for tx in ordered:
        ticker = tx['ticker']
        amount = float(tx['amount'])
        price = float(tx['cost_basis'])

        held = shares_held.get(ticker, 0.0) + amount
        cost = avg_cost.get(ticker, 0.0)

        if amount > 0:
            cost = (cost * (held - amount) + price * amount) / held
        else:
            realized[ticker] = realized.get(ticker, 0) + (price - cost) * abs(amount)

        shares_held[ticker] = held
        avg_cost[ticker] = cost

    open_avg_cost = {
        ticker: cost for ticker, cost in avg_cost.items() if shares_held.get(ticker, 0) > 0
    }
    realized = {ticker: round(value, 2) for ticker, value in realized.items()}

    return open_avg_cost, realized


def compute_realized_lots(transactions):
    """Same walk as compute_positions, but emits one record per sell instead of a per-ticker total."""
    ordered = _sort_transactions(transactions)

    shares_held = {}
    avg_cost = {}
    lots = []

    for tx in ordered:
        ticker = tx['ticker']
        amount = float(tx['amount'])
        price = float(tx['cost_basis'])
        held = shares_held.get(ticker, 0.0) + amount
        cost = avg_cost.get(ticker, 0.0)

        if amount > 0:
            cost = (cost * (held - amount) + price * amount) / held
        else:
            sold = -amount
            lots.append({
                'ticker': ticker,
                'date': tx['transaction_date'],
                'shares': sold,
                'avg_cost': round(cost, 4),
                'sale_price': price,
                'pnl': round((price - cost) * sold, 2),
            })

        shares_held[ticker] = held
        avg_cost[ticker] = cost

    return lots


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


def get_tickers_for_range(start_date, end_date, transactions):
    """Return tickers that can have a non-zero position during a date range."""
    holdings_at_start = {}
    tickers = set()

    for transaction in _sort_transactions(transactions):
        transaction_date = _date_key(transaction["transaction_date"])
        ticker = transaction["ticker"]
        amount = float(transaction["amount"])

        if transaction_date < start_date:
            holdings_at_start[ticker] = holdings_at_start.get(ticker, 0.0) + amount
        elif transaction_date <= end_date:
            tickers.add(ticker)

    tickers.update(
        ticker
        for ticker, amount in holdings_at_start.items()
        if amount
    )
    return sorted(tickers)


def compute_portfolio_values(dates, transactions, ticker_values):
    """Calculate daily portfolio values with one chronological transaction pass.

    `ticker_values` maps each ticker to a {date: closing_price} dictionary.
    Transactions are applied on their calendar date before that day's closing
    value is calculated. A ticker missing a price on a given date (a data gap,
    not necessarily a market holiday) holds its last known price rather than
    dropping to $0 for that day.
    """
    ordered_transactions = _sort_transactions(transactions)
    holdings = {}
    last_known_price = {}
    transaction_index = 0
    values = []

    for date in dates:
        while transaction_index < len(ordered_transactions):
            transaction = ordered_transactions[transaction_index]
            if _date_key(transaction["transaction_date"]) > date:
                break

            ticker = transaction["ticker"]
            holdings[ticker] = holdings.get(ticker, 0.0) + float(transaction["amount"])
            transaction_index += 1

        total_value = 0.0
        for ticker, amount in holdings.items():
            if not amount:
                continue
            price = ticker_values.get(ticker, {}).get(date)
            if price is not None:
                last_known_price[ticker] = price
            else:
                price = last_known_price.get(ticker)
            if price is not None:
                total_value += float(price) * amount

        values.append(round(total_value, 2))

    return values


def compute_cash_balances(dates, transactions):
    ordered = _sort_transactions(transactions)
    running_cash = 0.0
    tx_index = 0
    balances = []

    for date in dates:
        while tx_index < len(ordered):
            tx = ordered[tx_index]
            if _date_key(tx["transaction_date"]) > date:
                break

            tx_type = tx.get("type", "buy")
            amount = float(tx["amount"])
            cost_basis = tx.get("cost_basis")

            if tx_type == "deposit":
                running_cash += amount
            elif tx_type == "withdrawal":
                running_cash -= amount
            else:
                if cost_basis is not None:
                    running_cash -= amount * float(cost_basis)

            tx_index += 1

        balances.append(round(running_cash, 2))

    return balances

def _date_key(value):
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def _sort_transactions(transactions):
    return sorted(
        transactions,
        key=lambda tx: (_date_key(tx["transaction_date"]), tx.get("tr_id", 0)),
    )
