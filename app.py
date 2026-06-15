"""
NSDCP — Nigerian Student Digital Community Platform
Application Factory — Railway/PostgreSQL Ready
"""
import os
import markupsafe
from datetime import datetime
from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_mail import Mail
from dotenv import load_dotenv

load_dotenv()

socketio    = SocketIO()
login_mgr   = LoginManager()
migrate     = Migrate()
mail        = Mail()


def create_app():
    app = Flask(__name__)

    # ── Config ───────────────────────────────────────────────────────────────
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'nsdcp-change-me-in-production')

    db_url = os.environ.get('DATABASE_URL', 'sqlite:///nsdcp.db')
    # Railway gives postgres:// — SQLAlchemy 2.x requires postgresql://
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB

    app.config['MAIL_SERVER']   = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT']     = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS']  = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

    app.config['SESSION_COOKIE_SECURE']   = os.environ.get('RAILWAY_ENVIRONMENT') is not None
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # ── Extensions ───────────────────────────────────────────────────────────
    from models import db, bcrypt
    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    login_mgr.init_app(app)
    mail.init_app(app)
    socketio.init_app(app, cors_allowed_origins='*', async_mode='eventlet',
                      logger=False, engineio_logger=False)

    login_mgr.login_view = 'auth.login'
    login_mgr.login_message = 'Please sign in to continue.'
    login_mgr.login_message_category = 'info'

    from models import User

    @login_mgr.user_loader
    def load_user(user_id):
        # SA 2.x compatible: use db.session.get()
        return db.session.get(User, int(user_id))

    # ── Blueprints ────────────────────────────────────────────────────────────
    from auth    import auth_bp
    from main    import main_bp
    from posts   import posts_bp
    from polls   import polls_bp
    from chat    import chat_bp
    from groups  import groups_bp
    from friends import friends_bp
    from admin   import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(posts_bp,   url_prefix='/posts')
    app.register_blueprint(polls_bp,   url_prefix='/polls')
    app.register_blueprint(chat_bp,    url_prefix='/chat')
    app.register_blueprint(groups_bp,  url_prefix='/groups')
    app.register_blueprint(friends_bp, url_prefix='/friends')
    app.register_blueprint(admin_bp,   url_prefix='/admin')

    # ── Template Filters ──────────────────────────────────────────────────────
    @app.template_filter('nl2br')
    def nl2br(val):
        if not val:
            return ''
        return markupsafe.Markup(
            markupsafe.escape(val).replace('\n', markupsafe.Markup('<br>\n'))
        )

    @app.template_filter('ago')
    def time_ago(dt):
        if not dt:
            return ''
        diff = datetime.utcnow() - dt
        s = diff.total_seconds()
        if s < 60:    return 'just now'
        if s < 3600:  return f'{int(s/60)}m ago'
        if s < 86400: return f'{int(s/3600)}h ago'
        return f'{int(s/86400)}d ago'

    # ── DB + Admin Seed ────────────────────────────────────────────────────────
    with app.app_context():
        db.create_all()
        _seed_admin(db, User)

    return app


def _seed_admin(db, User):
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@nsdcp.ng')
    try:
        if not User.query.filter_by(email=admin_email).first():
            admin = User(
                full_name='NSDCP Administrator',
                email=admin_email,
                role='admin',
                role_title='System Administrator',
                institution_tag='NSDCP HQ',
                verification_level=2,
                trust_level='trusted',
                email_verified=True,
                school_name='NSDCP HQ',
                state_of_origin='FCT',
            )
            admin.set_password(os.environ.get('ADMIN_PASSWORD', 'Admin@NSDCP2025'))
            db.session.add(admin)
            db.session.commit()
            print(f'[NSDCP] Admin seeded: {admin_email}')
    except Exception as e:
        db.session.rollback()
        print(f'[NSDCP] Admin seed skipped: {e}')


if __name__ == '__main__':
    app = create_app()
    socketio.run(app, debug=False, host='0.0.0.0', port=5000)
