from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.db import orders_table, menus_table
from app.utils.role_utils import role_required
from boto3.dynamodb.conditions import Key, Attr
from datetime import datetime
import uuid
import logging

order_bp = Blueprint("order", __name__)

# ✅ Get all orders for a restaurant
@order_bp.route("/restaurant/orders", methods=["GET"])
@jwt_required()
@role_required("restaurant")
def get_orders_for_restaurant():
    restaurant_id = request.args.get("restaurant_id")
    if not restaurant_id:
        return jsonify({"error": "Missing restaurant_id"}), 400

    result = orders_table.scan(
        FilterExpression=Attr("restaurant_id").eq(restaurant_id)
    )
    orders = result.get("Items", [])
    sorted_orders = sorted(orders, key=lambda x: x.get("order_time", ""), reverse=True)
    return jsonify({"orders": sorted_orders}), 200

# ✅ Update order status (Accept, Reject, Ready, Delivered, etc.)
@order_bp.route("/restaurant/order/<order_id>", methods=["PUT"])
@jwt_required()
@role_required("restaurant")
def update_order_status(order_id):
    data = request.get_json()
    new_status = data.get("status")

    if new_status not in ["accepted", "in_process", "ready", "delivered", "rejected"]:
        return jsonify({"error": "Invalid status"}), 400

    try:
        orders_table.update_item(
            Key={"order_id": order_id},
            UpdateExpression="SET #s = :status",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":status": new_status}
        )
        return jsonify({"message": f"Order {order_id} status updated to {new_status}"}), 200
    except Exception as e:
        logging.error(f"❗ Error updating order status: {str(e)}")
        return jsonify({"error": "Failed to update order status"}), 500

# ✅ (Optional) You can also add PATCH endpoint for partial updates or future extensions
# For example, assign delivery agent or set estimated delivery time, etc.
