from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.role_utils import role_required
from app.services.db import users_table, orders_table
import logging

admin_bp = Blueprint("admin", __name__)

# ✅ Get all users
@admin_bp.route("/users", methods=["GET"])
@jwt_required()
@role_required("admin")
def get_all_users():
    admin = get_jwt_identity()
    try:
        response = users_table.scan()
        logging.info(f"👤 Admin '{admin}' viewed all users.")
        return jsonify(response.get("Items", [])), 200
    except Exception as e:
        logging.error(f"❌ Admin '{admin}' failed to fetch users: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ✅ Get all orders
@admin_bp.route("/orders", methods=["GET"])
@jwt_required()
@role_required("admin")
def get_all_orders():
    admin = get_jwt_identity()
    try:
        response = orders_table.scan()
        logging.info(f"📦 Admin '{admin}' viewed all orders.")
        return jsonify(response.get("Items", [])), 200
    except Exception as e:
        logging.error(f"❌ Admin '{admin}' failed to fetch orders: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ✅ Delete a user by username
@admin_bp.route("/user/<username>", methods=["DELETE"])
@jwt_required()
@role_required("admin")
def delete_user(username):
    admin = get_jwt_identity()
    try:
        users_table.delete_item(Key={"username": username})
        logging.info(f"🗑️ Admin '{admin}' deleted user '{username}'.")
        return jsonify({"message": f"🗑️ User '{username}' deleted successfully"}), 200
    except Exception as e:
        logging.error(f"❌ Admin '{admin}' failed to delete user '{username}': {str(e)}")
        return jsonify({"error": str(e)}), 500

# ✅ Delete an order by order_id
@admin_bp.route("/order/<order_id>", methods=["DELETE"])
@jwt_required()
@role_required("admin")
def delete_order(order_id):
    admin = get_jwt_identity()
    try:
        orders_table.delete_item(Key={"order_id": order_id})
        logging.info(f"🗑️ Admin '{admin}' deleted order '{order_id}'.")
        return jsonify({"message": f"🗑️ Order '{order_id}' deleted successfully"}), 200
    except Exception as e:
        logging.error(f"❌ Admin '{admin}' failed to delete order '{order_id}': {str(e)}")
        return jsonify({"error": str(e)}), 500

# ✅ Admin test route
@admin_bp.route("/test", methods=["GET"])
@jwt_required()
@role_required("admin")
def test_admin():
    admin = get_jwt_identity()
    logging.info(f"🛡️ Admin test route accessed by '{admin}'.")
    return jsonify({"message": "✅ Admin route access confirmed!"}), 200
