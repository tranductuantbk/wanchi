import streamlit as st
import pandas as pd
import time
from db_utils import get_connection, check_password

st.set_page_config(page_title="Quản Lý Sản Phẩm", page_icon="📦", layout="wide")

# ==========================================
# Ổ KHÓA BẢO VỆ 2 LỚP
# ==========================================
role = check_password()
if not role:
    st.stop() # Lớp 1: Chưa nhập mật khẩu -> Dừng tại đây

if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang này chứa dữ liệu mật, chỉ dành cho Quản lý WANCHI.")
    st.stop() # Lớp 2: Có mật khẩu nhân viên -> Báo lỗi và đuổi ra ngoài
# ==========================================

st.header("📦 Quản Lý Danh Mục Sản Phẩm & OME")

conn = get_connection()
c = conn.cursor()

# ==========================================
# CẬP NHẬT DATABASE (BẢNG HÀNG CHUẨN & BẢNG HÀNG OME)
# ==========================================
# 1. Bảng Hàng Chuẩn
c.execute('''CREATE TABLE IF NOT EXISTS dm_san_pham (
                id SERIAL PRIMARY KEY,
                ma_sp TEXT UNIQUE,
                ten_sp TEXT UNIQUE,
                gia_dai_ly REAL DEFAULT 0,
                gia_khach_le REAL DEFAULT 0,
                dinh_muc_nhua REAL DEFAULT 0,
                don_gia_nhua REAL DEFAULT 0,
                don_gia_cong REAL DEFAULT 0
            )''')
try: c.execute("ALTER TABLE dm_san_pham ADD COLUMN ma_sp TEXT")
except: pass

# 2. Bảng Hàng OME (MỚI)
c.execute('''CREATE TABLE IF NOT EXISTS dm_san_pham_ome (
                id SERIAL PRIMARY KEY,
                ten_sp TEXT UNIQUE,
                gia_ome REAL DEFAULT 0,
                dinh_muc_nhua REAL DEFAULT 0,
                don_gia_nhua REAL DEFAULT 0,
                don_gia_cong REAL DEFAULT 0,
                chi_phi_khac REAL DEFAULT 0
            )''')
conn.commit()

# CHIA THÀNH 4 TABS RÕ RÀNG
tab1, tab2, tab3, tab4 = st.tabs(["➕ Thêm SP Chuẩn", "📋 Danh Sách SP Chuẩn", "➕ Thêm SP OME", "📋 Danh Sách SP OME"])

# ==========================================
# TAB 1: THÊM SẢN PHẨM CHUẨN (GIỮ NGUYÊN)
# ==========================================
with tab1:
    st.subheader("Thêm Sản Phẩm Hàng Chợ / Hàng Chuẩn")
    with st.form("form_them_sp"):
        col1, col2, col3 = st.columns(3)
        with col1:
            ma_sp = st.text_input("Mã sản phẩm (VD: SP001) (*)")
            ten_sp = st.text_input("Tên sản phẩm (VD: Khay nhựa A1) (*)")
        with col2:
            gia_dai_ly = st.number_input("Đơn giá Đại lý (VNĐ)", min_value=0.0, step=1000.0)
            st.markdown("*(Giá khách lẻ sẽ tự động tính bằng Giá Đại Lý / 0.6)*")
        with col3:
            dinh_muc_nhua = st.number_input("Định mức nhựa (Gram/cái)", min_value=0.0, step=10.0)
            don_gia_nhua = st.number_input("Đơn giá nhựa (VNĐ/kg)", min_value=0.0, step=1000.0)
            don_gia_cong = st.number_input("Đơn giá công ép (VNĐ/cái)", min_value=0.0, step=100.0)

        if st.form_submit_button("💾 Lưu Sản Phẩm", type="primary"):
            if not ma_sp.strip() or not ten_sp.strip():
                st.warning("⚠️ Vui lòng nhập đầy đủ Mã sản phẩm và Tên sản phẩm!")
            else:
                gia_khach_le_calc = round(gia_dai_ly / 0.6)
                try:
                    c.execute("""INSERT INTO dm_san_pham 
                                 (ma_sp, ten_sp, gia_dai_ly, gia_khach_le, dinh_muc_nhua, don_gia_nhua, don_gia_cong) 
                                 VALUES (%s, %s, %s, %s, %s, %s, %s)""", 
                              (ma_sp.strip(), ten_sp.strip(), gia_dai_ly, gia_khach_le_calc, dinh_muc_nhua, don_gia_nhua, don_gia_cong))
                    st.success(f"✅ Đã thêm sản phẩm {ten_sp} thành công!")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    st.error("⚠️ Mã hoặc Tên sản phẩm này đã tồn tại trong hệ thống!")

# ==========================================
# TAB 2: QUẢN LÝ DANH SÁCH SP CHUẨN (GIỮ NGUYÊN)
# ==========================================
with tab2:
    st.subheader("Cập Nhật & Sửa Chữa SP Chuẩn")
    df_sp = pd.read_sql("SELECT * FROM dm_san_pham ORDER BY id DESC", conn)
    
    if not df_sp.empty:
        edited_sp = st.data_editor(
            df_sp, key="bang_sua_gia",
            column_config={
                "id": None, 
                "ma_sp": st.column_config.TextColumn("Mã SP"),
                "ten_sp": st.column_config.TextColumn("Tên Sản Phẩm", disabled=True),
                "gia_dai_ly": st.column_config.NumberColumn("Giá Đại lý", format="%d"),
                "gia_khach_le": st.column_config.NumberColumn("Giá Khách lẻ (Tự động)", disabled=True, format="%d"),
                "dinh_muc_nhua": st.column_config.NumberColumn("Định mức nhựa (g)", format="%d"),
                "don_gia_nhua": st.column_config.NumberColumn("Giá nhựa/kg", format="%d"),
                "don_gia_cong": st.column_config.NumberColumn("Giá công/cái", format="%d"),
            },
            use_container_width=True, hide_index=True
        )

        if st.button("💾 Lưu Bảng Giá Chuẩn", type="primary"):
            for index, row in edited_sp.iterrows():
                gia_kl = round(float(row['gia_dai_ly']) / 0.6)
                c.execute("""UPDATE dm_san_pham 
                             SET ma_sp=%s, gia_dai_ly=%s, gia_khach_le=%s, dinh_muc_nhua=%s, don_gia_nhua=%s, don_gia_cong=%s 
                             WHERE id=%s""",
                          (str(row['ma_sp']), float(row['gia_dai_ly']), gia_kl, float(row['dinh_muc_nhua']), float(row['don_gia_nhua']), float(row['don_gia_cong']), int(row['id'])))
            st.success("✅ Đã cập nhật thành công!")
            time.sleep(1)
            st.rerun()

        st.markdown("---")
        st.subheader("🗑️ Xóa SP Chuẩn")
        col_xoa1, col_xoa2 = st.columns([3, 1])
        with col_xoa1: sp_can_xoa = st.selectbox("Chọn SP Chuẩn cần xóa:", ["-- Chọn --"] + df_sp['ten_sp'].tolist())
        with col_xoa2:
            st.write(""); st.write("")
            if st.button("🚨 Xóa Vĩnh Viễn", type="primary", use_container_width=True, key="xoa_chuan"):
                if sp_can_xoa != "-- Chọn --":
                    c.execute("DELETE FROM dm_san_pham WHERE ten_sp=%s", (sp_can_xoa,))
                    st.success(f"✅ Đã xóa: {sp_can_xoa}")
                    time.sleep(1)
                    st.rerun()
    else: st.info("Chưa có sản phẩm nào.")

# ==========================================
# TAB 3: THÊM SẢN PHẨM OME (TÍNH NĂNG MỚI)
# ==========================================
with tab3:
    st.subheader("Thêm Sản Phẩm OME (Gia Công)")
    with st.form("form_them_ome", clear_on_submit=True):
        col_o1, col_o2, col_o3 = st.columns(3)
        with col_o1:
            ten_sp_ome = st.text_input("Tên sản phẩm OME (*)")
            gia_ome = st.number_input("Đơn giá OME (VNĐ)", min_value=0.0, step=1000.0)
        with col_o2:
            dinh_muc_ome = st.number_input("Định mức nhựa (Gram/cái)", min_value=0.0, step=10.0)
            gia_nhua_ome = st.number_input("Đơn giá nhựa (VNĐ/kg)", min_value=0.0, step=1000.0)
        with col_o3:
            gia_cong_ome = st.number_input("Đơn giá công ép (VNĐ/cái)", min_value=0.0, step=100.0)
            chi_phi_khac = st.number_input("Chi phí khác tạo SP (VNĐ)", min_value=0.0, step=1000.0)

        if st.form_submit_button("💾 Lưu Sản Phẩm OME", type="primary"):
            if not ten_sp_ome.strip():
                st.warning("⚠️ Vui lòng nhập Tên sản phẩm OME!")
            else:
                try:
                    c.execute("""INSERT INTO dm_san_pham_ome 
                                 (ten_sp, gia_ome, dinh_muc_nhua, don_gia_nhua, don_gia_cong, chi_phi_khac) 
                                 VALUES (%s, %s, %s, %s, %s, %s)""", 
                              (ten_sp_ome.strip(), gia_ome, dinh_muc_ome, gia_nhua_ome, gia_cong_ome, chi_phi_khac))
                    st.success(f"✅ Đã thêm sản phẩm OME: {ten_sp_ome}!")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    st.error("⚠️ Tên sản phẩm OME này đã tồn tại trong hệ thống!")

# ==========================================
# TAB 4: QUẢN LÝ DANH SÁCH SP OME (TÍNH NĂNG MỚI)
# ==========================================
with tab4:
    st.subheader("Cập Nhật & Sửa Chữa SP OME")
    df_ome = pd.read_sql("SELECT * FROM dm_san_pham_ome ORDER BY id DESC", conn)
    
    if not df_ome.empty:
        st.markdown("💡 *Click đúp vào các ô số liệu để sửa lại thông tin OME.*")
        
        edited_ome = st.data_editor(
            df_ome, key="bang_sua_ome",
            column_config={
                "id": None, 
                "ten_sp": st.column_config.TextColumn("Tên Sản Phẩm OME", disabled=True),
                "gia_ome": st.column_config.NumberColumn("Đơn giá OME", format="%d"),
                "dinh_muc_nhua": st.column_config.NumberColumn("Định mức nhựa (g)", format="%d"),
                "don_gia_nhua": st.column_config.NumberColumn("Giá nhựa/kg", format="%d"),
                "don_gia_cong": st.column_config.NumberColumn("Giá công/cái", format="%d"),
                "chi_phi_khac": st.column_config.NumberColumn("Chi phí khác", format="%d"),
            },
            use_container_width=True, hide_index=True
        )

        if st.button("💾 Lưu Bảng Giá OME", type="primary"):
            for index, row in edited_ome.iterrows():
                c.execute("""UPDATE dm_san_pham_ome 
                             SET gia_ome=%s, dinh_muc_nhua=%s, don_gia_nhua=%s, don_gia_cong=%s, chi_phi_khac=%s 
                             WHERE id=%s""",
                          (float(row['gia_ome']), float(row['dinh_muc_nhua']), float(row['don_gia_nhua']), float(row['don_gia_cong']), float(row['chi_phi_khac']), int(row['id'])))
            st.success("✅ Đã cập nhật hàng OME thành công!")
            time.sleep(1)
            st.rerun()

        st.markdown("---")
        st.subheader("🗑️ Xóa SP OME")
        col_oxoa1, col_oxoa2 = st.columns([3, 1])
        with col_oxoa1: ome_can_xoa = st.selectbox("Chọn SP OME cần xóa:", ["-- Chọn --"] + df_ome['ten_sp'].tolist())
        with col_oxoa2:
            st.write(""); st.write("")
            if st.button("🚨 Xóa Hàng OME", type="primary", use_container_width=True, key="xoa_ome"):
                if ome_can_xoa != "-- Chọn --":
                    c.execute("DELETE FROM dm_san_pham_ome WHERE ten_sp=%s", (ome_can_xoa,))
                    st.success(f"✅ Đã xóa OME: {ome_can_xoa}")
                    time.sleep(1)
                    st.rerun()
    else:
        st.info("Chưa có sản phẩm OME nào. Hãy thêm ở Tab bên cạnh.")
