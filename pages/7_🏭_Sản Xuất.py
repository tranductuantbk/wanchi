import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import time
from fpdf import FPDF
import os
from db_utils import get_connection

st.set_page_config(page_title="Quản Lý Sản Xuất", page_icon="🏭", layout="wide")
st.header("🏭 Hệ Thống Điều Hành Máy Ép")
conn = get_connection()
c = conn.cursor()

# ==========================================
# TỰ ĐỘNG KHỞI TẠO BẢNG CHO CLOUD (POSTGRESQL)
# ==========================================
c.execute('''CREATE TABLE IF NOT EXISTS dm_may_ep (
                id SERIAL PRIMARY KEY,
                ten_may TEXT UNIQUE,
                loai_may TEXT
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS nhat_ky_san_xuat (
                id SERIAL PRIMARY KEY,
                ngay TEXT,
                ca_lam_viec TEXT,
                may_ep TEXT,
                ten_tho TEXT,
                san_pham TEXT,
                mau_sac TEXT,
                so_rap REAL,
                tong_shot REAL,
                sl_ly_thuyet REAL,
                phe_pham REAL,
                thanh_pham REAL,
                khoi_luong_sp REAL,
                tong_kl REAL,
                ghi_chu TEXT
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS ke_hoach_san_xuat (
                id SERIAL PRIMARY KEY,
                tuan TEXT,
                tu_ngay TEXT,
                den_ngay TEXT,
                may_ep TEXT,
                san_pham TEXT,
                t2 REAL DEFAULT 0,
                t3 REAL DEFAULT 0,
                t4 REAL DEFAULT 0,
                t5 REAL DEFAULT 0,
                t6 REAL DEFAULT 0,
                t7 REAL DEFAULT 0,
                cn REAL DEFAULT 0
            )''')
# ==========================================

# Lấy dữ liệu nền
try: df_sp = pd.read_sql("SELECT ten_sp FROM dm_san_pham", conn)
except: df_sp = pd.DataFrame(columns=['ten_sp'])
list_sp = df_sp['ten_sp'].tolist() if not df_sp.empty else ["Chưa có SP"]

try: df_may = pd.read_sql("SELECT ten_may FROM dm_may_ep", conn)
except: df_may = pd.DataFrame(columns=['ten_may'])
list_may = df_may['ten_may'].tolist() if not df_may.empty else ["Vui lòng thêm máy ở Tab 4"]

try: df_tho = pd.read_sql("SELECT ten_nv FROM nhan_vien", conn)
except: df_tho = pd.DataFrame(columns=['ten_nv'])
list_tho = df_tho['ten_nv'].tolist() if not df_tho.empty else ["Chưa có Thợ"]

tab1, tab2, tab3, tab4 = st.tabs(["📝 Nhật Ký Thực Tế", "📅 Kế Hoạch Tuần", "🖨️ In Kế Hoạch (PDF)", "⚙️ Quản Lý Máy Ép"])

# ==========================================
# TAB 1: NHẬT KÝ VẬN HÀNH
# ==========================================
with tab1:
    st.subheader("Ghi Nhận Ca Máy Thực Tế")
    with st.form("form_san_xuat"):
        col1, col2, col3 = st.columns(3)
        with col1:
            ngay = st.date_input("Ngày sản xuất", date.today())
            ca = st.selectbox("Ca làm việc", ["Ca 1", "Ca 2", "Ca 3"])
            may_ep = st.selectbox("Máy ép", list_may)
            tho = st.selectbox("Tên Thợ đứng máy", list_tho)
        with col2:
            san_pham = st.selectbox("Sản phẩm chạy", list_sp)
            mau_sac = st.text_input("Màu sắc (VD: Đen, Trắng...)")
            so_rap = st.number_input("Số rập (Cavities)", min_value=1, value=2, step=1)
            kl_sp = st.number_input("Khối lượng 1 SP (gram)", min_value=0.0, step=1.0)
        with col3:
            tong_shot = st.number_input("Tổng số Shot ép", min_value=0, step=100)
            phe_pham = st.number_input("Số Phế phẩm (Cái)", min_value=0, step=1)
            ghi_chu = st.text_area("Ghi chú (Hư mốc, vệ sinh...)")
            
        submit_sx = st.form_submit_button("Lưu Nhật Ký", type="primary")
        
        if submit_sx:
            sl_ly_thuyet = tong_shot * so_rap
            thanh_pham = sl_ly_thuyet - phe_pham
            tong_kl = ((thanh_pham + phe_pham) * kl_sp) / 1000 
            
            try:
                # ĐÃ ĐỔI 14 DẤU ? THÀNH %s
                c.execute("""INSERT INTO nhat_ky_san_xuat 
                             (ngay, ca_lam_viec, may_ep, ten_tho, san_pham, mau_sac, so_rap, tong_shot, sl_ly_thuyet, phe_pham, thanh_pham, khoi_luong_sp, tong_kl, ghi_chu)
                             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                          (ngay.strftime("%Y-%m-%d"), ca, may_ep, tho, san_pham, mau_sac, so_rap, tong_shot, sl_ly_thuyet, phe_pham, thanh_pham, kl_sp, tong_kl, ghi_chu))
                st.success(f"✅ Ghi nhận thành công! Đạt: {thanh_pham:,.0f} cái.")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi: {e}")

    df_sx = pd.read_sql("SELECT * FROM nhat_ky_san_xuat ORDER BY id DESC", conn)
    if not df_sx.empty:
        st.markdown("---")
        st.dataframe(df_sx, use_container_width=True, hide_index=True)

# ==========================================
# TAB 2: KẾ HOẠCH SẢN XUẤT TUẦN
# ==========================================
with tab2:
    st.subheader("Lên Kế Hoạch Chạy Máy Trong Tuần")
    
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    tuan_hien_tai = f"Tuần {start_of_week.isocalendar()[1]} - {start_of_week.year}"

    col_kh1, col_kh2 = st.columns([1, 2])
    with col_kh1:
        st.info(f"📅 **{tuan_hien_tai}**\n\nTừ {start_of_week.strftime('%d/%m')} đến {end_of_week.strftime('%d/%m')}")
        with st.form("form_len_kh"):
            kh_may = st.selectbox("Chọn Máy ép", list_may)
            kh_sp = st.selectbox("Sản phẩm cần chạy", list_sp)
            submit_kh = st.form_submit_button("➕ Thêm vào Kế hoạch")
            
            if submit_kh:
                # ĐÃ ĐỔI 5 DẤU ? THÀNH %s
                c.execute("""INSERT INTO ke_hoach_san_xuat 
                             (tuan, tu_ngay, den_ngay, may_ep, san_pham) 
                             VALUES (%s, %s, %s, %s, %s)""",
                          (tuan_hien_tai, start_of_week.strftime("%Y-%m-%d"), end_of_week.strftime("%Y-%m-%d"), kh_may, kh_sp))
                st.rerun()

    with col_kh2:
        st.markdown("**Bảng Kế Hoạch Tuần Này (Click đúp vào ô số để sửa trực tiếp):**")
        df_kh = pd.read_sql(f"SELECT id, may_ep, san_pham, t2, t3, t4, t5, t6, t7, cn FROM ke_hoach_san_xuat WHERE tuan = '{tuan_hien_tai}'", conn)
        
        if not df_kh.empty:
            edited_df = st.data_editor(
                df_kh,
                column_config={
                    "id": None, 
                    "may_ep": st.column_config.TextColumn("Máy Ép", disabled=True),
                    "san_pham": st.column_config.TextColumn("Sản Phẩm", disabled=True),
                    "t2": st.column_config.NumberColumn("Thứ 2", step=100),
                    "t3": st.column_config.NumberColumn("Thứ 3", step=100),
                    "t4": st.column_config.NumberColumn("Thứ 4", step=100),
                    "t5": st.column_config.NumberColumn("Thứ 5", step=100),
                    "t6": st.column_config.NumberColumn("Thứ 6", step=100),
                    "t7": st.column_config.NumberColumn("Thứ 7", step=100),
                    "cn": st.column_config.NumberColumn("Chủ Nhật", step=100),
                },
                use_container_width=True,
                hide_index=True
            )
            
            if st.button("💾 Lưu thay đổi bảng", type="primary"):
                for index, row in edited_df.iterrows():
                    # ĐÃ ĐỔI 8 DẤU ? THÀNH %s VÀ ÉP KIỂU id
                    c.execute("""UPDATE ke_hoach_san_xuat 
                                 SET t2=%s, t3=%s, t4=%s, t5=%s, t6=%s, t7=%s, cn=%s WHERE id=%s""",
                              (row['t2'], row['t3'], row['t4'], row['t5'], row['t6'], row['t7'], row['cn'], int(row['id'])))
                st.success("✅ Đã cập nhật kế hoạch thành công!")
                time.sleep(1)
                st.rerun()
        else:
            st.warning("Chưa có kế hoạch nào cho tuần này. Hãy thêm ở form bên trái.")

# ==========================================
# TAB 3: XUẤT FILE PDF KẾ HOẠCH
# ==========================================
with tab3:
    st.subheader("🖨️ Trích xuất Kế Hoạch Sản Xuất")
    try:
        list_tuan = pd.read_sql("SELECT DISTINCT tuan FROM ke_hoach_san_xuat", conn)['tuan'].tolist()
    except:
        list_tuan = []
        
    if list_tuan:
        chon_tuan = st.selectbox("Chọn Tuần cần in:", list_tuan)
        df_in = pd.read_sql(f"SELECT * FROM ke_hoach_san_xuat WHERE tuan = '{chon_tuan}' ORDER BY may_ep", conn)
        
        if st.button("Tạo File PDF Kế Hoạch (Khổ A4 Ngang)"):
            pdf = FPDF(orientation='L', format='A4') 
            pdf.add_page()
            
            if not (os.path.exists("arial.ttf") and os.path.exists("arialbd.ttf")):
                st.error("🚨 Không tìm thấy font chữ arial.ttf!")
            else:
                # BỔ SUNG uni=True ĐỂ TRÁNH LỖI UNICODE TRÊN CLOUD
                pdf.add_font("Arial", "", "arial.ttf", uni=True)
                pdf.add_font("Arial", "B", "arialbd.ttf", uni=True)
                
                pdf.set_font("Arial", "B", 16)
                pdf.set_text_color(180, 0, 0) 
                pdf.cell(0, 10, "KẾ HOẠCH SẢN XUẤT", align="C", ln=True)
                pdf.set_font("Arial", "", 12)
                pdf.set_text_color(0, 0, 0)
                
                tu_ngay = df_in.iloc[0]['tu_ngay']
                den_ngay = df_in.iloc[0]['den_ngay']
                tu_ngay_str = datetime.strptime(tu_ngay, "%Y-%m-%d").strftime("%d/%m")
                den_ngay_str = datetime.strptime(den_ngay, "%Y-%m-%d").strftime("%d/%m")
                
                pdf.cell(0, 8, f"Từ ngày: {tu_ngay_str}    đến ngày: {den_ngay_str}", align="C", ln=True)
                pdf.ln(5)
                
                cac_may = df_in['may_ep'].unique()
                for may in cac_may:
                    pdf.set_font("Arial", "B", 11)
                    pdf.set_fill_color(240, 240, 240)
                    pdf.cell(50, 8, f"KẾ HOẠCH CHẠY {may.upper()}", border=1, fill=True)
                    
                    pdf.cell(25, 8, "Thứ 2", border=1, align="C", fill=True)
                    pdf.cell(25, 8, "Thứ 3", border=1, align="C", fill=True)
                    pdf.cell(25, 8, "Thứ 4", border=1, align="C", fill=True)
                    pdf.cell(25, 8, "Thứ 5", border=1, align="C", fill=True)
                    pdf.cell(25, 8, "Thứ 6", border=1, align="C", fill=True)
                    pdf.cell(25, 8, "Thứ 7", border=1, align="C", fill=True)
                    pdf.cell(25, 8, "Chủ Nhật", border=1, align="C", fill=True, ln=True)
                    
                    df_may_nay = df_in[df_in['may_ep'] == may]
                    pdf.set_font("Arial", "", 10)
                    
                    for index, row in df_may_nay.iterrows():
                        pdf.cell(50, 8, row['san_pham'][:30], border=1) 
                        pdf.cell(25, 8, f"{row['t2']:,.0f}" if row['t2'] > 0 else "", border=1, align="C")
                        pdf.cell(25, 8, f"{row['t3']:,.0f}" if row['t3'] > 0 else "", border=1, align="C")
                        pdf.cell(25, 8, f"{row['t4']:,.0f}" if row['t4'] > 0 else "", border=1, align="C")
                        pdf.cell(25, 8, f"{row['t5']:,.0f}" if row['t5'] > 0 else "", border=1, align="C")
                        pdf.cell(25, 8, f"{row['t6']:,.0f}" if row['t6'] > 0 else "", border=1, align="C")
                        pdf.cell(25, 8, f"{row['t7']:,.0f}" if row['t7'] > 0 else "", border=1, align="C")
                        pdf.cell(25, 8, f"{row['cn']:,.0f}" if row['cn'] > 0 else "", border=1, align="C", ln=True)
                    
                    pdf.ln(5) 
                
                st.download_button(
                    label="📥 TẢI XUỐNG PDF (Khổ A4 Ngang)",
                    data=bytes(pdf.output()),
                    file_name=f"Ke_Hoach_San_Xuat_{chon_tuan}.pdf",
                    mime="application/pdf",
                    type="primary"
                )
    else:
        st.info("Chưa có dữ liệu kế hoạch.")

# ==========================================
# TAB 4: QUẢN LÝ DANH MỤC MÁY ÉP
# ==========================================
with tab4:
    st.subheader("Cài Đặt Danh Sách Máy Ép")
    col_m1, col_m2 = st.columns([1, 2])
    
    with col_m1:
        with st.form("form_may"):
            ten_may = st.text_input("Tên máy (VD: Toshiba 150T)")
            loai_may = st.text_input("Loại máy (Hãng/Dòng)")
            submit_may = st.form_submit_button("Lưu Máy Mới")
            if submit_may and ten_may:
                try:
                    # ĐÃ ĐỔI 2 DẤU ? THÀNH %s
                    c.execute("INSERT INTO dm_may_ep (ten_may, loai_may) VALUES (%s, %s)", (ten_may, loai_may))
                    st.success("Đã thêm máy ép!")
                    time.sleep(1)
                    st.rerun()
                except:
                    st.error("Tên máy bị trùng!")
                    
    with col_m2:
        try:
            df_hien_thi_may = pd.read_sql("SELECT * FROM dm_may_ep", conn)
            st.dataframe(df_hien_thi_may, use_container_width=True, hide_index=True)
        except:
            st.info("Chưa có danh sách máy.")