from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import EventVersion, Event, User
from app import db
from datetime import datetime
import pytz
from sqlalchemy import func

version_bp = Blueprint("version", __name__)
IST = pytz.timezone("Asia/Kolkata")

def get_next_version_id(event_id):
    max_version = db.session.query(func.max(EventVersion.version_id)).filter_by(event_id=event_id).scalar()
    if max_version is None:
        return 1
    else:
        return max_version + 1
    
def save_event_version(event, user_id):
    last_version = EventVersion.query.filter_by(event_id=event.id).order_by(EventVersion.version_number.desc()).first()
    version_number = last_version.version_number + 1 if last_version else 1

    data_snapshot = {
        "title": event.title,
        "description": event.description,
        "start_time": event.start_time.isoformat() if event.start_time else None,
        "end_time": event.end_time.isoformat() if event.end_time else None,
        "location": event.location,
        "is_recurring": event.is_recurring,
        "recurrence_pattern": event.recurrence_pattern,
        "modified_at": datetime.now(IST).isoformat()
    }

    new_version_id = get_next_version_id(event.id)
    
    version = EventVersion(
        event_id=event.id,
        version_number=version_number,
        data=data_snapshot,
        modified_by=user_id,
        version_id=new_version_id,
        updated_by=user_id
    )
    db.session.add(version)
    db.session.commit()


@version_bp.route("/events/<int:event_id>/versions", methods=["GET"])
@jwt_required()
def list_event_versions(event_id):
    user_id = int(get_jwt_identity())
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404

   
        return jsonify({"error": "Permission denied"}), 403

    versions = EventVersion.query.filter_by(event_id=event_id).order_by(EventVersion.created_at.desc()).all()
    result = []
    for v in versions:
        user = User.query.get(v.modified_by)
        result.append({
            "version_id": v.id,
            "version_number": v.version_number,
            **v.data,
            "modified_by": user.username if user else "Unknown",
            "created_at": v.created_at.isoformat()
        })

    return jsonify(result), 200

@version_bp.route("/events/<int:event_id>/history/<int:version_id>", methods=["GET"])
@jwt_required()
def get_event_version(event_id, version_id):
    user_id = int(get_jwt_identity())

    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404

        return jsonify({"error": "Permission denied"}), 403

    version = EventVersion.query.filter_by(event_id=event_id, version_id=version_id).first()
    if not version:
        return jsonify({"error": "Version not found"}), 404

    user = User.query.get(version.modified_by)
    response = {
        "version_id": version.version_id,
        "version_number": version.version_number,
        **version.data,
        "modified_by": user.username if user else "Unknown",
        "created_at": version.created_at.isoformat()
    }

    return jsonify(response), 200



@version_bp.route("/events/<int:event_id>/rollback/<int:version_id>", methods=["POST"])
@jwt_required()
def rollback_event(event_id, version_id):
    user_id = int(get_jwt_identity())
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404

    if event.owner_id != user_id and not any(
        perm.user_id == user_id and perm.role == "Editor" for perm in event.permissions
    ):
        return jsonify({"error": "Permission denied"}), 403

    version = EventVersion.query.filter_by(version_id=version_id, event_id=event_id).first()
    if not version:
        return jsonify({"error": "Version not found"}), 404

    data = version.data
    event.title = data.get("title")
    event.description = data.get("description")
    event.start_time = datetime.fromisoformat(data["start_time"]) if data.get("start_time") else None
    event.end_time = datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None
    event.location = data.get("location")
    event.is_recurring = data.get("is_recurring")
    event.recurrence_pattern = data.get("recurrence_pattern")

    db.session.commit()
    save_event_version(event, user_id)

    return jsonify({"msg": f"Rolled back to version {version_id}"}), 200
