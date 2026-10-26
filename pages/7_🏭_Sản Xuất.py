import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta, timezone
import time
from fpdf import FPDF
import os
import urllib.request
from db_utils import get_connection, check_password

# ==========================================
# CẤU HÌNH MÚI GIỜ & FONT CHỮ (FIX LỖI UNICODE)
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
        page = doc.load_page(0) # Lấy trang đầu tiên
        pix = page.get_pixmap(dpi=200) # dpi=200 cho ảnh xuất ra nét
        return pix.tobytes("png")
    except Exception as e:
        st.error(f"Lỗi khi chuyển đổi ảnh: {e}")
        return None

st.set_page_config(page_title="Quản Lý Sản Xuất", page_icon="🏭", layout="wide")

# ==========================================
# Ổ KHÓA BẢO VỆ 2 LỚP
# ==========================================
role = check_password()
if not role: st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang này chỉ dành cho Quản lý WANCHI.")
    st.stop()

st.header("🏭 Hệ Thống Điều Hành & Kế Hoạch Máy Ép")
conn = get_connection()
c = conn.cursor()

# ==========================================
# TỰ ĐỘNG KHỞI TẠO BẢNG 
# ==========================================
try:
    c.execute("CREATE SCHEMA IF NOT EXISTS public;")
    
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_may_ep (
                    id SERIAL PRIMARY KEY, ten_may TEXT UNIQUE, loai_may TEXT
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS public.ke_hoach_sx_ngay (
                    id SERIAL PRIMARY KEY,
                    ngay TEXT, tuan TEXT, may_ep TEXT, san_pham TEXT, so_luong REAL DEFAULT 0
                )''')
                
    c.execute('''CREATE TABLE IF NOT EXISTS public.ke_hoach_tang_ca (
                    tuan TEXT PRIMARY KEY, ghi_chu TEXT
                )''')
                
    # Thêm cột Đổi Thùng vào bảng kế hoạch
    c.execute("ALTER TABLE public.ke_hoach_sx_ngay ADD COLUMN IF NOT EXISTS doi_thung TEXT DEFAULT 'Tất cả'")
    
    conn.commit()
except Exception as e: 
    conn.rollback()

# Lấy dữ liệu Sản phẩm & Máy ép & Nhân viên đóng gói
try: 
    df_sp_chuan = pd.read_sql("SELECT ten_sp FROM public.dm_san_pham", conn)
    df_sp_ome = pd.read_sql("SELECT ten_sp FROM public.dm_san_pham_ome", conn)
    list_sp = pd.concat([df_sp_chuan, df_sp_ome])['ten_sp'].tolist()
except: list_sp = []
if not list_sp: list_sp = ["-- Chưa có Sản Phẩm --"]

try: df_may = pd.read_sql("SELECT ten_may FROM public.dm_may_ep", conn)
except: df_may = pd.DataFrame(columns=['ten_may'])
list_may = df_may['ten_may'].tolist() if not df_may.empty else ["Vui lòng thêm máy ở Tab 2"]

# Lấy danh sách nhân viên từ bảng nhan_vien có bộ phận đóng gói
try:
    df_ns = pd.read_sql("SELECT ten_nv FROM public.nhan_vien WHERE bo_phan ILIKE '%đóng gói%'", conn)
    list_nv_dong_goi = df_ns['ten_nv'].tolist() if not df_ns.empty else []
except:
    list_nv_dong_goi = []
list_doi_thung = ["Tất cả"] + list_nv_dong_goi

# ==========================================
# GIAO DIỆN 2 TABS 
# ==========================================
tab1, tab3 = st.tabs(["📅 Quản Lý Kế Hoạch & Tải Ảnh", "⚙️ Quản Lý Máy Ép"])

# ------------------------------------------
# TAB 1: BẢNG TÍNH EXCEL LÊN KẾ HOẠCH & XUẤT ẢNH
# ------------------------------------------
with tab1:
    st.subheader("KẾ HOẠCH SẢN XUẤT (Ma trận Excel)")
    
    # 1. BỘ CHỌN TUẦN VÀ TÍNH TOÁN NGÀY
    ngay_chon = st.date_input("🗓️ Chọn một ngày bất kỳ để nạp bảng kế hoạch của Tuần đó:", lay_gio_vn().date())
    
    start_of_week = ngay_chon - timedelta(days=ngay_chon.weekday())
    dates = [start_of_week + timedelta(days=i) for i in range(7)]
    
    date_cols = [d.strftime('%d/%m') for d in dates] 
    db_dates = [d.strftime('%Y-%m-%d') for d in dates] 
    
    tuan_iso = start_of_week.isocalendar()
    tuan_str = f"{tuan_iso[0]}-W{tuan_iso[1]:02d}"

    col_t1, col_t2 = st.columns([1, 1])
    col_t1.markdown(f"**Từ ngày:** `{date_cols[0]}/{start_of_week.year}` &nbsp;&nbsp;➔&nbsp;&nbsp; **đến:** `{date_cols[-1]}/{dates[-1].year}`")
    
    try:
        c.execute("SELECT ghi_chu FROM public.ke_hoach_tang_ca WHERE tuan=%s", (tuan_str,))
        tc_res = c.fetchone()
        tc_val = tc_res[0] if tc_res else ""
    except: tc_val = ""
    
    danh_sach_thu = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
    tc_default = [x.strip() for x in tc_val.split(",")] if tc_val else []
    tc_default = [x for x in tc_default if x in danh_sach_thu] 
    
    tang_ca_list = col_t2.multiselect(
        "🌙 Lịch tăng ca tuần này (Nhấp để chọn):", 
        options=danh_sach_thu, 
        default=tc_default
    )
    tang_ca_str = ", ".join(tang_ca_list) 
    
    st.markdown("---")
    st.info("💡 **Ghi chú:** Bảng luôn ở chế độ sẵn sàng cập nhật. Hãy nhập dữ liệu, sau đó bấm nút LƯU KẾ HOẠCH ở dưới cùng.")

    try:
        df_week = pd.read_sql(f"SELECT ngay, may_ep, san_pham, so_luong, doi_thung FROM public.ke_hoach_sx_ngay WHERE ngay >= '{db_dates[0]}' AND ngay <= '{db_dates[-1]}'", conn)
    except:
        df_week = pd.DataFrame(columns=["ngay", "may_ep", "san_pham", "so_luong", "doi_thung"])

    edited_dfs = {}
    
    # 2. VẼ BẢNG EXCEL CHO TỪNG MÁY
    if list_may == ["Vui lòng thêm máy ở Tab 2"]:
        st.warning("⚠️ Chưa có Máy Ép nào. Vui lòng sang Tab Cài Đặt (⚙️) để thêm máy trước!")
    else:
        for may in list_may:
            st.markdown(f"<h5 style='color:#b30000; margin-top: 15px;'>KẾ HOẠCH CHẠY MÁY: {may.upper()}</h5>", unsafe_allow_html=True)
            
            df_m = df_week[df_week['may_ep'] == may]
            records = []
            
            if not df_m.empty:
                for sp, group in df_m.groupby('san_pham'):
                    row = {"Sản Phẩm": sp}
                    for d in date_cols: row[d] = None 
                    
                    dt_val = "Tất cả"
                    if 'doi_thung' in group.columns:
                        dt_list = group['doi_thung'].dropna().tolist()
                        if dt_list: dt_val = dt_list[0]
                    row["Đổi Thùng"] = dt_val
                    
                    for _, r in group.iterrows():
                        try:
                            idx = db_dates.index(r['ngay'])
                            if r['so_luong'] > 0: row[date_cols[idx]] = float(r['so_luong'])
                        except: pass
                    records.append(row)
                    
            if len(records) == 0:
                empty_row = {"Sản Phẩm": None}
                for d in date_cols: empty_row[d] = None
                empty_row["Đổi Thùng"] = "Tất cả"
                records = [empty_row.copy() for _ in range(2)]
                
            df_table = pd.DataFrame(records)
            
            col_cfg = {"Sản Phẩm": st.column_config.SelectboxColumn("Sản Phẩm", options=list_sp, width="large")}
            for d in date_cols:
                col_cfg[d] = st.column_config.NumberColumn(d, min_value=0.0, format="%g", width="small")
            col_cfg["Đổi Thùng"] = st.column_config.SelectboxColumn("Đổi Thùng", options=list_doi_thung, default="Tất cả", width="medium")
                
            edited_dfs[may] = st.data_editor(
                df_table, num_rows="dynamic", column_config=col_cfg, 
                hide_index=True, key=f"ed_{may}_{tuan_str}", use_container_width=True
            )

        # 3. NÚT CHỐT LƯU VÀ XUẤT ẢNH
        st.markdown("---")
        col_btn1, col_btn2 = st.columns([1, 1])
        
        with col_btn1:
            if st.button("💾 LƯU KẾ HOẠCH", type="primary", use_container_width=True):
                try:
                    c.execute("INSERT INTO public.ke_hoach_tang_ca (tuan, ghi_chu) VALUES (%s, %s) ON CONFLICT (tuan) DO UPDATE SET ghi_chu=EXCLUDED.ghi_chu", (tuan_str, tang_ca_str))
                    c.execute("DELETE FROM public.ke_hoach_sx_ngay WHERE ngay >= %s AND ngay <= %s", (db_dates[0], db_dates[-1]))
                    
                    for may, edf in edited_dfs.items():
                        for _, row in edf.iterrows():
                            sp = row.get("Sản Phẩm")
                            if not sp or pd.isna(sp) or sp == "-- Chưa có Sản Phẩm --": continue
                            
                            dt_val = row.get("Đổi Thùng", "Tất cả")
                            
                            for i, d_col in enumerate(date_cols):
                                sl = row.get(d_col)
                                if pd.notna(sl) and sl > 0:
                                    c.execute("""INSERT INTO public.ke_hoach_sx_ngay 
                                                 (ngay, tuan, may_ep, san_pham, so_luong, doi_thung) 
                                                 VALUES (%s, %s, %s, %s, %s, %s)""",
                                              (db_dates[i], tuan_str, may, sp, float(sl), dt_val))
                    conn.commit()
                    st.success("✅ Đã lưu toàn bộ kế hoạch vào hệ thống thành công!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"Lỗi khi lưu Database: {e}")

        # TỰ ĐỘNG TẠO ẢNH NẾU ĐÃ CÓ DỮ LIỆU
        df_in = pd.read_sql(f"SELECT ngay, may_ep, san_pham, so_luong, doi_thung FROM public.ke_hoach_sx_ngay WHERE tuan = '{tuan_str}'", conn)
        if not df_in.empty:
            df_in['ngay_dt'] = pd.to_datetime(df_in['ngay'])
            df_in['thu'] = df_in['ngay_dt'].dt.weekday.map({0:'T2', 1:'T3', 2:'T4', 3:'T5', 4:'T6', 5:'T7', 6:'CN'})
            
            tu_ngay_str = start_of_week.strftime("%d/%m/%Y")
            den_ngay_str = dates[-1].strftime("%d/%m/%Y")

            pivot_df = df_in.pivot_table(index=['may_ep', 'san_pham'], columns='thu', values='so_luong', aggfunc='sum').fillna(0).reset_index()
            for col in ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']:
                if col not in pivot_df.columns: pivot_df[col] = 0.0

            df_dt = df_in.groupby(['may_ep', 'san_pham'])['doi_thung'].first().reset_index()
            pivot_df = pd.merge(pivot_df, df_dt, on=['may_ep', 'san_pham'], how='left')
            pivot_df['doi_thung'] = pivot_df['doi_thung'].fillna('Tất cả')

            try:
                c.execute("SELECT ghi_chu FROM public.ke_hoach_tang_ca WHERE tuan=%s", (tuan_str,))
                tc_res_pdf = c.fetchone()
                tc_pdf = tc_res_pdf[0] if tc_res_pdf and tc_res_pdf[0] else "Không có"
            except: tc_pdf = "Không có"

            # TẠO PDF NGẦM ĐỂ XUẤT ẢNH
            pdf = FPDF(orientation='L', format='A4') 
            pdf.add_page()
            
            has_font = False
            if os.path.exists("Roboto-Regular.ttf"):
                pdf.add_font("Roboto", "", "Roboto-Regular.ttf", uni=True)
                pdf.add_font("Roboto", "B", "Roboto-Regular.ttf", uni=True)
                font_name = "Roboto"
                has_font = True
            else: font_name = "Helvetica"
                
            pdf.set_font(font_name, "B" if has_font else "", 16)
            pdf.set_text_color(180, 0, 0) 
            pdf.cell(0, 10, "KẾ HOẠCH SẢN XUẤT", align="C", ln=True)
            pdf.set_font(font_name, "", 12)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 6, f"Từ ngày: {tu_ngay_str}    đến: {den_ngay_str}", align="C", ln=True)
            
            pdf.set_font(font_name, "", 11)
            pdf.cell(0, 8, f"Các ngày dự kiến tăng ca: {tc_pdf}", align="C", ln=True)
            pdf.ln(3)
            
            w_sp = 90
            w_day = 20
            w_dt = 35
            
            cac_may = pivot_df['may_ep'].unique()
            for may in cac_may:
                pdf.set_font(font_name, "B" if has_font else "", 10)
                pdf.set_fill_color(0, 128, 0)
                pdf.set_text_color(255, 140, 0)
                
                pdf.cell(w_sp, 8, f"KẾ HOẠCH CHẠY MÁY: {may.upper()}", border=1, fill=True)
                pdf.cell(w_day, 8, "Thứ 2", border=1, align="C", fill=True)
                pdf.cell(w_day, 8, "Thứ 3", border=1, align="C", fill=True)
                pdf.cell(w_day, 8, "Thứ 4", border=1, align="C", fill=True)
                pdf.cell(w_day, 8, "Thứ 5", border=1, align="C", fill=True)
                pdf.cell(w_day, 8, "Thứ 6", border=1, align="C", fill=True)
                pdf.cell(w_day, 8, "Thứ 7", border=1, align="C", fill=True)
                pdf.cell(w_day, 8, "CN", border=1, align="C", fill=True)
                pdf.cell(w_dt, 8, "Đổi Thùng", border=1, align="C", fill=True, ln=True)
                
                df_may_nay = pivot_df[pivot_df['may_ep'] == may]
                pdf.set_font(font_name, "", 10)
                pdf.set_text_color(0, 0, 0)
                pdf.set_fill_color(255, 255, 255)
                
                for index, row in df_may_nay.iterrows():
                    pdf.cell(w_sp, 8, str(row['san_pham'])[:45], border=1) 
                    pdf.cell(w_day, 8, f"{row['T2']:,.0f}" if row['T2'] > 0 else "-", border=1, align="C")
                    pdf.cell(w_day, 8, f"{row['T3']:,.0f}" if row['T3'] > 0 else "-", border=1, align="C")
                    pdf.cell(w_day, 8, f"{row['T4']:,.0f}" if row['T4'] > 0 else "-", border=1, align="C")
                    pdf.cell(w_day, 8, f"{row['T5']:,.0f}" if row['T5'] > 0 else "-", border=1, align="C")
                    pdf.cell(w_day, 8, f"{row['T6']:,.0f}" if row['T6'] > 0 else "-", border=1, align="C")
                    pdf.cell(w_day, 8, f"{row['T7']:,.0f}" if row['T7'] > 0 else "-", border=1, align="C")
                    pdf.cell(w_day, 8, f"{row['CN']:,.0f}" if row['CN'] > 0 else "-", border=1, align="C")
                    
                    dt_text = str(row['doi_thung']) if pd.notna(row['doi_thung']) else "Tất cả"
                    pdf.cell(w_dt, 8, dt_text[:15], border=1, align="C", ln=True)
                
                pdf.ln(5) 
            
            try: pdf_bytes = bytes(pdf.output())
            except: pdf_bytes = pdf.output(dest='S').encode('latin-1')

            img_bytes = convert_pdf_to_png(pdf_bytes)
            
            if img_bytes:
                with col_btn2:
                    st.download_button(
                        label="🖼️ TẢI BẢN KẾ HOẠCH (ẢNH)",
                        data=img_bytes,
                        file_name=f"Ke_Hoach_San_Xuat_{tuan_str}.png",
                        mime="image/png",
                        type="primary",
                        use_container_width=True
                    )

# ------------------------------------------
# TAB 2: QUẢN LÝ DANH MỤC MÁY ÉP
# ------------------------------------------
with tab3:
    st.subheader("Cài Đặt Danh Sách Máy Ép")
    col_m1, col_m2 = st.columns([1, 2])
    
    with col_m1:
        with st.form("form_may", clear_on_submit=True):
            ten_may = st.text_input("Tên máy (VD: Toshiba 150T)")
            loai_may = st.text_input("Loại máy (Hãng/Dòng)")
            submit_may = st.form_submit_button("💾 Lưu Máy Mới", type="primary")
            if submit_may and ten_may:
                try:
                    c.execute("INSERT INTO public.dm_may_ep (ten_may, loai_may) VALUES (%s, %s)", (ten_may, loai_may))
                    conn.commit()
                    st.success("Đã thêm máy ép!")
                    time.sleep(1)
                    st.rerun()
                except: 
                    conn.rollback()
                    st.error("Tên máy bị trùng!")
                    
    with col_m2:
        try:
            df_hien_thi_may = pd.read_sql("SELECT id, ten_may, loai_may FROM public.dm_may_ep", conn)
            if not df_hien_thi_may.empty:
                df_hien_thi_may['Xóa'] = False
                edited_may = st.data_editor(
                    df_hien_thi_may[['Xóa', 'id', 'ten_may', 'loai_may']],
                    column_config={"Xóa": st.column_config.CheckboxColumn("🗑️", default=False), "id": None},
                    hide_index=True, use_container_width=True
                )
                if st.button("🚨 Cập Nhật / Xóa Máy Chọn", type="primary"):
                    for index, row in edited_may.iterrows():
                        if row['Xóa']: 
                            c.execute("DELETE FROM public.dm_may_ep WHERE id=%s", (int(row['id']),))
                    conn.commit()
                    st.success("Cập nhật thành công!")
                    time.sleep(1); st.rerun()
            else: st.info("Chưa có danh sách máy.")
        except: pass
