import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import io
import zipfile
import psycopg2
import psycopg2.extras
from db_utils import get_connection, check_password

# ==========================================
# CẤU HÌNH TRANG, MÚI GIỜ & BẢO MẬT
# ==========================================
st.set_page_config(page_title="Quản Trị Dữ Liệu", page_icon="🗄️", layout="wide")

VN_TZ = timezone(timedelta(hours=7))
def lay_gio_vn():
    return datetime.now(VN_TZ)

MAT_KHAU_GIAM_DOC = "tbk1102"

role = check_password()
if not role: st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang Quản Trị Hệ Thống chỉ dành cho Quản lý WANCHI.")
    st.stop()

st.title("🗄️ TRUNG TÂM QUẢN TRỊ & BẢO VỆ DỮ LIỆU")
st.markdown("Khu vực này cho phép Quản lý tải về bản sao lưu an toàn của **toàn bộ dữ liệu xưởng** (Kho, Nhân sự, Công nợ, Máy ép...) và phục hồi lại khi có sự cố.")
st.write("---")

# ==========================================
# KẾT NỐI DATABASE & TẠO BẢNG CẤU HÌNH (NẾU CHƯA CÓ)
# ==========================================
conn = get_connection()
if conn.closed != 0:
    st.cache_resource.clear()
    conn = get_connection()
c = conn.cursor()

try:
    c.execute('''CREATE TABLE IF NOT EXISTS public.cau_hinh (
                    id SERIAL PRIMARY KEY, ten_cau_hinh TEXT UNIQUE, gia_tri TEXT
                )''')
    conn.commit()
except: pass

# Hàm tự động quét lấy danh sách tất cả các bảng trong Database
def get_all_tables(cursor):
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE';
    """)
    return [row[0] for row in cursor.fetchall()]

danh_sach_bang = get_all_tables(c)

# Lấy ngày Backup cuối cùng
c.execute("SELECT gia_tri FROM public.cau_hinh WHERE ten_cau_hinh='NGAY_BACKUP_CUOI'")
row_backup = c.fetchone()
ngay_backup_cuoi = row_backup[0] if row_backup else None

if ngay_backup_cuoi:
    try:
        dt_backup = datetime.strptime(ngay_backup_cuoi, "%d/%m/%Y").date()
        so_ngay_troi_qua = (lay_gio_vn().date() - dt_backup).days
        
        if so_ngay_troi_qua >= 15:
            st.error(f"🚨 CẢNH BÁO: Đã **{so_ngay_troi_qua} ngày** hệ thống chưa được sao lưu (Lần cuối: {ngay_backup_cuoi})! Vui lòng thực hiện Backup ngay lập tức để bảo vệ dữ liệu xưởng.")
        else:
            st.success(f"✅ Dữ liệu đang ở trạng thái an toàn. Bản sao lưu gần nhất: **{ngay_backup_cuoi}** ({so_ngay_troi_qua} ngày trước).")
    except: pass
else:
    st.warning("⚠️ Hệ thống chưa ghi nhận bản sao lưu nào. Vui lòng bấm tạo bản sao lưu ngay!")

st.write("---")

# ==========================================
# GIAO DIỆN BACKUP & RESTORE
# ==========================================
col_backup, col_restore = st.columns(2)

# ------------------------------------------
# 1. TÍNH NĂNG SAO LƯU (BACKUP)
# ------------------------------------------
with col_backup:
    st.subheader("📥 1. Tải Bản Sao Lưu (Backup)")
    st.info("Hệ thống sẽ gom toàn bộ dữ liệu hiện tại thành 1 file ZIP. Anh/chị nên thực hiện việc này định kỳ để đảm bảo an toàn.")
    
    if st.button("📦 TẠO BẢN SAO LƯU TOÀN HỆ THỐNG", use_container_width=True, type="primary"):
        with st.spinner("⏳ Đang quét và nén dữ liệu từ đám mây..."):
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED, False) as zip_file:
                for table in danh_sach_bang:
                    try:
                        # Đọc dữ liệu từ từng bảng
                        df = pd.read_sql(f"SELECT * FROM public.{table}", conn)
                        if not df.empty:
                            # Chuyển thành CSV (hỗ trợ tiếng Việt) và nén vào ZIP
                            csv_data = df.to_csv(index=False).encode('utf-8-sig')
                            zip_file.writestr(f"{table}.csv", csv_data)
                    except Exception as e:
                        pass
            
            st.session_state["backup_zip"] = zip_buffer.getvalue()
            
            # Lưu lại ngày đã backup vào Database
            hom_nay_str = lay_gio_vn().strftime("%d/%m/%Y")
            c.execute("INSERT INTO public.cau_hinh (ten_cau_hinh, gia_tri) VALUES ('NGAY_BACKUP_CUOI', %s) ON CONFLICT (ten_cau_hinh) DO UPDATE SET gia_tri = EXCLUDED.gia_tri", (hom_nay_str,))
            conn.commit()
            
        st.success("✅ Đã tạo file nén dữ liệu thành công!")
        time.sleep(1)
        st.rerun()
        
    if "backup_zip" in st.session_state:
        st.write("")
        st.download_button(
            label="⬇️ BẤM VÀO ĐÂY ĐỂ TẢI FILE ZIP VỀ MÁY",
            data=st.session_state["backup_zip"],
            file_name=f"Wanchi_Backup_Toan_Bo_{lay_gio_vn().strftime('%d_%m_%Y')}.zip",
            mime="application/zip",
            use_container_width=True
        )

# ------------------------------------------
# 2. TÍNH NĂNG PHỤC HỒI (RESTORE)
# ------------------------------------------
with col_restore:
    st.subheader("🔥 2. Phục Hồi Dữ Liệu (Restore)")
    st.error("⚠️ **CẢNH BÁO NGUY HIỂM:** Khi nạp file Backup vào đây, toàn bộ dữ liệu hiện tại trên phần mềm sẽ bị XÓA SẠCH và thay thế bằng dữ liệu trong file ZIP.")
    
    mk_nhap = st.text_input("🔑 Nhập Mật Khẩu Giám Đốc để mở khóa công cụ Phục hồi:", type="password", key="mk_restore")
    
    if mk_nhap == MAT_KHAU_GIAM_DOC:
        st.success("🔓 Đã mở khóa! Mời anh/chị tải file Backup lên.")
        uploaded_zip = st.file_uploader("Kéo thả file Backup (.zip) vào đây", type="zip")
        
        if uploaded_zip is not None:
            if st.button("🚨 XÁC NHẬN GHI ĐÈ PHỤC HỒI", type="primary", use_container_width=True):
                with st.spinner("⏳ Đang bung file ZIP và ghi đè lên hệ thống..."):
                    try:
                        with zipfile.ZipFile(uploaded_zip) as z:
                            for filename in z.namelist():
                                if filename.endswith('.csv'):
                                    table_name = filename.replace('.csv', '')
                                    
                                    # Chỉ phục hồi nếu bảng đó tồn tại trong hệ thống
                                    if table_name in danh_sach_bang:
                                        with z.open(filename) as f:
                                            df_restore = pd.read_csv(f)
                                            
                                            if not df_restore.empty:
                                                # Xóa sạch dữ liệu cũ của bảng đó
                                                c.execute(f"DELETE FROM public.{table_name}")
                                                
                                                # Tạo câu lệnh INSERT linh hoạt
                                                columns = ",".join(df_restore.columns)
                                                placeholders = ",".join(["%s"] * len(df_restore.columns))
                                                insert_query = f"INSERT INTO public.{table_name} ({columns}) VALUES ({placeholders})"
                                                
                                                # Đổ dữ liệu mới vào
                                                data_tuples = [tuple(x) for x in df_restore.to_numpy()]
                                                psycopg2.extras.execute_batch(c, insert_query, data_tuples)
                        
                        conn.commit()
                        st.success("🎉 PHỤC HỒI THÀNH CÔNG! Toàn bộ hệ thống đã được khôi phục. Vui lòng bấm F5 (Tải lại trang web).")
                    except Exception as e:
                        conn.rollback()
                        st.error(f"❌ Lỗi trong quá trình phục hồi: {e}")
    elif mk_nhap != "":
        st.error("❌ Mật khẩu không chính xác! Không thể sử dụng công cụ phục hồi.")

st.markdown("---")
st.markdown("*Lưu ý: Quá trình Phục hồi có thể mất từ 10 - 30 giây tùy thuộc vào dung lượng file. Vui lòng không đóng trình duyệt khi hệ thống đang xử lý.*")
