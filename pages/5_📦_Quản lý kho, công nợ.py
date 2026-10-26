import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import json
import os
import urllib.request
from fpdf import FPDF
from db_utils import get_connection, check_password

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
        except: pass
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

st.set_page_config(page_title="Quản Lý Kho WANCHI", page_icon="📦", layout="wide")

role = check_password()
if not role: st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang Quản Lý Kho chỉ dành cho Quản lý WANCHI.")
    st.stop()

st.header("📦 Quản Lý Kho, Công Nợ")

conn = get_connection()
c = conn.cursor()

# ==========================================
# KHỞI TẠO BẢNG DỮ LIỆU
# ==========================================
try:
    c.execute("CREATE SCHEMA IF NOT EXISTS public;")
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_nguyen_lieu (
                    id SERIAL PRIMARY KEY, ma_nl TEXT UNIQUE, ten_nl TEXT UNIQUE, don_vi TEXT, ton_kho REAL DEFAULT 0
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS public.ls_nhap_xuat_kho (
                    id SERIAL PRIMARY KEY, ngay_thao_tac TEXT, loai_thao_tac TEXT, ten_nl TEXT, 
                    so_luong REAL, don_gia REAL DEFAULT 0, thanh_tien REAL DEFAULT 0, ghi_chu TEXT
                )''')
    c.execute("ALTER TABLE public.dm_san_pham ADD COLUMN IF NOT EXISTS ton_kho REAL DEFAULT 0")
    c.execute("ALTER TABLE public.dm_san_pham_ome ADD COLUMN IF NOT EXISTS ton_kho REAL DEFAULT 0")
    
    # Đảm bảo có cột quy cách lốc để tránh lỗi khi Báo cáo tồn kho truy xuất
    c.execute("ALTER TABLE public.dm_san_pham ADD COLUMN IF NOT EXISTS quy_cach_loc REAL DEFAULT 1")
    c.execute("ALTER TABLE public.dm_san_pham_ome ADD COLUMN IF NOT EXISTS quy_cach_loc REAL DEFAULT 1")
    
    c.execute("ALTER TABLE public.don_hang ADD COLUMN IF NOT EXISTS trang_thai TEXT DEFAULT 'Chờ xuất kho'")
    
    # BẢNG VÀ CỘT MỚI CHO NHÀ CUNG CẤP & THANH TOÁN
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_ncc (
                    id SERIAL PRIMARY KEY, ten_ncc TEXT UNIQUE
                )''')
    c.execute("ALTER TABLE public.ls_nhap_xuat_kho ADD COLUMN IF NOT EXISTS nha_cung_cap TEXT")
    c.execute("ALTER TABLE public.ls_nhap_xuat_kho ADD COLUMN IF NOT EXISTS khach_hang TEXT")
    c.execute("ALTER TABLE public.ls_nhap_xuat_kho ADD COLUMN IF NOT EXISTS trang_thai_tt TEXT")
    c.execute("ALTER TABLE public.ls_nhap_xuat_kho ADD COLUMN IF NOT EXISTS tien_da_thu REAL DEFAULT 0")
    
    # BẢNG MỚI ĐỂ LƯU LỊCH SỬ PHIẾU CHI
    c.execute('''CREATE TABLE IF NOT EXISTS public.ls_phieu_chi (
                    id SERIAL PRIMARY KEY, ma_phieu TEXT, ngay_chi TEXT, ten_ncc TEXT, tong_chi REAL, chi_tiet TEXT
                )''')
    conn.commit()
except: 
    conn.rollback()

def format_vn(value):
    try: return "{:,.0f}".format(value).replace(",", ".")
    except: return str(value)

def don_dep_lich_su_chi():
    """Hàm tự động dọn dẹp, chỉ giữ lại 50 phiếu chi gần nhất"""
    try:
        c.execute("""DELETE FROM public.ls_phieu_chi 
                     WHERE id NOT IN (
                         SELECT id FROM public.ls_phieu_chi 
                         ORDER BY id DESC LIMIT 50
                     )""")
        conn.commit()
    except: 
        conn.rollback()

# ==========================================
# HÀM TẠO PHIẾU PDF
# ==========================================
def generate_phieu_xuat_pdf(df_items, ma_don, ten_kh):
    pdf = FPDF()
    pdf.add_page()
    
    has_font = os.path.exists(FONT_FILE)
    if has_font:
        pdf.add_font("Roboto", "", FONT_FILE, uni=True)
        font_name = "Roboto"
    else: font_name = "Helvetica"

    pdf.set_font(font_name, "", 16)
    pdf.cell(0, 10, "PHIẾU XUẤT KHO HÀNG HÓA", ln=True, align="C")
    pdf.set_font(font_name, "", 10)
    pdf.cell(0, 6, f"Mã đơn: {ma_don}", ln=True, align="C")
    pdf.cell(0, 6, f"Khách hàng: {ten_kh}", ln=True, align="C")
    pdf.cell(0, 6, f"Ngày xuất: {lay_gio_vn().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
    pdf.ln(10)

    pdf.set_fill_color(230, 230, 230)
    pdf.cell(10, 10, "STT", 1, 0, "C", True)
    pdf.cell(110, 10, "Tên Sản Phẩm", 1, 0, "C", True)
    pdf.cell(35, 10, "Số Lượng", 1, 0, "C", True)
    pdf.cell(35, 10, "Đơn Vị", 1, 1, "C", True)

    for i, row in df_items.iterrows():
        ten = str(row.get('Tên Sản Phẩm', row.get('Tên Sản Phẩm OME', 'N/A')))
        sl = row.get('Số Lượng', 0)
        pdf.cell(10, 8, str(i+1), 1, 0, "C")
        pdf.cell(110, 8, ten, 1, 0, "L")
        pdf.cell(35, 8, format_vn(sl), 1, 0, "C")
        pdf.cell(35, 8, "Cái/Bộ", 1, 1, "C")
    
    pdf.ln(10)
    pdf.cell(95, 6, "Người lập phiếu", 0, 0, "C")
    pdf.cell(95, 6, "Người nhận hàng", 0, 1, "C")
    
    try: return bytes(pdf.output())
    except:
        out = pdf.output(dest='S')
        return out.encode('latin-1') if isinstance(out, str) else bytes(out)

def generate_phieu_chi_pdf(ten_ncc, ma_phieu, tong_chi, ngay_chi, df_selected=None):
    pdf = FPDF()
    pdf.add_page()
    has_font = os.path.exists(FONT_FILE)
    if has_font:
        pdf.add_font("Roboto", "", FONT_FILE, uni=True)
        pdf.add_font("Roboto", "B", FONT_FILE, uni=True) 
        font_name = "Roboto"
    else: font_name = "Helvetica"

    start_y, start_x = 12, 65  
    try:
        if os.path.exists("logo.jpg"): pdf.image("logo.jpg", x=15, y=start_y, w=40)
        elif os.path.exists("logo.png"): pdf.image("logo.png", x=15, y=start_y, w=40)
        else:
            pdf.set_font(font_name, 'B', 18)
            pdf.set_xy(15, start_y + 3); pdf.cell(40, 10, "WANCHI", align="C")
    except:
        pdf.set_font(font_name, 'B', 18)
        pdf.set_xy(15, start_y + 3); pdf.cell(40, 10, "WANCHI", align="C")
    
    pdf.set_font(font_name, size=10)
    pdf.set_xy(start_x, start_y + 2)
    pdf.multi_cell(0, 5, "775 Võ Hữu Lợi, Xã Lê Minh Xuân, Huyện Bình Chánh, TP.HCM")
    pdf.set_xy(start_x, pdf.get_y() + 1)
    pdf.cell(0, 5, "SĐT: 0902.580.828 - 0937.572.577", ln=True)
    pdf.ln(12)

    pdf.set_font(font_name, 'B' if has_font else '', 16)
    pdf.cell(0, 10, "PHIẾU CHI TIỀN (THANH TOÁN CÔNG NỢ NCC)", ln=True, align="C")
    
    pdf.set_font(font_name, "", 11)
    pdf.cell(0, 6, f"Ngày lập: {ngay_chi}", ln=True, align="C")
    pdf.cell(0, 6, f"Mã Phiếu Thanh Toán: {ma_phieu}", ln=True, align="C")
    pdf.ln(5)
    
    pdf.cell(0, 8, f"Người nhận tiền (Nhà cung cấp): {ten_ncc}", ln=True)
    pdf.cell(0, 8, f"Lý do chi: Thanh toán công nợ tiền vật tư / nguyên liệu nhập kho.", ln=True)
    pdf.ln(3)
    
    if df_selected is not None and not df_selected.empty:
        pdf.set_font(font_name, 'B' if has_font else '', 10)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(15, 10, "STT", border=1, align="C", fill=True)
        pdf.cell(35, 10, "Ngày Nhập", border=1, align="C", fill=True)
        pdf.cell(90, 10, "Thông tin SP (Vật tư)", border=1, align="C", fill=True)
        pdf.cell(50, 10, "Thành Tiền", border=1, ln=True, align="C", fill=True)

        pdf.set_font(font_name, "", 10)
        stt = 1
        for _, row in df_selected.iterrows():
            ngay = str(row.get("Ngày Nhập", ""))
            ten_vt = str(row.get("Tên Vật Tư", ""))
            sl = row.get("Số Lượng", 0)
            sp_info = f"{ten_vt} (SL: {format_vn(sl)})"
            thanh_tien = row.get("Thành Tiền", 0)
            
            pdf.cell(15, 8, str(stt), border=1, align="C")
            pdf.cell(35, 8, ngay, border=1, align="C")
            pdf.cell(90, 8, sp_info, border=1, align="L")
            pdf.cell(50, 8, format_vn(thanh_tien), border=1, ln=True, align="R")
            stt += 1
            
        pdf.set_font(font_name, 'B' if has_font else '', 11)
        pdf.cell(140, 10, "TỔNG CỘNG:", border=1, align="R")
        pdf.cell(50, 10, format_vn(tong_chi) + " VNĐ", border=1, ln=True, align="R")
    else:
        pdf.set_font(font_name, 'B' if has_font else '', 12)
        pdf.cell(0, 10, f"Số tiền thanh toán: {format_vn(tong_chi)} VNĐ", ln=True)

    pdf.ln(10)
    
    pdf.set_font(font_name, "", 11)
    pdf.cell(95, 6, "Người Lập Phiếu", align='C')
    pdf.cell(95, 6, "Người Nhận Tiền", ln=True, align='C')
    pdf.cell(95, 6, "(Ký, ghi rõ họ tên)", align='C')
    pdf.cell(95, 6, "(Ký, ghi rõ họ tên)", align='C')
    
    try: return bytes(pdf.output())
    except:
        out = pdf.output(dest='S')
        return out.encode('latin-1') if isinstance(out, str) else bytes(out)

def generate_doi_soat_kh_pdf(ten_kh, tong_no, df_no):
    pdf = FPDF()
    pdf.add_page()
    has_font = os.path.exists(FONT_FILE)
    if has_font:
        pdf.add_font("Roboto", "", FONT_FILE, uni=True)
        pdf.add_font("Roboto", "B", FONT_FILE, uni=True) 
        font_name = "Roboto"
    else: font_name = "Helvetica"

    start_y, start_x = 12, 65  
    try:
        if os.path.exists("logo.jpg"): pdf.image("logo.jpg", x=15, y=start_y, w=40)
        elif os.path.exists("logo.png"): pdf.image("logo.png", x=15, y=start_y, w=40)
        else:
            pdf.set_font(font_name, 'B', 18)
            pdf.set_xy(15, start_y + 3); pdf.cell(40, 10, "WANCHI", align="C")
    except:
        pdf.set_font(font_name, 'B', 18)
        pdf.set_xy(15, start_y + 3); pdf.cell(40, 10, "WANCHI", align="C")
    
    pdf.set_font(font_name, size=10)
    pdf.set_xy(start_x, start_y + 2)
    pdf.multi_cell(0, 5, "775 Võ Hữu Lợi, Xã Lê Minh Xuân, Huyện Bình Chánh, TP.HCM")
    pdf.set_xy(start_x, pdf.get_y() + 1)
    pdf.cell(0, 5, "SĐT: 0902.580.828 - 0937.572.577", ln=True)
    pdf.ln(12)

    pdf.set_font(font_name, 'B' if has_font else '', 16)
    pdf.cell(0, 10, "BẢNG KÊ ĐỐI SOÁT CÔNG NỢ", ln=True, align="C")
    
    pdf.set_font(font_name, "", 11)
    pdf.cell(0, 6, f"Ngày xuất: {lay_gio_vn().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
    pdf.ln(5)
    
    pdf.cell(0, 8, f"Khách hàng / Đại lý: {ten_kh}", ln=True)
    pdf.ln(3)
    
    if not df_no.empty:
        pdf.set_font(font_name, 'B' if has_font else '', 9)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(10, 10, "STT", border=1, align="C", fill=True)
        pdf.cell(25, 10, "Ngày Xuất", border=1, align="C", fill=True)
        pdf.cell(65, 10, "Sản Phẩm (Ghi chú)", border=1, align="C", fill=True)
        pdf.cell(30, 10, "Tổng Tiền", border=1, align="C", fill=True)
        pdf.cell(30, 10, "Đã Thanh Toán", border=1, align="C", fill=True)
        pdf.cell(30, 10, "Còn Nợ", border=1, ln=True, align="C", fill=True)

        pdf.set_font(font_name, "", 9)
        stt = 1
        for _, row in df_no.iterrows():
            ngay = str(row.get("Ngày Xuất", ""))
            sp = str(row.get("Sản Phẩm", ""))
            gc = str(row.get("Ghi Chú", ""))
            sp_info = f"{sp} - {gc}" if gc else sp
            
            tt = row.get("Thành Tiền", 0)
            dt = row.get("Đã Thu Tiền (VNĐ)", 0)
            cn = row.get("Còn Nợ (VNĐ)", 0)
            
            pdf.cell(10, 8, str(stt), border=1, align="C")
            pdf.cell(25, 8, ngay.split()[0] if ngay else "", border=1, align="C")
            
            # Xử lý text dài
            current_x, current_y = pdf.get_x(), pdf.get_y()
            pdf.multi_cell(65, 8, sp_info, border=1, align="L")
            next_y = pdf.get_y()
            pdf.set_xy(current_x + 65, current_y)
            
            pdf.cell(30, next_y - current_y, format_vn(tt), border=1, align="R")
            pdf.cell(30, next_y - current_y, format_vn(dt), border=1, align="R")
            pdf.cell(30, next_y - current_y, format_vn(cn), border=1, ln=True, align="R")
            stt += 1
            
        pdf.set_font(font_name, 'B' if has_font else '', 11)
        pdf.cell(160, 10, "TỔNG NỢ HIỆN TẠI:", border=1, align="R")
        pdf.cell(30, 10, format_vn(tong_no) + " đ", border=1, ln=True, align="R")

    pdf.ln(10)
    pdf.set_font(font_name, "", 11)
    pdf.cell(95, 6, "Người Lập Phiếu", align='C')
    pdf.cell(95, 6, "Khách Hàng (Xác Nhận)", ln=True, align='C')
    
    try: return bytes(pdf.output())
    except:
        out = pdf.output(dest='S')
        return out.encode('latin-1') if isinstance(out, str) else bytes(out)

def generate_doi_soat_ncc_pdf(ten_ncc, tong_no, df_no):
    pdf = FPDF()
    pdf.add_page()
    has_font = os.path.exists(FONT_FILE)
    if has_font:
        pdf.add_font("Roboto", "", FONT_FILE, uni=True)
        pdf.add_font("Roboto", "B", FONT_FILE, uni=True) 
        font_name = "Roboto"
    else: font_name = "Helvetica"

    start_y, start_x = 12, 65  
    try:
        if os.path.exists("logo.jpg"): pdf.image("logo.jpg", x=15, y=start_y, w=40)
        elif os.path.exists("logo.png"): pdf.image("logo.png", x=15, y=start_y, w=40)
        else:
            pdf.set_font(font_name, 'B', 18)
            pdf.set_xy(15, start_y + 3); pdf.cell(40, 10, "WANCHI", align="C")
    except:
        pdf.set_font(font_name, 'B', 18)
        pdf.set_xy(15, start_y + 3); pdf.cell(40, 10, "WANCHI", align="C")
    
    pdf.set_font(font_name, size=10)
    pdf.set_xy(start_x, start_y + 2)
    pdf.multi_cell(0, 5, "775 Võ Hữu Lợi, Xã Lê Minh Xuân, Huyện Bình Chánh, TP.HCM")
    pdf.set_xy(start_x, pdf.get_y() + 1)
    pdf.cell(0, 5, "SĐT: 0902.580.828 - 0937.572.577", ln=True)
    pdf.ln(12)

    pdf.set_font(font_name, 'B' if has_font else '', 16)
    pdf.cell(0, 10, "BẢNG KÊ ĐỐI SOÁT CÔNG NỢ NHÀ CUNG CẤP", ln=True, align="C")
    
    pdf.set_font(font_name, "", 11)
    pdf.cell(0, 6, f"Ngày xuất: {lay_gio_vn().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
    pdf.ln(5)
    
    pdf.cell(0, 8, f"Nhà cung cấp: {ten_ncc}", ln=True)
    pdf.ln(3)
    
    if not df_no.empty:
        pdf.set_font(font_name, 'B' if has_font else '', 9)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(10, 10, "STT", border=1, align="C", fill=True)
        pdf.cell(30, 10, "Ngày Nhập", border=1, align="C", fill=True)
        pdf.cell(100, 10, "Vật Tư (Ghi chú)", border=1, align="C", fill=True)
        pdf.cell(50, 10, "Thành Tiền", border=1, ln=True, align="C", fill=True)

        pdf.set_font(font_name, "", 9)
        stt = 1
        for _, row in df_no.iterrows():
            ngay = str(row.get("Ngày Nhập", ""))
            vt = str(row.get("Tên Vật Tư", ""))
            sl = format_vn(row.get("Số Lượng", 0))
            gc = str(row.get("Ghi Chú", ""))
            
            vt_info = f"{vt} (SL: {sl})"
            if gc and gc != "None": vt_info += f" - {gc}"
            
            tt = row.get("Thành Tiền", 0)
            
            pdf.cell(10, 8, str(stt), border=1, align="C")
            pdf.cell(30, 8, ngay.split()[0] if ngay else "", border=1, align="C")
            
            current_x, current_y = pdf.get_x(), pdf.get_y()
            pdf.multi_cell(100, 8, vt_info, border=1, align="L")
            next_y = pdf.get_y()
            pdf.set_xy(current_x + 100, current_y)
            
            pdf.cell(50, next_y - current_y, format_vn(tt), border=1, ln=True, align="R")
            stt += 1
            
        pdf.set_font(font_name, 'B' if has_font else '', 11)
        pdf.cell(140, 10, "TỔNG NỢ HIỆN TẠI:", border=1, align="R")
        pdf.cell(50, 10, format_vn(tong_no) + " đ", border=1, ln=True, align="R")

    pdf.ln(10)
    pdf.set_font(font_name, "", 11)
    pdf.cell(95, 6, "Người Lập Phiếu", align='C')
    pdf.cell(95, 6, "Nhà Cung Cấp (Xác Nhận)", ln=True, align='C')
    
    try: return bytes(pdf.output())
    except:
        out = pdf.output(dest='S')
        return out.encode('latin-1') if isinstance(out, str) else bytes(out)

def generate_phieu_nhap_pdf(ma_phieu, ten_ncc, df_items, ghi_chu, ngay_nhap):
    pdf = FPDF()
    pdf.add_page()
    has_font = os.path.exists(FONT_FILE)
    if has_font:
        pdf.add_font("Roboto", "", FONT_FILE, uni=True)
        pdf.add_font("Roboto", "B", FONT_FILE, uni=True) 
        font_name = "Roboto"
    else: font_name = "Helvetica"

    start_y, start_x = 12, 65  
    try:
        if os.path.exists("logo.jpg"): pdf.image("logo.jpg", x=15, y=start_y, w=40)
        elif os.path.exists("logo.png"): pdf.image("logo.png", x=15, y=start_y, w=40)
        else:
            pdf.set_font(font_name, 'B', 18)
            pdf.set_xy(15, start_y + 3); pdf.cell(40, 10, "WANCHI", align="C")
    except:
        pdf.set_font(font_name, 'B', 18)
        pdf.set_xy(15, start_y + 3); pdf.cell(40, 10, "WANCHI", align="C")
    
    pdf.set_font(font_name, size=10)
    pdf.set_xy(start_x, start_y + 2)
    pdf.multi_cell(0, 5, "775 Võ Hữu Lợi, Xã Lê Minh Xuân, Huyện Bình Chánh, TP.HCM")
    pdf.set_xy(start_x, pdf.get_y() + 1)
    pdf.cell(0, 5, "SĐT: 0902.580.828 - 0937.572.577", ln=True)
    pdf.ln(12)

    pdf.set_font(font_name, 'B' if has_font else '', 16)
    pdf.cell(0, 10, "PHIẾU NHẬP KHO", ln=True, align="C")
    
    pdf.set_font(font_name, "", 11)
    pdf.cell(0, 6, f"Mã Phiếu: {ma_phieu}   |   Ngày nhập: {ngay_nhap}", ln=True, align="C")
    pdf.ln(5)
    
    pdf.cell(0, 8, f"Nhà cung cấp: {ten_ncc}", ln=True)
    pdf.ln(3)
    
    if not df_items.empty:
        pdf.set_font(font_name, 'B' if has_font else '', 10)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(15, 10, "STT", border=1, align="C", fill=True)
        pdf.cell(100, 10, "Tên Vật Tư", border=1, align="C", fill=True)
        pdf.cell(40, 10, "Số Lượng", border=1, align="C", fill=True)
        pdf.cell(35, 10, "Phân Loại", border=1, ln=True, align="C", fill=True)

        pdf.set_font(font_name, "", 10)
        stt = 1
        for _, row in df_items.iterrows():
            vt = str(row.get("Vật Tư", ""))
            sl = row.get("Số Lượng", 0)
            pl = str(row.get("Phân Loại", ""))
            
            pdf.cell(15, 8, str(stt), border=1, align="C")
            pdf.cell(100, 8, vt, border=1, align="L")
            pdf.cell(40, 8, format_vn(sl), border=1, align="C")
            pdf.cell(35, 8, pl, border=1, ln=True, align="C")
            stt += 1

    pdf.ln(5)
    
    # BẢNG GHI CHÚ
    if ghi_chu and ghi_chu.strip() != "":
        pdf.set_font(font_name, 'B' if has_font else '', 10)
        pdf.set_fill_color(245, 245, 245)
        pdf.cell(190, 8, "GHI CHÚ KÈM THEO", border=1, ln=True, align="L", fill=True)
        pdf.set_font(font_name, "", 10)
        pdf.multi_cell(190, 8, ghi_chu, border=1, align="L")
        pdf.ln(5)

    pdf.ln(5)
    pdf.set_font(font_name, "", 11)
    pdf.cell(95, 6, "Người Lập Phiếu", align='C')
    pdf.cell(95, 6, "Đại Diện Giao Hàng", ln=True, align='C')
    
    try: return bytes(pdf.output())
    except:
        out = pdf.output(dest='S')
        return out.encode('latin-1') if isinstance(out, str) else bytes(out)

# ==========================================
# GIAO DIỆN CHÍNH
# ==========================================
tab2, tab1, tab_kh, tab3, tab4 = st.tabs(["📥 Nhập / Xuất Kho", "📋 NVL, NCC, Công Nợ", "👤 Khách Hàng Công Nợ", "📊 Báo Cáo Tồn Kho", "🕰️ Lịch Sử Công Nợ"])

with tab1:
    st.subheader("🏢 Quản Lý Nhà Cung Cấp & Theo Dõi Công Nợ")
    with st.form("form_them_ncc", clear_on_submit=True):
        c_ncc1, c_ncc2 = st.columns([3, 1])
        with c_ncc1: 
            ten_ncc = st.text_input("Tên Nhà Cung Cấp Mới (*)")
        with c_ncc2:
            st.write("") 
            btn_ncc = st.form_submit_button("💾 Lưu NCC", type="primary", use_container_width=True)
        if btn_ncc:
            if ten_ncc.strip():
                try:
                    c.execute("INSERT INTO public.dm_ncc (ten_ncc) VALUES (%s)", (ten_ncc.strip(),))
                    conn.commit()
                    st.success("✅ Đã thêm Nhà Cung Cấp thành công!")
                    time.sleep(1); st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error("⚠️ Lỗi: Tên Nhà Cung Cấp này đã tồn tại!")
            else:
                st.warning("Vui lòng nhập tên Nhà Cung Cấp!")

    st.markdown("**🔍 Theo dõi Hóa đơn & Công Nợ NCC**")
    try:
        df_ncc = pd.read_sql("SELECT ten_ncc FROM public.dm_ncc ORDER BY id DESC", conn)
        danh_sach_ncc = df_ncc['ten_ncc'].tolist() if not df_ncc.empty else []
        
        col_cn1, col_cn2 = st.columns([1, 2])
        with col_cn1:
            ncc_chon_cong_no = st.selectbox("Lọc công nợ theo Nhà Cung Cấp:", ["-- Chọn NCC --"] + danh_sach_ncc)
        
        if ncc_chon_cong_no != "-- Chọn NCC --":
            df_no = pd.read_sql(f"SELECT id, ngay_thao_tac, ten_nl, so_luong, don_gia, thanh_tien, ghi_chu FROM public.ls_nhap_xuat_kho WHERE nha_cung_cap='{ncc_chon_cong_no}' AND trang_thai_tt='Chưa thanh toán' AND loai_thao_tac='Nhập NVL'", conn)
            
            if not df_no.empty:
                tong_no = df_no['thanh_tien'].sum()
                st.warning(f"🚨 **CẢNH BÁO:** Bạn đang nợ {ncc_chon_cong_no} tổng cộng **{format_vn(tong_no)} VNĐ**.")
                
                # --- XUẤT FILE ĐỐI SOÁT ---
                st.markdown("**📁 Tùy chọn in phiếu đối soát để gửi NCC:**")
                loai_xuat_ds_ncc = st.radio(
                    "Định dạng xuất Phiếu Đối Soát:", 
                    ["Chỉ xuất file PDF", "Chỉ xuất file Ảnh (PNG)", "Xuất cả PDF và Ảnh"], 
                    horizontal=True, 
                    index=1,
                    key=f"radio_ds_ncc_{ncc_chon_cong_no}"
                )
                
                col_ds1, col_ds2 = st.columns(2)
                with col_ds1:
                    if st.button("📝 TẠO FILE ĐỐI SOÁT CÔNG NỢ", use_container_width=True):
                        df_in_ncc = df_no.copy()
                        df_in_ncc.columns = ["ID", "Ngày Nhập", "Tên Vật Tư", "Số Lượng", "Đơn Giá", "Thành Tiền", "Ghi Chú"]
                        
                        pdf_ds_ncc = generate_doi_soat_ncc_pdf(ncc_chon_cong_no, tong_no, df_in_ncc)
                        st.session_state['pdf_doi_soat_ncc'] = pdf_ds_ncc
                        st.session_state['file_ds_name_ncc'] = f"DoiSoat_{ncc_chon_cong_no}.pdf"
                        
                        img_ds_ncc = convert_pdf_to_png(pdf_ds_ncc)
                        if img_ds_ncc:
                            st.session_state['img_doi_soat_ncc'] = img_ds_ncc
                        st.success("Đã tạo file đối soát thành công!")
                
                if 'pdf_doi_soat_ncc' in st.session_state and st.session_state.get('file_ds_name_ncc') == f"DoiSoat_{ncc_chon_cong_no}.pdf":
                    dl_d1, dl_d2 = st.columns(2)
                    if "PDF" in loai_xuat_ds_ncc or "Cả" in loai_xuat_ds_ncc:
                        with dl_d1:
                            st.download_button("🖨️ TẢI FILE ĐỐI SOÁT (PDF)", data=st.session_state['pdf_doi_soat_ncc'], file_name=st.session_state['file_ds_name_ncc'], mime="application/pdf", type="primary", use_container_width=True)
                    if ("Ảnh" in loai_xuat_ds_ncc or "Cả" in loai_xuat_ds_ncc) and st.session_state.get('img_doi_soat_ncc'):
                        with dl_d2:
                            st.download_button("🖼️ TẢI FILE ĐỐI SOÁT (ẢNH)", data=st.session_state['img_doi_soat_ncc'], file_name=st.session_state['file_ds_name_ncc'].replace('.pdf','.png'), mime="image/png", type="primary", use_container_width=True)
                
                st.markdown("---")

                # --- BẢNG THANH TOÁN ---
                st.markdown("#### 💰 Thanh toán & Cấn trừ nợ NCC")
                df_no.insert(0, "Chọn Thanh Toán", False)
                df_hien_thi_no = df_no.copy()
                df_hien_thi_no.columns = ["Chọn Thanh Toán", "Mã Giao Dịch (ID)", "Ngày Nhập", "Tên Vật Tư", "Số Lượng", "Đơn Giá", "Thành Tiền", "Ghi Chú"]
                
                st.write("Tích chọn vào các khoản nợ bên dưới mà bạn muốn thanh toán đợt này:")
                edited_no = st.data_editor(
                    df_hien_thi_no, 
                    hide_index=True, 
                    use_container_width=True,
                    column_config={
                        "Chọn Thanh Toán": st.column_config.CheckboxColumn("Thanh Toán", default=False),
                        "Mã Giao Dịch (ID)": st.column_config.NumberColumn(disabled=True),
                        "Ngày Nhập": st.column_config.TextColumn(disabled=True),
                        "Tên Vật Tư": st.column_config.TextColumn(disabled=True),
                        "Số Lượng": st.column_config.NumberColumn(disabled=True),
                        "Đơn Giá": st.column_config.NumberColumn(disabled=True),
                        "Thành Tiền": st.column_config.NumberColumn(disabled=True),
                        "Ghi Chú": st.column_config.TextColumn(disabled=True)
                    },
                    key=f"editor_no_{ncc_chon_cong_no}"
                )
                
                selected_rows = edited_no[edited_no["Chọn Thanh Toán"] == True]
                tong_chi_chon = selected_rows["Thành Tiền"].sum()
                
                st.info(f"💵 Đang chọn thanh toán: **{format_vn(tong_chi_chon)} VNĐ** / Tổng nợ: **{format_vn(tong_no)} VNĐ**")
                
                st.markdown("**📁 Tùy chọn in phiếu chi:**")
                loai_xuat_chi = st.radio(
                    "Định dạng xuất Phiếu Chi:", 
                    ["Chỉ xuất file PDF", "Chỉ xuất file Ảnh (PNG)", "Xuất cả PDF và Ảnh"], 
                    horizontal=True, 
                    key="radio_xuat_chi",
                    index=1
                )
                
                c_tt1, c_tt2 = st.columns([1, 2])
                with c_tt1:
                    if st.button("💸 XÁC NHẬN THANH TOÁN MỤC ĐÃ CHỌN", type="primary", use_container_width=True):
                        ids_to_pay = selected_rows["Mã Giao Dịch (ID)"].tolist()
                        if not ids_to_pay:
                            st.error("⚠️ Vui lòng tích chọn ít nhất 1 khoản nợ từ bảng trên để thanh toán!")
                        else:
                            ids_tuple = tuple(ids_to_pay)
                            if len(ids_to_pay) == 1:
                                c.execute("UPDATE public.ls_nhap_xuat_kho SET trang_thai_tt='Đã thanh toán' WHERE id = %s", (ids_to_pay[0],))
                            else:
                                c.execute(f"UPDATE public.ls_nhap_xuat_kho SET trang_thai_tt='Đã thanh toán' WHERE id IN {ids_tuple}")
                            
                            ngay_chi_hien_tai = lay_gio_vn().strftime("%d/%m/%Y %H:%M")
                            ma_phieu_chi = f"PC_{int(time.time())}"
                            chi_tiet_json = selected_rows.to_json(orient='records')
                            
                            c.execute("""INSERT INTO public.ls_phieu_chi (ma_phieu, ngay_chi, ten_ncc, tong_chi, chi_tiet) 
                                         VALUES (%s, %s, %s, %s, %s)""", 
                                      (ma_phieu_chi, ngay_chi_hien_tai, ncc_chon_cong_no, float(tong_chi_chon), chi_tiet_json))
                            conn.commit()
                            don_dep_lich_su_chi()
                            
                            st.session_state['pdf_phieu_chi'] = generate_phieu_chi_pdf(ncc_chon_cong_no, ma_phieu_chi, tong_chi_chon, ngay_chi_hien_tai, selected_rows)
                            st.session_state['ten_file_chi'] = f"PhieuChi_{ncc_chon_cong_no}.pdf"
                            
                            img_chi = convert_pdf_to_png(st.session_state['pdf_phieu_chi'])
                            if img_chi:
                                st.session_state['img_phieu_chi'] = img_chi
                                
                            st.success(f"✅ Đã thanh toán công nợ thành công. Hệ thống đã gạch nợ.")
                
                if 'pdf_phieu_chi' in st.session_state:
                    st.markdown("---")
                    dl_c1, dl_c2 = st.columns(2)
                    if "PDF" in loai_xuat_chi or "Cả" in loai_xuat_chi:
                        with dl_c1:
                            st.download_button("🖨️ TẢI PHIẾU CHI (PDF)", data=st.session_state['pdf_phieu_chi'], file_name=st.session_state['ten_file_chi'], mime="application/pdf", type="primary", use_container_width=True)
                    if ("Ảnh" in loai_xuat_chi or "Cả" in loai_xuat_chi) and st.session_state.get('img_phieu_chi'):
                        with dl_c2:
                            st.download_button("🖼️ TẢI PHIẾU CHI (ẢNH)", data=st.session_state['img_phieu_chi'], file_name=st.session_state['ten_file_chi'].replace('.pdf','.png'), mime="image/png", type="primary", use_container_width=True)
            else:
                st.success(f"✅ Tuyệt vời! Hiện tại bạn không nợ công ty {ncc_chon_cong_no} đồng nào.")
    except Exception as e: pass

    st.markdown("---")
    st.subheader("➕ Thêm Nguyên Vật Liệu Mới")
    with st.form("form_them_nl", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1: ma_nl = st.text_input("Mã Vật Tư")
        with c2: ten_nl = st.text_input("Tên Vật Tư (*)")
        with c3: don_vi = st.selectbox("Đơn vị", ["Kg", "Gram", "Cái", "Thùng", "Cuộn", "Mét", "Lít", "Bộ"])
        if st.form_submit_button("💾 Lưu NVL Mới"):
            if ten_nl:
                try:
                    c.execute("INSERT INTO public.dm_nguyen_lieu (ma_nl, ten_nl, don_vi) VALUES (%s, %s, %s)", (ma_nl or f"VT{int(time.time())}", ten_nl.strip(), don_vi))
                    conn.commit(); st.success("✅ Đã thêm!"); time.sleep(1); st.rerun()
                except: st.error("⚠️ Lỗi: Trùng tên hoặc mã vật tư!")
            else: st.warning("Vui lòng nhập Tên Vật Tư!")

    st.markdown("---")
    st.subheader("📄 Danh Sách Nguyên Vật Liệu")
    try:
        df_nl = pd.read_sql("SELECT id, ma_nl, ten_nl, don_vi FROM public.dm_nguyen_lieu ORDER BY id DESC", conn)
        if not df_nl.empty:
            df_nl = df_nl.fillna({"ma_nl": "", "ten_nl": "", "don_vi": ""})
            edited_nl = st.data_editor(
                df_nl,
                column_config={
                    "id": None,
                    "ma_nl": st.column_config.TextColumn("Mã NVL"),
                    "ten_nl": st.column_config.TextColumn("Tên Nguyên Vật Liệu"),
                    "don_vi": st.column_config.TextColumn("Đơn Vị"),
                },
                hide_index=True, use_container_width=True, key="editor_nl"
            )

            diff_mask = (edited_nl['ma_nl'] != df_nl['ma_nl']) | (edited_nl['ten_nl'] != df_nl['ten_nl']) | (edited_nl['don_vi'] != df_nl['don_vi'])

            if diff_mask.any():
                st.warning("⚠️ CHÚ Ý: Bạn vừa chỉnh sửa thông tin vật tư trên bảng. Bạn có muốn lưu lại những thay đổi này không?")
                col_luu1, col_luu2 = st.columns(2)
                with col_luu1:
                    if st.button("💾 ĐỒNG Ý LƯU THAY ĐỔI", type="primary", use_container_width=True):
                        changed_rows = edited_nl[diff_mask]
                        try:
                            count = 0
                            for _, row in changed_rows.iterrows():
                                c.execute("UPDATE public.dm_nguyen_lieu SET ma_nl=%s, ten_nl=%s, don_vi=%s WHERE id=%s",
                                          (str(row['ma_nl']).strip(), str(row['ten_nl']).strip(), str(row['don_vi']).strip(), int(row['id'])))
                                count += 1
                            conn.commit()
                            st.success(f"✅ Đã cập nhật thành công {count} vật tư!"); time.sleep(1.5); st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Lỗi cập nhật: {e}")
                with col_luu2:
                    if st.button("❌ HỦY BỎ", use_container_width=True): st.rerun()
            
            st.markdown("---")
            col_xoa1, col_xoa2 = st.columns([3, 1])
            with col_xoa1: nl_can_xoa = st.selectbox("Chọn NVL cần xóa:", ["-- Chọn --"] + df_nl['ten_nl'].tolist())
            with col_xoa2:
                st.write(""); st.write("")
                if st.button("🚨 Xóa Vĩnh Viễn", type="primary", use_container_width=True):
                    if nl_can_xoa != "-- Chọn --":
                        try:
                            c.execute("DELETE FROM public.dm_nguyen_lieu WHERE ten_nl=%s", (nl_can_xoa,))
                            conn.commit(); st.success(f"✅ Đã xóa: {nl_can_xoa}"); time.sleep(1); st.rerun()
                        except Exception as e:
                            conn.rollback(); st.error(f"Lỗi: {e}")
        else: st.info("Kho NVL đang trống.")
    except Exception as e: st.error(f"Lỗi truy xuất dữ liệu: {e}")

with tab2:
    chuyem_muc = st.radio("Chọn nghiệp vụ Kho:", ["📝 0. Tạo Đơn Nhập Hàng", "📥 1. Nhập NVL, NCC", "📦 2. Nhập Thành Phẩm", "🚚 3. Xuất Kho (Theo Đơn Hàng)"], horizontal=True)
    st.markdown("---")

    if "0. Tạo Đơn Nhập Hàng" in chuyem_muc:
        st.markdown("#### 📝 Lập Phiếu Nhập Kho (Nhiều Vật Tư)")
        
        if 'gio_nhap_kho' not in st.session_state:
            st.session_state.gio_nhap_kho = []

        try:
            df_ncc = pd.read_sql("SELECT ten_ncc FROM public.dm_ncc", conn)
            danh_sach_ncc = df_ncc['ten_ncc'].tolist() if not df_ncc.empty else []
            
            df_nl_ton = pd.read_sql("SELECT ten_nl FROM public.dm_nguyen_lieu", conn)
            danh_sach_nl = df_nl_ton['ten_nl'].tolist() if not df_nl_ton.empty else []
            
            ncc_chon = st.selectbox("🏢 Chọn Nhà Cung Cấp:", ["-- Chọn NCC --"] + danh_sach_ncc)
            
            with st.form("form_them_sp_nhap"):
                c1, c2, c3 = st.columns([2, 1, 1])
                nl_chon = c1.selectbox("📦 Chọn Vật Tư", ["-- Chọn Vật Tư --"] + danh_sach_nl)
                sl_nhap = c2.number_input("Số lượng", min_value=1.0, step=1.0)
                phan_loai = c3.selectbox("Phân loại nhập", ["Kg", "Bịch", "Cái"])
                
                if st.form_submit_button("➕ Thêm vào phiếu nhập"):
                    if nl_chon != "-- Chọn Vật Tư --":
                        st.session_state.gio_nhap_kho.append({
                            "Vật Tư": nl_chon,
                            "Số Lượng": sl_nhap,
                            "Phân Loại": phan_loai
                        })
                        st.rerun()
                    else:
                        st.warning("Vui lòng chọn vật tư!")
            
            if st.session_state.gio_nhap_kho:
                df_gio = pd.DataFrame(st.session_state.gio_nhap_kho)
                df_gio.insert(0, "Xóa", False)
                
                st.write("**Danh sách vật tư trong phiếu nhập hiện tại:**")
                edited_gio = st.data_editor(
                    df_gio,
                    column_config={
                        "Xóa": st.column_config.CheckboxColumn("🗑️ Xóa", default=False),
                        "Vật Tư": st.column_config.TextColumn(disabled=True),
                        "Số Lượng": st.column_config.NumberColumn("Số Lượng", min_value=1.0),
                        "Phân Loại": st.column_config.SelectboxColumn("Phân Loại", options=["Kg", "Bịch", "Cái"])
                    },
                    hide_index=True, use_container_width=True
                )
                
                if edited_gio['Xóa'].any():
                    df_valid = edited_gio[edited_gio['Xóa'] == False].drop(columns=['Xóa'])
                    st.session_state.gio_nhap_kho = df_valid.to_dict('records')
                    st.rerun()
                
                st.session_state.gio_nhap_kho = edited_gio.drop(columns=['Xóa']).to_dict('records')
                
                col_tt1, col_tt2 = st.columns(2)
                with col_tt1:
                    trang_thai_tt = st.selectbox("Trạng thái thanh toán", ["Chưa thanh toán", "Đã thanh toán"])
                with col_tt2:
                    ghi_chu = st.text_area("📝 Ghi chú (sẽ in thành bảng riêng bên dưới):")
                
                loai_xuat_nhap = st.radio(
                    "Định dạng xuất file:", 
                    ["Chỉ xuất PDF", "Chỉ xuất Ảnh (PNG)", "Xuất cả PDF và Ảnh"], 
                    horizontal=True, index=1
                )
                
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("💾 LƯU KHO & TẠO PHIẾU", type="primary", use_container_width=True):
                        if ncc_chon == "-- Chọn NCC --":
                            st.error("⚠️ Vui lòng chọn Nhà Cung Cấp!")
                        else:
                            ma_phieu_nhap = f"PN_{int(time.time())}"
                            ngay_nhap_str = lay_gio_vn().strftime("%d/%m/%Y %H:%M")
                            
                            df_luu = pd.DataFrame(st.session_state.gio_nhap_kho)
                            
                            for _, row in df_luu.iterrows():
                                vt = row['Vật Tư']
                                sl = row['Số Lượng']
                                pl = row['Phân Loại']
                                gc_chi_tiet = f"Phiếu {ma_phieu_nhap} - Phân loại: {pl} - {ghi_chu}" if ghi_chu else f"Phiếu {ma_phieu_nhap} - Phân loại: {pl}"
                                
                                c.execute("UPDATE public.dm_nguyen_lieu SET ton_kho = ton_kho + %s WHERE ten_nl = %s", (sl, vt))
                                
                                c.execute("""INSERT INTO public.ls_nhap_xuat_kho 
                                             (ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, don_gia, thanh_tien, ghi_chu, nha_cung_cap, trang_thai_tt) 
                                             VALUES (%s, 'Nhập NVL', %s, %s, %s, %s, %s, %s, %s)""", 
                                          (ngay_nhap_str, vt, sl, 0, 0, gc_chi_tiet, ncc_chon, trang_thai_tt))
                            
                            conn.commit()
                            
                            pdf_nhap = generate_phieu_nhap_pdf(ma_phieu_nhap, ncc_chon, df_luu, ghi_chu, ngay_nhap_str)
                            st.session_state['pdf_phieu_nhap'] = pdf_nhap
                            st.session_state['ten_phieu_nhap'] = f"{ma_phieu_nhap}_{ncc_chon}.pdf"
                            
                            img_nhap = convert_pdf_to_png(pdf_nhap)
                            if img_nhap:
                                st.session_state['img_phieu_nhap'] = img_nhap
                                
                            st.session_state.gio_nhap_kho = []
                            st.success("✅ Đã lưu kho và tạo phiếu thành công! Hãy tải file bên dưới.")
                
                with col_b2:
                    if st.button("🗑️ Xóa Phiếu Nháp", use_container_width=True):
                        st.session_state.gio_nhap_kho = []
                        st.rerun()
                
                if 'pdf_phieu_nhap' in st.session_state:
                    st.markdown("---")
                    dl1, dl2 = st.columns(2)
                    if "PDF" in loai_xuat_nhap or "Cả" in loai_xuat_nhap:
                        with dl1:
                            st.download_button("🖨️ TẢI PHIẾU (PDF)", data=st.session_state['pdf_phieu_nhap'], file_name=st.session_state['ten_phieu_nhap'], mime="application/pdf", type="primary", use_container_width=True)
                    if ("Ảnh" in loai_xuat_nhap or "Cả" in loai_xuat_nhap) and st.session_state.get('img_phieu_nhap'):
                        with dl2:
                            st.download_button("🖼️ TẢI PHIẾU (ẢNH)", data=st.session_state['img_phieu_nhap'], file_name=st.session_state['ten_phieu_nhap'].replace('.pdf','.png'), mime="image/png", type="primary", use_container_width=True)
                            
        except Exception as e:
            st.error(f"Lỗi: {e}")

    elif "3. Xuất Kho" in chuyem_muc:
        st.markdown("#### 🚚 Quản Lý Xuất Kho & Thu Hồi Đơn")
        try:
            df_dh = pd.read_sql("SELECT id, ma_don, ten_kh, ngay_tao, trang_thai, chi_tiet FROM public.don_hang ORDER BY id DESC", conn)
            if not df_dh.empty:
                df_dh['trang_thai'] = df_dh['trang_thai'].fillna('Chờ xuất kho')
                options = [f"[{row['trang_thai']}] {row['ma_don']} - {row['ten_kh']}" for _, row in df_dh.iterrows()]
                
                don_chon_str = st.selectbox("📌 Chọn Số Phiếu Đơn Hàng", options)
                ma_don_chon = don_chon_str.split("] ")[1].split(" - ")[0]
                don_info = df_dh[df_dh['ma_don'] == ma_don_chon].iloc[0]
                
                ten_khach_hang_hien_tai = don_info['ten_kh']
                la_dai_ly = "đại lý" in ten_khach_hang_hien_tai.lower()
                trang_thai_tt_xuat = st.selectbox(
                    "Trạng thái thanh toán Đơn hàng", 
                    ["Chưa thanh toán", "Đã thanh toán"], 
                    index=0 if la_dai_ly else 1
                )
                
                items = json.loads(don_info['chi_tiet'])
                df_items = pd.DataFrame(items)
                st.dataframe(df_items, use_container_width=True, hide_index=True)
                
                c_btn1, c_btn2 = st.columns([2, 2])
                
                if don_info['trang_thai'] in ['Chờ xuất kho', 'Mới tạo']:
                    with c_btn1:
                        if st.button("📦 XÁC NHẬN XUẤT KHO", type="primary", use_container_width=True):
                            for item in items:
                                ten_sp = item.get('Tên Sản Phẩm', item.get('Tên Sản Phẩm OME'))
                                sl = float(item.get('Số Lượng', 0))
                                don_gia_sp = float(item.get('Đơn Giá', item.get('Giá', 0)))
                                thanh_tien_sp = sl * don_gia_sp
                                
                                c.execute("UPDATE public.dm_san_pham SET ton_kho = ton_kho - %s WHERE ten_sp = %s", (sl, ten_sp))
                                c.execute("UPDATE public.dm_san_pham_ome SET ton_kho = ton_kho - %s WHERE ten_sp = %s", (sl, ten_sp))
                                
                                c.execute("""INSERT INTO public.ls_nhap_xuat_kho 
                                             (ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, don_gia, thanh_tien, ghi_chu, khach_hang, trang_thai_tt, tien_da_thu) 
                                             VALUES (%s, 'Xuất Bán', %s, %s, %s, %s, %s, %s, %s, %s)""", 
                                          (lay_gio_vn().strftime("%d/%m/%Y %H:%M"), ten_sp, -sl, don_gia_sp, thanh_tien_sp, f"Đơn {ma_don_chon}", ten_khach_hang_hien_tai, trang_thai_tt_xuat, 0))
                                
                            c.execute("UPDATE public.don_hang SET trang_thai = 'Đã xuất kho' WHERE ma_don = %s", (ma_don_chon,))
                            conn.commit(); st.success("Đã xuất kho và lưu công nợ!"); time.sleep(1.5); st.rerun()
                    
                    with c_btn2:
                        if st.button("❌ HỦY ĐƠN NÀY", use_container_width=True):
                            c.execute("UPDATE public.don_hang SET trang_thai = 'Đã hủy' WHERE ma_don = %s", (ma_don_chon,))
                            conn.commit(); st.warning("Đã hủy đơn."); time.sleep(1); st.rerun()

                elif don_info['trang_thai'] == 'Đã xuất kho':
                    with c_btn1:
                        pdf_bytes = generate_phieu_xuat_pdf(df_items, ma_don_chon, don_info['ten_kh'])
                        st.download_button("🖨️ IN PHIẾU XUẤT (PDF)", pdf_bytes, f"PhieuXuat_{ma_don_chon}.pdf", "application/pdf", use_container_width=True)
                    
                    with c_btn2:
                        if st.button("🔄 THU HỒI ĐƠN (Trả hàng)", use_container_width=True):
                            for item in items:
                                ten_sp = item.get('Tên Sản Phẩm', item.get('Tên Sản Phẩm OME'))
                                sl = float(item.get('Số Lượng', 0))
                                c.execute("UPDATE public.dm_san_pham SET ton_kho = ton_kho + %s WHERE ten_sp = %s", (sl, ten_sp))
                                c.execute("UPDATE public.dm_san_pham_ome SET ton_kho = ton_kho + %s WHERE ten_sp = %s", (sl, ten_sp))
                                c.execute("INSERT INTO public.ls_nhap_xuat_kho (ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, ghi_chu) VALUES (%s, 'Thu hồi đơn', %s, %s, %s)", (lay_gio_vn().strftime("%d/%m/%Y %H:%M"), ten_sp, sl, f"Thu hồi đơn {ma_don_chon}"))
                            c.execute("UPDATE public.don_hang SET trang_thai = 'Đã thu hồi' WHERE ma_don = %s", (ma_don_chon,))
                            conn.commit(); st.info("Đã thu hồi hàng về kho."); time.sleep(1.5); st.rerun()
                else:
                    st.info(f"Đơn hàng này đang ở trạng thái: **{don_info['trang_thai']}**")

            else: st.info("Chưa có đơn hàng nào.")
        except Exception as e: st.error(str(e))
    
    elif "1. Nhập NVL, NCC" in chuyem_muc:
        st.markdown("#### 📥 Nhập Đơn Lẻ Nguyên Vật Liệu")
        try:
            df_nl_ton = pd.read_sql("SELECT ten_nl, don_vi FROM public.dm_nguyen_lieu", conn)
            try: df_ncc = pd.read_sql("SELECT ten_ncc FROM public.dm_ncc", conn)
            except: df_ncc = pd.DataFrame()
            danh_sach_ncc = df_ncc['ten_ncc'].tolist() if not df_ncc.empty else ["-- Chưa có Nhà Cung Cấp --"]

            if not df_nl_ton.empty:
                with st.form("form_nhap_nvl"):
                    col_n1, col_n2 = st.columns(2)
                    with col_n1:
                        ngay_nhap_hd = st.date_input("Ngày nhập hàng", lay_gio_vn().date(), format="DD/MM/YYYY")
                        nl_chon = st.selectbox("Chọn Vật Tư cần nhập", df_nl_ton['ten_nl'].tolist())
                        sl_tt = st.number_input("Số lượng nhập", min_value=1.0, step=1.0)
                    with col_n2:
                        ncc_chon = st.selectbox("Chọn Nhà Cung Cấp", danh_sach_ncc)
                        don_gia = st.number_input("Đơn giá nhập (VNĐ)", min_value=0.0, step=1000.0)
                        trang_thai_tt = st.selectbox("Trạng thái thanh toán", ["Chưa thanh toán", "Đã thanh toán"])
                    
                    ghi_chu = st.text_input("Ghi chú thêm (Số xe, người giao...)")

                    if st.form_submit_button("💾 Xác nhận Nhập NVL", type="primary"):
                        if ncc_chon.startswith("--"):
                            st.error("⚠️ Vui lòng thêm tên Nhà Cung Cấp ở Tab 1 trước khi nhập hàng!")
                        else:
                            thanh_tien = sl_tt * don_gia
                            ngay_tt = ngay_nhap_hd.strftime("%d/%m/%Y")
                            
                            c.execute("""INSERT INTO public.ls_nhap_xuat_kho 
                                         (ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, don_gia, thanh_tien, ghi_chu, nha_cung_cap, trang_thai_tt) 
                                         VALUES (%s, 'Nhập NVL', %s, %s, %s, %s, %s, %s, %s)""", 
                                      (ngay_tt, nl_chon, sl_tt, don_gia, thanh_tien, ghi_chu, ncc_chon, trang_thai_tt))
                            conn.commit()
                            st.success(f"✅ Đã ghi nhận lô hàng từ {ncc_chon} vào Lịch sử & Công nợ!")
                            time.sleep(2); st.rerun()
            else: st.warning("⚠️ Kho chưa có Danh mục Vật tư nào.")
        except Exception as e: st.error(str(e))

    elif "2. Nhập Thành Phẩm" in chuyem_muc:
        st.markdown("#### 📦 Nhập Thành Phẩm Vừa Sản Xuất")
        try:
            df_sp_chuan = pd.read_sql("SELECT ten_sp, ton_kho, 'chuẩn' as loai FROM public.dm_san_pham", conn)
            df_sp_ome = pd.read_sql("SELECT ten_sp, ton_kho, 'ome' as loai FROM public.dm_san_pham_ome", conn)
            df_all_sp = pd.concat([df_sp_chuan, df_sp_ome]).dropna(subset=['ten_sp']).reset_index(drop=True)
            
            if not df_all_sp.empty:
                with st.form("form_nhap_sp"):
                    sp_chon = st.selectbox("Chọn Thành Phẩm đã làm xong", df_all_sp['ten_sp'].unique().tolist())
                    
                    col_sl1, col_sl2 = st.columns([2, 1])
                    with col_sl1:
                        sl_nhap = st.number_input("Số lượng thành phẩm nhập kho", min_value=1.0, step=1.0)
                    with col_sl2:
                        don_vi_nhap = st.selectbox("Đơn vị", ["bộ", "lẻ", "kg"], index=0)

                    if st.form_submit_button("🔄 Lưu Thành Phẩm", type="primary"):
                        sp_info = df_all_sp[df_all_sp['ten_sp'] == sp_chon].iloc[0]
                        loai_sp = sp_info['loai']
                        ngay_tt = lay_gio_vn().strftime("%d/%m/%Y %H:%M")

                        bang_update = "public.dm_san_pham" if loai_sp == 'chuẩn' else "public.dm_san_pham_ome"
                        c.execute(f"UPDATE {bang_update} SET ton_kho = ton_kho + %s WHERE ten_sp = %s", (sl_nhap, sp_chon))
                        
                        ghi_chu_sp = f"Sản xuất hoàn thành ({don_vi_nhap})"
                        c.execute("""INSERT INTO public.ls_nhap_xuat_kho (ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, ghi_chu) 
                                     VALUES (%s, 'Nhập Thành Phẩm', %s, %s, %s)""", (ngay_tt, sp_chon, sl_nhap, ghi_chu_sp))
                        
                        conn.commit()
                        st.success(f"✅ Đã nhập {sl_nhap} {don_vi_nhap} {sp_chon} vào kho!")
                        time.sleep(2); st.rerun()
            else: st.info("Chưa có danh mục sản phẩm.")
        except Exception as e: st.error(str(e))

# ------------------------------------------
# TAB KHÁCH HÀNG CÔNG NỢ
# ------------------------------------------
with tab_kh:
    st.subheader("👤 Theo Dõi & Thu Hồi Công Nợ Khách Hàng / Đại Lý")
    try:
        # Tải danh sách đơn xuất bán chưa thanh toán hết (kể cả có trả 1 phần)
        df_kh_no = pd.read_sql("SELECT id, ngay_thao_tac, khach_hang, ten_nl, so_luong, don_gia, thanh_tien, COALESCE(tien_da_thu, 0) as tien_da_thu, ghi_chu FROM public.ls_nhap_xuat_kho WHERE loai_thao_tac='Xuất Bán' AND trang_thai_tt='Chưa thanh toán' ORDER BY khach_hang, id ASC", conn)
        
        if not df_kh_no.empty:
            df_kh_no['tien_con_no'] = df_kh_no['thanh_tien'] - df_kh_no['tien_da_thu']
            danh_sach_kh = df_kh_no['khach_hang'].unique().tolist()
            kh_chon = st.selectbox("🔍 Chọn Khách Hàng / Đại Lý để xem công nợ:", ["-- Chọn Khách Hàng --"] + danh_sach_kh)
            
            if kh_chon != "-- Chọn Khách Hàng --":
                df_hien_thi_kh = df_kh_no[df_kh_no['khach_hang'] == kh_chon].copy()
                tong_tien_no_kh = df_hien_thi_kh['tien_con_no'].sum()
                
                st.warning(f"🚨 **TỔNG NỢ HIỆN TẠI CỦA {kh_chon.upper()}: {format_vn(tong_tien_no_kh)} VNĐ**")
                
                # --- XUẤT FILE ĐỐI SOÁT ---
                st.markdown("**📁 Tùy chọn in phiếu đối soát để gửi khách:**")
                loai_xuat_ds = st.radio(
                    "Định dạng xuất Phiếu Đối Soát:", 
                    ["Chỉ xuất file PDF", "Chỉ xuất file Ảnh (PNG)", "Xuất cả PDF và Ảnh"], 
                    horizontal=True, 
                    index=1
                )
                
                col_ds1, col_ds2 = st.columns(2)
                with col_ds1:
                    if st.button("📝 TẠO FILE ĐỐI SOÁT CÔNG NỢ", use_container_width=True):
                        df_in = df_hien_thi_kh[['ngay_thao_tac', 'ten_nl', 'ghi_chu', 'thanh_tien', 'tien_da_thu', 'tien_con_no']].copy()
                        df_in.columns = ["Ngày Xuất", "Sản Phẩm", "Ghi Chú", "Thành Tiền", "Đã Thu Tiền (VNĐ)", "Còn Nợ (VNĐ)"]
                        
                        pdf_ds = generate_doi_soat_kh_pdf(kh_chon, tong_tien_no_kh, df_in)
                        st.session_state['pdf_doi_soat'] = pdf_ds
                        st.session_state['file_ds_name'] = f"DoiSoat_{kh_chon}.pdf"
                        
                        img_ds = convert_pdf_to_png(pdf_ds)
                        if img_ds:
                            st.session_state['img_doi_soat'] = img_ds
                        st.success("Đã tạo file thành công!")
                
                if 'pdf_doi_soat' in st.session_state and st.session_state.get('file_ds_name') == f"DoiSoat_{kh_chon}.pdf":
                    dl_d1, dl_d2 = st.columns(2)
                    if "PDF" in loai_xuat_ds or "Cả" in loai_xuat_ds:
                        with dl_d1:
                            st.download_button("🖨️ TẢI FILE ĐỐI SOÁT (PDF)", data=st.session_state['pdf_doi_soat'], file_name=st.session_state['file_ds_name'], mime="application/pdf", type="primary", use_container_width=True)
                    if ("Ảnh" in loai_xuat_ds or "Cả" in loai_xuat_ds) and st.session_state.get('img_doi_soat'):
                        with dl_d2:
                            st.download_button("🖼️ TẢI FILE ĐỐI SOÁT (ẢNH)", data=st.session_state['img_doi_soat'], file_name=st.session_state['file_ds_name'].replace('.pdf','.png'), mime="image/png", type="primary", use_container_width=True)
                
                st.markdown("---")
                
                # --- THANH TOÁN TRẢ TỪNG PHẦN ---
                st.markdown("#### 💰 Thanh toán & Cấn trừ nợ")
                with st.form("form_thu_tien_kh"):
                    col_thu1, col_thu2 = st.columns([2, 1])
                    with col_thu1:
                        so_tien_thu = st.number_input("Nhập số tiền khách hàng thanh toán (VNĐ):", min_value=0.0, step=100000.0)
                    with col_thu2:
                        st.write("")
                        st.write("")
                        btn_thu = st.form_submit_button("✅ XÁC NHẬN THU TIỀN & CẤN TRỪ NỢ", type="primary", use_container_width=True)
                        
                    if btn_thu:
                        if so_tien_thu > 0:
                            if so_tien_thu > tong_tien_no_kh:
                                st.error(f"⚠️ Số tiền nhập vào lớn hơn tổng nợ ({format_vn(tong_tien_no_kh)} đ). Vui lòng nhập lại!")
                            else:
                                tien_dang_thu = so_tien_thu
                                for _, row in df_hien_thi_kh.iterrows():
                                    if tien_dang_thu <= 0:
                                        break
                                    
                                    tien_con_no_don_nay = row['tien_con_no']
                                    if tien_dang_thu >= tien_con_no_don_nay:
                                        c.execute("UPDATE public.ls_nhap_xuat_kho SET tien_da_thu = thanh_tien, trang_thai_tt = 'Đã thanh toán' WHERE id = %s", (row['id'],))
                                        tien_dang_thu -= tien_con_no_don_nay
                                    else:
                                        c.execute("UPDATE public.ls_nhap_xuat_kho SET tien_da_thu = tien_da_thu + %s WHERE id = %s", (tien_dang_thu, row['id']))
                                        tien_dang_thu = 0
                                conn.commit()
                                st.success(f"✅ Đã cấn trừ thành công {format_vn(so_tien_thu)} VNĐ vào công nợ của {kh_chon}!")
                                time.sleep(1.5); st.rerun()
                        else:
                            st.warning("Vui lòng nhập số tiền lớn hơn 0.")

                st.markdown("---")
                
                # --- BẢNG CHI TIẾT ---
                st.write("**Bảng chi tiết các đơn còn nợ (Có thể tích chọn để gạch nợ thủ công nguyên đơn):**")
                df_hien_thi_kh.insert(0, "Đã Thu Đủ Tiền Đơn", False)
                df_hien_thi_b = df_hien_thi_kh[['Đã Thu Đủ Tiền Đơn', 'id', 'ngay_thao_tac', 'ten_nl', 'thanh_tien', 'tien_da_thu', 'tien_con_no', 'ghi_chu']].copy()
                df_hien_thi_b.columns = ["Đã Thu Đủ Tiền Đơn", "ID", "Ngày Xuất", "Sản Phẩm", "Tổng Tiền", "Đã Thu (Một phần)", "Còn Nợ (Cần Thu)", "Ghi Chú"]
                
                edited_kh_no = st.data_editor(
                    df_hien_thi_b,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Đã Thu Đủ Tiền Đơn": st.column_config.CheckboxColumn("Thu Đủ Nguyên Đơn", default=False),
                        "ID": st.column_config.NumberColumn(disabled=True),
                        "Ngày Xuất": st.column_config.TextColumn(disabled=True),
                        "Sản Phẩm": st.column_config.TextColumn(disabled=True),
                        "Tổng Tiền": st.column_config.NumberColumn(disabled=True),
                        "Đã Thu (Một phần)": st.column_config.NumberColumn(disabled=True),
                        "Còn Nợ (Cần Thu)": st.column_config.NumberColumn(disabled=True),
                        "Ghi Chú": st.column_config.TextColumn(disabled=True)
                    },
                    key="editor_kh_no"
                )
                
                selected_kh_rows = edited_kh_no[edited_kh_no["Đã Thu Đủ Tiền Đơn"] == True]
                if st.button("💰 GẠCH NỢ THỦ CÔNG CÁC ĐƠN ĐÃ CHỌN", type="primary", use_container_width=True):
                    ids_to_update = selected_kh_rows["ID"].tolist()
                    if not ids_to_update:
                        st.error("⚠️ Vui lòng tích chọn ít nhất 1 đơn!")
                    else:
                        if len(ids_to_update) == 1:
                            c.execute("UPDATE public.ls_nhap_xuat_kho SET tien_da_thu = thanh_tien, trang_thai_tt='Đã thanh toán' WHERE id = %s", (ids_to_update[0],))
                        else:
                            c.execute(f"UPDATE public.ls_nhap_xuat_kho SET tien_da_thu = thanh_tien, trang_thai_tt='Đã thanh toán' WHERE id IN {tuple(ids_to_update)}")
                        conn.commit()
                        st.success("✅ Đã gạch nợ thành công!")
                        time.sleep(1.5); st.rerun()
        else:
            st.success("✅ Tuyệt vời! Hiện tại không có Khách hàng hoặc Đại lý nào nợ tiền.")
    except Exception as e: st.error(f"Lỗi: {e}")

with tab3:
    st.info("💡 **Mẹo:** Bạn có thể chỉnh sửa trực tiếp số liệu ở cột **Tồn Kho theo Lốc (Sửa được)**. Sau khi sửa, hãy bấm nút Lưu xuất hiện bên dưới bảng để tự động tính và cập nhật số Cái.")
    
    st.subheader("📦 Tồn Kho Thành Phẩm")
    try:
        # Lấy thêm cột quy_cach_loc để phục vụ quy đổi lốc <-> cái
        df_tc = pd.read_sql("SELECT id, ten_sp, ton_kho, COALESCE(quy_cach_loc, 1) as quy_cach_loc, 'chuẩn' as loai FROM public.dm_san_pham", conn)
        df_to = pd.read_sql("SELECT id, ten_sp, ton_kho, COALESCE(quy_cach_loc, 1) as quy_cach_loc, 'ome' as loai FROM public.dm_san_pham_ome", conn)
        
        df_tp = pd.concat([df_tc, df_to]).dropna(subset=['id']).reset_index(drop=True)
        df_tp['ton_kho'] = df_tp['ton_kho'].fillna(0.0)
        df_tp['quy_cach_loc'] = df_tp['quy_cach_loc'].fillna(1.0)
        
        # Tạo các cột hiển thị: Lốc và Cái
        df_tp['ton_kho_loc'] = df_tp['ton_kho'] / df_tp['quy_cach_loc']
        df_tp['ton_kho_cai'] = df_tp['ton_kho']
        
        edited_tp = st.data_editor(
            df_tp,
            column_config={
                "id": None,
                "loai": None,
                "quy_cach_loc": None,
                "ton_kho": None, # Ẩn cột tồn kho gốc
                "ten_sp": st.column_config.TextColumn("Tên Sản Phẩm", disabled=True),
                "ton_kho_loc": st.column_config.NumberColumn("Tồn Kho theo Lốc (Sửa được)", format="%.2f"),
                "ton_kho_cai": st.column_config.NumberColumn("Số Lượng (Cái) - Hiện tại", disabled=True, format="%.0f")
            },
            hide_index=True, use_container_width=True, key="edit_ton_sp"
        )
        
        diff_tp = (edited_tp['ton_kho_loc'] != df_tp['ton_kho_loc'])
        if diff_tp.any():
            st.warning("⚠️ Số lượng lốc đã thay đổi. Bấm LƯU để cập nhật số Cái tương ứng vào hệ thống.")
            if st.button("💾 LƯU TỒN KHO THÀNH PHẨM", type="primary", use_container_width=True):
                changed_tp = edited_tp[diff_tp]
                for _, row in changed_tp.iterrows():
                    bang_update = "public.dm_san_pham" if row['loai'] == 'chuẩn' else "public.dm_san_pham_ome"
                    # Tự động tính số cái = số lốc nhập vào * quy cách lốc
                    so_cai_moi = float(row['ton_kho_loc']) * float(row['quy_cach_loc'])
                    c.execute(f"UPDATE {bang_update} SET ton_kho=%s WHERE id=%s", (so_cai_moi, int(row['id'])))
                conn.commit()
                st.success("✅ Đã tính toán và cập nhật tồn kho Thành phẩm!"); time.sleep(1.5); st.rerun()
    except Exception as e:
        st.error(f"Lỗi truy xuất tồn kho: {e}")

with tab4:
    st.subheader("🕰️ Lịch sử Thanh toán Công nợ (50 phiếu gần nhất)")
    try:
        df_ls_chi = pd.read_sql("SELECT ma_phieu, ngay_chi, ten_ncc, tong_chi, chi_tiet FROM public.ls_phieu_chi ORDER BY id DESC LIMIT 50", conn)
        if not df_ls_chi.empty:
            df_hien_thi = df_ls_chi.drop(columns=['chi_tiet'])
            df_hien_thi.columns = ["Mã Phiếu", "Ngày Chi", "Tên Nhà Cung Cấp", "Tổng Chi (VNĐ)"]
            st.dataframe(df_hien_thi, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader("🖨️ Xuất lại Phiếu Công Nợ / Phiếu Chi")
            options_chi = ["-- Chọn phiếu chi --"] + df_ls_chi['ma_phieu'].tolist()
            chon_phieu = st.selectbox("🔍 Chọn Mã Phiếu để xuất lại:", options_chi)
            
            if chon_phieu != "-- Chọn phiếu chi --":
                row_data = df_ls_chi[df_ls_chi['ma_phieu'] == chon_phieu].iloc[0]
                df_chi_tiet = pd.DataFrame(json.loads(row_data['chi_tiet']))
                
                st.write(f"**Chi tiết các khoản thanh toán của mã {chon_phieu}:**")
                st.dataframe(df_chi_tiet.drop(columns=["Chọn Thanh Toán"], errors="ignore"), use_container_width=True, hide_index=True)
                
                loai_xuat_ls = st.radio(
                    "Định dạng xuất Phiếu Chi (Xuất lại):", 
                    ["Chỉ xuất PDF", "Chỉ xuất Ảnh (PNG)", "Cả PDF và Ảnh"], 
                    horizontal=True, 
                    key=f"radio_ls_{chon_phieu}", 
                    index=1
                )
                
                pdf_re = generate_phieu_chi_pdf(row_data['ten_ncc'], chon_phieu, float(row_data['tong_chi']), row_data['ngay_chi'], df_chi_tiet)
                pdf_name_re = f"PhieuChi_{row_data['ten_ncc']}_{chon_phieu}.pdf"
                
                col_ls1, col_ls2 = st.columns(2)
                if "PDF" in loai_xuat_ls or "Cả" in loai_xuat_ls:
                    with col_ls1:
                        st.download_button("📥 XUẤT LẠI FILE PDF", data=pdf_re, file_name=pdf_name_re, mime="application/pdf", type="primary", use_container_width=True)
                if "Ảnh" in loai_xuat_ls or "Cả" in loai_xuat_ls:
                    img_re = convert_pdf_to_png(pdf_re)
                    if img_re:
                        with col_ls2:
                            st.download_button("🖼️ XUẤT LẠI FILE ẢNH", data=img_re, file_name=pdf_name_re.replace('.pdf','.png'), mime="image/png", type="primary", use_container_width=True)
        else:
            st.info("Hệ thống chưa ghi nhận lịch sử thanh toán công nợ nào.")
    except Exception as e:
        st.error(f"Lỗi: {e}")
