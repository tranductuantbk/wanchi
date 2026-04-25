import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta, timezone
import time
from fpdf import FPDF
import os
from db_utils import get_connection, check_password

# ==========================================
# CẤU HÌNH MÚI GIỜ VIỆT NAM (UTC+7)
# ==========================================
VN_TZ = timezone(timedelta(hours=7))
def lay_gio_vn():
    return datetime.now(VN_TZ)

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
    
    # Bảng Quản lý danh sách máy ép
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_may_ep (
                    id SERIAL PRIMARY KEY, ten_may TEXT UNIQUE, loai_may TEXT
                )''')

    # Bảng Kế hoạch sản xuất
    c.execute('''CREATE TABLE IF NOT EXISTS public.ke_hoach_sx_ngay (
                    id SERIAL PRIMARY KEY,
                    ngay TEXT, tuan TEXT, may_ep TEXT, san_pham TEXT, so_luong REAL DEFAULT 0
                )''')
                
    # Bảng Ghi chú tăng ca theo tuần
    c.execute('''CREATE TABLE IF NOT EXISTS public.ke_hoach_tang_ca (
                    tuan TEXT PRIMARY KEY, ghi_chu TEXT
                )''')
    conn.commit()
except Exception as e: 
    conn.rollback()
# ==========================================

# Lấy dữ liệu Sản phẩm & Máy ép
try: 
    df_sp_chuan = pd.read_sql("SELECT ten_sp FROM public.dm_san_pham", conn)
    df_sp_ome = pd.read_sql("SELECT ten_sp FROM public.dm_san_pham_ome", conn)
    list_sp = pd.concat([df_sp_chuan, df_sp_ome])['ten_sp'].tolist()
except: list_sp = []
if not list_sp: list_sp = ["-- Chưa có Sản Phẩm --"]

try: df_may = pd.read_sql("SELECT ten_may FROM public.dm_may_ep", conn)
except: df_may = pd.DataFrame(columns=['ten_may'])
list_may = df_may['ten_may'].tolist() if not df_may.empty else ["Vui lòng thêm máy ở Tab 3"]

# ==========================================
# GIAO DIỆN 3 TABS 
# ==========================================
tab1, tab2, tab3 = st.tabs(["📅 Lên Kế Hoạch (Dạng Bảng)", "🖨️ In Kế Hoạch (PDF)", "⚙️ Quản Lý Máy Ép"])

# ------------------------------------------
# TAB 1: BẢNG TÍNH EXCEL LÊN KẾ HOẠCH
# ------------------------------------------
with tab1:
    st.subheader("KẾ HOẠCH SẢN XUẤT (Ma trận Excel)")
    
    # 1. BỘ CHỌN TUẦN VÀ TÍNH TOÁN NGÀY
    ngay_chon = st.date_input("🗓️ Chọn một ngày bất kỳ để nạp bảng kế hoạch của Tuần đó:", lay_gio_vn().date())
    
    # Tính ra Thứ 2 và Chủ Nhật của tuần được chọn
    start_of_week = ngay_chon - timedelta(days=ngay_chon.weekday())
    dates = [start_of_week + timedelta(days=i) for i in range(7)]
    
    date_cols = [d.strftime('%d/%m') for d in dates] # Để hiện trên cột bảng (VD: 30/03)
    db_dates = [d.strftime('%Y-%m-%d') for d in dates] # Để lưu vào DB
    
    tuan_iso = start_of_week.isocalendar()
    tuan_str = f"{tuan_iso[0]}-W{tuan_iso[1]:02d}" # Identifier: 2026-W14
    
    col_t1, col_t2 = st.columns([1, 1])
    col_t1.markdown(f"**Từ ngày:** `{date_cols[0]}/{start_of_week.year}` &nbsp;&nbsp;➔&nbsp;&nbsp; **đến:** `{date_cols[-1]}/{dates[-1].year}`")
    
    # Lấy ghi chú tăng ca của tuần này
    try:
        c.execute("SELECT ghi_chu FROM public.ke_hoach_tang_ca WHERE tuan=%s", (tuan_str,))
        tc_res = c.fetchone()
        tc_val = tc_res[0] if tc_res else ""
    except: tc_val = ""
    
    tang_ca = col_t2.text_input("Kế hoạch tăng ca (VD: 2, 3):", value=tc_val)
    st.info("💡 **Hướng dẫn:** Chọn Sản Phẩm, gõ số lượng vào các ngày. Bấm dấu `+` ở góc dưới bảng để THÊM HÀNG.")

    # 2. TRÍCH XUẤT DỮ LIỆU CŨ TỪ DATABASE ĐỂ ĐIỀN VÀO BẢNG
    try:
        df_week = pd.read_sql(f"SELECT ngay, may_ep, san_pham, so_luong FROM public.ke_hoach_sx_ngay WHERE ngay >= '{db_dates[0]}' AND ngay <= '{db_dates[-1]}'", conn)
    except:
        df_week = pd.DataFrame(columns=["ngay", "may_ep", "san_pham", "so_luong"])

    edited_dfs = {}
    
    # 3. VẼ BẢNG EXCEL CHO TỪNG MÁY
    if list_may == ["Vui lòng thêm máy ở Tab 3"]:
        st.warning("⚠️ Chưa có Máy Ép nào. Vui lòng sang Tab Cài Đặt (⚙️) để thêm máy trước!")
    else:
        for may in list_may:
            st.markdown(f"<h5 style='color:#b30000; margin-top: 20px;'>KẾ HOẠCH CHẠY MÁY: {may.upper()}</h5>", unsafe_allow_html=True)
            
            df_m = df_week[df_week['may_ep'] == may]
            records = []
            
            if not df_m.empty:
                # Gom nhóm theo sản phẩm để đưa lên cùng 1 hàng
                for sp, group in df_m.groupby('san_pham'):
                    row = {"Sản Phẩm": sp}
                    for d in date_cols: row[d] = None # Khởi tạo giá trị rỗng
                    for _, r in group.iterrows():
                        try:
                            idx = db_dates.index(r['ngay'])
                            if r['so_luong'] > 0:
                                row[date_cols[idx]] = float(r['so_luong'])
                        except: pass
                    records.append(row)
                    
            # Nếu bảng trống, tạo sẵn 2 hàng trắng để user dễ nhập (Thay thế cho số 1, 2, 3 cố định)
            if len(records) == 0:
                empty_row = {"Sản Phẩm": None}
                for d in date_cols: empty_row[d] = None
                records = [empty_row.copy() for _ in range(2)]
                
            df_table = pd.DataFrame(records)
            
            # Cấu hình form nhập liệu cho Bảng
            col_cfg = {
                "Sản Phẩm": st.column_config.SelectboxColumn("Sản Phẩm", options=list_sp, width="large")
            }
            for d in date_cols:
                col_cfg[d] = st.column_config.NumberColumn(d, min_value=0.0, format="%g", width="small")
                
            # data_editor với num_rows="dynamic" chính là tính năng có dấu CỘNG để thêm hàng
            edited_dfs[may] = st.data_editor(
                df_table, 
                num_rows="dynamic", 
                column_config=col_cfg, 
                hide_index=True, 
                key=f"ed_{may}_{tuan_str}", 
                use_container_width=True
            )

        # 4. NÚT LƯU TOÀN BỘ KẾ HOẠCH VÀO DATABASE
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 LƯU TOÀN BỘ BẢNG KẾ HOẠCH TUẦN NÀY", type="primary", use_container_width=True):
            try:
                # Lưu tăng ca
                c.execute("INSERT INTO public.ke_hoach_tang_ca (tuan, ghi_chu) VALUES (%s, %s) ON CONFLICT (tuan) DO UPDATE SET ghi_chu=EXCLUDED.ghi_chu", (tuan_str, tang_ca))
                
                # Xóa sạch kế hoạch cũ của tuần này để ghi đè (Chống trùng lặp)
                c.execute("DELETE FROM public.ke_hoach_sx_ngay WHERE ngay >= %s AND ngay <= %s", (db_dates[0], db_dates[-1]))
                
                # Quét lại toàn bộ các bảng trên màn hình để insert
                for may, edf in edited_dfs.items():
                    for _, row in edf.iterrows():
                        sp = row.get("Sản Phẩm")
                        if not sp or pd.isna(sp) or sp == "-- Chưa có Sản Phẩm --": continue
                        
                        # Quét qua 7 cột ngày
                        for i, d_col in enumerate(date_cols):
                            sl = row.get(d_col)
                            if pd.notna(sl) and sl > 0:
                                c.execute("""INSERT INTO public.ke_hoach_sx_ngay 
                                             (ngay, tuan, may_ep, san_pham, so_luong) 
                                             VALUES (%s, %s, %s, %s, %s)""",
                                          (db_dates[i], tuan_str, may, sp, float(sl)))
                conn.commit()
                st.success("✅ Đã lưu toàn bộ kế hoạch vào hệ thống thành công!")
                time.sleep(1.5); st.rerun()
            except Exception as e:
                conn.rollback()
                st.error(f"Lỗi khi lưu Database: {e}")

# ------------------------------------------
# TAB 2: IN KẾ HOẠCH (PDF)
# ------------------------------------------
with tab2:
    st.subheader("🖨️ Xuất File PDF Kế Hoạch Sản Xuất")
    
    try: list_tuan_co_san = pd.read_sql("SELECT DISTINCT tuan FROM public.ke_hoach_sx_ngay", conn)['tuan'].tolist()
    except: list_tuan_co_san = []
    
    if list_tuan_co_san:
        chon_tuan_in = st.selectbox("Chọn Tuần cần in:", list_tuan_co_san, index=len(list_tuan_co_san)-1, key="in_tuan")
        df_in = pd.read_sql(f"SELECT ngay, may_ep, san_pham, so_luong FROM public.ke_hoach_sx_ngay WHERE tuan = '{chon_tuan_in}'", conn)
        
        if not df_in.empty:
            df_in['ngay_dt'] = pd.to_datetime(df_in['ngay'])
            df_in['thu'] = df_in['ngay_dt'].dt.weekday.map({0:'T2', 1:'T3', 2:'T4', 3:'T5', 4:'T6', 5:'T7', 6:'CN'})
            
            ngay_min = df_in['ngay_dt'].min()
            tu_ngay_str = (ngay_min - timedelta(days=ngay_min.weekday())).strftime("%d/%m/%Y")
            den_ngay_str = (ngay_min + timedelta(days=6 - ngay_min.weekday())).strftime("%d/%m/%Y")

            pivot_df = df_in.pivot_table(index=['may_ep', 'san_pham'], columns='thu', values='so_luong', aggfunc='sum').fillna(0).reset_index()
            for col in ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']:
                if col not in pivot_df.columns: pivot_df[col] = 0.0

            st.markdown(f"**Bản xem trước: Từ {tu_ngay_str} đến {den_ngay_str}**")
            hien_thi_df = pivot_df[['may_ep', 'san_pham', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']]
            hien_thi_df.columns = ['Máy Ép', 'Sản Phẩm', 'Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7', 'Chủ Nhật']
            st.dataframe(hien_thi_df, use_container_width=True, hide_index=True)

            if st.button("🖨️ Tạo File PDF (Khổ A4 Ngang)", type="primary"):
                pdf = FPDF(orientation='L', format='A4') 
                pdf.add_page()
                
                has_font = False
                if os.path.exists("Roboto-Regular.ttf"):
                    pdf.add_font("Roboto", "", "Roboto-Regular.ttf", uni=True)
                    font_name = "Roboto"
                    has_font = True
                else: font_name = "Helvetica"
                    
                pdf.set_font(font_name, "", 16)
                pdf.set_text_color(180, 0, 0) 
                pdf.cell(0, 10, "KẾ HOẠCH SẢN XUẤT", align="L", ln=True)
                pdf.set_font(font_name, "", 12)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(0, 8, f"Từ ngày: {tu_ngay_str}    đến: {den_ngay_str}", align="C", ln=True)
                pdf.ln(5)
                
                cac_may = pivot_df['may_ep'].unique()
                for may in cac_may:
                    pdf.set_font(font_name, "", 11)
                    pdf.set_fill_color(240, 240, 240)
                    pdf.cell(60, 8, f"KẾ HOẠCH CHẠY MÁY: {may.upper()}", border=1, fill=True)
                    
                    pdf.cell(25, 8, "Thứ 2", border=1, align="C", fill=True)
                    pdf.cell(25, 8, "Thứ 3", border=1, align="C", fill=True)
                    pdf.cell(25, 8, "Thứ 4", border=1, align="C", fill=True)
                    pdf.cell(25, 8, "Thứ 5", border=1, align="C", fill=True)
                    pdf.cell(25, 8, "Thứ 6", border=1, align="C", fill=True)
                    pdf.cell(25, 8, "Thứ 7", border=1, align="C", fill=True)
                    pdf.cell(25, 8, "Chủ Nhật", border=1, align="C", fill=True, ln=True)
                    
                    df_may_nay = pivot_df[pivot_df['may_ep'] == may]
                    pdf.set_font(font_name, "", 10)
                    
                    for index, row in df_may_nay.iterrows():
                        pdf.cell(60, 8, row['san_pham'][:35], border=1) 
                        pdf.cell(25, 8, f"{row['T2']:,.0f}" if row['T2'] > 0 else "-", border=1, align="C")
                        pdf.cell(25, 8, f"{row['T3']:,.0f}" if row['T3'] > 0 else "-", border=1, align="C")
                        pdf.cell(25, 8, f"{row['T4']:,.0f}" if row['T4'] > 0 else "-", border=1, align="C")
                        pdf.cell(25, 8, f"{row['T5']:,.0f}" if row['T5'] > 0 else "-", border=1, align="C")
                        pdf.cell(25, 8, f"{row['T6']:,.0f}" if row['T6'] > 0 else "-", border=1, align="C")
                        pdf.cell(25, 8, f"{row['T7']:,.0f}" if row['T7'] > 0 else "-", border=1, align="C")
                        pdf.cell(25, 8, f"{row['CN']:,.0f}" if row['CN'] > 0 else "-", border=1, align="C", ln=True)
                    
                    pdf.ln(5) 
                
                try: pdf_bytes = bytes(pdf.output())
                except: pdf_bytes = pdf.output(dest='S').encode('latin-1')

                st.download_button(
                    label="📥 TẢI XUỐNG BẢN IN (PDF)",
                    data=pdf_bytes,
                    file_name=f"Ke_Hoach_San_Xuat_{chon_tuan_in}.pdf",
                    mime="application/pdf",
                    type="primary"
                )
    else:
        st.info("Chưa có dữ liệu kế hoạch.")

# ------------------------------------------
# TAB 3: QUẢN LÝ DANH MỤC MÁY ÉP
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
