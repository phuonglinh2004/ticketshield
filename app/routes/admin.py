import os
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from app.models import db, Ticket, AuditLog, Order, User, Seat
from app.services.security_service import SecurityService
from app.services.totp_service import TicketSecurityService
from config import Config

admin_bp = Blueprint("admin", __name__)

@admin_bp.post("/gate/verify")
def api_gate_verify():
    """
    Cổng soát vé Ban tổ chức (Gate Check-in Scanner)
    - Nhận chuỗi payload: ticket_id:totp_code
    - Kiểm tra tính nguyên tử: đã quét chưa (used == 1)?
    - Kiểm tra mã TOTP trong khung 15 giây hiện tại
    - Chống Replay / Ảnh chụp màn hình cũ triệt để
    """
    data = request.json or {}
    raw_payload = str(data.get("payload", "")).strip()

    if not raw_payload or ":" not in raw_payload:
        return jsonify(
            ok=False,
            status="INVALID_FORMAT",
            msg="CẢNH BÁO: Định dạng mã QR không hợp lệ! Vui lòng quét mã trên app Ticketbox chính thức."
        ), 400

    ticket_id, client_totp = raw_payload.split(":", 1)
    ticket_id = ticket_id.strip()
    client_totp = client_totp.strip()

    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        SecurityService.record_audit(
            event="FAKE_TICKET_DETECTED",
            detail=f"Phát hiện quét vé không tồn tại: {ticket_id}",
            severity="DANGER"
        )
        return jsonify(
            ok=False,
            status="NOT_FOUND",
            msg="CẢNH BÁO BẢO MẬT: Mã vé không tồn tại trên hệ thống! Nghi vấn làm giả vé."
        ), 404

    # Kiểm tra vé đã từng quét vào cổng chưa (Double Check-in Prevention)
    if ticket.used:
        SecurityService.record_audit(
            event="DOUBLE_CHECKIN_BLOCKED",
            detail=f"Vé {ticket_id} bị quét lần 2 (Đã vào cổng lúc {ticket.used_at})",
            severity="WARNING",
            user_id=ticket.user_id
        )
        return jsonify(
            ok=False,
            status="ALREADY_USED",
            msg=f"CẢNH BÁO: Vé này đã được quét vào cổng lúc {ticket.used_at}! Mỗi vé chỉ được vào cổng 1 lần.",
            used_at=ticket.used_at
        ), 400

    # Kiểm tra trạng thái vé
    if ticket.status != "valid":
        return jsonify(
            ok=False,
            status="REVOKED",
            msg=f"Vé này đã bị vô hiệu hóa hoặc chuyển nhượng (Trạng thái: {ticket.status})! Không thể sử dụng."
        ), 400

    # Kiểm tra mã TOTP động (chu kỳ 15 giây)
    is_valid = TicketSecurityService.verify_ticket_qr(ticket.ticket_secret, client_totp, interval=Config.TOTP_INTERVAL)
    if not is_valid:
        SecurityService.record_audit(
            event="REPLAY_QR_BLOCKED",
            detail=f"Vé {ticket_id} quét mã TOTP sai/hết hạn: {client_totp}. Nghi vấn Replay Attack bằng ảnh chụp màn hình!",
            severity="DANGER",
            user_id=ticket.user_id
        )
        return jsonify(
            ok=False,
            status="EXPIRED_QR",
            msg="CẢNH BÁO BẢO MẬT: Mã QR đã hết hạn hoặc bị chụp màn hình chia sẻ lại! Từ chối vào cổng."
        ), 400

    # Hợp lệ -> Đánh dấu vé đã check-in ngay lập tức
    checkin_time = datetime.now().strftime("%H:%M:%S")
    ticket.used = 1
    ticket.used_at = checkin_time
    db.session.commit()

    ev = ticket.event
    owner = ticket.owner

    SecurityService.record_audit(
        event="CHECKIN_SUCCESS",
        detail=f"Vé {ticket_id} ({ticket.ticket_type}) đã check-in thành công qua cổng lúc {checkin_time}",
        severity="INFO",
        user_id=ticket.user_id
    )

    return jsonify(
        ok=True,
        status="ALLOWED",
        msg="VÉ HỢP LỆ - MỜI QUÝ KHÁCH VÀO CỔNG!",
        ticket_id=ticket.id,
        ticket_type=ticket.ticket_type,
        seat_id=ticket.seat_id or "Khu vực đứng (GA)",
        event_title=ev.title if ev else "Concert Ticketbox",
        attendee=owner.full_name if owner else "Khách tham dự",
        checkin_time=checkin_time
    )

@admin_bp.get("/audit")
def api_audit_logs():
    """Xem nhật ký kiểm toán an ninh thời gian thực (Lớp Zero Trust)"""
    logs = AuditLog.query.order_by(AuditLog.id.desc()).limit(30).all()
    return jsonify(ok=True, logs=[l.to_dict() for l in logs])

@admin_bp.get("/stats")
def api_stats():
    """Thống kê tổng quan hệ thống"""
    total_orders = Order.query.count()
    total_tickets = Ticket.query.count()
    checked_in = Ticket.query.filter_by(used=1).count()
    alerts = AuditLog.query.filter(AuditLog.severity.in_(["WARNING", "DANGER"])).count()

    return jsonify(
        ok=True,
        orders=total_orders,
        tickets=total_tickets,
        checked_in=checked_in,
        alerts=alerts
    )

@admin_bp.post("/security/simulate")
def api_security_simulate():
    """Sandbox mô phỏng trực tiếp các tình huống tấn công cho Giảng viên xem"""
    data = request.json or {}
    attack_type = str(data.get("type", "tamper_price")).strip()

    if attack_type == "tamper_price":
        SecurityService.record_audit(
            event="TAMPER_SIMULATION",
            detail="Giả lập: Hacker can thiệp sửa giá vé VIP từ 2.000.000đ thành 10.000đ qua F12. Chữ ký HMAC không khớp -> BỊ CHẶN!",
            severity="DANGER"
        )
        return jsonify(
            ok=True,
            attack="Sửa giá tiền (Parameter Tampering)",
            attempt="Gửi đơn hàng VIP giá 10.000đ với HMAC Token giả",
            defense="Lớp 3: Server-side Pricing + Chữ ký HMAC-SHA256 bí mật",
            result="TỪ CHỐI GIAO DỊCH (HTTP 400) & Ghi nhật ký báo động"
        )

    elif attack_type == "replay_qr":
        SecurityService.record_audit(
            event="REPLAY_SIMULATION",
            detail="Giả lập: Quét mã QR cũ đã chụp từ 2 phút trước. Mã TOTP hết hạn 15s -> BỊ TỪ CHỐI TẠI CỔNG!",
            severity="DANGER"
        )
        return jsonify(
            ok=True,
            attack="Replay Attack (Ảnh chụp màn hình vé)",
            attempt="Mang ảnh chụp màn hình mã QR đã quá 15 giây đến cổng",
            defense="Lớp 4: Dynamic TOTP QR (15s rotation) + Atomic Flag used=1",
            result="TỪ CHỐI VÀO CỔNG (HTTP 400) - Báo động 'Mã QR đã hết hạn'"
        )

    elif attack_type == "bot_spam":
        SecurityService.record_audit(
            event="BOT_SPAM_SIMULATION",
            detail="Giả lập: Botnet gửi 20 yêu cầu gom vé/giây từ 1 IP. Rate Limiter kích hoạt -> BỊ KHÓA HTTP 429!",
            severity="WARNING"
        )
        return jsonify(
            ok=True,
            attack="Bot gom vé (Scalper Bot / DDoS)",
            attempt="Gửi 20 request/giây để vét sạch vé VIP",
            defense="Lớp 1: Rate Limiting Middleware (Sliding Window)",
            result="CHẶN NGAY LẬP TỨC (HTTP 429: Too Many Requests)"
        )

    elif attack_type == "session_hijack":
        SecurityService.record_audit(
            event="HIJACK_SIMULATION",
            detail="Giả lập: Hacker đánh cắp Session Cookie nhưng gửi từ thiết bị khác. Sai Fingerprint -> HỦY PHIÊN!",
            severity="DANGER"
        )
        return jsonify(
            ok=True,
            attack="Đánh cắp phiên (Session Hijacking)",
            attempt="Dùng token hợp lệ nhưng gửi từ IP và User-Agent khác",
            defense="Lớp 2: Client Fingerprint (IP + User-Agent Hash)",
            result="HỦY PHIÊN NGAY LẬP TỨC (HTTP 401: Unauthorized)"
        )

    elif attack_type == "sqli_login":
        SecurityService.record_audit(
            event="SQLI_SIMULATION",
            detail="Giả lập: Thử chèn `' OR '1'='1` vào form đăng nhập. SQLAlchemy ORM vô hiệu hóa -> THẤT BẠI!",
            severity="WARNING"
        )
        return jsonify(
            ok=True,
            attack="SQL Injection",
            attempt="Nhập username: ' OR '1'='1 vào form đăng nhập",
            defense="Prepared Statements / SQLAlchemy ORM Parameterization",
            result="TỪ CHỐI (HTTP 401: Tên đăng nhập không chính xác)"
        )

    return jsonify(ok=False, msg="Loại tấn công không xác định"), 400

@admin_bp.get("/smtp/status")
def api_smtp_status():
    user = os.getenv("SMTP_USER", "").strip()
    has_pass = bool(os.getenv("SMTP_PASS", "").strip())
    return jsonify(
        configured=bool(user and has_pass),
        smtp_user=user or "Chưa cấu hình",
        smtp_server=os.getenv("SMTP_SERVER", "smtp.gmail.com")
    )

@admin_bp.post("/smtp/config")
def api_smtp_config():
    data = request.json or {}
    user = str(data.get("smtp_user", "")).strip()
    pwd = str(data.get("smtp_pass", "")).strip().replace(" ", "")
    if not user or not pwd:
        return jsonify(ok=False, msg="Vui lòng nhập Email và Mật khẩu ứng dụng Gmail (16 chữ cái)"), 400

    os.environ["SMTP_USER"] = user
    os.environ["SMTP_PASS"] = pwd

    try:
        with open(".env", "w", encoding="utf-8") as f:
            f.write(f"SMTP_SERVER=smtp.gmail.com\nSMTP_PORT=465\nSMTP_USER={user}\nSMTP_PASS={pwd}\n")
    except Exception:
        pass

    return jsonify(ok=True, msg=f"Đã lưu cấu hình SMTP thành công cho {user}! Hệ thống sẽ gửi email thật qua tài khoản này.")
