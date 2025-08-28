from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.db import orders_table, delivery_partners_table
from app.utils.role_utils import role_required
from boto3.dynamodb.conditions import Attr
from datetime import datetime
import threading
import logging

delivery_bp = Blueprint('delivery', __name__)

# ✅ Test route
@delivery_bp.route("/test", methods=["GET"])
@jwt_required()
@role_required("delivery")
def test_delivery():
    username = get_jwt_identity()
    logging.info(f"✅ Test route accessed by delivery personnel '{username}'")
    return jsonify({"message": "✅ Delivery route access confirmed!"}), 200

# ✅ Get specific order info (open access)
@delivery_bp.route("/order/<order_id>", methods=["GET"])
def get_order(order_id):
    try:
        res = orders_table.get_item(Key={"order_id": order_id})
        order = res.get("Item")
        if not order:
            return jsonify({"error": "❌ Order not found"}), 404
        return jsonify(order), 200
    except Exception as e:
        logging.error(f"❌ Error fetching order '{order_id}': {str(e)}")
        return jsonify({"error": str(e)}), 500

# ✅ Update order delivery status
@delivery_bp.route("/order/<order_id>", methods=["PATCH"])
@jwt_required()
@role_required("delivery")
def update_delivery_status(order_id):
    try:
        status = request.json.get("status")
        if not status:
            return jsonify({"error": "Missing 'status'"}), 400

        username = get_jwt_identity()

        update_expr = "SET #s = :s, updated_by = :u"
        attr_names = {"#s": "status"}
        attr_values = {":s": status, ":u": username}

        if status == "delivered":
            now = datetime.utcnow().isoformat()
            update_expr += ", delivered_at = :t"
            attr_values[":t"] = now

        orders_table.update_item(
            Key={"order_id": order_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=attr_names,
            ExpressionAttributeValues=attr_values
        )

        logging.info(f"🚚 Order '{order_id}' updated to '{status}' by '{username}'")
        return jsonify({"message": f"✅ Order status updated to '{status}'"}), 200
    except Exception as e:
        logging.error(f"❌ Error updating order '{order_id}': {str(e)}")
        return jsonify({"error": str(e)}), 500

# ✅ Fetch all 'ready' orders assigned to current delivery partner
@delivery_bp.route("/ready", methods=["GET"])
@jwt_required()
@role_required("delivery")
def get_ready_orders():
    try:
        username = get_jwt_identity()
        res = orders_table.scan(
            FilterExpression=Attr("status").eq("ready") & Attr("delivery_partner_name").eq(username)
        )
        items = res.get("Items", [])
        logging.info(f"📦 Ready orders for '{username}': {len(items)}")
        return jsonify(items), 200
    except Exception as e:
        logging.error(f"❌ Error fetching ready orders: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ✅ Fetch completed deliveries
@delivery_bp.route("/completed", methods=["GET"])
@jwt_required()
@role_required("delivery")
def get_completed_deliveries():
    try:
        username = get_jwt_identity()
        res = orders_table.scan(
            FilterExpression=Attr("status").eq("delivered") & Attr("delivery_partner_name").eq(username)
        )
        items = res.get("Items", [])
        logging.info(f"📦 Completed deliveries for '{username}': {len(items)}")
        return jsonify(items), 200
    except Exception as e:
        logging.error(f"❌ Error fetching completed deliveries: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ✅ Fetch all delivery partners
@delivery_bp.route("/partners", methods=["GET"])
@jwt_required()
@role_required("delivery")
def get_all_partners():
    try:
        res = delivery_partners_table.scan()
        items = res.get("Items", [])
        return jsonify(items), 200
    except Exception as e:
        logging.error(f"❌ Error fetching delivery partners: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ✅ Background task to auto-mark delivery as completed
def schedule_auto_delivery_completion(order_id, partner_id, eta_minutes):
    def mark_as_delivered():
        try:
            now = datetime.utcnow().isoformat()

            # ✅ Update order as delivered
            orders_table.update_item(
                Key={"order_id": order_id},
                UpdateExpression="SET #s = :s, delivered_at = :t",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": "delivered", ":t": now}
            )

            # ✅ Reset delivery partner to idle
            delivery_partners_table.update_item(
                Key={"partner_id": partner_id},
                UpdateExpression="SET #s = :s REMOVE current_order_id, delivery_end_time",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": "idle"}
            )

            logging.info(f"✅ Order '{order_id}' auto-delivered. Partner '{partner_id}' set to idle.")

        except Exception as e:
            logging.error(f"❌ Auto-completion failed for '{order_id}': {str(e)}")

    threading.Timer(eta_minutes * 60, mark_as_delivered).start()