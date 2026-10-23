import sys
from app import create_app

# Cấu hình UTF-8 cho Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

app = create_app()

if __name__ == "__main__":
    print("================================================================")
    print(" 🚀 KHỞI CHẠY MÁY CHỦ TICKETSHIELD - MÔ HÌNH MVC / BLUEPRINTS")
    print(" 🛡️ KIẾN TRÚC ZERO TRUST BẢO VỆ VÉ CONCERT TRỰC TUYẾN")
    print(" 🌐 URL TRANG CHỦ : http://127.0.0.1:5000")
    print(" ⚡ CỔNG SOÁT VÉ  : http://127.0.0.1:5000/gate")
    print("================================================================")
    app.run(host="127.0.0.1", port=5000, debug=False)
