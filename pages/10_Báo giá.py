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
# BỘ HÀM CALLBACK: TRỊ DỨT ĐIỂM LỖI WIDGET INSTANTIATED
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

# KHỞI TẠO BẢNG
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

try: c.execute("ALTER TABLE public.lich_su_bao_gia ADD COLUMN chi_tiet TEXT"); conn.commit()
except: conn.rollback()

try: c.execute("ALTER TABLE public.lich_su_bao_gia ADD COLUMN ma_bao_gia TEXT"); conn.commit()
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
try: df_sp = pd.read_sql("SELECT ma_sp, ten_sp, gia_dai_ly, gia_khach_le FROM public.dm_san_pham", conn)
except: df_sp = pd.DataFrame(columns=['ma_sp', 'ten_sp', 'gia_dai_ly', 'gia_khach_le'])

def format_vn(value):
    try: return "{:,.0f}".format(value).replace(",", ".")
    except: return str(value)

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
    except Exception:
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
                
                # ===============================================
                # ĐÃ SỬA CÔNG THỨC: GIÁ CÔNG TY = GIÁ ĐẠI LÝ / 0.55
                # ===============================================
                gia_goc = info.get('gia_dai_ly', 0)
                gia_cty_chuan = gia_goc / 0.55 if gia_goc > 0 else info.get('gia_khach_le', 0)
                
                st.session_state.gio_bao_gia.append({
                    "Mã SP": info['ma_sp'], 
                    "Tên SP": sp_chon, 
                    "Số Lượng": sl_chon, 
                    "Giá Gốc": gia_goc,
                    "Giá công ty": int(round(gia_cty_chuan, -1)),
                    "Đơn Giá": 0 
                })
                
                # TÍNH LẠI TOÀN BỘ THEO 7 MỐC MỚI NHẤT
                tong_goc = sum([(item.get('Giá Gốc', 0) / 0.55) * item.get('Số Lượng', 1) for item in st.session_state.gio_bao_gia])
                
                if tong_goc < 3000000: ck = 1.0          # Mốc 1: Dưới 3tr (Không giảm)
                elif tong_goc < 5000000: ck = 0.98       # Mốc 2: Từ 3tr đến <5tr (Giảm 2%)
                elif tong_goc < 8000000: ck = 0.95       # Mốc 3: Từ 5tr đến <8tr (Giảm 5%)
                elif tong_goc < 12000000: ck = 0.92      # Mốc 4: Từ 8tr đến <12tr (Giảm 8%)
                elif tong_goc < 16000000: ck = 0.90      # Mốc 5: Từ 12tr đến <16tr (Giảm 10%)
                elif tong_goc < 20000000: ck = 0.88      # Mốc 6: Từ 16tr đến <20tr (Giảm 12%)
                else: ck = 0.85                          # Mốc 7: Từ 20tr trở lên (Giảm 15%)
                
                for item in st.session_state.gio_bao_gia:
                    g_cty = item.get('Giá Gốc', 0) / 0.55 if item.get('Giá Gốc', 0) > 0 else item.get('Giá công ty', 0)
                    item['Đơn Giá'] = int(round(g_cty * ck, -1)) 
                    item['Giá công ty'] = int(round(g_cty, -1))
                    
                st.rerun()

    if st.session_state.gio_bao_gia:
        st.markdown("---")
        if st.button("🔄 TỰ ĐỘNG TÍNH LẠI CHIẾT KHẤU THEO TỔNG ĐƠN MỚI NHẤT", type="secondary"):
            tong_goc = sum([(item.get('Giá Gốc', 0) / 0.55) * item.get('Số Lượng', 1) for item in st.session_state.gio_bao_gia])
            
            # Cập nhật thuật toán tính lại cho Nút (7 mốc)
            if tong_goc < 3000000: ck = 1.0
            elif tong_goc < 5000000: ck = 0.98
            elif tong_goc < 8000000: ck = 0.95
            elif tong_goc < 12000000: ck = 0.92
            elif tong_goc < 16000000: ck = 0.90
            elif tong_goc < 20000000: ck = 0.88
            else: ck = 0.85
            
            for item in st.session_state.gio_bao_gia:
                g_cty = item.get('Giá Gốc', 0) / 0.55 if item.get('Giá Gốc', 0) > 0 else item.get('Giá công ty', 0)
                item['Đơn Giá'] = int(round(g_cty * ck, -1))
                item['Giá công ty'] = int(round(g_cty, -1))
            st.success(f"✅ Đã quét lại toàn bộ giỏ hàng và áp dụng mức chiết khấu: Giảm {round((1-ck)*100, 1)}%")
            time.sleep(1.5)
            st.rerun()
            
        df_curr = pd.DataFrame(st.session_state.gio_bao_gia)
        st.info("💡 **Mẹo Pro:** Nếu số lượng đổi làm thay đổi mốc, hãy bấm nút 🔄 TÍNH LẠI phía trên. Hoặc bạn có thể **nhấp đúp** vào cột Đơn Giá để sửa tay!")
        
        df_curr['Thành Tiền'] = df_curr['Số Lượng'] * df_curr['Đơn Giá']
        
        edited_df = st.data_editor(
            df_curr,
            column_config={
                "Mã SP": st.column_config.TextColumn("Mã SP", disabled=True),
                "Tên SP": st.column_config.TextColumn("Tên SP", disabled=True),
                "Giá Gốc": None, 
                "Giá công ty": st.column_config.NumberColumn("Giá công ty (Tham khảo)", disabled=True),
                "Số Lượng": st.column_config.NumberColumn("Số Lượng", min_value=1, step=1),
                "Đơn Giá": st.column_config.NumberColumn("Đơn Giá (Chỉnh sửa được)", min_value=0, step=1000),
                "Thành Tiền": st.column_config.NumberColumn("Thành Tiền", disabled=True)
            },
            hide_index=True,
            use_container_width=True,
            key="editor_bg1"
        )
        
        edited_df['Thành Tiền'] = edited_df['Số Lượng'] * edited_df['Đơn Giá']
        tong_cuoi = float(edited_df['Thành Tiền'].sum())
        
        st.session_state.gio_bao_gia = edited_df[["Mã SP", "Tên SP", "Số Lượng", "Giá Gốc", "Giá công ty", "Đơn Giá"]].to_dict('records')
        df_hien_thi = edited_df[["Mã SP", "Tên SP", "Số Lượng", "Giá công ty", "Đơn Giá", "Thành Tiền"]]
        
        st.write(f"### 💰 TỔNG CỘNG: {format_vn(tong_cuoi)} VNĐ")
        
        col_btn1, col_btn2 = st.columns([2, 2])
        with col_btn1:
            if ten_kh.strip():
                btn_label = "🔄 CẬP NHẬT BÁO GIÁ & TẠO LẠI PDF" if is_edit else "💾 CHỐT ĐƠN & TẠO FILE PDF"
                if st.button(btn_label, type="primary", use_container_width=True, key="luu_t1"):
                    
                    if is_edit:
                        ma_bg = edit_bg['ma_bao_gia']
                        ngay_gio_str = edit_bg['ngay_tao']
                    else:
                        ngay_gio_obj = lay_gio_vn()
                        ma_bg = f"BG{ngay_gio_obj.strftime('%y%m%d%H%M')}"
                        ngay_gio_str = ngay_gio_obj.strftime("%d/%m/%Y %H:%M")
                    
                    st.session_state['pdf_data_t1'] = generate_generic_pdf(
                        df_hien_thi, 
                        "BÁO GIÁ SẢN PHẨM", 
                        f"Mã phiếu: {ma_bg} | Khách hàng: {ten_kh} | SĐT: {sdt_kh}", 
                        ["Mã SP", "Tên SP", "Số Lượng", "Đơn Giá", "Thành Tiền"], 
                        col_widths=[30, 70, 20, 35, 35], 
                        total_amount=tong_cuoi
                    )
                    st.session_state['pdf_name_t1'] = f"{ma_bg}_{ten_kh}.pdf"
                    
                    try:
                        chi_tiet_json = df_hien_thi.to_json(orient='records')
                        if is_edit:
                            c.execute("""UPDATE public.lich_su_bao_gia 
                                         SET ten_kh=%s, so_dien_thoai=%s, tong_tien=%s, chi_tiet=%s 
                                         WHERE id=%s""", 
                                      (ten_kh, sdt_kh, tong_cuoi, chi_tiet_json, edit_bg['id']))
                            conn.commit()
                            st.success(f"✅ Đã CẬP NHẬT báo giá {ma_bg} thành công! Tải PDF bên dưới.")
                            clear_t1()
                        else:
                            c.execute("""INSERT INTO public.lich_su_bao_gia 
                                         (ma_bao_gia, ngay_tao, ten_kh, so_dien_thoai, tong_tien, loai_bao_gia, chi_tiet) 
                                         VALUES (%s, %s, %s, %s, %s, %s, %s)""", 
                                      (ma_bg, ngay_gio_str, ten_kh, sdt_kh, tong_cuoi, 'Tiêu chuẩn', chi_tiet_json))
                            conn.commit()
                            don_dep_lich_su()
                            st.success(f"✅ Đã chốt báo giá {ma_bg}! Vui lòng tải File PDF bên dưới.")
                    except Exception as e:
                        conn.rollback()
                        st.warning(f"⚠️ Báo giá PDF đã tạo thành công! (Nhưng không lưu được lịch sử: {e})")
            else:
                st.error("⚠️ Vui lòng nhập Tên Khách Hàng!")
                
        if 'pdf_data_t1' in st.session_state:
            st.download_button("📥 TẢI FILE BÁO GIÁ XUỐNG MÁY (PDF)", data=st.session_state['pdf_data_t1'], file_name=st.session_state['pdf_name_t1'], mime="application/pdf", type="primary", use_container_width=True)
            
        with col_btn2:
            st.button("🗑️ Dọn dẹp giỏ hàng & Làm mới", use_container_width=True, on_click=clear_t1)

# --- TAB 2: BÁO GIÁ TÙY CHỈNH ---
with tab2:
    edit_bg_c = st.session_state.get('edit_bg_custom_data', None)
    is_edit_c = edit_bg_c is not None

    if is_edit_c:
        st.warning(f"🛠️ **CHẾ ĐỘ SỬA CHỮA TÙY CHỈNH:** Đang chỉnh sửa phiếu **{edit_bg_c['ma_bao_gia']}**.")
        st.button("❌ Hủy chỉnh sửa (Quay về Tạo mới)", key="cancel_t2", on_click=clear_t2)
    else:
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
                    "Mã SP": "CUSTOM", "Tên SP": sp_chon_c, "Số Lượng": sl_chon_c, "Đơn Giá": gia_chon_c
                })
                st.rerun()
            else:
                st.warning("Vui lòng nhập tên sản phẩm/dịch vụ!")

    if st.session_state.gio_bao_gia_custom:
        for item in st.session_state.gio_bao_gia_custom:
            if 'Đơn Giá' not in item: item['Đơn Giá'] = 0

        df_curr_c = pd.DataFrame(st.session_state.gio_bao_gia_custom)
        st.info("💡 **Mẹo Pro:** Bạn có thể **nhấp đúp chuột** vào cột **Số Lượng** và **Đơn Giá** bên dưới để sửa lại!")
        
        df_curr_c['Thành Tiền'] = df_curr_c['Số Lượng'] * df_curr_c['Đơn Giá']
        
        edited_df_c = st.data_editor(
            df_curr_c,
            column_config={
                "Mã SP": st.column_config.TextColumn(disabled=True),
                "Tên SP": st.column_config.TextColumn(disabled=True),
                "Số Lượng": st.column_config.NumberColumn("Số Lượng", min_value=1, step=1),
                "Đơn Giá": st.column_config.NumberColumn("Đơn Giá", min_value=0, step=1000),
                "Thành Tiền": st.column_config.NumberColumn("Thành Tiền", disabled=True)
            },
            hide_index=True, use_container_width=True, key="editor_bg2"
        )
        
        edited_df_c['Thành Tiền'] = edited_df_c['Số Lượng'] * edited_df_c['Đơn Giá']
        tong_cuoi_c = float(edited_df_c['Thành Tiền'].sum())
        
        st.session_state.gio_bao_gia_custom = edited_df_c[["Mã SP", "Tên SP", "Số Lượng", "Đơn Giá"]].to_dict('records')
        df_hien_thi_c = edited_df_c[["Mã SP", "Tên SP", "Số Lượng", "Đơn Giá", "Thành Tiền"]]
        
        st.write(f"### 💰 TỔNG CỘNG THANH TOÁN: {format_vn(tong_cuoi_c)} VNĐ")
        
        col_btn_c1, col_btn_c2 = st.columns([2, 2])
        with col_btn_c1:
            if ten_kh_c.strip():
                btn_label_c = "🔄 CẬP NHẬT BÁO GIÁ & TẠO LẠI PDF" if is_edit_c else "💾 CHỐT ĐƠN & TẠO FILE PDF"
                if st.button(btn_label_c, type="primary", use_container_width=True, key="luu_t2"):
                    if is_edit_c:
                        ma_bg_c = edit_bg_c['ma_bao_gia']
                        ngay_gio_str_c = edit_bg_c['ngay_tao']
                    else:
                        ngay_gio_obj_c = lay_gio_vn()
                        ma_bg_c = f"BGC{ngay_gio_obj_c.strftime('%y%m%d%H%M')}"
                        ngay_gio_str_c = ngay_gio_obj_c.strftime("%d/%m/%Y %H:%M")

                    st.session_state['pdf_data_t2'] = generate_generic_pdf(
                        df_hien_thi_c, "BÁO GIÁ DỊCH VỤ", f"Mã phiếu: {ma_bg_c} | Khách hàng: {ten_kh_c} | SĐT: {sdt_kh_c}", 
                        ["Mã SP", "Tên SP", "Số Lượng", "Đơn Giá", "Thành Tiền"], col_widths=[30, 70, 20, 35, 35], total_amount=tong_cuoi_c)
                    st.session_state['pdf_name_t2'] = f"{ma_bg_c}_{ten_kh_c}.pdf"
                    
                    try:
                        chi_tiet_json_c = df_hien_thi_c.to_json(orient='records')
                        if is_edit_c:
                            c.execute("""UPDATE public.lich_su_bao_gia SET ten_kh=%s, so_dien_thoai=%s, tong_tien=%s, chi_tiet=%s WHERE id=%s""", 
                                      (ten_kh_c, sdt_kh_c, tong_cuoi_c, chi_tiet_json_c, edit_bg_c['id']))
                            conn.commit()
                            st.success(f"✅ Đã CẬP NHẬT báo giá {ma_bg_c} thành công! Tải PDF bên dưới.")
                            clear_t2()
                        else:
                            c.execute("""INSERT INTO public.lich_su_bao_gia (ma_bao_gia, ngay_tao, ten_kh, so_dien_thoai, tong_tien, loai_bao_gia, chi_tiet) VALUES (%s, %s, %s, %s, %s, %s, %s)""", 
                                      (ma_bg_c, ngay_gio_str_c, ten_kh_c, sdt_kh_c, tong_cuoi_c, 'Tùy chỉnh', chi_tiet_json_c))
                            conn.commit()
                            don_dep_lich_su()
                            st.success(f"✅ Đã chốt báo giá {ma_bg_c}!")
                    except Exception as e:
                        conn.rollback() 
                        st.warning(f"⚠️ Lỗi Database: {e}")
            else: st.error("⚠️ Vui lòng nhập Tên Khách Hàng!")

        if 'pdf_data_t2' in st.session_state:
            st.download_button("📥 TẢI FILE BÁO GIÁ (PDF)", data=st.session_state['pdf_data_t2'], file_name=st.session_state['pdf_name_t2'], mime="application/pdf", type="primary", use_container_width=True)
            
        with col_btn_c2: st.button("🗑️ Xóa sạch báo giá này", use_container_width=True, key="clear_t2", on_click=clear_t2)

# --- TAB 3: XEM LỊCH SỬ & XUẤT LẠI ---
with tab3:
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
            
            chon_bg = st.selectbox("🔍 Chọn một báo giá bên dưới để tải PDF hoặc Chỉnh sửa:", options)
            if chon_bg != "-- Chọn báo giá --":
                ma_tim_kiem = chon_bg.split("] ")[0].replace("[", "")
                if "Mã ID-" in ma_tim_kiem: row_data = df_his[df_his['id'] == int(ma_tim_kiem.replace("Mã ID-", ""))].iloc[0]
                else: row_data = df_his[df_his['ma_bao_gia'] == ma_tim_kiem].iloc[0]
                
                if pd.notna(row_data['chi_tiet']) and row_data['chi_tiet']:
                    df_chi_tiet = pd.DataFrame(json.loads(row_data['chi_tiet']))
                    st.write(f"**Nội dung phiếu (Mã {ma_tim_kiem}):**")
                    st.dataframe(df_chi_tiet, use_container_width=True, hide_index=True)
                    
                    col_his1, col_his2 = st.columns(2)
                    with col_his1:
                        pdf_re = generate_generic_pdf(dataframe=df_chi_tiet, title="BÁO GIÁ SẢN PHẨM" if row_data['loai_bao_gia'] == 'Tiêu chuẩn' else "BÁO GIÁ", subtitle=f"Mã phiếu: {ma_tim_kiem} | Khách hàng: {row_data['ten_kh']} | SĐT: {row_data['so_dien_thoai']}", columns_to_print=["Mã SP", "Tên SP", "Số Lượng", "Đơn Giá", "Thành Tiền"], col_widths=[30, 70, 20, 35, 35], total_amount=row_data['tong_tien'])
                        st.download_button("📥 XUẤT LẠI FILE PDF NÀY", data=pdf_re, file_name=f"{ma_tim_kiem}_ReExport_{row_data['ten_kh']}.pdf", mime="application/pdf", type="primary", use_container_width=True)
                    
                    with col_his2:
                        is_chuan_flag = (row_data['loai_bao_gia'] == 'Tiêu chuẩn')
                        if st.button("🛠️ Nạp dữ liệu để Chỉnh Sửa", type="primary", use_container_width=True, on_click=nap_du_lieu_sua, args=(row_data.to_dict(), json.loads(row_data['chi_tiet']), is_chuan_flag)):
                            if is_chuan_flag: st.success("✅ Đã nạp thành công! Hãy bấm sang Tab '🤝 Báo Giá' để sửa.")
                            else: st.success("✅ Đã nạp thành công! Hãy bấm sang Tab '🛠️ Báo Giá Tùy Chỉnh' để sửa.")
                else: st.warning("⚠️ Báo giá này là dữ liệu cũ, không lưu chi tiết sản phẩm nên máy không thể vẽ lại PDF hoặc chỉnh sửa được.")
        else: st.info("Chưa có lịch sử báo giá.")
    except Exception as e:
        conn.rollback()
        st.info(f"Chưa có lịch sử hoặc bảng dữ liệu trống. ({e})")
