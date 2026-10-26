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
# 1. CẤU HÌNH FONT & DATABASE
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

st.title("🏭 Hệ Thống Báo Giá Khách Hàng WANCHI")

conn = get_connection()
c = conn.cursor()

# ---------------------------------------------------------
# KHỞI TẠO BẢNG DỮ LIỆU
# ---------------------------------------------------------
try:
    c.execute("CREATE SCHEMA IF NOT EXISTS public;")
    conn.commit()
except: conn.rollback()

try:
    c.execute('''CREATE TABLE IF NOT EXISTS public.lich_su_bao_gia (
                    id SERIAL PRIMARY KEY,
                    ma_bao_gia TEXT,
                    ngay_tao TEXT,
                    ten_kh TEXT,
                    so_dien_thoai TEXT,
                    tong_tien REAL,
                    loai_bao_gia TEXT DEFAULT 'Tiêu chuẩn',
                    chi_tiet TEXT
                )''')
    conn.commit()
except: conn.rollback()

# Đảm bảo các cột mới tồn tại
try: c.execute("ALTER TABLE public.lich_su_bao_gia ADD COLUMN IF NOT EXISTS chi_tiet TEXT"); conn.commit()
except: conn.rollback()

try: c.execute("ALTER TABLE public.lich_su_bao_gia ADD COLUMN IF NOT EXISTS ma_bao_gia TEXT"); conn.commit()
except: conn.rollback()

def don_dep_lich_su():
    try:
        c.execute("""DELETE FROM public.lich_su_bao_gia 
                     WHERE id NOT IN (
                         SELECT id FROM public.lich_su_bao_gia 
                         ORDER BY id DESC LIMIT 50
                     )""")
        conn.commit()
    except Exception as e: conn.rollback()

# LẤY GIÁ TỪ KHO
try: df_sp = pd.read_sql("SELECT ma_sp, ten_sp, quy_cach_loc, gia_dai_ly, gia_khach_le FROM public.dm_san_pham", conn)
except: df_sp = pd.DataFrame(columns=['ma_sp', 'ten_sp', 'quy_cach_loc', 'gia_dai_ly', 'gia_khach_le'])

# LẤY DANH BẠ KHÁCH HÀNG TỪ KHO
try: df_kh = pd.read_sql("SELECT ten_kh, so_dien_thoai FROM public.dm_khach_hang", conn)
except: df_kh = pd.DataFrame(columns=['ten_kh', 'so_dien_thoai'])

# ---------------------------------------------------------
# BỘ HÀM CALLBACK VÀ BIẾN TRẠNG THÁI
# ---------------------------------------------------------
if 't1_kh' not in st.session_state: st.session_state['t1_kh'] = ""
if 't1_sdt' not in st.session_state: st.session_state['t1_sdt'] = ""
if 'gio_bao_gia' not in st.session_state: st.session_state.gio_bao_gia = []

def clear_t1():
    st.session_state['edit_bg_data'] = None
    st.session_state.gio_bao_gia = []
    st.session_state['t1_kh'] = ""
    st.session_state['t1_sdt'] = ""
    if 'pdf_data_t1' in st.session_state: del st.session_state['pdf_data_t1']
    if 'img_data_t1' in st.session_state: del st.session_state['img_data_t1']

def nap_du_lieu_sua(row_dict, chi_tiet_list):
    st.session_state['edit_bg_data'] = row_dict
    st.session_state.gio_bao_gia = chi_tiet_list
    st.session_state['t1_kh'] = str(row_dict.get('ten_kh', ''))
    st.session_state['t1_sdt'] = str(row_dict.get('so_dien_thoai', ''))

def format_vn(value):
    try: return "{:,.0f}".format(value).replace(",", ".")
    except: return str(value)

# --- HÀM TÍNH CHIẾT KHẤU THEO MỐC ---
def tinh_chiet_khau_theo_tong(tong_niem_yet):
    if tong_niem_yet < 3000000: return 1.0          # Không giảm
    elif tong_niem_yet < 5000000: return 0.97       # Giảm 3%
    elif tong_niem_yet < 8000000: return 0.94       # Giảm 6%
    elif tong_niem_yet < 12000000: return 0.90      # Giảm 10%
    elif tong_niem_yet < 16000000: return 0.87      # Giảm 13%
    elif tong_niem_yet < 20000000: return 0.84      # Giảm 16%
    else: return 0.80                               # Giảm 20%

# ==========================================
# 2. HÀM XUẤT PDF AN TOÀN
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
    
    try: return bytes(pdf.output())
    except:
        out = pdf.output(dest='S')
        return out.encode('latin-1') if isinstance(out, str) else bytes(out)

# ==========================================
# 3. GIAO DIỆN CHÍNH
# ==========================================
tab1, tab2 = st.tabs(["🤝 Báo Giá", "📂 Lịch Sử & Xuất Lại"])

# --- TAB 1: BÁO GIÁ TỪ DANH MỤC ---
with tab1:
    edit_bg = st.session_state.get('edit_bg_data', None)
    is_edit = edit_bg is not None

    if is_edit:
        st.warning(f"🛠️ **CHẾ ĐỘ SỬA CHỮA BÁO GIÁ:** Đang chỉnh sửa phiếu **{edit_bg['ma_bao_gia']}**.")
        st.button("❌ Hủy chỉnh sửa (Quay về Tạo mới)", key="cancel_t1", on_click=clear_t1)
        c1, c2 = st.columns(2)
        ten_kh = c1.text_input("Tên khách hàng:", value=st.session_state.get('t1_kh', ''), key="t1_kh_edit")
        sdt_kh = c2.text_input("Số điện thoại:", value=st.session_state.get('t1_sdt', ''), key="t1_sdt_edit")
    else:
        st.subheader("Tạo báo giá từ danh mục có sẵn")
        
        kh_list = ["-- Khách mới (Tự nhập) --"] + df_kh['ten_kh'].tolist() if not df_kh.empty else ["-- Khách mới (Tự nhập) --"]
        chon_kh = st.selectbox("🙋‍♂️ Chọn khách hàng từ danh bạ:", kh_list, key="t1_chon_kh")
        
        c1, c2 = st.columns(2)
        if chon_kh == "-- Khách mới (Tự nhập) --":
            ten_kh = c1.text_input("Tên khách hàng:", key="t1_kh")
            sdt_kh = c2.text_input("Số điện thoại:", key="t1_sdt")
        else:
            sdt_cu = df_kh[df_kh['ten_kh'] == chon_kh].iloc[0].get('so_dien_thoai', '') if not df_kh[df_kh['ten_kh'] == chon_kh].empty else ""
            ten_kh = c1.text_input("Tên khách hàng:", value=chon_kh, key="t1_kh_old")
            sdt_kh = c2.text_input("Số điện thoại:", value=sdt_cu, key="t1_sdt_old")

    st.markdown("---")
    
    col_s1, col_s2 = st.columns([3, 1])
    sp_list = df_sp['ten_sp'].tolist() if not df_sp.empty else []
    sp_chon = col_s1.selectbox("Chọn sản phẩm", ["-- Chọn --"] + sp_list, key="t1_chon_sp")
    
    so_loc_chon = col_s2.number_input("📦 Số Lốc:", min_value=1, step=1, key="t1_sl_loc")
    
    tong_so_cai = 0
    quy_cach_loc = 1
    
    if sp_chon != "-- Chọn --":
        info_sp = df_sp[df_sp['ten_sp'] == sp_chon].iloc[0]
        try:
            quy_cach_loc = int(info_sp.get('quy_cach_loc', 1))
        except:
            quy_cach_loc = 1
        if pd.isna(quy_cach_loc) or quy_cach_loc <= 0:
            quy_cach_loc = 1
            
        tong_so_cai = so_loc_chon * quy_cach_loc
        
        st.info(f"👉 **Hệ thống tự tính:** {so_loc_chon} lốc (Quy cách đóng gói: **{quy_cach_loc} cái/lốc**) = **Xuất {tong_so_cai} cái**")
        st.success("✅ Số lượng đã đảm bảo chẵn lốc.")
            
    if st.button("Thêm vào danh sách", type="secondary"):
        if sp_chon == "-- Chọn --":
            st.error("⚠️ Vui lòng chọn sản phẩm!")
        elif tong_so_cai == 0:
            st.error("⚠️ Vui lòng nhập Số Lốc hợp lệ!")
        else:
            info = df_sp[df_sp['ten_sp'] == sp_chon].iloc[0]
            gia_cty_goc = info.get('gia_khach_le', 0)
            
            st.session_state.gio_bao_gia.append({
                "Mã SP": info['ma_sp'], 
                "Tên SP": sp_chon, 
                "Số Lượng": tong_so_cai, 
                "Giá công ty": gia_cty_goc,  
                "Đơn Giá": 0 
            })
            
            tong_niem_yet = sum([item['Giá công ty'] * item['Số Lượng'] for item in st.session_state.gio_bao_gia])
            ck = tinh_chiet_khau_theo_tong(tong_niem_yet)
            for item in st.session_state.gio_bao_gia:
                item['Đơn Giá'] = int(round(item['Giá công ty'] * ck, -1)) 
            st.rerun()

    if st.session_state.gio_bao_gia:
        st.markdown("---")
        if st.button("🔄 TỰ ĐỘNG TÍNH LẠI CHIẾT KHẤU THEO TỔNG ĐƠN MỚI NHẤT", type="secondary"):
            tong_niem_yet = sum([item['Giá công ty'] * item['Số Lượng'] for item in st.session_state.gio_bao_gia])
            ck = tinh_chiet_khau_theo_tong(tong_niem_yet)
            
            for item in st.session_state.gio_bao_gia:
                item['Đơn Giá'] = int(round(item['Giá công ty'] * ck, -1))
            st.success(f"✅ Đã áp dụng mức chiết khấu mới dựa trên Giá Danh Mục: Giảm {round((1-ck)*100, 1)}%")
            time.sleep(1.5)
            st.rerun()
            
        df_curr = pd.DataFrame(st.session_state.gio_bao_gia)
        st.info("💡 **Mẹo Pro:** Cột Số Lượng hiển thị là tổng số cái. Nếu số lượng đổi làm thay đổi mốc, hãy bấm nút 🔄 TÍNH LẠI phía trên. Hoặc bạn có thể **nhấp đúp** vào cột Đơn Giá để sửa tay!")
        
        df_curr['Thành Tiền'] = df_curr['Số Lượng'] * df_curr['Đơn Giá']
        
        edited_df = st.data_editor(
            df_curr,
            column_config={
                "Mã SP": st.column_config.TextColumn("Mã SP", disabled=True),
                "Tên SP": st.column_config.TextColumn("Tên SP", disabled=True),
                "Giá công ty": st.column_config.NumberColumn("Giá công ty (Gốc Danh mục)", disabled=True),
                "Số Lượng": st.column_config.NumberColumn("Số lượng cái (Tổng)", min_value=1, step=1, disabled=True),
                "Đơn Giá": st.column_config.NumberColumn("Đơn Giá (Sau CK)", min_value=0, step=1000),
                "Thành Tiền": st.column_config.NumberColumn("Thành Tiền", disabled=True)
            },
            hide_index=True,
            use_container_width=True,
            key="editor_bg1"
        )
        
        edited_df['Thành Tiền'] = edited_df['Số Lượng'] * edited_df['Đơn Giá']
        tong_cuoi = float(edited_df['Thành Tiền'].sum())
        
        st.session_state.gio_bao_gia = edited_df[["Mã SP", "Tên SP", "Số Lượng", "Giá công ty", "Đơn Giá"]].to_dict('records')
        df_hien_thi = edited_df[["Mã SP", "Tên SP", "Số Lượng", "Giá công ty", "Đơn Giá", "Thành Tiền"]]
        
        st.write(f"### 💰 TỔNG CỘNG: {format_vn(tong_cuoi)} VNĐ")
        
        # BỔ SUNG LỰA CHỌN LOẠI FILE XUẤT 
        st.markdown("**📁 Tùy chọn xuất file:**")
        loai_xuat_t1 = st.radio(
            "Lựa chọn định dạng để tạo Báo giá:", 
            ["Chỉ xuất file PDF", "Chỉ xuất file Ảnh (PNG)", "Xuất cả PDF và Ảnh"], 
            horizontal=True, 
            key="radio_xuat_t1",
            index=1 # Mặc định chọn Chỉ xuất Ảnh
        )
        
        col_btn1, col_btn2 = st.columns([2, 2])
        with col_btn1:
            if ten_kh.strip():
                btn_label = "🔄 CẬP NHẬT & TẠO FILE" if is_edit else "💾 CHỐT ĐƠN & TẠO FILE"
                if st.button(btn_label, type="primary", use_container_width=True, key="luu_t1"):
                    
                    if is_edit:
                        ma_bg = edit_bg['ma_bao_gia']
                        ngay_gio_str = edit_bg['ngay_tao']
                    else:
                        ngay_gio_obj = lay_gio_vn()
                        ma_bg = f"BG{ngay_gio_obj.strftime('%y%m%d%H%M')}"
                        ngay_gio_str = ngay_gio_obj.strftime("%d/%m/%Y %H:%M")
                    
                    # Bỏ cột "Giá công ty" ra khỏi PDF
                    st.session_state['pdf_data_t1'] = generate_generic_pdf(
                        df_hien_thi, "BÁO GIÁ SẢN PHẨM", f"Mã phiếu: {ma_bg} | Khách hàng: {ten_kh} | SĐT: {sdt_kh}", 
                        ["Mã SP", "Tên SP", "Số Lượng", "Đơn Giá", "Thành Tiền"], col_widths=[30, 70, 20, 35, 35], total_amount=tong_cuoi)
                    st.session_state['pdf_name_t1'] = f"{ma_bg}_{ten_kh}.pdf"
                    
                    # Tự động render luôn cả hình ảnh vào bộ nhớ ảo
                    img_data = convert_pdf_to_png(st.session_state['pdf_data_t1'])
                    if img_data:
                        st.session_state['img_data_t1'] = img_data
                    
                    try:
                        chi_tiet_json = df_hien_thi.to_json(orient='records')
                        if is_edit:
                            c.execute("""UPDATE public.lich_su_bao_gia SET ten_kh=%s, so_dien_thoai=%s, tong_tien=%s, chi_tiet=%s WHERE id=%s""", 
                                      (ten_kh, sdt_kh, tong_cuoi, chi_tiet_json, edit_bg['id']))
                            conn.commit()
                            st.success(f"✅ Đã CẬP NHẬT báo giá {ma_bg} thành công! Tải file bên dưới.")
                            clear_t1()
                        else:
                            c.execute("""INSERT INTO public.lich_su_bao_gia (ma_bao_gia, ngay_tao, ten_kh, so_dien_thoai, tong_tien, loai_bao_gia, chi_tiet) VALUES (%s, %s, %s, %s, %s, %s, %s)""", 
                                      (ma_bg, ngay_gio_str, ten_kh, sdt_kh, tong_cuoi, 'Tiêu chuẩn', chi_tiet_json))
                            conn.commit()
                            don_dep_lich_su()
                            st.success(f"✅ Đã chốt báo giá {ma_bg}! Vui lòng tải file bên dưới.")
                    except Exception as e:
                        conn.rollback()
                        st.warning(f"⚠️ Lỗi Database: {e}")
            else:
                st.error("⚠️ Vui lòng nhập Tên Khách Hàng!")
        
        with col_btn2:
            st.button("🗑️ Dọn dẹp giỏ hàng & Làm mới", use_container_width=True, on_click=clear_t1)
                
        # HIỂN THỊ CÁC NÚT TẢI XUỐNG DỰA THEO LỰA CHỌN
        if 'pdf_data_t1' in st.session_state:
            st.markdown("---")
            col_dl1, col_dl2 = st.columns(2)
            
            # Button tải PDF
            if "PDF" in loai_xuat_t1 or "Cả" in loai_xuat_t1:
                with col_dl1:
                    st.download_button("📥 TẢI FILE PDF CHUẨN", data=st.session_state['pdf_data_t1'], file_name=st.session_state['pdf_name_t1'], mime="application/pdf", type="primary", use_container_width=True)
            
            # Button tải Ảnh
            if ("Ảnh" in loai_xuat_t1 or "Cả" in loai_xuat_t1) and st.session_state.get('img_data_t1'):
                with col_dl2:
                    img_name = st.session_state['pdf_name_t1'].replace('.pdf', '.png')
                    st.download_button("🖼️ TẢI FILE ẢNH BÁO GIÁ", data=st.session_state['img_data_t1'], file_name=img_name, mime="image/png", type="primary", use_container_width=True)

# --- TAB 2: XEM LỊCH SỬ & XUẤT LẠI ---
with tab2:
    st.subheader("📂 50 Phiếu Báo Giá Gần Nhất")
    try:
        df_his = pd.read_sql("SELECT id, ma_bao_gia, ngay_tao, ten_kh, so_dien_thoai, tong_tien, loai_bao_gia, chi_tiet FROM public.lich_su_bao_gia ORDER BY id DESC LIMIT 50", conn)
        if not df_his.empty:
            df_hien_thi_his = df_his.drop(columns=['chi_tiet'])
            df_hien_thi_his['ma_bao_gia'] = df_hien_thi_his['ma_bao_gia'].fillna("Mã Cũ")
            st.dataframe(df_hien_thi_his, use_container_width=True, hide_index=True)
            st.markdown("---")
            st.subheader("🖨️ Thao tác với Lịch Sử Cũ")
            
            options = ["-- Chọn báo giá --"]
            for _, row in df_his.iterrows():
                ma_hien_thi = row['ma_bao_gia'] if pd.notna(row['ma_bao_gia']) else f"Mã ID-{row['id']}"
                options.append(f"[{ma_hien_thi}] Khách: {row['ten_kh']} ({row['ngay_tao']})")
            
            chon_bg = st.selectbox("🔍 Chọn một báo giá bên dưới để tải PDF/Ảnh hoặc Chỉnh sửa:", options)
            if chon_bg != "-- Chọn báo giá --":
                ma_tim_kiem = chon_bg.split("] ")[0].replace("[", "")
                if "Mã ID-" in ma_tim_kiem: row_data = df_his[df_his['id'] == int(ma_tim_kiem.replace("Mã ID-", ""))].iloc[0]
                else: row_data = df_his[df_his['ma_bao_gia'] == ma_tim_kiem].iloc[0]
                
                if pd.notna(row_data['chi_tiet']) and row_data['chi_tiet']:
                    df_chi_tiet = pd.DataFrame(json.loads(row_data['chi_tiet']))
                    st.write(f"**Nội dung phiếu (Mã {ma_tim_kiem}):**")
                    st.dataframe(df_chi_tiet, use_container_width=True, hide_index=True)
                    
                    # Bổ sung lựa chọn định dạng cho Lịch sử
                    loai_xuat_his = st.radio("Lựa chọn định dạng để XUẤT LẠI:", ["Chỉ xuất PDF", "Chỉ xuất Ảnh (PNG)", "Cả PDF và Ảnh"], horizontal=True, key=f"radio_his_{ma_tim_kiem}", index=1)
                    
                    col_his1, col_his2 = st.columns(2)
                    with col_his1:
                        # Đảm bảo PDF in lại chuẩn
                        pdf_re = generate_generic_pdf(
                            dataframe=df_chi_tiet, 
                            title="BÁO GIÁ SẢN PHẨM" if row_data['loai_bao_gia'] == 'Tiêu chuẩn' else "BÁO GIÁ DỊCH VỤ", 
                            subtitle=f"Mã phiếu: {ma_tim_kiem} | Khách hàng: {row_data['ten_kh']} | SĐT: {row_data['so_dien_thoai']}", 
                            columns_to_print=["Mã SP", "Tên SP", "Số Lượng", "Đơn Giá", "Thành Tiền"], 
                            col_widths=[30, 70, 20, 35, 35], 
                            total_amount=row_data['tong_tien']
                        )
                        
                        pdf_name_re = f"{ma_tim_kiem}_ReExport_{row_data['ten_kh']}.pdf"
                        if "PDF" in loai_xuat_his or "Cả" in loai_xuat_his:
                            st.download_button("📥 XUẤT LẠI FILE PDF", data=pdf_re, file_name=pdf_name_re, mime="application/pdf", type="primary", use_container_width=True)
                        
                        if "Ảnh" in loai_xuat_his or "Cả" in loai_xuat_his:
                            img_re = convert_pdf_to_png(pdf_re)
                            if img_re:
                                img_name_re = pdf_name_re.replace('.pdf', '.png')
                                st.download_button("🖼️ XUẤT LẠI FILE ẢNH", data=img_re, file_name=img_name_re, mime="image/png", type="primary", use_container_width=True)
                    
                    with col_his2:
                        st.write("") # Cân dòng
                        is_chuan_flag = (row_data['loai_bao_gia'] == 'Tiêu chuẩn')
                        if is_chuan_flag:
                            if st.button("🛠️ Nạp dữ liệu để Chỉnh Sửa", type="primary", use_container_width=True, on_click=nap_du_lieu_sua, args=(row_data.to_dict(), json.loads(row_data['chi_tiet']))):
                                st.success("✅ Đã nạp thành công! Hãy tải lại trang để sửa.")
                        else:
                            st.info("⚠️ Báo giá tùy chỉnh cũ chỉ có thể xem và xuất lại, không hỗ trợ chỉnh sửa nữa.")
                else: st.warning("⚠️ Báo giá này là dữ liệu cũ, không lưu chi tiết sản phẩm nên máy không thể vẽ lại PDF hoặc chỉnh sửa được.")
        else: st.info("Chưa có lịch sử báo giá.")
    except Exception as e:
        conn.rollback()
        st.info(f"Chưa có lịch sử hoặc bảng dữ liệu trống. ({e})")
