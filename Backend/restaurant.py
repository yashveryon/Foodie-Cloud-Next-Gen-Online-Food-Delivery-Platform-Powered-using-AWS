from flask import Blueprint, request, jsonify, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.db import menus_table, orders_table, restaurants_table, delivery_partners_table
from app.utils.role_utils import role_required
from boto3.dynamodb.conditions import Attr
import uuid
import os
import logging
import random
from datetime import datetime, timedelta
import threading

restaurant_bp = Blueprint('restaurant', __name__)

STATIC_FOLDER = os.path.join("app", "static", "uploads")
os.makedirs(STATIC_FOLDER, exist_ok=True)

# ✅ PATCH: Restaurant profile update
@restaurant_bp.route("/profile", methods=["PATCH"])
@jwt_required()
@role_required("restaurant")
def update_restaurant_profile():
    try:
        restaurant_id = get_jwt_identity()
        data = request.get_json()

        if not data:
            logging.error("❌ No data received in PATCH /profile")
            return jsonify({"error": "No input data provided"}), 400

        logging.info(f"📦 Incoming profile update for {restaurant_id}: {data}")

        update_expr = []
        attr_names = {}
        attr_vals = {}

        for key, value in data.items():
            actual_key = "logo_url" if key == "logo" else key
            update_expr.append(f"#attr_{actual_key} = :val_{key}")
            attr_names[f"#attr_{actual_key}"] = actual_key
            attr_vals[f":val_{key}"] = value

        restaurants_table.update_item(
            Key={"restaurant_id": restaurant_id},
            UpdateExpression="SET " + ", ".join(update_expr),
            ExpressionAttributeNames=attr_names,
            ExpressionAttributeValues=attr_vals
        )

        logging.info(f"✅ Profile updated for {restaurant_id}")
        return jsonify({"message": "✅ Profile updated"}), 200

    except Exception as e:
        logging.exception("❌ Exception during profile update")
        return jsonify({"error": str(e)}), 500

# ✅ Fetch all restaurants
@restaurant_bp.route("/restaurants", methods=["GET"])
@jwt_required()
@role_required(["restaurant", "customer"])
def get_all_restaurants():
    try:
        response = restaurants_table.scan()
        items = response.get("Items", [])
        valid_restaurants = [r for r in items if "restaurant_id" in r and "name" in r]
        return jsonify(valid_restaurants), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Add menu item
@restaurant_bp.route("/menu", methods=["POST"])
@jwt_required()
@role_required("restaurant")
def add_menu_item():
    try:
        data = request.get_json()
        required_fields = ["restaurant_id", "name", "image_url", "prep_time", "price_small", "price_medium", "price_large"]
        if not all(k in data for k in required_fields):
            return jsonify({"error": f"Missing fields. Required: {required_fields}"}), 400

        data["menu_id"] = str(uuid.uuid4())
        data["created_by"] = get_jwt_identity()
        data["is_available"] = True

        menus_table.put_item(Item=data)
        return jsonify({"message": "✅ Menu item added", "menu_id": data["menu_id"]}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Get menu for a restaurant
@restaurant_bp.route("/menu/<restaurant_id>", methods=["GET"])
def get_menu(restaurant_id):
    try:
        response = menus_table.scan(FilterExpression=Attr("restaurant_id").eq(restaurant_id))
        return jsonify(response.get("Items", [])), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Update menu item
@restaurant_bp.route("/menu/<menu_id>", methods=["PUT"])
@jwt_required()
@role_required("restaurant")
def update_menu_item(menu_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        expr = []
        expr_names = {}
        expr_values = {}
        for key, value in data.items():
            expr.append(f"#attr_{key} = :val_{key}")
            expr_names[f"#attr_{key}"] = key
            expr_values[f":val_{key}"] = value

        menus_table.update_item(
            Key={'menu_id': menu_id},
            UpdateExpression="SET " + ", ".join(expr),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values
        )
        return jsonify({"message": f"✅ Menu item '{menu_id}' updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Delete menu item
@restaurant_bp.route("/menu/<menu_id>", methods=["DELETE"])
@jwt_required()
@role_required("restaurant")
def delete_menu_item(menu_id):
    try:
        menus_table.delete_item(Key={"menu_id": menu_id})
        return jsonify({"message": f"🗑️ Menu item '{menu_id}' deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Toggle availability
@restaurant_bp.route("/menu/<menu_id>/availability", methods=["PATCH"])
@jwt_required()
@role_required("restaurant")
def toggle_menu_item_availability(menu_id):
    try:
        data = request.get_json()
        if "is_available" not in data:
            return jsonify({"error": "Missing 'is_available' field"}), 400

        menus_table.update_item(
            Key={"menu_id": menu_id},
            UpdateExpression="SET is_available = :val",
            ExpressionAttributeValues={":val": data["is_available"]}
        )
        return jsonify({"message": "Availability updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ View orders for restaurant
@restaurant_bp.route("/orders", methods=["GET"])
@jwt_required()
@role_required("restaurant")
def view_orders():
    try:
        restaurant_id = request.args.get("restaurant_id")
        if not restaurant_id:
            return jsonify({"error": "Missing restaurant_id in query parameters"}), 400

        response = orders_table.scan(FilterExpression=Attr("restaurant_id").eq(restaurant_id))
        orders = response.get("Items", [])

        menu_res = menus_table.scan(FilterExpression=Attr("restaurant_id").eq(restaurant_id))
        menu_lookup = {item["name"].lower(): item for item in menu_res.get("Items", [])}

        total_earnings = 0
        for order in orders:
            total_price = 0
            for item in order.get("items", []):
                name = item.get("name", "").lower()
                size = item.get("size", "").lower()
                qty = int(item.get("quantity", 0))
                price = float(menu_lookup.get(name, {}).get(f"price_{size}", 0))
                total_price += price * qty

            order["total_price"] = total_price
            if order.get("status") in ["accepted", "ready", "delivered"]:
                total_earnings += total_price

        return jsonify({"orders": orders, "total_earnings": total_earnings}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Update order status (now with auto-assign delivery)
@restaurant_bp.route("/order/<order_id>", methods=["PUT"])
@jwt_required()
@role_required("restaurant")
def update_order(order_id):
    try:
        data = request.get_json()
        new_status = data.get("status")
        if not new_status:
            return jsonify({"error": "Status not provided"}), 400

        restaurant_id = get_jwt_identity()
        update_expr = "SET #s = :s, updated_by = :u"
        attr_names = {"#s": "status"}
        attr_vals = {":s": new_status, ":u": restaurant_id}

        if new_status == "rejected":
            update_expr += ", reason = :r"
            attr_vals[":r"] = "We're sorry, but your order was politely declined by the restaurant due to availability or operational constraints."

        orders_table.update_item(
            Key={"order_id": order_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=attr_names,
            ExpressionAttributeValues=attr_vals
        )

        if new_status == "ready":
            response = delivery_partners_table.scan(FilterExpression=Attr("status").eq("idle"))
            idle_partners = response.get("Items", [])

            if idle_partners:
                partner = idle_partners[0]
                eta = random.randint(3, 10)
                delivery_start_time = datetime.utcnow()
                delivery_end_time = delivery_start_time + timedelta(minutes=eta)

                delivery_partners_table.update_item(
                    Key={"partner_id": partner["partner_id"]},
                    UpdateExpression="SET #s = :s, current_order_id = :o, delivery_end_time = :e",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={":s": "busy", ":o": order_id, ":e": delivery_end_time.isoformat()}
                )

                orders_table.update_item(
                    Key={"order_id": order_id},
                    UpdateExpression="SET delivery_partner_id = :pid, delivery_partner_name = :pname, eta_minutes = :eta, delivery_status = :ds, delivery_start_time = :start, delivery_end_time = :end",
                    ExpressionAttributeValues={
                        ":pid": partner["partner_id"],
                        ":pname": partner["name"],
                        ":eta": eta,
                        ":ds": "assigned",
                        ":start": delivery_start_time.isoformat(),
                        ":end": delivery_end_time.isoformat()
                    }
                )

        return jsonify({"message": f"✅ Order '{order_id}' updated to '{new_status}'"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Test route
@restaurant_bp.route("/test", methods=["GET"])
@jwt_required()
@role_required("restaurant")
def test_restaurant():
    username = get_jwt_identity()
    return jsonify({"message": f"✅ Auth success for restaurant '{username}'"}), 200

# ✅ Upload image
@restaurant_bp.route("/upload-image", methods=["POST"])
@jwt_required()
@role_required("restaurant")
def upload_image():
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No image file provided"}), 400

        image = request.files['image']
        filename = f"{uuid.uuid4().hex}_{image.filename}"
        filepath = os.path.join(STATIC_FOLDER, filename)
        image.save(filepath)

        image_url = f"/static/uploads/{filename}"
        return jsonify({"image_url": image_url}), 200
    except Exception as e:
        return jsonify({"error": "Image upload failed"}), 500

# ✅ Serve image
@restaurant_bp.route("/static/uploads/<filename>")
def serve_uploaded_image(filename):
    return send_from_directory(STATIC_FOLDER, filename)
