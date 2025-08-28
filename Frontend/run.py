from app import create_app
from flask_cors import CORS
from app.services.scheduler import start_scheduler  # ✅ Added this line

print("🚀 run.py started")  # Debug log

app = create_app()

# ✅ Enable CORS for all origins (frontend access from localhost:5173)
CORS(app, supports_credentials=True)

# ✅ Start background scheduler
start_scheduler()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",     # Required for public EC2 access
        port=5050,          # Make sure port 5050 is open in AWS security group
        debug=True          # Enable auto-reload and logging
    )
