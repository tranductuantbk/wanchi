import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import os
import urllib.request
import time
from db_utils import get_connection

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG & FONT TỰ ĐỘNG
# ==========================================
FONT_FILE = "Roboto-Regular.ttf"
FONT_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"
LOGO_FILE = "logo.png"

@st.cache_resource
def download_font():
    if not os.path.exists(FONT_FILE):
        try:
            urllib.request.urlretrieve(FONT_URL, FONT_FILE)
            return True
        except:
            return False
    return True

download_font()

st.set_page_config(page_title="WANCHI Báo Giá", page_icon="🏭", layout="wide")
st.title("🏭 Hệ Thống Báo Giá Khách Hàng WANCHI")

# Kết nối database an toàn qua db_utils
conn = get_connection()
c = conn.cursor()

# Khởi tạo giỏ hàng tạm thời
if 'gio_bao_gia' not in st.session_state:
    st.session_state.gio_bao_gia = []
if 'gio_bao_gia_custom' not in st.session_state:
    st.session_state.gio_bao_gia_custom = []

# ==========================================
# KHỞI TẠO BẢNG DATABASE (POSTGRESQL)
# ==========================================
c.execute('''CREATE TABLE IF NOT EXISTS lich_su_bao_gia (
                id SERIAL PRIMARY KEY,
                ngay_tao TEXT,
                ten_kh TEXT,
                so_dien_thoai TEXT,
                tong_tien REAL,
                loai_bao_gia TEXT DEFAULT 'Tiêu chuẩn'
            )''')

# Lấy danh mục sản phẩm để chọn
try:
    df_sp = pd.read_sql("SELECT ma_sp, ten_sp, gia_dai_ly FROM dm_san_pham", conn)
except:
    df_sp = pd.DataFrame(columns=['ma_sp', 'ten_sp', 'gia_dai_ly'])

def format_vn(value):
    try:
        return "{:,.0f}".format(value).replace(",", ".")
    except:
        return str(value)

# ==========================================
# 2. HÀM XUẤT PDF AN TOÀN (CHỐNG LỖI LOGO)
# ==========================================
def generate_generic_pdf(dataframe, title, subtitle="", columns_to_print=None, logo_path=LOGO_FILE, col_widths=None):
    pdf = FPDF()
    pdf.add_page()
    
    # Kiểm tra Font
    has_font = os.path.exists(FONT_FILE)
    if has_font:
        pdf.add_font("Roboto", "", FONT_FILE, uni=True)
        pdf.set_font("Roboto", size=10)
    else:
        pdf.set_font("Helvetica", size=10)

    # Xử lý Logo an toàn
    start_y = 12
    try:
        if os.path.exists(logo_path):
            pdf.image(logo_path, x=15, y=start_y, w=40)
            start_x = 60
        else:
            start_x = 15
            pdf.set_y(start_y)
    except:
        # Nếu file logo lỗi định dạng, tự động bỏ qua để không sập app
        start_x = 15
        pdf.set_y(start_y)
    
    # Thông tin công ty
    pdf.set_xy(start_x, start_y + 2)
    pdf.set_font("Roboto" if has_font else "Helvetica", size=10)
    pdf.multi_cell(0, 5, "775 Võ Hữu Lợi (KCN Lê Minh Xuân 3), Xã Lê Minh Xuân, Huyện Bình Chánh, TP.HCM")
    pdf.set_xy(start_x, pdf.get_y() + 1)
    pdf.cell(0, 5, "Điện thoại: 0902580828 - 0937572577", ln=True)
    pdf.ln(12) 

    # Tiêu đề phiếu
    pdf.set_font("Roboto" if has_font else "Helvetica", size=16)
    pdf.cell(0, 10, title, ln=True, align='C')
    if subtitle:
        pdf.set_font("Roboto" if has_font else "Helvetica", size=11)
        pdf.cell(0, 8, subtitle, ln=True, align='C')
    pdf.ln(5)

    # Vẽ bảng dữ liệu
    if columns_to_print is None: columns_to_print = dataframe.columns.tolist()
    if col_widths is None: col_widths = [190 / len(columns_to_print)] * len(columns_to_print)
    
    pdf.set_font("Roboto" if has_font else "Helvetica", size=10)
    pdf.set_fill_color(230, 230, 230)
    for i, col in enumerate(columns_to_print):
        pdf.cell(col_widths[i], 10, col, border=1, align='C', fill=True)
    pdf.ln()

    pdf.set_font("Roboto" if has_font else "Helvetica", size=9)
    for _, row in dataframe.iterrows():
        for i, col in enumerate(columns_to_print):
            val = row[col]
            display_val = format_vn(val) if isinstance(val, (int, float)) else str(val)
            pdf.cell(col_widths[i], 9, display_val, border=1, align='C' if not isinstance(val, (int, float)) else 'R')
        pdf.ln()

    # Chân trang
    pdf.ln(10)
    pdf.set_font("Roboto" if has_font else "Helvetica", size=10)
    pdf.cell(0, 6, "* Phiếu báo giá có giá trị trong 10 ngày. Giá chưa bao gồm phí vận chuyển.", ln=True)
    pdf.ln(10)
    pdf.cell(95, 6, "KHÁCH HÀNG KÝ TÊN", align='C')
    pdf.cell(95, 6, "NGƯỜI LẬP PHIẾU", align='C', ln=True)

    return bytes(pdf.output())

# ==========================================
# 3. GIAO DIỆN CHÍNH
# ==========================================
tab1, tab2, tab3 = st.tabs(["🤝 Báo Giá Chuẩn", "🛠️ Báo Giá Tùy Chỉnh", "📂 Lịch Sử"])

# --- TAB 1: BÁO GIÁ THEO DANH MỤC ---
with tab1:
    st.subheader("Tạo báo giá từ danh mục có sẵn")
    c1, c2 = st.columns(2)
    ten_kh = c1.text_input("Tên khách hàng:", key="t1_kh")
    sdt_kh = c2.text_input("Số điện thoại:", key="t1_sdt")

    with st.form("add_sp_t1"):
        col_s1, col_s2 = st.columns([3, 1])
        sp_list = df_sp['ten_sp'].tolist() if not df_sp.empty else []
        sp_chon = col_s1.selectbox("Chọn sản phẩm", ["-- Chọn --"] + sp_list)
        sl_chon = col_s2.number_input("Số lượng", min_value=1, step=1)
        if st.form_submit_button("Thêm vào danh sách"):
            if sp_chon != "-- Chọn --":
                info = df_sp[df_sp['ten_sp'] == sp_chon].iloc[0]
                st.session_state.gio_bao_gia.append({
                    "Mã SP": info['ma_sp'], "Tên SP": sp_chon, "Số Lượng": sl_chon, "Giá Gốc": info['gia_dai_ly']
                })
                st.rerun()

    if st.session_state.gio_bao_gia:
        df_curr = pd.DataFrame(st.session_state.gio_bao_gia)
        st.dataframe(df_curr, use_container_width=True)
        
        # Tính toán chiết khấu
        tong_goc = (df_curr['Giá Gốc'] / 0.6 * df_curr['Số Lượng']).sum()
        if tong_goc < 3000000: ck = 1.0
        elif tong_goc < 6000000: ck = 0.95
        elif tong_goc < 9000000: ck = 0.90
        else: ck = 0.85
        
        df_curr['Đơn Giá'] = (df_curr['Giá Gốc'] / 0.6 * ck).round(0)
        df_curr['Thành Tiền'] = df_curr['Đơn Giá'] * df_curr['Số Lượng']
        tong_cuoi = df_curr['Thành Tiền'].sum()
        
        st.write(f"### Tổng cộng: {format_vn(tong_cuoi)} VNĐ")
        
        if st.button("XUẤT BÁO GIÁ PDF", type="primary"):
            pdf_out = generate_generic_pdf(df_curr, "BÁO GIÁ SẢN PHẨM", f"Khách hàng: {ten_kh}", ["Mã SP", "Tên SP", "Số Lượng", "Đơn Giá", "Thành Tiền"], col_widths=[30, 70, 20, 35, 35])
            c.execute("INSERT INTO lich_su_bao_gia (ngay_tao, ten_kh, so_dien_thoai, tong_tien, loai_bao_gia) VALUES (%s, %s, %s, %s, 'Tiêu chuẩn')", (datetime.now().strftime("%d/%m/%Y %H:%M"), ten_kh, sdt_kh, tong_cuoi))
            st.download_button("📥 Tải Báo Giá", pdf_out, f"BaoGia_{ten_kh}.pdf")

# --- TAB 3: XEM LỊCH SỬ ---
with tab3:
    st.subheader("Lịch sử báo giá đã xuất")
    df_his = pd.read_sql("SELECT * FROM lich_su_bao_gia ORDER BY id DESC", conn)
    st.dataframe(df_his, use_container_width=True, hide_index=True)
