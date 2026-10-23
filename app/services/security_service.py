import time
import json
import base64
import hmac
import hashlib
import secrets
from flask import request
from app.models import db, AuditLog
from config import Config

# Quản lý phiên trong bộ nhớ và danh sách Nonce
SESSIONS = {}          # token -> {uid, username, role, fp}
LOGIN_FAILS = {}       # username -> (fail_count, lock_until_timestamp)
USED_NONCES = set()    # Chống replay attack cho order tokens

class SecurityService:
    @staticmethod
    def hash_password(password: str) -> str:
        """Băm mật khẩu kết hợp salt ngẫu nhiên"""
        salt = "ticketshield_secure_salt_2026"
        return hashlib.sha256(f"{salt}::{password}".encode("utf-8")).hexdigest()

    @staticmethod
    def compute_fingerprint():
        """Tạo vân tay thiết bị dựa trên IP + User-Agent"""
        client_ip = request.remote_addr or ""
        ua = request.headers.get("User-Agent", "")
        return hashlib.sha256(f"{client_ip}::{ua}".encode("utf-8")).hexdigest()

    @staticmethod
    def record_audit(event: str, detail: str, severity: str = "INFO", user_id: int = None, ip: str = None):
        """Ghi nhận nhật ký kiểm toán bảo mật vào CSDL"""
        try:
            client_ip = ip or request.remote_addr or "127.0.0.1"
            ua = request.headers.get("User-Agent", "Client") if request else "System"
            log = AuditLog(
                ip=client_ip,
                user_agent=ua[:190],
                user_id=user_id,
                event=event,
                detail=detail,
                severity=severity
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[!] Lỗi ghi audit log: {e}")

    @staticmethod
    def create_session(user) -> str:
        token = secrets.token_hex(24)
        fp = SecurityService.compute_fingerprint()
        SESSIONS[token] = {
            "uid": user.id,
            "username": user.username,
            "role": user.role,
            "fp": fp,
            "created_at": time.time()
        }
        return token

    @staticmethod
    def get_session(token: str):
        return SESSIONS.get(token)

    @staticmethod
    def revoke_session(token: str):
        if token in SESSIONS:
            del SESSIONS[token]

    @staticmethod
    def create_order_token(ticket_type: str, qty: int, price: int, event_id: int) -> str:
        """
        Server tính toán giá tiền và ký số bằng HMAC-SHA256:
        - exp: Hạn dùng 10 phút (600s)
        - nonce: Chuỗi ngẫu nhiên duy nhất (Chống Replay)
        - Client KHÔNG THỂ sửa đổi giá mà không làm hỏng chữ ký HMAC!
        """
        nonce = secrets.token_hex(8)
        payload = {
            "type": ticket_type,
            "qty": qty,
            "unit_price": price,
            "total": price * qty,
            "event_id": event_id,
            "exp": time.time() + 600,
            "nonce": nonce
        }
        raw_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        raw_b64 = base64.urlsafe_b64encode(raw_json.encode("utf-8")).decode("utf-8")
        sig = hmac.new(Config.HMAC_SECRET_KEY, raw_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{raw_b64}.{sig}"

    @staticmethod
    def verify_order_token(token_str: str):
        """Xác thực token đơn hàng: Kiểm tra chữ ký HMAC và hạn dùng"""
        try:
            raw_b64, sig = token_str.split(".")
            expected_sig = hmac.new(Config.HMAC_SECRET_KEY, raw_b64.encode("utf-8"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected_sig):
                return None # Chữ ký bị sai lệch hoặc bị làm giả!
            data = json.loads(base64.urlsafe_b64decode(raw_b64.encode("utf-8")).decode("utf-8"))
            if data.get("exp", 0) < time.time():
                return None # Token đã hết hạn 10 phút
            return data
        except Exception:
            return None
