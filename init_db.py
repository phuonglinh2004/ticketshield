import sys
import pyotp
from app import create_app
from app.models import db, User, Event, TicketType, Seat, Order, Ticket, ResellListing, TransactionalOTP, AuditLog
from app.services.security_service import SecurityService
from app.services.totp_service import TicketSecurityService

# Cấu hình UTF-8 cho Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def init_database():
    app = create_app()
    with app.app_context():
        # Xóa các bảng cũ để tái tạo schema đồng bộ
        db.drop_all()
        # Tạo bảng mới trong CSDL (PostgreSQL hoặc SQLite)
        db.create_all()

        # 1. Nạp người dùng mặc định
        users_data = [
            ("linhtran1412", "phuonglinh2k41412@gmail.com", "Trần Ngọc Phương Linh", "0987141288", "123456", "fan"),
            ("fan_a", "fana@ticketbox.demo", "Nguyễn Văn Anh", "0901234567", "123456", "fan"),
            ("fan_b", "fanb@ticketbox.demo", "Trần Thị Bình", "0912345678", "123456", "fan"),
            ("organizer", "btc@ticketbox.demo", "Ban Tổ Chức Superfest", "0988888888", "123456", "organizer"),
            ("admin", "admin@ticketshield.vn", "Quản Trị Viên An Ninh", "0999999999", "admin123", "admin"),
        ]

        user_objects = {}
        for u, email, fn, phone, pw, role in users_data:
            user_obj = User(
                username=u,
                email=email,
                full_name=fn,
                phone=phone,
                password_hash=SecurityService.hash_password(pw),
                otp_secret=pyotp.random_base32(),
                role=role
            )
            db.session.add(user_obj)
            user_objects[u] = user_obj
        db.session.commit()

        # 2. Nạp sự kiện chính (SUPERFEST 2026)
        ev = Event(
            title="SUPERFEST 2026 - Concert Mùa Hè Rực Sáng",
            artist="Sơn Tùng M-TP, Soobin, Wren Evans, MONO, tlinh",
            venue="Quảng trường Sun Carnival, Bãi Cháy, TP. Hạ Long, Quảng Ninh",
            date_str="18:30 - 22:00, 19 Tháng 12, 2026",
            banner_url="https://images.unsplash.com/photo-1470225620780-dba8ba36b745?auto=format&fit=crop&w=1200&q=80",
            description="Đại nhạc hội đỉnh cao quy tụ dàn sao hàng đầu Việt Nam. Nền tảng bán vé ứng dụng Zero Trust Architecture bảo vệ người mua chống phe vé, bot gom vé và vé giả.",
            status="selling"
        )
        db.session.add(ev)
        db.session.commit()

        # 3. Nạp các hạng vé
        ticket_types = [
            TicketType(event_id=ev.id, code="VIP", name="Khu Vực VIP Khán Đài (Có Ghế Ngồi)", price=2000000, total_stock=200, remaining_stock=200, color="#f59e0b"),
            TicketType(event_id=ev.id, code="GA", name="Khu Vực GA Sân Cỏ (Vé Đứng Sát Sân Khấu)", price=800000, total_stock=500, remaining_stock=500, color="#2dc275"),
            TicketType(event_id=ev.id, code="FAST", name="Khu Vực Fast Pass (Cổng Riêng - Hết Vé)", price=1200000, total_stock=50, remaining_stock=0, color="#ec4899"),
        ]
        db.session.add_all(ticket_types)
        db.session.commit()

        # 4. Nạp sơ đồ ghế ngồi khán đài (24 ghế)
        seats = []
        for r in ["A", "B", "C", "D"]:
            for n in range(1, 7):
                sid = f"SEAT-{r}{n:02d}"
                t_type = "VIP" if r in ("A", "B") else "GA"
                # Đặt ghế A01 và A02 đã bán từ trước để minh họa
                initial_status = "booked" if sid in ("SEAT-A01", "SEAT-A02") else "available"
                seats.append(Seat(
                    id=sid,
                    event_id=ev.id,
                    ticket_type=t_type,
                    row_name=r,
                    seat_num=n,
                    status=initial_status,
                    held_until=0
                ))
        db.session.add_all(seats)
        db.session.commit()

        # 5. Nạp vé mẫu cho fan_b trên Chợ Pass vé
        fan_b = User.query.filter_by(username="fan_b").first()
        order_sample = Order(
            order_id="ORD-SAMPLE-FANB",
            user_id=fan_b.id,
            event_id=ev.id,
            ticket_type="VIP",
            qty=1,
            total=2000000,
            method="VNPAY",
            buyer_name=fan_b.full_name,
            buyer_phone=fan_b.phone,
            buyer_email=fan_b.email
        )
        db.session.add(order_sample)
        db.session.commit()

        ticket_sample = Ticket(
            id="TICK-FANB-VIP1",
            order_id=order_sample.order_id,
            user_id=fan_b.id,
            event_id=ev.id,
            ticket_type="VIP",
            seat_id="SEAT-A02",
            price=2000000,
            ticket_secret=TicketSecurityService.generate_secret(),
            used=0,
            status="reselling"
        )
        db.session.add(ticket_sample)
        db.session.commit()

        resell_sample = ResellListing(
            ticket_id=ticket_sample.id,
            seller_id=fan_b.id,
            original_price=2000000,
            resell_price=1900000,
            status="active"
        )
        db.session.add(resell_sample)
        db.session.commit()

        print("[+] Khởi tạo CSDL thành công theo mô hình MVC / Blueprints / SQLAlchemy!")
        print(f"    - CSDL đang dùng: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print("    - Tài khoản demo: linhtran1412 (pw: 123456), fan_a (pw: 123456), fan_b (pw: 123456), admin")
        print("    - Bảng OTP giao dịch: transactional_otps (băm SHA-256, hạn 120s)")
        print("    - Sự kiện: SUPERFEST 2026")
        print("    - Hạng vé: VIP (2.000.000đ), GA (800.000đ), FAST (0 còn lại - hết vé)")
        print("    - Chợ Pass vé: Đã có sẵn 1 vé VIP pass giá 1.900.000đ từ fan_b")

init = init_database

if __name__ == "__main__":
    init_database()
