import streamlit as st
import pandas as pd
import time
from db_utils import get_connection, check_password

st.set_page_config(page_title="Quản Lý Sản Phẩm", page_icon="📦", layout="wide")

# ==========================================
# Ổ KHÓA BẢO VỆ 2 LỚP
# ==========================================
role = check_password()
if not role: st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang này chứa dữ liệu mật, chỉ dành cho Quản lý WANCHI.")
    st.stop()

st.header("📦 Quản Lý Danh Mục Sản Phẩm (Đã liên kết Kho)")

conn = get_connection()
c = conn.cursor()

# ==========================================
# CẬP NHẬT DATABASE 
# ==========================================
try:
    c.execute("CREATE SCHEMA IF NOT EXISTS public;")
    
    # --- 1. TẠO BẢNG DANH MỤC NGUYÊN LIỆU (CHỜ KẾT NỐI KHO) ---
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_nguyen_lieu (
                    id SERIAL PRIMARY KEY,
                    ma_nl TEXT UNIQUE,
                    ten_nl TEXT UNIQUE,
                    don_vi TEXT,
                    ton_kho REAL DEFAULT 0
                )''')
    
    # --- 2. BẢNG HÀNG CHUẨN ---
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_san_pham (
                    id SERIAL PRIMARY KEY,
                    ma_sp TEXT UNIQUE,
                    ten_sp TEXT UNIQUE,
                    gia_dai_ly REAL DEFAULT 0,
                    gia_khach_le REAL DEFAULT 0,
                    dinh_muc_nhua REAL DEFAULT 0,
                    don_gia_nhua REAL DEFAULT 0,
                    don_gia_cong REAL DEFAULT 0
                )''')
    
    # --- 3. BẢNG HÀNG OME ---
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_san_pham_ome (
                    id SERIAL PRIMARY KEY,
                    ten_sp TEXT UNIQUE,
                    gia_ome REAL DEFAULT 0,
                    dinh_muc_nhua REAL DEFAULT 0,
                    don_gia_nhua REAL DEFAULT 0,
                    don_gia_cong REAL DEFAULT 0,
                    chi_phi_khac REAL DEFAULT 0
                )''')
    
    # --- 4. ÉP THÊM CỘT GIÁ VỐN & NGUYÊN LIỆU MỚI ---
    cac_cot_moi = {
        "gia_von": "REAL DEFAULT 0",
        "ten_nguyen_lieu": "TEXT",
        "chi_phi_khac": "REAL DEFAULT 0"
    }
    for cot, kieu in cac_cot_moi.items():
        try: c.execute(f"ALTER TABLE public.dm_san_pham ADD COLUMN {cot} {kieu}")
        except: pass
        try: c.execute(f"ALTER TABLE public.dm_san_pham_ome ADD COLUMN {cot} {kieu}")
        except: pass

    conn.commit()
except Exception as e: pass

# Lấy danh sách nguyên vật liệu từ kho (Nếu chưa có kho thì để trống)
try:
    df_nl = pd.read_sql("SELECT ten_nl FROM public.dm_nguyen_lieu", conn)
    danh_sach_nl = df_nl['ten_nl'].tolist() if not df_nl.empty else []
except: danh_sach_nl = []

# ==========================================
# GIAO DIỆN 4 TABS (ĐÃ XÓA BOM)
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    "➕ Thêm SP Chuẩn", "📋 Danh Sách SP Chuẩn", 
    "➕ Thêm SP OME", "📋 Danh Sách SP OME"
])

# ------------------------------------------
# TAB 1: THÊM SẢN PHẨM CHUẨN
# ------------------------------------------
with tab1:
    st.subheader("Thêm Sản Phẩm Chuẩn Mới")
    with st.form("form_them_sp", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            ma_sp = st.text_input("Mã sản phẩm (VD: SP01) (*)")
            ten_sp = st.text_input("Tên sản phẩm (*)")
            # MỤC MỚI: CHỌN NGUYÊN LIỆU
            ten_nguyen_lieu = st.selectbox("Nguyên liệu cấu tạo (*)", ["-- Chọn từ Kho --"] + danh_sach_nl + ["Chưa có trong kho"])
        
        with col2:
            gia_dai_ly = st.number_input("Giá bán Đại lý (VNĐ)", min_value=0.0, step=1000.0)
            # MỤC MỚI: GIÁ VỐN (Để tính lợi nhuận sau này)
            gia_von = st.number_input("Giá Vốn / Giá thành (VNĐ)", min_value=0.0, step=1000.0)
            st.markdown("*(Giá khách lẻ tự động = Giá Đại Lý / 0.6)*")
            
        with col3:
            # ĐỊNH MỨC HAO PHÍ (Để tính toán trừ kho sau này)
            dinh_muc_nhua = st.number_input("Định mức tiêu hao NL (Gram/cái)", min_value=0.0, step=10.0)
            chi_phi_khac_chuan = st.number_input("Chi phí khác (Tem, thùng...) (VNĐ)", min_value=0.0, step=1000.0)
            st.write("") # Cân bằng giao diện

        if st.form_submit_button("💾 Lưu Sản Phẩm", type="primary"):
            if not ma_sp.strip() or not ten_sp.strip():
                st.warning("⚠️ Vui lòng nhập Mã và Tên sản phẩm!")
            else:
                gia_khach_le_calc = round(gia_dai_ly / 0.6)
                nl_luu = ten_nguyen_lieu if ten_nguyen_lieu not in ["-- Chọn từ Kho --", "Chưa có trong kho"] else ""
                try:
                    c.execute("""INSERT INTO public.dm_san_pham 
                                 (ma_sp, ten_sp, gia_dai_ly, gia_khach_le, gia_von, ten_nguyen_lieu, dinh_muc_nhua, chi_phi_khac) 
                                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", 
                              (ma_sp.strip(), ten_sp.strip(), gia_dai_ly, gia_khach_le_calc, gia_von, nl_luu, dinh_muc_nhua, chi_phi_khac_chuan))
                    st.success(f"✅ Đã thêm {ten_sp} thành công!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e: st.error(f"⚠️ Mã hoặc Tên này đã tồn tại!")

# ------------------------------------------
# TAB 2: QUẢN LÝ DANH SÁCH SP CHUẨN
# ------------------------------------------
with tab2:
    st.subheader("Cập Nhật & Sửa Chữa SP Chuẩn")
    try:
        # Ẩn các cột cũ (đơn giá nhựa, đơn giá công), hiển thị các cột mới
        df_sp = pd.read_sql("SELECT id, ma_sp, ten_sp, gia_dai_ly, gia_khach_le, gia_von, ten_nguyen_lieu, dinh_muc_nhua, chi_phi_khac FROM public.dm_san_pham ORDER BY id DESC", conn)
        
        if not df_sp.empty:
            edited_sp = st.data_editor(
                df_sp, key="bang_sua_gia",
                column_config={
                    "id": None, 
                    "ma_sp": st.column_config.TextColumn("Mã SP"),
                    "ten_sp": st.column_config.TextColumn("Tên Sản Phẩm", disabled=True),
                    "gia_dai_ly": st.column_config.NumberColumn("Giá Đại lý", format="%d"),
                    "gia_khach_le": st.column_config.NumberColumn("Giá Khách lẻ", disabled=True, format="%d"),
                    "gia_von": st.column_config.NumberColumn("Giá Vốn", format="%d"),
                    "ten_nguyen_lieu": st.column_config.SelectboxColumn("Vật Tư Trừ Kho", options=[""] + danh_sach_nl),
                    "dinh_muc_nhua": st.column_config.NumberColumn("Định mức NL (g)", format="%d"),
                    "chi_phi_khac": st.column_config.NumberColumn("Chi phí khác", format="%d"),
                },
                use_container_width=True, hide_index=True
            )

            if st.button("💾 Lưu Bảng Thay Đổi", type="primary"):
                for index, row in edited_sp.iterrows():
                    gia_kl = round(float(row['gia_dai_ly']) / 0.6)
                    c.execute("""UPDATE public.dm_san_pham 
                                 SET ma_sp=%s, gia_dai_ly=%s, gia_khach_le=%s, gia_von=%s, ten_nguyen_lieu=%s, dinh_muc_nhua=%s, chi_phi_khac=%s 
                                 WHERE id=%s""",
                              (str(row['ma_sp']), float(row['gia_dai_ly']), gia_kl, float(row['gia_von']), str(row['ten_nguyen_lieu']), float(row['dinh_muc_nhua']), float(row['chi_phi_khac']), int(row['id'])))
                st.success("✅ Đã cập nhật thành công!")
                time.sleep(1)
                st.rerun()

            st.markdown("---")
            st.subheader("🗑️ Xóa Sản Phẩm")
            col_xoa1, col_xoa2 = st.columns([3, 1])
            with col_xoa1: sp_can_xoa = st.selectbox("Chọn SP cần xóa:", ["-- Chọn --"] + df_sp['ten_sp'].tolist())
            with col_xoa2:
                st.write(""); st.write("")
                if st.button("🚨 Xóa Vĩnh Viễn", type="primary", use_container_width=True):
                    if sp_can_xoa != "-- Chọn --":
                        c.execute("DELETE FROM public.dm_san_pham WHERE ten_sp=%s", (sp_can_xoa,))
                        st.success(f"✅ Đã xóa: {sp_can_xoa}")
                        time.sleep(1)
                        st.rerun()
        else: st.info("Chưa có sản phẩm nào.")
    except Exception as e: st.error(f"Lỗi: {e}")

# ------------------------------------------
# TAB 3: THÊM SP OME (CŨNG CẬP NHẬT LOGIC TƯƠNG TỰ)
# ------------------------------------------
with tab3:
    st.subheader("Thêm Sản Phẩm OME (Gia Công)")
    with st.form("form_them_ome", clear_on_submit=True):
        col_o1, col_o2, col_o3 = st.columns(3)
        with col_o1:
            ten_sp_ome = st.text_input("Tên sản phẩm OME (*)")
            ten_nguyen_lieu_ome = st.selectbox("Nguyên liệu cấu tạo (*)", ["-- Chọn từ Kho --"] + danh_sach_nl + ["Khách tự mang NL"])
        with col_o2:
            gia_ome = st.number_input("Giá bán OME (VNĐ)", min_value=0.0, step=1000.0)
            gia_von_ome = st.number_input("Giá Vốn / Giá thành (VNĐ)", min_value=0.0, step=1000.0)
        with col_o3:
            dinh_muc_ome = st.number_input("Định mức tiêu hao NL (Gram/cái)", min_value=0.0, step=10.0)
            chi_phi_khac_ome = st.number_input("Chi phí khác (VNĐ)", min_value=0.0, step=1000.0)

        if st.form_submit_button("💾 Lưu Sản Phẩm OME", type="primary"):
            if not ten_sp_ome.strip(): st.warning("⚠️ Vui lòng nhập Tên sản phẩm OME!")
            else:
                nl_luu_ome = ten_nguyen_lieu_ome if ten_nguyen_lieu_ome not in ["-- Chọn từ Kho --", "Khách tự mang NL"] else ""
                try:
                    c.execute("""INSERT INTO public.dm_san_pham_ome 
                                 (ten_sp, gia_ome, gia_von, ten_nguyen_lieu, dinh_muc_nhua, chi_phi_khac) 
                                 VALUES (%s, %s, %s, %s, %s, %s)""", 
                              (ten_sp_ome.strip(), gia_ome, gia_von_ome, nl_luu_ome, dinh_muc_ome, chi_phi_khac_ome))
                    st.success(f"✅ Đã thêm OME: {ten_sp_ome}!")
                    time.sleep(1)
                    st.rerun()
                except: st.error("⚠️ Tên OME này đã tồn tại!")

# ------------------------------------------
# TAB 4: DS SP OME
# ------------------------------------------
with tab4:
    st.subheader("Cập Nhật SP OME")
    try:
        df_ome = pd.read_sql("SELECT id, ten_sp, gia_ome, gia_von, ten_nguyen_lieu, dinh_muc_nhua, chi_phi_khac FROM public.dm_san_pham_ome ORDER BY id DESC", conn)
        if not df_ome.empty:
            edited_ome = st.data_editor(
                df_ome, key="bang_sua_ome",
                column_config={
                    "id": None, 
                    "ten_sp": st.column_config.TextColumn("Tên SP OME", disabled=True),
                    "gia_ome": st.column_config.NumberColumn("Giá bán OME", format="%d"),
                    "gia_von": st.column_config.NumberColumn("Giá Vốn", format="%d"),
                    "ten_nguyen_lieu": st.column_config.SelectboxColumn("Vật Tư Trừ Kho", options=[""] + danh_sach_nl),
                    "dinh_muc_nhua": st.column_config.NumberColumn("Định mức NL (g)", format="%d"),
                    "chi_phi_khac": st.column_config.NumberColumn("Chi phí khác", format="%d"),
                }, use_container_width=True, hide_index=True
            )

            if st.button("💾 Lưu Bảng OME", type="primary"):
                for index, row in edited_ome.iterrows():
                    c.execute("""UPDATE public.dm_san_pham_ome 
                                 SET gia_ome=%s, gia_von=%s, ten_nguyen_lieu=%s, dinh_muc_nhua=%s, chi_phi_khac=%s 
                                 WHERE id=%s""",
                              (float(row['gia_ome']), float(row['gia_von']), str(row['ten_nguyen_lieu']), float(row['dinh_muc_nhua']), float(row['chi_phi_khac']), int(row['id'])))
                st.success("✅ Cập nhật OME thành công!")
                time.sleep(1)
                st.rerun()
                
            st.markdown("---")
            col_oxoa1, col_oxoa2 = st.columns([3, 1])
            with col_oxoa1: ome_can_xoa = st.selectbox("Chọn OME cần xóa:", ["-- Chọn --"] + df_ome['ten_sp'].tolist())
            with col_oxoa2:
                st.write(""); st.write("")
                if st.button("🚨 Xóa Hàng OME", type="primary", use_container_width=True):
                    if ome_can_xoa != "-- Chọn --":
                        c.execute("DELETE FROM public.dm_san_pham_ome WHERE ten_sp=%s", (ome_can_xoa,))
                        st.success("✅ Đã xóa!")
                        time.sleep(1)
                        st.rerun()
        else: st.info("Chưa có hàng OME.")
    except: pass
