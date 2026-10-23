import pyotp
import qrcode
import io
import base64

class TicketSecurityService:
    @staticmethod
    def generate_secret():
        """Tạo khóa bí mật ngẫu nhiên (Base32) duy nhất cho từng chiếc vé khi thanh toán xong"""
        return pyotp.random_base32()

    @staticmethod
    def get_current_totp(secret, interval=15):
        """Frontend gọi API để lấy mã cập nhật cho mã QR mỗi 15 giây (RFC 6238)"""
        totp = pyotp.TOTP(secret, interval=interval)
        return totp.now()

    @staticmethod
    def verify_ticket_qr(secret, client_totp_code, interval=15):
        """
        Cổng soát vé kiểm chứng mã quét được:
        valid_window=0 kiểm soát nghiêm ngặt chu kỳ 15 giây, chống chụp ảnh màn hình cũ (Replay Attack)
        """
        try:
            totp = pyotp.TOTP(secret, interval=interval)
            return totp.verify(str(client_totp_code).strip(), valid_window=0)
        except Exception:
            return False

    @staticmethod
    def render_qr_base64(payload_string):
        """Tạo ảnh PNG mã QR dạng base64 để hiển thị trực tiếp trên web"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(payload_string)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#000000", back_color="#ffffff")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
