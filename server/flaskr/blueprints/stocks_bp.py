from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import InvalidOperation

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
import mysql

from flaskr.services.database import (
    get_stock_performance, get_transactions, buy_holding, sell_holding,
    get_portfolio_performance, get_account_balance
)
from flaskr.services import performance
from flaskr.services.yahoo_finance import YahooFinanceStock, search_stocks

stocks_bp = Blueprint("stocks", __name__, url_prefix="/stocks")

_MAX_INFO_WORKERS = 10


def _parse_date_range(start_date, end_date):
    """Validate start_date/end_date are well-formed "YYYY-MM-DD" strings
    with start_date on or before end_date.

    Returns None on success, or an error message string.
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        return "start_date and end_date must be in YYYY-MM-DD format"

    if start > end:
        return "start_date must not be after end_date"

    return None


@stocks_bp.get("/search")
def search_stocks_route():
    query = request.args.get("q", "")
    return jsonify(search_stocks(query)), 200


@stocks_bp.get("/quote/<string:ticker>")
def get_ticker_info(ticker):
    try:
        info = YahooFinanceStock(ticker.upper()).get_info()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    if info["company_name"] is None:
        return jsonify({"error": f'No quote found for "{ticker}"'}), 404
    return jsonify(info), 200


@stocks_bp.get("/")
@jwt_required()
def get_stocks():
    account_id = int(get_jwt_identity())
    try:
        holdings, _ = _build_holdings(account_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(holdings), 200


@stocks_bp.get("/summary")
@jwt_required()
def get_summary():
    account_id = int(get_jwt_identity())
    try:
        holdings, realized = _build_holdings(account_id)

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
        realized_lots = sorted(
            performance.compute_realized_lots(get_transactions(account_id)),
            key=lambda lot: lot['date'],
            reverse=True,
        )

        cash_balance = get_account_balance(account_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    net_worth = total_value + float(cash_balance)

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
        'realized_pnl_by_ticker': realized,
        'realized_lots': realized_lots,
        'cash_balance': round(float(cash_balance), 2),
        'net_worth': round(net_worth, 2),
    }), 200


@stocks_bp.get("/performance")
@jwt_required()
def get_performance():
    account_id = int(get_jwt_identity())
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date query parameters are required"}), 400

    date_error = _parse_date_range(start_date, end_date)
    if date_error:
        return jsonify({"error": date_error}), 400

    try:
        dates, equity, cash = get_portfolio_performance(account_id, start_date, end_date)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"dates": dates, "equity": equity, "cash": cash}), 200

@stocks_bp.get("/performance/<string:ticker>")
def get_stock_performance_route(ticker):
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date query parameters are required"}), 400

    date_error = _parse_date_range(start_date, end_date)
    if date_error:
        return jsonify({"error": date_error}), 400

    try:
        dates, equity = get_stock_performance(ticker, start_date, end_date)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"dates": dates, "equity": equity}), 200


@stocks_bp.post("/buy")
@jwt_required()
def buy_stock():
    return _trade_action(buy_holding, "bought")


@stocks_bp.post("/sell")
@jwt_required()
def sell_stock():
    return _trade_action(sell_holding, "sold")

def _trade_action(trade_fn, trade_verb):
    account_id = int(get_jwt_identity())
    data = request.get_json() or {}
    ticker = data.get("ticker")
    amount = data.get("amount")

    if ticker is None or amount is None:
        return "", 400

    cost_basis = data.get("cost_basis")
    transaction_date = data.get("transaction_date")
    try:
        trade_fn(account_id, ticker, amount, cost_basis, transaction_date)
    except mysql.connector.errors.IntegrityError:
        return "", 400
    except InvalidOperation:
        return jsonify({"error": "amount must be a number"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"message": f"Stock {trade_verb} successfully"}), 201

def _build_holdings(account_id):
    transactions = get_transactions(account_id)

    amounts = {}
    for tx in transactions:
        ticker = tx['ticker']
        amounts[ticker] = amounts.get(ticker, 0) + float(tx['amount'])
    amounts = {ticker: amount for ticker, amount in amounts.items() if amount != 0}

    avg_costs, realized = performance.compute_positions(transactions)

    tickers = list(amounts.keys())
    with ThreadPoolExecutor(max_workers=min(len(tickers), _MAX_INFO_WORKERS) or 1) as executor:
        infos = dict(zip(tickers, executor.map(lambda t: YahooFinanceStock(t).get_info(), tickers)))

    holdings = {}
    for ticker, amount in amounts.items():
        info = infos[ticker]
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

    total_holdings_value = sum(h['value'] for h in holdings.values() if h['value'] is not None)
    for h in holdings.values():
        h['pct_of_portfolio'] = (
            round(h['value'] / total_holdings_value * 100, 2)
            if h['value'] is not None and total_holdings_value
            else None
        )

    return holdings, realized