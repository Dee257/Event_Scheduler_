from flask import Blueprint, json, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import pytz
from app import db
from app.models import Event, EventPermission, EventVersion, User
from datetime import datetime
from sqlalchemy import or_

from app.routes.versioning import save_event_version

events_bp = Blueprint("events", __name__)

IST = pytz.timezone("Asia/Kolkata")

def parse_datetime(dt_str):
    try:
        return IST.localize(datetime.fromisoformat(dt_str))
    except Exception:
        return None

def emit_event(event_type, event_data):
    
    print(f"Emitted event: {event_type} with data: {event_data}")

def check_user_role(event, user_id):
    if event.owner_id == user_id:
        return "Owner"
    perm = EventPermission.query.filter_by(event_id=event.id, user_id=user_id).first()
    return perm.role if perm else None

def check_event_conflicts(user_id, start_time, end_time, exclude_event_id=None):
    query = Event.query.filter(
        Event.owner_id == user_id,
        Event.start_time < end_time,
        Event.end_time > start_time
    )
    if exclude_event_id:
        query = query.filter(Event.id != exclude_event_id)
    return query.all()

def event_to_dict(event, user_role=None):
    data = event.to_dict()
    data["permissions"] = user_role or "None"
    return data

def validate_event_data(data, for_update=False):
    errors = []
    if not for_update:
        if not data.get("title"):
            errors.append("Missing title")
        if not data.get("start_time"):
            errors.append("Missing start_time")
        if not data.get("end_time"):
            errors.append("Missing end_time")

    if "start_time" in data and "end_time" in data:
        try:
            start = datetime.fromisoformat(data["start_time"])
            end = datetime.fromisoformat(data["end_time"])
            if start >= end:
                errors.append("start_time must be before end_time")
        except Exception:
            errors.append("start_time and end_time must be valid ISO format datetime strings")

    if data.get("is_recurring") and not data.get("recurrence_pattern"):
        errors.append("recurrence_pattern required if is_recurring is True")

    return errors

@events_bp.route('/events', methods=['POST'])
@jwt_required()
def create_event():
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    
    shared = EventPermission.query.filter_by(user_id=user_id).first()
    if shared:
        return jsonify({"error": "Only event owners can create events."}), 403

    if "owner_id" in data and data["owner_id"] != user_id:
        return jsonify({"error": "You cannot assign owner_id manually."}), 403


    conflicts = check_event_conflicts(user_id, data.get('start_time'), data.get('end_time'))
    if conflicts:
        return jsonify({
            "message": "Event conflict detected",
            "conflicts": [event.id for event in conflicts]
        }), 409

    errors = validate_event_data(data)
    if errors:
        return jsonify({"errors": errors}), 400

    event = Event(
        title=data.get('title'),
        description=data.get('description'),
        start_time=datetime.fromisoformat(data.get('start_time')),
        end_time=datetime.fromisoformat(data.get('end_time')),
        location=data.get('location'),
        is_recurring=data.get('is_recurring', False),
        owner_id=user_id,
        recurrence_pattern=data.get('recurrence_pattern')
    )
    db.session.add(event)
    db.session.commit()

    save_event_version(event, user_id) 
    emit_event('event_created', event.to_dict())

    return jsonify({
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "start_time": event.start_time.isoformat(),
        "end_time": event.end_time.isoformat(),
        "location": event.location,
        "is_recurring": event.is_recurring,
        "recurrence_pattern": event.recurrence_pattern
        }), 201

@events_bp.route('/events', methods=['GET'])
@jwt_required()
def list_events():
    user_id = int(get_jwt_identity())

    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    start_filter = request.args.get('start_time')
    end_filter = request.args.get('end_time')
    owner_filter = request.args.get('owner_id')
    is_recurring_filter = request.args.get('is_recurring')

    query = Event.query.join(EventPermission, isouter=True).filter(
        or_(Event.owner_id == user_id, EventPermission.user_id == user_id)
    ).distinct()

    try:
        if start_filter:
            query = query.filter(Event.start_time >= datetime.fromisoformat(start_filter))
        if end_filter:
            query = query.filter(Event.end_time <= datetime.fromisoformat(end_filter))
    except Exception:
        return jsonify({"error": "Invalid start_time or end_time filter"}), 400

    if owner_filter:
        try:
            query = query.filter(Event.owner_id == int(owner_filter))
        except ValueError:
            return jsonify({"error": "Invalid owner_id"}), 400

    if is_recurring_filter:
        if is_recurring_filter.lower() == "true":
            query = query.filter(Event.is_recurring.is_(True))
        elif is_recurring_filter.lower() == "false":
            query = query.filter(Event.is_recurring.is_(False))
        else:
            return jsonify({"error": "Invalid is_recurring filter"}), 400

    paginated = query.order_by(Event.start_time.asc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "page": page,
        "per_page": per_page,
        "total": paginated.total,
        "events": [event_to_dict(event, check_user_role(event, user_id)) for event in paginated.items]
    }), 200

@events_bp.route('/events/<int:event_id>', methods=['GET'])
@jwt_required()
def get_event(event_id):
    user_id = int(get_jwt_identity())
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404

    role = check_user_role(event, user_id)
    # if not role:
    #     return jsonify({"error": "Permission denied"}), 403

    return jsonify(event_to_dict(event, role)), 200

@events_bp.route('/events/<int:event_id>', methods=['PUT'])
@jwt_required()
def update_event(event_id):
    user_id = int(get_jwt_identity())
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404

    role = check_user_role(event, user_id)
    if role not in ("Owner", "Editor"):
        return jsonify({"error": "Permission denied"}), 403
    data = request.get_json() or {}
    conflicts = check_event_conflicts(user_id, data.get('start_time'), data.get('end_time'), exclude_event_id=event_id)
    if conflicts:
        return jsonify({
            "message": "Event conflict detected",
            "conflicts": [event.id for event in conflicts]
        }), 409

    errors = validate_event_data(data, for_update=True)
    if errors:
        return jsonify({"errors": errors}), 400

    updated = False
    for field in ["title", "description", "location", "is_recurring", "recurrence_pattern"]:
        if field in data and getattr(event, field) != data[field]:
            setattr(event, field, data[field])
            updated = True

    for dt_field in ["start_time", "end_time"]:
        if dt_field in data:
            try:
                new_val = datetime.fromisoformat(data[dt_field])
                if getattr(event, dt_field) != new_val:
                    setattr(event, dt_field, new_val)
                    updated = True
            except Exception:
                return jsonify({"error": f"Invalid {dt_field} format"}), 400

    if not updated:
        return jsonify({"msg": "No changes detected"}), 200

    db.session.commit()
    emit_event('event_updated', event.to_dict())
    save_event_version(event, user_id)
    role = check_user_role(event, user_id)
    if not role:
        return jsonify({"error": "Permission denied"}), 403
    return jsonify(event_to_dict(event, role)), 200

@events_bp.route('/events/<int:event_id>', methods=['DELETE'])
@jwt_required()
def delete_event(event_id):
    user_id = int(get_jwt_identity())
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404

    if event.owner_id != user_id:
        return jsonify({"error": "Only the owner can delete the event"}), 403

    EventPermission.query.filter_by(event_id=event.id).delete()
    EventVersion.query.filter_by(event_id=event.id).delete()
    db.session.delete(event)
    db.session.commit()

    emit_event('event_deleted', {"id": event_id, "owner_id": user_id})
    
    return jsonify({"msg": "Event deleted"}), 200

@events_bp.route('/events/batch', methods=['POST'])
@jwt_required()
def batch_create_events():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    if not data or not isinstance(data, list):
        return jsonify({"error": "Expected a list of event objects"}), 400

    created_events = []
    errors = []

    for idx, entry in enumerate(data):
        errs = validate_event_data(entry)
        if errs:
            errors.append({"index": idx, "errors": errs})
            continue

        try:
            event = Event(
                title=entry["title"],
                description=entry.get("description"),
                start_time=datetime.fromisoformat(entry["start_time"]),
                end_time=datetime.fromisoformat(entry["end_time"]),
                location=entry.get("location"),
                is_recurring=entry.get("is_recurring", False),
                recurrence_pattern=entry.get("recurrence_pattern"),
                owner_id=user_id
            )
            db.session.add(event)
            db.session.flush()

            save_event_version(event, user_id)
            emit_event('event_created', event.to_dict())
            created_events.append(event.to_dict())
            role = check_user_role(event, user_id)
            if not role:
                return jsonify({"error": "Only owner and editor can create multiple events"}), 403

        except Exception as e:
            errors.append({"index": idx, "errors": [str(e)]})
    db.session.commit()
    
    return jsonify({"created": created_events, "errors": errors}), 207

@events_bp.route('/events/<int:event_id>/share', methods=['POST'])
@jwt_required()
def share_event(event_id):
    user_id = int(get_jwt_identity())

    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404

    if event.owner_id != user_id:
        return jsonify({"error": "Only the owner can share the event"}), 403

    data = request.get_json()
    if not data or "users" not in data:
        return jsonify({"error": "Missing 'users' list in request body"}), 400

    shared_users = []
    for entry in data["users"]:
        share_with_user_id = entry.get("user_id")
        role = entry.get("permission")

        if not share_with_user_id or role not in ("Editor", "Viewer"):
            continue  # skip invalid entries

        if int(share_with_user_id) == user_id:
            continue  # skip owner

        share_with_user = User.query.get(share_with_user_id)
        if not share_with_user:
            continue  # skip if target user doesn't exist

        # Create or update permission
        perm = EventPermission.query.filter_by(event_id=event_id, user_id=share_with_user_id).first()
        if perm:
            perm.role = role
        else:
            perm = EventPermission(
                event_id=event_id,
                user_id=share_with_user_id,
                role=role,
                username=share_with_user.username
            )
            db.session.add(perm)

        shared_users.append({
            "user_id": share_with_user_id,
            "role": role
        })

        emit_event('event_shared', {
            "event_id": event_id,
            "shared_with_user_id": share_with_user_id,
            "role": role,
            "owner_id": user_id
        })

    db.session.commit()
    emit_event('event_shared', {
        "event_id": event_id,
        "shared_users": shared_users,
        "role": role,
        "owner_id": user_id
    })
    return jsonify({
        "msg": f"Event shared with {len(shared_users)} user(s)",
        "shared": shared_users
    }), 200
