import os
import secrets
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Khóa bảo mật phiên và chữ ký HMAC
    SECRET_KEY = os.getenv("SECRET_KEY", "ticketshield_flask_secret_2026_super_key")
    HMAC_SECRET_KEY = os.getenv("HMAC_SECRET_KEY", "ticketshield_hmac_secret_master_token_2026").encode("utf-8")

    # Cấu hình Cơ sở dữ liệu: Hỗ trợ linh hoạt PostgreSQL, tự động fallback SQLite
    # Ví dụ: postgresql://postgres:password123@localhost:5432/ticketshield_db
    DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
    if DATABASE_URL:
        # Hỗ trợ chuẩn chuỗi kết nối SQLAlchemy cho Postgres
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # Fallback SQLite mặc định để Thầy/Cô chạy không cần cài đặt thêm phần mềm
        base_dir = os.path.abspath(os.path.dirname(__file__))
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(base_dir, 'ticketshield.db')}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Cấu hình chu kỳ mã QR TOTP động (chuẩn RFC 6238)
    TOTP_INTERVAL = int(os.getenv("TOTP_INTERVAL", 15))

    # Cấu hình Gmail SMTP gửi Email thật
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASS = os.getenv("SMTP_PASS", "")

    # Cấu hình Rate Limiting chống bot gom vé
    RATELIMIT_DEFAULT = "100/minute"
    RATELIMIT_STORAGE_URI = "memory://"
