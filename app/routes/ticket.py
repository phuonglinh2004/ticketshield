import time
import secrets
from flask import Blueprint, request, jsonify, g
from app.models import db, Ticket, User, ResellListing, TicketType
from app.services.security_service import SecurityService
from app.services.totp_service import TicketSecurityService
from app.services.otp_service import OTPService
from app.routes.auth import login_required
from config import Config

ticket_bp = Blueprint("ticket", __name__)

@ticket_bp.get("/my-tickets")
@login_required
def api_my_tickets():
    """Lấy danh sách vé đã mua của người dùng hiện tại"""
    tickets = Ticket.query.filter_by(user_id=g.uid).order_by(Ticket.created_at.desc()).all()
    return jsonify(
        ok=True,
        tickets=[t.to_dict() for t in tickets]
    )

@ticket_bp.get("/tickets/<ticket_id>/qr")
@login_required
def api_ticket_qr(ticket_id):
    """
    Sinh mã QR động TOTP (RFC 6238) đổi mỗi 15 giây
    - Kết hợp ticket_secret + timestamp hiện tại
    - Ngăn chặn triệt để hành vi chụp ảnh màn hình bán lại (Replay Attack)
    """
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify(ok=False, msg="Không tìm thấy vé"), 404

    if ticket.user_id != g.uid and g.role != "admin":
        return jsonify(ok=False, msg="Bạn không có quyền truy cập vé này"), 403

    if ticket.used:
        return jsonify(
            ok=False,
            msg=f"Vé này đã được quét vào cổng lúc {ticket.used_at}!",
            used=True
        ), 400

    if ticket.status != "valid":
        return jsonify(ok=False, msg=f"Vé này không còn khả dụng (Trạng thái: {ticket.status})!"), 400

    interval = Config.TOTP_INTERVAL
    current_totp = TicketSecurityService.get_current_totp(ticket.ticket_secret, interval=interval)
    now = int(time.time())
    exp_in = interval - (now % interval)

    # Chuỗi payload quét tại cổng: ticket_id:totp_code
    payload_str = f"{ticket.id}:{current_totp}"
    qr_img = TicketSecurityService.render_qr_base64(payload_str)

    return jsonify(
        ok=True,
        ticket_id=ticket.id,
        current_totp=current_totp,
        exp_in=exp_in,
        interval=interval,
        payload=payload_str,
        qr_image=qr_img
    )

@ticket_bp.post("/gift")
@login_required
def api_gift_ticket():
    """Tặng vé an toàn: Thu hồi vé cũ và cấp mã vé mới toanh cho người nhận"""
    data = request.json or {}
    ticket_id = str(data.get("ticket_id", "")).strip()
    recipient_ident = str(data.get("recipient", "")).strip().lower()

    ticket = Ticket.query.get(ticket_id)
    if not ticket or ticket.user_id != g.uid:
        return jsonify(ok=False, msg="Không tìm thấy vé hoặc bạn không phải chủ sở hữu"), 404

    if ticket.used or ticket.status != "valid":
        return jsonify(ok=False, msg="Vé đã sử dụng hoặc đang chờ xử lý, không thể tặng!"), 400

    recipient = User.query.filter((User.username == recipient_ident) | (User.email == recipient_ident)).first()
    if not recipient:
        return jsonify(ok=False, msg="Không tìm thấy tài khoản người nhận trên hệ thống"), 404

    if recipient.id == g.uid:
        return jsonify(ok=False, msg="Không thể tự tặng vé cho chính mình"), 400

    # Vô hiệu hóa vé cũ để ngăn chủ cũ chụp ảnh gian lận
    ticket.status = "gifted"

    # Cấp vé mới với khóa bí mật hoàn toàn mới cho người nhận
    new_tid = f"TICK-{secrets.token_hex(4).upper()}"
    new_secret = TicketSecurityService.generate_secret()
    new_ticket = Ticket(
        id=new_tid,
        order_id=ticket.order_id,
        user_id=recipient.id,
        event_id=ticket.event_id,
        ticket_type=ticket.ticket_type,
        seat_id=ticket.seat_id,
        price=ticket.price,
        ticket_secret=new_secret,
        used=0,
        status="valid"
    )
    db.session.add(new_ticket)
    db.session.commit()

    SecurityService.record_audit(
        event="TICKET_GIFTED",
        detail=f"Vé {ticket_id} được tặng cho {recipient.username}. Đã cấp mã mới {new_tid}",
        severity="INFO",
        user_id=g.uid
    )

    return jsonify(
        ok=True,
        msg=f"Tặng vé thành công cho tài khoản '{recipient.username}'. Vé cũ đã bị vô hiệu hóa!",
        new_ticket_id=new_tid
    )

@ticket_bp.post("/resell/list")
@login_required
def api_resell_list():
    """Đăng bán vé lại trên Chợ Pass vé Ticketbox (Kiểm soát trần giá chống đầu cơ)"""
    data = request.json or {}
    ticket_id = str(data.get("ticket_id", "")).strip()
    resell_price = int(data.get("resell_price", 0))

    ticket = Ticket.query.get(ticket_id)
    if not ticket or ticket.user_id != g.uid:
        return jsonify(ok=False, msg="Vé không hợp lệ hoặc bạn không phải chủ sở hữu"), 404

    if ticket.used or ticket.status != "valid":
        return jsonify(ok=False, msg="Vé đã sử dụng hoặc đang ở trạng thái không thể bán"), 400

    # Quy chế Ticketbox: Giá bán lại không được vượt quá giá gốc
    if resell_price > ticket.price:
        return jsonify(ok=False, msg=f"Giá pass vé tối đa bằng giá gốc ({ticket.price:,}đ) theo quy chế sàn!"), 400

    if resell_price <= 0:
        return jsonify(ok=False, msg="Giá vé không hợp lệ"), 400

    ticket.status = "reselling"
    listing = ResellListing(
        ticket_id=ticket.id,
        seller_id=g.uid,
        original_price=ticket.price,
        resell_price=resell_price,
        status="active"
    )
    db.session.add(listing)
    db.session.commit()

    SecurityService.record_audit(
        event="RESELL_LISTED",
        detail=f"Vé {ticket_id} được đăng pass với giá {resell_price:,}đ",
        severity="INFO",
        user_id=g.uid
    )

    return jsonify(ok=True, msg="Đăng bán vé thành công trên Chợ Vé Chuyển Nhượng!")

@ticket_bp.get("/resell/listings")
def api_resell_listings():
    """Lấy danh sách các vé đang được pass hợp lệ trên sàn"""
    listings = ResellListing.query.filter_by(status="active").order_by(ResellListing.created_at.desc()).all()
    results = []
    for item in listings:
        t = item.ticket
        ev = t.event if t else None
        results.append({
            "id": item.id,
            "ticket_id": item.ticket_id,
            "ticket_type": t.ticket_type if t else "VIP",
            "type_name": t.ticket_type if t else "VIP",
            "event_title": ev.title if ev else "Concert Ticketbox",
            "date_str": ev.date_str if ev else "",
            "seller_name": item.seller.full_name if item.seller else "Thành viên",
            "original_price": item.original_price,
            "resell_price": item.resell_price
        })
    return jsonify(ok=True, listings=results)

@ticket_bp.post("/resell/buy")
@login_required
def api_resell_buy():
    """Mua vé pass an toàn: Thu hồi vé cũ của người bán, cấp vé mới cho người mua"""
    data = request.json or {}
    listing_id = int(data.get("listing_id", 0))
    otp_code = str(data.get("otp", "")).strip()

    listing = ResellListing.query.get(listing_id)
    if not listing or listing.status != "active":
        return jsonify(ok=False, msg="Vé này đã được mua hoặc không còn mở bán"), 404

    if listing.seller_id == g.uid:
        return jsonify(ok=False, msg="Bạn không thể mua lại chính vé của mình!"), 400

    # Xác thực OTP người mua
    user = User.query.get(g.uid)
    ok_otp, _ = OTPService.verify_otp(user.username, "payment", otp_code)
    if not ok_otp:
        ok_otp, _ = OTPService.verify_otp(user.email, "payment", otp_code)
    if not ok_otp:
        import pyotp
        totp = pyotp.TOTP(user.otp_secret)
        if totp.verify(otp_code):
            ok_otp = True

    if not ok_otp:
        return jsonify(ok=False, msg="Mã OTP 2FA không chính xác hoặc đã hết hạn!"), 401

    old_ticket = listing.ticket
    old_ticket.status = "resold"
    listing.status = "sold"

    # Cấp vé mới tinh cho người mua mới
    new_tid = f"TICK-{secrets.token_hex(4).upper()}"
    new_secret = TicketSecurityService.generate_secret()
    new_ticket = Ticket(
        id=new_tid,
        order_id=old_ticket.order_id,
        user_id=g.uid,
        event_id=old_ticket.event_id,
        ticket_type=old_ticket.ticket_type,
        seat_id=old_ticket.seat_id,
        price=listing.resell_price,
        ticket_secret=new_secret,
        used=0,
        status="valid"
    )
    db.session.add(new_ticket)
    db.session.commit()

    SecurityService.record_audit(
        event="RESELL_BOUGHT",
        detail=f"Vé pass {old_ticket.id} đã được bán cho {user.username}. Cấp mã mới: {new_tid}",
        severity="INFO",
        user_id=g.uid
    )

    return jsonify(
        ok=True,
        msg="Mua vé chuyển nhượng thành công! Vé đã được chuyển sang tài khoản của bạn.",
        new_ticket_id=new_tid
    )
