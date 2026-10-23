
    // Trạng thái ứng dụng toàn cục (App State)
    const STATE = {
      token: localStorage.getItem('ts_token') || null,
      user: JSON.parse(localStorage.getItem('ts_user') || 'null'),
      event: null,
      ticketTypes: [],
      seats: [],
      selectedType: null,
      selectedQty: 0,
      selectedSeatId: null,
      totalAmount: 0,
      orderToken: null,
      activeTimers: [],
      myTicketsList: []
    };

    const $ = id => document.getElementById(id);
    const formatVND = num => (num || 0).toLocaleString('vi-VN') + ' đ';

    // Hiển thị thông báo Banner Flash
    function showAlert(msg, isOk = true, duration = 6000) {
      const banner = $('alert-banner');
      banner.className = isOk ? 'ok' : 'err';
      banner.textContent = msg;
      banner.style.display = 'block';
      clearTimeout(banner._timer);
      banner._timer = setTimeout(() => { banner.style.display = 'none'; }, duration);
    }

    // Helper gọi API chuẩn RESTful có gắn kèm Bearer Token
    async function apiRequest(endpoint, options = {}) {
      const headers = { 'Content-Type': 'application/json' };
      if (STATE.token) headers['Authorization'] = 'Bearer ' + STATE.token;

      const fetchOpts = {
        method: options.method || 'GET',
        headers: headers
      };
      if (options.body) fetchOpts.body = JSON.stringify(options.body);

      try {
        const resp = await fetch(endpoint, fetchOpts);
        const data = await resp.json();
        if (!data.ok && data.msg) {
          showAlert(data.msg, false);
        }
        return { status: resp.status, data };
      } catch (err) {
        showAlert('Lỗi kết nối máy chủ hoặc sự cố mạng!', false);
        return { status: 500, data: { ok: false, msg: err.message } };
      }
    }

    // Xóa toàn bộ timer đếm ngược khi chuyển trang
    function clearAppTimers() {
      STATE.activeTimers.forEach(clearInterval);
      STATE.activeTimers = [];
    }

    // ================= QUẢN LÝ TÀI KHOẢN (AUTH) =================
    function updateAuthUI() {
      const box = $('auth-box');
      if (STATE.user && STATE.token) {
        const role = (STATE.user.role || 'fan').toUpperCase();
        box.innerHTML = `
          <div style="display: flex; align-items: center; gap: 12px;">
            <span style="font-weight: 700; color: #fff;">👤 ${STATE.user.full_name || STATE.user.username}</span>
            <span style="background: rgba(45,194,117,0.2); color: var(--tb-green); padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight:700;">
              ${role}
            </span>
            <button class="btn-secondary" style="padding: 4px 10px; font-size: 12px;" onclick="doLogout()">Đăng xuất</button>
          </div>
        `;
      } else {
        box.innerHTML = `
          <button class="btn-auth-user" onclick="openAuthModal('login')">
            <span>👤</span> Đăng nhập | Đăng ký
          </button>
        `;
      }
    }

    function openAuthModal(mode = 'login') {
      $('auth-modal').classList.remove('hide');
      setAuthTab(mode);
    }

    function closeAuthModal() {
      $('auth-modal').classList.add('hide');
    }

    function setAuthTab(tab) {
      if (tab === 'login') {
        $('tab-btn-login').classList.add('active');
        $('tab-btn-register').classList.remove('active');
        $('form-login-pane').classList.remove('hide');
        $('form-register-pane').classList.add('hide');
      } else {
        $('tab-btn-login').classList.remove('active');
        $('tab-btn-register').classList.add('active');
        $('form-login-pane').classList.add('hide');
        $('form-register-pane').classList.remove('hide');
      }
    }

    function fillLogin(u, p) {
      $('login-ident').value = u;
      $('login-pwd').value = p;
      requestOtpFor('login-ident', 'login', 'btn-send-login-otp', 'login-otp');
    }

    // Luồng SMS / Email OTP: Gửi mã 6 số (Server băm SHA-256 kèm hạn 120s)
    async function requestOtpFor(targetSource, action, btnId, targetOtpInputId) {
      let targetVal = '';
      if ($(targetSource)) {
        targetVal = $(targetSource).value.trim();
      } else {
        targetVal = String(targetSource).trim();
      }
      if (!targetVal) return showAlert('Vui lòng nhập Email, SĐT hoặc Tên đăng nhập trước!', false);

      const btn = $(btnId);
      if (btn) {
        btn.disabled = true;
        btn.textContent = 'Đang gửi...';
      }

      const res = await apiRequest('/api/otp/send', {
        method: 'POST',
        body: { target: targetVal, action: action }
      });

      if (res.data.ok) {
        showAlert(res.data.msg, true);
        // Hiển thị Toast thông báo mô phỏng SMS / Email nhận được trong hộp thư
        showOtpToast(res.data.demo_otp, targetVal, action, targetOtpInputId);

        // Đếm ngược 60s cho nút gửi lại
        let cd = 60;
        if (btn) {
          btn.textContent = `Gửi lại (${cd}s)`;
          const timer = setInterval(() => {
            cd--;
            if (btn) btn.textContent = `Gửi lại (${cd}s)`;
            if (cd <= 0) {
              clearInterval(timer);
              if (btn) {
                btn.disabled = false;
                btn.textContent = '📩 Gửi mã OTP';
              }
            }
          }, 1000);
          STATE.activeTimers.push(timer);
        }
      } else {
        if (btn) {
          btn.disabled = false;
          btn.textContent = '📩 Gửi mã OTP';
        }
      }
    }

    // Popup Toast mô phỏng Hộp thư đến (SMS / Email Incoming Message)
    function showOtpToast(code, target, action, fillInputId) {
      let toast = $('otp-simulation-toast');
      if (!toast) {
        toast = document.createElement('div');
        toast.id = 'otp-simulation-toast';
        toast.className = 'otp-toast';
        document.body.appendChild(toast);
      }
      toast.innerHTML = `
        <div class="toast-header">
          <span>📩 HỘP THƯ TIN NHẮN TICKETBOX</span>
          <button onclick="document.getElementById('otp-simulation-toast').style.display='none'">✕</button>
        </div>
        <div class="toast-body">
          <div style="font-size:12px; color:#8b949e;"><b>Gửi đến:</b> <span style="color:#58a6ff;">${target}</span> | Hành động: <b style="color:var(--tb-green);">${action.toUpperCase()}</b></div>
          <div style="margin: 8px 0; font-size: 13px; color:#fff;">Mã xác thực OTP của bạn là:</div>
          <div class="toast-otp-code">${code}</div>
          <div style="font-size: 11px; color:#8b949e; margin-top: 6px;">
            ⏱️ Hiệu lực 120 giây · Server băm <b>SHA-256</b> an toàn · Nhập sai > 3 lần sẽ tự hủy
          </div>
          <button class="btn-primary" style="margin-top: 10px; width: 100%; padding: 7px; font-size:12px;" onclick="fillToastOtp('${fillInputId}', '${code}')">
            ⚡ Tự động điền mã này vào ô
          </button>
        </div>
      `;
      toast.style.display = 'block';
    }

    function fillToastOtp(inputId, code) {
      const inp = $(inputId);
      if (inp) inp.value = code;
      const toast = $('otp-simulation-toast');
      if (toast) toast.style.display = 'none';
      showAlert('Đã tự động điền mã OTP: ' + code, true);
    }

    async function fetchDemoOtp(identInputId, targetOtpInputId) {
      requestOtpFor(identInputId, 'login', 'btn-send-login-otp', targetOtpInputId);
    }

    async function submitLogin() {
      const ident = $('login-ident').value.trim();
      const pwd = $('login-pwd').value;
      const otp = $('login-otp').value.trim();

      if (!ident || !otp) {
        return showAlert('Vui lòng nhập tên đăng nhập và mã OTP 6 số', false);
      }

      const res = await apiRequest('/api/login', {
        method: 'POST',
        body: { username: ident, password: pwd, otp: otp }
      });

      if (res.data.ok) {
        STATE.token = res.data.token;
        STATE.user = res.data.user;
        localStorage.setItem('ts_token', STATE.token);
        localStorage.setItem('ts_user', JSON.stringify(STATE.user));
        closeAuthModal();
        updateAuthUI();
        showAlert('Đăng nhập thành công! Chào mừng ' + (STATE.user.full_name || STATE.user.username), true);
        switchView('home');
      }
    }

    async function submitRegister() {
      const otp = $('reg-otp').value.trim();
      if (!otp) {
        return showAlert('Vui lòng nhấn "Gửi OTP" và nhập mã xác thực email trước khi hoàn tất đăng ký', false);
      }
      const body = {
        full_name: $('reg-fullname').value.trim(),
        email: $('reg-email').value.trim(),
        phone: $('reg-phone').value.trim(),
        username: $('reg-username').value.trim(),
        password: $('reg-pwd').value,
        otp: otp
      };

      const res = await apiRequest('/api/register', { method: 'POST', body });
      if (res.data.ok) {
        showAlert('Đăng ký tài khoản thành công! Bạn có thể đăng nhập ngay.', true);
        setAuthTab('login');
        $('login-ident').value = body.username;
        $('login-pwd').value = body.password;
        requestOtpFor('login-ident', 'login', 'btn-send-login-otp', 'login-otp');
      }
    }

    async function doLogout() {
      await apiRequest('/api/logout', { method: 'POST' });
      STATE.token = null;
      STATE.user = null;
      localStorage.removeItem('ts_token');
      localStorage.removeItem('ts_user');
      updateAuthUI();
      showAlert('Đã đăng xuất tài khoản thành công', true);
      switchView('home');
    }

    // ================= BỘ ĐIỀU HƯỚNG GIAO DIỆN (VIEWS) =================
    async function switchView(viewName) {
      clearAppTimers();
      const root = $('app-root');

      if (viewName === 'home') {
        const res = await apiRequest('/api/events');
        if (res.data.ok) {
          STATE.event = res.data.event;
          STATE.ticketTypes = res.data.ticket_types;
        }
        root.innerHTML = renderHomeView();
      }
      else if (viewName === 'select') {
        if (!STATE.token) {
          openAuthModal('login');
          return showAlert('Vui lòng đăng nhập trước khi tiến hành đặt vé', false);
        }
        const [resEv, resSeats] = await Promise.all([
          apiRequest('/api/events'),
          apiRequest('/api/seats')
        ]);
        if (resEv.data.ok) {
          STATE.event = resEv.data.event;
          STATE.ticketTypes = resEv.data.ticket_types;
        }
        if (resSeats.data.ok) {
          STATE.seats = resSeats.data.seats;
        }
        STATE.selectedType = 'VIP';
        STATE.selectedQty = 1;
        STATE.selectedSeatId = 'SEAT-A03';
        root.innerHTML = renderSelectTicketView();
      }
      else if (viewName === 'info') {
        if (!STATE.selectedType || STATE.selectedQty <= 0) {
          return switchView('select');
        }
        root.innerHTML = renderInfoSurveyView();
      }
      else if (viewName === 'pay') {
        if (!STATE.orderToken) {
          return switchView('select');
        }
        root.innerHTML = renderPaymentView();
        startCheckoutCountdown();
      }
      else if (viewName === 'mine') {
        if (!STATE.token) {
          openAuthModal('login');
          return showAlert('Vui lòng đăng nhập để xem vé của bạn', false);
        }
        root.innerHTML = renderMyTicketsView();
        loadMyTickets();
      }
      else if (viewName === 'resell') {
        root.innerHTML = renderResellMarketView();
        loadResellListings();
      }
      else if (viewName === 'security') {
        root.innerHTML = renderSecurityHubView();
        loadAuditLogs();
        const timer = setInterval(loadAuditLogs, 3000);
        STATE.activeTimers.push(timer);
      }
    }

    function openMyTickets() {
      switchView('mine');
    }

    // ================= RENDER CÁC TRANG (TEMPLATES) =================

    // 1. TRANG CHỦ (HOME VIEW)
    function renderHomeView() {
      const ev = STATE.event || {
        title: 'SUPERFEST 2026 - Concert Mùa Hè Rực Sáng',
        date_str: '18:30 - 22:00, 19 Tháng 12, 2026',
        venue: 'Quảng trường Sun Carnival, Bãi Cháy, TP. Hạ Long, Quảng Ninh'
      };

      return `
        <!-- HERO BANNER TICKETBOX -->
        <section class="hero-wrapper">
          <div class="hero-info">
            <div>
              <span class="hero-tag">SỰ KIỆN NỔI BẬT NHẤT 2026</span>
              <h1 class="hero-title">${ev.title}</h1>
              <div class="hero-meta"><span>📅</span> ${ev.date_str}</div>
              <div class="hero-meta"><span>📍</span> ${ev.venue}</div>
              <p style="color: #c9d1d9; font-size: 13px; margin-top: 14px; line-height: 1.6;">
                Đại nhạc hội đỉnh cao quy tụ dàn sao hàng đầu Việt Nam. Nền tảng bán vé ứng dụng <b>Zero Trust Architecture</b> bảo vệ người mua chống phe vé, bot gom vé và vé giả.
              </p>
            </div>

            <div class="hero-price-box">
              <div class="hero-price-label">Giá vé chính thức chỉ từ</div>
              <div class="hero-price-val">800.000 đ</div>
              <button class="btn-primary" style="width: 100%; font-size: 16px; padding: 14px;" onclick="switchView('select')">
                🎟️ Mua vé ngay
              </button>
            </div>
          </div>

          <div class="hero-banner-visual" style="background: linear-gradient(180deg, rgba(14,17,23,0.3) 0%, rgba(14,17,23,0.85) 100%), url('https://images.unsplash.com/photo-1470225620780-dba8ba36b745?auto=format&fit=crop&w=1200&q=80') center/cover no-repeat;">
            <div class="visual-badge">LIVE CONCERT ĐẠI NHẠC HỘI</div>
            <div class="visual-headline">SUPERFEST 2026<br>MÙA HÈ RỰC SÁNG</div>
            <div class="visual-sub">🛡️ CÔNG NGHỆ VÉ AN TOÀN ZERO TRUST CHỐNG VÉ GIẢ</div>
          </div>
        </section>

        <!-- DANH SÁCH SỰ KIỆN NỔI BẬT THEO QUY CHẾ TICKETBOX -->
        <div class="section-header">
          <h2 class="section-title">Sự kiện âm nhạc & nghệ thuật đang mở bán</h2>
          <span style="color: var(--tb-text-muted); font-size: 13px;">Theo chuẩn Sàn Giao dịch TMĐT Ticketbox.vn</span>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 24px; margin-bottom: 40px;">
          <!-- Card 1: Hà Nội Artificial Paradise -->
          <div class="tb-card event-poster-card">
            <div class="poster-thumb-wrapper">
              <img src="https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=600&q=80" alt="Hà Nội Artificial Paradise" class="poster-img">
              <span class="poster-badge-category">Nhạc sống</span>
            </div>
            <div class="poster-content">
              <h3 class="poster-title">Hà Nội The Artificial Paradise Tour</h3>
              <div class="poster-meta"><span>📅</span> 20:00, 23 Tháng 12, 2026</div>
              <div class="poster-meta"><span>📍</span> Cung Thể thao Quần Ngựa, Hà Nội</div>
              <div class="poster-footer">
                <div>
                  <span class="price-from-label">Giá từ</span>
                  <div class="poster-price">1.400.000 đ</div>
                </div>
                <button class="btn-primary" style="padding: 8px 18px;" onclick="switchView('select')">Mua vé</button>
              </div>
            </div>
          </div>

          <!-- Card 2: Trường Twins Fan Meeting -->
          <div class="tb-card event-poster-card">
            <div class="poster-thumb-wrapper">
              <img src="https://images.unsplash.com/photo-1501386761578-eac5c94b800a?auto=format&fit=crop&w=600&q=80" alt="Trường Twins Fan Meeting" class="poster-img">
              <span class="poster-badge-category">Fan Meeting</span>
            </div>
            <div class="poster-content">
              <h3 class="poster-title">Fan Meeting Mùa 2 - Trường Twins Rise Together</h3>
              <div class="poster-meta"><span>📅</span> 19:00, 05 Tháng 11, 2026</div>
              <div class="poster-meta"><span>📍</span> Nhà thi đấu Cầu Giấy, Hà Nội</div>
              <div class="poster-footer">
                <div>
                  <span class="price-from-label">Giá từ</span>
                  <div class="poster-price">650.000 đ</div>
                </div>
                <button class="btn-primary" style="padding: 8px 18px;" onclick="switchView('select')">Mua vé</button>
              </div>
            </div>
          </div>

          <!-- Card 3: Việt Nam Bách Nghệ -->
          <div class="tb-card event-poster-card">
            <div class="poster-thumb-wrapper">
              <img src="https://images.unsplash.com/photo-1465847899084-d164df4dedc6?auto=format&fit=crop&w=600&q=80" alt="Việt Nam Bách Nghệ" class="poster-img">
              <span class="poster-badge-category">Sân khấu</span>
            </div>
            <div class="poster-content">
              <h3 class="poster-title">Việt Nam Bách Nghệ - Thập Niên Hồn Việt</h3>
              <div class="poster-meta"><span>📅</span> 18:00, 28 Tháng 11, 2026</div>
              <div class="poster-meta"><span>📍</span> Nhà hát Hòa Bình, TP. Hồ Chí Minh</div>
              <div class="poster-footer">
                <div>
                  <span class="price-from-label">Giá từ</span>
                  <div class="poster-price">500.000 đ</div>
                </div>
                <button class="btn-primary" style="padding: 8px 18px;" onclick="switchView('select')">Mua vé</button>
              </div>
            </div>
          </div>

          <!-- Card 4: Lam Trường Tình Đơn Phương -->
          <div class="tb-card event-poster-card">
            <div class="poster-thumb-wrapper">
              <img src="https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?auto=format&fit=crop&w=600&q=80" alt="Lam Trường Liveshow" class="poster-img">
              <span class="poster-badge-category">Liveshow</span>
            </div>
            <div class="poster-content">
              <h3 class="poster-title">Lam Trường - Tình Đơn Phương Sol8</h3>
              <div class="poster-meta"><span>📅</span> 20:00, 15 Tháng 12, 2026</div>
              <div class="poster-meta"><span>📍</span> Sky Expo Hall A5, TP. Hồ Chí Minh</div>
              <div class="poster-footer">
                <div>
                  <span class="price-from-label">Giá từ</span>
                  <div class="poster-price">800.000 đ</div>
                </div>
                <button class="btn-primary" style="padding: 8px 18px;" onclick="switchView('select')">Mua vé</button>
              </div>
            </div>
          </div>

          <!-- Card 5: Rap Việt All-Star Concert -->
          <div class="tb-card event-poster-card">
            <div class="poster-thumb-wrapper">
              <img src="https://images.unsplash.com/photo-1492684223066-81342ee5ff30?auto=format&fit=crop&w=600&q=80" alt="Rap Việt Concert" class="poster-img">
              <span class="poster-badge-category">Hiphop</span>
            </div>
            <div class="poster-content">
              <h3 class="poster-title">Rap Việt All-Star Concert 2026</h3>
              <div class="poster-meta"><span>📅</span> 19:30, 20 Tháng 12, 2026</div>
              <div class="poster-meta"><span>📍</span> Trung tâm Triển lãm SECC, Q.7, TP.HCM</div>
              <div class="poster-footer">
                <div>
                  <span class="price-from-label">Giá từ</span>
                  <div class="poster-price">900.000 đ</div>
                </div>
                <button class="btn-primary" style="padding: 8px 18px;" onclick="switchView('select')">Mua vé</button>
              </div>
            </div>
          </div>

          <!-- Card 6: Hai Đứa Thần Mặt Trời -->
          <div class="tb-card event-poster-card">
            <div class="poster-thumb-wrapper">
              <img src="https://images.unsplash.com/photo-1507676184212-d03ab07a01bf?auto=format&fit=crop&w=600&q=80" alt="Kịch Thần Mặt Trời" class="poster-img">
              <span class="poster-badge-category">Kịch nói</span>
            </div>
            <div class="poster-content">
              <h3 class="poster-title">Kịch Sân Khấu: Hầu Án Thần Mặt Trời</h3>
              <div class="poster-meta"><span>📅</span> 19:00, 10 Tháng 11, 2026</div>
              <div class="poster-meta"><span>📍</span> Sân khấu Kịch IDECAF, TP.HCM</div>
              <div class="poster-footer">
                <div>
                  <span class="price-from-label">Giá từ</span>
                  <div class="poster-price">350.000 đ</div>
                </div>
                <button class="btn-primary" style="padding: 8px 18px;" onclick="switchView('select')">Mua vé</button>
              </div>
            </div>
          </div>
        </div>

        <!-- THẺ GIỚI THIỆU ZERO TRUST THEO YÊU CẦU ĐỒ ÁN -->
        <div class="tb-card" style="background: linear-gradient(145deg, #161e2e, #111722); border: 1px solid #388bfd; border-radius: 14px; padding: 28px;">
          <div style="display: flex; gap: 18px; align-items: flex-start;">
            <div style="font-size: 38px;">🛡️</div>
            <div>
              <h3 style="color: #fff; font-size: 18px; margin-bottom: 6px;">
                Cơ chế Bảo mật Cốt lõi: Zero Trust Concert Architecture
              </h3>
              <p style="color: #c9d1d9; font-size: 13px; line-height: 1.7;">
                Hệ thống tuân thủ nguyên tắc cốt lõi của giảng viên: <i>"Không phải mọi thông tin mà hệ thống nhận được đều đáng tin cậy"</i>. 
                Giá vé được ký bằng chữ ký số <b>HMAC-SHA256</b> bí mật phía Server, mã QR sử dụng cơ chế <b>Dynamic TOTP 15 giây</b> đổi mã liên tục (chống ảnh chụp chia sẻ lại), 
                và tính năng <b>Chợ Pass Vé</b> kiểm soát trần giá để dập tắt nạn phe vé chợ đen.
              </p>
              <div style="margin-top: 14px; display: flex; gap: 12px; flex-wrap: wrap;">
                <span class="security-pill">Chống sửa giá (Parameter Tampering)</span>
                <span class="security-pill">Chống Replay QR Code (TOTP 15s)</span>
                <span class="security-pill">Chống Bot gom vé (Rate Limiter)</span>
                <span class="security-pill">Chống Chiếm phiên (Fingerprint)</span>
              </div>
            </div>
          </div>
        </div>
      `;
    }

    // 2. TRANG CHỌN VÉ VÀ SƠ ĐỒ CHỖ NGỒI (STEP 1)
    function renderSelectTicketView() {
      const types = STATE.ticketTypes || [];
      const ev = STATE.event || {};

      return `
        <!-- STEPPER -->
        <div class="stepper-nav">
          <div class="step-item active"><span class="step-num">1</span> 1. Chọn loại vé & Chỗ ngồi</div>
          <div class="step-item"><span class="step-num">2</span> 2. Thông tin người tham dự</div>
          <div class="step-item"><span class="step-num">3</span> 3. Thanh toán an toàn</div>
        </div>

        <div class="split-layout">
          <div>
            <h2 class="section-title">Hạng vé sự kiện</h2>
            <div style="margin-top: 16px;">
              ${types.map(t => `
                <div class="ticket-type-card ${STATE.selectedType === t.code ? 'selected' : ''}" id="tt-card-${t.code}">
                  <div>
                    <div class="tt-name">${t.name}</div>
                    <div class="tt-price">${formatVND(t.price)}</div>
                    <div class="tt-info">${t.info}</div>
                  </div>

                  <div>
                    ${t.stock > 0 ? `
                      <div class="qty-control">
                        <button class="qty-btn" onclick="changeQty('${t.code}', -1)">-</button>
                        <span class="qty-value" id="qty-val-${t.code}">${STATE.selectedType === t.code ? STATE.selectedQty : 0}</span>
                        <button class="qty-btn" onclick="changeQty('${t.code}', 1)">+</button>
                      </div>
                    ` : `
                      <span class="tag-sold-out">HẾT VÉ</span>
                    `}
                  </div>
                </div>
              `).join('')}
            </div>

            <!-- SƠ ĐỒ CHỖ NGỒI TRỰC QUAN (SEAT MAP NHƯ TRONG QUY CHẾ TICKETBOX) -->
            <div class="seat-map-wrapper">
              <h3 style="color: #fff; margin-bottom: 6px;">Sơ đồ chỗ ngồi khán đài (Seat Map)</h3>
              <p style="color: var(--tb-text-muted); font-size: 12px; margin-bottom: 20px;">
                Chọn ghế cho hạng vé VIP Seated (Ghế xanh lá: trống | Ghế xanh ngọc: đang chọn | Ghế xám: đã đặt)
              </p>

              <div class="stage-box">STAGE / SÂN KHẤU CHÍNH</div>

              <div class="seat-grid">
                ${renderSeatRows()}
              </div>

              <div class="seat-legend">
                <div class="legend-item"><div class="legend-color" style="background:#21262d; border:1px solid #30363d;"></div> Ghế trống</div>
                <div class="legend-item"><div class="legend-color" style="background:var(--tb-green);"></div> Đang chọn</div>
                <div class="legend-item"><div class="legend-color" style="background:#30363d;"></div> Đã bán / Khóa</div>
              </div>
            </div>
          </div>

          <!-- SIDEBAR TÓM TẮT ĐƠN HÀNG -->
          <div class="sidebar-summary">
            <h3 style="font-size: 16px; margin-bottom: 12px; color: #fff;">Thông tin đặt vé</h3>
            <div style="font-weight: 700; color: #fff; margin-bottom: 4px;">${ev.title || 'SUPERFEST 2026'}</div>
            <div style="color: var(--tb-text-muted); font-size: 12px; margin-bottom: 16px;">📅 ${ev.date_str || ''}</div>
            <hr style="border-color: var(--tb-border); margin-bottom: 16px;">

            <div id="side-calc-pane">
              ${renderSidebarCalc()}
            </div>

            <button class="btn-primary" style="width: 100%; margin-top: 20px;" id="btn-goto-info" onclick="requestOrderQuote()" ${STATE.selectedQty > 0 ? '' : 'disabled'}>
              Tiếp tục ≫
            </button>
          </div>
        </div>
      `;
    }

    function renderSeatRows() {
      const rows = ['A', 'B', 'C'];
      return rows.map(r => {
        const seatsInRow = (STATE.seats || []).filter(s => s.row_name === r);
        return `
          <div class="seat-row">
            <span class="row-label">${r}</span>
            ${seatsInRow.map(s => {
              const isSelected = STATE.selectedSeatId === s.seat_id;
              const isBooked = s.status === 'booked';
              return `
                <div class="seat-node ${isBooked ? 'booked' : ''} ${isSelected ? 'selected' : ''}"
                     onclick="${isBooked ? '' : `selectSeat('${s.seat_id}')`}"
                     title="Ghế ${s.seat_id} (${s.status})">
                  ${s.seat_num}
                </div>
              `;
            }).join('')}
          </div>
        `;
      }).join('');
    }

    function renderSidebarCalc() {
      if (!STATE.selectedType || STATE.selectedQty <= 0) {
        return `<div style="color: var(--tb-text-muted); font-size: 13px;">Chưa chọn hạng vé nào.</div>`;
      }
      const t = STATE.ticketTypes.find(x => x.code === STATE.selectedType) || {};
      const subtotal = (t.price || 0) * STATE.selectedQty;
      return `
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
          <span>${t.name}</span>
          <span style="font-weight: 700; color: #fff;">x${STATE.selectedQty}</span>
        </div>
        ${STATE.selectedSeatId ? `
          <div style="display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 12px; color: var(--tb-green);">
            <span>Ghế đã chọn:</span>
            <span><b>${STATE.selectedSeatId}</b></span>
          </div>
        ` : ''}
        <div style="display: flex; justify-content: space-between; margin-bottom: 12px; font-size: 13px; color: var(--tb-text-muted);">
          <span>Đơn giá:</span>
          <span>${formatVND(t.price)}</span>
        </div>
        <hr style="border-color: var(--tb-border); margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; font-size: 16px;">
          <span style="font-weight: 700;">Tạm tính:</span>
          <span style="font-weight: 800; color: var(--tb-green);">${formatVND(subtotal)}</span>
        </div>
      `;
    }

    function changeQty(typeCode, delta) {
      if (STATE.selectedType !== typeCode) {
        STATE.selectedType = typeCode;
        STATE.selectedQty = 0;
      }
      const newQty = Math.max(0, Math.min(4, STATE.selectedQty + delta));
      STATE.selectedQty = newQty;
      if (newQty === 0) {
        STATE.selectedType = null;
        STATE.selectedSeatId = null;
      }
      // Re-render
      $('app-root').innerHTML = renderSelectTicketView();
    }

    function selectSeat(seatId) {
      STATE.selectedSeatId = seatId;
      STATE.selectedType = 'VIP';
      if (STATE.selectedQty === 0) STATE.selectedQty = 1;
      $('app-root').innerHTML = renderSelectTicketView();
    }

    // Yêu cầu Server tính giá và cấp Order Token có ký HMAC (Chống sửa giá Client)
    async function requestOrderQuote() {
      if (!STATE.selectedType || STATE.selectedQty <= 0) {
        return showAlert('Vui lòng chọn ít nhất 1 vé', false);
      }

      const res = await apiRequest('/api/quote', {
        method: 'POST',
        body: {
          ticket_type: STATE.selectedType,
          qty: STATE.selectedQty,
          seat_id: STATE.selectedSeatId
        }
      });

      if (res.data.ok) {
        STATE.totalAmount = res.data.total;
        STATE.orderToken = res.data.token;
        switchView('info');
      }
    }

    // 3. TRANG BẢNG CÂU HỎI NGƯỜI THAM DỰ (STEP 2)
    function renderInfoSurveyView() {
      const u = STATE.user || {};
      const t = STATE.ticketTypes.find(x => x.code === STATE.selectedType) || {};

      return `
        <div class="stepper-nav">
          <div class="step-item"><span class="step-num">1</span> 1. Chọn loại vé & Chỗ ngồi</div>
          <div class="step-item active"><span class="step-num">2</span> 2. Thông tin người tham dự</div>
          <div class="step-item"><span class="step-num">3</span> 3. Thanh toán an toàn</div>
        </div>

        <div class="split-layout">
          <div>
            <div class="tb-card">
              <h2 class="section-title">Bảng câu hỏi thông tin người tham dự</h2>
              <p style="color: var(--tb-text-muted); font-size: 13px; margin-bottom: 20px;">
                Theo quy định sàn Ticketbox: Vui lòng điền chính xác thông tin để BTC đối soát vé tại cổng và gửi vé điện tử.
              </p>

              <div class="form-group">
                <label>* Họ và tên người tham dự</label>
                <input type="text" id="buyer-fullname" value="${u.full_name || ''}" placeholder="ví dụ: Nguyễn Văn Anh">
              </div>

              <div class="form-group">
                <label>* Số điện thoại liên hệ</label>
                <input type="tel" id="buyer-phone" value="${u.phone || ''}" placeholder="ví dụ: 0901234567">
              </div>

              <div class="form-group">
                <label>* Địa chỉ Email nhận vé điện tử</label>
                <input type="email" id="buyer-email" value="${u.email || ''}" placeholder="ví dụ: fana@ticketbox.demo">
              </div>

              <label class="checkbox-label">
                <input type="checkbox" id="buyer-agreement" checked>
                <span>Tôi đồng ý để Ticketbox & Ban tổ chức sử dụng thông tin nhằm mục đích vận hành và kiểm soát an ninh sự kiện.</span>
              </label>
            </div>
          </div>

          <div class="sidebar-summary">
            <h3 style="font-size: 16px; margin-bottom: 12px; color: #fff;">Tóm tắt đơn hàng</h3>
            <div style="font-weight: 700; color: #fff;">${t.name} x${STATE.selectedQty}</div>
            ${STATE.selectedSeatId ? `<div style="font-size: 12px; color: var(--tb-green); margin-top: 4px;">Ghế: ${STATE.selectedSeatId}</div>` : ''}
            <div style="font-size: 13px; color: var(--tb-text-muted); margin-top: 8px;">Tổng tiền do Server xác thực:</div>
            <div style="font-size: 20px; font-weight: 800; color: var(--tb-green); margin: 8px 0 16px;">
              ${formatVND(STATE.totalAmount)}
            </div>
            <button class="btn-primary" style="width: 100%;" onclick="proceedToPayment()">
              Tiếp tục thanh toán ≫
            </button>
            <button class="btn-secondary" style="width: 100%; margin-top: 10px;" onclick="switchView('select')">
              ≪ Quay lại
            </button>
          </div>
        </div>
      `;
    }

    function proceedToPayment() {
      const name = $('buyer-fullname').value.trim();
      const phone = $('buyer-phone').value.trim();
      const email = $('buyer-email').value.trim();
      const agree = $('buyer-agreement').checked;

      if (!name) return showAlert('Vui lòng nhập Họ và tên người tham dự', false);
      if (!/^[0-9]{9,11}$/.test(phone)) return showAlert('Số điện thoại chỉ gồm chữ số (9-11 số)', false);
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return showAlert('Địa chỉ email không đúng định dạng', false);
      if (!agree) return showAlert('Bạn cần đồng ý với điều khoản sử dụng của Ticketbox', false);

      STATE.buyerInfo = { name, phone, email };
      switchView('pay');
    }

    // 4. TRANG THANH TOÁN & ĐẾM NGƯỢC 10 PHÚT (STEP 3)
    function renderPaymentView() {
      const t = STATE.ticketTypes.find(x => x.code === STATE.selectedType) || {};
      const buyer = STATE.buyerInfo || {};

      return `
        <div class="stepper-nav">
          <div class="step-item"><span class="step-num">1</span> 1. Chọn loại vé & Chỗ ngồi</div>
          <div class="step-item"><span class="step-num">2</span> 2. Thông tin người tham dự</div>
          <div class="step-item active"><span class="step-num">3</span> 3. Thanh toán an toàn</div>
        </div>

        <div class="checkout-timer-bar">
          <div>
            <span>⏱️ Vé của bạn đang được tạm giữ trong</span>
            <div style="font-size: 11px; color: var(--tb-text-muted);">Quá thời gian trên, mã giữ chỗ và token chữ ký sẽ tự động hủy.</div>
          </div>
          <div class="timer-countdown" id="checkout-timer-display">10:00</div>
        </div>

        <div class="split-layout">
          <div>
            <!-- PHƯƠNG THỨC THANH TOÁN THEO QUY CHẾ TICKETBOX -->
            <div class="tb-card">
              <h2 class="section-title">Chọn phương thức thanh toán</h2>
              <div class="payment-method-grid">
                <label class="pm-radio-card selected" onclick="selectPaymentMethod(this, 'VietQR')">
                  <input type="radio" name="pay-method" value="VietQR" checked style="display:none;">
                  <span class="pm-icon-tag" style="background:#e11d48; color:#fff;">VIETQR</span>
                  <div>
                    <div style="font-weight:700;">Chuyển khoản VietQR</div>
                    <div style="font-size:11px; color:var(--tb-text-muted);">Quét mã chuyển tiền tức thì</div>
                  </div>
                </label>

                <label class="pm-radio-card" onclick="selectPaymentMethod(this, 'VNPAY')">
                  <input type="radio" name="pay-method" value="VNPAY" style="display:none;">
                  <span class="pm-icon-tag" style="background:#0284c7; color:#fff;">VNPAY</span>
                  <div>
                    <div style="font-weight:700;">VNPAY / App Ngân hàng</div>
                    <div style="font-size:11px; color:var(--tb-text-muted);">Cổng thanh toán quốc gia</div>
                  </div>
                </label>

                <label class="pm-radio-card" onclick="selectPaymentMethod(this, 'ShopeePay')">
                  <input type="radio" name="pay-method" value="ShopeePay" style="display:none;">
                  <span class="pm-icon-tag" style="background:#ea580c; color:#fff;">SHOPEEPAY</span>
                  <div>
                    <div style="font-weight:700;">Ví ShopeePay</div>
                    <div style="font-size:11px; color:var(--tb-text-muted);">Thanh toán ví điện tử</div>
                  </div>
                </label>

                <label class="pm-radio-card" onclick="selectPaymentMethod(this, 'Zalopay')">
                  <input type="radio" name="pay-method" value="Zalopay" style="display:none;">
                  <span class="pm-icon-tag" style="background:#059669; color:#fff;">ZALOPAY</span>
                  <div>
                    <div style="font-weight:700;">Ví điện tử ZaloPay</div>
                    <div style="font-size:11px; color:var(--tb-text-muted);">Liên kết thẻ và ví</div>
                  </div>
                </label>
              </div>
            </div>

            <!-- XÁC THỰC BẢO MẬT GIAO DỊCH KHI THANH TOÁN -->
            <div class="tb-card">
              <h2 class="section-title">Xác thực giao dịch an toàn (SMS / Email OTP)</h2>
              <p style="color: var(--tb-text-muted); font-size: 13px; margin-bottom: 14px;">
                Nhập mã OTP 6 chữ số gửi đến Email/SĐT người nhận <b>${buyer.email}</b> để xác nhận thanh toán đơn hàng.
              </p>
              <div style="display: flex; gap: 10px; max-width: 480px;">
                <input type="text" id="pay-otp-code" placeholder="Nhập mã OTP 6 số" maxlength="6" style="flex: 1; font-size: 16px; letter-spacing: 2px;">
                <button class="btn-primary" id="btn-send-pay-otp" onclick="requestOtpFor('${buyer.email}', 'payment', 'btn-send-pay-otp', 'pay-otp-code')" type="button" style="white-space: nowrap; padding: 10px 16px;">
                  📩 Gửi mã OTP
                </button>
              </div>
              <small style="color: var(--tb-text-muted); display: block; margin-top: 6px;">
                Mã OTP băm <b>SHA-256</b> tại Server, thời hạn <b>120s</b>. Chống kẻ gian chiếm phiên mua trộm vé.
              </small>
            </div>
          </div>

          <!-- SIDEBAR TỔNG TIỀN VÀ THANH TOÁN -->
          <div class="sidebar-summary">
            <h3 style="font-size: 16px; margin-bottom: 12px; color: #fff;">Thông tin nhận vé</h3>
            <div style="font-size: 13px; margin-bottom: 4px;">Khách hàng: <b>${buyer.name}</b></div>
            <div style="font-size: 13px; margin-bottom: 4px;">Email nhận: <b>${buyer.email}</b></div>
            <div style="font-size: 13px; margin-bottom: 14px;">SĐT: <b>${buyer.phone}</b></div>
            <hr style="border-color: var(--tb-border); margin-bottom: 14px;">

            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
              <span>${t.name}</span>
              <span>x${STATE.selectedQty}</span>
            </div>
            ${STATE.selectedSeatId ? `<div style="font-size:12px; color:var(--tb-green); margin-bottom:8px;">Ghế: ${STATE.selectedSeatId}</div>` : ''}
            <div style="display: flex; justify-content: space-between; margin-bottom: 14px;">
              <span>Tổng tiền thanh toán:</span>
              <span style="font-size: 18px; font-weight: 800; color: var(--tb-green);">${formatVND(STATE.totalAmount)}</span>
            </div>

            <button class="btn-primary" style="width: 100%; font-size: 15px;" onclick="executePayment()">
              💳 Xác nhận thanh toán
            </button>
          </div>
        </div>
      `;
    }

    function selectPaymentMethod(cardElem, methodVal) {
      document.querySelectorAll('.pm-radio-card').forEach(c => c.classList.remove('selected'));
      cardElem.classList.add('selected');
      cardElem.querySelector('input').checked = true;
    }

    function startCheckoutCountdown() {
      let secondsLeft = 600;
      const display = $('checkout-timer-display');
      const timer = setInterval(() => {
        secondsLeft--;
        if (display) {
          const m = String(Math.floor(secondsLeft / 60)).padStart(2, '0');
          const s = String(secondsLeft % 60).padStart(2, '0');
          display.textContent = `${m}:${s}`;
        }
        if (secondsLeft <= 0) {
          clearInterval(timer);
          showAlert('Đã hết thời gian giữ chỗ! Đơn hàng đã bị hủy.', false);
          switchView('select');
        }
      }, 1000);
      STATE.activeTimers.push(timer);
    }

    async function fetchDemoOtpForCurrent(targetInputId) {
      if (!STATE.user) return;
      const res = await apiRequest('/api/demo-otp?u=' + encodeURIComponent(STATE.user.username));
      if (res.data.ok) {
        $(targetInputId).value = res.data.otp;
        showAlert('Đã lấy OTP xác nhận thanh toán: ' + res.data.otp, true);
      }
    }

    async function executePayment() {
      const otp = $('pay-otp-code').value.trim();
      if (!otp) return showAlert('Vui lòng nhập mã OTP 2FA để hoàn tất thanh toán', false);

      const methodChecked = document.querySelector('input[name="pay-method"]:checked');
      const method = methodChecked ? methodChecked.value : 'VietQR';

      const payload = {
        token: STATE.orderToken,
        total: STATE.totalAmount,
        otp: otp,
        method: method,
        ...STATE.buyerInfo
      };

      const res = await apiRequest('/api/buy', {
        method: 'POST',
        body: payload
      });

      if (res.data.ok) {
        showAlert('🎉 Thanh toán thành công! Mã đơn: ' + res.data.order_id, true);
        switchView('mine');
      }
    }

    // 5. TRANG VÉ CỦA TÔI & MÃ QR ĐỘNG TOTP (MY TICKETS)
    function renderMyTicketsView() {
      return `
        <div class="section-header">
          <h2 class="section-title">Vé điện tử của tôi (My Tickets)</h2>
          <span style="color: var(--tb-text-muted); font-size: 13px;">Bảo mật QR động TOTP đổi mã mỗi 15 giây</span>
        </div>
        <div id="my-tickets-container">
          <p style="color: var(--tb-text-muted);">Đang tải danh sách vé điện tử...</p>
        </div>
      `;
    }

    async function loadMyTickets() {
      const res = await apiRequest('/api/my-tickets');
      const container = $('my-tickets-container');
      if (!container) return;

      if (!res.data.ok || !res.data.tickets.length) {
        container.innerHTML = `
          <div class="tb-card" style="text-align: center; padding: 40px;">
            <p style="color: var(--tb-text-muted); font-size: 15px; margin-bottom: 16px;">Bạn chưa có vé điện tử nào.</p>
            <button class="btn-primary" onclick="switchView('select')">Đặt vé ngay bây giờ</button>
          </div>
        `;
        return;
      }

      STATE.myTicketsList = res.data.tickets;
      container.innerHTML = STATE.myTicketsList.map(t => `
        <div class="ticket-pass-card" id="ticket-card-${t.ticket_id}">
          <div class="ticket-qr-zone">
            <div class="qr-timer-pill" id="pill-${t.ticket_id}">
              <span>⏱️</span> Đổi mã sau <b id="countdown-${t.ticket_id}">15s</b>
            </div>

            <div class="qr-image-container">
              <img id="qr-img-${t.ticket_id}" src="" alt="Mã QR Vé">
            </div>

            <div class="qr-payload-code" id="payload-${t.ticket_id}"
                 onclick="copyQrPayload('${t.ticket_id}')"
                 title="Bấm để sao chép mã dán vào cổng Check-in kiểm thử">
              Đang tải mã...
            </div>
            <small style="color:var(--tb-text-muted); font-size:10px; margin-top:4px;">(Click mã để copy test)</small>
          </div>

          <div class="ticket-details-zone">
            <div>
              <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                  <span class="hero-tag">${t.type_name || t.type}</span>
                  <div class="ticket-headline">${t.event_title}</div>
                </div>
                <div>
                  ${t.used ? '<span class="tag-sold-out">ĐÃ VÀO CỔNG</span>' : '<span class="hero-tag" style="border-color:var(--tb-green);">CHƯA QUA CỔNG</span>'}
                </div>
              </div>

              <div class="ticket-field-row">
                <div>
                  <div class="tf-label">Mã vé (Ticket ID)</div>
                  <div class="tf-val" style="font-family:monospace; color:var(--tb-green);">${t.ticket_id}</div>
                </div>
                <div>
                  <div class="tf-label">Vị trí chỗ ngồi</div>
                  <div class="tf-val">${t.seat_id || 'Tự do'}</div>
                </div>
                <div>
                  <div class="tf-label">Thời gian biểu diễn</div>
                  <div class="tf-val" style="font-size:12px;">${t.date_str}</div>
                </div>
              </div>

              <div style="font-size: 12px; color: var(--tb-text-muted);">
                📍 Địa điểm: <b>${t.venue}</b> | Đơn hàng: <b>${t.order_id}</b>
              </div>
            </div>

            <div class="ticket-actions-bar">
              ${!t.used ? `
                <button class="btn-outline-green" onclick="openGiftModal('${t.ticket_id}')">🎁 Tặng vé</button>
                <button class="btn-secondary" onclick="openResellModal('${t.ticket_id}', ${t.original_price || 2000000})">🛒 Bán lại (Pass vé)</button>
              ` : `
                <span style="color:var(--tb-text-muted); font-size:12px;">Vé đã sử dụng, không thể chuyển nhượng</span>
              `}
            </div>
          </div>
        </div>
      `).join('');

      // Bắt đầu cập nhật mã QR động mỗi 3 giây
      STATE.myTicketsList.forEach(t => refreshTicketQr(t.ticket_id));
      const qrTimer = setInterval(() => {
        STATE.myTicketsList.forEach(t => refreshTicketQr(t.ticket_id));
      }, 3000);
      STATE.activeTimers.push(qrTimer);
    }

    async function refreshTicketQr(tid) {
      const res = await apiRequest('/api/tickets/' + tid + '/qr');
      if (res.data.ok) {
        const img = $('qr-img-' + tid);
        const cd = $('countdown-' + tid);
        const pl = $('payload-' + tid);
        if (img) img.src = 'data:image/png;base64,' + res.data.png;
        if (cd) cd.textContent = res.data.left + 's';
        if (pl) pl.textContent = res.data.payload;
      }
    }

    function copyQrPayload(tid) {
      const plElem = $('payload-' + tid);
      if (plElem && plElem.textContent) {
        navigator.clipboard.writeText(plElem.textContent);
        showAlert('Đã copy mã QR vé ' + tid + ' vào clipboard! Hãy dán vào trang Check-in để test.', true);
      }
    }

    // Modal tặng vé
    function openGiftModal(tid) {
      $('gift-ticket-id').value = tid;
      $('gift-recipient').value = '';
      $('gift-modal').classList.remove('hide');
    }
    function closeGiftModal() { $('gift-modal').classList.add('hide'); }

    async function submitGiftTicket() {
      const tid = $('gift-ticket-id').value;
      const to = $('gift-recipient').value.trim();
      if (!to) return showAlert('Vui lòng nhập tên người nhận', false);

      const res = await apiRequest('/api/gift', {
        method: 'POST',
        body: { ticket_id: tid, recipient: to }
      });
      if (res.data.ok) {
        closeGiftModal();
        showAlert(res.data.msg, true);
        loadMyTickets();
      }
    }

    // Modal pass vé
    function openResellModal(tid, origPrice) {
      $('resell-ticket-id').value = tid;
      $('resell-original-price').value = formatVND(origPrice);
      $('resell-new-price').value = origPrice - 100000;
      $('resell-modal').classList.remove('hide');
    }
    function closeResellModal() { $('resell-modal').classList.add('hide'); }

    async function submitResellListing() {
      const tid = $('resell-ticket-id').value;
      const price = parseInt($('resell-new-price').value, 10);
      const bank = $('resell-bank-info').value.trim();

      const res = await apiRequest('/api/resell/list', {
        method: 'POST',
        body: { ticket_id: tid, resell_price: price, bank_info: bank }
      });
      if (res.data.ok) {
        closeResellModal();
        showAlert(res.data.msg, true);
        switchView('resell');
      }
    }

    // 6. TRANG CHỢ PASS VÉ (RESELL MARKETPLACE)
    function renderResellMarketView() {
      return `
        <div class="section-header">
          <div>
            <h2 class="section-title">Chợ Pass Vé Chính Thống Ticketbox</h2>
            <p style="color: var(--tb-text-muted); font-size: 13px; margin-top: 4px;">
              An toàn 100%: Hệ thống tự động hủy vé người bán cũ và cấp vé mới toanh cho bạn. Không lo lừa đảo vé giả!
            </p>
          </div>
        </div>
        <div id="resell-listings-container">
          <p style="color: var(--tb-text-muted);">Đang tải danh sách vé pass...</p>
        </div>
      `;
    }

    async function loadResellListings() {
      const res = await apiRequest('/api/resell/listings');
      const container = $('resell-listings-container');
      if (!container) return;

      if (!res.data.ok || !res.data.listings.length) {
        container.innerHTML = `
          <div class="tb-card" style="text-align:center; padding: 40px;">
            <p style="color: var(--tb-text-muted); font-size: 15px;">Hiện tại chưa có vé pass nào được đăng bán.</p>
          </div>
        `;
        return;
      }

      container.innerHTML = `
        <div class="resell-grid">
          ${res.data.listings.map(item => `
            <div class="resell-card">
              <div>
                <span class="hero-tag">${item.type_name || item.ticket_type}</span>
                <h3 style="font-size: 16px; margin: 8px 0; color: #fff;">${item.event_title}</h3>
                <div style="font-size: 12px; color: var(--tb-text-muted); margin-bottom: 4px;">📅 ${item.date_str}</div>
                <div style="font-size: 12px; color: var(--tb-text-muted);">Người pass: <b>${item.seller_name}</b></div>

                <div class="resell-price-row">
                  <span class="resell-new-price">${formatVND(item.resell_price)}</span>
                  <span class="resell-old-price">${formatVND(item.original_price)}</span>
                  <span style="color: var(--tb-green); font-size: 11px; font-weight: 700;">(Chính hãng)</span>
                </div>
              </div>

              <div style="margin-top: 16px; border-top: 1px solid var(--tb-border); padding-top: 14px;">
                <button class="btn-primary" style="width: 100%; font-size: 13px;" onclick="buyResellTicket(${item.id})">
                  ⚡ Mua lại vé pass an toàn
                </button>
              </div>
            </div>
          `).join('')}
        </div>
      `;
    }

    async function buyResellTicket(listingId) {
      if (!STATE.token) {
        openAuthModal('login');
        return showAlert('Vui lòng đăng nhập trước khi mua vé pass', false);
      }
      const otp = prompt('Nhập mã OTP 2FA của bạn để xác nhận mua vé pass:');
      if (!otp) return;

      const res = await apiRequest('/api/resell/buy', {
        method: 'POST',
        body: { listing_id: listingId, otp: otp }
      });
      if (res.data.ok) {
        showAlert(res.data.msg, true);
        switchView('mine');
      }
    }

    // 7. TRANG SECURITY HUB & ATTACK PLAYGROUND (DEMO CHO THẦY CÔ)
    function renderSecurityHubView() {
      return `
        <div class="security-hub-card">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
              <span class="badge-shield" style="font-size:12px; padding:4px 12px;">ZERO TRUST SECURITY HUB</span>
              <h2 style="font-size: 22px; font-weight: 800; color: #fff; margin-top: 8px;">
                Trung Tâm Kiểm Soát An Ninh & Giả Lập Tấn Công
              </h2>
            </div>
            <button class="btn-secondary" onclick="loadAuditLogs()">🔄 Làm mới Audit Log</button>
          </div>
          <p style="color: var(--tb-text-muted); font-size: 13px; margin-top: 8px;">
            Trình diễn trực tiếp phản ứng của hệ thống trước 5 kịch bản tấn công điển hình theo yêu cầu của Giảng viên.
          </p>

          <div class="attack-buttons-grid">
            <div class="attack-btn" onclick="triggerSimulatedAttack('tamper_price')">
              <div class="attack-title"><span>⚡</span> TC2: Sửa giá vé (Parameter Tampering)</div>
              <div class="attack-sub">Sửa giá vé VIP từ 2.000.000đ xuống 10.000đ bằng F12 / Burp Suite.</div>
            </div>

            <div class="attack-btn" onclick="triggerSimulatedAttack('replay_qr')">
              <div class="attack-title"><span>📷</span> TC3: Replay QR cũ (Chụp màn hình)</div>
              <div class="attack-sub">Dùng ảnh chụp màn hình mã QR đã quá 15 giây để quét tại cổng.</div>
            </div>

            <div class="attack-btn" onclick="triggerSimulatedAttack('bot_spam')">
              <div class="attack-title"><span>🤖</span> TC4: Bot gom vé (Spam 20 req/s)</div>
              <div class="attack-sub">Script tự động gửi hàng loạt yêu cầu đặt vé để ôm sạch vé chợ đen.</div>
            </div>

            <div class="attack-btn" onclick="triggerSimulatedAttack('session_hijack')">
              <div class="attack-title"><span>🕵️</span> TC8: Đánh cắp Token (Session Hijack)</div>
              <div class="attack-sub">Đánh cắp Cookie/Session Token và sử dụng từ thiết bị/IP của hacker.</div>
            </div>

            <div class="attack-btn" onclick="triggerSimulatedAttack('sqli_login')">
              <div class="attack-title"><span>💉</span> TC6: Chèn SQL Injection</div>
              <div class="attack-sub">Thử chuỗi ' OR '1'='1 vào form đăng nhập để bypass xác thực.</div>
            </div>
          </div>

          <div style="margin-top: 20px;">
            <div style="font-weight: 700; color: #fff; margin-bottom: 8px;">🖥️ Sandbox Terminal Response:</div>
            <div class="sandbox-console" id="sandbox-output">
[TicketShield Security Hub v2.0 ready]
Nhấn vào bất kỳ kịch bản tấn công nào phía trên để xem hệ thống phát hiện và ngăn chặn theo thời gian thực...
            </div>
          </div>
        </div>

        <div class="tb-card">
          <div class="section-header">
            <h3 class="section-title">Nhật ký kiểm toán bảo mật thời gian thực (Audit Log)</h3>
            <span style="color:var(--tb-text-muted); font-size:12px;">Tự động làm mới mỗi 3 giây</span>
          </div>

          <div class="audit-table-container">
            <table class="audit-table">
              <thead>
                <tr>
                  <th>Thời gian</th>
                  <th>IP Client</th>
                  <th>Sự kiện</th>
                  <th>Mức độ</th>
                  <th>Chi tiết phát hiện</th>
                </tr>
              </thead>
              <tbody id="audit-table-body">
                <tr><td colspan="5" style="text-align:center; color:var(--tb-text-muted);">Đang tải dữ liệu kiểm toán...</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      `;
    }

    async function triggerSimulatedAttack(attackType) {
      const term = $('sandbox-output');
      term.textContent = `[+] Đang kích hoạt kịch bản tấn công: ${attackType}...\n[+] Gửi HTTP Request độc hại tới Backend Server...`;

      const res = await apiRequest('/api/security/simulate', {
        method: 'POST',
        body: { type: attackType }
      });

      if (res.data) {
        term.textContent = `
================= KẾT QUẢ KIỂM THỬ AN NINH =================
LOẠI TẤN CÔNG  : ${res.data.attack}
HÀNH VI HACKER : ${res.data.attempt}
LỚP BẢO VỆ     : ${res.data.defense}
PHẢN HỒI SERVER: ${res.data.result}
=============================================================
        `.trim();
        loadAuditLogs();
      }
    }

    async function loadAuditLogs() {
      const res = await apiRequest('/api/audit');
      const tbody = $('audit-table-body');
      if (!tbody) return;

      if (res.data.ok && res.data.logs) {
        tbody.innerHTML = res.data.logs.map(log => `
          <tr>
            <td style="font-family:monospace; color:#c9d1d9;">${log.ts}</td>
            <td style="font-family:monospace; color:var(--tb-text-muted);">${log.ip}</td>
            <td style="font-weight:700; color:#fff;">${log.event}</td>
            <td><span class="badge-sev ${log.severity}">${log.severity}</span></td>
            <td style="color:#e6edf3;">${log.detail}</td>
          </tr>
        `).join('');
      }
    }

    // Khởi tạo ban đầu khi mở trang
    window.addEventListener('DOMContentLoaded', () => {
      updateAuthUI();
      switchView('home');
    });
  