import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import json
from db_utils import get_connection, check_password

# ==========================================
# CẤU HÌNH MÚI GIỜ VIỆT NAM (UTC+7)
# ==========================================
VN_TZ = timezone(timedelta(hours=7))
def lay_gio_vn():
    return datetime.now(VN_TZ)

st.set_page_config(page_title="Tạo Đơn Hàng", page_icon="📝", layout="wide")

# ==========================================
# Ổ KHÓA BẢO VỆ 2 LỚP
# ==========================================
role = check_password()
if not role:
    st.stop() # Lớp 1: Bắt buộc nhập mật khẩu

if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang Tạo Đơn chỉ dành cho Quản lý / Kế toán WANCHI.")
    st.stop() # Lớp 2: Đuổi nhân viên ra ngoài
# ==========================================

st.header("📝 Hệ Thống Lên Đơn Hàng WANCHI")

conn = get_connection()
c = conn.cursor()

# ==========================================
# KHỞI TẠO BẢNG LƯU ĐƠN HÀNG
# ==========================================
c.execute('''CREATE TABLE IF NOT EXISTS don_hang (
                id SERIAL PRIMARY KEY,
                ngay_tao TEXT,
                ten_kh TEXT,
                loai_don TEXT,
                tong_tien REAL,
                chi_tiet TEXT,
                trang_thai TEXT DEFAULT 'Mới tạo'
            )''')
conn.commit()

# Lấy danh sách Khách Hàng, SP Chuẩn, SP OME từ Database
try: df_kh = pd.read_sql("SELECT ten_kh FROM dm_khach_hang", conn)
except: df_kh = pd.DataFrame(columns=['ten_kh'])

try: df_sp_chuan = pd.read_sql("SELECT ten_sp, gia_dai_ly, gia_khach_le FROM dm_san_pham", conn)
except: df_sp_chuan = pd.DataFrame(columns=['ten_sp', 'gia_dai_ly', 'gia_khach_le'])

try: df_sp_ome = pd.read_sql("SELECT ten_sp, gia_ome FROM dm_san_pham_ome", conn)
except: df_sp_ome = pd.DataFrame(columns=['ten_sp', 'gia_ome'])

# Khởi tạo 2 Giỏ hàng riêng biệt
if 'gio_chuan' not in st.session_state: st.session_state.gio_chuan = []
if 'gio_ome' not in st.session_state: st.session_state.gio_ome = []

def format_vn(value):
    try: return "{:,.0f}".format(value).replace(",", ".")
    except: return str(value)

# ==========================================
# GIAO DIỆN 2 TAB TẠO ĐƠN
# ==========================================
tab1, tab2 = st.tabs(["🛒 Lên Đơn Hàng Chuẩn", "🛠️ Lên Đơn Hàng OME"])

# ------------------------------------------
# TAB 1: ĐƠN HÀNG CHUẨN
# ------------------------------------------
with tab1:
    st.subheader("1. Chọn Khách Hàng & Thêm Sản Phẩm Chuẩn")
    
    khach_hang_chuan = st.selectbox("🙋‍♂️ Chọn Khách Hàng:", ["-- Chọn Khách Hàng --"] + df_kh['ten_kh'].tolist(), key="kh_chuan")
    
    with st.form("form_chuan", clear_on_submit=True):
        col_c1, col_c2, col_c3 = st.columns([2, 1, 1])
        sp_chon = col_c1.selectbox("📦 Chọn Sản Phẩm:", ["-- Chọn Sản Phẩm --"] + df_sp_chuan['ten_sp'].tolist())
        loai_gia = col_c2.selectbox("🏷️ Loại giá:", ["Giá Đại Lý", "Giá Khách Lẻ"])
        sl_chon = col_c3.number_input("🔢 Số lượng:", min_value=1, step=1)
        
        if st.form_submit_button("➕ Thêm vào đơn"):
            if sp_chon != "-- Chọn Sản Phẩm --":
                info = df_sp_chuan[df_sp_chuan['ten_sp'] == sp_chon].iloc[0]
                don_gia = info['gia_dai_ly'] if loai_gia == "Giá Đại Lý" else info['gia_khach_le']
                
                st.session_state.gio_chuan.append({
                    "Tên Sản Phẩm": sp_chon,
                    "Loại Giá": loai_gia,
                    "Số Lượng": sl_chon,
                    "Đơn Giá": don_gia,
                    "Thành Tiền": sl_chon * don_gia
                })
                st.rerun()
            else:
                st.warning("Vui lòng chọn sản phẩm!")

    # Hiển thị giỏ hàng chuẩn
    if st.session_state.gio_chuan:
        st.markdown("---")
        st.subheader("📋 Chi Tiết Đơn Hàng Chuẩn")
        df_gio_chuan = pd.DataFrame(st.session_state.gio_chuan)
        st.dataframe(df_gio_chuan, use_container_width=True, hide_index=True)
        
        tong_tien_chuan = df_gio_chuan['Thành Tiền'].sum()
        st.write(f"### 💰 TỔNG CỘNG: {format_vn(tong_tien_chuan)} VNĐ")
        
        col_btn_c1, col_btn_c2 = st.columns([1, 1])
        with col_btn_c1:
            if st.button("💾 CHỐT ĐƠN HÀNG CHUẨN", type="primary", use_container_width=True):
                if khach_hang_chuan == "-- Chọn Khách Hàng --":
                    st.error("⚠️ Vui lòng chọn Khách Hàng trước khi chốt đơn!")
                else:
                    try:
                        chi_tiet_json = df_gio_chuan.to_json(orient='records')
                        ngay_gio = lay_gio_vn().strftime("%d/%m/%Y %H:%M")
                        c.execute("INSERT INTO don_hang (ngay_tao, ten_kh, loai_don, tong_tien, chi_tiet) VALUES (%s, %s, %s, %s, %s)", 
                                  (ngay_gio, khach_hang_chuan, 'Hàng Chuẩn', tong_tien_chuan, chi_tiet_json))
                        st.success(f"✅ Đã tạo thành công Đơn Hàng Chuẩn cho {khach_hang_chuan}!")
                        st.session_state.gio_chuan = []
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Lỗi: {e}")
        with col_btn_c2:
            if st.button("🗑️ Xóa sạch đơn này", use_container_width=True, key="xoa_gio_chuan"):
                st.session_state.gio_chuan = []
                st.rerun()

# ------------------------------------------
# TAB 2: ĐƠN HÀNG OME
# ------------------------------------------
with tab2:
    st.subheader("1. Chọn Khách Hàng & Thêm Sản Phẩm OME")
    
    khach_hang_ome = st.selectbox("🙋‍♂️ Chọn Khách Hàng:", ["-- Chọn Khách Hàng --"] + df_kh['ten_kh'].tolist(), key="kh_ome")
    
    with st.form("form_ome", clear_on_submit=True):
        col_o1, col_o2 = st.columns([3, 1])
        sp_ome_chon = col_o1.selectbox("⚙️ Chọn Sản Phẩm OME:", ["-- Chọn Sản Phẩm --"] + df_sp_ome['ten_sp'].tolist())
        sl_ome_chon = col_o2.number_input("🔢 Số lượng:", min_value=1, step=1, key="sl_ome")
        
        if st.form_submit_button("➕ Thêm vào đơn OME"):
            if sp_ome_chon != "-- Chọn Sản Phẩm --":
                info_ome = df_sp_ome[df_sp_ome['ten_sp'] == sp_ome_chon].iloc[0]
                don_gia_ome = info_ome['gia_ome']
                
                st.session_state.gio_ome.append({
                    "Tên Sản Phẩm OME": sp_ome_chon,
                    "Số Lượng": sl_ome_chon,
                    "Đơn Giá OME": don_gia_ome,
                    "Thành Tiền": sl_ome_chon * don_gia_ome
                })
                st.rerun()
            else:
                st.warning("Vui lòng chọn sản phẩm OME!")

    # Hiển thị giỏ hàng OME
    if st.session_state.gio_ome:
        st.markdown("---")
        st.subheader("📋 Chi Tiết Đơn Hàng OME")
        df_gio_ome = pd.DataFrame(st.session_state.gio_ome)
        st.dataframe(df_gio_ome, use_container_width=True, hide_index=True)
        
        tong_tien_ome = df_gio_ome['Thành Tiền'].sum()
        st.write(f"### 💰 TỔNG CỘNG OME: {format_vn(tong_tien_ome)} VNĐ")
        
        col_btn_o1, col_btn_o2 = st.columns([1, 1])
        with col_btn_o1:
            if st.button("💾 CHỐT ĐƠN HÀNG OME", type="primary", use_container_width=True):
                if khach_hang_ome == "-- Chọn Khách Hàng --":
                    st.error("⚠️ Vui lòng chọn Khách Hàng trước khi chốt đơn!")
                else:
                    try:
                        chi_tiet_json_ome = df_gio_ome.to_json(orient='records')
                        ngay_gio_ome = lay_gio_vn().strftime("%d/%m/%Y %H:%M")
                        c.execute("INSERT INTO don_hang (ngay_tao, ten_kh, loai_don, tong_tien, chi_tiet) VALUES (%s, %s, %s, %s, %s)", 
                                  (ngay_gio_ome, khach_hang_ome, 'Hàng OME', tong_tien_ome, chi_tiet_json_ome))
                        st.success(f"✅ Đã tạo thành công Đơn Hàng OME cho {khach_hang_ome}!")
                        st.session_state.gio_ome = []
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Lỗi: {e}")
        with col_btn_o2:
            if st.button("🗑️ Xóa sạch đơn OME này", use_container_width=True, key="xoa_gio_ome"):
                st.session_state.gio_ome = []
                st.rerun()
