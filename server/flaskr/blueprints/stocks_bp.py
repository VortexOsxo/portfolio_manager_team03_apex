from flask import Blueprint, jsonify, request
import mysql

from flaskr.services.database import get_transactions, buy_holding, sell_holding
from flaskr.services import performance
from flaskr.yahoo_finance import YahooFinanceStock, search_stocks

stocks_bp = Blueprint("stocks", __name__, url_prefix="/stocks")


@stocks_bp.get("/search")
def search_stocks_route():
    query = request.args.get("q", "")
    return jsonify(search_stocks(query)), 200


def _build_holdings():
    """Group transactions by ticker and enrich with live price and P&L.

    Returns (holdings, realized_pnl_by_ticker).
    """
    transactions = get_transactions()

    amounts = {}
    for tx in transactions:
        ticker = tx['ticker']
        amounts[ticker] = amounts.get(ticker, 0) + float(tx['amount'])

    avg_costs, realized = performance.compute_positions(transactions)

    holdings = {}
    for ticker, amount in amounts.items():
        if amount == 0:
            continue

        info = YahooFinanceStock(ticker).get_info()
        current_price = info["current_price"]
        avg_cost = avg_costs.get(ticker)

        pnl = performance.unrealized_pnl(amount, avg_cost, current_price)
        change = performance.day_change(amount, info["day_change"], info["day_change_pct"])

        holdings[ticker] = {
            'ticker': ticker,
            'name': info["company_name"],
            'amount': amount,
            'current_price': current_price,
            'value': round(amount * current_price, 2) if current_price is not None else None,
            'avg_cost': avg_cost,
            'unrealized_pnl': pnl["pnl"],
            'unrealized_pnl_pct': pnl["pnl_pct"],
            'day_change': change["value"],
            'day_change_pct': change["pct"],
        }

    return holdings, realized


@stocks_bp.get("/")
def get_stocks():
    holdings, _ = _build_holdings()
    return jsonify(holdings), 200


@stocks_bp.get("/summary")
def get_summary():
    holdings, realized = _build_holdings()

    total_value = sum(h['value'] for h in holdings.values() if h['value'] is not None)
    total_cost_basis = sum(
        h['avg_cost'] * h['amount'] for h in holdings.values() if h['avg_cost'] is not None
    )
    total_unrealized_pnl = sum(
        h['unrealized_pnl'] for h in holdings.values() if h['unrealized_pnl'] is not None
    )
    total_day_change = sum(
        h['day_change'] for h in holdings.values() if h['day_change'] is not None
    )
    total_realized_pnl = sum(realized.values())

    prior_value = total_value - total_day_change
    total_unrealized_pnl_pct = round(total_unrealized_pnl / total_cost_basis * 100, 2) if total_cost_basis else None
    total_day_change_pct = round(total_day_change / prior_value * 100, 2) if prior_value else None

    return jsonify({
        'total_value': round(total_value, 2),
        'total_cost_basis': round(total_cost_basis, 2),
        'total_unrealized_pnl': round(total_unrealized_pnl, 2),
        'total_unrealized_pnl_pct': total_unrealized_pnl_pct,
        'total_day_change': round(total_day_change, 2),
        'total_day_change_pct': total_day_change_pct,
        'total_realized_pnl': round(total_realized_pnl, 2),
    }), 200

@stocks_bp.post("/buy")
def buy_stock():
    data = request.get_json()
    ticker = data.get("ticker")
    amount = data.get("amount")

    if ticker is None or amount is None:
        return "", 400

    cost_basis = data.get("cost_basis")
    transaction_date = data.get("transaction_date")
    try: 
        buy_holding(ticker, amount, cost_basis, transaction_date)
    except mysql.connector.errors.IntegrityError as e:
        return "", 400

    return jsonify({"message": "Stock bought successfully"}), 201

@stocks_bp.post("/sell")
def sell_stock():
    data = request.get_json()
    ticker = data.get("ticker")
    amount = data.get("amount")

    if ticker is None or amount is None:
        return "", 400

    cost_basis = data.get("cost_basis")
    transaction_date = data.get("transaction_date")
    try:
        sell_holding(ticker, amount, cost_basis, transaction_date)
    except mysql.connector.errors.IntegrityError as e:
        return "", 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"message": "Stock sold successfully"}), 201