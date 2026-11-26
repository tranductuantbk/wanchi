import streamlit as st
import pandas as pd
from datetime import date, datetime
import time
from db_utils import get_connection, check_password

st.set_page_config(page_title="Đầu Tư Chiến Lược", page_icon="🚀", layout="wide")

# ==========================================
# Ổ KHÓA BẢO VỆ 2 LỚP - PHÂN QUYỀN
# ==========================================
role = check_password()
if not role:
    st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang Đầu Tư Chiến Lược là dữ liệu mật, chỉ dành cho Quản lý.")
    st.stop()

# ==========================================
# 🔑 KHÓA BẢO VỆ CẤP GIÁM ĐỐC
# ==========================================
MAT_KHAU_GIAM_DOC = "tbk1102"

if 'dau_tu_unlocked' not in st.session_state:
    st.session_state.dau_tu_unlocked = False

st.header("🚀 Đầu Tư Chiến Lược")

if not st.session_state.dau_tu_unlocked:
    st.markdown("<br>", unsafe_allow_html=True)
    col_khoa1, col_khoa2, col_khoa3 = st.columns([1, 2, 1])
    with col_khoa2:
        st.warning("🔒 **BẢO MẬT CẤP CAO:** Vui lòng nhập Mã PIN Giám Đốc để truy cập Đầu Tư Chiến Lược.")
        with st.form("form_mat_khau_dau_tu"):
            pin_input = st.text_input("Mã PIN / Mật khẩu:", type="password")
            if st.form_submit_button("🔓 Mở Khóa", type="primary", use_container_width=True):
                if pin_input == MAT_KHAU_GIAM_DOC:
                    st.session_state.dau_tu_unlocked = True
                    st.rerun()
                else:
                    st.error("❌ Mã PIN không chính xác!")
    st.stop()

# Nút khóa lại
if st.button("🔒 Khóa Lại Trang", key="lock_dau_tu"):
    st.session_state.dau_tu_unlocked = False
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
# KHỞI TẠO BẢNG DATABASE ĐẦU TƯ CHIẾN LƯỢC
# ==========================================
try:
    c.execute('''CREATE TABLE IF NOT EXISTS dau_tu_chien_luoc (
                    id SERIAL PRIMARY KEY,
                    ngay TEXT,
                    ten_hang_muc TEXT,
                    so_tien REAL,
                    ghi_chu TEXT
                )''')
    conn.commit()
except Exception:
    conn.rollback()

# ==========================================
# TẢI DỮ LIỆU & BỘ LỌC THEO NĂM
# ==========================================
try:
    df_all = pd.read_sql(
        "SELECT id, ngay, ten_hang_muc, so_tien, ghi_chu FROM dau_tu_chien_luoc ORDER BY ngay DESC, id DESC",
        conn
    )
except Exception:
    df_all = pd.DataFrame(columns=['id', 'ngay', 'ten_hang_muc', 'so_tien', 'ghi_chu'])

nam_hien_tai = str(date.today().year)
if not df_all.empty:
    df_all['nam'] = df_all['ngay'].apply(lambda x: str(x)[:4] if len(str(x)) >= 4 else nam_hien_tai)
    cac_nam = sorted(list(set(df_all['nam'].tolist() + [nam_hien_tai])), reverse=True)
else:
    cac_nam = [nam_hien_tai]

st.markdown("---")
col_loc1, col_loc2 = st.columns([1, 3])
with col_loc1:
    nam_loc = st.selectbox("🗓️ Lọc theo năm:", ["Tất cả các năm"] + cac_nam, index=0)

df_loc = df_all.copy() if nam_loc == "Tất cả các năm" else df_all[df_all['nam'] == nam_loc].copy()

tong_tat_ca = float(df_all['so_tien'].sum()) if not df_all.empty else 0.0
tong_theo_loc = float(df_loc['so_tien'].sum()) if not df_loc.empty else 0.0
so_hang_muc = len(df_loc)

# ==========================================
# HIỂN THỊ TỔNG SỐ TIỀN ĐÃ ĐẦU TƯ
# ==========================================
nhan_tieu_de = "TỔNG SỐ TIỀN ĐÃ ĐẦU TƯ" if nam_loc == "Tất cả các năm" else f"TỔNG SỐ TIỀN ĐẦU TƯ NĂM {nam_loc}"
st.markdown(
    f"<h2 style='text-align: center; color: #0066cc;'>{nhan_tieu_de}: {tong_theo_loc:,.0f} VNĐ</h2>",
    unsafe_allow_html=True
)

col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Tổng Đầu Tư Toàn Bộ", f"{tong_tat_ca:,.0f} VNĐ")
col_m2.metric(f"Tổng Đầu Tư ({nam_loc})", f"{tong_theo_loc:,.0f} VNĐ")
col_m3.metric(f"Số Hạng Mục ({nam_loc})", f"{so_hang_muc} hạng mục")

# ==========================================
# KHU VỰC NHẬP LIỆU & BẢNG THEO DÕI RIÊNG
# ==========================================
st.markdown("---")
col_form, col_table = st.columns([1, 2])

# 1. FORM NHẬP HẠNG MỤC ĐẦU TƯ
with col_form:
    st.subheader("📝 Nhập Hạng Mục Đầu Tư")
    with st.form("form_nhap_dau_tu", clear_on_submit=True):
        dt_ngay = st.date_input("Ngày đầu tư", date.today(), format="DD/MM/YYYY")
        dt_hangmuc = st.text_input("Tên hạng mục (*)", placeholder="VD: Mua máy ép nhựa, mở rộng kho...")
        dt_sotien = st.number_input("Số tiền đầu tư (VNĐ)", min_value=0.0, step=1000000.0, format="%.0f")
        dt_ghichu = st.text_area("Ghi chú (Nhà cung cấp, mục tiêu, tiến độ...)")

        if st.form_submit_button("💾 Lưu Hạng Mục Đầu Tư", type="primary", use_container_width=True):
            if not dt_hangmuc.strip():
                st.warning("⚠️ Vui lòng nhập tên hạng mục đầu tư!")
            elif dt_sotien <= 0:
                st.warning("⚠️ Vui lòng nhập số tiền lớn hơn 0!")
            else:
                try:
                    c.execute(
                        "INSERT INTO dau_tu_chien_luoc (ngay, ten_hang_muc, so_tien, ghi_chu) VALUES (%s, %s, %s, %s)",
                        (dt_ngay.strftime("%Y-%m-%d"), dt_hangmuc.strip(), float(dt_sotien), dt_ghichu.strip())
                    )
                    conn.commit()
                    st.success("✅ Đã lưu hạng mục đầu tư thành công!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"⚠️ Lỗi hệ thống: {e}")

# 2. BẢNG RIÊNG THEO DÕI CÁC HẠNG MỤC ĐÃ NHẬP
with col_table:
    st.subheader(f"📋 Bảng Theo Dõi Các Hạng Mục Đã Nhập ({nam_loc})")

    if not df_loc.empty:
        def format_ngay_vn(val):
            try:
                return datetime.strptime(str(val), "%Y-%m-%d").strftime("%d/%m/%Y")
            except:
                return str(val)

        df_view = pd.DataFrame({
            "Xóa": False,
            "ID": df_loc['id'],
            "Ngày": df_loc['ngay'].apply(format_ngay_vn),
            "Tên Hạng Mục": df_loc['ten_hang_muc'].fillna(""),
            "Số Tiền (VNĐ)": df_loc['so_tien'],
            "Ghi Chú": df_loc['ghi_chu'].fillna("")
        })

        st.caption("💡 Tích chọn vào cột **🗑️ Xóa** nếu muốn xóa hạng mục nhập sai.")
        edited_dt = st.data_editor(
            df_view,
            column_config={
                "Xóa": st.column_config.CheckboxColumn("🗑️ Xóa", default=False),
                "ID": st.column_config.NumberColumn("ID", disabled=True),
                "Ngày": st.column_config.TextColumn("Ngày", disabled=True),
                "Tên Hạng Mục": st.column_config.TextColumn("Tên Hạng Mục", disabled=True),
                "Số Tiền (VNĐ)": st.column_config.NumberColumn("Số Tiền (VNĐ)", format="%.0f", disabled=True),
                "Ghi Chú": st.column_config.TextColumn("Ghi Chú", disabled=True)
            },
            use_container_width=True,
            hide_index=True,
            key=f"editor_dau_tu_{nam_loc}"
        )

        selected_del = edited_dt[edited_dt["Xóa"] == True]
        if not selected_del.empty:
            if st.button("🚨 Xóa các hạng mục đã chọn", type="primary", use_container_width=True, key="btn_xoa_dau_tu"):
                ids_to_del = [int(x) for x in selected_del["ID"].tolist()]
                try:
                    for item_id in ids_to_del:
                        c.execute("DELETE FROM dau_tu_chien_luoc WHERE id = %s", (item_id,))
                    conn.commit()
                    st.success(f"✅ Đã xóa thành công {len(ids_to_del)} hạng mục!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"⚠️ Lỗi khi xóa dữ liệu: {e}")
    else:
        st.info(f"Chưa có hạng mục đầu tư nào được ghi nhận trong {nam_loc}.")