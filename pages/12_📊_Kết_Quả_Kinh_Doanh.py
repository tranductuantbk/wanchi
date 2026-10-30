import streamlit as st
import pandas as pd
from datetime import date
import time
import json
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
list_months_value = []

# Tạo danh sách 12 tháng (Tháng hiện tại và 11 tháng trước đó)
for i in range(12):
    m = today.month - i
    y = today.year
    while m <= 0:
        m += 12
        y -= 1
    list_months_display.append(f"{m:02d}/{y}")
    list_months_value.append(f"{y}-{m:02d}") # Chuẩn ISO YYYY-MM

st.markdown("### 🗓️ Chọn Kỳ Báo Cáo")
thang_chon_display = st.selectbox("Lọc dữ liệu theo tháng/năm:", list_months_display, index=0)

# Lấy giá trị YYYY-MM tương ứng để truy vấn DB chuẩn hơn
idx = list_months_display.index(thang_chon_display)
thang_chon_val = list_months_value[idx] 
m_str, y_str = thang_chon_display.split('/')

# MỞ RỘNG BỘ QUÉT: Bắt mọi định dạng ngày tháng có thể bị nhập sai lệch từ trước
p1 = f"%{y_str}-{m_str}-%"
p2 = f"%/{m_str}/{y_str}%"
p3 = f"%{y_str}/{m_str}/%"
p4 = f"%-{m_str}-{y_str}%"

# ==========================================
# TRÍCH XUẤT DỮ LIỆU TỪ HỆ THỐNG
# ==========================================
doanh_thu = 0.0
gia_von = 0.0
thanh_toan_ncc = 0.0
chi_phi_tu_nhap = 0.0

# 1. DOANH THU THÁNG (Tính bằng đơn đã xuất kho)
try:
    c.execute("SELECT SUM(tong_tien) FROM don_hang WHERE trang_thai = 'Đã xuất kho' AND (ngay LIKE %s OR ngay LIKE %s OR ngay LIKE %s OR ngay LIKE %s)", (p1, p2, p3, p4))
    dt = c.fetchone()[0]
    doanh_thu = float(dt) if dt else 0.0
except:
    pass

# 2. GIÁ VỐN HÀNG BÁN (Lấy tổng của giá vốn trong mục danh sách sản phẩm)
try:
    # Lấy danh sách từ điển Giá Vốn từ bảng dm_san_pham
    df_sp = pd.read_sql("SELECT ten_sp, gia_von FROM dm_san_pham", conn)
    dict_gia_von = dict(zip(df_sp['ten_sp'], df_sp['gia_von']))
    
    # Lấy thêm từ điển Giá Vốn từ bảng dm_san_pham_ome
    try:
        df_ome = pd.read_sql("SELECT ten_sp, gia_von FROM dm_san_pham_ome", conn)
        dict_gia_von.update(dict(zip(df_ome['ten_sp'], df_ome['gia_von'])))
    except:
        pass
    
    # Quét tất cả các đơn hàng đã xuất kho trong tháng để nhân số lượng với Giá Vốn
    c.execute("SELECT chi_tiet FROM don_hang WHERE trang_thai = 'Đã xuất kho' AND (ngay LIKE %s OR ngay LIKE %s OR ngay LIKE %s OR ngay LIKE %s)", (p1, p2, p3, p4))
    cac_don_hang = c.fetchall()
    
    for row in cac_don_hang:
        chi_tiet_str = row[0]
        if chi_tiet_str:
            items = json.loads(chi_tiet_str)
            for sp in items:
                ten_san_pham = sp.get('Tên Sản Phẩm', sp.get('Tên Sản Phẩm OME', ''))
                so_luong = float(sp.get('Số Lượng', 0))
                # Lấy giá vốn, nếu không có trong danh mục thì tính là 0
                gia_von_1_sp = dict_gia_von.get(ten_san_pham, 0)
                gia_von += gia_von_1_sp * so_luong
except Exception as e:
    pass

# 3. THANH TOÁN CÔNG NỢ NCC (Đã thanh toán NVL, NCC)
try:
    df_nhap = pd.read_sql("SELECT * FROM don_nhap_hang WHERE ngay LIKE %s OR ngay LIKE %s OR ngay LIKE %s OR ngay LIKE %s", conn, params=(p1, p2, p3, p4))
    if not df_nhap.empty and 'tong_tien' in df_nhap.columns:
        if 'trang_thai' in df_nhap.columns:
            thanh_toan_ncc = float(df_nhap[df_nhap['trang_thai'] == 'Đã thanh toán']['tong_tien'].sum())
        elif 'da_thanh_toan' in df_nhap.columns: 
            thanh_toan_ncc = float(df_nhap['da_thanh_toan'].sum())
except:
    pass

# 4. CHI PHÍ TỰ NHẬP (Từ bảng chi_phi_khac)
try:
    df_cp = pd.read_sql("SELECT id, ngay, dien_giai, so_tien FROM chi_phi_khac WHERE ngay LIKE %s OR ngay LIKE %s OR ngay LIKE %s OR ngay LIKE %s ORDER BY id DESC", conn, params=(p1, p2, p3, p4))
    chi_phi_tu_nhap = float(df_cp['so_tien'].sum()) if not df_cp.empty else 0.0
except:
    df_cp = pd.DataFrame()
    chi_phi_tu_nhap = 0.0

# ==========================================
# TÍNH TOÁN CÔNG THỨC KINH DOANH MỚI
# ==========================================
# Lợi nhuận ròng = Đơn đã xuất kho (Doanh thu) - Giá vốn trong đơn đã xuất kho
loi_nhuan_rong = doanh_thu - gia_von

# Lợi nhuận tháng = Lợi nhuận ròng - Tiền đã thanh toán NVL/NCC - Chi phí tự nhập
loi_nhuan_thang = loi_nhuan_rong - thanh_toan_ncc - chi_phi_tu_nhap

# ==========================================
# HIỂN THỊ METRICS KẾT QUẢ KINH DOANH
# ==========================================
st.markdown("---")
st.markdown(f"### 📈 TỔNG QUAN KẾT QUẢ KINH DOANH - {thang_chon_display}")

col_dt1, col_dt2, col_dt3 = st.columns(3)
col_dt1.metric("Doanh Thu Tháng (Đã xuất kho)", f"{doanh_thu:,.0f} VNĐ")
col_dt2.metric("Giá Vốn Hàng Bán (Đã xuất kho)", f"{gia_von:,.0f} VNĐ")
col_dt3.metric("LỢI NHUẬN RÒNG", f"{loi_nhuan_rong:,.0f} VNĐ")

st.markdown("<br>", unsafe_allow_html=True)
col_cp1, col_cp2 = st.columns(2)
col_cp1.metric("Đã Thanh Toán NCC/NVL", f"{thanh_toan_ncc:,.0f} VNĐ")
col_cp2.metric("Chi Phí Tự Nhập", f"{chi_phi_tu_nhap:,.0f} VNĐ")

st.markdown("---")
# Hiển thị màu xanh nếu có lãi, màu đỏ nếu lỗ
color = "#00cc00" if loi_nhuan_thang >= 0 else "#cc0000"
st.markdown(f"<h1 style='text-align: center; color: {color};'>LỢI NHUẬN THÁNG: {loi_nhuan_thang:,.0f} VNĐ</h1>", unsafe_allow_html=True)

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
                    # Lưu ngày chuẩn ISO để dễ truy vấn sau này
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
    if not df_cp.empty:
        df_hien_thi = df_cp.copy()
        # Đổi tên cột cho đẹp
        df_hien_thi.columns = ['ID', 'Ngày', 'Diễn Giải', 'Số Tiền (VNĐ)']
        
        # Định dạng tiền tệ
        st.dataframe(
            df_hien_thi.style.format({"Số Tiền (VNĐ)": "{:,.0f}"}),
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info(f"Chưa có chi phí tự nhập nào được ghi nhận trong {thang_chon_display}.")
