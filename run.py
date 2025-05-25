from app import create_app, db, socketio
from flask import Flask, send_from_directory
from flask_swagger_ui import get_swaggerui_blueprint
import os
app = create_app()

with app.app_context():
    db.create_all()


@app.route('/openapi.yaml')
def openapi_spec():
    return send_from_directory(os.getcwd(), 'openapi.yaml', mimetype='text/yaml')

SWAGGER_URL = '/docs'
API_URL = '/openapi.yaml'

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "event_scheduler"}
)

app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

if __name__ == "__main__":
    socketio.run(app, debug=True)
