import time
import secrets
from flask import Blueprint, request, jsonify, g
from app.models import db, Event, TicketType, Seat, Order, Ticket, User
from app.services.security_service import SecurityService, USED_NONCES
from app.services.otp_service import OTPService
from app.services.totp_service import TicketSecurityService
from app.routes.auth import login_required

booking_bp = Blueprint("booking", __name__)

@booking_bp.post("/quote")
@login_required
def api_quote():
    """
    Bước 1 Mua vé: Yêu cầu tính giá (Server-side Pricing)
    - Kiểm tra tồn kho tại CSDL
    - Kiểm tra và Khóa giữ ghế tạm thời (5 phút) chống Race Condition
    - Server sinh mã Order Token có chữ ký HMAC-SHA256 (Hạn 10 phút)
    """
    data = request.json or {}
    t_type = str(data.get("ticket_type", "GA")).strip().upper()
    qty = int(data.get("qty", 1))
    seat_id = str(data.get("seat_id", "")).strip().upper()

    if qty <= 0 or qty > 4:
        return jsonify(ok=False, msg="Số lượng vé mỗi đơn tối đa từ 1 đến 4 vé"), 400

    ev = Event.query.first()
    if not ev:
        return jsonify(ok=False, msg="Không tìm thấy thông tin sự kiện"), 404

    tt = TicketType.query.filter_by(event_id=ev.id, code=t_type).first()
    if not tt:
        return jsonify(ok=False, msg=f"Không tìm thấy hạng vé: {t_type}"), 404

    if tt.remaining_stock < qty:
        return jsonify(ok=False, msg="Rất tiếc, hạng vé này đã hết! Vui lòng chọn hạng vé khác."), 409

    # Cơ chế khóa giữ ghế (Hold Lock 5 phút)
    if seat_id:
        seat = Seat.query.get(seat_id)
        if seat:
            if not seat.is_available():
                return jsonify(ok=False, msg=f"Ghế {seat_id} hiện đang được người khác giữ hoặc đã bán!"), 409
            seat.status = "held"
            seat.held_by = g.username
            seat.held_until = time.time() + 300 # Giữ ghế trong 5 phút
            db.session.commit()

    order_token = SecurityService.create_order_token(t_type, qty, tt.price, ev.id)

    return jsonify(
        ok=True,
        event_id=ev.id,
        event_title=ev.title,
        ticket_type=t_type,
        ticket_name=tt.name,
        qty=qty,
        unit_price=tt.price,
        total=tt.price * qty,
        token=order_token,
        order_token=order_token,
        seat_id=seat_id,
        expires_in_secs=600
    )

@booking_bp.post("/buy")
@login_required
def api_buy():
    """
    Bước 2 Mua vé: Xác nhận thanh toán & Kiểm tra an ninh Zero Trust
    1. Kiểm tra chữ ký HMAC của Order Token (Chống sửa giá F12)
    2. Kiểm tra Nonce chống Replay
    3. Xác thực mã OTP 2FA giao dịch
    4. Cập nhật tồn kho & tạo vé với mã bí mật TOTP riêng biệt
    """
    data = request.json or {}
    order_token = str(data.get("order_token") or data.get("token") or "").strip()
    method = str(data.get("method", "VietQR")).strip()
    buyer_name = str(data.get("buyer_name") or data.get("name") or "").strip()
    buyer_phone = str(data.get("buyer_phone") or data.get("phone") or "").strip()
    buyer_email = str(data.get("buyer_email") or data.get("email") or "").strip()
    otp_code = str(data.get("otp", "")).strip()
    seat_id = str(data.get("seat_id", "")).strip()

    # 1. Kiểm tra Order Token HMAC (Lớp 3 Zero Trust)
    payload = SecurityService.verify_order_token(order_token)
    if not payload:
        SecurityService.record_audit(
            event="TAMPER_DETECTED",
            detail=f"Phát hiện chữ ký HMAC không hợp lệ hoặc token đã hết hạn từ user {g.username}",
            severity="DANGER",
            user_id=g.uid
        )
        return jsonify(ok=False, msg="CẢNH BÁO BẢO MẬT: Dữ liệu đơn hàng hoặc chữ ký số không hợp lệ! Giao dịch bị từ chối."), 400

    # 2. Kiểm tra Nonce chống Replay Attack
    nonce = payload.get("nonce")
    if not nonce or nonce in USED_NONCES:
        SecurityService.record_audit(
            event="REPLAY_ATTACK",
            detail=f"Phát hiện sử dụng lại token/nonce {nonce} đã thanh toán từ user {g.username}",
            severity="DANGER",
            user_id=g.uid
        )
        return jsonify(ok=False, msg="CẢNH BÁO: Đơn hàng này đã được thanh toán hoặc mã giao dịch đã sử dụng!"), 400

    # 3. Kiểm tra OTP 2FA (Transactional Email OTP hoặc TOTP)
    user = User.query.get(g.uid)
    ok_otp = False
    ok_trans, _ = OTPService.verify_otp(user.email, "payment", otp_code)
    if not ok_trans:
        ok_trans_u, _ = OTPService.verify_otp(user.username, "payment", otp_code)
        if ok_trans_u:
            ok_otp = True
        elif buyer_email:
            ok_trans_b, _ = OTPService.verify_otp(buyer_email, "payment", otp_code)
            if ok_trans_b:
                ok_otp = True
    else:
        ok_otp = True

    # Fallback kiểm tra TOTP Authenticator
    if not ok_otp:
        import pyotp
        totp = pyotp.TOTP(user.otp_secret)
        if totp.verify(otp_code):
            ok_otp = True

    if not ok_otp:
        return jsonify(ok=False, msg="Mã OTP xác nhận thanh toán không chính xác hoặc đã hết hạn (120s)! Vui lòng bấm 'Gửi mã OTP' để nhận mã mới."), 401

    # 4. Kiểm tra và trừ tồn kho
    tt = TicketType.query.filter_by(event_id=payload["event_id"], code=payload["type"]).first()
    if not tt or tt.remaining_stock < payload["qty"]:
        return jsonify(ok=False, msg="Rất tiếc, số lượng vé còn lại không đủ!"), 409

    tt.remaining_stock -= payload["qty"]

    # Đánh dấu Nonce đã sử dụng
    USED_NONCES.add(nonce)

    # Cập nhật ghế đã mua
    if seat_id:
        seat = Seat.query.get(seat_id)
        if seat:
            seat.status = "booked"
            seat.held_by = None
            seat.held_until = 0

    order_id = f"ORD-{secrets.token_hex(4).upper()}"
    new_order = Order(
        order_id=order_id,
        user_id=g.uid,
        event_id=payload["event_id"],
        ticket_type=payload["type"],
        qty=payload["qty"],
        total=payload["total"],
        method=method,
        buyer_name=buyer_name or user.full_name,
        buyer_phone=buyer_phone or user.phone,
        buyer_email=buyer_email or user.email
    )
    db.session.add(new_order)

    # Sinh các vé riêng biệt với ticket_secret độc nhất (Lớp 4 Zero Trust)
    created_ticket_ids = []
    for i in range(payload["qty"]):
        t_id = f"TICK-{secrets.token_hex(4).upper()}"
        ticket_secret = TicketSecurityService.generate_secret()
        s_id = seat_id if (i == 0 and seat_id) else None
        new_ticket = Ticket(
            id=t_id,
            order_id=order_id,
            user_id=g.uid,
            event_id=payload["event_id"],
            ticket_type=payload["type"],
            seat_id=s_id,
            price=payload["unit_price"],
            ticket_secret=ticket_secret,
            used=0,
            status="valid"
        )
        db.session.add(new_ticket)
        created_ticket_ids.append(t_id)

    db.session.commit()

    SecurityService.record_audit(
        event="ORDER_SUCCESS",
        detail=f"Đơn hàng {order_id} thành công: {payload['qty']} vé {payload['type']} = {payload['total']:,}đ",
        severity="INFO",
        user_id=g.uid
    )

    return jsonify(
        ok=True,
        msg="Thanh toán thành công! Vé điện tử bảo mật Zero Trust đã được cấp.",
        order_id=order_id,
        total=payload["total"],
        tickets=created_ticket_ids,
        ticket_ids=created_ticket_ids
    )
