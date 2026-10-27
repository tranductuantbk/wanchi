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
    
    # Bổ sung cột don_gia cho Nguyên Vật Liệu
    c.execute("ALTER TABLE public.dm_nguyen_lieu ADD COLUMN IF NOT EXISTS don_gia REAL DEFAULT 0")

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
def generate_phieu_xuat_pdf(df_items, ma_don, ten_kh, conn):
    pdf = FPDF()
    pdf.add_page()
    
    has_font = os.path.exists(FONT_FILE)
    if has_font:
        pdf.add_font("Roboto", "", FONT_FILE, uni=True)
        pdf.add_font("Roboto", "B", FONT_FILE, uni=True)
        font_name = "Roboto"
    else: font_name = "Helvetica"

    pdf.set_font(font_name, "B" if has_font else "", 16)
    pdf.cell(0, 10, "PHIẾU XUẤT KHO HÀNG HÓA", ln=True, align="C")
    pdf.set_font(font_name, "", 10)
    pdf.cell(0, 6, f"Mã đơn: {ma_don}", ln=True, align="C")
    pdf.cell(0, 6, f"Khách hàng: {ten_kh}", ln=True, align="C")
    pdf.cell(0, 6, f"Ngày xuất: {lay_gio_vn().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
    pdf.ln(10)

    pdf.set_font(font_name, "B" if has_font else "", 10)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(10, 10, "STT", 1, 0, "C", True)
    pdf.cell(75, 10, "Tên Sản Phẩm", 1, 0, "C", True)
    pdf.cell(35, 10, "Số Lượng (Lốc)", 1, 0, "C", True)
    pdf.cell(35, 10, "Số Lượng (Cái)", 1, 0, "C", True)
    pdf.cell(35, 10, "Số Bao", 1, 1, "C", True)

    pdf.set_font(font_name, "", 10)
    c_pdf = conn.cursor()
    for i, row in df_items.iterrows():
        ten = str(row.get('Tên Sản Phẩm', row.get('Tên Sản Phẩm OME', 'N/A')))
        sl_loc = float(row.get('Số Lượng', 0))
        
        # Tự động lấy Quy cách lốc từ CSDL để nhân ra số cái
        quy_cach = 1.0
        try:
            c_pdf.execute("SELECT quy_cach_loc FROM public.dm_san_pham WHERE ten_sp = %s", (ten,))
            res = c_pdf.fetchone()
            if res: quy_cach = float(res[0])
            else:
                c_pdf.execute("SELECT quy_cach_loc FROM public.dm_san_pham_ome WHERE ten_sp = %s", (ten,))
                res2 = c_pdf.fetchone()
                if res2: quy_cach = float(res2[0])
        except:
            pass
            
        sl_cai = sl_loc * quy_cach
        so_bao = str(row.get('Số Bao', ''))

        pdf.cell(10, 8, str(i+1), 1, 0, "C")
        pdf.cell(75, 8, ten, 1, 0, "L")
        pdf.cell(35, 8, format_vn(sl_loc), 1, 0, "C")
        pdf.cell(35, 8, format_vn(sl_cai), 1, 0, "C")
        pdf.cell(35, 8, so_bao, 1, 1, "C")
    
    # Bảng Ghi chú trống cho nhân viên viết
    pdf.ln(8)
    pdf.set_font(font_name, 'B' if has_font else '', 11)
    pdf.cell(0, 6, "Ghi chú (Note):", ln=True)
    pdf.cell(0, 25, "", border=1, ln=True)

    pdf.ln(10)
    pdf.set_font(font_name, "", 11)
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
            pdf.cell(30, 8, ngay.split()[0] if ngay else "", border=
