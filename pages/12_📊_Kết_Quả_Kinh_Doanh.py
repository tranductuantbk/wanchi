import streamlit as st
import pandas as pd
from datetime import date
import time
import json
from db_utils import get_connection, check_password

st.set_page_config(page_title="Kết Quả Kinh Doanh", page_icon="📊", layout="wide")

# ==========================================
# Ổ KHÓA BẢO VỆ 2 LỚP
# ==========================================
role = check_password()
if not role: st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang Báo Cáo Kinh Doanh là dữ liệu mật, chỉ dành cho Quản lý.")
    st.stop()

st.header("📊 Báo Cáo Kết Quả Kinh Doanh")
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
# GIAO DIỆN CHỌN THÁNG
# ==========================================
# Tạo danh sách các tháng gần đây (từ năm ngoái đến năm sau)
current_year = date.today().year
current_month = date.today().month
list_months = []
for y in range(current_year - 1, current_year + 2):
    for m in range(1, 13):
        list_months.append(f"{y}-{m:02d}")
list_months.sort(reverse=True)
default_idx = list_months.index(f"{current_year}-{current_month:02d}")

st.markdown("### 🗓️ Chọn Kỳ Báo Cáo")
thang_chon = st.selectbox("Lọc dữ liệu theo tháng:", list_months, index=default_idx)

# ==========================================
# TRÍCH XUẤT DỮ LIỆU TỪ HỆ THỐNG
# ==========================================
doanh_thu = 0.0
gia_von = 0.0
thanh_toan_ncc = 0.0
chi_phi_tu_nhap = 0.0

# 1. DOANH THU THÁNG (Từ bảng hoa_don / don_hang xuất cho Đại lý/Khách hàng)
try:
    c.execute("SELECT SUM(tong_tien) FROM don_hang WHERE trang_thai = 'Đã xuất kho' AND ngay LIKE %s", (f"{thang_chon}-%",))
    dt = c.fetchone()[0]
    doanh_thu = float(dt) if dt else 0.0
except:
    pass

# Nếu muốn lấy từ hóa đơn đại lý (bảng hoa_don), bỏ block trên và dùng block dưới:
# try:
#     c.execute("SELECT SUM(tong_tien) FROM hoa_don WHERE ngay LIKE %s", (f"{thang_chon}-%",))
#     dt = c.fetchone()[0]
#     doanh_thu = float(dt) if dt else 0.0
# except:
#     pass

# 2. GIÁ VỐN HÀNG BÁN (Tính từ giá công ty trong danh mục sản phẩm)
try:
    # Lấy danh sách từ điển Giá gốc (Giá Công ty)
    df_sp = pd.read_sql("SELECT ten_sp, gia_khach_le FROM dm_san_pham", conn)
    dict_gia_von = dict(zip(df_sp['ten_sp'], df_sp['gia_khach_le']))
    
    # Quét tất cả các đơn hàng đã xuất kho trong tháng để nhân số lượng với giá gốc
    c.execute("SELECT chi_tiet FROM don_hang WHERE trang_thai = 'Đã xuất kho' AND ngay LIKE %s", (f"{thang_chon}-%",))
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
    st.error(f"Lỗi tính giá vốn: {e}")

# 3. THANH TOÁN CÔNG NỢ NCC (Từ bảng don_nhap_hang của kho)
try:
    df_nhap = pd.read_sql(f"SELECT * FROM don_nhap_hang WHERE ngay LIKE '{thang_chon}-%'", conn)
    if not df_nhap.empty and 'tong_tien' in df_nhap.columns:
        # Lọc ra các đơn đã thanh toán công nợ
        if 'trang_thai' in df_nhap.columns:
            thanh_toan_ncc = float(df_nhap[df_nhap['trang_thai'] == 'Đã thanh toán']['tong_tien'].sum())
        elif 'da_thanh_toan' in df_nhap.columns: 
            thanh_toan_ncc = float(df_nhap['da_thanh_toan'].sum())
except:
    pass

# 4. CHI PHÍ TỰ NHẬP (Từ bảng chi_phi_khac)
try:
    df_cp = pd.read_sql(f"SELECT id, ngay, dien_giai, so_tien FROM chi_phi_khac WHERE ngay LIKE '{thang_chon}-%' ORDER BY id DESC", conn)
    chi_phi_tu_nhap = float(df_cp['so_tien'].sum()) if not df_cp.empty else 0.0
except:
    df_cp = pd.DataFrame()
    chi_phi_tu_nhap = 0.0

# ==========================================
# TÍNH TOÁN CÔNG THỨC KINH DOANH
# ==========================================
loi_nhuan_rong = doanh_thu - gia_von
tong_chi_phi = thanh_toan_ncc + chi_phi_tu_nhap
loi_nhuan_thang = loi_nhuan_rong - tong_chi_phi

# ==========================================
# HIỂN THỊ METRICS KẾT QUẢ KINH DOANH
# ==========================================
st.markdown("---")
st.markdown(f"### 📈 TỔNG QUAN KẾT QUẢ KINH DOANH - {thang_chon}")

col_dt1, col_dt2, col_dt3 = st.columns(3)
col_dt1.metric("Doanh Thu Tháng (Đã xuất kho)", f"{doanh_thu:,.0f} VNĐ")
col_dt2.metric("Giá Vốn Hàng Bán (Giá gốc SP)", f"{gia_von:,.0f} VNĐ")
col_dt3.metric("LỢI NHUẬN RÒNG", f"{loi_nhuan_rong:,.0f} VNĐ")

st.markdown("<br>", unsafe_allow_html=True)
col_cp1, col_cp2, col_cp3 = st.columns(3)
col_cp1.metric("Đã Thanh Toán NCC/NVL", f"{thanh_toan_ncc:,.0f} VNĐ")
col_cp2.metric("Chi Phí Tự Nhập", f"{chi_phi_tu_nhap:,.0f} VNĐ")
col_cp3.metric("TỔNG CHI PHÍ", f"{tong_chi_phi:,.0f} VNĐ")

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
        cp_ngay = st.date_input("Ngày phát sinh", date.today())
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
    st.markdown(f"**Bảng chi phí đã nhập trong tháng {thang_chon}**")
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
        st.info(f"Chưa có chi phí tự nhập nào được ghi nhận trong tháng {thang_chon}.")
