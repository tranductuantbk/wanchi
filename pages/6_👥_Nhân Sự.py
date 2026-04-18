import streamlit as st
import pandas as pd
from datetime import date, datetime
from fpdf import FPDF
import os
import time
from db_utils import get_connection, check_password

# 1. Cấu hình trang
st.set_page_config(page_title="Hệ Thống Nhân Sự WANCHI", page_icon="👥", layout="wide")

# 2. Ổ Khóa Bảo Vệ Phần Mềm
if not check_password():
    st.stop()

st.header("👥 Quản Lý Nhân Sự & Chấm Công WANCHI")

conn = get_connection()
c = conn.cursor()

# ==========================================
# CỖ MÁY TỰ ĐỘNG KHỞI TẠO BẢNG DATABASE
# ==========================================
c.execute('''CREATE TABLE IF NOT EXISTS public.nhan_vien (
                id SERIAL PRIMARY KEY,
                ten_nv TEXT UNIQUE,
                bo_phan TEXT,
                luong_cb REAL DEFAULT 0,
                tham_nien REAL DEFAULT 0,
                tien_com REAL DEFAULT 0,
                tc_ngay_thuong_gia REAL DEFAULT 0,
                tc_chu_nhat_gia REAL DEFAULT 0,
                ngay_vao_lam TEXT,
                luong_nang_luc REAL DEFAULT 0,
                phu_cap_khac REAL DEFAULT 0,
                ma_pin TEXT DEFAULT '0000'
            )''')

try: c.execute("ALTER TABLE public.nhan_vien ADD COLUMN ma_pin TEXT DEFAULT '0000'")
except: pass

c.execute('''CREATE TABLE IF NOT EXISTS public.cham_cong (
                id SERIAL PRIMARY KEY,
                ten_nv TEXT,
                ngay TEXT,
                gio_vao TEXT,
                gio_ra TEXT,
                ip_vao TEXT,
                ip_ra TEXT
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS public.cau_hinh (
                id SERIAL PRIMARY KEY,
                ten_cau_hinh TEXT UNIQUE,
                gia_tri TEXT
            )''')
conn.commit()

# --- HÀM BẮT ĐỊA CHỈ IP ---
def get_client_ip():
    try:
        headers = st.context.headers
        ip = headers.get("X-Forwarded-For", "")
        if ip: return ip.split(",")[0].strip()
        return "Không xác định"
    except: return "Không xác định"

try:
    c.execute("SELECT gia_tri FROM public.cau_hinh WHERE ten_cau_hinh='IP_XUONG'")
    row = c.fetchone()
    IP_XUONG = row[0] if row else "Chưa cài đặt"
except:
    IP_XUONG = "Chưa cài đặt"

try: df_nv = pd.read_sql("SELECT * FROM public.nhan_vien ORDER BY id DESC", conn)
except: df_nv = pd.DataFrame()

# ==========================================
# GIAO DIỆN CHÍNH (3 TAB)
# ==========================================
tab1, tab3, tab2 = st.tabs(["📁 Hồ Sơ Nhân Sự", "📱 Chấm Công (Wi-Fi + PIN)", "💸 Tính Lương (Tự Động) & Xuất Phiếu"])

# ==========================================
# TAB 1: QUẢN LÝ HỒ SƠ NHÂN SỰ
# ==========================================
with tab1:
    st.subheader("1. Thêm Nhân Viên Mới")
    with st.form("form_them_nv", clear_on_submit=True):
        col_n1, col_n2, col_n3, col_n4 = st.columns([2, 2, 2, 1])
        with col_n1:
            ten_nv = st.text_input("Tên nhân viên (*)")
            bo_phan = st.text_input("Bộ phận")
            ngay_vao = st.date_input("Ngày vào làm", date.today())
        with col_n2:
            luong_cb = st.number_input("Lương cơ bản (VNĐ/ngày)", min_value=0, value=0, step=10000)
            luong_nl = st.number_input("Lương năng lực (VNĐ/ngày)", min_value=0, value=0, step=10000)
            t_nien_fixed = st.number_input("Tiền thâm niên (VNĐ/ngày)", min_value=0, value=0, step=5000)
        with col_n3:
            t_com_fixed = st.number_input("Tiền cơm (VNĐ/ngày)", min_value=0, value=0, step=5000)
            tc_thuong = st.number_input("Giá TC ngày (VNĐ/giờ)", min_value=0, value=0, step=1000)
            # ĐÃ ĐỔI NHÃN THÀNH (VNĐ/giờ)
            tc_cn = st.number_input("Giá TC CN (VNĐ/giờ)", min_value=0, value=0, step=5000)
        with col_n4:
            phu_cap_khac = st.number_input("Phụ cấp (VNĐ)", min_value=0, value=0, step=10000)
            ma_pin_moi = st.text_input("Mã PIN (4 số)", value="0000", max_chars=4)

        submit_nv = st.form_submit_button("💾 Lưu Hồ Sơ", type="primary")
        if submit_nv and ten_nv:
            try:
                c.execute("""INSERT INTO public.nhan_vien 
                             (ten_nv, bo_phan, ngay_vao_lam, luong_cb, luong_nang_luc, tham_nien, tien_com, tc_ngay_thuong_gia, tc_chu_nhat_gia, phu_cap_khac, ma_pin) 
                             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
                          (ten_nv, bo_phan, ngay_vao.strftime("%Y-%m-%d"), luong_cb, luong_nl, t_nien_fixed, t_com_fixed, tc_thuong, tc_cn, phu_cap_khac, ma_pin_moi))
                st.success(f"✅ Đã lưu hồ sơ {ten_nv}!")
                time.sleep(1.5)
                st.rerun()
            except: st.error("Lỗi: Tên nhân viên đã tồn tại.")

    st.markdown("---")
    st.subheader("2. Danh Sách Nhân Sự Gốc")
    if not df_nv.empty:
        edited_nv = st.data_editor(
            df_nv, hide_index=True, use_container_width=True,
            column_config={"id": None, "ten_nv": st.column_config.TextColumn("Tên NV", disabled=True), "ma_pin": st.column_config.TextColumn("Mã PIN", max_chars=4)}
        )
        if st.button("💾 Lưu Thay Đổi Bảng Nhân Sự"):
            for index, row in edited_nv.iterrows():
                c.execute("""UPDATE public.nhan_vien 
                             SET bo_phan=%s, ngay_vao_lam=%s, luong_cb=%s, luong_nang_luc=%s, tham_nien=%s, tien_com=%s, tc_ngay_thuong_gia=%s, tc_chu_nhat_gia=%s, phu_cap_khac=%s, ma_pin=%s 
                             WHERE id=%s""",
                          (row['bo_phan'], row['ngay_vao_lam'], row['luong_cb'], row['luong_nang_luc'], row['tham_nien'], row['tien_com'], row['tc_ngay_thuong_gia'], row['tc_chu_nhat_gia'], row['phu_cap_khac'], row['ma_pin'], int(row['id'])))
            st.success("Đã cập nhật thay đổi nhân sự!")
            time.sleep(1)
            st.rerun()
    else: st.info("Chưa có nhân sự nào.")

# ==========================================
# TAB 3: CHẤM CÔNG (WI-FI + MÃ PIN)
# ==========================================
with tab3:
    current_ip = get_client_ip()
    hom_nay = date.today().strftime("%d/%m/%Y")
    
    st.markdown(f"### 📍 Điểm danh ngày: **{hom_nay}**")
    with st.expander("⚙️ Cài đặt Cổng Wi-Fi Xưởng"):
        st.write(f"IP Wi-Fi Xưởng đang lưu: `{IP_XUONG}` | IP của bạn: `{current_ip}`")
        if st.button("🔒 Đặt IP hiện tại làm IP Xưởng", type="primary"):
            c.execute("""INSERT INTO public.cau_hinh (ten_cau_hinh, gia_tri) VALUES ('IP_XUONG', %s) 
                         ON CONFLICT (ten_cau_hinh) DO UPDATE SET gia_tri = EXCLUDED.gia_tri""", (current_ip,))
            st.rerun()

    st.markdown("---")
    if df_nv.empty or IP_XUONG == "Chưa cài đặt":
        st.warning("⚠️ Chưa có nhân viên hoặc chưa cài đặt mạng Wi-Fi xưởng!")
    else:
        if current_ip == IP_XUONG:
            st.success(f"📶 Đã kết nối Mạng Nội Bộ WANCHI. Bạn có thể chấm công!")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                nv_cham_cong = st.selectbox("🙋‍♂️ Chọn tên của bạn:", ["-- Chọn Tên --"] + df_nv['ten_nv'].tolist())
            with col_c2:
                if nv_cham_cong != "-- Chọn Tên --":
                    real_pin = df_nv[df_nv['ten_nv'] == nv_cham_cong].iloc[0]['ma_pin']
                    pin_nhap = st.text_input("Nhập mã PIN bí mật của bạn:", type="password", max_chars=4)
                    
                    c.execute("SELECT gio_vao, gio_ra FROM public.cham_cong WHERE ten_nv=%s AND ngay=%s", (nv_cham_cong, hom_nay))
                    trang_thai = c.fetchone()
                    gio_hien_tai = datetime.now().strftime("%H:%M")
                    
                    if pin_nhap == real_pin:
                        if not trang_thai:
                            if st.button("🟢 VÀO CA (Check-in)", type="primary", use_container_width=True):
                                c.execute("INSERT INTO public.cham_cong (ten_nv, ngay, gio_vao, ip_vao) VALUES (%s, %s, %s, %s)", (nv_cham_cong, hom_nay, gio_hien_tai, current_ip))
                                st.rerun()
                        else:
                            if trang_thai[1] is None:
                                st.info(f"Đã vào ca lúc: {trang_thai[0]}")
                                if st.button("🔴 TAN CA (Check-out)", type="primary", use_container_width=True):
                                    c.execute("UPDATE public.cham_cong SET gio_ra=%s, ip_ra=%s WHERE ten_nv=%s AND ngay=%s", (gio_hien_tai, current_ip, nv_cham_cong, hom_nay))
                                    st.rerun()
                            else:
                                st.success(f"✅ Đã hoàn thành. Vào: {trang_thai[0]} | Ra: {trang_thai[1]}")
                    elif pin_nhap != "": st.error("❌ Mã PIN sai!")
        else:
            st.error(f"🛑 Bạn đang dùng mạng ngoài. Vui lòng kết nối Wi-Fi Xưởng WANCHI!")

    st.markdown("---")
    try:
        df_cc = pd.read_sql(f"SELECT ten_nv, gio_vao, gio_ra FROM public.cham_cong WHERE ngay='{hom_nay}' ORDER BY gio_vao DESC", conn)
        if not df_cc.empty:
            df_cc.columns = ["Tên Nhân Viên", "Giờ Vào", "Giờ Ra"]
            st.dataframe(df_cc, use_container_width=True, hide_index=True)
    except: pass

# ==========================================
# TAB 2: TÍNH LƯƠNG TỰ ĐỘNG & XUẤT PDF
# ==========================================
with tab2:
    if df_nv.empty:
        st.warning("⚠️ Vui lòng khai báo nhân sự ở Tab 1 trước!")
    else:
        st.subheader("BƯỚC 1: Chọn Nhân Viên & Tự Động Tính Công")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            chon_nv_luong = st.selectbox("Chọn nhân viên:", df_nv['ten_nv'].tolist(), key="chon_nv_luong_pdf")
            nv_data = df_nv[df_nv['ten_nv'] == chon_nv_luong].iloc[0]
        with col_s2:
            ky_luong_str = st.text_input("Kỳ lương (MM/YYYY)", value=date.today().strftime("%m/%Y"))

        # --- AI TỰ ĐỘNG QUÉT VÀ TÍNH TOÁN GIỜ LÀM TRONG THÁNG ---
        c.execute("SELECT ngay, gio_vao, gio_ra FROM public.cham_cong WHERE ten_nv=%s AND ngay LIKE %s", (chon_nv_luong, f"%/{ky_luong_str}"))
        bang_cong = c.fetchall()

        auto_ngay_cong = 0.0
        auto_tc_thuong = 0.0
        auto_tc_cn = 0.0

        for r in bang_cong:
            ngay_str, g_vao, g_ra = r
            if not g_ra: g_ra = "17:00" # Quy tắc 2: Quên bấm ra thì auto gán 17:00
            
            try:
                d = datetime.strptime(ngay_str, "%d/%m/%Y")
                is_sunday = (d.weekday() == 6)
                
                t_in = datetime.strptime(g_vao, "%H:%M")
                t_out = datetime.strptime(g_ra, "%H:%M")
                if t_out < t_in: t_out = datetime.strptime("17:00", "%H:%M") # Chống lỗi logic
                
                # Chia khung giờ
                m_start, m_end = datetime.strptime("07:30", "%H:%M"), datetime.strptime("11:30", "%H:%M")
                a_start, a_end = datetime.strptime("13:00", "%H:%M"), datetime.strptime("17:00", "%H:%M")
                ot_start, ot_end = datetime.strptime("17:00", "%H:%M"), datetime.strptime("23:59", "%H:%M")
                
                def intersect(t1, t2, r1, r2):
                    s = max(t1, r1)
                    e = min(t2, r2)
                    return max(0, (e - s).total_seconds() / 60)
                
                std_mins = intersect(t_in, t_out, m_start, m_end) + intersect(t_in, t_out, a_start, a_end)
                ot_mins = intersect(t_in, t_out, ot_start, ot_end)
                
                if is_sunday:
                    auto_tc_cn += (std_mins + ot_mins) / 60.0 # Quy tắc 3: CN tính theo giờ, gộp hết
                else:
                    auto_ngay_cong += (std_mins / 60.0) / 8.0 # Quy tắc 1: 8 tiếng = 1 ngày công, đi trễ tự trừ
                    auto_tc_thuong += (ot_mins / 60.0)        # Quy tắc 1: Về sau 17h tự cộng vào TC
            except: pass

        ngay_vao_str = nv_data.get('ngay_vao_lam')
        if pd.isna(ngay_vao_str) or not ngay_vao_str: ngay_vao_str = date.today().strftime("%Y-%m-%d")
        try:
            d_vao = datetime.strptime(ngay_vao_str, "%Y-%m-%d")
            d_ky_luong = datetime.strptime(ky_luong_str, "%m/%Y")
            so_thang_tn = (d_ky_luong.year - d_vao.year) * 12 + (d_ky_luong.month - d_vao.month)
            if so_thang_tn < 0: so_thang_tn = 0
            so_nam_tn = round(so_thang_tn / 12, 1)
            hien_thi_nam = f"{int(so_nam_tn)}" if so_nam_tn.is_integer() else f"{so_nam_tn}"
        except: hien_thi_nam = "0"; d_vao = date.today()

        st.info(f"📅 Cỗ máy đã quét **{len(bang_cong)}** lượt chấm công trong tháng này. Dữ liệu đã được tự động điền vào bảng bên dưới 👇")

        st.markdown("---")
        st.subheader("BƯỚC 2: Kiểm Tra Biến Số & Tính Toán")
        
        def s_int(val): return int(val) if pd.notna(val) else 0

        col_l1, col_l2, col_l3 = st.columns(3)
        with col_l1:
            st.caption("CÁC KHOẢN CỐ ĐỊNH")
            l_cb = st.number_input("Lương cơ bản", value=s_int(nv_data.get('luong_cb', 0)), step=10000)
            l_nl = st.number_input("Lương năng lực", value=s_int(nv_data.get('luong_nang_luc', 0)), step=10000)
            t_nien = st.number_input("Tiền thâm niên", value=s_int(nv_data.get('tham_nien', 0)), step=5000)
            t_com = st.number_input("Tiền cơm", value=s_int(nv_data.get('tien_com', 0)), step=5000)
            p_cap = st.number_input("Phụ cấp cố định", value=s_int(nv_data.get('phu_cap_khac', 0)), step=10000)

        with col_l2:
            st.caption("DỮ LIỆU TỰ ĐỘNG TỪ MÁY CHẤM CÔNG (Có thể sửa tay)")
            ngay_cong = st.number_input("Ngày công thực tế", min_value=0.0, value=float(round(auto_ngay_cong, 2)), step=0.5)
            tc_thuong_gio = st.number_input("Giờ TC ngày thường", min_value=0.0, value=float(round(auto_tc_thuong, 2)), step=0.5)
            tc_cn_gio = st.number_input("Giờ TC Chủ Nhật", min_value=0.0, value=float(round(auto_tc_cn, 2)), step=0.5)

        with col_l3:
            st.caption("THƯỞNG & KHẤU TRỪ")
            thuong = st.number_input("Thưởng thêm", min_value=0, value=0, step=100000)
            tam_ung = st.number_input("Tạm ứng đợt 1", min_value=0, value=0, step=100000)
            khau_tru = st.number_input("Khấu trừ / Phạt", min_value=0, value=0, step=50000)
            ghi_chu = st.text_area("Ghi chú", value="")

        tien_cb = l_cb * ngay_cong
        tien_nl = l_nl * ngay_cong
        tien_tn = t_nien * ngay_cong
        tien_com_th = t_com * ngay_cong
        tien_tc_t = float(nv_data.get('tc_ngay_thuong_gia', 0) or 0) * tc_thuong_gio
        tien_tc_c = float(nv_data.get('tc_chu_nhat_gia', 0) or 0) * tc_cn_gio
        
        gross = tien_cb + tien_nl + tien_tn + tien_com_th + tien_tc_t + tien_tc_c + p_cap + thuong
        tong_kt = tam_ung + khau_tru
        thuc_lanh = gross - tong_kt

        st.markdown(f"### 💰 THỰC LÃNH CUỐI CÙNG: **{thuc_lanh:,.0f} VNĐ**")

        def create_payslip_pdf():
            pdf = FPDF(orientation='L', format='A5')
            pdf.add_page()
            if not (os.path.exists("arial.ttf") and os.path.exists("arialbd.ttf")): return None
            pdf.add_font("Arial", "", "arial.ttf", uni=True)
            pdf.add_font("Arial", "B", "arialbd.ttf", uni=True)

            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, "PHIẾU LƯƠNG NHÂN VIÊN", align="C", ln=True)
            pdf.ln(2)

            pdf.set_font("Arial", "B", 10)
            pdf.cell(25, 6, "Nhân viên:"); pdf.set_font("Arial", "", 10); pdf.cell(65, 6, chon_nv_luong)
            pdf.set_font("Arial", "B", 10); pdf.cell(35, 6, "Vào làm:"); pdf.set_font("Arial", "", 10); pdf.cell(0, 6, d_vao.strftime('%d/%m/%Y'), ln=True)

            pdf.set_font("Arial", "B", 10)
            pdf.cell(25, 6, "Bộ phận:"); pdf.set_font("Arial", "", 10); pdf.cell(65, 6, nv_data.get('bo_phan', ''))
            pdf.set_font("Arial", "B", 10); pdf.cell(35, 6, "Thâm niên:"); pdf.set_font("Arial", "B", 10); pdf.cell(0, 6, f"{hien_thi_nam} năm", ln=True)
            pdf.ln(4)

            w = [10, 65, 25, 35, 55]
            pdf.set_fill_color(220, 220, 220)
            for i, h in enumerate(["STT", "KHOẢN MỤC", "SỐ LƯỢNG", "ĐƠN GIÁ", "THÀNH TIỀN"]):
                pdf.cell(w[i], 8, h, 1, 0 if i<4 else 1, 'C', True)

            def f(n): return f"{n:,.0f}".replace(",", ".")
            def r(s, n, sl, dg, tt):
                pdf.set_font("Arial", "", 10)
                pdf.cell(w[0], 7, s, 1, 0, 'C'); pdf.cell(w[1], 7, " " + n, 1, 0, 'L')
                pdf.cell(w[2], 7, sl, 1, 0, 'C'); pdf.cell(w[3], 7, dg, 1, 0, 'R'); pdf.cell(w[4], 7, tt, 1, 1, 'R')

            def s(n, tt, bold=False):
                pdf.set_font("Arial", "B" if bold else "", 10)
                pdf.cell(sum(w[:4]), 8, n, 1, 0, 'R'); pdf.cell(w[4], 8, tt, 1, 1, 'R')

            pdf.set_font("Arial", "B", 10); pdf.set_fill_color(240, 240, 240); pdf.cell(sum(w), 8, "  I. THU NHẬP", 1, 1, 'L', True)

            r("1", "Lương cơ bản", f"{ngay_cong}".replace('.', ','), f(l_cb), f(tien_cb))
            r("2", "Lương năng lực", f"{ngay_cong}".replace('.', ','), f(l_nl), f(tien_nl))
            r("3", "Tiền thâm niên", f"{ngay_cong}".replace('.', ','), f(t_nien), f(tien_tn))
            r("4", "Tiền cơm", f"{ngay_cong}".replace('.', ','), f(t_com), f(tien_com_th))
            r("5", "Tăng ca ngày thường", f"{tc_thuong_gio}".replace('.', ','), f(nv_data.get('tc_ngay_thuong_gia',0)), f(tien_tc_t))
            r("6", "Tăng ca chủ nhật", f"{tc_cn_gio}".replace('.', ','), f(nv_data.get('tc_chu_nhat_gia',0)), f(tien_tc_c))
            r("7", "Phụ cấp cố định", "", "", f(p_cap))
            r("8", "Thưởng thêm", "", "", f(thuong))
            s("Tổng thu nhập (Gross): ", f(gross) + "  ", True)
            
            pdf.set_font("Arial", "B", 10); pdf.set_fill_color(240, 240, 240); pdf.cell(sum(w), 8, "  II. KHẤU TRỪ", 1, 1, 'L', True)
            r("9", "Tạm ứng đợt 1", "", "", f(tam_ung))
            r("10", "Khấu trừ / Phạt", "", "", f(khau_tru))
            s("Tổng khấu trừ: ", f(tong_kt) + "  ", True)

            pdf.set_font("Arial", "B", 10); pdf.set_fill_color(240, 240, 240); pdf.cell(sum(w), 8, "  III. THỰC LÃNH", 1, 1, 'L', True)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(sum(w[:4]), 10, "THỰC LÃNH (I - II): ", 1, 0, 'R')
            pdf.cell(w[4], 10, f(thuc_lanh) + " đ  ", 1, 1, 'R')

            if ghi_chu:
                pdf.ln(2); pdf.set_font("Arial", "B", 10); pdf.cell(20, 6, "Nhận xét:")
                pdf.set_font("Arial", "", 10); pdf.multi_cell(0, 6, ghi_chu); pdf.ln(1)
            else: pdf.ln(4)

            return bytes(pdf.output())

        st.subheader("BƯỚC 3: Tải Phiếu Lương")
        pdf_data = create_payslip_pdf()
        if pdf_data:
            st.download_button(f"🖨️ Tải PDF Phiếu Lương - {chon_nv_luong}", pdf_data, f"Phieu_Luong_{chon_nv_luong}.pdf", "application/pdf", type="primary")
