import streamlit as st
import pandas as pd
import time
from db_utils import get_connection, check_password

st.set_page_config(page_title="Quản Lý Khách Hàng", page_icon="👥", layout="wide")

# ==========================================
# Ổ KHÓA BẢO VỆ 2 LỚP
# ==========================================
role = check_password()
if not role:
    st.stop()

if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Danh sách khách hàng là dữ liệu mật, chỉ dành cho Quản lý WANCHI.")
    st.stop()

st.header("👥 Quản Lý Danh Mục Khách Hàng & OME")

conn = get_connection()
c = conn.cursor()

# ==========================================
# KHỞI TẠO BẢNG DATABASE
# ==========================================
c.execute('''CREATE TABLE IF NOT EXISTS dm_khach_hang (
                id SERIAL PRIMARY KEY,
                ten_kh TEXT UNIQUE,
                nhom_kh TEXT,
                so_dien_thoai TEXT,
                dia_chi TEXT
            )''')

cac_cot_can_them = ["nhom_kh TEXT", "so_dien_thoai TEXT", "dia_chi TEXT"]
for cot in cac_cot_can_them:
    try: c.execute(f"ALTER TABLE dm_khach_hang ADD COLUMN {cot}")
    except: pass 

c.execute('''CREATE TABLE IF NOT EXISTS dm_khach_hang_ome (
                id SERIAL PRIMARY KEY,
                ten_kh TEXT UNIQUE,
                so_dien_thoai TEXT,
                dia_chi TEXT
            )''')
conn.commit()

# ==========================================
# GIAO DIỆN 4 TABS
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["➕ Thêm KH", "📋 Danh Sách KH", "➕ Thêm KH OME", "📋 Danh Sách KH OME"])

# ------------------------------------------
# TAB 1: THÊM KHÁCH HÀNG
# ------------------------------------------
with tab1:
    st.subheader("1. Thêm Khách Hàng Mới")
    
    with st.form("form_them_kh", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            ten_kh = st.text_input("Tên Khách hàng / Tên Đơn vị (*)")
            # ĐÃ THÊM NHÓM "ƯU ĐÃI" VÀO ĐÂY
            nhom_kh = st.selectbox("Nhóm khách hàng", ["Đại lý", "Công ty", "Ưu đãi"])
        with col2:
            sdt = st.text_input("Số điện thoại")
            dia_chi = st.text_input("Địa chỉ / Khu vực")

        if st.form_submit_button("💾 Lưu Khách Hàng", type="primary"):
            if not ten_kh.strip():
                st.warning("⚠️ Vui lòng nhập tên khách hàng!")
            else:
                c.execute("SELECT ten_kh FROM dm_khach_hang WHERE ten_kh = %s", (ten_kh.strip(),))
                if c.fetchone():
                    st.error(f"⚠️ Khách hàng '{ten_kh}' đã tồn tại!")
                else:
                    try:
                        c.execute("""INSERT INTO dm_khach_hang (ten_kh, nhom_kh, so_dien_thoai, dia_chi) 
                                     VALUES (%s, %s, %s, %s)""", (ten_kh.strip(), nhom_kh, sdt, dia_chi))
                        st.success(f"✅ Đã thêm Khách hàng: **{ten_kh}** (Nhóm: {nhom_kh})")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Lỗi: {e}")

# ------------------------------------------
# TAB 2: QUẢN LÝ KHÁCH HÀNG
# ------------------------------------------
with tab2:
    st.subheader("2. Cập Nhật & Xóa Khách Hàng")
    
    with st.expander("🛠️ Công cụ đồng bộ dữ liệu (Khách lẻ -> Công ty)"):
        st.info("Bấm nút này để hệ thống tự động quét và đổi toàn bộ khách hàng cũ thuộc nhóm 'Khách lẻ' sang nhóm 'Công ty'.")
        if st.button("🔄 Chạy tự động đồng bộ nhóm khách", type="secondary"):
            try:
                c.execute("UPDATE dm_khach_hang SET nhom_kh = 'Công ty' WHERE nhom_kh = 'Khách lẻ'")
                conn.commit()
                st.success("✅ Đã đồng bộ thành công dữ liệu cũ!")
                time.sleep(1.5)
                st.rerun()
            except Exception as e: st.error(f"Lỗi: {e}")

    df_kh = pd.read_sql("SELECT * FROM dm_khach_hang ORDER BY id DESC", conn)
    
    if not df_kh.empty:
        st.markdown("💡 *Click đúp vào ô để sửa Nhóm khách, SĐT hoặc Địa chỉ.*")
        
        edited_kh = st.data_editor(
            df_kh, key="bang_khach_hang",
            column_config={
                "id": None, 
                "ten_kh": st.column_config.TextColumn("Tên Khách Hàng", disabled=True),
                # ĐÃ THÊM NHÓM "ƯU ĐÃI" VÀO BẢNG CHỈNH SỬA
                "nhom_kh": st.column_config.SelectboxColumn("Nhóm Khách", options=["Đại lý", "Công ty", "Ưu đãi"]),
                "so_dien_thoai": st.column_config.TextColumn("Số Điện Thoại"),
                "dia_chi": st.column_config.TextColumn("Địa Chỉ"),
            },
            use_container_width=True, hide_index=True
        )

        if st.button("💾 Lưu Sửa Đổi", type="primary"):
            for index, row in edited_kh.iterrows():
                c.execute("""UPDATE dm_khach_hang 
                             SET nhom_kh=%s, so_dien_thoai=%s, dia_chi=%s 
                             WHERE id=%s""",
                          (row['nhom_kh'], row['so_dien_thoai'], row['dia_chi'], int(row['id'])))
            st.success("✅ Đã cập nhật thông tin thành công!")
            time.sleep(1)
            st.rerun()

        st.markdown("---")
        st.subheader("🗑️ Xóa Khách Hàng")
        col_xoa1, col_xoa2 = st.columns([3, 1])
        with col_xoa1: kh_can_xoa = st.selectbox("Chọn khách hàng cần xóa:", ["-- Chọn --"] + df_kh['ten_kh'].tolist(), key="del_kh_chuan")
        with col_xoa2:
            st.write(""); st.write("")
            if st.button("🚨 Xóa Vĩnh Viễn", type="primary", use_container_width=True, key="btn_del_chuan"):
                if kh_can_xoa != "-- Chọn --":
                    c.execute("DELETE FROM dm_khach_hang WHERE ten_kh=%s", (kh_can_xoa,))
                    st.success(f"✅ Đã xóa khách hàng: {kh_can_xoa}")
                    time.sleep(1.5)
                    st.rerun()
    else: st.info("Danh sách khách hàng đang trống.")

# ------------------------------------------
# TAB 3 & 4: KHÁCH HÀNG OME (GIỮ NGUYÊN)
# ------------------------------------------
with tab3:
    st.subheader("Thêm Khách Hàng Mới (Gia Công OME)")
    with st.form("form_them_kh_ome", clear_on_submit=True):
        col_o1, col_o2 = st.columns(2)
        with col_o1:
            ten_kh_ome = st.text_input("Tên Khách hàng OME (*)")
            sdt_ome = st.text_input("Số điện thoại")
        with col_o2:
            dia_chi_ome = st.text_input("Địa chỉ / Đơn vị")
            st.write("") 

        if st.form_submit_button("💾 Lưu KH OME", type="primary"):
            if not ten_kh_ome.strip():
                st.warning("⚠️ Vui lòng nhập tên khách hàng OME!")
            else:
                c.execute("SELECT ten_kh FROM dm_khach_hang_ome WHERE ten_kh = %s", (ten_kh_ome.strip(),))
                if c.fetchone():
                    st.error(f"⚠️ Khách OME '{ten_kh_ome}' đã tồn tại!")
                else:
                    try:
                        c.execute("""INSERT INTO dm_khach_hang_ome (ten_kh, so_dien_thoai, dia_chi) 
                                     VALUES (%s, %s, %s)""", (ten_kh_ome.strip(), sdt_ome, dia_chi_ome))
                        st.success(f"✅ Đã thêm KH OME: **{ten_kh_ome}**")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Lỗi: {e}")

with tab4:
    st.subheader("Cập Nhật & Xóa KH OME")
    df_kh_ome = pd.read_sql("SELECT * FROM dm_khach_hang_ome ORDER BY id DESC", conn)
    
    if not df_kh_ome.empty:
        st.markdown("💡 *Click đúp vào ô để sửa SĐT hoặc Địa chỉ khách OME.*")
        edited_kh_ome = st.data_editor(
            df_kh_ome, key="bang_khach_hang_ome",
            column_config={
                "id": None, 
                "ten_kh": st.column_config.TextColumn("Tên Khách Hàng OME", disabled=True),
                "so_dien_thoai": st.column_config.TextColumn("Số Điện Thoại"),
                "dia_chi": st.column_config.TextColumn("Địa Chỉ"),
            },
            use_container_width=True, hide_index=True
        )

        if st.button("💾 Lưu Sửa Đổi (KH OME)", type="primary"):
            for index, row in edited_kh_ome.iterrows():
                c.execute("""UPDATE dm_khach_hang_ome 
                             SET so_dien_thoai=%s, dia_chi=%s 
                             WHERE id=%s""",
                          (row['so_dien_thoai'], row['dia_chi'], int(row['id'])))
            st.success("✅ Đã cập nhật KH OME thành công!")
            time.sleep(1)
            st.rerun()

        st.markdown("---")
        st.subheader("🗑️ Xóa KH OME")
        col_oxoa1, col_oxoa2 = st.columns([3, 1])
        with col_oxoa1: kh_ome_can_xoa = st.selectbox("Chọn KH OME cần xóa:", ["-- Chọn --"] + df_kh_ome['ten_kh'].tolist(), key="del_kh_ome")
        with col_oxoa2:
            st.write(""); st.write("")
            if st.button("🚨 Xóa KH OME", type="primary", use_container_width=True, key="btn_del_ome"):
                if kh_ome_can_xoa != "-- Chọn --":
                    c.execute("DELETE FROM dm_khach_hang_ome WHERE ten_kh=%s", (kh_ome_can_xoa,))
                    st.success(f"✅ Đã xóa KH OME: {kh_ome_can_xoa}")
                    time.sleep(1.5)
                    st.rerun()
    else: st.info("Danh sách khách OME trống.")
