def calculate_holding_metrics(holding, market_data):
    """Add market value, cost total, unrealized P&L and return % to a holding.

    holding: dict with at least "shares" and "cost_basis" (e.g. a row from the `holdings` table).
    market_data: dict from YahooFinanceStock.get_info(), with "current_price" and optionally
        "day_change" / "day_change_pct".
    """
    shares = float(holding["shares"])
    cost_basis = float(holding["cost_basis"])
    current_price = market_data["current_price"]

    market_value = shares * current_price
    cost_total = shares * cost_basis

    return {
        **holding,
        "current_price": current_price,
        "day_change": market_data.get("day_change"),
        "day_change_pct": market_data.get("day_change_pct"),
        "market_value": market_value,
        "cost_total": cost_total,
        "unrealized_pnl": market_value - cost_total,
        "return_pct": (current_price - cost_basis) / cost_basis * 100,
    }


def calculate_portfolio_summary(holdings_with_metrics):
    """Total value, total cost basis, overall return %, best/worst performer,
    and per-holding allocation % (added in place) across all holdings.

    holdings_with_metrics: list of dicts already run through calculate_holding_metrics.
    """
    total_value = sum(h["market_value"] for h in holdings_with_metrics)
    total_cost_basis = sum(h["cost_total"] for h in holdings_with_metrics)

    for h in holdings_with_metrics:
        h["allocation_pct"] = h["market_value"] / total_value * 100

    best = max(holdings_with_metrics, key=lambda h: h["return_pct"])
    worst = min(holdings_with_metrics, key=lambda h: h["return_pct"])

    return {
        "total_value": total_value,
        "total_cost_basis": total_cost_basis,
        "overall_return_pct": (total_value - total_cost_basis) / total_cost_basis * 100,
        "best_performer": {"stock_ticker": best["stock_ticker"], "return_pct": best["return_pct"]},
        "worst_performer": {"stock_ticker": worst["stock_ticker"], "return_pct": worst["return_pct"]},
    }
