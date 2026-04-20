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
# TỰ ĐỘNG KHỞI TẠO BẢNG CHO CLOUD (POSTGRESQL)
# ==========================================
try:
    c.execute("CREATE SCHEMA IF NOT EXISTS public;")
    
    # Bảng Quản lý danh sách máy ép
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_may_ep (
                    id SERIAL PRIMARY KEY,
                    ten_may TEXT UNIQUE,
                    loai_may TEXT
                )''')

    # Bảng Kế hoạch sản xuất thiết kế mới (Lưu theo từng ngày)
    c.execute('''CREATE TABLE IF NOT EXISTS public.ke_hoach_sx_ngay (
                    id SERIAL PRIMARY KEY,
                    ngay TEXT,
                    tuan TEXT,
                    may_ep TEXT,
                    san_pham TEXT,
                    so_luong REAL DEFAULT 0
                )''')
    conn.commit()
except Exception as e: pass
# ==========================================

# Lấy dữ liệu nền (Sản phẩm từ kho Chuẩn và OME)
try: 
    df_sp_chuan = pd.read_sql("SELECT ten_sp FROM public.dm_san_pham", conn)
    df_sp_ome = pd.read_sql("SELECT ten_sp FROM public.dm_san_pham_ome", conn)
    list_sp = pd.concat([df_sp_chuan, df_sp_ome])['ten_sp'].tolist()
except: list_sp = ["Chưa có SP"]
if not list_sp: list_sp = ["Chưa có SP"]

# Lấy danh sách máy ép
try: df_may = pd.read_sql("SELECT ten_may FROM public.dm_may_ep", conn)
except: df_may = pd.DataFrame(columns=['ten_may'])
list_may = df_may['ten_may'].tolist() if not df_may.empty else ["Vui lòng thêm máy ở Tab 3"]

# ==========================================
# GIAO DIỆN 3 TABS (Đã xóa Nhật ký thực tế)
# ==========================================
tab1, tab2, tab3 = st.tabs(["📅 Lên Kế Hoạch", "🖨️ In Kế Hoạch (PDF)", "⚙️ Quản Lý Máy Ép"])

# ------------------------------------------
# TAB 1: LÊN KẾ HOẠCH THEO NGÀY
# ------------------------------------------
with tab1:
    st.subheader("1. Lên Kế Hoạch Chạy Máy Mới")
    
    with st.form("form_len_kh", clear_on_submit=True):
        col_k1, col_k2, col_k3, col_k4 = st.columns(4)
        with col_k1: ngay_chay = st.date_input("🗓️ Chọn Ngày", lay_gio_vn().date())
        with col_k2: kh_may = st.selectbox("⚙️ Chọn Máy Ép", list_may)
        with col_k3: kh_sp = st.selectbox("📦 Chọn Sản Phẩm", list_sp)
        with col_k4: sl_chay = st.number_input("🔢 Số Lượng Chạy", min_value=1, step=100)
        
        if st.form_submit_button("➕ Thêm vào Kế hoạch", type="primary"):
            if kh_may == "Vui lòng thêm máy ở Tab 3" or kh_sp == "Chưa có SP":
                st.warning("⚠️ Vui lòng khai báo Máy Ép và Sản Phẩm trước khi lên kế hoạch!")
            else:
                # Tính toán "Tuần" tự động dựa trên ngày đã chọn
                tuan_iso = ngay_chay.isocalendar()
                tuan_nhan_dien = f"Tuần {tuan_iso[1]} - {tuan_iso[0]}"
                
                try:
                    c.execute("""INSERT INTO public.ke_hoach_sx_ngay 
                                 (ngay, tuan, may_ep, san_pham, so_luong) 
                                 VALUES (%s, %s, %s, %s, %s)""",
                              (ngay_chay.strftime("%Y-%m-%d"), tuan_nhan_dien, kh_may, kh_sp, sl_chay))
                    st.success(f"✅ Đã phân việc cho {kh_may} chạy {sl_chay:,.0f} {kh_sp} vào ngày {ngay_chay.strftime('%d/%m/%Y')}!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e: st.error(f"Lỗi lưu dữ liệu: {e}")

    st.markdown("---")
    st.subheader("2. Điều chỉnh Kế Hoạch Đã Lên")
    
    # Bộ lọc tuần để xem danh sách dễ hơn
    try: list_tuan_co_san = pd.read_sql("SELECT DISTINCT tuan FROM public.ke_hoach_sx_ngay", conn)['tuan'].tolist()
    except: list_tuan_co_san = []
    
    if list_tuan_co_san:
        loc_tuan = st.selectbox("🔍 Xem kế hoạch của:", list_tuan_co_san, index=len(list_tuan_co_san)-1)
        df_kh_ngay = pd.read_sql(f"SELECT id, ngay, may_ep, san_pham, so_luong FROM public.ke_hoach_sx_ngay WHERE tuan = '{loc_tuan}' ORDER BY ngay DESC", conn)
        
        if not df_kh_ngay.empty:
            st.markdown("💡 *Click đúp vào ô 'Số lượng' hoặc 'Ngày' để sửa trực tiếp. Tích chọn ô vuông bên trái để xóa.*")
            
            df_kh_ngay['Xóa'] = False
            df_edit = df_kh_ngay[['Xóa', 'id', 'ngay', 'may_ep', 'san_pham', 'so_luong']]
            
            edited_df = st.data_editor(
                df_edit,
                column_config={
                    "Xóa": st.column_config.CheckboxColumn("🗑️ Xóa", default=False),
                    "id": None, 
                    "ngay": st.column_config.TextColumn("Ngày (YYYY-MM-DD)"),
                    "may_ep": st.column_config.TextColumn("Máy Ép", disabled=True),
                    "san_pham": st.column_config.TextColumn("Sản Phẩm", disabled=True),
                    "so_luong": st.column_config.NumberColumn("Số Lượng", step=100, format="%d"),
                },
                use_container_width=True,
                hide_index=True,
                key="bang_sua_kh"
            )
            
            col_b1, col_b2 = st.columns([1, 5])
            with col_b1:
                if st.button("💾 LƯU THAY ĐỔI", type="primary"):
                    for index, row in edited_df.iterrows():
                        if row['Xóa']:
                            c.execute("DELETE FROM public.ke_hoach_sx_ngay WHERE id=%s", (int(row['id']),))
                        else:
                            # Cập nhật lại ngày và tuần nếu người dùng sửa ngày
                            try:
                                d = datetime.strptime(row['ngay'], "%Y-%m-%d")
                                t_iso = d.isocalendar()
                                t_moi = f"Tuần {t_iso[1]} - {t_iso[0]}"
                                c.execute("""UPDATE public.ke_hoach_sx_ngay 
                                             SET ngay=%s, tuan=%s, so_luong=%s WHERE id=%s""",
                                          (row['ngay'], t_moi, float(row['so_luong']), int(row['id'])))
                            except: pass # Nếu nhập sai định dạng ngày thì bỏ qua
                    st.success("✅ Đã cập nhật!")
                    time.sleep(1)
                    st.rerun()
    else:
        st.info("Chưa có kế hoạch nào được tạo.")

# ------------------------------------------
# TAB 2: IN KẾ HOẠCH (PDF)
# ------------------------------------------
with tab2:
    st.subheader("🖨️ Xuất File PDF Kế Hoạch Sản Xuất")
    if list_tuan_co_san:
        chon_tuan_in = st.selectbox("Chọn Tuần cần in:", list_tuan_co_san, key="in_tuan")
        df_in = pd.read_sql(f"SELECT ngay, may_ep, san_pham, so_luong FROM public.ke_hoach_sx_ngay WHERE tuan = '{chon_tuan_in}'", conn)
        
        if not df_in.empty:
            # 1. CỖ MÁY GOM DỮ LIỆU: Biến đổi ngày rời rạc thành Ma Trận Tuần
            df_in['ngay_dt'] = pd.to_datetime(df_in['ngay'])
            df_in['thu'] = df_in['ngay_dt'].dt.weekday.map({0:'T2', 1:'T3', 2:'T4', 3:'T5', 4:'T6', 5:'T7', 6:'CN'})
            
            # Tính khoảng ngày của tuần đó
            ngay_min = df_in['ngay_dt'].min()
            ngay_max = ngay_min + timedelta(days=6 - ngay_min.weekday()) # Lấy ra chủ nhật của tuần đó
            tu_ngay_str = (ngay_min - timedelta(days=ngay_min.weekday())).strftime("%d/%m")
            den_ngay_str = ngay_max.strftime("%d/%m")

            # Pivot table
            pivot_df = df_in.pivot_table(index=['may_ep', 'san_pham'], columns='thu', values='so_luong', aggfunc='sum').fillna(0).reset_index()
            
            # Đảm bảo đủ các cột Thứ
            for col in ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']:
                if col not in pivot_df.columns:
                    pivot_df[col] = 0.0

            # Hiển thị trước xem trước khi in
            st.markdown(f"**Bản xem trước: {chon_tuan_in} (Từ {tu_ngay_str} đến {den_ngay_str})**")
            hien_thi_df = pivot_df[['may_ep', 'san_pham', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']]
            hien_thi_df.columns = ['Máy Ép', 'Sản Phẩm', 'Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7', 'Chủ Nhật']
            st.dataframe(hien_thi_df, use_container_width=True, hide_index=True)

            if st.button("🖨️ Tạo File PDF (Khổ A4 Ngang)", type="primary"):
                pdf = FPDF(orientation='L', format='A4') 
                pdf.add_page()
                
                has_font = False
                if os.path.exists("arial.ttf") and os.path.exists("arialbd.ttf"):
                    pdf.add_font("Arial", "", "arial.ttf", uni=True)
                    pdf.add_font("Arial", "B", "arialbd.ttf", uni=True)
                    font_name = "Arial"
                    has_font = True
                else: font_name = "Helvetica"
                    
                pdf.set_font(font_name, "B", 16)
                pdf.set_text_color(180, 0, 0) 
                pdf.cell(0, 10, "KẾ HOẠCH SẢN XUẤT", align="C", ln=True)
                pdf.set_font(font_name, "", 12)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(0, 8, f"Tuan: {chon_tuan_in}   |   Từ ngày: {tu_ngay_str} đến ngày: {den_ngay_str}", align="C", ln=True)
                pdf.ln(5)
                
                cac_may = pivot_df['may_ep'].unique()
                for may in cac_may:
                    pdf.set_font(font_name, "B", 11)
                    pdf.set_fill_color(240, 240, 240)
                    pdf.cell(60, 8, f"MÁY: {may.upper()}", border=1, fill=True)
                    
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
                
                st.download_button(
                    label="📥 TẢI XUỐNG BẢN IN (PDF)",
                    data=pdf.output(dest='S').encode('latin-1'),
                    file_name=f"Ke_Hoach_San_Xuat_{chon_tuan_in.replace(' ', '_')}.pdf",
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
                    st.success("Đã thêm máy ép!")
                    time.sleep(1)
                    st.rerun()
                except: st.error("Tên máy bị trùng!")
                    
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
                        if row['Xóa']: c.execute("DELETE FROM public.dm_may_ep WHERE id=%s", (int(row['id']),))
                    st.success("Cập nhật thành công!")
                    time.sleep(1); st.rerun()
            else: st.info("Chưa có danh sách máy.")
        except: pass
