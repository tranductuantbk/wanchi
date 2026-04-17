import streamlit as st
import pandas as pd
import time
from db_utils import get_connection

st.set_page_config(page_title="Quản Lý Sản Phẩm", page_icon="📦", layout="wide")
st.header("📦 Quản Lý Danh Mục Sản Phẩm")

# Kết nối đã được cấu hình sang Neon trong file db_utils.py
conn = get_connection()
c = conn.cursor()

# ==========================================
# CẬP NHẬT DATABASE (ĐÃ CHUYỂN SANG POSTGRESQL)
# ==========================================
c.execute('''CREATE TABLE IF NOT EXISTS dm_san_pham (
                id SERIAL PRIMARY KEY,
                ten_sp TEXT UNIQUE,
                gia_dai_ly REAL DEFAULT 0,
                gia_khach_le REAL DEFAULT 0,
                dinh_muc_nhua REAL DEFAULT 0,
                don_gia_nhua REAL DEFAULT 0,
                don_gia_cong REAL DEFAULT 0
            )''')
# Lưu ý: psycopg2 với autocommit=True không cần gọi conn.commit() nữa, nhưng gọi cũng không sao

tab1, tab2 = st.tabs(["➕ Thêm Sản Phẩm Mới", "📋 Danh Sách Sản Phẩm"])

# ==========================================
# TAB 1: THÊM SẢN PHẨM (TỰ ĐỘNG TÍNH GIÁ LẺ)
# ==========================================
with tab1:
    st.subheader("1. Thêm Sản Phẩm Mới")
    with st.form("form_them_sp"):
        col1, col2, col3 = st.columns(3)
        with col1:
            ten_sp = st.text_input("Tên sản phẩm (VD: Khay nhựa A1)")
        with col2:
            gia_dai_ly = st.number_input("Đơn giá Đại lý (VNĐ)", min_value=0.0, step=1000.0)
            st.markdown("*(Giá khách lẻ sẽ tự động tính bằng Giá Đại Lý / 0.6)*")
        with col3:
            dinh_muc_nhua = st.number_input("Định mức nhựa (Gram/cái)", min_value=0.0, step=10.0)
            don_gia_nhua = st.number_input("Đơn giá nhựa (VNĐ/kg)", min_value=0.0, step=1000.0)
            don_gia_cong = st.number_input("Đơn giá công ép (VNĐ/cái)", min_value=0.0, step=100.0)

        submit_sp = st.form_submit_button("💾 Lưu Sản Phẩm", type="primary")
        if submit_sp and ten_sp:
            gia_khach_le_calc = round(gia_dai_ly / 0.6)
            
            try:
                # ĐÃ ĐỔI DẤU ? THÀNH %s
                c.execute("""INSERT INTO dm_san_pham 
                             (ten_sp, gia_dai_ly, gia_khach_le, dinh_muc_nhua, don_gia_nhua, don_gia_cong) 
                             VALUES (%s, %s, %s, %s, %s, %s)""", 
                          (ten_sp, gia_dai_ly, gia_khach_le_calc, dinh_muc_nhua, don_gia_nhua, don_gia_cong))
                
                st.success(f"✅ Đã thêm sản phẩm {ten_sp} thành công! Giá khách lẻ tự tính là {gia_khach_le_calc:,.0f} VNĐ.")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error("⚠️ Tên sản phẩm này đã tồn tại trong hệ thống (Hoặc lỗi mạng)!")

# ==========================================
# TAB 2: QUẢN LÝ DANH SÁCH (SỬA GIÁ & XÓA)
# ==========================================
with tab2:
    st.subheader("2. Cập Nhật Giá Sản Phẩm")
    df_sp = pd.read_sql("SELECT * FROM dm_san_pham", conn)
    
    if not df_sp.empty:
        st.markdown("💡 *Click đúp vào các ô số liệu để sửa. Giá khách lẻ sẽ tự động cập nhật theo Giá Đại lý.*")
        
        edited_sp = st.data_editor(
            df_sp,
            key="bang_sua_gia",
            column_config={
                "id": None, # Ẩn ID
                "ten_sp": st.column_config.TextColumn("Tên Sản Phẩm", disabled=True),
                "gia_dai_ly": st.column_config.NumberColumn("Giá Đại lý", format="%d"),
                "gia_khach_le": st.column_config.NumberColumn("Giá Khách lẻ (Tự động)", disabled=True, format="%d"),
                "dinh_muc_nhua": st.column_config.NumberColumn("Định mức nhựa (g)", format="%d"),
                "don_gia_nhua": st.column_config.NumberColumn("Giá nhựa/kg", format="%d"),
                "don_gia_cong": st.column_config.NumberColumn("Giá công/cái", format="%d"),
            },
            use_container_width=True, hide_index=True
        )

        if st.button("💾 Lưu Bảng Giá Mới", type="primary"):
            try:
                for index, row in edited_sp.iterrows():
                    sp_id = int(row['id'])
                    gia_dl = float(row['gia_dai_ly'])
                    gia_kl = round(gia_dl / 0.6)
                    dm_nhua = float(row['dinh_muc_nhua'])
                    dg_nhua = float(row['don_gia_nhua'])
                    dg_cong = float(row['don_gia_cong'])

                    # ĐÃ ĐỔI DẤU ? THÀNH %s
                    c.execute("""UPDATE dm_san_pham 
                                 SET gia_dai_ly=%s, gia_khach_le=%s, dinh_muc_nhua=%s, don_gia_nhua=%s, don_gia_cong=%s 
                                 WHERE id=%s""",
                              (gia_dl, gia_kl, dm_nhua, dg_nhua, dg_cong, sp_id))
                
                st.success("✅ Đã cập nhật thành công toàn bộ giá mới!")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi hệ thống: {e}")

        # ==========================================
        # CÔNG CỤ XÓA SẢN PHẨM ĐỘC LẬP
        # ==========================================
        st.markdown("---")
        st.subheader("🗑️ Xóa Sản Phẩm")
        st.warning("⚠️ Cẩn thận: Sản phẩm bị xóa sẽ biến mất khỏi hệ thống và không thể khôi phục.")

        col_xoa1, col_xoa2 = st.columns([3, 1])
        with col_xoa1:
            sp_can_xoa = st.selectbox("🔍 Chọn sản phẩm cần xóa:", ["-- Chọn sản phẩm --"] + df_sp['ten_sp'].tolist())
        with col_xoa2:
            st.write("") 
            st.write("")
            if st.button("🚨 Xóa Vĩnh Viễn", type="primary", use_container_width=True):
                if sp_can_xoa != "-- Chọn sản phẩm --":
                    # ĐÃ ĐỔI DẤU ? THÀNH %s
                    c.execute("DELETE FROM dm_san_pham WHERE ten_sp=%s", (sp_can_xoa,))
                    
                    st.success(f"✅ Đã xóa thành công sản phẩm: {sp_can_xoa}")
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error("⚠️ Vui lòng chọn một sản phẩm từ danh sách để xóa!")
    else:
        st.info("Chưa có sản phẩm nào. Hãy thêm ở form bên cạnh.")