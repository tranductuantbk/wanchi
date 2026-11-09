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

# ==========================================
# 🛡️ LÁ CHẮN CHỐNG MẤT DỮ LIỆU (DATABASE GUARD)
# ==========================================
conn = get_connection()

def kiem_tra_du_lieu_thuc_te(connection):
    """Hàm bắn tín hiệu kiểm tra xem Neon có đang ngủ đông không"""
    try:
        if connection.closed != 0:
            return False
        cur = connection.cursor()
        cur.execute("SELECT 1") # Lệnh test nhẹ nhất để gọi Neon dậy
        cur.fetchone()
        return True
    except:
        return False

# Kích hoạt lá chắn
if not kiem_tra_du_lieu_thuc_te(conn):
    # Nếu mất kết nối, thử xóa cache và gọi Neon dậy 1 lần
    st.cache_resource.clear()
    conn = get_connection()
    
    # Nếu gọi lần 2 vẫn không được -> Đóng băng hệ thống
    if not kiem_tra_du_lieu_thuc_te(conn):
        st.error("🚨 LÁ CHẮN BẢO VỆ DỮ LIỆU ĐANG KÍCH HOẠT!")
        st.warning("⚠️ Mạng yếu hoặc Máy chủ Neon đang ngủ đông khiến dữ liệu xưởng chưa được tải về. Để chống tình trạng ghi đè làm mất dữ liệu cũ, hệ thống tạm thời KHÓA toàn bộ thao tác.")
        if st.button("🔄 Bấm vào đây để tải lại kết nối", type="primary"):
            st.rerun()
        st.stop() # 🛑 Lệnh này sẽ chặn đứng mọi code phía dưới, không cho hiện giao diện

c = conn.cursor()
# ==========================================

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
    
    # Thêm cột giá đại lý để phục vụ tính toán module Chuyển đơn (Dropship)
    c.execute("ALTER TABLE public.dm_san_pham ADD COLUMN IF NOT EXISTS gia_dai_ly REAL DEFAULT 0")
    c.execute("ALTER TABLE public.dm_san_pham_ome ADD COLUMN IF NOT EXISTS gia_dai_ly REAL DEFAULT 0")
    
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
                
    # BẢNG MỚI ĐỂ LƯU LỊCH SỬ CHUYỂN ĐƠN ĐẠI LÝ
    c.execute('''CREATE TABLE IF NOT EXISTS public.ls_chuyen_don (
                    id SERIAL PRIMARY KEY,
                    ngay_chuyen TEXT,
                    ma_don TEXT,
                    dai_ly_nhan TEXT,
                    tong_tien_don REAL DEFAULT 0,
                    so_tien_ghi_no REAL DEFAULT 0
                )''')
                
    # BẢNG MỚI ĐỂ LƯU ĐƠN NHẬP HÀNG (CHỈ TẠO ĐƠN, KHÔNG GHI CÔNG NỢ)
    c.execute('''CREATE TABLE IF NOT EXISTS public.ls_don_nhap_hang (
                    id SERIAL PRIMARY KEY, 
                    ma_phieu TEXT, 
                    ngay_tao TEXT, 
                    ten_ncc TEXT, 
                    tong_tien REAL DEFAULT 0, 
                    chi_tiet TEXT, 
                    ghi_chu TEXT
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

def don_dep_lich_su_chuyen_don():
    """Hàm tự động dọn dẹp, chỉ giữ lại 50 đơn chuyển gần nhất"""
    try:
        c.execute("""DELETE FROM public.ls_chuyen_don
                     WHERE id NOT IN (
                         SELECT id FROM public.ls_chuyen_don 
                         ORDER BY id DESC LIMIT 50
                     )""")
        conn.commit()
    except: 
        conn.rollback()

def don_dep_lich_su_don_nhap():
    """Hàm tự động dọn dẹp, chỉ giữ lại 10 đơn nhập hàng gần nhất"""
    try:
        c.execute("""DELETE FROM public.ls_don_nhap_hang
                     WHERE id NOT IN (
                         SELECT id FROM public.ls_don_nhap_hang 
                         ORDER BY id DESC LIMIT 10
                     )""")
        conn.commit()
    except: 
        conn.rollback()

def don_dep_lich_su_nhap_nvl():
    """Hàm tự động dọn dẹp, chỉ giữ lại 100 đơn nhập NVL gần nhất"""
    try:
        c.execute("""DELETE FROM public.ls_nhap_xuat_kho
                     WHERE loai_thao_tac = 'Nhập NVL' AND id NOT IN (
                         SELECT id FROM public.ls_nhap_xuat_kho 
                         WHERE loai_thao_tac = 'Nhập NVL'
                         ORDER BY id DESC LIMIT 100
                     )""")
        conn.commit()
    except: 
        conn.rollback()

def don_dep_lich_su_nhap_tp():
    """Hàm tự động dọn dẹp, chỉ giữ lại 100 đơn nhập Thành Phẩm gần nhất"""
    try:
        c.execute("""DELETE FROM public.ls_nhap_xuat_kho
                     WHERE loai_thao_tac = 'Nhập Thành Phẩm' AND id NOT IN (
                         SELECT id FROM public.ls_nhap_xuat_kho 
                         WHERE loai_thao_tac = 'Nhập Thành Phẩm'
                         ORDER BY id DESC LIMIT 100
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

    # Logo & Header WANCHI
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

    # Tiêu đề giữ nguyên là PHIẾU XUẤT KHO HÀNG HÓA
    pdf.set_font(font_name, "B" if has_font else "", 16)
    pdf.cell(0, 10, "PHIẾU XUẤT KHO HÀNG HÓA", ln=True, align="C")
    
    pdf.set_font(font_name, "", 10)
    ngay_xuat = lay_gio_vn().strftime('%d/%m/%Y')
    pdf.cell(0, 6, f"Mã Đơn: {ma_don}   |   Ngày: {ngay_xuat}", ln=True, align="C")
    pdf.ln(5)
    
    # Căn lề trái cho Khách hàng & SĐT
    pdf.cell(0, 6, f"Khách hàng: {ten_kh}", ln=True, align="L")
    pdf.cell(0, 6, f"Điện thoại:", ln=True, align="L")
    pdf.ln(5)

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
        
        sl_cai = float(row.get('Số Lượng Cái', row.get('Số Lượng', 0)))
        
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
            
        sl_loc = sl_cai / quy_cach if quy_cach > 0 else 0
        so_bao = str(row.get('Số Bao', ''))

        pdf.cell(10, 8, str(i+1), 1, 0, "C")
        pdf.cell(75, 8, ten, 1, 0, "L")
        
        loc_str = "{:,.2f}".format(sl_loc).rstrip('0').rstrip('.') if sl_loc % 1 != 0 else format_vn(sl_loc)
        
        pdf.cell(35, 8, loc_str, 1, 0, "C")
        pdf.cell(35, 8, format_vn(sl_cai), 1, 0, "C")
        pdf.cell(35, 8, so_bao, 1, 1, "C")
    
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

def generate_phieu_nhap_pdf(ma_phieu, ten_ncc, df_items, tong_tien, ghi_chu, ngay_nhap):
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
    if ghi_chu:
        pdf.cell(0, 8, f"Ghi chú: {ghi_chu}", ln=True)
    pdf.ln(3)
    
    if not df_items.empty:
        pdf.set_font(font_name, 'B' if has_font else '', 10)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(15, 10, "STT", border=1, align="C", fill=True)
        pdf.cell(85, 10, "Tên Vật Tư", border=1, align="C", fill=True)
        pdf.cell(20, 10, "SL", border=1, align="C", fill=True)
        pdf.cell(35, 10, "Đơn Giá", border=1, align="C", fill=True)
        pdf.cell(35, 10, "Thành Tiền", border=1, ln=True, align="C", fill=True)

        pdf.set_font(font_name, "", 10)
        stt = 1
        for _, row in df_items.iterrows():
            vt = str(row.get("Vật Tư", ""))
            sl = row.get("Số Lượng", 0)
            dg = row.get("Đơn Giá", 0)
            tt = row.get("Thành Tiền", 0)
            
            pdf.cell(15, 8, str(stt), border=1, align="C")
            pdf.cell(85, 8, vt, border=1, align="L")
            pdf.cell(20, 8, format_vn(sl), border=1, align="C")
            pdf.cell(35, 8, format_vn(dg), border=1, align="R")
            pdf.cell(35, 8, format_vn(tt), border=1, ln=True, align="R")
            stt += 1
            
        pdf.set_font(font_name, 'B' if has_font else '', 11)
        pdf.cell(155, 10, "TỔNG CỘNG:", border=1, align="R")
        pdf.cell(35, 10, format_vn(tong_tien) + " đ", border=1, ln=True, align="R")

    # Thêm bảng ghi chú riêng
    pdf.ln(8)
    pdf.set_font(font_name, 'B' if has_font else '', 11)
    pdf.cell(0, 6, "Ghi chú (Note):", ln=True)
    pdf.set_font(font_name, "", 11)
    if ghi_chu:
        pdf.multi_cell(0, 8, str(ghi_chu), border=1, align="L")
    else:
        pdf.cell(0, 25, "", border=1, ln=True)

    pdf.ln(10)
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
tab2, tab1, tab_kh, tab3, tab4, tab5 = st.tabs(["📥 Nhập / Xuất Kho", "📋 NVL, NCC, Công Nợ", "👤 Khách Hàng Công Nợ", "📊 Báo Cáo Tồn Kho", "🕰️ Lịch Sử Công Nợ", "🔄 5. Quản Lý Đơn Đã Chuyển"])

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
        c1, c2, c3, c4 = st.columns([1, 2, 1, 1.5])
        with c1: ma_nl = st.text_input("Mã Vật Tư")
        with c2: ten_nl = st.text_input("Tên Vật Tư (*)")
        with c3: don_vi = st.selectbox("Đơn vị", ["Kg", "Gram", "Cái", "Thùng", "Cuộn", "Mét", "Lít", "Bộ"])
        with c4: don_gia_nl = st.number_input("Đơn giá mặc định (VNĐ)", min_value=0.0, step=1000.0)
        
        if st.form_submit_button("💾 Lưu NVL Mới"):
            if ten_nl:
                try:
                    c.execute("INSERT INTO public.dm_nguyen_lieu (ma_nl, ten_nl, don_vi, don_gia) VALUES (%s, %s, %s, %s)", 
                              (ma_nl or f"VT{int(time.time())}", ten_nl.strip(), don_vi, don_gia_nl))
                    conn.commit(); st.success("✅ Đã thêm!"); time.sleep(1); st.rerun()
                except: st.error("⚠️ Lỗi: Trùng tên hoặc mã vật tư!")
            else: st.warning("Vui lòng nhập Tên Vật Tư!")

    st.markdown("---")
    st.subheader("📄 Danh Mục Quản Lý (NVL & NCC)")
    
    col_ds_nl, col_ds_ncc = st.columns([2, 1])
    
    with col_ds_nl:
        st.markdown("**📦 Danh Sách Nguyên Vật Liệu**")
        try:
            df_nl = pd.read_sql("SELECT id, ma_nl, ten_nl, don_vi, don_gia FROM public.dm_nguyen_lieu ORDER BY id DESC", conn)
            if not df_nl.empty:
                df_nl = df_nl.fillna({"ma_nl": "", "ten_nl": "", "don_vi": "", "don_gia": 0.0})
                edited_nl = st.data_editor(
                    df_nl,
                    column_config={
                        "id": None,
                        "ma_nl": st.column_config.TextColumn("Mã NVL"),
                        "ten_nl": st.column_config.TextColumn("Tên Nguyên Vật Liệu"),
                        "don_vi": st.column_config.TextColumn("Đơn Vị"),
                        "don_gia": st.column_config.NumberColumn("Đơn Giá (VNĐ)", format="%.0f")
                    },
                    hide_index=True, use_container_width=True, key="editor_nl"
                )

                diff_mask = (edited_nl['ma_nl'] != df_nl['ma_nl']) | (edited_nl['ten_nl'] != df_nl['ten_nl']) | (edited_nl['don_vi'] != df_nl['don_vi']) | (edited_nl['don_gia'] != df_nl['don_gia'])

                if diff_mask.any():
                    st.warning("⚠️ CHÚ Ý: Bạn vừa chỉnh sửa thông tin vật tư. Bấm lưu để cập nhật.")
                    if st.button("💾 LƯU THAY ĐỔI NVL", type="primary", use_container_width=True):
                        changed_rows = edited_nl[diff_mask]
                        try:
                            for _, row in changed_rows.iterrows():
                                c.execute("UPDATE public.dm_nguyen_lieu SET ma_nl=%s, ten_nl=%s, don_vi=%s, don_gia=%s WHERE id=%s",
                                          (str(row['ma_nl']).strip(), str(row['ten_nl']).strip(), str(row['don_vi']).strip(), float(row['don_gia']), int(row['id'])))
                            conn.commit()
                            st.success(f"✅ Đã cập nhật thành công!"); time.sleep(1); st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Lỗi cập nhật: {e}")
                
                st.write("")
                nl_can_xoa = st.selectbox("Chọn NVL cần xóa:", ["-- Chọn --"] + df_nl['ten_nl'].tolist())
                if st.button("🚨 Xóa NVL Vĩnh Viễn", use_container_width=True):
                    if nl_can_xoa != "-- Chọn --":
                        try:
                            c.execute("DELETE FROM public.dm_nguyen_lieu WHERE ten_nl=%s", (nl_can_xoa,))
                            conn.commit(); st.success(f"✅ Đã xóa: {nl_can_xoa}"); time.sleep(1); st.rerun()
                        except Exception as e:
                            conn.rollback(); st.error(f"Lỗi: {e}")
            else: st.info("Kho NVL đang trống.")
        except Exception as e: st.error(f"Lỗi: {e}")
        
    with col_ds_ncc:
        st.markdown("**🏢 Danh Sách Nhà Cung Cấp**")
        try:
            df_ncc_list = pd.read_sql("SELECT id, ten_ncc FROM public.dm_ncc ORDER BY id DESC", conn)
            if not df_ncc_list.empty:
                edited_ncc = st.data_editor(
                    df_ncc_list,
                    column_config={
                        "id": None,
                        "ten_ncc": st.column_config.TextColumn("Tên Nhà Cung Cấp")
                    },
                    hide_index=True, use_container_width=True, key="editor_ncc_list"
                )
                
                diff_ncc = (edited_ncc['ten_ncc'] != df_ncc_list['ten_ncc'])
                if diff_ncc.any():
                    st.warning("⚠️ Bấm lưu để đổi tên NCC.")
                    if st.button("💾 LƯU ĐỔI TÊN NCC", type="primary", use_container_width=True):
                        try:
                            for _, r in edited_ncc[diff_ncc].iterrows():
                                c.execute("UPDATE public.dm_ncc SET ten_ncc=%s WHERE id=%s", (str(r['ten_ncc']).strip(), int(r['id'])))
                            conn.commit()
                            st.success("✅ Đã cập nhật!"); time.sleep(1); st.rerun()
                        except Exception as e:
                            conn.rollback(); st.error("Lỗi cập nhật hoặc tên đã tồn tại!")

                st.write("")
                ncc_can_xoa = st.selectbox("Chọn NCC cần xóa:", ["-- Chọn --"] + df_ncc_list['ten_ncc'].tolist())
                if st.button("🚨 Xóa NCC Vĩnh Viễn", use_container_width=True):
                    if ncc_can_xoa != "-- Chọn --":
                        try:
                            c.execute("DELETE FROM public.dm_ncc WHERE ten_ncc=%s", (ncc_can_xoa,))
                            conn.commit(); st.success(f"✅ Đã xóa: {ncc_can_xoa}"); time.sleep(1); st.rerun()
                        except Exception as e:
                            conn.rollback(); st.error(f"Lỗi: {e}")
            else: st.info("Chưa có Nhà cung cấp nào.")
        except Exception as e: st.error(f"Lỗi: {e}")

with tab2:
    chuyem_muc = st.radio("Chọn nghiệp vụ Kho:", ["📝 0. Tạo Đơn Nhập Hàng", "📥 1. Nhập NVL, NCC", "📦 2. Nhập Thành Phẩm", "🚚 3. Xuất Kho (Theo Đơn Hàng)", "🔄 4. Chuyển đơn (Đại lý)"], horizontal=True)
    st.markdown("---")

    if "0. Tạo Đơn Nhập Hàng" in chuyem_muc:
        st.markdown("#### 📝 Lập Phiếu Nhập Kho (Đơn thuần tạo phiếu)")
        
        if 'gio_nhap_kho' not in st.session_state:
            st.session_state.gio_nhap_kho = []

        try:
            df_ncc = pd.read_sql("SELECT ten_ncc FROM public.dm_ncc", conn)
            danh_sach_ncc = df_ncc['ten_ncc'].tolist() if not df_ncc.empty else []
            
            df_nl_ton = pd.read_sql("SELECT ten_nl FROM public.dm_nguyen_lieu", conn)
            danh_sach_nl = df_nl_ton['ten_nl'].tolist() if not df_nl_ton.empty else []
            
            ncc_chon = st.selectbox("🏢 Chọn Nhà Cung Cấp:", ["-- Chọn NCC --"] + danh_sach_ncc)
            
            with st.form("form_them_sp_nhap"):
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1.5])
                nl_chon = c1.selectbox("📦 Chọn Vật Tư", ["-- Chọn Vật Tư --"] + danh_sach_nl)
                sl_nhap = c2.number_input("Số lượng", min_value=1.0, step=1.0)
                phan_loai = c3.selectbox("Phân loại", ["Kg", "Bịch", "Cái"])
                don_gia = c4.number_input("Đơn giá (VNĐ)", min_value=0.0, step=1000.0)
                
                if st.form_submit_button("➕ Thêm vào phiếu nhập"):
                    if nl_chon != "-- Chọn Vật Tư --":
                        st.session_state.gio_nhap_kho.append({
                            "Vật Tư": nl_chon,
                            "Số Lượng": sl_nhap,
                            "Phân Loại": phan_loai,
                            "Đơn Giá": don_gia,
                            "Thành Tiền": sl_nhap * don_gia
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
                        "Phân Loại": st.column_config.SelectboxColumn("Phân Loại", options=["Kg", "Bịch", "Cái"]),
                        "Đơn Giá": st.column_config.NumberColumn("Đơn Giá (VNĐ)", min_value=0.0),
                        "Thành Tiền": st.column_config.NumberColumn("Thành Tiền", disabled=True)
                    },
                    hide_index=True, use_container_width=True
                )
                
                if edited_gio['Xóa'].any():
                    df_valid = edited_gio[edited_gio['Xóa'] == False].drop(columns=['Xóa'])
                    df_valid['Thành Tiền'] = df_valid['Số Lượng'] * df_valid['Đơn Giá']
                    st.session_state.gio_nhap_kho = df_valid.to_dict('records')
                    st.rerun()
                
                edited_gio['Thành Tiền'] = edited_gio['Số Lượng'] * edited_gio['Đơn Giá']
                st.session_state.gio_nhap_kho = edited_gio.drop(columns=['Xóa']).to_dict('records')
                
                tong_tien = float(edited_gio['Thành Tiền'].sum())
                st.write(f"### 💰 TỔNG CỘNG: {format_vn(tong_tien)} VNĐ")
                
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
                    if st.button("💾 TẠO ĐƠN & XUẤT PHIẾU (Không ghi công nợ)", type="primary", use_container_width=True):
                        # Gỡ bỏ kiểm tra NCC, thay bằng chuỗi rỗng nếu chưa chọn
                        ten_ncc_luu = ncc_chon if ncc_chon != "-- Chọn NCC --" else ""
                        
                        ma_phieu_nhap = f"PN_{int(time.time())}"
                        ngay_nhap_str = lay_gio_vn().strftime("%d/%m/%Y %H:%M")
                        
                        df_luu = pd.DataFrame(st.session_state.gio_nhap_kho)
                        
                        # CHỈ LƯU VÀO BẢNG ĐƠN TẠO, KHÔNG TRỪ/CỘNG TỒN KHO, KHÔNG GHI CÔNG NỢ
                        chi_tiet_json = df_luu.to_json(orient='records')
                        c.execute("""INSERT INTO public.ls_don_nhap_hang (ma_phieu, ngay_tao, ten_ncc, tong_tien, chi_tiet, ghi_chu)
                                     VALUES (%s, %s, %s, %s, %s, %s)""",
                                  (ma_phieu_nhap, ngay_nhap_str, ten_ncc_luu, tong_tien, chi_tiet_json, ghi_chu))
                        conn.commit()
                        don_dep_lich_su_don_nhap() # Giữ 10 đơn gần nhất
                        
                        pdf_nhap = generate_phieu_nhap_pdf(ma_phieu_nhap, ten_ncc_luu, df_luu, tong_tien, ghi_chu, ngay_nhap_str)
                        st.session_state['pdf_phieu_nhap'] = pdf_nhap
                        
                        ten_file_ncc = ten_ncc_luu if ten_ncc_luu else "ChuaXacDinh"
                        st.session_state['ten_phieu_nhap'] = f"{ma_phieu_nhap}_{ten_file_ncc}.pdf"
                        
                        img_nhap = convert_pdf_to_png(pdf_nhap)
                        if img_nhap:
                            st.session_state['img_phieu_nhap'] = img_nhap
                            
                        st.session_state.gio_nhap_kho = []
                        st.success("✅ Đã tạo đơn nháp thành công! Hãy tải file bên dưới.")
                
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
            
        # ------------------------------------------
        # BẢNG 10 ĐƠN NHẬP HÀNG ĐÃ TẠO
        # ------------------------------------------
        st.markdown("---")
        st.markdown("#### 📋 Danh sách 10 Đơn Nhập Hàng gần nhất (Chưa ghi nhận công nợ)")
        try:
            df_don_nhap = pd.read_sql("SELECT id, ma_phieu, ngay_tao, ten_ncc, tong_tien, ghi_chu FROM public.ls_don_nhap_hang ORDER BY id DESC LIMIT 10", conn)
            if not df_don_nhap.empty:
                df_don_nhap.insert(0, "Xóa Đơn", False)
                df_don_nhap.columns = ["Xóa Đơn", "ID", "Mã Phiếu", "Ngày Tạo", "Nhà Cung Cấp", "Tổng Tiền (VNĐ)", "Ghi Chú"]
                
                edited_don = st.data_editor(
                    df_don_nhap,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Xóa Đơn": st.column_config.CheckboxColumn("🗑️ Chọn Xóa", default=False),
                        "ID": None,
                        "Mã Phiếu": st.column_config.TextColumn(disabled=True),
                        "Ngày Tạo": st.column_config.TextColumn(disabled=True),
                        "Nhà Cung Cấp": st.column_config.TextColumn(disabled=True),
                        "Tổng Tiền (VNĐ)": st.column_config.NumberColumn("Tổng Tiền (VNĐ)", disabled=True, format="%.0f"),
                        "Ghi Chú": st.column_config.TextColumn(disabled=True)
                    },
                    key="editor_don_nhap"
                )
                
                selected_don = edited_don[edited_don["Xóa Đơn"] == True]
                if not selected_don.empty:
                    if st.button("🚨 XÓA CÁC ĐƠN ĐÃ CHỌN", type="primary"):
                        ids_to_delete = selected_don["ID"].tolist()
                        if len(ids_to_delete) == 1:
                            c.execute("DELETE FROM public.ls_don_nhap_hang WHERE id = %s", (ids_to_delete[0],))
                        else:
                            c.execute(f"DELETE FROM public.ls_don_nhap_hang WHERE id IN {tuple(ids_to_delete)}")
                        conn.commit()
                        st.success("✅ Đã xóa đơn khỏi lịch sử thành công!")
                        time.sleep(1.5); st.rerun()
            else:
                st.info("Chưa có đơn nhập hàng nào được tạo.")
        except Exception as e:
            st.error(f"Lỗi hiển thị bảng đơn nhập: {e}")

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
                
                # Hai nút chọn loại hóa đơn
                col_hd1, col_hd2 = st.columns(2)
                with col_hd1:
                    co_xuat_hoa_don = st.checkbox("✅ Có xuất hóa đơn (Chia 0.95)", value=False)
                with col_hd2:
                    co_xuat_hoa_don_nguyen = st.checkbox("✅ Có xuất hóa đơn (Giữ nguyên giá)", value=False)
                
                # Mặc định chọn "Chưa thanh toán" (index=0) cho mọi đơn xuất kho
                trang_thai_tt_xuat = st.selectbox(
                    "Trạng thái thanh toán Đơn hàng", 
                    ["Chưa thanh toán", "Đã thanh toán"], 
                    index=0 if la_dai_ly else 1
                )
                
                items = json.loads(don_info['chi_tiet'])
                df_items = pd.DataFrame(items)
                
                # Xử lý để hiển thị đúng Số Lượng Lốc, Số Lượng Cái và cập nhật tiền nếu có xuất hóa đơn
                sl_loc_list = []
                sl_cai_list = []
                don_gia_list = []
                thanh_tien_list = []
                
                for _, row in df_items.iterrows():
                    ten_sp = row.get('Tên Sản Phẩm', row.get('Tên Sản Phẩm OME', ''))
                    # Số lượng trong JSON gốc chính là Tổng Số Cái
                    sl_cai = float(row.get('Số Lượng', 0))
                    sl_cai_list.append(sl_cai)
                    
                    quy_cach = 1.0
                    try:
                        c.execute("SELECT quy_cach_loc FROM public.dm_san_pham WHERE ten_sp = %s", (ten_sp,))
                        res = c.fetchone()
                        if res: quy_cach = float(res[0])
                        else:
                            c.execute("SELECT quy_cach_loc FROM public.dm_san_pham_ome WHERE ten_sp = %s", (ten_sp,))
                            res2 = c.fetchone()
                            if res2: quy_cach = float(res2[0])
                    except: pass
                    
                    # Số lốc = Số cái / Quy cách
                    sl_loc = sl_cai / quy_cach if quy_cach > 0 else 0
                    sl_loc_list.append(sl_loc)
                    
                    # CẬP NHẬT: Lấy đơn giá đảm bảo quét trúng giá hàng OME nếu có
                    val_gia = row.get('Đơn Giá OME', row.get('Đơn Giá', row.get('Giá', 0)))
                    don_gia_goc = float(val_gia) if pd.notna(val_gia) and val_gia != "" else 0.0
                    
                    # Áp dụng logic hiển thị bảng
                    if co_xuat_hoa_don and not co_xuat_hoa_don_nguyen:
                        don_gia_moi = round(don_gia_goc / 0.95)
                    elif co_xuat_hoa_don_nguyen and not co_xuat_hoa_don:
                        don_gia_moi = don_gia_goc
                    else:
                        don_gia_moi = don_gia_goc
                        
                    don_gia_list.append(don_gia_moi)
                    thanh_tien_list.append(don_gia_moi * sl_cai)
                
                df_items['Số Lượng Lốc'] = sl_loc_list
                df_items['Số Lượng Cái'] = sl_cai_list
                if 'Đơn Giá' in df_items.columns:
                    df_items['Đơn Giá'] = don_gia_list
                if 'Giá' in df_items.columns:
                    df_items['Giá'] = don_gia_list
                if 'Đơn Giá OME' in df_items.columns:
                    df_items['Đơn Giá OME'] = don_gia_list
                df_items['Thành Tiền'] = thanh_tien_list
                
                # Bổ sung cột "Số Bao" cho phép người dùng nhập trực tiếp trên giao diện
                df_items.insert(len(df_items.columns), "Số Bao", "")
                
                st.write("Bảng chi tiết hàng hóa (Bạn có thể nhập thêm Số Bao ở cột cuối cùng):")
                
                # Ẩn cột "Số Lượng" cũ đi cho đỡ rối, dùng 2 cột mới tính
                df_display = df_items.drop(columns=['Số Lượng'], errors='ignore')
                
                edited_df_items = st.data_editor(
                    df_display, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Tên Sản Phẩm": st.column_config.TextColumn(disabled=True),
                        "Tên Sản Phẩm OME": st.column_config.TextColumn(disabled=True),
                        "Số Lượng Lốc": st.column_config.NumberColumn("Số Lượng (Lốc)", disabled=True, format="%.2f"),
                        "Số Lượng Cái": st.column_config.NumberColumn("Số Lượng (Cái)", disabled=True, format="%.0f"),
                        "Đơn Giá": st.column_config.NumberColumn(disabled=True, format="%.0f"),
                        "Đơn Giá OME": st.column_config.NumberColumn(disabled=True, format="%.0f"),
                        "Giá": st.column_config.NumberColumn(disabled=True, format="%.0f"),
                        "Thành Tiền": st.column_config.NumberColumn(disabled=True, format="%.0f"),
                        "Ghi Chú": st.column_config.TextColumn(disabled=True),
                        "Số Bao": st.column_config.TextColumn("Số Bao (Nhập tay)")
                    }
                )
                
                c_btn1, c_btn2, c_btn3 = st.columns([2, 2, 2])
                
                if don_info['trang_thai'] in ['Chờ xuất kho', 'Mới tạo']:
                    with c_btn1:
                        if st.button("📦 XÁC NHẬN XUẤT KHO", type="primary", use_container_width=True):
                            if co_xuat_hoa_don and co_xuat_hoa_don_nguyen:
                                st.error("⚠️ Vui lòng chỉ tích chọn 1 loại xuất hóa đơn!")
                            else:
                                for item in items:
                                    ten_sp = item.get('Tên Sản Phẩm', item.get('Tên Sản Phẩm OME'))
                                    sl = float(item.get('Số Lượng', 0)) # Đây là số lượng cái cần trừ kho
                                    
                                    # CẬP NHẬT: Lấy đơn giá quét trúng giá hàng OME
                                    val_gia_sp = item.get('Đơn Giá OME', item.get('Đơn Giá', item.get('Giá', 0)))
                                    don_gia_sp = float(val_gia_sp) if val_gia_sp != "" else 0.0
                                    
                                    ghi_chu_hd = ""
                                    if co_xuat_hoa_don:
                                        don_gia_sp = round(don_gia_sp / 0.95)
                                        ghi_chu_hd = " (Hóa đơn chia 0.95)"
                                    elif co_xuat_hoa_don_nguyen:
                                        ghi_chu_hd = " (Hóa đơn nguyên giá)"
                                        
                                    thanh_tien_sp = sl * don_gia_sp
                                    # Phân loại Doanh Thu hay Công Nợ ngay lúc lưu
                                    tien_da_thu_sp = thanh_tien_sp if trang_thai_tt_xuat == "Đã thanh toán" else 0
                                    
                                    c.execute("UPDATE public.dm_san_pham SET ton_kho = ton_kho - %s WHERE ten_sp = %s", (sl, ten_sp))
                                    c.execute("UPDATE public.dm_san_pham_ome SET ton_kho = ton_kho - %s WHERE ten_sp = %s", (sl, ten_sp))
                                    
                                    c.execute("""INSERT INTO public.ls_nhap_xuat_kho 
                                                 (ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, don_gia, thanh_tien, tien_da_thu, ghi_chu, khach_hang, trang_thai_tt) 
                                                 VALUES (%s, 'Xuất Bán', %s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
                                              (lay_gio_vn().strftime("%d/%m/%Y %H:%M"), ten_sp, -sl, don_gia_sp, thanh_tien_sp, tien_da_thu_sp, f"Đơn {ma_don_chon}{ghi_chu_hd}", ten_khach_hang_hien_tai, trang_thai_tt_xuat))
                                    
                                c.execute("UPDATE public.don_hang SET trang_thai = 'Đã xuất kho' WHERE ma_don = %s", (ma_don_chon,))
                                conn.commit(); st.success("Đã xuất kho và lưu số liệu thành công!"); time.sleep(1.5); st.rerun()
                    
                    with c_btn2:
                        if st.button("❌ HỦY ĐƠN NÀY", use_container_width=True):
                            c.execute("UPDATE public.don_hang SET trang_thai = 'Đã hủy' WHERE ma_don = %s", (ma_don_chon,))
                            conn.commit(); st.warning("Đã hủy đơn."); time.sleep(1); st.rerun()

                elif don_info['trang_thai'] == 'Đã xuất kho':
                    st.markdown("**📁 Tùy chọn in Phiếu Xuất Kho:**")
                    loai_xuat_xk = st.radio(
                        "Định dạng xuất Phiếu Xuất:", 
                        ["Chỉ xuất file PDF", "Chỉ xuất file Ảnh (PNG)", "Xuất cả PDF và Ảnh"], 
                        horizontal=True, 
                        index=1,
                        key=f"radio_xk_{ma_don_chon}"
                    )
                    
                    c_dl1, c_dl2, c_btn_thu = st.columns([1, 1, 1])
                    
                    pdf_bytes = generate_phieu_xuat_pdf(edited_df_items, ma_don_chon, don_info['ten_kh'], conn)
                    img_bytes = convert_pdf_to_png(pdf_bytes)

                    if "PDF" in loai_xuat_xk or "Cả" in loai_xuat_xk:
                        with c_dl1:
                            st.download_button("🖨️ TẢI PHIẾU (PDF)", pdf_bytes, f"PhieuXuat_{ma_don_chon}.pdf", "application/pdf", use_container_width=True)
                    if ("Ảnh" in loai_xuat_xk or "Cả" in loai_xuat_xk) and img_bytes:
                        with c_dl2:
                            st.download_button("🖼️ TẢI PHIẾU (ẢNH)", img_bytes, f"PhieuXuat_{ma_don_chon}.png", "image/png", use_container_width=True)
                    
                    with c_btn_thu:
                        if st.button("🔄 THU HỒI ĐƠN (Trả hàng)", use_container_width=True):
                            for item in items:
                                ten_sp = item.get('Tên Sản Phẩm', item.get('Tên Sản Phẩm OME'))
                                sl = float(item.get('Số Lượng', 0))
                                c.execute("UPDATE public.dm_san_pham SET ton_kho = ton_kho + %s WHERE ten_sp = %s", (sl, ten_sp))
                                c.execute("UPDATE public.dm_san_pham_ome SET ton_kho = ton_kho + %s WHERE ten_sp = %s", (sl, ten_sp))
                                c.execute("INSERT INTO public.ls_nhap_xuat_kho (ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, ghi_chu, khach_hang) VALUES (%s, 'Thu hồi đơn', %s, %s, %s, %s)", (lay_gio_vn().strftime("%d/%m/%Y %H:%M"), ten_sp, sl, f"Thu hồi đơn {ma_don_chon}", don_info['ten_kh']))
                            
                            # Xóa khoản công nợ/doanh thu ứng với mã đơn này khỏi bảng ls_nhap_xuat_kho
                            c.execute("DELETE FROM public.ls_nhap_xuat_kho WHERE (ghi_chu = %s OR ghi_chu LIKE %s) AND loai_thao_tac = 'Xuất Bán'", (f"Đơn {ma_don_chon}", f"Đơn {ma_don_chon} (%"))

                            c.execute("UPDATE public.don_hang SET trang_thai = 'Đã thu hồi' WHERE ma_don = %s", (ma_don_chon,))
                            conn.commit(); st.info("Đã thu hồi hàng về kho và xóa công nợ/doanh thu gốc."); time.sleep(1.5); st.rerun()
                else:
                    st.info(f"Đơn hàng này đang ở trạng thái: **{don_info['trang_thai']}**")

            else: st.info("Chưa có đơn hàng nào.")
            
            # --- BẢNG THEO DÕI XUẤT KHO VÀ THU HỒI ---
            st.markdown("---")
            st.markdown("#### 📋 Bảng Danh Sách Phiếu Xuất Kho & Thu Hồi")
            try:
                df_ls_xuat = pd.read_sql("""
                    SELECT 
                        MAX(ngay_thao_tac) as "Ngày Thao Tác", 
                        ghi_chu as "Số Phiếu (Ghi chú)", 
                        MAX(khach_hang) as "Khách Hàng", 
                        loai_thao_tac as "Trạng Thái (Loại)", 
                        MAX(trang_thai_tt) as "Thanh Toán",
                        SUM(thanh_tien) as "Tổng Tiền (VNĐ)",
                        SUM(tien_da_thu) as "Doanh Thu (Đã thu)",
                        SUM(thanh_tien - COALESCE(tien_da_thu, 0)) as "Công Nợ (Chưa thu)"
                    FROM public.ls_nhap_xuat_kho
                    WHERE loai_thao_tac IN ('Xuất Bán', 'Thu hồi đơn')
                    GROUP BY ghi_chu, loai_thao_tac
                    ORDER BY MAX(id) DESC
                    LIMIT 100
                """, conn)
                
                if not df_ls_xuat.empty:
                    df_ls_xuat['Thanh Toán'] = df_ls_xuat['Thanh Toán'].fillna('---')
                    df_ls_xuat['Khách Hàng'] = df_ls_xuat['Khách Hàng'].fillna('---')
                    df_ls_xuat['Tổng Tiền (VNĐ)'] = df_ls_xuat['Tổng Tiền (VNĐ)'].apply(lambda x: format_vn(x) if pd.notnull(x) else "0")
                    df_ls_xuat['Doanh Thu (Đã thu)'] = df_ls_xuat['Doanh Thu (Đã thu)'].apply(lambda x: format_vn(x) if pd.notnull(x) else "0")
                    df_ls_xuat['Công Nợ (Chưa thu)'] = df_ls_xuat['Công Nợ (Chưa thu)'].apply(lambda x: format_vn(x) if pd.notnull(x) else "0")
                    
                    st.dataframe(df_ls_xuat, use_container_width=True, hide_index=True)
                else:
                    st.info("Chưa có dữ liệu xuất kho hoặc thu hồi nào được ghi nhận.")
            except Exception as e:
                st.error(f"Lỗi hiển thị bảng lịch sử xuất kho: {e}")
                
        except Exception as e: st.error(str(e))
    
    elif "4. Chuyển đơn" in chuyem_muc:
        st.markdown("#### 🔄 Chuyển Đơn Hàng Cho Đại Lý Bán Thay (Dropship)")
        st.info("Nghiệp vụ này **KHÔNG** ghi nhận xuất kho thực tế. Hệ thống sẽ tự động tính toán khoản lời / chênh lệch và đẩy thẳng vào Công nợ của Đại lý được chọn.")
        
        try:
            # Lấy danh sách đơn hàng chờ xuất
            df_dh = pd.read_sql("SELECT id, ma_don, ten_kh, ngay_tao, trang_thai, chi_tiet FROM public.don_hang WHERE trang_thai IN ('Chờ xuất kho', 'Mới tạo') ORDER BY id DESC", conn)
            
            # Lấy danh sách đại lý/khách hàng hiện có trong lịch sử công nợ
            df_kh = pd.read_sql("SELECT DISTINCT khach_hang FROM public.ls_nhap_xuat_kho WHERE khach_hang IS NOT NULL AND khach_hang != ''", conn)
            ds_dai_ly = df_kh['khach_hang'].tolist() if not df_kh.empty else []

            if not df_dh.empty:
                options = [f"[{row['trang_thai']}] {row['ma_don']} - Khách mua: {row['ten_kh']}" for _, row in df_dh.iterrows()]
                
                don_chon_str = st.selectbox("📌 Chọn Đơn Hàng Cần Chuyển", options)
                ma_don_chon = don_chon_str.split("] ")[1].split(" - ")[0]
                don_info = df_dh[df_dh['ma_don'] == ma_don_chon].iloc[0]
                items = json.loads(don_info['chi_tiet'])
                
                st.markdown("---")
                # Chọn đại lý nhận đơn
                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    dai_ly_nhan = st.selectbox("🏢 Chọn Đại Lý chịu trách nhiệm giao đơn này:", ["-- Chọn Đại Lý --"] + ds_dai_ly)
                with col_dl2:
                    dai_ly_moi = st.text_input("Hoặc nhập tên Đại lý mới (nếu chưa có trong danh sách):")
                
                ten_dai_ly_chot = dai_ly_moi.strip() if dai_ly_moi.strip() else dai_ly_nhan
                
                st.write("**Chi tiết hàng hóa trong đơn gốc:**")
                df_items = pd.DataFrame(items)
                cols_to_show = [c for c in ['Tên Sản Phẩm', 'Tên Sản Phẩm OME', 'Số Lượng', 'Đơn Giá', 'Đơn Giá OME', 'Thành Tiền', 'Thành Tiền OME'] if c in df_items.columns]
                st.dataframe(df_items[cols_to_show], use_container_width=True, hide_index=True)

                if st.button("🚀 XÁC NHẬN CHUYỂN ĐƠN & GHI CÔNG NỢ", type="primary", use_container_width=True):
                    if ten_dai_ly_chot == "-- Chọn Đại Lý --" or not ten_dai_ly_chot:
                        st.error("⚠️ Vui lòng chọn hoặc nhập tên Đại lý nhận chuyển đơn!")
                    else:
                        with st.spinner("⏳ Đang xử lý bóc tách và tính toán công nợ..."):
                            tong_tien_don = 0
                            tong_tien_gia_dl = 0
                            
                            for item in items:
                                ten_sp = item.get('Tên Sản Phẩm', item.get('Tên Sản Phẩm OME', ''))
                                sl = float(item.get('Số Lượng', 0))
                                
                                # CẬP NHẬT: Lấy thành tiền quét trúng giá hàng OME
                                val_thanh_tien = item.get('Thành Tiền OME', item.get('Thành Tiền', 0))
                                thanh_tien_sp = float(val_thanh_tien) if val_thanh_tien != "" else 0.0
                                tong_tien_don += thanh_tien_sp
                                
                                # Tra cứu giá đại lý từ database
                                gia_dl_sp = 0
                                try:
                                    # Thử tìm trong bảng sản phẩm chuẩn
                                    c.execute("SELECT gia_dai_ly FROM public.dm_san_pham WHERE ten_sp = %s", (ten_sp,))
                                    res = c.fetchone()
                                    if res and res[0]: 
                                        gia_dl_sp = float(res[0])
                                    else:
                                        # Thử tìm trong bảng OME
                                        c.execute("SELECT gia_dai_ly FROM public.dm_san_pham_ome WHERE ten_sp = %s", (ten_sp,))
                                        res2 = c.fetchone()
                                        if res2 and res2[0]: 
                                            gia_dl_sp = float(res2[0])
                                except Exception:
                                    pass 
                                    
                                tong_tien_gia_dl += (gia_dl_sp * sl)
                                
                            # CÔNG THỨC: Tiền đơn - (20% Tiền đơn + Tổng tiền theo giá đại lý)
                            so_tien_ghi_no = tong_tien_don - ((tong_tien_don * 0.2) + tong_tien_gia_dl)
                            ngay_thao_tac = lay_gio_vn().strftime("%d/%m/%Y %H:%M")
                            
                            # 1. Ghi nhận vào công nợ chung
                            ghi_chu_chuyen = f"Chuyển đơn {ma_don_chon} (Tiền đơn: {format_vn(tong_tien_don)} | Trừ 20%: {format_vn(tong_tien_don*0.2)} | Tiền vốn ĐL: {format_vn(tong_tien_gia_dl)})"
                            c.execute("""INSERT INTO public.ls_nhap_xuat_kho 
                                         (ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, don_gia, thanh_tien, ghi_chu, khach_hang, trang_thai_tt) 
                                         VALUES (%s, 'Xuất Bán', %s, %s, %s, %s, %s, %s, %s)""", 
                                      (ngay_thao_tac, f"Chuyển giao đơn {ma_don_chon}", 1, so_tien_ghi_no, so_tien_ghi_no, ghi_chu_chuyen, ten_dai_ly_chot, 'Chưa thanh toán'))
                            
                            # 2. Ghi nhận vào bảng riêng quản lý lịch sử chuyển đơn
                            c.execute("""INSERT INTO public.ls_chuyen_don (ngay_chuyen, ma_don, dai_ly_nhan, tong_tien_don, so_tien_ghi_no) 
                                         VALUES (%s, %s, %s, %s, %s)""", 
                                      (ngay_thao_tac, ma_don_chon, ten_dai_ly_chot, tong_tien_don, so_tien_ghi_no))
                            
                            # Đánh dấu trạng thái đơn hàng để không hiện lại ở mục Chờ xuất kho nữa
                            c.execute("UPDATE public.don_hang SET trang_thai = 'Đã chuyển đại lý' WHERE ma_don = %s", (ma_don_chon,))
                            
                            conn.commit()
                            don_dep_lich_su_chuyen_don() # Chỉ giữ 50 đơn gần nhất
                            
                            st.success(f"✅ Đã chuyển đơn thành công cho đại lý {ten_dai_ly_chot}!")
                            st.success(f"💰 Đã tính và cộng khoản công nợ: {format_vn(so_tien_ghi_no)} VNĐ vào tài khoản đại lý.")
                            time.sleep(3)
                            st.rerun()
            else:
                st.info("🎉 Hiện tại không có đơn hàng nào đang chờ xử lý.")
        except Exception as e:
            st.error(f"Lỗi truy xuất dữ liệu: {e}")

    elif "1. Nhập NVL, NCC" in chuyem_muc:
        st.markdown("#### 📥 Nhập Nguyên Vật Liệu từ Nhà Cung Cấp")
        try:
            df_nl_ton = pd.read_sql("SELECT ten_nl, don_vi FROM public.dm_nguyen_lieu", conn)
            try: df_ncc = pd.read_sql("SELECT ten_ncc FROM public.dm_ncc", conn)
            except: df_ncc = pd.DataFrame()
            danh_sach_ncc = df_ncc['ten_ncc'].tolist() if not df_ncc.empty else ["-- Chưa có Nhà Cung Cấp --"]

            if not df_nl_ton.empty:
                with st.form("form_nhap_nvl", clear_on_submit=True):
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
                            don_dep_lich_su_nhap_nvl()
                            st.success(f"✅ Đã ghi nhận lô hàng từ {ncc_chon} vào Lịch sử & Công nợ!")
                            time.sleep(2); st.rerun()
                
                # --- BẢNG DANH SÁCH 100 ĐƠN NHẬP GẦN NHẤT ---
                st.markdown("---")
                st.markdown("#### 📋 Danh sách 100 Lần Nhập NVL, NCC Gần Nhất")
                try:
                    df_ls_nhap = pd.read_sql("SELECT id, ngay_thao_tac, nha_cung_cap, ten_nl, so_luong, don_gia, thanh_tien, trang_thai_tt, ghi_chu FROM public.ls_nhap_xuat_kho WHERE loai_thao_tac='Nhập NVL' ORDER BY id DESC LIMIT 100", conn)
                    if not df_ls_nhap.empty:
                        df_ls_nhap.insert(0, "Xóa Phiếu", False)
                        df_ls_nhap.columns = ["Xóa Phiếu", "ID", "Ngày Nhập", "Nhà Cung Cấp", "Vật Tư", "Số Lượng", "Đơn Giá (VNĐ)", "Thành Tiền (VNĐ)", "Trạng Thái", "Ghi Chú"]
                        
                        edited_nhap = st.data_editor(
                            df_ls_nhap,
                            hide_index=True,
                            use_container_width=True,
                            column_config={
                                "Xóa Phiếu": st.column_config.CheckboxColumn("🗑️ Chọn Xóa", default=False),
                                "ID": None,
                                "Ngày Nhập": st.column_config.TextColumn(disabled=True),
                                "Nhà Cung Cấp": st.column_config.TextColumn(disabled=True),
                                "Vật Tư": st.column_config.TextColumn(disabled=True),
                                "Số Lượng": st.column_config.NumberColumn(disabled=True),
                                "Đơn Giá (VNĐ)": st.column_config.NumberColumn("Đơn Giá (VNĐ)", disabled=True, format="%.0f"),
                                "Thành Tiền (VNĐ)": st.column_config.NumberColumn("Thành Tiền (VNĐ)", disabled=True, format="%.0f"),
                                "Trạng Thái": st.column_config.TextColumn(disabled=True),
                                "Ghi Chú": st.column_config.TextColumn(disabled=True)
                            },
                            key="editor_ls_nhap_nvl"
                        )
                        
                        selected_nhap = edited_nhap[edited_nhap["Xóa Phiếu"] == True]
                        if not selected_nhap.empty:
                            if st.button("🚨 XÓA CÁC PHIẾU ĐÃ CHỌN", type="primary"):
                                ids_to_delete = selected_nhap["ID"].tolist()
                                if len(ids_to_delete) == 1:
                                    c.execute("DELETE FROM public.ls_nhap_xuat_kho WHERE id = %s", (ids_to_delete[0],))
                                else:
                                    c.execute(f"DELETE FROM public.ls_nhap_xuat_kho WHERE id IN {tuple(ids_to_delete)}")
                                conn.commit()
                                st.success("✅ Đã xóa phiếu nhập thành công! Hệ thống đã tự động gỡ khoản này khỏi Công nợ và Chi phí.")
                                time.sleep(1.5); st.rerun()
                    else:
                        st.info("Chưa có đơn nhập nguyên vật liệu nào được ghi nhận.")
                except Exception as e:
                    st.error(f"Lỗi hiển thị bảng lịch sử: {e}")

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
                        don_dep_lich_su_nhap_tp()
                        st.success(f"✅ Đã nhập {sl_nhap} {don_vi_nhap} {sp_chon} vào kho!")
                        time.sleep(2); st.rerun()
                
                # --- BẢNG DANH SÁCH 100 LẦN NHẬP THÀNH PHẨM ---
                st.markdown("---")
                st.markdown("#### 📋 Danh sách 100 Lần Nhập Thành Phẩm Gần Nhất")
                
                df_ls_nhap_tp = pd.read_sql("SELECT id, ngay_thao_tac, ten_nl, so_luong, ghi_chu FROM public.ls_nhap_xuat_kho WHERE loai_thao_tac='Nhập Thành Phẩm' ORDER BY id DESC LIMIT 100", conn)
                if not df_ls_nhap_tp.empty:
                    df_ls_nhap_tp.insert(0, "Xóa Phiếu", False)
                    df_ls_nhap_tp.columns = ["Xóa Phiếu", "ID", "Ngày Nhập", "Tên Sản Phẩm", "Số Lượng (Bộ/Thành phẩm)", "Ghi Chú (Đơn vị)"]

                    edited_nhap_tp = st.data_editor(
                        df_ls_nhap_tp,
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "Xóa Phiếu": st.column_config.CheckboxColumn("🗑️ Chọn Xóa", default=False),
                            "ID": None,
                            "Ngày Nhập": st.column_config.TextColumn(disabled=True),
                            "Tên Sản Phẩm": st.column_config.TextColumn(disabled=True),
                            "Số Lượng (Bộ/Thành phẩm)": st.column_config.NumberColumn("Số Lượng (Sửa được)", format="%.0f"),
                            "Ghi Chú (Đơn vị)": st.column_config.TextColumn("Ghi Chú / Đơn Vị (Sửa được)")
                        },
                        key="editor_ls_nhap_tp"
                    )

                    # Xử lý Cập nhật (Sửa số lượng / Ghi chú)
                    diff_mask_tp = (edited_nhap_tp['Số Lượng (Bộ/Thành phẩm)'] != df_ls_nhap_tp['Số Lượng (Bộ/Thành phẩm)']) | \
                                   (edited_nhap_tp['Ghi Chú (Đơn vị)'] != df_ls_nhap_tp['Ghi Chú (Đơn vị)'])
                    
                    if diff_mask_tp.any():
                        st.warning("⚠️ Bạn vừa sửa dữ liệu nhập kho. Vui lòng bấm LƯU để tự động tính và cập nhật bù lại vào Tồn kho.")
                        if st.button("💾 LƯU THAY ĐỔI PHIẾU NHẬP", type="primary"):
                            for _, row in edited_nhap_tp[diff_mask_tp].iterrows():
                                id_phieu = row['ID']
                                old_qty = df_ls_nhap_tp[df_ls_nhap_tp['ID'] == id_phieu]['Số Lượng (Bộ/Thành phẩm)'].iloc[0]
                                new_qty = row['Số Lượng (Bộ/Thành phẩm)']
                                new_note = row['Ghi Chú (Đơn vị)']
                                sp_name = row['Tên Sản Phẩm']
                                
                                qty_diff = new_qty - old_qty
                                
                                # Cập nhật tồn kho (Cộng thêm hoặc trừ bớt phần chênh lệch)
                                if qty_diff != 0:
                                    c.execute("UPDATE public.dm_san_pham SET ton_kho = ton_kho + %s WHERE ten_sp = %s", (qty_diff, sp_name))
                                    c.execute("UPDATE public.dm_san_pham_ome SET ton_kho = ton_kho + %s WHERE ten_sp = %s", (qty_diff, sp_name))
                                
                                # Cập nhật lịch sử
                                c.execute("UPDATE public.ls_nhap_xuat_kho SET so_luong = %s, ghi_chu = %s WHERE id = %s", (new_qty, new_note, id_phieu))
                                
                            conn.commit()
                            st.success("✅ Đã tính toán và cập nhật lại Báo cáo tồn kho thành phẩm!")
                            time.sleep(1.5); st.rerun()

                    # Xử lý Xóa Phiếu
                    selected_nhap_tp = edited_nhap_tp[edited_nhap_tp["Xóa Phiếu"] == True]
                    if not selected_nhap_tp.empty:
                        if st.button("🚨 XÓA CÁC PHIẾU ĐÃ CHỌN & THU HỒI TỒN KHO", type="primary"):
                            for _, row in selected_nhap_tp.iterrows():
                                id_phieu = row['ID']
                                qty_to_revert = row['Số Lượng (Bộ/Thành phẩm)']
                                sp_name = row['Tên Sản Phẩm']
                                
                                # Trừ lại tồn kho vì thao tác này là xóa phiếu đã nhập
                                c.execute("UPDATE public.dm_san_pham SET ton_kho = ton_kho - %s WHERE ten_sp = %s", (qty_to_revert, sp_name))
                                c.execute("UPDATE public.dm_san_pham_ome SET ton_kho = ton_kho - %s WHERE ten_sp = %s", (qty_to_revert, sp_name))
                                
                                # Xóa phiếu khỏi lịch sử
                                c.execute("DELETE FROM public.ls_nhap_xuat_kho WHERE id = %s", (id_phieu,))
                                
                            conn.commit()
                            st.success("✅ Đã xóa phiếu! Hệ thống đã tự động gỡ sản lượng này khỏi Báo cáo tồn kho.")
                            time.sleep(1.5); st.rerun()
                else:
                    st.info("Chưa có phiếu nhập thành phẩm nào được ghi nhận.")

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

# ------------------------------------------
# TAB 5: QUẢN LÝ ĐƠN ĐÃ CHUYỂN
# ------------------------------------------
with tab5:
    st.subheader("🔄 Quản Lý Đơn Đã Chuyển Đại Lý")
    st.markdown("Theo dõi danh sách các đơn hàng Dropship và hủy chuyển đơn (xóa) nếu thao tác sai.")
    
    try:
        df_ls_chuyen = pd.read_sql("SELECT id, ngay_chuyen, ma_don, dai_ly_nhan, tong_tien_don, so_tien_ghi_no FROM public.ls_chuyen_don ORDER BY id DESC", conn)
        
        if not df_ls_chuyen.empty:
            df_hien_thi = df_ls_chuyen.copy()
            df_hien_thi.columns = ["ID", "Ngày Chuyển", "Mã Đơn", "Đại Lý Nhận", "Tổng Tiền Đơn (VNĐ)", "Đại Lý Nợ (VNĐ)"]
            
            # Format tiền tệ để hiển thị đẹp hơn
            df_hien_thi['Tổng Tiền Đơn (VNĐ)'] = df_hien_thi['Tổng Tiền Đơn (VNĐ)'].apply(lambda x: format_vn(x))
            df_hien_thi['Đại Lý Nợ (VNĐ)'] = df_hien_thi['Đại Lý Nợ (VNĐ)'].apply(lambda x: format_vn(x))
            
            st.dataframe(df_hien_thi.drop(columns=["ID"]), use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.markdown("#### 🗑️ Hủy Chuyển Đơn (Xóa Giao Dịch)")
            st.warning("⚠️ Nếu bạn xóa đơn chuyển tại đây, hệ thống sẽ tự động rút khoản công nợ khỏi đại lý và đưa trạng thái đơn hàng quay về 'Chờ xuất kho'.")
            
            options_del = ["-- Chọn mã đơn cần xóa --"] + df_ls_chuyen['ma_don'].tolist()
            chon_don_xoa = st.selectbox("Chọn Mã Đơn:", options_del)
            
            if chon_don_xoa != "-- Chọn mã đơn cần xóa --":
                if st.button(f"🚨 Xác Nhận Hủy Chuyển Đơn {chon_don_xoa}", type="primary"):
                    with st.spinner("⏳ Đang hoàn tác giao dịch chuyển đơn..."):
                        # 1. Tìm thông tin của giao dịch đó để xóa bên bảng công nợ chung (ls_nhap_xuat_kho)
                        c.execute("DELETE FROM public.ls_nhap_xuat_kho WHERE ghi_chu LIKE %s AND loai_thao_tac = 'Xuất Bán'", (f"%Chuyển đơn {chon_don_xoa}%",))
                        
                        # 2. Xóa khỏi bảng ls_chuyen_don
                        c.execute("DELETE FROM public.ls_chuyen_don WHERE ma_don = %s", (chon_don_xoa,))
                        
                        # 3. Trả lại trạng thái đơn hàng
                        c.execute("UPDATE public.don_hang SET trang_thai = 'Chờ xuất kho' WHERE ma_don = %s", (chon_don_xoa,))
                        
                        conn.commit()
                        st.success(f"✅ Đã hủy chuyển đơn {chon_don_xoa} thành công. Công nợ đã được hoàn tác.")
                        time.sleep(2)
                        st.rerun()
        else:
            st.info("Chưa có đơn hàng nào được chuyển cho đại lý.")
    except Exception as e:
        st.error(f"Lỗi: {e}")
