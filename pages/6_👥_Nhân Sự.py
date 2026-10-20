import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta, timezone
from fpdf import FPDF
import os
import urllib.request
import time
import random
from db_utils import get_connection, check_password

# ==========================================
# 🔑 CẤU HÌNH MẬT KHẨU GIÁM ĐỐC (ĐỔI TẠI ĐÂY)
# ==========================================
MAT_KHAU_GIAM_DOC = "tbk1102" 

# ==========================================
# CẤU HÌNH MÚI GIỜ & FONT PDF
# ==========================================
VN_TZ = timezone(timedelta(hours=7))

def lay_gio_vn():
    return datetime.now(VN_TZ)

FONT_FILE = "Roboto-Regular.ttf"
FONT_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"

@st.cache_resource
def download_font():
    if not os.path.exists(FONT_FILE):
        try: urllib.request.urlretrieve(FONT_URL, FONT_FILE)
        except: return False
    return True
download_font()

# ==========================================
# KHỞI TẠO THƯ VIỆN CHUYỂN PDF SANG ẢNH
# ==========================================
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

def convert_pdf_to_png(pdf_bytes):
    """Hàm phụ trợ chuyển byte PDF thành byte Ảnh PNG độ nét cao"""
    if not HAS_FITZ:
        st.error("⚠️ Hệ thống thiếu thư viện 'PyMuPDF' để xuất ảnh. Vui lòng chạy lệnh: pip install PyMuPDF")
        return None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(0) 
        pix = page.get_pixmap(dpi=200) 
        return pix.tobytes("png")
    except Exception as e:
        st.error(f"Lỗi khi chuyển đổi ảnh: {e}")
        return None

# --- HÀM TẠO PHIẾU LƯƠNG PDF ---
def generate_payslip_pdf(nv_name, ky_luong, data):
    pdf = FPDF()
    pdf.add_page()
    
    has_font = os.path.exists(FONT_FILE)
    if has_font:
        pdf.add_font("Roboto", "", FONT_FILE, uni=True)
        pdf.add_font("Roboto", "B", FONT_FILE, uni=True) 
        font_name = "Roboto"
    else: font_name = "Helvetica"

    def f_vn(val): return f"{val:,.0f}".replace(",", ".")
    def f_num(val): return str(int(val)) if val == int(val) else str(val).replace(".", ",")
        
    pdf.set_font(font_name, 'B' if has_font else '', 14)
    pdf.cell(100, 8, "PHIẾU LƯƠNG NHÂN VIÊN", ln=0, align='L')
    pdf.set_font(font_name, '', 12)
    pdf.cell(40, 8, "Tháng:", ln=0, align='R')
    pdf.set_font(font_name, 'B' if has_font else '', 12)
    pdf.cell(50, 8, ky_luong.split('/')[0] + "." + ky_luong.split('/')[1][-2:] if '/' in ky_luong else ky_luong, ln=1, align='C')
    
    pdf.set_font(font_name, '', 12)
    pdf.cell(35, 8, "Nhân viên:", ln=0, align='R')
    pdf.set_font(font_name, 'B' if has_font else '', 12)
    pdf.cell(65, 8, nv_name.upper(), ln=0, align='L')
    pdf.set_font(font_name, '', 12)
    pdf.cell(40, 8, "Bộ phận:", ln=0, align='R')
    pdf.cell(50, 8, data['bo_phan'], ln=1, align='C')
    
    pdf.ln(2)
    y = pdf.get_y()
    pdf.set_draw_color(50, 50, 50)
    pdf.line(10, y, 200, y)
    pdf.line(10, y+0.8, 200, y+0.8)
    pdf.ln(4)
    
    pdf.set_draw_color(180, 180, 180) 
    
    def pdf_row(label, col2="", col3="", col4="", col5="", col6="", bold_label=False, bold_total=False):
        pdf.set_font(font_name, 'B' if bold_label and has_font else '', 11)
        pdf.cell(65, 8, label, border='B', align='L')
        pdf.set_font(font_name, '', 11)
        pdf.cell(30, 8, col2, border='B', align='R')
        pdf.cell(15, 8, col3, border='B', align='C')
        pdf.set_font(font_name, 'B' if has_font else '', 11)
        pdf.cell(20, 8, col4, border='B', align='C')
        pdf.set_font(font_name, '', 11)
        pdf.cell(10, 8, col5, border='B', align='C')
        pdf.set_font(font_name, 'B' if bold_total and has_font else '', 11)
        pdf.cell(50, 8, col6, border='B', align='R', ln=1)

    l_cb, l_nl, t_nien, t_com = data['l_cb'], data['l_nl'], data['t_nien'], data['t_com']

    pdf_row("Lương cơ bản:", f_vn(l_cb), "ngày")
    if l_nl > 0: pdf_row("  + Năng lực:", f_vn(l_nl), "ngày")
    pdf_row("  + Thâm niên:", f_vn(t_nien), "ngày")
    
    l_chinh_thuc = l_cb + l_nl + t_nien
    pdf_row("Lương chính thức:", f_vn(l_chinh_thuc), "ngày")
    pdf_row("  + Tiền cơm:", f_vn(t_com), "ngày")
    
    l_thuc_lanh_ngay = l_chinh_thuc + t_com
    tong_luong_ngay = l_thuc_lanh_ngay * data['ngay_cong']
    pdf_row("Lương thực lãnh:", f_vn(l_thuc_lanh_ngay), "x", f"{f_num(data['ngay_cong'])} ngày", "=", f"{f_vn(tong_luong_ngay)} đ", bold_label=True)
    
    pdf_row("Tiền tăng ca ngày thường:", f_vn(data['tc_thuong_gia']), "x", f"{f_num(data['tc_thuong_gio'])} tiếng", "=", f"{f_vn(data['tien_tc_t'])} đ")
    pdf_row("Tiền tăng ca chủ nhật:", f_vn(data['tc_cn_gia']), "x", f"{f_num(data['tc_cn_gio'])} tiếng", "=", f"{f_vn(data['tien_tc_c'])} đ")
    
    pdf_row("Phụ cấp khác:", "", "", "", "", f"{f_vn(data['p_cap'])} đ")
    pdf_row("Thưởng:", "", "", "", "", f"{f_vn(data['thuong'])} đ")
    
    pdf_row("Tổng lương:", "", "", "", "", f"{f_vn(data['gross'])} đ", bold_label=True, bold_total=True)
    pdf_row("Tạm ứng:", "", "", "", "", f"{f_vn(data['tam_ung'])} đ")
    
    pdf_row("Thực lãnh:", "", "", "", "", f"{f_vn(data['thuc_lanh'])} đ", bold_label=True, bold_total=True)
    
    pdf.ln(3)
    pdf.set_font(font_name, '', 11)
    pdf.cell(22, 6, "Nhận xét:", ln=0)
    pdf.multi_cell(0, 6, data['ghi_chu'])
    
    try: return bytes(pdf.output())
    except: return pdf.output(dest='S').encode('latin-1')

# ==========================================

st.set_page_config(page_title="Hệ Thống Nhân Sự WANCHI", page_icon="👥", layout="wide")
role = check_password()
if not role: st.stop()

if 'dashboard_unlocked' not in st.session_state:
    st.session_state.dashboard_unlocked = False

def yeu_cau_pin_giam_doc(tab_key):
    st.markdown("<br>", unsafe_allow_html=True)
    col_khoa1, col_khoa2, col_khoa3 = st.columns([1, 2, 1])
    with col_khoa2:
        st.warning("🔒 **BẢO MẬT CẤP CAO:** Vui lòng nhập Mã PIN Giám Đốc để mở khóa.")
        with st.form(f"form_mat_khau_{tab_key}"):
            pin_input = st.text_input("Mã PIN / Mật khẩu:", type="password")
            if st.form_submit_button("🔓 Mở Khóa Két Sắt", type="primary", use_container_width=True):
                if pin_input == MAT_KHAU_GIAM_DOC:
                    st.session_state.dashboard_unlocked = True
                    st.rerun()
                else: st.error("❌ Mã PIN không chính xác!")

def nut_khoa_lai(tab_key):
    if st.button("🔒 Khóa Lại Két Sắt", key=f"lock_{tab_key}"):
        st.session_state.dashboard_unlocked = False
        st.rerun()

conn = get_connection()
c = conn.cursor()

try:
    c.execute('''CREATE TABLE IF NOT EXISTS public.cau_hinh (
                    id SERIAL PRIMARY KEY, ten_cau_hinh TEXT UNIQUE, gia_tri TEXT
                )''')
    conn.commit()
except: pass

# Tự động cập nhật Database thêm cột trạng thái có phép
try:
    c.execute("ALTER TABLE public.cham_cong ADD COLUMN ve_som_co_phep BOOLEAN DEFAULT FALSE")
    conn.commit()
except Exception:
    conn.rollback()

def lay_thong_tin_ma_ca():
    try:
        c.execute("SELECT gia_tri FROM public.cau_hinh WHERE ten_cau_hinh='MA_CA_HIEN_TAI'")
        r1 = c.fetchone()
        c.execute("SELECT gia_tri FROM public.cau_hinh WHERE ten_cau_hinh='THOI_GIAN_TAO_MA'")
