from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import Event, EventVersion, User
from app import db
from deepdiff import DeepDiff
import json

changelog_bp = Blueprint("changelog", __name__)

def serialize_event_version(version):
    return {
        "version_id": version.id,
        "version_number": version.version_number,
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "modified_by": User.query.get(version.modified_by).username if version.modified_by else None,
        "data": json.loads(version.data) if isinstance(version.data, str) else version.data
    }

def make_diff_serializable(diff_tree):
    if isinstance(diff_tree, dict):
        return {k: make_diff_serializable(v) for k, v in diff_tree.items()}
    elif isinstance(diff_tree, list):
        return [make_diff_serializable(i) for i in diff_tree]
    elif hasattr(diff_tree, '__dict__'):
        return make_diff_serializable(vars(diff_tree))
    else:
        return diff_tree

@changelog_bp.route('/events/<int:event_id>/changelog', methods=['GET'])
@jwt_required()
def get_changelog(event_id):
    user_id = int(get_jwt_identity())
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404


    versions = EventVersion.query.filter_by(event_id=event_id).order_by(EventVersion.created_at.asc()).all()
    if not versions:
        return jsonify({"error": "No versions found for this event"}), 404

    return jsonify([serialize_event_version(v) for v in versions]), 200


@changelog_bp.route('/events/<int:event_id>/diff/<int:vid1>/<int:vid2>', methods=['GET'])
@jwt_required()
def get_diff(event_id, vid1, vid2):
    user_id = int(get_jwt_identity())
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404


    v1 = EventVersion.query.filter_by(id=vid1, event_id=event_id).first()
    v2 = EventVersion.query.filter_by(id=vid2, event_id=event_id).first()

    if not v1 or not v2:
        return jsonify({"error": "One or both versions not found"}), 404

    try:
        data1 = json.loads(v1.data) if isinstance(v1.data, str) else v1.data
        data2 = json.loads(v2.data) if isinstance(v2.data, str) else v2.data
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse version data as JSON"}), 500

    raw_diff = DeepDiff(data1, data2)
    return jsonify({"diff": raw_diff}), 200
