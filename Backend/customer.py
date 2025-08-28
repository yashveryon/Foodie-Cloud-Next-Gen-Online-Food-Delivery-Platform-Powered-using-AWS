from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.db import orders_table, menus_table, restaurants_table, sns
from app.utils.role_utils import role_required
from boto3.dynamodb.conditions import Attr
from datetime import datetime
import uuid
import logging

customer_bp = Blueprint('customer', __name__)

# ✅ Get all restaurants
@customer_bp.route("/restaurants", methods=["GET"])
@jwt_required()
@role_required("customer")
def get_restaurants():
    try:
        response = restaurants_table.scan()
        restaurants = response.get("Items", [])
        logging.info(f"📍 Total restaurants fetched: {len(restaurants)}")
        return jsonify({"restaurants": restaurants}), 200
    except Exception as e:
        logging.error(f"❌ Failed to fetch restaurants: {str(e)}")
        return jsonify({"error": "Failed to retrieve restaurants"}), 500

# ✅ Get menu of a selected restaurant
@customer_bp.route("/menu/<restaurant_id>", methods=["GET"])
@jwt_required()
@role_required("customer")
def get_menu_by_restaurant(restaurant_id):
    try:
        response = menus_table.scan(
            FilterExpression=Attr("restaurant_id").eq(restaurant_id)
        )
        menu = response.get("Items", [])
        logging.info(f"🍽️ Menu fetched for restaurant_id={restaurant_id} → {len(menu)} items")
        return jsonify({"menu": menu}), 200
    except Exception as e:
        logging.error(f"❌ Failed to fetch menu for restaurant {restaurant_id}: {str(e)}")
        return jsonify({"error": "Failed to retrieve menu"}), 500

# ✅ Create new order (includes customer details and unique ID)
@customer_bp.route("/order", methods=["POST"])
@jwt_required()
@role_required("customer")
def create_order():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing order data"}), 400

        required_fields = {"restaurant_id", "items", "customer_name", "customer_email", "customer_contact", "unique_customer_id"}
        if not required_fields.issubset(data):
            return jsonify({"error": "Missing required fields"}), 400

        restaurant_id = data["restaurant_id"]
        items = data["items"]
        customer_id = get_jwt_identity()

        customer_name = data["customer_name"]
        customer_email = data["customer_email"]
        customer_contact = data["customer_contact"]
        unique_id = data["unique_customer_id"]

        logging.info(f"📨 Creating order for restaurant_id={restaurant_id} by '{customer_id}'")

        menu_response = menus_table.scan(
            FilterExpression=Attr("restaurant_id").eq(restaurant_id)
        )
        menu_items = menu_response.get("Items", [])

        menu_dict = {item["name"].lower(): item for item in menu_items}

        order_items = []
        for i in items:
            name = i.get("name", "").lower()
            size = i.get("size", "").lower()
            quantity = int(i.get("quantity", 1))

            if name not in menu_dict or size not in ["small", "medium", "large"]:
                return jsonify({"error": f"Invalid item: {i}"}), 400

            menu_item = menu_dict[name]
            order_items.append({
                "name": menu_item["name"],
                "menu_id": menu_item["menu_id"],
                "size": size,
                "quantity": quantity,
                "price_small": menu_item.get("price_small", "0"),
                "price_medium": menu_item.get("price_medium", "0"),
                "price_large": menu_item.get("price_large", "0"),
                "prep_time": menu_item.get("prep_time", "1")
            })

        order_id = str(uuid.uuid4())
        order_time = datetime.utcnow().isoformat()

        order_data = {
            "order_id": order_id,
            "unique_customer_id": unique_id,
            "customer": customer_id,
            "restaurant_id": restaurant_id,
            "items": order_items,
            "status": "pending",
            "order_time": order_time,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_contact": customer_contact
        }

        orders_table.put_item(Item=order_data)
        logging.info(f"🛒 Order placed by '{customer_id}' → Order ID: {order_id}")

        sns.publish(
            TopicArn="arn:aws:sns:eu-north-1:075664900901:RestaurantAlert",
            Message=f"🛒 New order from {customer_name}\nOrder ID: {unique_id}",
            Subject="New Food Order Placed"
        )

        return jsonify({"message": "✅ Order placed successfully", "order_id": unique_id}), 201

    except Exception as e:
        logging.error(f"❌ Failed to place order: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ✅ View customer's own orders
@customer_bp.route("/orders", methods=["GET"])
@jwt_required()
@role_required("customer")
def get_orders():
    try:
        username = get_jwt_identity()
        response = orders_table.scan(
            FilterExpression=Attr("customer").eq(username)
        )
        orders = response.get("Items", [])
        for order in orders:
            order.setdefault("delivery_partner_name", None)
            order.setdefault("delivery_partner_id", None)
            order.setdefault("eta_minutes", None)
            order.setdefault("delivery_status", order.get("status"))
        return jsonify({"orders": orders}), 200
    except Exception as e:
        logging.error(f"❌ Error retrieving orders for '{username}': {str(e)}")
        return jsonify({"error": str(e)}), 500

# ✅ Cancel order before accepted
@customer_bp.route("/order/<order_id>/cancel", methods=["PATCH"])
@jwt_required()
@role_required("customer")
def cancel_order(order_id):
    try:
        username = get_jwt_identity()
        response = orders_table.scan(
            FilterExpression=Attr("order_id").eq(order_id) & Attr("customer").eq(username)
        )
        items = response.get("Items", [])
        if not items:
            return jsonify({"error": "Order not found or unauthorized"}), 404

        order = items[0]
        if order["status"] != "pending":
            return jsonify({"error": "Order can only be cancelled while pending."}), 400

        orders_table.update_item(
            Key={"order_id": order_id},
            UpdateExpression="SET #s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "cancelled"}
        )

        logging.info(f"❌ Order '{order_id}' cancelled by '{username}'")
        return jsonify({"message": f"Order '{order_id}' cancelled."}), 200

    except Exception as e:
        logging.error(f"❌ Failed to cancel order: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ✅ Test route
@customer_bp.route("/test", methods=["GET"])
@jwt_required()
@role_required("customer")
def test_customer():
    username = get_jwt_identity()
    return jsonify({"message": f"✅ Customer route access confirmed for '{username}'"}), 200
