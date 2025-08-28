from flask import Blueprint, request, jsonify
from passlib.hash import bcrypt
from flask_jwt_extended import create_access_token
from app.services.db import users_table
import logging

auth_bp = Blueprint('auth', __name__)

# ✅ REGISTER
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    role = data.get('role')

    if not username or not password or not role:
        logging.warning("Registration failed: Missing username, password, or role")
        return jsonify({"error": "Username, password, and role are required"}), 400

    # ✅ Updated to support admin role too
    valid_roles = ['customer', 'restaurant', 'delivery', 'admin']
    if role not in valid_roles:
        logging.warning(f"Registration failed: Invalid role '{role}'")
        return jsonify({
            "error": f"Invalid role. Must be one of: {', '.join(valid_roles)}"
        }), 400

    # ✅ Check if user already exists
    try:
        existing = users_table.get_item(Key={'username': username})
        if 'Item' in existing:
            logging.warning(f"Registration failed: Username '{username}' already exists")
            return jsonify({"error": "User already exists"}), 400
    except Exception as e:
        logging.error(f"DynamoDB error while checking user existence: {str(e)}")
        return jsonify({"error": f"DynamoDB error: {str(e)}"}), 500

    # ✅ Hash password and store user
    hashed_password = bcrypt.hash(password)
    try:
        users_table.put_item(Item={
            'username': username,
            'password': hashed_password,
            'role': role
        })
        logging.info(f"User '{username}' registered successfully with role '{role}'")
        return jsonify({"message": "✅ User registered successfully"}), 201
    except Exception as e:
        logging.error(f"Failed to store user '{username}': {str(e)}")
        return jsonify({"error": f"Failed to store user: {str(e)}"}), 500

# ✅ LOGIN
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        logging.warning("Login failed: Missing username or password")
        return jsonify({"error": "Username and password required"}), 400

    try:
        response = users_table.get_item(Key={'username': username})
        user = response.get('Item')

        if not user or not bcrypt.verify(password, user['password']):
            logging.warning(f"Login failed for '{username}': Invalid credentials")
            return jsonify({"error": "Invalid username or password"}), 401

        access_token = create_access_token(
            identity=username,
            additional_claims={"role": user["role"]}
        )
        logging.info(f"User '{username}' logged in successfully as '{user['role']}'")
        return jsonify({
            "message": "✅ Login successful",
            "token": access_token,
            "role": user["role"]
        }), 200

    except Exception as e:
        logging.error(f"Login failed for '{username}': {str(e)}")
        return jsonify({"error": f"Login failed: {str(e)}"}), 500
