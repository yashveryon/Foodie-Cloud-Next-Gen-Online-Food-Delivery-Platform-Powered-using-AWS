from flask_jwt_extended import verify_jwt_in_request, get_jwt
from functools import wraps
from flask import jsonify

def role_required(allowed_roles):
    """
    Custom decorator to enforce role-based access control.
    Accepts a single role string or a list of allowed roles.

    Examples:
        @role_required("customer")
        @role_required(["customer", "restaurant"])
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]  # convert to list if passed as string

    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            try:
                verify_jwt_in_request()
                claims = get_jwt()
                user_role = claims.get("role")

                if user_role not in allowed_roles:
                    return jsonify({
                        "error": f"❌ Access denied. Role '{user_role}' not permitted."
                    }), 403

                return fn(*args, **kwargs)

            except Exception as e:
                return jsonify({"error": f"Role verification failed: {str(e)}"}), 403

        return decorator
    return wrapper
