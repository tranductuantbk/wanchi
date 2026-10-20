import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
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

# ==========================================
# CẤU HÌNH GIAO DIỆN & BẢO MẬT
# ==========================================
st.set_page_config(page_title="Quản Lý Quỹ Thu Chi", page_icon="💰", layout="wide")

role = check_password()
if not role: st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang Quản Lý Quỹ chỉ dành cho Quản lý.")
    st.stop()

st.header("💰 Quản Lý Quỹ Thu Chi WANCHI")

conn = get_connection()
c = conn.cursor()

# ==========================================
# KHỞI TẠO BẢNG DỮ LIỆU & HÀM DỌN DẸP
# ==========================================
try:
    c.execute("CREATE SCHEMA IF NOT EXISTS public;")
    c.execute('''CREATE TABLE IF NOT EXISTS public.quy_thu_chi (
                    id SERIAL PRIMARY KEY, 
                    ma_phieu TEXT, 
                    loai_gd TEXT, 
                    ngay_gd TEXT, 
                    so_tien REAL, 
                    noi_dung TEXT, 
                    co_hoa_don TEXT
                )''')
    conn.commit()
except: 
    conn.rollback()

def don_dep_lich_su_quy():
    """Tự động xóa dữ liệu cũ, chỉ giữ lại 100 phiếu gần nhất"""
    try:
        c.execute("""DELETE FROM public.quy_thu_chi 
                     WHERE id NOT IN (
                         SELECT id FROM public.quy_thu_chi 
                         ORDER BY id DESC LIMIT 100
                     )""")
        conn.commit()
    except: 
        conn.rollback()

def format_vn(value):
    try: return "{:,.0f}".format(value).replace(",", ".")
    except: return str(value)

# ==========================================
# HÀM XUẤT PHIẾU PDF (THU / CHI)
# ==========================================
def generate_phieu_pdf(ma_phieu, loai_gd, ngay_gd, so_tien, noi_dung, co_hoa_don):
    pdf = FPDF()
    pdf.add_page()
    has_font = os.path.exists(FONT_FILE)
    if has_font:
        pdf.add_font("Roboto", "", FONT_FILE, uni=True)
        pdf.add_font("Roboto", "B", FONT_FILE, uni=True) 
        font_name = "Roboto"
    else: font_name = "Helvetica"

    # Logo và thông tin công ty
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

    # Tiêu đề
    pdf.set_font(font_name, 'B' if has_font else '', 16)
    tieu_de = "PHIẾU THU TIỀN" if loai_gd == "Thu" else "PHIẾU CHI TIỀN"
    pdf.cell(0, 10, tieu_de, ln=True, align="C")
    
    pdf.set_font(font_name, "", 11)
    pdf.cell(0, 6, f"Ngày: {ngay_gd}", ln=True, align="C")
    pdf.cell(0, 6, f"Mã Phiếu: {ma_phieu}", ln=True, align="C")
    pdf.ln(8)
    
    # Nội dung
    pdf.set_font(font_name, 'B' if has_font else '', 12)
    pdf.cell(40, 10, "Số tiền:", border=0)
    pdf.set_font(font_name, "", 12)
    pdf.cell(0, 10, f"{format_vn(so_tien)} VNĐ", ln=True)

    pdf.set_font(font_name, 'B' if has_font else '', 12)
    pdf.cell(40, 10, "Nội dung:", border=0)
    pdf.set_font(font_name, "", 12)
    pdf.multi_cell(0, 10, noi_dung)

    if loai_gd == "Chi":
        pdf.set_font(font_name, 'B' if has_font else '', 12)
        pdf.cell(40, 10, "Chứng từ (HĐ):", border=0)
        pdf.set_font(font_name, "", 12)
        pdf.cell(0, 10, co_hoa_don, ln=True)

    pdf.ln(15)
    
    # Chữ ký
    pdf.set_font(font_name, "", 11)
    pdf.cell(95, 6, "Người Lập Phiếu", align='C')
    pdf.cell(95, 6, "Người Giao/Nhận Tiền", ln=True, align='C')
    pdf.cell(95, 6, "(Ký, ghi rõ họ tên)", align='C')
    pdf.cell(95, 6, "(Ký, ghi rõ họ tên)", align='C')
    
    try: return bytes(pdf.output())
    except:
        out = pdf.output(dest='S')
        return out.encode('latin-1') if isinstance(out, str) else bytes(out)


# ==========================================
# GIAO DIỆN NGƯỜI DÙNG
# ==========================================
tab1, tab2, tab3 = st.tabs(["📥 Nạp Ngân Sách (Thu)", "📤 Chi Tiền", "📊 Bảng Kê & Lịch Sử"])

# --- TAB 1: NẠP NGÂN SÁCH ---
with tab1:
    st.subheader("📥 Nhập Khoản Thu / Nạp Ngân Sách")
    with st.form("form_thu_quy", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            ngay_thu = st.date_input("Ngày nạp tiền", lay_gio_vn().date(), format="DD/MM/YYYY")
            so_tien_thu = st.number_input("Số tiền nạp (VNĐ)", min_value=0.0, step=100000.0)
        with c2:
            nd_thu = st.text_area("Nội dung / Nguồn thu")
            
        st.markdown("**📁 Tùy chọn in phiếu Thu:**")
        loai_xuat_thu = st.radio("Định dạng xuất Phiếu Thu:", ["Chỉ xuất file PDF", "Chỉ xuất file Ảnh (PNG)", "Xuất cả PDF và Ảnh"], horizontal=True, index=1, key="rd_thu")

        if st.form_submit_button("💾 LƯU PHIẾU THU", type="primary"):
            if so_tien_thu > 0 and nd_thu.strip():
                ma_phieu = f"PT_{int(time.time())}"
                ngay_str = ngay_thu.strftime("%d/%m/%Y")
                
                c.execute("""INSERT INTO public.quy_thu_chi (ma_phieu, loai_gd, ngay_gd, so_tien, noi_dung, co_hoa_don) 
                             VALUES (%s, 'Thu', %s, %s, %s, %s)""", 
                          (ma_phieu, ngay_str, so_tien_thu, nd_thu, "Không áp dụng"))
                conn.commit()
                don_dep_lich_su_quy()
                
                st.session_state['pdf_gd'] = generate_phieu_pdf(ma_phieu, "Thu", ngay_str, so_tien_thu, nd_thu, "Không áp dụng")
                st.session_state['ten_file_gd'] = f"{ma_phieu}.pdf"
                st.session_state['rd_xuat'] = loai_xuat_thu
                
                img_gd = convert_pdf_to_png(st.session_state['pdf_gd'])
                if img_gd:
                    st.session_state['img_gd'] = img_gd
                    
                st.success("✅ Đã ghi nhận Phiếu Thu vào hệ thống!")
            else:
                st.warning("⚠️ Vui lòng nhập số tiền lớn hơn 0 và ghi rõ nội dung nạp quỹ.")

# --- TAB 2: CHI TIỀN ---
with tab2:
    st.subheader("📤 Tạo Phiếu Chi Tiền")
    with st.form("form_chi_quy", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            ngay_chi = st.date_input("Ngày chi tiền", lay_gio_vn().date(), format="DD/MM/YYYY")
            so_tien_chi = st.number_input("Số tiền chi (VNĐ)", min_value=0.0, step=50000.0)
            kem_hoa_don = st.radio("Tình trạng chứng từ:", ["Có hóa đơn", "Không có hóa đơn"], index=0, horizontal=True)
        with c2:
            nd_chi = st.text_area("Nội dung chi (Ghi rõ mục đích sử dụng)")
            
        st.markdown("**📁 Tùy chọn in phiếu Chi:**")
        loai_xuat_chi = st.radio("Định dạng xuất Phiếu Chi:", ["Chỉ xuất file PDF", "Chỉ xuất file Ảnh (PNG)", "Xuất cả PDF và Ảnh"], horizontal=True, index=1, key="rd_chi")

        if st.form_submit_button("💸 LƯU PHIẾU CHI", type="primary"):
            if so_tien_chi > 0 and nd_chi.strip():
                ma_phieu = f"PC_{int(time.time())}"
                ngay_str = ngay_chi.strftime("%d/%m/%Y")
                
                c.execute("""INSERT INTO public.quy_thu_chi (ma_phieu, loai_gd, ngay_gd, so_tien, noi_dung, co_hoa_don) 
                             VALUES (%s, 'Chi', %s, %s, %s, %s)""", 
                          (ma_phieu, ngay_str, so_tien_chi, nd_chi, kem_hoa_don))
                conn.commit()
                don_dep_lich_su_quy()
                
                st.session_state['pdf_gd'] = generate_phieu_pdf(ma_phieu, "Chi", ngay_str, so_tien_chi, nd_chi, kem_hoa_don)
                st.session_state['ten_file_gd'] = f"{ma_phieu}.pdf"
                st.session_state['rd_xuat'] = loai_xuat_chi
                
                img_gd = convert_pdf_to_png(st.session_state['pdf_gd'])
                if img_gd:
                    st.session_state['img_gd'] = img_gd
                    
                st.success("✅ Đã ghi nhận Phiếu Chi vào hệ thống!")
            else:
                st.warning("⚠️ Vui lòng nhập số tiền lớn hơn 0 và ghi rõ nội dung chi.")

# --- HIỂN THỊ NÚT TẢI XUỐNG DƯỚI CÙNG CHO CẢ 2 TAB THU & CHI ---
if 'pdf_gd' in st.session_state:
    st.markdown("---")
    st.info("🖨️ **Bản In Giao Dịch Vừa Tạo:**")
    dl_c1, dl_c2 = st.columns(2)
    loai_xuat = st.session_state.get('rd_xuat', [])
    
    if "PDF" in loai_xuat or "Cả" in loai_xuat:
        with dl_c1:
            st.download_button("📥 TẢI PHIẾU (PDF)", data=st.session_state['pdf_gd'], file_name=st.session_state['ten_file_gd'], mime="application/pdf", type="primary", use_container_width=True)
            
    if ("Ảnh" in loai_xuat or "Cả" in loai_xuat) and st.session_state.get('img_gd'):
        with dl_c2:
            img_name = st.session_state['ten_file_gd'].replace('.pdf', '.png')
            st.download_button("🖼️ TẢI PHIẾU (ẢNH)", data=st.session_state['img_gd'], file_name=img_name, mime="image/png", type="primary", use_container_width=True)

# --- TAB 3: BẢNG KÊ & LỊCH SỬ ---
with tab3:
    st.subheader("📊 Tổng Quan Quỹ & Lịch Sử Giao Dịch")
    
    try:
        df_quy = pd.read_sql("SELECT ma_phieu, loai_gd, ngay_gd, so_tien, noi_dung, co_hoa_don FROM public.quy_thu_chi ORDER BY id DESC", conn)
        
        if not df_quy.empty:
            tong_thu = df_quy[df_quy['loai_gd'] == 'Thu']['so_tien'].sum()
            tong_chi = df_quy[df_quy['loai_gd'] == 'Chi']['so_tien'].sum()
            ton_quy = tong_thu - tong_chi
            
            # --- HIỂN THỊ METRICS TỔNG QUAN ---
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("💰 TỔNG NẠP (THU)", f"{format_vn(tong_thu)} VNĐ")
            col_m2.metric("💸 TỔNG ĐÃ CHI", f"{format_vn(tong_chi)} VNĐ")
            col_m3.metric("🏦 TỒN QUỸ HIỆN TẠI", f"{format_vn(ton_quy)} VNĐ")
            
            st.markdown("---")
            st.markdown(f"**Danh sách 100 giao dịch Thu / Chi gần nhất:**")
            
            # Đổi tên cột cho hiển thị đẹp
            df_hien_thi = df_quy.copy()
            df_hien_thi.columns = ["Mã Phiếu", "Loại", "Ngày", "Số Tiền (VNĐ)", "Nội Dung", "Hóa Đơn"]
            df_hien_thi['Số Tiền (VNĐ)'] = df_hien_thi['Số Tiền (VNĐ)'].apply(lambda x: format_vn(x))
            
            # Highlight màu nền cho Thu (xanh) / Chi (đỏ)
            def highlight_loai(val):
                if val == 'Thu': return 'color: green; font-weight: bold'
                elif val == 'Chi': return 'color: red; font-weight: bold'
                return ''
            
            st.dataframe(df_hien_thi.style.map(highlight_loai, subset=['Loại']), use_container_width=True, hide_index=True)
            
        else:
            st.info("Chưa có phát sinh giao dịch nạp / chi quỹ nào.")
    except Exception as e:
        st.error(f"Lỗi tải dữ liệu quỹ: {e}")