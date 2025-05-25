from datetime import datetime
import pytz  
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt, decode_token
)
from app import db, bcrypt, jwt
from app.models import User, TokenBlocklist, UserToken

auth_bp = Blueprint("auth", __name__)
IST = pytz.timezone("Asia/Kolkata")

@jwt.additional_claims_loader
def add_claims_to_access_token(identity):
    user = User.query.get(identity)
    return {"role": user.role} if user else {}

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    required_fields = ["username", "email", "password", "role"]

    if not data or not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    if data["role"] not in {"Owner", "Editor", "Viewer"}:
        return jsonify({"error": "Invalid role"}), 400

    if not data["email"].strip() or not data["password"].strip():
        return jsonify({"error": "Email and password required"}), 400

    existing = User.query.filter(
        (User.username == data["username"]) | (User.email == data["email"])
    ).first()
    if existing:
        return jsonify({"error": "User already exists"}), 409

    hashed_pw = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    user = User(username=data["username"], email=data["email"], password=hashed_pw, role=data["role"])
    db.session.add(user)
    db.session.commit()

    return _generate_token_response(user), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"error": "Missing email or password"}), 400

    user = User.query.filter(
        (User.username == data.get("username")) | (User.email == data.get("email"))
    ).first()

    if not user or not bcrypt.check_password_hash(user.password, data["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    return _generate_token_response(user)

def _generate_token_response(user):
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    access_decoded = decode_token(access_token)
    refresh_decoded = decode_token(refresh_token)

    access_expires = datetime.fromtimestamp(access_decoded['exp'], tz=IST)
    refresh_expires = datetime.fromtimestamp(refresh_decoded['exp'], tz=IST)

    UserToken.query.filter_by(user_id=user.id).delete()
    db.session.add(UserToken(
        user_id=user.id,
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_at=access_expires,
        refresh_expires_at=refresh_expires
    ))
    db.session.commit()

    return jsonify({
        "user": {"id": user.id, "username": user.username, "email": user.email, "role": user.role},
        "access_token": access_token,
        "refresh_token": refresh_token
    })

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    user_id = int(get_jwt_identity())
    return jsonify(access_token=create_access_token(identity=user_id)), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required(refresh=True)
def logout():
    try:
        jti = get_jwt()["jti"]  
        user_id = get_jwt_identity()

        token = TokenBlocklist(
            jti=jti,
            user_id=user_id,
            access_token="",
            refresh_token="",
            access_expires_at=datetime.utcnow(),
            refresh_expires_at=datetime.utcnow()
        )

        db.session.add(token)
        db.session.commit()

        return jsonify({"msg": "Logout successful"}), 200

    except Exception as e:
        return jsonify({"error": f"Logout failed: {str(e)}"}), 400
@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    jti = jwt_payload["jti"]

    if TokenBlocklist.query.filter_by(jti=jti).first():
        return True 
    return False 
