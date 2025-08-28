import boto3

# ✅ Auto-authentication using EC2 IAM Role (or local AWS CLI config)
dynamodb = boto3.resource('dynamodb', region_name='eu-north-1')

# ✅ DynamoDB Table References
orders_table = dynamodb.Table('Orders')              # Stores all order info
users_table = dynamodb.Table('Users')                # Stores registered users
menus_table = dynamodb.Table('Menus')                # Stores food menu items
restaurants_table = dynamodb.Table('Restaurants')    # Stores restaurant profiles
delivery_partners_table = dynamodb.Table('DeliveryTable')  # ✅ Delivery partner assignment table

# ✅ SNS Client for real-time notifications (e.g., order alerts to delivery)
sns = boto3.client('sns', region_name='eu-north-1')
