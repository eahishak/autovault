import os
from flask import Flask
from config import config
from app.extensions import db, login_manager, mail, bcrypt, csrf


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')

    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)

    # blueprints
    from app.auth import auth as auth_bp
    from app.main import main as main_bp
    from app.listings import listings as listings_bp
    from app.dashboard import dashboard as dashboard_bp
    from app.messages import messages as messages_bp
    from app.admin import admin as admin_bp
    from app.api import api as api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(listings_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')

    # jinja globals
    from app.utils import format_price, format_mileage, time_ago, days_since
    app.jinja_env.globals.update(
        format_price=format_price,
        format_mileage=format_mileage,
        time_ago=time_ago,
        days_since=days_since,
    )

    # create tables and seed on first run
    with app.app_context():
        db.create_all()
        _ensure_admin()
        from app.utils import seed_database
        seed_database(app)

    _register_error_handlers(app)
    _register_shell_context(app)

    return app


def _ensure_admin():
    from app.models import User
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@autovault.com')
    if not User.query.filter_by(email=admin_email).first():
        admin = User(
            name='AutoVault Admin',
            email=admin_email,
            role='admin',
            is_verified=True,
        )
        admin.set_password(os.environ.get('ADMIN_PASSWORD', 'Admin1234!'))
        db.session.add(admin)
        db.session.commit()


def _register_error_handlers(app):
    from flask import render_template

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template('errors/500.html'), 500


def _register_shell_context(app):
    from app.models import User, Car, Message, Favorite, CarImage, Notification, Review

    @app.shell_context_processor
    def ctx():
        return dict(db=db, User=User, Car=Car, Message=Message,
                    Favorite=Favorite, CarImage=CarImage,
                    Notification=Notification, Review=Review)