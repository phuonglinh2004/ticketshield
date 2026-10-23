from datetime import datetime
from . import db

class TransactionalOTP(db.Model):
    __tablename__ = "transactional_otps"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    target = db.Column(db.String(120), nullable=False, index=True) # email, phone hoặc username
    action = db.Column(db.String(50), nullable=False) # 'register', 'login', 'payment'
    otp_hash = db.Column(db.String(64), nullable=False) # SHA-256 hash của mã OTP 6 số
    demo_code = db.Column(db.String(10), nullable=False)
    expiry_time = db.Column(db.Float, nullable=False) # Unix timestamp thời điểm hết hạn (120s)
    fail_count = db.Column(db.Integer, default=0, nullable=False) # Đếm số lần nhập sai (max 3 lần)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self):
        return {
            "id": self.id,
            "target": self.target,
            "action": self.action,
            "expiry_time": self.expiry_time,
            "fail_count": self.fail_count,
            "created_at": self.created_at
        }

class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ts = db.Column(db.String(50), default=lambda: datetime.now().strftime("%H:%M:%S"))
    ip = db.Column(db.String(50), default="127.0.0.1")
    user_agent = db.Column(db.String(200), default="WebClient")
    user_id = db.Column(db.Integer, nullable=True)
    event = db.Column(db.String(100), nullable=False) # e.g. TAMPER_PRICE, BOT_SUSPECTED, REPLAY_QR
    detail = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), default="INFO") # 'INFO', 'WARNING', 'DANGER'

    def to_dict(self):
        return {
            "id": self.id,
            "ts": self.ts,
            "ip": self.ip,
            "user_agent": self.user_agent,
            "user_id": self.user_id,
            "event": self.event,
            "detail": self.detail,
            "severity": self.severity
        }
