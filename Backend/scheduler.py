# app/services/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from app.services.db import delivery_partners_table, orders_table
from boto3.dynamodb.conditions import Attr

def reset_delivery_partners():
    try:
        response = delivery_partners_table.scan(
            FilterExpression=Attr("status").eq("busy")
        )
        busy_partners = response.get("Items", [])

        for partner in busy_partners:
            partner_id = partner["partner_id"]
            delivery_end = partner.get("delivery_end_time")
            if not delivery_end or delivery_end == "-":
                continue

            # Convert ISO string to datetime
            end_time = datetime.fromisoformat(delivery_end)
            now = datetime.utcnow()

            if now >= end_time:
                print(f"🕒 Resetting delivery partner: {partner_id}")

                # Update delivery partner to idle
                delivery_partners_table.update_item(
                    Key={"partner_id": partner_id},
                    UpdateExpression="SET #s = :s, current_order_id = :o, delivery_end_time = :e",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={
                        ":s": "idle",
                        ":o": "-",
                        ":e": "-"
                    }
                )

                # Also update the order status to 'delivered'
                order_id = partner.get("current_order_id")
                if order_id and order_id != "-":
                    orders_table.update_item(
                        Key={"order_id": order_id},
                        UpdateExpression="SET delivery_status = :ds",
                        ExpressionAttributeValues={":ds": "delivered"}
                    )
    except Exception as e:
        print(f"❌ Error during delivery partner reset: {e}")

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(reset_delivery_partners, "interval", minutes=1)
    scheduler.start()
    print("✅ Delivery partner reset scheduler started")
