import streamlit as st
import pandas as pd
import time
from db_utils import get_connection

st.set_page_config(page_title="Quản Lý Khách Hàng", page_icon="👥", layout="wide")
st.header("👥 Quản Lý Danh Mục Khách Hàng")

# Kết nối database
conn = get_connection()
c = conn.cursor()

# ==========================================
# KHỞI TẠO & TỰ ĐỘNG NÂNG CẤP DATABASE (POSTGRESQL)
# ==========================================
c.execute('''CREATE TABLE IF NOT EXISTS dm_khach_hang (
                id SERIAL PRIMARY KEY,
                ten_kh TEXT UNIQUE,
                nhom_kh TEXT,
                so_dien_thoai TEXT,
                dia_chi TEXT
            )''')

# 🛠️ CÔNG CỤ ÉP NÂNG CẤP: Tự động đục thêm cột nếu Database cũ bị thiếu
cac_cot_can_them = ["nhom_kh TEXT", "so_dien_thoai TEXT", "dia_chi TEXT"]
for cot in cac_cot_can_them:
    try:
        c.execute(f"ALTER TABLE dm_khach_hang ADD COLUMN {cot}")
    except:
        pass # Nếu cột đã có sẵn thì bỏ qua, không báo lỗi

tab1, tab2 = st.tabs(["➕ Thêm Khách Hàng", "📋 Quản Lý Danh Sách"])

# ==========================================
# TAB 1: THÊM KHÁCH HÀNG 
# ==========================================
with tab1:
    st.subheader("1. Thêm Khách Hàng Mới")
    
    with st.form("form_them_kh"):
        col1, col2 = st.columns(2)
        with col1:
            ten_kh = st.text_input("Tên Khách hàng / Tên Đơn vị (*)")
            nhom_kh = st.selectbox("Nhóm khách hàng", ["Đại lý", "Khách lẻ"])
        with col2:
            sdt = st.text_input("Số điện thoại")
            dia_chi = st.text_input("Địa chỉ / Khu vực")

        submit_kh = st.form_submit_button("💾 Lưu Khách Hàng", type="primary")

        if submit_kh:
            if ten_kh.strip() == "":
                st.warning("⚠️ Bạn quên nhập tên khách hàng kìa, gõ tên vào rồi hẵng bấm Lưu nhé!")
            else:
                # ĐÃ ĐỔI DẤU ? THÀNH %s
                c.execute("SELECT ten_kh FROM dm_khach_hang WHERE ten_kh = %s", (ten_kh.strip(),))
                if c.fetchone():
                    st.error(f"⚠️ Khách hàng '{ten_kh}' đã có trong danh sách. Bạn thử thêm số hoặc ký hiệu để phân biệt nhé (VD: {ten_kh} 2)")
                else:
                    try:
                        # ĐÃ ĐỔI DẤU ? THÀNH %s
                        c.execute("""INSERT INTO dm_khach_hang (ten_kh, nhom_kh, so_dien_thoai, dia_chi) 
                                     VALUES (%s, %s, %s, %s)""", (ten_kh.strip(), nhom_kh, sdt, dia_chi))
                        
                        st.success(f"✅ Đã thêm khách hàng **{ten_kh}** vào hệ thống thành công!")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Lỗi hệ thống: {e}")

# ==========================================
# TAB 2: QUẢN LÝ DANH SÁCH & XÓA
# ==========================================
with tab2:
    st.subheader("2. Cập Nhật & Sửa Thông Tin")
    df_kh = pd.read_sql("SELECT * FROM dm_khach_hang", conn)
    
    if not df_kh.empty:
        st.markdown("💡 *Click đúp vào ô để sửa Nhóm khách, SĐT hoặc Địa chỉ.*")
        
        edited_kh = st.data_editor(
            df_kh,
            key="bang_khach_hang",
            column_config={
                "id": None, 
                "ten_kh": st.column_config.TextColumn("Tên Khách Hàng", disabled=True),
                "nhom_kh": st.column_config.SelectboxColumn("Nhóm Khách", options=["Đại lý", "Khách lẻ"]),
                "so_dien_thoai": st.column_config.TextColumn("Số Điện Thoại"),
                "dia_chi": st.column_config.TextColumn("Địa Chỉ"),
            },
            use_container_width=True, hide_index=True
        )

        if st.button("💾 Lưu Bảng Thay Đổi", type="primary"):
            try:
                for index, row in edited_kh.iterrows():
                    # ĐÃ ĐỔI DẤU ? THÀNH %s
                    c.execute("""UPDATE dm_khach_hang 
                                 SET nhom_kh=%s, so_dien_thoai=%s, dia_chi=%s 
                                 WHERE id=%s""",
                              (row['nhom_kh'], row['so_dien_thoai'], row['dia_chi'], int(row['id'])))
                
                st.success("✅ Đã cập nhật thông tin khách hàng thành công!")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi hệ thống: {e}")

        st.markdown("---")
        st.subheader("🗑️ Xóa Khách Hàng")

        col_xoa1, col_xoa2 = st.columns([3, 1])
        with col_xoa1:
            kh_can_xoa = st.selectbox("🔍 Chọn khách hàng cần xóa:", ["-- Chọn khách hàng --"] + df_kh['ten_kh'].tolist())
        with col_xoa2:
            st.write("") 
            st.write("")
            if st.button("🚨 Xóa Vĩnh Viễn", type="primary", use_container_width=True):
                if kh_can_xoa != "-- Chọn khách hàng --":
                    # ĐÃ ĐỔI DẤU ? THÀNH %s
                    c.execute("DELETE FROM dm_khach_hang WHERE ten_kh=%s", (kh_can_xoa,))
                    
                    st.success(f"✅ Đã xóa thành công khách hàng: {kh_can_xoa}")
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error("⚠️ Vui lòng chọn một khách hàng từ danh sách để xóa!")
    else:
        st.info("Danh sách khách hàng đang trống. Vui lòng thêm mới ở form bên cạnh.")