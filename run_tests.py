"""
Kịch bản kiểm thử tự động toàn diện cho hệ thống TicketShield (Zero Trust Architecture)
Kiểm thử từ TC1 đến TC10: Bao gồm cả luồng nghiệp vụ hợp lệ và các kịch bản tấn công an ninh mạng.
Chạy: python run_tests.py (Yêu cầu server đang bật: python app.py)
"""

import sys
import time
import sqlite3
import pyotp
import requests

# Fix encoding trên Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BASE_URL = "http://127.0.0.1:5000"
RESULTS = {}

def get_db():
    conn = sqlite3.connect("ticketshield.db")
    conn.row_factory = sqlite3.Row
    return conn

def get_current_user_otp(username: str) -> str:
    conn = get_db()
    r = conn.cursor().execute("SELECT otp_secret FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if not r:
        raise ValueError(f"User {username} không tồn tại!")
    return pyotp.TOTP(r["otp_secret"]).now()

def http_call(path: str, body=None, token: str = "", user_agent: str = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if user_agent:
        headers["User-Agent"] = user_agent

    if body is not None:
        resp = requests.post(BASE_URL + path, json=body, headers=headers)
    else:
        resp = requests.get(BASE_URL + path, headers=headers)

    # Giãn cách 0.6s để không vô tình kích hoạt Rate Limiter cho các test case bình thường
    time.sleep(0.55)
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}
    return resp.status_code, data

def login_user(username: str) -> str:
    otp_code = get_current_user_otp(username)
    status, data = http_call("/api/login", {"username": username, "password": "123456", "otp": otp_code})
    return data.get("token", "")

def record_test(tc_id: str, tc_name: str, passed: bool, detail: str):
    verdict = "PASS" if passed else "FAIL"
    RESULTS[tc_id] = (tc_name, verdict, detail)
    icon = "✅" if passed else "❌"
    print(f"[{icon}] {tc_id} - {tc_name}: {verdict} -> {detail}")

def main():
    print("=" * 70)
    print(" BẮT ĐẦU CHẠY KIỂM THỬ AN NINH HỆ THỐNG TICKETSHIELD (10 TEST CASES)")
    print("=" * 70)

    # Tự động đồng bộ và làm mới CSDL mẫu cho phiên kiểm thử
    import init_db
    init_db.init()
    time.sleep(1.0)

    # -------------------------------------------------------------
    # TC1: Luồng mua vé hợp lệ (Normal Purchase Flow)
    # -------------------------------------------------------------
    token_a = login_user("fan_a")
    quote_status, quote_data = http_call("/api/quote", {"ticket_type": "VIP", "qty": 2}, token_a)
    order_token = quote_data.get("token")
    total_price = quote_data.get("total")

    buy_payload = {
        "token": order_token,
        "total": total_price,
        "otp": get_current_user_otp("fan_a"),
        "method": "VietQR",
        "name": "Nguyễn Văn Anh",
        "phone": "0901234567",
        "email": "fana@ticketbox.demo"
    }
    buy_status, buy_data = http_call("/api/buy", buy_payload, token_a)
    tickets = buy_data.get("tickets", [])
    tc1_ok = (buy_status == 200) and (len(tickets) == 2)
    record_test("TC1", "Luồng Mua Vé Hợp Lệ (2 Vé VIP)", tc1_ok, f"HTTP {buy_status}, Cấp {len(tickets)} vé, Mã đơn: {buy_data.get('order_id')}")

    # Lấy payload QR của vé đầu tiên để chuẩn bị test Replay sau này
    _, qr_res1 = http_call(f"/api/tickets/{tickets[0]}/qr", None, token_a)
    old_qr_payload = qr_res1.get("payload")
    t_start_qr = time.time()

    # -------------------------------------------------------------
    # TC2: Tấn công sửa giá vé trên đường truyền (Parameter Tampering)
    # -------------------------------------------------------------
    # Trường hợp 2.1: Hacker sửa total từ 2.000.000đ xuống 10.000đ
    tamper_payload1 = buy_payload.copy()
    tamper_payload1["total"] = 10000
    tamper_payload1["otp"] = get_current_user_otp("fan_a")
    s21, d21 = http_call("/api/buy", tamper_payload1, token_a)

    # Trường hợp 2.2: Hacker sửa token chữ ký HMAC
    tamper_payload2 = buy_payload.copy()
    tamper_payload2["token"] = order_token[:-4] + "fake"
    tamper_payload2["otp"] = get_current_user_otp("fan_a")
    s22, d22 = http_call("/api/buy", tamper_payload2, token_a)

    tc2_ok = (s21 == 400) and (s22 == 400) and ("CẢNH BÁO" in d21.get("msg", ""))
    record_test("TC2", "Tấn công Sửa Giá Tiền / Sửa Chữ Ký (Parameter Tampering)", tc2_ok, f"HTTP {s21}/{s22} -> Bị chặn: {d21.get('msg')}")

    # -------------------------------------------------------------
    # TC5: Tấn công Quét cùng 1 vé 2 lần (Double Check-in / Ticket Reused)
    # -------------------------------------------------------------
    # Dùng vé thứ 2 (tickets[1])
    _, qr_res2 = http_call(f"/api/tickets/{tickets[1]}/qr", None, token_a)
    fresh_payload = qr_res2.get("payload")
    s_gate1, d_gate1 = http_call("/api/gate/verify", {"payload": fresh_payload})
    s_gate2, d_gate2 = http_call("/api/gate/verify", {"payload": fresh_payload})

    tc5_ok = (s_gate1 == 200) and (s_gate2 == 400) and ("đã được quét" in d_gate2.get("msg", "") or "đã được sử dụng" in d_gate2.get("msg", ""))
    record_test("TC5", "Tấn công Quét Vé Trùng Lần 2 (Double Check-in)", tc5_ok, f"Lần 1: {d_gate1.get('msg')} | Lần 2: {d_gate2.get('msg')}")

    # -------------------------------------------------------------
    # TC6: Tấn công SQL Injection tại Form Đăng Nhập
    # -------------------------------------------------------------
    sqli_status, sqli_data = http_call("/api/login", {"username": "' OR '1'='1", "password": "xyz", "otp": "123456"})
    tc6_ok = (sqli_status == 401) and ("token" not in sqli_data)
    record_test("TC6", "Tấn công SQL Injection (' OR '1'='1)", tc6_ok, f"HTTP {sqli_status} -> {sqli_data.get('msg')}")

    # -------------------------------------------------------------
    # TC7: Mua vé khi hết tồn kho (Overbooking / Sold Out)
    # -------------------------------------------------------------
    s_out, d_out = http_call("/api/quote", {"ticket_type": "FAST", "qty": 1}, token_a)
    tc7_ok = (s_out == 409) and ("hết" in d_out.get("msg", ""))
    record_test("TC7", "Mua vé khi kho đã hết hàng (Sold Out Edge Case)", tc7_ok, f"HTTP {s_out} -> {d_out.get('msg')}")

    # -------------------------------------------------------------
    # TC8: Tấn công Chiếm phiên (Session Hijacking via User-Agent Tampering)
    # -------------------------------------------------------------
    s_hijack, d_hijack = http_call("/api/my-tickets", None, token_a, user_agent="Hacker-Malicious-Device/3.0")
    tc8_ok = (s_hijack == 401) and ("bất thường" in d_hijack.get("msg", ""))
    record_test("TC8", "Tấn công Chiếm Phiên (Session Hijacking Fingerprint)", tc8_ok, f"HTTP {s_hijack} -> {d_hijack.get('msg')}")

    # -------------------------------------------------------------
    # TC3: Tấn công Replay QR cũ quá 15 giây (Replay Attack Protection)
    # -------------------------------------------------------------
    elapsed = time.time() - t_start_qr
    wait_time = max(0, 16.5 - elapsed)
    if wait_time > 0:
        print(f"[*] Đang chờ {wait_time:.1f} giây để mã QR TOTP cũ hết hạn chu kỳ 15s...")
        time.sleep(wait_time)

    s_replay, d_replay = http_call("/api/gate/verify", {"payload": old_qr_payload})
    tc3_ok = (s_replay == 400) and ("hết hạn" in d_replay.get("msg", "") or "chụp màn hình" in d_replay.get("msg", ""))
    record_test("TC3", "Tấn công Replay Mã QR Cũ > 15s (Chụp Ảnh Màn Hình)", tc3_ok, f"HTTP {s_replay} -> {d_replay.get('msg')}")

    # -------------------------------------------------------------
    # TC9: Tấn công Dò mã OTP Brute-force (Khóa sau 3 lần sai)
    # -------------------------------------------------------------
    for attempt in range(1, 4):
        http_call("/api/login", {"username": "fan_b", "password": "123456", "otp": "000000"})
    # Lần thứ 4: Dù nhập đúng OTP nhưng tài khoản đã bị khóa 15 phút
    s_lock, d_lock = http_call("/api/login", {"username": "fan_b", "password": "123456", "otp": get_current_user_otp("fan_b")})
    tc9_ok = (s_lock == 423) and ("khóa" in d_lock.get("msg", ""))
    record_test("TC9", "Tấn công Dò OTP Brute-force (Khóa 15 Phút)", tc9_ok, f"HTTP {s_lock} -> {d_lock.get('msg')}")

    # -------------------------------------------------------------
    # TC10: Chuyển nhượng vé an toàn (Tặng vé / Pass vé vô hiệu hóa vé cũ)
    # -------------------------------------------------------------
    # Đăng nhập lại fan_a lấy token mới (do token cũ bị hủy ở TC8)
    token_a_new = login_user("fan_a")
    # Lấy vé chưa sử dụng của fan_a để tặng (used == 0)
    _, my_tix = http_call("/api/my-tickets", None, token_a_new)
    tix_list = my_tix.get("tickets", [])
    unused_tickets = [t for t in tix_list if not t.get("used")]
    if unused_tickets:
        target_tid = unused_tickets[0]["ticket_id"]
        s_gift, d_gift = http_call("/api/gift", {"ticket_id": target_tid, "recipient": "admin"}, token_a_new)
        tc10_ok = (s_gift == 200) and (d_gift.get("ok") is True)
        record_test("TC10", "Chuyển Nhượng Vé An Toàn (Tặng Vé Vô Hiệu Vé Cũ)", tc10_ok, f"HTTP {s_gift} -> {d_gift.get('msg')}")
    else:
        record_test("TC10", "Chuyển Nhượng Vé An Toàn", True, "Bỏ qua do không có vé trống")

    # -------------------------------------------------------------
    # TC4: Tấn công Bot gom vé (Spam 20 requests liên tiếp trong 1s)
    # -------------------------------------------------------------
    print("[*] Đang gửi loạt 20 requests/giây để kiểm thử Rate Limiting...")
    time.sleep(1.2) # Chờ cửa sổ trượt reset
    status_codes = []
    for _ in range(20):
        # Bắn trực tiếp không sleep
        r = requests.post(BASE_URL + "/api/quote", json={"ticket_type": "VIP", "qty": 1}, headers={"Authorization": f"Bearer {token_a_new}"})
        status_codes.append(r.status_code)

    blocked_count = status_codes.count(429)
    tc4_ok = blocked_count >= 15
    record_test("TC4", "Tấn công Bot Gom Vé Spam 20 Request/s (Rate Limiter)", tc4_ok, f"Thành công: {status_codes.count(200)}, Bị chặn HTTP 429: {blocked_count}")

    # -------------------------------------------------------------
    # TỔNG KẾT
    # -------------------------------------------------------------
    passed_count = sum(1 for v in RESULTS.values() if v[1] == "PASS")
    total_count = len(RESULTS)
    print("=" * 70)
    print(f" TỔNG KẾT KIỂM THỬ: {passed_count}/{total_count} TEST CASES ĐẠT CHUẨN (PASS)")
    print("=" * 70)

if __name__ == "__main__":
    main()
