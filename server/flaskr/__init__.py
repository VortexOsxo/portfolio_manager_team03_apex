from flask import Flask

from flaskr.blueprints.stocks_bp import stocks_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(stocks_bp)

    return app