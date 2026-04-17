import streamlit as st
import pandas as pd
import time
from datetime import date
from db_utils import get_connection

st.set_page_config(page_title="Quản Lý Tồn Kho", page_icon="📦", layout="wide")
st.header("📦 Quản Lý Kho Vật Tư & Thành Phẩm")
conn = get_connection()
c = conn.cursor()

# ==========================================
# KHỞI TẠO BẢNG DATABASE NẾU CHƯA CÓ (POSTGRESQL)
# ==========================================
c.execute('''CREATE TABLE IF NOT EXISTS dm_vat_tu (
                id SERIAL PRIMARY KEY,
                ten_vat_tu TEXT UNIQUE
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS giao_dich_kho (
                id SERIAL PRIMARY KEY,
                ngay TEXT,
                loai_phieu TEXT,
                loai_hang TEXT,
                ten_hang TEXT,
                so_luong REAL,
                ghi_chu TEXT
            )''')
# ==========================================

# ĐÃ BỔ SUNG TAB 4: DANH MỤC VẬT TƯ VÀO ĐÂY CHO GỌN
tab1, tab2, tab3, tab4 = st.tabs(["📊 Tồn Kho Hiện Tại", "🔄 Nhập / Xuất Kho", "🕒 Lịch Sử Giao Dịch", "⚙️ Danh Mục Vật Tư"])

# --- TAB 1: TỒN KHO HIỆN TẠI ---
with tab1:
    st.subheader("Báo Cáo Tồn Kho Theo Thời Gian Thực")
    try:
        df_kho = pd.read_sql("SELECT * FROM giao_dich_kho", conn)
    except:
        df_kho = pd.DataFrame()
    
    if not df_kho.empty:
        df_kho['so_luong_tinh'] = df_kho.apply(lambda x: x['so_luong'] if x['loai_phieu'] == 'Nhập' else -x['so_luong'], axis=1)
        df_ton_kho = df_kho.groupby(['loai_hang', 'ten_hang'])['so_luong_tinh'].sum().reset_index()
        df_ton_kho.columns = ['Loại Hàng', 'Tên Hàng', 'Tồn Kho Cuối']
        
        col_vt, col_tp = st.columns(2)
        with col_vt:
            st.markdown("#### 🛢️ Kho Nguyên Vật Liệu (kg)")
            df_nhua = df_ton_kho[df_ton_kho['Loại Hàng'] == 'Vật tư (Hạt nhựa, màu...)']
            st.dataframe(df_nhua, use_container_width=True, hide_index=True)
            
        with col_tp:
            st.markdown("#### 🛍️ Kho Thành Phẩm (Cái/Lốc)")
            df_san_pham = df_ton_kho[df_ton_kho['Loại Hàng'] == 'Thành phẩm']
            st.dataframe(df_san_pham, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có dữ liệu tồn kho. Hãy thực hiện Nhập/Xuất kho ở Tab bên cạnh.")

# --- TAB 2: NHẬP / XUẤT KHO ---
with tab2:
    st.subheader("Tạo Phiếu Nhập / Xuất")
    
    try:
        df_sp = pd.read_sql("SELECT ten_sp FROM dm_san_pham", conn)
    except:
        df_sp = pd.DataFrame(columns=['ten_sp'])
        
    try:
        df_vt = pd.read_sql("SELECT ten_vat_tu FROM dm_vat_tu", conn)
    except:
        df_vt = pd.DataFrame(columns=['ten_vat_tu'])
    
    col1, col2 = st.columns(2)
    with col1:
        ngay_gd = st.date_input("Ngày giao dịch", date.today(), key="ngay_kho")
        loai_phieu = st.radio("Loại Phiếu", ["Nhập", "Xuất"], horizontal=True)
        loai_hang = st.radio("Loại Hàng Hóa", ["Vật tư (Hạt nhựa, màu...)", "Thành phẩm"], horizontal=True)
    
    with col2:
        danh_sach_hang = []
        if loai_hang == "Thành phẩm":
            danh_sach_hang = df_sp['ten_sp'].tolist() if not df_sp.empty else []
            don_vi = "(Cái/Lốc)"
        else:
            danh_sach_hang = df_vt['ten_vat_tu'].tolist() if not df_vt.empty else []
            don_vi = "(Kg)"
            
        ten_hang = st.selectbox(f"Tên Hàng Hóa", ["-- Chọn hàng hóa --"] + danh_sach_hang)
        so_luong = st.number_input(f"Số lượng {don_vi}", min_value=0.0, step=1.0)
        ghi_chu = st.text_input("Ghi chú (VD: Nhập nhựa, Xuất hàng...)")
        
    if st.button("💾 Ghi Nhận Kho", type="primary"):
        if ten_hang == "-- Chọn hàng hóa --" or not ten_hang:
            st.error("⚠️ Lỗi: Vui lòng chọn tên hàng hóa (Nếu danh sách trống, hãy sang Tab Danh mục để thêm trước).")
        elif so_luong <= 0:
            st.error("⚠️ Lỗi: Số lượng phải lớn hơn 0.")
        else:
            try:
                # ĐÃ ĐỔI DẤU ? THÀNH %s
                c.execute("""INSERT INTO giao_dich_kho (ngay, loai_phieu, loai_hang, ten_hang, so_luong, ghi_chu)
                             VALUES (%s, %s, %s, %s, %s, %s)""", 
                          (ngay_gd.strftime("%Y-%m-%d"), loai_phieu, loai_hang, ten_hang, so_luong, ghi_chu))
                st.success(f"✅ Đã ghi nhận {loai_phieu} {so_luong} {ten_hang} thành công!")
                time.sleep(1)
                st.rerun() 
            except Exception as e:
                st.error(f"Lỗi hệ thống: {e}")

# --- TAB 3: LỊCH SỬ GIAO DỊCH ---
with tab3:
    st.subheader("Sổ Nhật Ký Kho")
    try:
        df_ls = pd.read_sql("SELECT * FROM giao_dich_kho ORDER BY id DESC", conn)
        if not df_ls.empty:
            st.dataframe(df_ls, use_container_width=True, hide_index=True)
        else:
            st.info("Sổ kho trống.")
    except Exception as e:
        st.info("Chưa có dữ liệu giao dịch.")

# --- TAB 4: DANH MỤC VẬT TƯ (GỘP VÀO ĐÂY CHO GỌN) ---
with tab4:
    col_tm, col_ds = st.columns([1, 2])
    
    with col_tm:
        st.subheader("1. Thêm Tên Vật Tư Mới")
        with st.form("form_them_vt"):
            ten_vt = st.text_input("Nhập tên (VD: Nhựa PP, Hạt màu xanh...)")
            submit_vt = st.form_submit_button("💾 Lưu Vật Tư", type="primary", use_container_width=True)

            if submit_vt:
                if ten_vt.strip() == "":
                    st.warning("⚠️ Vui lòng nhập tên!")
                else:
                    # ĐÃ ĐỔI DẤU ? THÀNH %s
                    c.execute("SELECT ten_vat_tu FROM dm_vat_tu WHERE ten_vat_tu = %s", (ten_vt.strip(),))
                    if c.fetchone():
                        st.error(f"⚠️ Đã có trong danh sách!")
                    else:
                        try:
                            # ĐÃ ĐỔI DẤU ? THÀNH %s
                            c.execute("INSERT INTO dm_vat_tu (ten_vat_tu) VALUES (%s)", (ten_vt.strip(),))
                            st.success("✅ Đã thêm!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Lỗi: {e}")

        # Khu vực xóa nằm ngay dưới form thêm
        st.markdown("---")
        st.subheader("🗑️ Xóa Vật Tư")
        df_vt = pd.read_sql("SELECT * FROM dm_vat_tu", conn)
        if not df_vt.empty:
            vt_can_xoa = st.selectbox("Chọn để xóa:", ["-- Chọn --"] + df_vt['ten_vat_tu'].tolist())
            if st.button("🚨 Xóa Vĩnh Viễn", use_container_width=True):
                if vt_can_xoa != "-- Chọn --":
                    # ĐÃ ĐỔI DẤU ? THÀNH %s
                    c.execute("DELETE FROM dm_vat_tu WHERE ten_vat_tu=%s", (vt_can_xoa,))
                    st.success("✅ Đã xóa!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("⚠️ Vui lòng chọn!")

    with col_ds:
        st.subheader("2. Sửa Tên Vật Tư Hiện Có")
        if not df_vt.empty:
            st.caption("Click đúp vào chữ để sửa tên vật tư")
            edited_vt = st.data_editor(
                df_vt, key="bang_vat_tu",
                column_config={"id": None, "ten_vat_tu": "Tên Vật Tư"},
                use_container_width=True, hide_index=True
            )
            if st.button("💾 Lưu Thay Đổi Bảng"):
                try:
                    for index, row in edited_vt.iterrows():
                        # ĐÃ ĐỔI DẤU ? THÀNH %s VÀ ÉP KIỂU id
                        c.execute("UPDATE dm_vat_tu SET ten_vat_tu=%s WHERE id=%s", (row['ten_vat_tu'], int(row['id'])))
                    st.success("✅ Đã cập nhật!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi: {e}")
        else:
            st.info("Chưa có danh sách vật tư.")