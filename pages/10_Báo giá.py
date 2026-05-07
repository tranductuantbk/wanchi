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
# BỘ HÀM CALLBACK
# ---------------------------------------------------------
if 't1_kh' not in st.session_state: st.session_state['t1_kh'] = ""
if 't1_sdt' not in st.session_state: st.session_state['t1_sdt'] = ""
if 't2_kh' not in st.session_state: st.session_state['t2_kh'] = ""
if 't2_sdt' not in st.session_state: st.session_state['t2_sdt'] = ""
if 'gio_bao_gia' not in st.session_state: st.session_state.gio_bao_gia = []
if 'gio_bao_gia_custom' not in st.session_state: st.session_state.gio_bao_gia_custom = []

def clear_t1():
    st.session_state['edit_bg_data'] = None
    st.session_state.gio_bao_gia = []
    st.session_state['t1_kh'] = ""
    st.session_state['t1_sdt'] = ""
    if 'pdf_data_t1' in st.session_state: del st.session_state['pdf_data_t1']

def clear_t2():
    st.session_state['edit_bg_custom_data'] = None
    st.session_state.gio_bao_gia_custom = []
    st.session_state['t2_kh'] = ""
    st.session_state['t2_sdt'] = ""
    if 'pdf_data_t2' in st.session_state: del st.session_state['pdf_data_t2']

def nap_du_lieu_sua(row_dict, chi_tiet_list, is_chuan):
    if is_chuan:
        st.session_state['edit_bg_data'] = row_dict
        st.session_state.gio_bao_gia = chi_tiet_list
        st.session_state['t1_kh'] = str(row_dict.get('ten_kh', ''))
        st.session_state['t1_sdt'] = str(row_dict.get('so_dien_thoai', ''))
    else:
        st.session_state['edit_bg_custom_data'] = row_dict
        st.session_state.gio_bao_gia_custom = chi_tiet_list
        st.session_state['t2_kh'] = str(row_dict.get('ten_kh', ''))
        st.session_state['t2_sdt'] = str(row_dict.get('so_dien_thoai', ''))

# LẤY GIÁ TỪ KHO (Lấy chuẩn cột gia_khach_le)
try: 
    df_sp = pd.read_sql("SELECT ma_sp, ten_sp, gia_dai_ly, gia_khach_le FROM public.dm_san_pham", conn)
except: 
    df_sp = pd.DataFrame(columns=['ma_sp', 'ten_sp', 'gia_dai_ly', 'gia_khach_le'])

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
tab1, tab2, tab3 = st.tabs(["🤝 Báo Giá", "🛠️ Báo Giá Tùy Chỉnh", "📂 Lịch Sử & Xuất Lại"])

# --- TAB 1: BÁO GIÁ TỪ DANH MỤC ---
with tab1:
    edit_bg = st.session_state.get('edit_bg_data', None)
    is_edit = edit_bg is not None

    if is_edit:
        st.warning(f"🛠️ **CHẾ ĐỘ SỬA CHỮA BÁO GIÁ:** Đang chỉnh sửa phiếu **{edit_bg['ma_bao_gia']}**.")
        st.button("❌ Hủy chỉnh sửa (Quay về Tạo mới)", key="cancel_t1", on_click=clear_t1)
    else:
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
                
                # SỬA LỖI: Lấy trực tiếp Giá Công Ty từ Danh mục sản phẩm (Giá A)
                gia_cty_goc = info.get('gia_khach_le', 0)
                
                st.session_state.gio_bao_gia.append({
                    "Mã SP": info['ma_sp'], 
                    "Tên SP": sp_chon, 
                    "Số Lượng": sl_chon, 
                    "Giá công ty": gia_cty_goc,  # Giá A làm gốc
                    "Đơn Giá": 0 
                })
                
                # TÍNH LẠI CHIẾT KHẤU THEO TỔNG ĐƠN (Dựa trên Giá công ty A)
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
        df_curr['Thành Tiền'] = df_curr['Số Lượng'] * df_curr['Đơn Giá']
        
        edited_df = st.data_editor(
            df_curr,
            column_config={
                "Mã SP": st.column_config.TextColumn("Mã SP", disabled=True),
                "Tên SP": st.column_config.TextColumn("Tên SP", disabled=True),
                "Giá công ty": st.column_config.NumberColumn("Giá công ty (Gốc Danh mục)", disabled=True),
                "Số Lượng": st.column_config.NumberColumn("Số Lượng", min_value=1, step=1),
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
        
        # Phần Lưu & Xuất PDF giữ nguyên logic cũ
        col_btn1, col_btn2 = st.columns([2, 2])
        with col_btn1:
            if ten_kh.strip():
                if st.button("💾 CHỐT ĐƠN & TẠO FILE PDF", type="primary", use_container_width=True):
                    ngay_gio_obj = lay_gio_vn()
                    ma_bg = f"BG{ngay_gio_obj.strftime('%y%m%d%H%M')}"
                    ngay_gio_str = ngay_gio_obj.strftime("%d/%m/%Y %H:%M")
                    
                    st.session_state['pdf_data_t1'] = generate_generic_pdf(
                        df_hien_thi, "BÁO GIÁ SẢN PHẨM", f"Mã phiếu: {ma_bg} | Khách hàng: {ten_kh} | SĐT: {sdt_kh}", 
                        ["Mã SP", "Tên SP", "Số Lượng", "Đơn Giá", "Thành Tiền"], col_widths=[30, 70, 20, 35, 35], total_amount=tong_cuoi
                    )
                    st.session_state['pdf_name_t1'] = f"{ma_bg}_{ten_kh}.pdf"
                    
                    try:
                        chi_tiet_json = df_hien_thi.to_json(orient='records')
                        c.execute("INSERT INTO public.lich_su_bao_gia (ma_bao_gia, ngay_tao, ten_kh, so_dien_thoai, tong_tien, loai_bao_gia, chi_tiet) VALUES (%s, %s, %s, %s, %s, %s, %s)", 
                                  (ma_bg, ngay_gio_str, ten_kh, sdt_kh, tong_cuoi, 'Tiêu chuẩn', chi_tiet_json))
                        conn.commit()
                        st.success(f"✅ Đã chốt báo giá {ma_bg}!")
                    except: conn.rollback()
            else: st.error("⚠️ Vui lòng nhập Tên Khách Hàng!")
                
        if 'pdf_data_t1' in st.session_state:
            st.download_button("📥 TẢI FILE BÁO GIÁ (PDF)", data=st.session_state['pdf_data_t1'], file_name=st.session_state['pdf_name_t1'], mime="application/pdf", type="primary", use_container_width=True)
        with col_btn2: st.button("🗑️ Dọn dẹp giỏ hàng", use_container_width=True, on_click=clear_t1)
