import streamlit as st
import pandas as pd
from sqlalchemy import text
import time
import io
import zipfile
from datetime import datetime

# --- KHÓA BẢO MẬT ĐĂNG NHẬP ---
if not st.session_state.get("logged_in", False):
    st.warning("🔒 Bạn chưa đăng nhập! Vui lòng quay lại Trang Chủ (Home) để gõ mật khẩu.")
    st.stop()

# ==========================================
# KẾT NỐI NEON & LÍNH GÁC BẢO VỆ
# ==========================================
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error("Chưa thể kết nối Database Neon. Vui lòng kiểm tra lại file cấu hình Secrets.")
    st.stop()

def verify_database_connection(conn_obj, max_retries=3, delay=2):
    for attempt in range(max_retries):
        try:
            with conn_obj.session as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                return False

if "db_load_success" not in st.session_state:
    st.session_state["db_load_success"] = False

is_connected = verify_database_connection(conn)
st.session_state["db_load_success"] = is_connected

if not is_connected:
    st.error("🚨 HỆ THỐNG ĐANG BỊ KHÓA AN TOÀN 🚨")
    st.error("⏳ Máy chủ cơ sở dữ liệu (Neon) đang ngủ đông hoặc đứt kết nối mạng.")
    st.warning("👉 Không thể thực hiện Sao lưu / Phục hồi lúc này. Vui lòng ấn F5 (Tải lại trang).")
    st.stop()

# ==========================================
# KHAI BÁO DANH SÁCH CÁC BẢNG DỮ LIỆU (MODULES)
# ==========================================
# Danh sách này chứa tên chính xác của các bảng trên Database Neon
DANH_SACH_BANG = [
    "wanchi_sanpham",    # 1. Tính giá sản xuất
    "wanchi_a",          # 3. Khuôn mẫu - Nguyên vật liệu
    "wanchi_c",          # 3. Khuôn mẫu - Vật tư
    "wanchi_d",          # 3. Khuôn mẫu - Tổng kết giá
    "wanchi_f",          # 3. Khuôn mẫu - Đơn gia công
    "wanchi_doitac",     # 3. Khuôn mẫu - Danh mục Đối tác
    "wanchi_donhang"     # 4. Đơn đặt hàng giao việc
]

# ==========================================
# GIAO DIỆN QUẢN TRỊ TRUNG TÂM
# ==========================================
st.title("⚙️ BẢNG ĐIỀU KHIỂN QUẢN TRỊ TRUNG TÂM")
st.markdown("Khu vực dành riêng cho Quản lý để **Sao lưu (Backup)** và **Phục hồi (Restore)** toàn bộ dữ liệu hệ thống.")
st.write("---")

col_backup, col_restore = st.columns(2)

# ------------------------------------------
# KHU VỰC 1: SAO LƯU (BACKUP)
# ------------------------------------------
with col_backup:
    st.header("📥 1. Tải Bản Sao Lưu (Backup)")
    st.info("Hệ thống sẽ gom toàn bộ dữ liệu của tất cả các Module thành các file `.csv` và nén gọn lại thành 1 file `.zip` duy nhất.")
    
    if st.button("📦 BẮT ĐẦU TẠO BẢN SAO LƯU", use_container_width=True):
        with st.spinner("⏳ Đang truy xuất dữ liệu từ đám mây và nén file..."):
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED, False) as zip_file:
                for table_name in DANH_SACH_BANG:
                    try:
                        # Rút dữ liệu từng bảng
                        df = pd.read_sql(f"SELECT * FROM {table_name}", con=conn.engine)
                        if not df.empty:
                            # Chuyển thành định dạng CSV chuẩn, hỗ trợ tiếng Việt (utf-8-sig)
                            csv_data = df.to_csv(index=False).encode('utf-8-sig')
                            # Ghi vào file ZIP với tên trùng với tên bảng
                            zip_file.writestr(f"{table_name}.csv", csv_data)
                    except Exception as e:
                        # Bỏ qua nếu bảng chưa được tạo (chưa có dữ liệu)
                        pass
            
            st.session_state["backup_zip"] = zip_buffer.getvalue()
            
        st.success("✅ Đã tạo gói sao lưu thành công!")
        
    if "backup_zip" in st.session_state:
        st.download_button(
            label="⬇️ CLICK VÀO ĐÂY ĐỂ TẢI FILE ZIP VỀ MÁY TÍNH",
            data=st.session_state["backup_zip"],
            file_name=f"Wanchi_Backup_ToanHeThong_{datetime.today().strftime('%d_%m_%Y')}.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True
        )

# ------------------------------------------
# KHU VỰC 2: PHỤC HỒI (RESTORE)
# ------------------------------------------
with col_restore:
    st.header("🔥 2. Phục Hồi Sự Cố (Restore)")
    st.error("⚠️ **CẢNH BÁO NGUY HIỂM:** Khi bạn nạp file Backup vào đây, toàn bộ dữ liệu cũ trên đám mây sẽ bị xóa sạch và thay thế bằng dữ liệu trong file ZIP.")
    
    uploaded_zip = st.file_uploader("Kéo thả file Backup (.zip) vào đây", type="zip")
    
    if uploaded_zip is not None:
        if st.button("🚨 XÁC NHẬN GHI ĐÈ PHỤC HỒI", type="primary", use_container_width=True):
            
            # Kiểm tra Lính gác lần cuối trước khi ghi đè
            if not st.session_state.get("db_load_success", False):
                st.error("Mạng đang mất kết nối, từ chối ghi đè dữ liệu để đảm bảo an toàn.")
                st.stop()
                
            with st.spinner("⏳ Đang bung file ZIP và ghi đè lên đám mây (Neon)..."):
                try:
                    with zipfile.ZipFile(uploaded_zip) as z:
                        for filename in z.namelist():
                            if filename.endswith('.csv'):
                                # Lấy lại tên bảng từ tên file (vd: wanchi_sanpham.csv -> wanchi_sanpham)
                                table_name = filename.replace('.csv', '')
                                
                                # Đọc dữ liệu từ file CSV bên trong ZIP
                                with z.open(filename) as f:
                                    df_restore = pd.read_csv(f)
                                    
                                    # Ghi đè toàn bộ dữ liệu trở lại PostgreSQL
                                    df_restore.to_sql(table_name, con=conn.engine, if_exists='replace', index=False)
                                    
                    st.success("🎉 PHỤC HỒI THÀNH CÔNG! Toàn bộ hệ thống đã được khôi phục về thời điểm sao lưu. Vui lòng bấm F5 (Tải lại trang web).")
                    time.sleep(3)
                except Exception as e:
                    st.error(f"❌ Lỗi trong quá trình phục hồi: {e}")
