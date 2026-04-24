import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, timedelta, timezone
import os
import urllib.request
import time
import json
from db_utils import get_connection, check_password

# ==========================================
# CẤU HÌNH MÚI GIỜ VIỆT NAM (UTC+7)
# ==========================================
VN_TZ = timezone(timedelta(hours=7))
def lay_gio_vn():
    return datetime.now(VN_TZ)

st.set_page_config(page_title="WANCHI Báo Giá", page_icon="🏭", layout="wide")

# ==========================================
# Ổ KHÓA BẢO VỆ 2 LỚP
# ==========================================
role = check_password()
if not role:
    st.stop()

if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang Báo Giá là dữ liệu mật, chỉ dành cho Quản lý.")
    st.stop()
# ==========================================

# ==========================================
# 1. CẤU HÌNH FONT & DATABASE
# ==========================================
FONT_FILE = "Roboto-Regular.ttf"
FONT_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"

@st.cache_resource
def download_font():
    if not os.path.exists(FONT_FILE):
        try:
            urllib.request.urlretrieve(FONT_URL, FONT_FILE)
            return True
        except: return False
    return True
download_font()

st.title("🏭 Hệ Thống Báo Giá Khách Hàng WANCHI")

conn = get_connection()
c = conn.cursor()

if 'gio_bao_gia' not in st.session_state: st.session_state.gio_bao_gia = []
if 'gio_bao_gia_custom' not in st.session_state: st.session_state.gio_bao_gia_custom = []

# Khởi tạo Schema và Bảng
try:
    c.execute("CREATE SCHEMA IF NOT EXISTS public;")
    c.execute('''CREATE TABLE IF NOT EXISTS public.lich_su_bao_gia (
                    id SERIAL PRIMARY KEY,
                    ngay_tao TEXT,
                    ten_kh TEXT,
                    so_dien_thoai TEXT,
                    tong_tien REAL,
                    loai_bao_gia TEXT DEFAULT 'Tiêu chuẩn',
                    chi_tiet TEXT
                )''')
    c.execute("ALTER TABLE public.lich_su_bao_gia ADD COLUMN chi_tiet TEXT")
except: pass 

# LẤY THÊM CỘT GIA_KHACH_LE LÀM "GIÁ CÔNG TY" THAM KHẢO
try: df_sp = pd.read_sql("SELECT ma_sp, ten_sp, gia_dai_ly, gia_khach_le FROM public.dm_san_pham", conn)
except: df_sp = pd.DataFrame(columns=['ma_sp', 'ten_sp', 'gia_dai_ly', 'gia_khach_le'])

def format_vn(value):
    try: return "{:,.0f}".format(value).replace(",", ".")
    except: return str(value)

# ==========================================
# 2. HÀM XUẤT PDF AN TOÀN (ĐÃ VÁ LỖI)
# ==========================================
def generate_generic_pdf(dataframe, title, subtitle="", columns_to_print=None, col_widths=None, total_amount=None):
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
    pdf.multi_cell(0, 5, "775 Võ Hữu Lợi (KCN Lê Minh Xuân 3), Xã Lê Minh Xuân, Huyện Bình Chánh, TP.HCM")
    pdf.set_xy(start_x, pdf.get_y() + 1)
    pdf.cell(0, 5, "Điện thoại: 0902580828 - 0937572577", ln=True)
    pdf.ln(12) 

    pdf.set_font(font_name, 'B' if has_font else '', 16)
    pdf.cell(0, 10, title, ln=True, align='C')
    if subtitle:
        pdf.set_font(font_name, size=11)
        pdf.cell(0, 8, subtitle, ln=True, align='C')
    pdf.ln(5)

    if columns_to_print is None: columns_to_print = dataframe.columns.tolist()
    if col_widths is None: col_widths = [190 / len(columns_to_print)] * len(columns_to_print)
    
    pdf.set_font(font_name, 'B' if has_font else '', 10)
    pdf.set_fill_color(230, 230, 230)
    for i, col in enumerate(columns_to_print):
        pdf.cell(col_widths[i], 10, col, border=1, align='C', fill=True)
    pdf.ln()

    pdf.set_font(font_name, size=9)
    for _, row in dataframe.iterrows():
        for i, col in enumerate(columns_to_print):
            val = row.get(col, "")
            display_val = format_vn(val) if isinstance(val, (int, float)) else str(val)
            pdf.cell(col_widths[i], 9, display_val, border=1, align='C' if not isinstance(val, (int, float)) else 'R')
        pdf.ln()

    if total_amount is not None:
        pdf.set_font(font_name, 'B' if has_font else '', 10)
        w_label = sum(col_widths[:-1])
        w_value = col_widths[-1]
        pdf.cell(w_label, 10, "TỔNG CỘNG:", border=1, align='R')
        pdf.cell(w_value, 10, format_vn(total_amount), border=1, align='R', ln=True)

    pdf.ln(8)
    pdf.set_font(font_name, size=10)
    pdf.cell(0, 6, "* Phiếu báo giá có giá trị trong 10 ngày.", ln=True)
    pdf.cell(0, 6, "* Giá chưa bao gồm phí vận chuyển.", ln=True)
    
    # BỘ VÁ LỖI XUẤT PDF TRÊN CLOUD
    try:
        return bytes(pdf.output())
    except Exception:
        out = pdf.output(dest='S')
        return out.encode('latin-1') if isinstance(out, str) else bytes(out)

# ==========================================
# 3. GIAO DIỆN CHÍNH
# ==========================================
tab1, tab2, tab3 = st.tabs(["🤝 Báo Giá Chuẩn", "🛠️ Báo Giá Tùy Chỉnh", "📂 Lịch Sử & Xuất Lại"])

# --- TAB 1: BÁO GIÁ CHUẨN TỪ DANH MỤC ---
with tab1:
    st.subheader("Tạo báo giá từ danh mục có sẵn")
    c1, c2 = st.columns(2)
    ten_kh = c1.text_input("Tên khách hàng:", key="t1_kh")
    sdt_kh = c2.text_input("Số điện thoại:", key="t1_sdt")

    with st.form("add_sp_t1", clear_on_submit=True):
        col_s1, col_s2 = st.columns([3, 1])
        sp_list = df_sp['ten_sp'].tolist() if not df_sp.empty else []
        sp_chon = col_s1.selectbox("Chọn sản phẩm", ["-- Chọn --"] + sp_list)
        sl_chon = col_s2.number_input("Số lượng", min_value=1, step=1)
        if st.form_submit_button("Thêm vào danh sách"):
            if sp_chon != "-- Chọn --":
                info = df_sp[df_sp['ten_sp'] == sp_chon].iloc[0]
                # LƯU THÊM GIÁ KHÁCH LẺ LÀM GIÁ CÔNG TY
                st.session_state.gio_bao_gia.append({
                    "Mã SP": info['ma_sp'], 
                    "Tên SP": sp_chon, 
                    "Số Lượng": sl_chon, 
                    "Giá Gốc": info['gia_dai_ly'],
                    "Giá công ty": info.get('gia_khach_le', 0)
                })
                st.rerun()

    if st.session_state.gio_bao_gia:
        df_curr = pd.DataFrame(st.session_state.gio_bao_gia)
        
        tong_goc = (df_curr['Giá Gốc'] / 0.6 * df_curr['Số Lượng']).sum()
        if tong_goc < 3000000: ck = 1.0
        elif tong_goc < 6000000: ck = 0.95
        elif tong_goc < 9000000: ck = 0.90
        else: ck = 0.85
        
        df_curr['Đơn Giá'] = (df_curr['Giá Gốc'] / 0.6 * ck).round(0)
        df_curr['Thành Tiền'] = df_curr['Đơn Giá'] * df_curr['Số Lượng']
        tong_cuoi = df_curr['Thành Tiền'].sum()
        
        # HIỂN THỊ CỘT GIÁ CÔNG TY TRÊN WEB (Nhưng không in ra PDF)
        df_hien_thi = df_curr[["Mã SP", "Tên SP", "Số Lượng", "Giá công ty", "Đơn Giá", "Thành Tiền"]]
        st.dataframe(df_hien_thi, use_container_width=True, hide_index=True)
        st.write(f"### 💰 TỔNG CỘNG: {format_vn(tong_cuoi)} VNĐ")
        
        col_btn1, col_btn2 = st.columns([2, 2])
        with col_btn1:
            if ten_kh.strip():
                if st.button("💾 CHỐT ĐƠN & TẠO FILE PDF", type="primary", use_container_width=True, key="luu_t1"):
                    
                    # TẠO PDF (Bỏ qua cột Giá công ty)
                    st.session_state['pdf_data_t1'] = generate_generic_pdf(
                        df_hien_thi, 
                        "BÁO GIÁ SẢN PHẨM", 
                        f"Khách hàng: {ten_kh} | SĐT: {sdt_kh}", 
                        ["Mã SP", "Tên SP", "Số Lượng", "Đơn Giá", "Thành Tiền"], # Cố tình ẩn cột Giá công ty đi
                        col_widths=[30, 70, 20, 35, 35], 
                        total_amount=tong_cuoi
                    )
                    st.session_state['pdf_name_t1'] = f"BaoGia_{ten_kh}.pdf"
                    
                    try:
                        chi_tiet_json = df_hien_thi.to_json(orient='records')
                        ngay_gio = lay_gio_vn().strftime("%d/%m/%Y %H:%M")
                        c.execute("INSERT INTO public.lich_su_bao_gia (ngay_tao, ten_kh, so_dien_thoai, tong_tien, loai_bao_gia, chi_tiet) VALUES (%s, %s, %s, %s, %s, %s)", 
                                  (ngay_gio, ten_kh, sdt_kh, tong_cuoi, 'Tiêu chuẩn', chi_tiet_json))
                        st.success("✅ Đã chốt đơn và lưu lịch sử thành công! Vui lòng tải File PDF bên dưới.")
                    except Exception as e:
                        st.warning("⚠️ Báo giá PDF đã tạo thành công! (Lưu lịch sử đang lỗi nhẹ nhưng không ảnh hưởng)")
            else:
                st.error("⚠️ Vui lòng nhập Tên Khách Hàng để xuất file!")
                
        if 'pdf_data_t1' in st.session_state:
            st.download_button("📥 TẢI FILE BÁO GIÁ XUỐNG MÁY (PDF)", data=st.session_state['pdf_data_t1'], file_name=st.session_state['pdf_name_t1'], mime="application/pdf", type="primary", use_container_width=True)
            
        with col_btn2:
            if st.button("🗑️ Dọn dẹp giỏ hàng & Làm mới", use_container_width=True):
                if 'pdf_data_t1' in st.session_state: del st.session_state['pdf_data_t1']
                st.session_state.gio_bao_gia = []
                st.rerun()

# --- TAB 2: BÁO GIÁ TÙY CHỈNH ---
with tab2:
    st.subheader("🛠️ Tạo Báo Giá Dịch Vụ / Sản Phẩm Tự Nhập")
    c_t2_1, c_t2_2 = st.columns(2)
    ten_kh_c = c_t2_1.text_input("Tên khách hàng:", key="t2_kh")
    sdt_kh_c = c_t2_2.text_input("Số điện thoại:", key="t2_sdt")

    with st.form("add_sp_t2", clear_on_submit=True):
        col_s1, col_s2, col_s3 = st.columns([2, 1, 1])
        sp_chon_c = col_s1.text_input("Nhập Tên Sản phẩm / Dịch vụ:")
        sl_chon_c = col_s2.number_input("Số lượng", min_value=1, step=1, key="sl_c")
        gia_chon_c = col_s3.number_input("Đơn giá (VNĐ)", min_value=0, step=1000)
        
        if st.form_submit_button("Thêm vào báo giá"):
            if sp_chon_c.strip():
                st.session_state.gio_bao_gia_custom.append({
                    "Mã SP": "CUSTOM", "Tên SP": sp_chon_c, "Số Lượng": sl_chon_c, "Đơn Giá": gia_chon_c, "Thành Tiền": sl_chon_c * gia_chon_c
                })
                st.rerun()
            else:
                st.warning("Vui lòng nhập tên sản phẩm/dịch vụ!")

    if st.session_state.gio_bao_gia_custom:
        df_curr_c = pd.DataFrame(st.session_state.gio_bao_gia_custom)
        tong_cuoi_c = df_curr_c['Thành Tiền'].sum()
        
        st.dataframe(df_curr_c, use_container_width=True, hide_index=True)
        st.write(f"### 💰 TỔNG CỘNG THANH TOÁN: {format_vn(tong_cuoi_c)} VNĐ")
        
        col_btn_c1, col_btn_c2 = st.columns([2, 2])
        with col_btn_c1:
            if ten_kh_c.strip():
                if st.button("💾 CHỐT ĐƠN & TẠO FILE PDF", type="primary", use_container_width=True, key="luu_t2"):
                    st.session_state['pdf_data_t2'] = generate_generic_pdf(df_curr_c, "BÁO GIÁ", f"Khách hàng: {ten_kh_c} | SĐT: {sdt_kh_c}", ["Mã SP", "Tên SP", "Số Lượng", "Đơn Giá", "Thành Tiền"], col_widths=[30, 70, 20, 35, 35], total_amount=tong_cuoi_c)
                    st.session_state['pdf_name_t2'] = f"BaoGia_TuyChinh_{ten_kh_c}.pdf"
                    
                    try:
                        chi_tiet_json_c = df_curr_c.to_json(orient='records')
                        ngay_gio_c = lay_gio_vn().strftime("%d/%m/%Y %H:%M")
                        c.execute("INSERT INTO public.lich_su_bao_gia (ngay_tao, ten_kh, so_dien_thoai, tong_tien, loai_bao_gia, chi_tiet) VALUES (%s, %s, %s, %s, %s, %s)", 
                                  (ngay_gio_c, ten_kh_c, sdt_kh_c, tong_cuoi_c, 'Tùy chỉnh', chi_tiet_json_c))
                        st.success("✅ Đã tạo báo giá tùy chỉnh và lưu lịch sử!")
                    except Exception as e:
                        st.warning("⚠️ Báo giá PDF đã tạo thành công! Bạn có thể tải file bên dưới.")
            else:
                st.error("⚠️ Vui lòng nhập Tên Khách Hàng!")

        if 'pdf_data_t2' in st.session_state:
            st.download_button("📥 TẢI FILE BÁO GIÁ (PDF)", data=st.session_state['pdf_data_t2'], file_name=st.session_state['pdf_name_t2'], mime="application/pdf", type="primary", use_container_width=True)
            
        with col_btn_c2:
            if st.button("🗑️ Xóa sạch báo giá này", use_container_width=True, key="clear_t2"):
                if 'pdf_data_t2' in st.session_state: del st.session_state['pdf_data_t2']
                st.session_state.gio_bao_gia_custom = []
                st.rerun()

# --- TAB 3: XEM LỊCH SỬ & XUẤT LẠI ---
with tab3:
    st.subheader("📂 Danh sách Báo Giá đã lưu")
    try:
        df_his = pd.read_sql("SELECT id, ngay_tao, ten_kh, so_dien_thoai, tong_tien, loai_bao_gia, chi_tiet FROM public.lich_su_bao_gia ORDER BY id DESC", conn)
        if not df_his.empty:
            df_hien_thi_his = df_his.drop(columns=['chi_tiet'])
            st.dataframe(df_hien_thi_his, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader("🖨️ Trích Xuất Lại File PDF Cũ")
            
            options = ["-- Chọn báo giá --"]
            for _, row in df_his.iterrows():
                options.append(f"Mã {row['id']} - Khách: {row['ten_kh']} ({row['ngay_tao']})")
            
            chon_bg = st.selectbox("🔍 Chọn một báo giá bên dưới để tải lại PDF:", options)
            
            if chon_bg != "-- Chọn báo giá --":
                bg_id = int(chon_bg.split(" - ")[0].replace("Mã ", ""))
                row_data = df_his[df_his['id'] == bg_id].iloc[0]
                
                if pd.notna(row_data['chi_tiet']) and row_data['chi_tiet']:
                    df_chi_tiet = pd.DataFrame(json.loads(row_data['chi_tiet']))
                    
                    st.write(f"**Nội dung đơn hàng (Mã {bg_id}):**")
                    st.dataframe(df_chi_tiet, use_container_width=True, hide_index=True)
                    
                    # Ẩn cột Giá Công Ty (nếu có) khi xuất lại PDF cũ
                    pdf_re = generate_generic_pdf(
                        dataframe=df_chi_tiet, 
                        title="BÁO GIÁ SẢN PHẨM" if row_data['loai_bao_gia'] == 'Tiêu chuẩn' else "BÁO GIÁ", 
                        subtitle=f"Khách hàng: {row_data['ten_kh']} | SĐT: {row_data['so_dien_thoai']}", 
                        columns_to_print=["Mã SP", "Tên SP", "Số Lượng", "Đơn Giá", "Thành Tiền"], 
                        col_widths=[30, 70, 20, 35, 35],
                        total_amount=row_data['tong_tien']
                    )
                    st.download_button("📥 XUẤT LẠI FILE PDF NÀY", data=pdf_re, file_name=f"BaoGia_ReExport_{row_data['ten_kh']}.pdf", mime="application/pdf", type="primary")
                else:
                    st.warning("⚠️ Báo giá này là dữ liệu cũ, không lưu chi tiết sản phẩm nên máy không thể vẽ lại PDF được.")
        else:
            st.info("Chưa có lịch sử báo giá.")
    except Exception as e:
        st.info("Chưa có lịch sử hoặc bảng dữ liệu trống.")
