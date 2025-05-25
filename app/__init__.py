from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from app.config import Config
from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins="*")
db = SQLAlchemy()
bcrypt = Bcrypt()
jwt = JWTManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    socketio.init_app(app)
    
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')

    with app.app_context():
        db.create_all()

    from app.routes.events import events_bp
    app.register_blueprint(events_bp, url_prefix='/api')

    from app.routes.collaboration import collab_bp
    app.register_blueprint(collab_bp, url_prefix='/api')
    
    from app.routes.versioning import version_bp
    app.register_blueprint(version_bp, url_prefix='/api')
    
    from app.routes.changelog import changelog_bp 
    app.register_blueprint(changelog_bp , url_prefix='/api')

    import app.sockets.realtime as _
    
    return app
