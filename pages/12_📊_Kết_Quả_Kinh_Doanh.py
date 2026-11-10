import streamlit as st
import pandas as pd
from datetime import date
import time
from db_utils import get_connection, check_password

st.set_page_config(page_title="Kết Quả Kinh Doanh", page_icon="📊", layout="wide")

# ==========================================
# Ổ KHÓA BẢO VỆ 2 LỚP - PHÂN QUYỀN
# ==========================================
role = check_password()
if not role: st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang Báo Cáo Kinh Doanh là dữ liệu mật, chỉ dành cho Quản lý.")
    st.stop()

# ==========================================
# 🔑 KHÓA BẢO VỆ CẤP GIÁM ĐỐC
# ==========================================
MAT_KHAU_GIAM_DOC = "tbk1102"

if 'bao_cao_unlocked' not in st.session_state:
    st.session_state.bao_cao_unlocked = False

st.header("📊 Báo Cáo Kết Quả Kinh Doanh")

if not st.session_state.bao_cao_unlocked:
    st.markdown("<br>", unsafe_allow_html=True)
    col_khoa1, col_khoa2, col_khoa3 = st.columns([1, 2, 1])
    with col_khoa2:
        st.warning("🔒 **BẢO MẬT CẤP CAO:** Vui lòng nhập Mã PIN Giám Đốc để xem Báo Cáo Tài Chính.")
        with st.form("form_mat_khau_baocao"):
            pin_input = st.text_input("Mã PIN / Mật khẩu:", type="password")
            if st.form_submit_button("🔓 Mở Khóa Báo Cáo", type="primary", use_container_width=True):
                if pin_input == MAT_KHAU_GIAM_DOC:
                    st.session_state.bao_cao_unlocked = True
                    st.rerun()
                else: 
                    st.error("❌ Mã PIN không chính xác!")
    st.stop()

# Nút khóa lại
if st.button("🔒 Khóa Lại Báo Cáo", key="lock_baocao"):
    st.session_state.bao_cao_unlocked = False
    st.rerun()

conn = get_connection()
c = conn.cursor()

# ==========================================
# KHỞI TẠO BẢNG CHI PHÍ TỰ NHẬP
# ==========================================
try:
    c.execute('''CREATE TABLE IF NOT EXISTS chi_phi_khac (
                    id SERIAL PRIMARY KEY,
                    ngay TEXT,
                    dien_giai TEXT,
                    so_tien REAL
                )''')
    conn.commit()
except Exception as e:
    conn.rollback()

# ==========================================
# GIAO DIỆN CHỌN THÁNG (ĐỊNH DẠNG THÁNG/NĂM)
# ==========================================
today = date.today()
list_months_display = []

# Tạo danh sách 12 tháng (Tháng hiện tại và 11 tháng trước đó)
for i in range(12):
    m = today.month - i
    y = today.year
    while m <= 0:
        m += 12
        y -= 1
    list_months_display.append(f"{m:02d}/{y}")

st.markdown("### 🗓️ Chọn Kỳ Báo Cáo")
thang_chon_display = st.selectbox("Lọc dữ liệu theo tháng/năm:", list_months_display, index=0)

m_str, y_str = thang_chon_display.split('/')

# BỘ LỌC ĐỒNG BỘ: Chuẩn ngày tháng trong bảng lịch sử kho là DD/MM/YYYY
pattern_thang_vn = f"%/{m_str}/{y_str}%"
# Bộ lọc ISO cho bảng chi phí tự nhập là YYYY-MM-DD
pattern_thang_iso = f"{y_str}-{m_str}-%"

# ==========================================
# TRÍCH XUẤT DỮ LIỆU TỪ HỆ THỐNG MỚI NHẤT
# ==========================================
doanh_so = 0.0
thuc_thu = 0.0
gia_von = 0.0
thanh_toan_ncc = 0.0
chi_phi_tu_nhap = 0.0

# 1. DOANH SỐ (YÊU CẦU MỚI: CHỈ LẤY ĐƠN ĐÃ XUẤT KHO VÀ ĐÃ THANH TOÁN)
# Trong bảng ls_nhap_xuat_kho, đơn xuất kho có loai_thao_tac = 'Xuất Bán'. 
# Đơn 'Đã thanh toán' sẽ có cột trang_thai_tt = 'Đã thanh toán'.
try:
    c.execute("SELECT SUM(thanh_tien), SUM(tien_da_thu) FROM public.ls_nhap_xuat_kho WHERE loai_thao_tac = 'Xuất Bán' AND trang_thai_tt = 'Đã thanh toán' AND ngay_thao_tac LIKE %s", (pattern_thang_vn,))
    res = c.fetchone()
    doanh_so = float(res[0]) if res and res[0] else 0.0
    thuc_thu = float(res[1]) if res and res[1] else 0.0
except Exception as e:
    pass

# 2. GIÁ VỐN HÀNG BÁN (Ánh xạ từ danh mục sản phẩm chuẩn - chỉ lấy của các đơn Đã xuất kho VÀ Đã thanh toán)
try:
    df_sp = pd.read_sql("SELECT ten_sp, gia_von FROM dm_san_pham", conn)
    dict_gia_von = dict(zip(df_sp['ten_sp'], df_sp['gia_von']))
    
    try:
        df_ome = pd.read_sql("SELECT ten_sp, gia_von FROM dm_san_pham_ome", conn)
        dict_gia_von.update(dict(zip(df_ome['ten_sp'], df_ome['gia_von'])))
    except:
        pass
    
    # Quét bảng lịch sử để tính giá vốn những mặt hàng đã xuất bán VÀ Đã thanh toán
    c.execute("SELECT ten_nl, so_luong FROM public.ls_nhap_xuat_kho WHERE loai_thao_tac = 'Xuất Bán' AND trang_thai_tt = 'Đã thanh toán' AND ngay_thao_tac LIKE %s", (pattern_thang_vn,))
    cac_mat_hang = c.fetchall()
    
    for row in cac_mat_hang:
        ten_san_pham = row[0]
        so_luong_xuat = abs(float(row[1])) # Lấy trị tuyệt đối vì xuất kho lưu số âm
        gia_von_1_sp = dict_gia_von.get(ten_san_pham, 0)
        gia_von += (gia_von_1_sp * so_luong_xuat)
except Exception as e:
    pass

# 3. THANH TOÁN CÔNG NỢ NCC (Lấy từ bảng phiếu chi ls_phieu_chi)
try:
    c.execute("SELECT SUM(tong_chi) FROM public.ls_phieu_chi WHERE ngay_chi LIKE %s", (pattern_thang_vn,))
    res_ncc = c.fetchone()[0]
    thanh_toan_ncc = float(res_ncc) if res_ncc else 0.0
except Exception as e:
    pass

# 4. CHI PHÍ TỰ NHẬP (Từ bảng chi_phi_khac)
try:
    c.execute("SELECT SUM(so_tien) FROM public.chi_phi_khac WHERE ngay LIKE %s", (pattern_thang_iso,))
    res_cp = c.fetchone()[0]
    chi_phi_tu_nhap = float(res_cp) if res_cp else 0.0
except:
    pass

# ==========================================
# TÍNH TOÁN CÔNG THỨC KINH DOANH
# ==========================================
# 1. BÁO CÁO LỢI NHUẬN KINH DOANH (P&L)
loi_nhuan_gop = doanh_so - gia_von
loi_nhuan_thang = loi_nhuan_gop - chi_phi_tu_nhap

# 2. BÁO CÁO DÒNG TIỀN (CASHFLOW)
tong_chi_tien = thanh_toan_ncc + chi_phi_tu_nhap
dong_tien_thuan = thuc_thu - tong_chi_tien

# ==========================================
# HIỂN THỊ METRICS KẾT QUẢ KINH DOANH
# ==========================================
st.markdown("---")
st.markdown(f"### 📈 BÁO CÁO LỢI NHUẬN KINH DOANH - {thang_chon_display}")
st.caption("*(Đánh giá hiệu quả kinh doanh dựa trên Tổng lượng hàng đã xuất, không tính công nợ)*")

# THAY ĐỔI YÊU CẦU: Hiển thị 4 cột
col_dt1, col_dt2, col_dt3, col_dt4 = st.columns(4)
col_dt1.metric("Tổng Doanh Số (Đã XB & TT)", f"{doanh_so:,.0f} VNĐ")
col_dt2.metric("Tổng Giá Vốn", f"{gia_von:,.0f} VNĐ")
col_dt3.metric("Chi Phí Phát Sinh (Tự Nhập)", f"{chi_phi_tu_nhap:,.0f} VNĐ")
col_dt4.metric("Chi Phí Thanh Toán NVL, NCC", f"{thanh_toan_ncc:,.0f} VNĐ")

st.markdown("<br>", unsafe_allow_html=True)
color_ln = "#00cc00" if loi_nhuan_thang >= 0 else "#cc0000"
st.markdown(f"<h2 style='text-align: center; color: {color_ln};'>LỢI NHUẬN THÁNG: {loi_nhuan_thang:,.0f} VNĐ</h2>", unsafe_allow_html=True)

st.markdown("---")
st.markdown(f"### 💸 THEO DÕI DÒNG TIỀN THỰC TẾ (CASHFLOW)")
st.caption("*(Đánh giá lượng Tiền mặt thực tế thu về và chi ra trong tháng)*")

col_cf1, col_cf2, col_cf3 = st.columns(3)
col_cf1.metric("Tiền Mặt Thực Thu (Khách Hàng)", f"{thuc_thu:,.0f} VNĐ")
col_cf2.metric("Tổng Chi (NCC + Vận hành)", f"{tong_chi_tien:,.0f} VNĐ")

color_cf = "#00cc00" if dong_tien_thuan >= 0 else "#cc0000"
col_cf3.markdown(f"<h4 style='text-align: center; color: {color_cf}; margin-top: 15px;'>DÒNG TIỀN THUẦN:<br>{dong_tien_thuan:,.0f} VNĐ</h4>", unsafe_allow_html=True)

# ==========================================
# KHU VỰC NHẬP & THEO DÕI CHI PHÍ TỰ NHẬP
# ==========================================
st.markdown("---")
st.subheader("📝 Quản Lý Chi Phí Phát Sinh (Tự Nhập)")

col_form, col_table = st.columns([1, 2])

# Form nhập liệu
with col_form:
    st.markdown("**Thêm chi phí mới**")
    with st.form("form_nhap_chi_phi", clear_on_submit=True):
        cp_ngay = st.date_input("Ngày phát sinh", date.today(), format="DD/MM/YYYY")
        cp_diengiai = st.text_area("Diễn giải (VD: Tiền điện, nước, rác...)")
        cp_sotien = st.number_input("Số tiền (VNĐ)", min_value=0.0, step=10000.0)
        
        if st.form_submit_button("💾 Lưu Chi Phí", type="primary", use_container_width=True):
            if cp_sotien > 0 and cp_diengiai:
                try:
                    c.execute("INSERT INTO chi_phi_khac (ngay, dien_giai, so_tien) VALUES (%s, %s, %s)",
                              (cp_ngay.strftime("%Y-%m-%d"), cp_diengiai, cp_sotien))
                    conn.commit()
                    st.success("✅ Đã lưu chi phí thành công!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"Lỗi hệ thống: {e}")
            else:
                st.warning("⚠️ Vui lòng nhập diễn giải và số tiền phải lớn hơn 0.")

# Bảng thể hiện
with col_table:
    st.markdown(f"**Bảng chi phí đã nhập trong {thang_chon_display}**")
    try:
        df_cp = pd.read_sql("SELECT id, ngay, dien_giai, so_tien FROM chi_phi_khac WHERE ngay LIKE %s ORDER BY id DESC", conn, params=(pattern_thang_iso,))
        if not df_cp.empty:
            df_hien_thi = df_cp.copy()
            df_hien_thi.columns = ['ID', 'Ngày', 'Diễn Giải', 'Số Tiền (VNĐ)']
            st.dataframe(
                df_hien_thi.style.format({"Số Tiền (VNĐ)": "{:,.0f}"}),
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.info(f"Chưa có chi phí tự nhập nào được ghi nhận trong {thang_chon_display}.")
    except:
        st.info(f"Chưa có chi phí tự nhập nào được ghi nhận trong {thang_chon_display}.")
