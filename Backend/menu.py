from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.db import menus_table
from app.utils.role_utils import role_required
from boto3.dynamodb.conditions import Key
import uuid

menu_bp = Blueprint("menu", __name__)

# ✅ Create menu item
@menu_bp.route("/restaurant/menu", methods=["POST"])
@jwt_required()
@role_required("restaurant")
def create_menu_item():
    data = request.get_json()
    required_fields = ["name", "price_small", "price_medium", "price_large", "prep_time", "restaurant_id", "image_url"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing fields"}), 400

    item = {
        "menu_id": str(uuid.uuid4()),
        "restaurant_id": data["restaurant_id"],
        "name": data["name"],
        "price_small": data["price_small"],
        "price_medium": data["price_medium"],
        "price_large": data["price_large"],
        "prep_time": data["prep_time"],
        "image_url": data["image_url"],
        "is_available": True
    }

    menus_table.put_item(Item=item)
    return jsonify({"message": "Menu item created", "menu_id": item["menu_id"]}), 201

# ✅ Get all menu items for a restaurant
@menu_bp.route("/restaurant/menu/<restaurant_id>", methods=["GET"])
@jwt_required()
@role_required("restaurant")
def get_menu_items(restaurant_id):
    res = menus_table.query(
        IndexName="restaurant_id-index",
        KeyConditionExpression=Key("restaurant_id").eq(restaurant_id)
    )
    return jsonify(res.get("Items", [])), 200

# ✅ Update a menu item
@menu_bp.route("/restaurant/menu/<menu_id>", methods=["PUT"])
@jwt_required()
@role_required("restaurant")
def update_menu_item(menu_id):
    data = request.get_json()
    update_fields = ["name", "price_small", "price_medium", "price_large", "prep_time", "image_url"]

    expression = []
    values = {}
    for field in update_fields:
        if field in data:
            expression.append(f"{field} = :{field}")
            values[f":{field}"] = data[field]

    if not expression:
        return jsonify({"error": "No valid fields to update"}), 400

    menus_table.update_item(
        Key={"menu_id": menu_id},
        UpdateExpression="SET " + ", ".join(expression),
        ExpressionAttributeValues=values
    )

    return jsonify({"message": "Menu item updated"}), 200

# ✅ Delete a menu item
@menu_bp.route("/restaurant/menu/<menu_id>", methods=["DELETE"])
@jwt_required()
@role_required("restaurant")
def delete_menu_item(menu_id):
    menus_table.delete_item(Key={"menu_id": menu_id})
    return jsonify({"message": "Menu item deleted"}), 200

# ✅ Toggle availability
@menu_bp.route("/restaurant/menu/<menu_id>/availability", methods=["PATCH"])
@jwt_required()
@role_required("restaurant")
def toggle_availability(menu_id):
    data = request.get_json()
    if "is_available" not in data:
        return jsonify({"error": "Missing 'is_available' field"}), 400

    menus_table.update_item(
        Key={"menu_id": menu_id},
        UpdateExpression="SET is_available = :val",
        ExpressionAttributeValues={":val": data["is_available"]}
    )

    return jsonify({"message": "Availability updated"}), 200
