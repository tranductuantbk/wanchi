import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import os
import urllib.request
import time
from db_utils import get_connection

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG & FONT TỰ ĐỘNG
# ==========================================
FONT_FILE = "Roboto-Regular.ttf"
FONT_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"
LOGO_FILE = "logo.png"

@st.cache_resource
def download_font():
    if not os.path.exists(FONT_FILE):
        try: urllib.request.urlretrieve(FONT_URL, FONT_FILE)
        except: return False
    return True
download_font()

st.set_page_config(page_title="WANCHI Báo Giá", page_icon="🏭", layout="wide")
st.title("🏭 Hệ Thống Báo Giá Khách Hàng WANCHI")

# Kết nối qua cấu hình Neon
conn = get_connection()
c = conn.cursor()

if 'gio_bao_gia' not in st.session_state:
    st.session_state.gio_bao_gia = []
if 'gio_bao_gia_custom' not in st.session_state:
    st.session_state.gio_bao_gia_custom = []

# ==========================================
# KHỞI TẠO BẢNG DATABASE CHO CLOUD (POSTGRESQL)
# ==========================================
c.execute('''CREATE TABLE IF NOT EXISTS lich_su_bao_gia (
                id SERIAL PRIMARY KEY,
                ngay_tao TEXT,
                ten_kh TEXT,
                so_dien_thoai TEXT,
                tong_tien REAL,
                loai_bao_gia TEXT DEFAULT 'Tiêu chuẩn'
            )''')

try:
    c.execute("ALTER TABLE lich_su_bao_gia ADD COLUMN loai_bao_gia TEXT DEFAULT 'Tiêu chuẩn'")
except:
    pass

try: df_sp = pd.read_sql("SELECT ma_sp, ten_sp, gia_dai_ly FROM dm_san_pham", conn)
except: df_sp = pd.DataFrame(columns=['ma_sp', 'ten_sp', 'gia_dai_ly'])

def format_vn(value):
    try: return "{:,.0f}".format(value).replace(",", ".")
    except: return str(value)

# ==========================================
# 2. HÀM XUẤT PDF
# ==========================================
def generate_generic_pdf(dataframe, title, subtitle="", columns_to_print=None, logo_path=LOGO_FILE, col_widths=None):
    pdf = FPDF()
    pdf.add_page()
    has_font = os.path.exists(FONT_FILE)
    if has_font:
        pdf.add_font("Roboto", "", FONT_FILE, uni=True)
        pdf.set_font("Roboto", size=10)
    else: pdf.set_font("Helvetica", size=10)

    start_y = 12
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=15, y=start_y, w=45)
        start_x = 65
    else:
        start_x = 15
        pdf.set_y(start_y)
    
    pdf.set_xy(start_x, start_y + 2)
    pdf.set_font("Roboto" if has_font else "Helvetica", size=10)
    pdf.multi_cell(0, 5, "775 Võ Hữu Lợi (KCN Lê Minh Xuân 3), Xã Lê Minh Xuân, Huyện Bình Chánh, TP.HCM")
    
    current_y = pdf.get_y()
    pdf.set_xy(start_x, current_y + 1)
    pdf.cell(0, 5, "Điện thoại: 0902580828 - 0937572577", ln=True)
    pdf.ln(12) 

    pdf.set_font("Roboto" if has_font else "Helvetica", size=16)
    pdf.cell(0, 10, title, ln=True, align='C')
    if subtitle:
        pdf.set_font("Roboto" if has_font else "Helvetica", size=11)
        pdf.cell(0, 8, subtitle, ln=True, align='C')
    pdf.ln(5)

    if columns_to_print is None: columns_to_print = dataframe.columns.tolist()
    
    if col_widths is None:
        col_widths = [190 / len(columns_to_print)] * len(columns_to_print)
    
    pdf.set_font("Roboto" if has_font else "Helvetica", size=10)
    pdf.set_fill_color(230, 230, 230)
    for i, col in enumerate(columns_to_print):
        pdf.cell(col_widths[i], 10, col, border=1, align='C', fill=True)
    pdf.ln()

    pdf.set_font("Roboto" if has_font else "Helvetica", size=9)
    for _, row in dataframe.iterrows():
        for i, col in enumerate(columns_to_print):
            val = row[col]
            display_val = format_vn(val) if isinstance(val, (int, float)) else str(val)
            pdf.cell(col_widths[i], 9, display_val, border=1, align='C' if not isinstance(val, (int, float)) else 'R')
        pdf.ln()

    pdf.ln(8)
    pdf.set_font("Roboto" if has_font else "Helvetica", size=10)
    pdf.cell(0, 6, "* Phiếu báo giá có giá trị trong 10 ngày", ln=True)
    pdf.cell(0, 6, "* Đơn giá trên không bao gồm phí vận chuyển", ln=True)

    pdf.ln(12)
    pdf.set_font("Roboto" if has_font else "Helvetica", size=11)
    pdf.cell(95, 6, "KHÁCH HÀNG KÝ TÊN", align='C')
    pdf.cell(95, 6, "NGƯỜI LẬP PHIẾU", align='C', ln=True)
    
    pdf.set_font("Roboto" if has_font else "Helvetica", size=9)
    pdf.cell(95, 5, "(Ký, ghi rõ họ/tên)", align='C')
    pdf.cell(95, 5, "(Ký, ghi rõ họ/tên)", align='C', ln=True)

    return bytes(pdf.output())

# ==========================================
# 3. GIAO DIỆN 3 TAB
# ==========================================
tab1, tab2, tab3 = st.tabs(["🤝 1. Báo Giá Chuẩn (Có Chiết Khấu)", "🛠️ 2. Báo Giá Theo Đơn Tùy Chỉnh", "📂 3. Lịch Sử Báo Giá"])

# --- TAB 1: BÁO GIÁ CHUẨN ---
with tab1:
    st.subheader("Báo giá sản phẩm có sẵn & Tự động chiết khấu")
    col_k1, col_k2 = st.columns(2)
    with col_k1: ten_kh_chot = st.text_input("Tên khách hàng / Đơn vị (*):", key="kh1")
    with col_k2: sdt_chot = st.text_input("Số điện thoại liên hệ:", key="sdt1")

    st.markdown("---")
    with st.form("form_chon_sp", clear_on_submit=True):
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            list_sp = df_sp['ten_sp'].tolist() if not df_sp.empty else []
            sp_chon = st.selectbox("Chọn Sản phẩm từ kho", ["-- Chọn sản phẩm --"] + list_sp)
        with col_s2: sl_chon = st.number_input("Số lượng", min_value=1, step=1)
        
        if st.form_submit_button("⬇️ Thêm vào bảng báo giá", type="primary") and sp_chon != "-- Chọn sản phẩm --":
            thong_tin = df_sp[df_sp['ten_sp'] == sp_chon].iloc[0]
            st.session_state.gio_bao_gia.append({
                "Mã SP": thong_tin['ma_sp'], "Tên SP": sp_chon, "Số Lượng": sl_chon, "Giá Đại Lý (VNĐ)": thong_tin['gia_dai_ly']
            })
            st.rerun()

    if len(st.session_state.gio_bao_gia) > 0:
        df_bg = pd.DataFrame(st.session_state.gio_bao_gia)
        df_bg.insert(0, "Xóa", False) 
        
        edited_bg = st.data_editor(df_bg, column_config={"Xóa": st.column_config.CheckboxColumn("🗑️ Xóa", default=False), "Mã SP": st.column_config.TextColumn("Mã SP", disabled=True), "Tên SP": st.column_config.TextColumn("Tên SP", disabled=True), "Giá Đại Lý (VNĐ)": st.column_config.NumberColumn("Giá Đại Lý", disabled=True, format="%d"), "Số Lượng": st.column_config.NumberColumn("Số Lượng", min_value=1, format="%d")}, use_container_width=True, hide_index=True)

        if st.button("🔄 Cập nhật thay đổi bảng", key="btn_upd1"):
            st.session_state.gio_bao_gia = edited_bg[edited_bg["Xóa"] == False].drop(columns=["Xóa"]).to_dict('records')
            st.rerun()

        st.markdown("---")
        df_tinh_toan = pd.DataFrame(st.session_state.gio_bao_gia)
        gia_ny_goc = (df_tinh_toan["Giá Đại Lý (VNĐ)"] / 0.6)
        tong_niem_yet = (gia_ny_goc * df_tinh_toan["Số Lượng"]).sum()
        
        if tong_niem_yet < 3000000: hs_ck, mo_ta = 1.0, "Dưới 3tr ➡️ Không chiết khấu (100% giá)"
        elif 3000000 <= tong_niem_yet < 6000000: hs_ck, mo_ta = 0.95, "Từ 3tr - 6tr ➡️ Giảm 5% (Nhân 0.95)"
        elif 6000000 <= tong_niem_yet < 9000000: hs_ck, mo_ta = 0.9, "Từ 6tr - 9tr ➡️ Giảm 10% (Nhân 0.9)"
        elif 9000000 <= tong_niem_yet < 12000000: hs_ck, mo_ta = 0.85, "Từ 9tr - 12tr ➡️ Giảm 15% (Nhân 0.85)"
        else: hs_ck, mo_ta = 0.8, "Trên 12 triệu ➡️ Giảm 20% (Nhân 0.8)"

        st.info(f"📊 **Mức chiết khấu áp dụng:** {mo_ta}")
        df_tinh_toan["Đơn Giá"] = (gia_ny_goc * hs_ck).round(0)
        df_tinh_toan["Thành Tiền"] = df_tinh_toan["Đơn Giá"] * df_tinh_toan["Số Lượng"]
        tong_cuoi = df_tinh_toan["Thành Tiền"].sum()
        
        st.subheader(f"💰 TỔNG CỘNG THANH TOÁN: {format_vn(tong_cuoi)} VNĐ")
        
        col_pdf1, col_pdf2 = st.columns(2)
        with col_pdf1:
            if st.button("💾 CHỐT & XUẤT BÁO GIÁ", type="primary", use_container_width=True, key="btn_chot1"):
                if not ten_kh_chot.strip(): st.error("⚠️ Vui lòng nhập tên khách hàng!")
                else:
                    pdf_bytes = generate_generic_pdf(
                        df_tinh_toan, 
                        "PHIẾU BÁO GIÁ KHÁCH HÀNG", 
                        f"Khách hàng: {ten_kh_chot} | SĐT: {sdt_chot} | Tổng: {format_vn(tong_cuoi)}đ", 
                        columns_to_print=["Mã SP", "Tên SP", "Số Lượng", "Đơn Giá", "Thành Tiền"],
                        col_widths=[30, 75, 25, 30, 30] 
                    )
                    try:
                        c.execute("INSERT INTO lich_su_bao_gia (ngay_tao, ten_kh, so_dien_thoai, tong_tien, loai_bao_gia) VALUES (%s, %s, %s, %s, %s)", (datetime.now().strftime("%Y-%m-%d %H:%M"), ten_kh_chot, sdt_chot, tong_cuoi, 'Tiêu chuẩn'))
                        st.session_state.gio_bao_gia = [] 
                        st.success("✅ Đã tạo Báo giá và lưu vào hệ thống!")
                        st.download_button("📥 TẢI FILE BÁO GIÁ (PDF)", pdf_bytes, f"BaoGia_{ten_kh_chot}.pdf", "application/pdf")
                    except Exception as e: st.error(f"Lỗi: {e}")

        with col_pdf2:
            if st.button("🗑️ Làm mới lại toàn bộ", use_container_width=True, key="btn_del1"):
                st.session_state.gio_bao_gia = []
                st.rerun()

# --- TAB 2: BÁO GIÁ ĐƠN ĐẶT HÀNG (TÙY CHỈNH) ---
with tab2:
    st.subheader("Báo giá linh hoạt (Tự đặt tên SP, Tự quyết định giá)")
    
    col_c1, col_c2 = st.columns(2)
    with col_c1: ten_kh_custom = st.text_input("Tên khách hàng / Đơn vị (* Bắt buộc):", key="kh2")
    with col_c2: sdt_custom = st.text_input("Số điện thoại liên hệ:", key="sdt2")

    st.markdown("---")
    
    st.markdown("**Bước 1: Thêm sản phẩm vào bảng**")
    with st.form("form_custom", clear_on_submit=True):
        col_m1, col_m2, col_m3, col_m4 = st.columns([2, 2, 1, 1.5])
        with col_m1:
            sp_kho_chua = st.selectbox("Lấy sản phẩm mẫu từ kho:", ["-- Không lấy, tự đặt tên --"] + list_sp)
        with col_m2:
            sp_tu_dat = st.text_input("Hoặc tự đặt Tên Sản Phẩm mới:")
        with col_m3:
            sl_custom = st.number_input("Số lượng", min_value=1, step=1, key="sl2")
        with col_m4:
            gia_custom = st.number_input("Đơn giá (VNĐ)", min_value=0.0, step=1000.0)
            
        if st.form_submit_button("⬇️ Thêm vào bảng", type="primary"):
            ten_sp_final = sp_tu_dat.strip() if sp_tu_dat.strip() else sp_kho_chua
            
            if ten_sp_final == "-- Không lấy, tự đặt tên --" or not ten_sp_final:
                st.warning("⚠️ Vui lòng chọn sản phẩm từ kho hoặc gõ Tên Sản Phẩm mới!")
            else:
                st.session_state.gio_bao_gia_custom.append({
                    "Tên Sản Phẩm": ten_sp_final,
                    "Số Lượng": sl_custom,
                    "Đơn Giá (Tùy chỉnh)": gia_custom
                })
                st.rerun()

    if len(st.session_state.gio_bao_gia_custom) > 0:
        st.markdown("**Bước 2: Căn chỉnh lại Báo giá**")
        df_custom = pd.DataFrame(st.session_state.gio_bao_gia_custom)
        df_custom.insert(0, "Xóa", False)
        
        edited_custom = st.data_editor(
            df_custom,
            column_config={
                "Xóa": st.column_config.CheckboxColumn("🗑️ Xóa", default=False),
                "Tên Sản Phẩm": st.column_config.TextColumn("Tên Sản Phẩm (Click để sửa)"),
                "Số Lượng": st.column_config.NumberColumn("Số Lượng", min_value=1, format="%d"),
                "Đơn Giá (Tùy chỉnh)": st.column_config.NumberColumn("Đơn Giá", min_value=0.0, format="%d")
            },
            use_container_width=True, hide_index=True
        )

        if st.button("🔄 Cập nhật lại Bảng & Tính tiền", key="btn_upd2"):
            df_sau_sua_c = edited_custom[edited_custom["Xóa"] == False].drop(columns=["Xóa"])
            st.session_state.gio_bao_gia_custom = df_sau_sua_c.to_dict('records')
            st.rerun()

        st.markdown("---")
        df_tinh_custom = pd.DataFrame(st.session_state.gio_bao_gia_custom)
        df_tinh_custom["Thành Tiền"] = df_tinh_custom["Đơn Giá (Tùy chỉnh)"] * df_tinh_custom["Số Lượng"]
        tong_tien_custom = df_tinh_custom["Thành Tiền"].sum()

        st.subheader(f"💰 TỔNG CỘNG ĐƠN HÀNG: {format_vn(tong_tien_custom)} VNĐ")
        
        col_pdf_c1, col_pdf_c2 = st.columns(2)
        with col_pdf_c1:
            if st.button("💾 CHỐT & XUẤT BÁO GIÁ ĐƠN HÀNG", type="primary", use_container_width=True, key="btn_chot2"):
                if not ten_kh_custom.strip(): 
                    st.error("⚠️ Vui lòng nhập tên khách hàng ở Mục 1!")
                else:
                    pdf_bytes_c = generate_generic_pdf(
                        df_tinh_custom, 
                        "BÁO GIÁ ĐƠN ĐẶT HÀNG", 
                        f"Khách hàng: {ten_kh_custom} | SĐT: {sdt_custom} | Tổng: {format_vn(tong_tien_custom)}đ", 
                        columns_to_print=["Tên Sản Phẩm", "Số Lượng", "Đơn Giá (Tùy chỉnh)", "Thành Tiền"],
                        col_widths=[95, 25, 35, 35] 
                    )
                    
                    try:
                        c.execute("INSERT INTO lich_su_bao_gia (ngay_tao, ten_kh, so_dien_thoai, tong_tien, loai_bao_gia) VALUES (%s, %s, %s, %s, %s)", (datetime.now().strftime("%Y-%m-%d %H:%M"), ten_kh_custom, sdt_custom, tong_tien_custom, 'Đơn tùy chỉnh'))
                        st.session_state.gio_bao_gia_custom = [] 
                        st.success("✅ Đã tạo Báo giá Tùy chỉnh và lưu vào hệ thống!")
                        st.download_button("📥 TẢI FILE BÁO GIÁ (PDF)", pdf_bytes_c, f"BaoGia_DonHang_{ten_kh_custom}.pdf", "application/pdf")
                    except Exception as e: st.error(f"Lỗi: {e}")

        with col_pdf_c2:
            if st.button("🗑️ Làm mới lại toàn bộ", use_container_width=True, key="btn_del2"):
                st.session_state.gio_bao_gia_custom = []
                st.rerun()

# --- TAB 3: TRÍCH XUẤT & XÓA LỊCH SỬ BÁO GIÁ ---
with tab3:
    st.subheader("🔍 Trích Xuất & Xóa Lịch Sử Báo Giá")
    col_tim1, col_tim2 = st.columns(2)
    with col_tim1: tim_ten = st.text_input("Nhập Tên khách hàng để tìm:")
    with col_tim2: tim_sdt = st.text_input("Nhập Số điện thoại để tìm:")
        
    try:
        query = "SELECT id, ngay_tao, ten_kh, so_dien_thoai, tong_tien, loai_bao_gia FROM lich_su_bao_gia WHERE 1=1"
        params = []
        if tim_ten:
            query += " AND ten_kh LIKE %s"
            params.append(f"%{tim_ten}%")
        if tim_sdt:
            query += " AND so_dien_thoai LIKE %s"
            params.append(f"%{tim_sdt}%")
        query += " ORDER BY id DESC"
        
        df_ls = pd.read_sql(query, conn, params=params)
        
        if not df_ls.empty:
            df_ls.insert(0, "Xóa", False)
            edited_ls = st.data_editor(df_ls, key="bang_lich_su_bao_gia", column_config={"Xóa": st.column_config.CheckboxColumn("🗑️ Xóa", default=False), "id": None, "ngay_tao": st.column_config.TextColumn("Ngày Tạo", disabled=True), "ten_kh": st.column_config.TextColumn("Khách Hàng", disabled=True), "so_dien_thoai": st.column_config.TextColumn("Số Điện Thoại", disabled=True), "tong_tien": st.column_config.NumberColumn("Tổng Báo Giá", format="%d", disabled=True), "loai_bao_gia": st.column_config.TextColumn("Loại Báo Giá", disabled=True)}, use_container_width=True, hide_index=True)
            
            if st.button("🚨 Xóa Báo Giá Đã Chọn", type="primary"):
                try:
                    so_luong_xoa = 0
                    for index, row in edited_ls.iterrows():
                        if row['Xóa'] == True:
                            c.execute("DELETE FROM lich_su_bao_gia WHERE id=%s", (int(row['id']),))
                            so_luong_xoa += 1
                    if so_luong_xoa > 0:
                        st.success(f"✅ Đã xóa {so_luong_xoa} báo giá!")
                        time.sleep(1.5)
                        st.rerun()
                except Exception as e: st.error(f"Lỗi: {e}")
        else: st.info("Không tìm thấy dữ liệu.")
    except Exception as e: st.info("Chưa có lịch sử.")
