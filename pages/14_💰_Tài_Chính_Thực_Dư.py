import streamlit as st
import pandas as pd
from datetime import date, datetime
import time
from db_utils import get_connection, check_password

st.set_page_config(page_title="Tài Chính Thực Dư", page_icon="💰", layout="wide")

# ==========================================
# Ổ KHÓA BẢO VỆ 2 LỚP - PHÂN QUYỀN
# ==========================================
role = check_password()
if not role:
    st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang Tài Chính Thực Dư là dữ liệu mật, chỉ dành cho Quản lý.")
    st.stop()

# ==========================================
# 🔑 KHÓA BẢO VỆ CẤP GIÁM ĐỐC
# ==========================================
MAT_KHAU_GIAM_DOC = "tbk1102"

if 'thuc_du_unlocked' not in st.session_state:
    st.session_state.thuc_du_unlocked = False

st.header("💰 Tài Chính Thực Dư")

if not st.session_state.thuc_du_unlocked:
    st.markdown("<br>", unsafe_allow_html=True)
    col_khoa1, col_khoa2, col_khoa3 = st.columns([1, 2, 1])
    with col_khoa2:
        st.warning("🔒 **BẢO MẬT CẤP CAO:** Vui lòng nhập Mã PIN Giám Đốc để truy cập Tài Chính Thực Dư.")
        with st.form("form_mat_khau_thuc_du"):
            pin_input = st.text_input("Mã PIN / Mật khẩu:", type="password")
            if st.form_submit_button("🔓 Mở Khóa", type="primary", use_container_width=True):
                if pin_input == MAT_KHAU_GIAM_DOC:
                    st.session_state.thuc_du_unlocked = True
                    st.rerun()
                else:
                    st.error("❌ Mã PIN không chính xác!")
    st.stop()

# Nút khóa lại
if st.button("🔒 Khóa Lại Trang", key="lock_thuc_du"):
    st.session_state.thuc_du_unlocked = False
    st.rerun()

# ==========================================
# 🛡️ LÁ CHẮN CHỐNG MẤT DỮ LIỆU (DATABASE GUARD)
# ==========================================
conn = get_connection()

def kiem_tra_du_lieu_thuc_te(connection):
    try:
        if connection.closed != 0:
            return False
        cur = connection.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        return True
    except:
        return False

if not kiem_tra_du_lieu_thuc_te(conn):
    st.cache_resource.clear()
    conn = get_connection()
    if not kiem_tra_du_lieu_thuc_te(conn):
        st.error("🚨 LÁ CHẮN BẢO VỆ DỮ LIỆU ĐANG KÍCH HOẠT!")
        st.warning("⚠️ Mạng yếu hoặc Máy chủ Neon đang ngủ đông. Hệ thống tạm thời KHÓA thao tác để bảo vệ dữ liệu.")
        if st.button("🔄 Bấm vào đây để tải lại kết nối", type="primary"):
            st.rerun()
        st.stop()

c = conn.cursor()

# ==========================================
# KHỞI TẠO BẢNG DATABASE TÀI CHÍNH THỰC DƯ
# ==========================================
try:
    c.execute('''CREATE TABLE IF NOT EXISTS tai_chinh_thuc_du (
                    id SERIAL PRIMARY KEY,
                    ngay TEXT,
                    loai TEXT DEFAULT 'Cộng vào',
                    so_tien REAL,
                    ghi_chu TEXT
                )''')
    conn.commit()
except Exception:
    conn.rollback()

# ==========================================
# TẢI DỮ LIỆU & TÍNH TỔNG THỰC DƯ TÀI CHÍNH
# ==========================================
try:
    df_all = pd.read_sql(
        "SELECT id, ngay, COALESCE(loai, 'Cộng vào') AS loai, so_tien, ghi_chu FROM tai_chinh_thuc_du ORDER BY ngay DESC, id DESC",
        conn
    )
except Exception:
    df_all = pd.DataFrame(columns=['id', 'ngay', 'loai', 'so_tien', 'ghi_chu'])

tong_cong_vao = 0.0
tong_tru_ra = 0.0

if not df_all.empty:
    tong_cong_vao = float(df_all[df_all['loai'] == 'Cộng vào']['so_tien'].sum())
    tong_tru_ra = float(df_all[df_all['loai'] == 'Trừ ra']['so_tien'].sum())

tong_thuc_du = tong_cong_vao - tong_tru_ra

# ==========================================
# HIỂN THỊ TỔNG THỰC DƯ TÀI CHÍNH
# ==========================================
st.markdown("---")
color_du = "#00cc00" if tong_thuc_du >= 0 else "#cc0000"
st.markdown(
    f"<h2 style='text-align: center; color: {color_du};'>TỔNG THỰC DƯ TÀI CHÍNH: {tong_thuc_du:,.0f} VNĐ</h2>",
    unsafe_allow_html=True
)

col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Tổng Thực Dư Hiện Có", f"{tong_thuc_du:,.0f} VNĐ")
col_m2.metric("Tổng Cộng Vào (+)", f"{tong_cong_vao:,.0f} VNĐ")
col_m3.metric("Tổng Trừ Ra (-)", f"{tong_tru_ra:,.0f} VNĐ")

# ==========================================
# KHU VỰC NHẬP LIỆU & BẢNG THEO DÕI
# ==========================================
st.markdown("---")
col_form, col_table = st.columns([1, 2])

# 1. FORM NHẬP DỮ LIỆU
with col_form:
    st.subheader("📝 Nhập Khoản Tài Chính")
    with st.form("form_nhap_thuc_du", clear_on_submit=True):
        td_ngay = st.date_input("Ngày ghi nhận", date.today(), format="DD/MM/YYYY")
        td_loai = st.radio(
            "Loại giao dịch:",
            ["Cộng vào", "Trừ ra"],
            horizontal=True
        )
        td_sotien = st.number_input("Số tiền (VNĐ)", min_value=0.0, step=100000.0, format="%.0f")
        td_ghichu = st.text_area("Ghi chú (VD: Tiền dư tháng 10, rút đầu tư máy...)")

        if st.form_submit_button("💾 Lưu Dữ Liệu", type="primary", use_container_width=True):
            if td_sotien > 0:
                try:
                    c.execute(
                        "INSERT INTO tai_chinh_thuc_du (ngay, loai, so_tien, ghi_chu) VALUES (%s, %s, %s, %s)",
                        (td_ngay.strftime("%Y-%m-%d"), td_loai, float(td_sotien), td_ghichu.strip())
                    )
                    conn.commit()
                    st.success("✅ Đã lưu vào Tài Chính Thực Dư thành công!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"⚠️ Lỗi hệ thống: {e}")
            else:
                st.warning("⚠️ Vui lòng nhập số tiền lớn hơn 0.")

# 2. BẢNG DANH SÁCH THEO DÕI ĐÃ NHẬP
with col_table:
    st.subheader("📋 Danh Sách Theo Dõi Đã Nhập")

    if not df_all.empty:
        # Bộ lọc nhanh theo tháng/năm hoặc xem tất cả
        df_all['thang_nam'] = df_all['ngay'].apply(
            lambda x: f"{str(x)[5:7]}/{str(x)[:4]}" if len(str(x)) >= 7 else "Khác"
        )
        ds_thang = ["Tất cả"] + sorted(df_all['thang_nam'].unique().tolist(), reverse=True)
        thang_loc = st.selectbox("🔍 Lọc theo tháng:", ds_thang, index=0)

        df_loc = df_all.copy() if thang_loc == "Tất cả" else df_all[df_all['thang_nam'] == thang_loc].copy()

        # Định dạng ngày hiển thị DD/MM/YYYY
        def format_ngay_vn(val):
            try:
                return datetime.strptime(str(val), "%Y-%m-%d").strftime("%d/%m/%Y")
            except:
                return str(val)

        df_view = pd.DataFrame({
            "Xóa": False,
            "ID": df_loc['id'],
            "Ngày": df_loc['ngay'].apply(format_ngay_vn),
            "Loại": df_loc['loai'].apply(lambda x: "➕ Cộng vào" if x == "Cộng vào" else "➖ Trừ ra"),
            "Số Tiền (VNĐ)": df_loc['so_tien'],
            "Ghi Chú": df_loc['ghi_chu'].fillna("")
        })

        st.caption("💡 Tích chọn vào cột **🗑️ Xóa** nếu muốn xóa dòng nhập sai.")
        edited_td = st.data_editor(
            df_view,
            column_config={
                "Xóa": st.column_config.CheckboxColumn("🗑️ Xóa", default=False),
                "ID": st.column_config.NumberColumn("ID", disabled=True),
                "Ngày": st.column_config.TextColumn("Ngày", disabled=True),
                "Loại": st.column_config.TextColumn("Loại", disabled=True),
                "Số Tiền (VNĐ)": st.column_config.NumberColumn("Số Tiền (VNĐ)", format="%.0f", disabled=True),
                "Ghi Chú": st.column_config.TextColumn("Ghi Chú", disabled=True)
            },
            use_container_width=True,
            hide_index=True,
            key=f"editor_thuc_du_{thang_loc}"
        )

        selected_del = edited_td[edited_td["Xóa"] == True]
        if not selected_del.empty:
            if st.button("🚨 Xóa các dòng đã chọn", type="primary", use_container_width=True, key="btn_xoa_thuc_du"):
                ids_to_del = [int(x) for x in selected_del["ID"].tolist()]
                try:
                    for item_id in ids_to_del:
                        c.execute("DELETE FROM tai_chinh_thuc_du WHERE id = %s", (item_id,))
                    conn.commit()
                    st.success(f"✅ Đã xóa thành công {len(ids_to_del)} dòng!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"⚠️ Lỗi khi xóa dữ liệu: {e}")
    else:
        st.info("Chưa có dữ liệu Tài Chính Thực Dư nào được nhập.")