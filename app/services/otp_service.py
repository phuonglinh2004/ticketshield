import time
import secrets
import hashlib
from app.models import db, TransactionalOTP, User
from app.services.security_service import SecurityService, LOGIN_FAILS
from app.services.email_service import EmailService

class OTPService:
    @staticmethod
    def generate_and_send_otp(target: str, action: str = "login"):
        """
        Sinh OTP 6 số, băm SHA-256 lưu vào DB (120s hạn),
        và gửi email thật nếu có email hợp lệ.
        """
        target = str(target).strip().lower()
        action = str(action).strip().lower()

        recipient_email = target if "@" in target else None
        full_name = "Quý khách"

        if target in ("linhtran1412", "phuonglinh2k41412@gmail.com"):
            recipient_email = "phuonglinh2k41412@gmail.com"
            full_name = "Trần Ngọc Phương Linh"
        else:
            u = User.query.filter((User.username == target) | (User.email == target) | (User.phone == target)).first()
            if u:
                recipient_email = u.email
                full_name = u.full_name or full_name

        # Sinh mã 6 chữ số
        otp_code = f"{secrets.randbelow(900000) + 100000}"
        otp_hash = hashlib.sha256(otp_code.encode("utf-8")).hexdigest()
        expiry_time = time.time() + 120 # 120 giây (2 phút)

        # Xóa các OTP cũ cùng target & action
        TransactionalOTP.query.filter_by(target=target, action=action).delete()

        # Tạo bản ghi mới cho target
        otp_entry = TransactionalOTP(
            target=target,
            action=action,
            otp_hash=otp_hash,
            demo_code=otp_code,
            expiry_time=expiry_time,
            fail_count=0
        )
        db.session.add(otp_entry)

        # Nếu target khác recipient_email, lưu đồng bộ cho recipient_email
        if recipient_email and recipient_email != target:
            TransactionalOTP.query.filter_by(target=recipient_email, action=action).delete()
            sync_entry = TransactionalOTP(
                target=recipient_email,
                action=action,
                otp_hash=otp_hash,
                demo_code=otp_code,
                expiry_time=expiry_time,
                fail_count=0
            )
            db.session.add(sync_entry)

        db.session.commit()

        # Kích hoạt gửi email thật
        if recipient_email and "@" in recipient_email:
            EmailService.send_otp_email_async(recipient_email, otp_code, action, full_name)

        SecurityService.record_audit(
            event="OTP_SENT",
            detail=f"Đã phát sinh OTP 6 số (SHA-256 băm) cho {target} -> Email: {recipient_email or target} (Hành động: {action}, Hạn: 120s)",
            severity="INFO"
        )

        return {
            "otp_code": otp_code,
            "recipient_email": recipient_email or target,
            "expiry_time": expiry_time
        }

    @staticmethod
    def verify_otp(target: str, action: str, input_code: str):
        """
        Xác thực OTP giao dịch:
        - Kiểm tra hạn 120s
        - Kiểm tra Brute-Force (quá 3 lần nhập sai hủy ngay)
        - So khớp mã băm SHA-256
        - Thành công: Xóa OTP (One-Time Use)
        """
        target = str(target).strip().lower()
        input_code = str(input_code).strip()
        if not input_code:
            return False, "Vui lòng nhập mã OTP 6 số"

        # Tra cứu bản ghi
        row = TransactionalOTP.query.filter_by(target=target, action=action).order_by(TransactionalOTP.id.desc()).first()
        if not row:
            # Tra cứu chéo qua user nếu target là username/email
            user = User.query.filter((User.username == target) | (User.email == target)).first()
            if user:
                alt_target = user.email if target == user.username else user.username
                row = TransactionalOTP.query.filter_by(target=alt_target, action=action).order_by(TransactionalOTP.id.desc()).first()

        if not row:
            return False, "Không tìm thấy mã OTP hoặc bạn chưa bấm 'Gửi mã OTP'!"

        # 1. Kiểm tra hạn dùng (120s)
        if time.time() > row.expiry_time:
            db.session.delete(row)
            db.session.commit()
            SecurityService.record_audit("OTP_EXPIRED", f"Mã OTP của {target} đã hết hạn hiệu lực 120s", "WARNING")
            return False, "Mã OTP đã hết hạn hiệu lực (quá 120 giây)! Vui lòng nhấn gửi lại mã mới."

        # 2. Kiểm tra Brute-Force (quá 3 lần nhập sai)
        if row.fail_count >= 3:
            db.session.delete(row)
            db.session.commit()
            SecurityService.record_audit("OTP_BRUTEFORCE", f"Mã OTP của {target} bị hủy do nhập sai quá 3 lần", "DANGER")
            return False, "Mã OTP đã bị vô hiệu hóa do nhập sai quá 3 lần để bảo vệ an toàn!"

        # 3. So khớp hash SHA-256
        input_hash = hashlib.sha256(input_code.encode("utf-8")).hexdigest()
        if input_hash != row.otp_hash:
            row.fail_count += 1
            db.session.commit()
            remaining = 3 - row.fail_count
            return False, f"Mã OTP không chính xác! (Còn {max(0, remaining)} lần thử)"

        # Khớp thành công -> Xóa ngay lập tức (One-Time Use)
        db.session.delete(row)
        db.session.commit()
        return True, "Xác thực thành công"
