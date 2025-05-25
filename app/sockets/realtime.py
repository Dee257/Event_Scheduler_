from flask_socketio import emit
from app import socketio

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('message', {'data': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('join_room')
def handle_join_room(data):
    room = data.get('room')
    if room:
        from flask_socketio import join_room
        join_room(room)
        emit('message', {'data': f'Joined room {room}'}, room=room)

@socketio.on('leave_room')
def handle_leave_room(data):
    room = data.get('room')
    if room:
        from flask_socketio import leave_room
        leave_room(room)
        emit('message', {'data': f'Left room {room}'}, room=room)

@socketio.on('send_event_update')
def handle_send_event_update(data):
    room = data.get('room')
    event_data = data.get('event')
    if room and event_data:
        emit('event_update', event_data, room=room)
