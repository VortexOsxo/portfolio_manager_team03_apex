from flask import Flask

from flaskr.blueprints.accounts_bp import accounts_bp
from flaskr.blueprints.stocks_bp import stocks_bp
from flaskr.blueprints.transactions_bp import transactions_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(stocks_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(accounts_bp)

    return app