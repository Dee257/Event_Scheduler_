from flask import Blueprint, request, jsonify
from app.models import Event, EventPermission, db
from flask_jwt_extended import jwt_required, get_jwt_identity

collab_bp = Blueprint("collaboration", __name__)

@collab_bp.route('/events/<int:event_id>/permissions', methods=['GET'])
@jwt_required()
def list_permissions(event_id):
    perms = EventPermission.query.filter_by(event_id=event_id).all()
    return jsonify([{"user_id": p.user_id, "role": p.role} for p in perms]), 200

@collab_bp.route('/events/<int:event_id>/permissions/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_permission(event_id, user_id):
    data = request.json
    role = data['role']
    perm = EventPermission.query.filter_by(event_id=event_id, user_id=user_id).first_or_404()
    perm.role = role
    db.session.commit()
    return jsonify({"message": "Permission updated."}), 200

@collab_bp.route('/events/<int:event_id>/permissions/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_permission(event_id, user_id):
    if Event.owner_id != user_id:
        return jsonify({"error": "Only the owner can delete the event"}), 403


    perm = EventPermission.query.filter_by(event_id=event_id, user_id=user_id).first_or_404()
    db.session.delete(perm)
    db.session.commit()
    return jsonify({"message": "Permission removed."}), 200
