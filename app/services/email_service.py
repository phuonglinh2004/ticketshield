import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

class EmailService:
    @staticmethod
    def send_otp_email_async(to_email: str, otp_code: str, action: str = "login", full_name: str = "Quý khách"):
        """Gửi email thật qua SMTP trong luồng nền (non-blocking)"""
        smtp_user = os.getenv("SMTP_USER", "").strip()
        smtp_pass = os.getenv("SMTP_PASS", "").strip()
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com").strip()
        try:
            smtp_port = int(os.getenv("SMTP_PORT", "465"))
        except Exception:
            smtp_port = 465

        if not smtp_user or not smtp_pass:
            print(f"[*] [SMTP INFO] Chưa cấu hình SMTP_USER/SMTP_PASS. Mã OTP gửi đến {to_email} là: {otp_code}")
            return False, "Chưa cấu hình tài khoản gửi SMTP"

        def _worker():
            try:
                action_map = {
                    "login": "Đăng nhập tài khoản",
                    "register": "Đăng ký thành viên mới",
                    "payment": "Xác nhận thanh toán đơn hàng"
                }
                action_title = action_map.get(action, "Xác thực danh tính")
                subject = f"[{otp_code}] Mã xác thực OTP Ticketbox ({action_title})"

                html = f"""
                <!DOCTYPE html>
                <html>
                <head><meta charset="utf-8"></head>
                <body style="margin:0; padding:0; background:#0b0e14; font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif; color:#e6edf3;">
                  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0b0e14; padding:30px 10px;">
                    <tr>
                      <td align="center">
                        <table width="520" cellpadding="0" cellspacing="0" style="background:#161b22; border-radius:12px; border:1px solid #30363d; overflow:hidden;">
                          <tr>
                            <td style="background: linear-gradient(135deg, #0e1117 0%, #161b22 100%); padding: 24px; border-bottom: 2px solid #2dc275; text-align:center;">
                              <h1 style="margin:0; font-size:28px; font-weight:800; color:#fff; letter-spacing:-0.5px;">
                                ticket<span style="color:#2dc275;">box</span>
                              </h1>
                              <div style="color:#8b949e; font-size:12px; margin-top:4px;">NỀN TẢNG BÁN VÉ AN TOÀN TICKETSHIELD</div>
                            </td>
                          </tr>
                          <tr>
                            <td style="padding: 30px 24px;">
                              <p style="font-size:15px; margin:0 0 12px 0; color:#c9d1d9;">Xin chào <b>{full_name}</b>,</p>
                              <p style="font-size:14px; margin:0 0 20px 0; color:#8b949e; line-height:1.6;">
                                Bạn vừa thực hiện yêu cầu <b>{action_title}</b> trên hệ thống Ticketbox. Vui lòng sử dụng mã xác thực bảo mật bên dưới để hoàn tất:
                              </p>
                              <div style="background:#0d1117; border:2px dashed #2dc275; border-radius:10px; padding:20px; text-align:center; margin:24px 0;">
                                <div style="font-size:12px; color:#8b949e; letter-spacing:1px; margin-bottom:6px;">MÃ XÁC THỰC OTP (SHA-256 SECURED)</div>
                                <div style="font-size:36px; font-weight:bold; letter-spacing:8px; color:#2dc275; font-family:Consolas, monospace;">{otp_code}</div>
                                <div style="font-size:11px; color:#f85149; margin-top:8px;">⏱️ Hiệu lực trong 120 giây (2 phút)</div>
                              </div>
                              <div style="background:#21262d; border-radius:8px; padding:12px 16px; font-size:12px; color:#8b949e; line-height:1.5;">
                                🔒 <b>Cơ chế an toàn Zero Trust:</b><br>
                                • Server lưu mã dưới dạng băm <b>SHA-256</b> (không lưu số thô).<br>
                                • Mã tự hủy sau 1 lần xác thực hoặc nếu nhập sai quá 3 lần.<br>
                                • Tuyệt đối không chia sẻ mã này cho bất kỳ ai.
                              </div>
                            </td>
                          </tr>
                          <tr>
                            <td style="background:#0e1117; padding:16px; text-align:center; font-size:11px; color:#6e7681; border-top:1px solid #21262d;">
                              © 2026 Ticketbox Co., Ltd. Tất cả quyền được bảo lưu.
                            </td>
                          </tr>
                        </table>
                      </td>
                    </tr>
                  </table>
                </body>
                </html>
                """

                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"TicketShield Ticketbox <{smtp_user}>"
                msg["To"] = to_email
                msg.attach(MIMEText(html, "html", "utf-8"))

                if smtp_port == 465:
                    with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10) as s:
                        s.login(smtp_user, smtp_pass)
                        s.sendmail(smtp_user, [to_email], msg.as_string())
                else:
                    with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as s:
                        s.starttls()
                        s.login(smtp_user, smtp_pass)
                        s.sendmail(smtp_user, [to_email], msg.as_string())

                print(f"[+] [SMTP REAL EMAIL] ĐÃ GỬI MÃ OTP {otp_code} THÀNH CÔNG ĐẾN {to_email}")
            except Exception as ex:
                print(f"[-] [SMTP ERROR] Gửi email thất bại đến {to_email}: {ex}")

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return True, "Đang gửi email..."
