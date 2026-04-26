import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta, timezone
from fpdf import FPDF
import os
import time
import random
from db_utils import get_connection, check_password

# ==========================================
# 🔑 CẤU HÌNH MẬT KHẨU GIÁM ĐỐC (ĐỔI TẠI ĐÂY)
# ==========================================
MAT_KHAU_GIAM_DOC = "tuanquang" 

# ==========================================
# Ổ KHÓA BẢO VỆ 1 & 2 (Quyền truy cập chung)
# ==========================================
role = check_password()
if not role: st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: hồ sơ nhân sự là dữ liệu tuyệt mật của Quản lý.")
    st.stop()
# ==========================================
# Ổ KHÓA BẢO VỆ 3 (KÉT SẮT TÀI CHÍNH)
# ==========================================
if 'dashboard_unlocked' not in st.session_state:
    st.session_state.dashboard_unlocked = False

if not st.session_state.dashboard_unlocked:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col_khoa1, col_khoa2, col_khoa3 = st.columns([1, 2, 1])
    with col_khoa2:
        st.warning("🔒 **BẢO MẬT CẤP CAO:** Vui lòng nhập Mã PIN Giám Đốc để xem Báo cáo tài chính.")
        with st.form("form_mat_khau"):
            pin_input = st.text_input("Mã PIN / Mật khẩu:", type="password")
            if st.form_submit_button("🔓 Mở Khóa Két Sắt", type="primary", use_container_width=True):
                if pin_input == MAT_KHAU_GIAM_DOC:
                    st.session_state.dashboard_unlocked = True
                    st.rerun()
                else:
                    st.error("❌ Mã PIN không chính xác!")
    st.stop() # Chặn đứng mọi đoạn code bên dưới nếu chưa mở khóa

# ==========================================
# CẤU HÌNH MÚI GIỜ VIỆT NAM (UTC+7)
# ==========================================
VN_TZ = timezone(timedelta(hours=7))

def lay_gio_vn():
    """Hàm luôn trả về ngày giờ chính xác tại Việt Nam"""
    return datetime.now(VN_TZ)

st.set_page_config(page_title="Hệ Thống Nhân Sự WANCHI", page_icon="👥", layout="wide")

# 1. Ổ Khóa Nhận Diện Vai Trò
role = check_password()
if not role:
    st.stop()

# 2. Kết nối DB và khởi tạo bảng
conn = get_connection()
c = conn.cursor()

# Đảm bảo có bảng cấu hình để lưu mã ca
c.execute('''CREATE TABLE IF NOT EXISTS public.cau_hinh (
                id SERIAL PRIMARY KEY, ten_cau_hinh TEXT UNIQUE, gia_tri TEXT
            )''')
conn.commit()

# --- HÀM TRUY XUẤT MÃ CA ---
def lay_thong_tin_ma_ca():
    try:
        c.execute("SELECT gia_tri FROM public.cau_hinh WHERE ten_cau_hinh='MA_CA_HIEN_TAI'")
        r1 = c.fetchone()
        c.execute("SELECT gia_tri FROM public.cau_hinh WHERE ten_cau_hinh='THOI_GIAN_TAO_MA'")
        r2 = c.fetchone()
        if r1 and r2:
            return r1[0], r2[0]
    except: pass
    return None, None

try: df_nv = pd.read_sql("SELECT * FROM public.nhan_vien ORDER BY id DESC", conn)
except: df_nv = pd.DataFrame()

# ==========================================
# GIAO DIỆN PHÂN QUYỀN
# ==========================================
if role == "admin":
    st.header("👥 Quản Lý Nhân Sự & Lương WANCHI")
    tab1, tab3, tab2 = st.tabs(["📁 Hồ Sơ Nhân Sự", "📱 Chấm Công", "💸 Tính Lương & Xuất Phiếu"])
    container_cham_cong = tab3
    
    # --- TAB 1: HỒ SƠ --- (Giữ nguyên như cũ)
    with tab1:
        st.subheader("1. Thêm Nhân Viên Mới")
        with st.form("form_them_nv", clear_on_submit=True):
            col_n1, col_n2, col_n3, col_n4 = st.columns([2, 2, 2, 1])
            with col_n1:
                ten_nv = st.text_input("Tên nhân viên (*)")
                bo_phan = st.text_input("Bộ phận")
                ngay_vao = st.date_input("Ngày vào làm", lay_gio_vn().date())
            with col_n2:
                luong_cb = st.number_input("Lương cơ bản (VNĐ/ngày)", min_value=0, value=0, step=10000)
                luong_nl = st.number_input("Lương năng lực (VNĐ/ngày)", min_value=0, value=0, step=10000)
                t_nien_fixed = st.number_input("Tiền thâm niên (VNĐ/ngày)", min_value=0, value=0, step=5000)
            with col_n3:
                t_com_fixed = st.number_input("Tiền cơm (VNĐ/ngày)", min_value=0, value=0, step=5000)
                tc_thuong = st.number_input("Giá TC ngày (VNĐ/giờ)", min_value=0, value=0, step=1000)
                tc_cn = st.number_input("Giá TC CN (VNĐ/giờ)", min_value=0, value=0, step=5000)
            with col_n4:
                phu_cap_khac = st.number_input("Phụ cấp (VNĐ)", min_value=0, value=0, step=10000)
                ma_pin_moi = st.text_input("Mã PIN (4 số)", value="0000", max_chars=4)

            if st.form_submit_button("💾 Lưu Hồ Sơ", type="primary") and ten_nv:
                try:
                    c.execute("""INSERT INTO public.nhan_vien 
                                 (ten_nv, bo_phan, ngay_vao_lam, luong_cb, luong_nang_luc, tham_nien, tien_com, tc_ngay_thuong_gia, tc_chu_nhat_gia, phu_cap_khac, ma_pin) 
                                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
                              (ten_nv.strip(), bo_phan, ngay_vao.strftime("%Y-%m-%d"), luong_cb, luong_nl, t_nien_fixed, t_com_fixed, tc_thuong, tc_cn, phu_cap_khac, ma_pin_moi))
                    st.success(f"✅ Đã lưu hồ sơ {ten_nv}!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e: st.error("Lỗi: Tên nhân viên này đã tồn tại!")

        st.markdown("---")
        st.subheader("2. Danh Sách Nhân Sự")
        if not df_nv.empty:
            disabled_cols = df_nv.columns.tolist()
            df_nv.insert(0, "Xóa", False)
            edited_nv = st.data_editor(
                df_nv, hide_index=True, use_container_width=True, disabled=disabled_cols,
                column_config={"Xóa": st.column_config.CheckboxColumn("🗑️ Xóa", default=False), "id": None, "ma_pin": st.column_config.TextColumn("Mã PIN", max_chars=4)}
            )
            if st.button("🚨 Xóa Nhân Sự Đã Chọn", type="primary"):
                for index, row in edited_nv.iterrows():
                    if row['Xóa']:
                        c.execute("DELETE FROM public.nhan_vien WHERE id=%s", (int(row['id']),))
                st.success("✅ Đã cập nhật danh sách.")
                time.sleep(1)
                st.rerun()

    # --- TAB 2: LƯƠNG --- (Giữ nguyên như cũ)
    with tab2:
        if df_nv.empty: st.warning("⚠️ Vui lòng khai báo nhân sự ở Tab 1 trước!")
        else:
            st.subheader("BƯỚC 1: Chọn Nhân Viên & Tự Động Tính Công")
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                chon_nv_luong = st.selectbox("Chọn nhân viên:", df_nv['ten_nv'].tolist(), key="chon_nv_luong_pdf")
                nv_data = df_nv[df_nv['ten_nv'] == chon_nv_luong].iloc[0]
            with col_s2:
                ky_luong_str = st.text_input("Kỳ lương (MM/YYYY)", value=lay_gio_vn().strftime("%m/%Y"))

            c.execute("SELECT ngay, gio_vao, gio_ra FROM public.cham_cong WHERE ten_nv=%s AND ngay LIKE %s", (chon_nv_luong, f"%/{ky_luong_str}"))
            bang_cong = c.fetchall()

            auto_ngay_cong, auto_tc_thuong, auto_tc_cn = 0.0, 0.0, 0.0
            for r in bang_cong:
                ngay_str, g_vao, g_ra = r
                if not g_ra: g_ra = "17:00" 
                try:
                    d = datetime.strptime(ngay_str, "%d/%m/%Y")
                    is_sunday = (d.weekday() == 6)
                    t_in = datetime.strptime(g_vao, "%H:%M")
                    t_out = datetime.strptime(g_ra, "%H:%M")
                    
                    m_start, m_end = datetime.strptime("07:30", "%H:%M"), datetime.strptime("11:30", "%H:%M")
                    a_start, a_end = datetime.strptime("13:00", "%H:%M"), datetime.strptime("17:00", "%H:%M")
                    ot_start = datetime.strptime("17:00", "%H:%M")
                    
                    def intersect(t1, t2, r1, r2):
                        s, e = max(t1, r1), min(t2, r2)
                        return max(0, (e - s).total_seconds() / 3600)
                    
                    std_hrs = intersect(t_in, t_out, m_start, m_end) + intersect(t_in, t_out, a_start, a_end)
                    ot_hrs = max(0, (t_out - ot_start).total_seconds() / 3600) if t_out > ot_start else 0
                    
                    if is_sunday: auto_tc_cn += std_hrs + ot_hrs
                    else:
                        auto_ngay_cong += std_hrs / 8.0 
                        auto_tc_thuong += ot_hrs      
                except: pass

            st.info(f"📅 Hệ thống quét được **{len(bang_cong)}** ngày chấm công.")
            st.markdown("---")
            def s_int(val): return int(val) if pd.notna(val) else 0

            col_l1, col_l2, col_l3 = st.columns(3)
            with col_l1:
                l_cb = st.number_input("Lương cơ bản", value=s_int(nv_data.get('luong_cb', 0)), step=10000)
                l_nl = st.number_input("Lương năng lực", value=s_int(nv_data.get('luong_nang_luc', 0)), step=10000)
                t_nien = st.number_input("Tiền thâm niên", value=s_int(nv_data.get('tham_nien', 0)), step=5000)
                t_com = st.number_input("Tiền cơm", value=s_int(nv_data.get('tien_com', 0)), step=5000)
                p_cap = st.number_input("Phụ cấp cố định", value=s_int(nv_data.get('phu_cap_khac', 0)), step=10000)

            with col_l2:
                ngay_cong = st.number_input("Ngày công", min_value=0.0, value=float(round(auto_ngay_cong, 2)), step=0.5)
                tc_thuong_gio = st.number_input("Giờ TC ngày", min_value=0.0, value=float(round(auto_tc_thuong, 2)), step=0.5)
                tc_cn_gio = st.number_input("Giờ TC Chủ Nhật", min_value=0.0, value=float(round(auto_tc_cn, 2)), step=0.5)

            with col_l3:
                thuong = st.number_input("Thưởng thêm", min_value=0, value=0, step=100000)
                tam_ung = st.number_input("Tạm ứng / Phạt", min_value=0, value=0, step=50000)
                ghi_chu = st.text_area("Ghi chú", value="")

            tien_cb, tien_nl, tien_tn, tien_com_th = l_cb * ngay_cong, l_nl * ngay_cong, t_nien * ngay_cong, t_com * ngay_cong
            tien_tc_t = float(nv_data.get('tc_ngay_thuong_gia', 0)) * tc_thuong_gio
            tien_tc_c = float(nv_data.get('tc_chu_nhat_gia', 0)) * tc_cn_gio
            gross = tien_cb + tien_nl + tien_tn + tien_com_th + tien_tc_t + tien_tc_c + p_cap + thuong
            thuc_lanh = gross - tam_ung

            st.markdown(f"### 💰 THỰC LÃNH: **{thuc_lanh:,.0f} VNĐ**")

else:
    # NẾU LÀ NHÂN VIÊN
    st.markdown("<h2 style='text-align: center; color: #4CAF50;'>📱 HỆ THỐNG CHẤM CÔNG WANCHI</h2>", unsafe_allow_html=True)
    container_cham_cong = st.container()

# ==========================================
# KHU VỰC CHẤM CÔNG (MÃ CA LÀM VIỆC)
# ==========================================
with container_cham_cong:
    ma_ca, thoi_gian_tao = lay_thong_tin_ma_ca()
    hom_nay = lay_gio_vn().strftime("%d/%m/%Y")
    gio_hien_tai = lay_gio_vn().strftime("%H:%M")
    
    st.markdown(f"### 📍 Điểm danh ngày: **{hom_nay}**")

    # --- PHẦN ADMIN: TẠO MÃ ---
    if role == "admin":
        with st.expander("🔑 QUẢN LÝ MÃ CHẤM CÔNG (Dành cho Chủ xưởng)"):
            if ma_ca:
                tg_tao_dt = datetime.fromisoformat(thoi_gian_tao)
                # ĐÃ SỬA THỜI GIAN HẾT HẠN XUỐNG 18 TIẾNG
                tg_het_han = tg_tao_dt + timedelta(hours=18)
                st.write(f"Mã hiện tại: **{ma_ca}** (Tạo lúc: {tg_tao_dt.strftime('%H:%M %d/%m')})")
                if lay_gio_vn() > tg_het_han:
                    st.error("⚠️ Mã này đã hết hạn 18h! Vui lòng tạo mã mới.")
                else:
                    st.success(f"Mã còn hiệu lực đến: {tg_het_han.strftime('%H:%M %d/%m')}")
            
            # ĐÃ CẬP NHẬT TÊN NÚT HIỂN THỊ
            if st.button("🔄 TẠO MÃ CA MỚI (Hiệu lực 18h)", type="primary"):
                moi_ma = str(random.randint(1000, 9999))
                bay_gio = lay_gio_vn().isoformat()
                c.execute("INSERT INTO public.cau_hinh (ten_cau_hinh, gia_tri) VALUES ('MA_CA_HIEN_TAI', %s) ON CONFLICT (ten_cau_hinh) DO UPDATE SET gia_tri = EXCLUDED.gia_tri", (moi_ma,))
                c.execute("INSERT INTO public.cau_hinh (ten_cau_hinh, gia_tri) VALUES ('THOI_GIAN_TAO_MA', %s) ON CONFLICT (ten_cau_hinh) DO UPDATE SET gia_tri = EXCLUDED.gia_tri", (bay_gio,))
                conn.commit()
                st.rerun()

    st.markdown("---")

    # --- PHẦN NHÂN VIÊN: CHẤM CÔNG ---
    if not ma_ca:
        st.warning("⚠️ Chủ xưởng chưa tạo mã ca làm việc. Vui lòng liên hệ Admin!")
    else:
        # Kiểm tra thời hạn mã
        tg_tao_dt = datetime.fromisoformat(thoi_gian_tao)
        # ĐÃ SỬA ĐIỀU KIỆN CHẶN CHẤM CÔNG XUỐNG 18 TIẾNG
        if lay_gio_vn() > (tg_tao_dt + timedelta(hours=18)):
            st.error("🛑 Mã ca làm việc đã hết hạn. Vui lòng báo Admin tạo mã mới!")
        else:
            col_c1, col_c2, col_c3 = st.columns([2, 1, 1])
            with col_c1:
                nv_cham_cong = st.selectbox("🙋‍♂️ Chọn tên của bạn:", ["-- Chọn Tên --"] + df_nv['ten_nv'].tolist())
            with col_c2:
                pin_nhap = st.text_input("Mã PIN cá nhân:", type="password", max_chars=4)
            with col_c3:
                ma_ca_nhap = st.text_input("Mã CA tại xưởng:", type="password", max_chars=4, help="Nhìn mã trên máy tính của xưởng")

            if nv_cham_cong != "-- Chọn Tên --" and pin_nhap and ma_ca_nhap:
                real_pin = df_nv[df_nv['ten_nv'] == nv_cham_cong].iloc[0]['ma_pin']
                
                if ma_ca_nhap == ma_ca:
                    if pin_nhap == real_pin:
                        c.execute("SELECT gio_vao, gio_ra FROM public.cham_cong WHERE ten_nv=%s AND ngay=%s", (nv_cham_cong, hom_nay))
                        trang_thai = c.fetchone()
                        
                        col_b1, col_b2 = st.columns(2)
                        if not trang_thai:
                            if col_b1.button("🟢 VÀO CA (Check-in)", type="primary", use_container_width=True):
                                c.execute("INSERT INTO public.cham_cong (ten_nv, ngay, gio_vao) VALUES (%s, %s, %s)", (nv_cham_cong, hom_nay, gio_hien_tai))
                                conn.commit()
                                st.success(f"✅ Đã vào ca lúc {gio_hien_tai}")
                                time.sleep(1); st.rerun()
                        elif trang_thai[1] is None:
                            st.info(f"Bạn đã vào ca lúc: {trang_thai[0]}")
                            if col_b2.button("🔴 TAN CA (Check-out)", type="primary", use_container_width=True):
                                c.execute("UPDATE public.cham_cong SET gio_ra=%s WHERE ten_nv=%s AND ngay=%s", (gio_hien_tai, nv_cham_cong, hom_nay))
                                conn.commit()
                                st.success(f"✅ Đã tan ca lúc {gio_hien_tai}")
                                time.sleep(1); st.rerun()
                        else:
                            st.success(f"✅ Đã hoàn thành ngày công. ({trang_thai[0]} - {trang_thai[1]})")
                    else: st.error("❌ Mã PIN cá nhân sai!")
                else: st.error("❌ Mã CA TẠI XƯỞNG không đúng!")

    st.markdown("---")
    try:
        df_cc = pd.read_sql(f"SELECT ten_nv, gio_vao, gio_ra FROM public.cham_cong WHERE ngay='{hom_nay}' ORDER BY gio_vao DESC", conn)
        if not df_cc.empty:
            df_cc.columns = ["Tên Nhân Viên", "Giờ Vào", "Giờ Ra"]
            st.dataframe(df_cc, use_container_width=True, hide_index=True)
    except: pass
