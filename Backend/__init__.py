from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
from datetime import timedelta
import os
import logging
from logging.handlers import RotatingFileHandler

def create_app():
    print("✅ create_app() executed")
    load_dotenv()

    app = Flask(__name__)

    # === CORS Setup ===
    CORS(app, supports_credentials=True, origins=["http://localhost:5173"])

    @app.after_request
    def apply_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "http://localhost:5173")
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    # === JWT Configuration ===
    app.config['JWT_SECRET_KEY'] = os.getenv("JWT_SECRET_KEY", "super-secret-key")
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=int(os.getenv("JWT_EXPIRE_MINUTES", 60)))

    JWTManager(app)

    # === Logging ===
    log_path = 'flask_app.log'
    handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3)
    logging.basicConfig(handlers=[handler], level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s')
    logging.info("🚀 Flask app initialized")

    # === Health Routes ===
    @app.route("/health")
    def health():
        return jsonify({"status": "healthy"})

    @app.route("/")
    def home():
        return jsonify({"message": "Flask API is working"})

    # === Register Blueprints ===
    from app.routes.customer import customer_bp
    from app.routes.restaurant import restaurant_bp
    from app.routes.delivery import delivery_bp
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(customer_bp, url_prefix="/customer")
    app.register_blueprint(restaurant_bp, url_prefix="/restaurant")
    app.register_blueprint(delivery_bp, url_prefix="/delivery")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    logging.info("✅ All blueprints registered")
    return app
