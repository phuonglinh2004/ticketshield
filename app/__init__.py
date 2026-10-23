import os
import time
from collections import defaultdict, deque
from flask import Flask, request, jsonify
from flask_migrate import Migrate
from config import Config
from app.models import db

migrate = Migrate()

# Bộ nhớ trượt phục vụ Rate Limiting chống Bot gom vé
IP_REQUEST_HITS = defaultdict(deque)
RATE_LIMITED_ENDPOINTS = (
    "/api/login",
    "/api/register",
    "/api/quote",
    "/api/buy",
    "/api/gate/verify"
)

def create_app(config_class=Config):
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    template_dir = os.path.join(base_dir, "templates")
    static_dir = os.path.join(base_dir, "static")

    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir
    )
    app.config.from_object(config_class)

    # Khởi tạo CSDL SQLAlchemy và Migration
    db.init_app(app)
    migrate.init_app(app, db)

    # Lớp 1 Zero Trust: Rate Limiting Middleware chống bot gom vé / DDoS
    @app.before_request
    def rate_limit_filter():
        if request.path in RATE_LIMITED_ENDPOINTS:
            client_ip = request.remote_addr or "127.0.0.1"
            now = time.time()
            q = IP_REQUEST_HITS[client_ip]

            # Xóa các yêu cầu cũ quá 1 giây
            while q and now - q[0] > 1.0:
                q.popleft()

            # Ngưỡng 5 req/s (Chặn bot spam, không gây cản trở thao tác click thực tế)
            if len(q) >= 5:
                from app.services.security_service import SecurityService
                SecurityService.record_audit(
                    event="BOT_SUSPECTED",
                    detail=f"Tốc độ bất thường tại endpoint {request.path} (>5 req/s)",
                    severity="WARNING",
                    ip=client_ip
                )
                return jsonify(
                    ok=False,
                    msg="CẢNH BÁO BẢO MẬT: Phát hiện quá nhiều yêu cầu trong thời gian ngắn! Hệ thống nghi ngờ có hành vi dùng Bot gom vé."
                ), 429

            q.append(now)

    # Đăng ký các Blueprints theo mô hình phân tầng
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.booking import booking_bp
    from app.routes.ticket import ticket_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(main_bp, url_prefix="")
    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(booking_bp, url_prefix="/api")
    app.register_blueprint(ticket_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api")

    return app
