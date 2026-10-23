import os
import time
from functools import wraps
from flask import Blueprint, request, jsonify, g
import pyotp

from app.models import db, User
from app.services.security_service import SecurityService, LOGIN_FAILS
from app.services.otp_service import OTPService

auth_bp = Blueprint("auth", __name__)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else request.cookies.get("session_token")
        if not token:
            return jsonify(ok=False, msg="Yêu cầu đăng nhập để thực hiện thao tác này!"), 401

        session = SecurityService.get_session(token)
        if not session:
            return jsonify(ok=False, msg="Phiên đăng nhập không hợp lệ hoặc đã hết hạn!"), 401

        # Lớp 2 Zero Trust: Kiểm tra vân tay thiết bị (Fingerprint) chống Session Hijacking
        curr_fp = SecurityService.compute_fingerprint()
        if session["fp"] != curr_fp:
            SecurityService.revoke_session(token)
            SecurityService.record_audit(
                event="SESSION_HIJACK_ATTEMPT",
                detail=f"Token của user {session['username']} bị sử dụng từ thiết bị/IP lạ! Đã thu hồi phiên.",
                severity="DANGER",
                user_id=session["uid"]
            )
            return jsonify(ok=False, msg="CẢNH BÁO: Phát hiện phiên đăng nhập bất thường từ thiết bị khác! Phiên đã bị hủy để bảo vệ tài khoản."), 401

        g.uid = session["uid"]
        g.username = session["username"]
        g.role = session["role"]
        return f(*args, **kwargs)
    return decorated

@auth_bp.post("/otp/send")
def api_send_otp():
    """Gửi OTP 6 số (băm SHA-256 lưu DB hạn 120s, gửi thư thật qua SMTP)"""
    data = request.json or {}
    target = str(data.get("target", "")).strip().lower()
    action = str(data.get("action", "login")).strip().lower()

    if not target:
        return jsonify(ok=False, msg="Vui lòng cung cấp Email, SĐT hoặc Tên đăng nhập"), 400

    otp_info = OTPService.generate_and_send_otp(target, action)
    has_smtp = bool(os.getenv("SMTP_USER", "").strip() and os.getenv("SMTP_PASS", "").strip())

    return jsonify(
        ok=True,
        msg=f"Mã OTP 6 số đã được gửi đến {otp_info['recipient_email']}!",
        demo_otp=otp_info["otp_code"],
        recipient_email=otp_info["recipient_email"],
        real_email_sent=has_smtp,
        exp_in=120,
        target=target,
        action=action
    )

@auth_bp.post("/register")
def api_register():
    """Đăng ký tài khoản mới: Xác thực Email/SĐT qua mã OTP giao dịch băm SHA-256"""
    data = request.json or {}
    username = str(data.get("username", "")).strip().lower()
    email = str(data.get("email", "")).strip().lower()
    full_name = str(data.get("full_name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    password = str(data.get("password", "")).strip()
    otp_code = str(data.get("otp", "")).strip()

    if not username or not email or not password or not full_name or not phone:
        return jsonify(ok=False, msg="Vui lòng điền đầy đủ tất cả thông tin bắt buộc"), 400
    if len(username) < 3 or not username.isalnum():
        return jsonify(ok=False, msg="Tên đăng nhập chỉ gồm chữ và số, tối thiểu 3 ký tự"), 400
    if "@" not in email or "." not in email:
        return jsonify(ok=False, msg="Email không hợp lệ"), 400

    # Kiểm tra trùng lặp
    existing = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing:
        return jsonify(ok=False, msg="Tên đăng nhập hoặc Email đã tồn tại trên hệ thống"), 400

    # Xác thực OTP giao dịch nếu có gửi lên
    if otp_code:
        ok_otp, msg_otp = OTPService.verify_otp(email, "register", otp_code)
        if not ok_otp:
            ok_u, _ = OTPService.verify_otp(username, "register", otp_code)
            if not ok_u:
                return jsonify(ok=False, msg=msg_otp), 401

    otp_secret = pyotp.random_base32()
    pw_hash = SecurityService.hash_password(password)

    new_user = User(
        username=username,
        email=email,
        full_name=full_name,
        phone=phone,
        password_hash=pw_hash,
        otp_secret=otp_secret,
        role="fan"
    )
    db.session.add(new_user)
    db.session.commit()

    SecurityService.record_audit(
        event="REGISTER_SUCCESS",
        detail=f"Người dùng mới: {username} ({email}) xác thực danh tính thành công"
    )
    return jsonify(ok=True, msg="Đăng ký tài khoản thành công! Bạn có thể đăng nhập ngay.")

@auth_bp.post("/login")
def api_login():
    """Đăng nhập bằng Username/Email + Mật khẩu + Mã OTP (Hỗ trợ SMS/Email OTP băm SHA-256 và TOTP)"""
    data = request.json or {}
    ident = str(data.get("username", "")).strip().lower()
    password = str(data.get("password", "")).strip()
    otp_code = str(data.get("otp", "")).strip()

    if not ident:
        return jsonify(ok=False, msg="Vui lòng nhập tên đăng nhập hoặc email"), 400

    # Kiểm tra trạng thái khóa tài khoản do nhập sai quá 3 lần
    fail_count, lock_until = LOGIN_FAILS.get(ident, (0, 0))
    if time.time() < lock_until:
        remaining_secs = int(lock_until - time.time())
        mins = remaining_secs // 60 + 1
        SecurityService.record_audit(
            event="LOCKED_ACCESS_ATTEMPT",
            detail=f"Cố gắng đăng nhập tài khoản đang bị khóa: {ident}",
            severity="WARNING"
        )
        return jsonify(ok=False, msg=f"CẢNH BÁO: Tài khoản tạm thời bị khóa do nhập sai OTP quá 3 lần! Vui lòng thử lại sau {mins} phút."), 423

    # Dùng ORM parameterized query chống SQL Injection
    user = User.query.filter((User.username == ident) | (User.email == ident)).first()
    if not user:
        return jsonify(ok=False, msg="Tên đăng nhập hoặc mật khẩu không chính xác"), 401

    # Kiểm tra mật khẩu
    if password and user.password_hash != SecurityService.hash_password(password):
        return jsonify(ok=False, msg="Tên đăng nhập hoặc mật khẩu không chính xác"), 401

    # Kiểm tra mã OTP: Ưu tiên Transactional OTP (SHA-256)
    is_valid_otp = False
    ok_trans, _ = OTPService.verify_otp(user.username, "login", otp_code)
    if not ok_trans:
        ok_trans_email, _ = OTPService.verify_otp(user.email, "login", otp_code)
        if ok_trans_email:
            is_valid_otp = True
    else:
        is_valid_otp = True

    # Fallback kiểm tra RFC 6238 TOTP
    if not is_valid_otp:
        totp = pyotp.TOTP(user.otp_secret)
        if totp.verify(otp_code):
            is_valid_otp = True

    if not is_valid_otp:
        fail_count += 1
        lock_time = (time.time() + 900) if fail_count >= 3 else 0
        LOGIN_FAILS[ident] = (fail_count, lock_time)

        if fail_count >= 3:
            SecurityService.record_audit(
                event="OTP_BRUTEFORCE",
                detail=f"Tài khoản {ident} bị tấn công dò OTP liên tiếp 3 lần. Đã khóa tài khoản 15 phút.",
                severity="DANGER",
                user_id=user.id
            )
            return jsonify(ok=False, msg="CẢNH BÁO BẢO MẬT: Nhập sai mã OTP 3 lần! Tài khoản của bạn đã bị khóa 15 phút để bảo vệ tài khoản."), 423

        return jsonify(ok=False, msg=f"Mã OTP xác thực không chính xác hoặc đã hết hạn! (Còn {3 - fail_count} lần thử)"), 401

    # Đăng nhập thành công -> Reset bộ đếm lỗi
    LOGIN_FAILS.pop(ident, None)
    token = SecurityService.create_session(user)

    SecurityService.record_audit(
        event="LOGIN_SUCCESS",
        detail=f"Tài khoản {user.username} đăng nhập thành công qua 2FA OTP",
        severity="INFO",
        user_id=user.id
    )

    return jsonify(
        ok=True,
        token=token,
        user=user.to_dict()
    )

@auth_bp.post("/logout")
def api_logout():
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else request.cookies.get("session_token")
    if token:
        SecurityService.revoke_session(token)
    return jsonify(ok=True, msg="Đã đăng xuất thành công")

@auth_bp.get("/user/me")
@login_required
def api_user_me():
    user = User.query.get(g.uid)
    if not user:
        return jsonify(ok=False, msg="Không tìm thấy người dùng"), 404
    return jsonify(ok=True, user=user.to_dict())
