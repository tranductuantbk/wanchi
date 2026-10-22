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
        page = doc.load_page(0) # Lấy trang đầu tiên
        pix = page.get_pixmap(dpi=200) # dpi=200 cho ảnh xuất ra cực nét
        return pix.tobytes("png")
    except Exception as e:
        st.error(f"Lỗi khi chuyển đổi ảnh: {e}")
        return None

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
if not role: st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang Tạo Đơn chỉ dành cho Quản lý / Kế toán WANCHI.")
    st.stop()

# ==========================================
# CẤU HÌNH FONT & DATABASE
# ==========================================
FONT_FILE = "Roboto-Regular.ttf"
FONT_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"

@st.cache_resource
def download_font():
    if not os.path.exists(FONT_FILE):
        try: urllib.request.urlretrieve(FONT_URL, FONT_FILE)
        except: return False
    return True
download_font()

st.header("📝 Hệ Thống Tạo Đơn Hàng WANCHI")

conn = get_connection()
c = conn.cursor()

# KHỞI TẠO BẢNG ĐƠN HÀNG (CÓ BỘ MỞ KHÓA)
try:
    c.execute('''CREATE TABLE IF NOT EXISTS don_hang (id SERIAL PRIMARY KEY)''')
    conn.commit()
except: conn.rollback()

cac_cot = {
    "ma_don": "TEXT", "ngay_tao": "TEXT", "ten_kh": "TEXT", 
    "loai_don": "TEXT", "tong_tien": "REAL", "chi_tiet": "TEXT", "trang_thai": "TEXT DEFAULT 'Mới tạo'"
}
for cot, kieu in cac_cot.items():
    try: 
        c.execute(f"ALTER TABLE don_hang ADD COLUMN {cot} {kieu}")
        conn.commit()
    except: conn.rollback()

# LẤY DỮ LIỆU TỪ CÁC KHO (Thêm truy vấn quy_cach_loc)
try: df_kh = pd.read_sql("SELECT ten_kh, nhom_kh, so_dien_thoai FROM dm_khach_hang", conn)
except: df_kh = pd.DataFrame(columns=['ten_kh', 'nhom_kh', 'so_dien_thoai'])

try: df_kh_ome = pd.read_sql("SELECT ten_kh, so_dien_thoai FROM dm_khach_hang_ome", conn)
except: df_kh_ome = pd.DataFrame(columns=['ten_kh', 'so_dien_thoai'])

try: df_sp_chuan = pd.read_sql("SELECT ten_sp, gia_dai_ly, gia_khach_le, quy_cach_loc FROM dm_san_pham", conn)
except: df_sp_chuan = pd.DataFrame(columns=['ten_sp', 'gia_dai_ly', 'gia_khach_le', 'quy_cach_loc'])

try: df_sp_ome = pd.read_sql("SELECT ten_sp, gia_ome, quy_cach_loc FROM dm_san_pham_ome", conn)
except: df_sp_ome = pd.DataFrame(columns=['ten_sp', 'gia_ome', 'quy_cach_loc'])

# Lấy Mã Đơn Tiếp Theo 
def lay_ma_don_moi():
    try:
        c.execute("SELECT ma_don FROM don_hang ORDER BY id DESC LIMIT 1")
        last_ma = c.fetchone()
        if last_ma and last_ma[0] and last_ma[0].startswith("DH-"):
            num = int(last_ma[0].split("-")[1])
            return f"DH-{num + 1:04d}"
    except: pass
    return "DH-0001"

if 'gio_chuan' not in st.session_state: st.session_state.gio_chuan = []
if 'gio_ome' not in st.session_state: st.session_state.gio_ome = []
ma_don_hien_tai = lay_ma_don_moi()

def format_vn(value):
    try: return "{:,.0f}".format(value).replace(",", ".")
    except: return str(value)

# ==========================================
# HÀM XUẤT PDF ĐƠN HÀNG (CÓ LOGO)
# ==========================================
def generate_order_pdf(ma_dh, kh_name, kh_phone, df_items, total, loai_don):
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
    pdf.cell(0, 10, "HÓA ĐƠN BÁN HÀNG" if loai_don != "Hàng OME" else "HÓA ĐƠN GIA CÔNG (OME)", ln=True, align='C')
    
    pdf.set_font(font_name, size=11)
    pdf.cell(0, 8, f"Mã Đơn: {ma_dh}   |   Ngày: {lay_gio_vn().strftime('%d/%m/%Y')}", ln=True, align='C')
    pdf.ln(5)
    
    pdf.set_font(font_name, size=11)
    pdf.cell(0, 6, f"Khách hàng: {kh_name}", ln=True)
    pdf.cell(0, 6, f"Điện thoại: {kh_phone}", ln=True)
    pdf.ln(5)

    col_widths = [15, 80, 20, 35, 40]
    headers = ["STT", "Tên Sản Phẩm", "SL", "Đơn Giá", "Thành Tiền"]
    
    pdf.set_font(font_name, 'B' if has_font else '', 10)
    pdf.set_fill_color(230, 230, 230)
    for i, col in enumerate(headers):
        pdf.cell(col_widths[i], 10, col, border=1, align='C', fill=True)
    pdf.ln()

    pdf.set_font(font_name, size=10)
    stt = 1
    for _, row in df_items.iterrows():
        ten_sp = str(row.get('Tên Sản Phẩm', row.get('Tên Sản Phẩm OME', 'N/A')))
        so_luong = row.get('Số Lượng', 0)
        don_gia = row.get('Đơn Giá', row.get('Đơn Giá OME', 0))
        thanh_tien = row.get('Thành Tiền', 0)
        
        pdf.cell(col_widths[0], 8, str(stt), border=1, align='C')
        pdf.cell(col_widths[1], 8, ten_sp, border=1) 
        pdf.cell(col_widths[2], 8, format_vn(so_luong), border=1, align='C') 
        pdf.cell(col_widths[3], 8, format_vn(don_gia), border=1, align='R') 
        pdf.cell(col_widths[4], 8, format_vn(thanh_tien), border=1, align='R') 
        pdf.ln()
        stt += 1

    pdf.set_font(font_name, 'B' if has_font else '', 11)
    pdf.cell(sum(col_widths[:-1]), 10, "TỔNG CỘNG:", border=1, align='R')
    pdf.cell(col_widths[-1], 10, format_vn(total), border=1, align='R', ln=True)

    pdf.ln(15)
    pdf.cell(95, 6, "Người Lập Phiếu", align='C')
    pdf.cell(95, 6, "Khách Hàng", align='C')
    
    try:
        return bytes(pdf.output())
    except Exception:
        out = pdf.output(dest='S')
        return out.encode('latin-1') if isinstance(out, str) else bytes(out)

# ==========================================
# GIAO DIỆN TẠO ĐƠN (4 TABS)
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["🛒 Tạo Đơn Hàng Wanchi", "🛠️ Tạo Đơn Hàng OME", "📑 Tạo Đơn Hàng Báo Giá", "📂 Lịch Sử Đơn Hàng"])

# ------------------------------------------
# TAB 1: ĐƠN HÀNG WANCHI (CHUẨN)
# ------------------------------------------
with tab1:
    st.subheader(f"Mã Đơn Tiếp Theo: {ma_don_hien_tai}")
    
    kh_chuan = st.selectbox("🙋‍♂️ Chọn Khách Hàng:", ["-- Chọn Khách Hàng --"] + df_kh['ten_kh'].tolist(), key="kh_chuan")
    loai_gia_chot = "Chưa xác định"
    sdt_kh_chot = ""
    
    if kh_chuan != "-- Chọn Khách Hàng --":
        thong_tin_kh = df_kh[df_kh['ten_kh'] == kh_chuan].iloc[0]
        sdt_kh_chot = thong_tin_kh.get('so_dien_thoai', '')
        nhom_kh = thong_tin_kh.get('nhom_kh', 'Công ty')
        loai_gia_chot = "Giá Đại Lý" if nhom_kh == "Đại lý" else "Giá Công ty"
        
        if nhom_kh == "Ưu đãi": loai_gia_chot = "Giá Ưu Đãi (Giảm 20%)"
        
        st.success(f"📌 Đã nhận diện: Khách hàng thuộc nhóm **{nhom_kh}** -> Hệ thống tự động áp dụng **{loai_gia_chot}**.")
    
    # Khu vực chọn sản phẩm và tính lốc tự động (Đã bỏ nhập số lượng cái)
    st.markdown("**📦 Chọn Sản Phẩm & Nhập Số Lốc**")
    col_c1, col_c2 = st.columns([3, 1])
    sp_chon = col_c1.selectbox("Tên Sản Phẩm:", ["-- Chọn Sản Phẩm --"] + df_sp_chuan['ten_sp'].tolist(), key="chon_sp_chuan")
    so_loc_chon = col_c2.number_input("📦 Số Lốc:", min_value=1, step=1, key="sl_loc_chuan")
    
    tong_so_cai_chuan = 0
    
    # TỰ ĐỘNG TÍNH TRÒN LỐC 
    if sp_chon != "-- Chọn Sản Phẩm --":
        info = df_sp_chuan[df_sp_chuan['ten_sp'] == sp_chon].iloc[0]
        loc = 1
        if 'quy_cach_loc' in info and pd.notna(info['quy_cach_loc']):
            try: loc = int(info['quy_cach_loc'])
            except: loc = 1
        if loc <= 0: loc = 1

        tong_so_cai_chuan = so_loc_chon * loc

        if tong_so_cai_chuan > 0:
            st.info(f"👉 **Hệ thống tự tính:** {so_loc_chon} lốc (Quy cách đóng gói: **{loc} cái/lốc**) = **Xuất {tong_so_cai_chuan} cái**")
            st.success("✅ Số lượng đã đảm bảo xuất xuất tròn lốc.")

    if st.button("➕ Thêm vào đơn", type="primary", key="btn_add_chuan"):
        if kh_chuan == "-- Chọn Khách Hàng --":
            st.error("⚠️ Vui lòng chọn Khách hàng ở trên để hệ thống biết áp dụng loại giá nào!")
        elif sp_chon == "-- Chọn Sản Phẩm --":
            st.error("⚠️ Vui lòng chọn sản phẩm!")
        elif tong_so_cai_chuan == 0:
            st.error("⚠️ Vui lòng nhập Số Lốc hợp lệ!")
        else:
            info = df_sp_chuan[df_sp_chuan['ten_sp'] == sp_chon].iloc[0]
            
            gia_goc = info.get('gia_dai_ly', 0)
            gia_cty_chuan = info.get('gia_khach_le', 0)
            
            if loai_gia_chot == "Giá Đại Lý": don_gia = int(gia_goc)
            elif "Ưu Đãi" in loai_gia_chot: don_gia = int(round(gia_cty_chuan * 0.80, -1))
            else: don_gia = int(gia_cty_chuan)
            
            st.session_state.gio_chuan.append({
                "Tên Sản Phẩm": sp_chon,
                "Loại Giá": loai_gia_chot,
                "Số Lượng": tong_so_cai_chuan,
                "Giá Công ty": int(gia_cty_chuan),
                "Đơn Giá": don_gia,
                "Thành Tiền": tong_so_cai_chuan * don_gia
            })
            st.rerun()

    if st.session_state.gio_chuan:
        st.markdown("---")
        df_gio_chuan = pd.DataFrame(st.session_state.gio_chuan)
        
        df_gio_chuan.insert(0, "Xóa", False)
        
        st.info("💡 **Mẹo Pro:** Cột Số Lượng hiển thị là tổng số cái. Cột Giá Công Ty chỉ hiện ở đây để đối chiếu, sẽ không xuất hiện trong PDF và Lịch sử đơn!")
        
        edited_df_chuan = st.data_editor(
            df_gio_chuan,
            column_config={
                "Xóa": st.column_config.CheckboxColumn("🗑️ Xóa", default=False),
                "Tên Sản Phẩm": st.column_config.TextColumn(disabled=True),
                "Loại Giá": st.column_config.TextColumn(disabled=True),
                "Số Lượng": st.column_config.NumberColumn("Số lượng cái (Tổng)", min_value=1, step=1, disabled=True), # Khóa luôn cột này để ép nhập theo lốc ở trên
                "Giá Công ty": st.column_config.NumberColumn(disabled=True),
                "Đơn Giá": st.column_config.NumberColumn(disabled=True),
                "Thành Tiền": st.column_config.NumberColumn(disabled=True)
            },
            hide_index=True,
            use_container_width=True,
            key="editor_don_chuan"
        )
        
        if edited_df_chuan['Xóa'].any():
            df_valid = edited_df_chuan[edited_df_chuan['Xóa'] == False].drop(columns=['Xóa'])
            df_valid['Thành Tiền'] = df_valid['Số Lượng'] * df_valid['Đơn Giá']
            st.session_state.gio_chuan = df_valid.to_dict('records')
            st.rerun() 
            
        edited_df_chuan['Thành Tiền'] = edited_df_chuan['Số Lượng'] * edited_df_chuan['Đơn Giá']
        st.session_state.gio_chuan = edited_df_chuan.drop(columns=['Xóa']).to_dict('records')
        
        tong_tien_chuan = float(edited_df_chuan['Thành Tiền'].sum())
        st.write(f"### 💰 TỔNG CỘNG: {format_vn(tong_tien_chuan)} VNĐ")
        
        if loai_gia_chot == "Giá Đại Lý" and tong_tien_chuan < 12000000:
            st.warning(f"⚠️ **CẢNH BÁO:** Khách hàng là ĐẠI LÝ nhưng tổng đơn hàng chưa đạt định mức **12.000.000 VNĐ** (Hiện tại: {format_vn(tong_tien_chuan)} VNĐ).")

        st.markdown("**📁 Tùy chọn xuất file:**")
        loai_xuat_t1 = st.radio(
            "Lựa chọn định dạng xuất Hóa đơn:", 
            ["Chỉ xuất file PDF", "Chỉ xuất file Ảnh (PNG)", "Xuất cả PDF và Ảnh"], 
            horizontal=True, 
            key="radio_xuat_t1",
            index=1 
        )
        
        col_btn_c1, col_btn_c2 = st.columns([1, 1])
        with col_btn_c1:
            if st.button("💾 CHỐT ĐƠN & TẠO FILE (ĐẠI LÝ / CÔNG TY)", type="primary", use_container_width=True, key="btn_chot_chuan"):
                df_print = pd.DataFrame(st.session_state.gio_chuan)
                if 'Giá Công ty' in df_print.columns:
                    df_print = df_print.drop(columns=['Giá Công ty'])
                
                st.session_state['pdf_don_chuan'] = generate_order_pdf(ma_don_hien_tai, kh_chuan, sdt_kh_chot, df_print, tong_tien_chuan, "Hàng Chuẩn")
                st.session_state['pdf_ten_chuan'] = f"{ma_don_hien_tai}_{kh_chuan}.pdf"
                
                img_data_chuan = convert_pdf_to_png(st.session_state['pdf_don_chuan'])
                if img_data_chuan:
                    st.session_state['img_don_chuan'] = img_data_chuan
                
                try:
                    chi_tiet_json = df_print.to_json(orient='records')
                    ngay_gio = lay_gio_vn().strftime("%d/%m/%Y %H:%M")
                    c.execute("INSERT INTO don_hang (ma_don, ngay_tao, ten_kh, loai_don, tong_tien, chi_tiet) VALUES (%s, %s, %s, %s, %s, %s)", 
                              (ma_don_hien_tai, ngay_gio, kh_chuan, 'Hàng Chuẩn', tong_tien_chuan, chi_tiet_json))
                    conn.commit()
                    st.success("✅ Chốt đơn thành công! Dữ liệu đã lưu vào lịch sử (không chứa Giá Công Ty). Vui lòng tải file bên dưới.")
                except Exception as e:
                    conn.rollback()
                    st.error(f"⚠️ Lỗi Database: {e}")
        
        with col_btn_c2:
            if st.button("🗑️ Xóa sạch đơn này", use_container_width=True, key="btn_xoa_chuan"):
                st.session_state.gio_chuan = []
                if 'pdf_don_chuan' in st.session_state: del st.session_state['pdf_don_chuan']
                if 'img_don_chuan' in st.session_state: del st.session_state['img_don_chuan']
                st.rerun()
                
        if 'pdf_don_chuan' in st.session_state:
            st.markdown("---")
            col_dl1, col_dl2 = st.columns(2)
            
            if "PDF" in loai_xuat_t1 or "Cả" in loai_xuat_t1:
                with col_dl1:
                    st.download_button("🖨️ TẢI FILE PDF", data=st.session_state['pdf_don_chuan'], file_name=st.session_state['pdf_ten_chuan'], mime="application/pdf", type="primary", use_container_width=True)
            
            if ("Ảnh" in loai_xuat_t1 or "Cả" in loai_xuat_t1) and st.session_state.get('img_don_chuan'):
                with col_dl2:
                    img_name_chuan = st.session_state['pdf_ten_chuan'].replace('.pdf', '.png')
                    st.download_button("🖼️ TẢI FILE ẢNH HÓA ĐƠN", data=st.session_state['img_don_chuan'], file_name=img_name_chuan, mime="image/png", type="primary", use_container_width=True)

# ------------------------------------------
# TAB 2: ĐƠN HÀNG OME
# ------------------------------------------
with tab2:
    st.subheader(f"Mã Đơn Tiếp Theo: {ma_don_hien_tai}")
    
    khach_hang_ome = st.selectbox("🙋‍♂️ Chọn Khách Hàng OME:", ["-- Chọn Khách Hàng --"] + df_kh_ome['ten_kh'].tolist(), key="kh_ome")
    sdt_ome_chot = ""
    if khach_hang_ome != "-- Chọn Khách Hàng --":
        sdt_ome_chot = df_kh_ome[df_kh_ome['ten_kh'] == khach_hang_ome].iloc[0].get('so_dien_thoai', '')

    st.markdown("**⚙️ Chọn Sản Phẩm OME & Nhập Số Lốc**")
    col_o1, col_o2 = st.columns([3, 1])
    sp_ome_chon = col_o1.selectbox("Tên Sản Phẩm OME:", ["-- Chọn Sản Phẩm --"] + df_sp_ome['ten_sp'].tolist(), key="chon_sp_ome")
    so_loc_ome_chon = col_o2.number_input("📦 Số Lốc:", min_value=1, step=1, key="sl_loc_ome")
    
    tong_so_cai_ome = 0

    # TỰ ĐỘNG TÍNH TRÒN LỐC CHO HÀNG OME
    if sp_ome_chon != "-- Chọn Sản Phẩm --":
        info_ome = df_sp_ome[df_sp_ome['ten_sp'] == sp_ome_chon].iloc[0]
        loc_ome = 1
        if 'quy_cach_loc' in info_ome and pd.notna(info_ome['quy_cach_loc']):
            try: loc_ome = int(info_ome['quy_cach_loc'])
            except: loc_ome = 1
        if loc_ome <= 0: loc_ome = 1

        tong_so_cai_ome = so_loc_ome_chon * loc_ome

        if tong_so_cai_ome > 0:
            st.info(f"👉 **Hệ thống tự tính:** {so_loc_ome_chon} lốc (Quy cách đóng gói: **{loc_ome} cái/lốc**) = **Xuất {tong_so_cai_ome} cái**")
            st.success("✅ Số lượng đã đảm bảo xuất xuất tròn lốc.")

    if st.button("➕ Thêm vào đơn OME", type="primary", key="btn_add_ome"):
        if sp_ome_chon == "-- Chọn Sản Phẩm --":
            st.error("⚠️ Vui lòng chọn sản phẩm OME!")
        elif tong_so_cai_ome == 0:
            st.error("⚠️ Vui lòng nhập Số Lốc hợp lệ!")
        else:
            info_ome = df_sp_ome[df_sp_ome['ten_sp'] == sp_ome_chon].iloc[0]
            don_gia_ome = info_ome['gia_ome']
            
            st.session_state.gio_ome.append({
                "Tên Sản Phẩm OME": sp_ome_chon,
                "Loại Giá": "Giá OME",
                "Số Lượng": tong_so_cai_ome,
                "Đơn Giá OME": don_gia_ome,
                "Thành Tiền": tong_so_cai_ome * don_gia_ome
            })
            st.rerun()

    if st.session_state.gio_ome:
        st.markdown("---")
        df_gio_ome = pd.DataFrame(st.session_state.gio_ome)
        df_gio_ome.insert(0, "Xóa", False)
        
        st.info("💡 **Mẹo Pro:** Tích chọn ô **Xóa** để lập tức loại bỏ sản phẩm khỏi đơn!")
        
        edited_df_ome = st.data_editor(
            df_gio_ome,
            column_config={
                "Xóa": st.column_config.CheckboxColumn("🗑️ Xóa", default=False),
                "Tên Sản Phẩm OME": st.column_config.TextColumn(disabled=True),
                "Loại Giá": st.column_config.TextColumn(disabled=True),
                "Số Lượng": st.column_config.NumberColumn("Số lượng cái (Tổng)", min_value=1, step=1, disabled=True),
                "Đơn Giá OME": st.column_config.NumberColumn(disabled=True),
                "Thành Tiền": st.column_config.NumberColumn(disabled=True)
            },
            hide_index=True,
            use_container_width=True,
            key="editor_don_ome"
        )
        
        if edited_df_ome['Xóa'].any():
            df_valid_ome = edited_df_ome[edited_df_ome['Xóa'] == False].drop(columns=['Xóa'])
            df_valid_ome['Thành Tiền'] = df_valid_ome['Số Lượng'] * df_valid_ome['Đơn Giá OME']
            st.session_state.gio_ome = df_valid_ome.to_dict('records')
            st.rerun()
            
        edited_df_ome['Thành Tiền'] = edited_df_ome['Số Lượng'] * edited_df_ome['Đơn Giá OME']
        st.session_state.gio_ome = edited_df_ome.drop(columns=['Xóa']).to_dict('records')
        
        tong_tien_ome = float(edited_df_ome['Thành Tiền'].sum())
        st.write(f"### 💰 TỔNG CỘNG OME: {format_vn(tong_tien_ome)} VNĐ")
        
        st.markdown("**📁 Tùy chọn xuất file:**")
        loai_xuat_t2 = st.radio(
            "Lựa chọn định dạng xuất Hóa đơn OME:", 
            ["Chỉ xuất file PDF", "Chỉ xuất file Ảnh (PNG)", "Xuất cả PDF và Ảnh"], 
            horizontal=True, 
            key="radio_xuat_t2",
            index=1 
        )
        
        col_btn_o1, col_btn_o2 = st.columns([1, 1])
        with col_btn_o1:
            if st.button("💾 CHỐT ĐƠN & TẠO FILE (HÀNG OME)", type="primary", use_container_width=True, key="btn_chot_ome"):
                if khach_hang_ome == "-- Chọn Khách Hàng --":
                    st.error("⚠️ Vui lòng chọn Khách Hàng!")
                else:
                    df_print_ome = pd.DataFrame(st.session_state.gio_ome)
                    st.session_state['pdf_don_ome'] = generate_order_pdf(ma_don_hien_tai, khach_hang_ome, sdt_ome_chot, df_print_ome, tong_tien_ome, "Hàng OME")
                    st.session_state['pdf_ten_ome'] = f"{ma_don_hien_tai}_OME_{khach_hang_ome}.pdf"
                    
                    img_data_ome = convert_pdf_to_png(st.session_state['pdf_don_ome'])
                    if img_data_ome:
                        st.session_state['img_don_ome'] = img_data_ome
                    
                    try:
                        chi_tiet_json_ome = df_print_ome.to_json(orient='records')
                        ngay_gio_ome = lay_gio_vn().strftime("%d/%m/%Y %H:%M")
                        c.execute("INSERT INTO don_hang (ma_don, ngay_tao, ten_kh, loai_don, tong_tien, chi_tiet) VALUES (%s, %s, %s, %s, %s, %s)", 
                                  (ma_don_hien_tai, ngay_gio_ome, khach_hang_ome, 'Hàng OME', tong_tien_ome, chi_tiet_json_ome))
                        conn.commit()
                        st.success("✅ Chốt đơn OME thành công! Dữ liệu đã lưu vào lịch sử. Tải file bên dưới.")
                    except Exception as e: 
                        conn.rollback()
                        st.error(f"⚠️ Lỗi Database: {e}")
        
        with col_btn_o2:
            if st.button("🗑️ Xóa sạch đơn OME", use_container_width=True, key="btn_xoa_ome"):
                st.session_state.gio_ome = []
                if 'pdf_don_ome' in st.session_state: del st.session_state['pdf_don_ome']
                if 'img_don_ome' in st.session_state: del st.session_state['img_don_ome']
                st.rerun()

        if 'pdf_don_ome' in st.session_state:
            st.markdown("---")
            col_dl_o1, col_dl_o2 = st.columns(2)
            
            if "PDF" in loai_xuat_t2 or "Cả" in loai_xuat_t2:
                with col_dl_o1:
                    st.download_button("🖨️ TẢI FILE PDF", data=st.session_state['pdf_don_ome'], file_name=st.session_state['pdf_ten_ome'], mime="application/pdf", type="primary", use_container_width=True)
            
            if ("Ảnh" in loai_xuat_t2 or "Cả" in loai_xuat_t2) and st.session_state.get('img_don_ome'):
                with col_dl_o2:
                    img_name_ome = st.session_state['pdf_ten_ome'].replace('.pdf', '.png')
                    st.download_button("🖼️ TẢI FILE ẢNH HÓA ĐƠN", data=st.session_state['img_don_ome'], file_name=img_name_ome, mime="image/png", type="primary", use_container_width=True)

# ------------------------------------------
# TAB 3: TẠO ĐƠN HÀNG BÁO GIÁ
# ------------------------------------------
with tab3:
    st.subheader("📑 Chuyển đổi Báo Giá thành Đơn Hàng")
    st.info(f"Hệ thống sẽ lấy dữ liệu từ Báo Giá và cấp cho nó một Mã Đơn Hàng chính thức (**{ma_don_hien_tai}**) để ghi nhận doanh thu và xuất kho.")
    
    try:
        df_bg = pd.read_sql("SELECT id, ma_bao_gia, ngay_tao, ten_kh, so_dien_thoai, tong_tien, chi_tiet FROM public.lich_su_bao_gia ORDER BY id DESC", conn)
        if not df_bg.empty:
            df_bg['ma_bao_gia'] = df_bg['ma_bao_gia'].fillna("Mã Cũ")
            options_bg = ["-- Chọn Báo Giá --"]
            for _, r in df_bg.iterrows():
                options_bg.append(f"[{r['ma_bao_gia']}] Khách: {r['ten_kh']} ({r['ngay_tao']})")
            
            chon_bg = st.selectbox("🔍 Chọn Mã Báo Giá khách đã chốt:", options_bg)
            
            if chon_bg != "-- Chọn Báo Giá --":
                ma_bg_chon = chon_bg.split("] ")[0].replace("[", "")
                
                if ma_bg_chon == "Mã Cũ":
                    ten_kh_split = chon_bg.split("Khách: ")[1].split(" (")[0]
                    bg_info = df_bg[df_bg['ten_kh'] == ten_kh_split].iloc[0]
                else:
                    bg_info = df_bg[df_bg['ma_bao_gia'] == ma_bg_chon].iloc[0]
                
                st.write(f"**Khách hàng:** {bg_info['ten_kh']} | **SĐT:** {bg_info['so_dien_thoai']}")
                
                if pd.notna(bg_info['chi_tiet']) and bg_info['chi_tiet']:
                    bg_items = json.loads(bg_info['chi_tiet'])
                    
                    order_items = []
                    for item in bg_items:
                        order_items.append({
                            "Tên Sản Phẩm": item.get("Tên SP", item.get("Tên Sản Phẩm", "N/A")),
                            "Loại Giá": f"Từ Báo Giá ({ma_bg_chon})",
                            "Số Lượng": item.get("Số Lượng", 0),
                            "Đơn Giá": item.get("Đơn Giá", 0),
                            "Thành Tiền": item.get("Thành Tiền", 0)
                        })
                        
                    df_order_bg = pd.DataFrame(order_items)
                    st.dataframe(df_order_bg, use_container_width=True, hide_index=True)
                    tong_tien_bg = float(df_order_bg['Thành Tiền'].sum())
                    
                    st.write(f"### 💰 TỔNG CỘNG CHỐT DEAL: {format_vn(tong_tien_bg)} VNĐ")
                    
                    st.markdown("**📁 Tùy chọn xuất file:**")
                    loai_xuat_t3 = st.radio(
                        "Lựa chọn định dạng xuất Hóa đơn từ Báo giá:", 
                        ["Chỉ xuất file PDF", "Chỉ xuất file Ảnh (PNG)", "Xuất cả PDF và Ảnh"], 
                        horizontal=True, 
                        key="radio_xuat_t3",
                        index=1 # Mặc định chọn Ảnh
                    )
                    
                    if st.button("🚀 CHỐT ĐƠN & TẠO FILE TỪ BÁO GIÁ", type="primary", use_container_width=True, key="btn_chot_bg"):
                        st.session_state['pdf_don_bg'] = generate_order_pdf(ma_don_hien_tai, bg_info['ten_kh'], bg_info['so_dien_thoai'], df_order_bg, tong_tien_bg, "Hàng Chuẩn") 
                        st.session_state['pdf_ten_bg'] = f"{ma_don_hien_tai}_TuBaoGia_{bg_info['ten_kh']}.pdf"
                        
                        img_data_bg = convert_pdf_to_png(st.session_state['pdf_don_bg'])
                        if img_data_bg:
                            st.session_state['img_don_bg'] = img_data_bg
                        
                        try:
                            chi_tiet_json_bg = df_order_bg.to_json(orient='records')
                            ngay_gio = lay_gio_vn().strftime("%d/%m/%Y %H:%M")
                            c.execute("INSERT INTO don_hang (ma_don, ngay_tao, ten_kh, loai_don, tong_tien, chi_tiet) VALUES (%s, %s, %s, %s, %s, %s)", 
                                      (ma_don_hien_tai, ngay_gio, bg_info['ten_kh'], f'Từ Báo Giá {ma_bg_chon}', tong_tien_bg, chi_tiet_json_bg))
                            conn.commit()
                            st.success(f"✅ Đã chuyển đổi thành công! Mã Báo Giá {ma_bg_chon} đã trở thành Đơn Hàng chính thức: **{ma_don_hien_tai}**")
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Lỗi hệ thống: {e}")
                            
                    if 'pdf_don_bg' in st.session_state:
                        st.markdown("---")
                        col_dl_b1, col_dl_b2 = st.columns(2)
                        
                        if "PDF" in loai_xuat_t3 or "Cả" in loai_xuat_t3:
                            with col_dl_b1:
                                st.download_button("🖨️ TẢI FILE PDF", data=st.session_state['pdf_don_bg'], file_name=st.session_state['pdf_ten_bg'], mime="application/pdf", type="primary", use_container_width=True)
                        
                        if ("Ảnh" in loai_xuat_t3 or "Cả" in loai_xuat_t3) and st.session_state.get('img_don_bg'):
                            with col_dl_b2:
                                img_name_bg = st.session_state['pdf_ten_bg'].replace('.pdf', '.png')
                                st.download_button("🖼️ TẢI FILE ẢNH HÓA ĐƠN", data=st.session_state['img_don_bg'], file_name=img_name_bg, mime="image/png", type="primary", use_container_width=True)

        else:
            st.info("Chưa có báo giá nào trong hệ thống.")
    except Exception as e:
        st.error(f"Không thể tải lịch sử báo giá. Lỗi: {e}")

# ------------------------------------------
# TAB 4: LỊCH SỬ ĐƠN HÀNG
# ------------------------------------------
with tab4:
    st.subheader("📂 Danh sách Đơn Hàng đã tạo")
    try:
        df_his = pd.read_sql("SELECT ma_don, ngay_tao, ten_kh, loai_don, tong_tien, trang_thai, chi_tiet FROM don_hang ORDER BY id DESC", conn)
        if not df_his.empty:
            df_hien_thi_his = df_his.drop(columns=['chi_tiet'])
            st.dataframe(df_hien_thi_his, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader("🖨️ Tải Lại Hóa Đơn Cũ")
            options = ["-- Chọn đơn hàng --"] + df_his['ma_don'].tolist()
            chon_don = st.selectbox("🔍 Chọn Mã Đơn để tải lại:", options)
            
            if chon_don != "-- Chọn đơn hàng --":
                row_data = df_his[df_his['ma_don'] == chon_don].iloc[0]
                if pd.notna(row_data['chi_tiet']):
                    df_chi_tiet = pd.DataFrame(json.loads(row_data['chi_tiet']))
                    st.dataframe(df_chi_tiet, use_container_width=True, hide_index=True)
                    
                    sdt_his = "" 
                    if row_data['loai_don'] == 'Hàng Chuẩn': sdt_his = df_kh[df_kh['ten_kh'] == row_data['ten_kh']].iloc[0].get('so_dien_thoai', '') if not df_kh[df_kh['ten_kh'] == row_data['ten_kh']].empty else ""
                    elif row_data['loai_don'] == 'Hàng OME': sdt_his = df_kh_ome[df_kh_ome['ten_kh'] == row_data['ten_kh']].iloc[0].get('so_dien_thoai', '') if not df_kh_ome[df_kh_ome['ten_kh'] == row_data['ten_kh']].empty else ""
                    else:
                        sdt_his = "Theo Báo Giá"

                    loai_pdf_header = "Hàng Chuẩn" if "Báo Giá" in row_data['loai_don'] else row_data['loai_don']
                    
                    loai_xuat_his = st.radio("Lựa chọn định dạng để XUẤT LẠI:", ["Chỉ xuất PDF", "Chỉ xuất Ảnh (PNG)", "Cả PDF và Ảnh"], horizontal=True, key=f"radio_his_{chon_don}", index=1)
                    
                    pdf_re = generate_order_pdf(chon_don, row_data['ten_kh'], sdt_his, df_chi_tiet, float(row_data['tong_tien']), loai_pdf_header)
                    pdf_name_re = f"{chon_don}_{row_data['ten_kh']}.pdf"
                    
                    col_his1, col_his2 = st.columns(2)
                    
                    if "PDF" in loai_xuat_his or "Cả" in loai_xuat_his:
                        with col_his1:
                            st.download_button("📥 XUẤT LẠI FILE PDF", data=pdf_re, file_name=pdf_name_re, mime="application/pdf", type="primary", use_container_width=True)
                    
                    if "Ảnh" in loai_xuat_his or "Cả" in loai_xuat_his:
                        img_re = convert_pdf_to_png(pdf_re)
                        if img_re:
                            with col_his2:
                                img_name_re = pdf_name_re.replace('.pdf', '.png')
                                st.download_button("🖼️ XUẤT LẠI FILE ẢNH", data=img_re, file_name=img_name_re, mime="image/png", type="primary", use_container_width=True)
        else: st.info("Chưa có đơn hàng nào.")
    except: st.info("Hệ thống chưa có dữ liệu lịch sử.")
