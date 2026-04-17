import streamlit as st
import pandas as pd
from datetime import date
import time
from db_utils import get_connection

st.set_page_config(page_title="Hóa Đơn & Công Nợ", page_icon="🧾", layout="wide")
st.header("🧾 Quản Lý Hóa Đơn & Công Nợ")
conn = get_connection()
c = conn.cursor()

# ==========================================
# KHỞI TẠO BẢNG DATABASE CHO CLOUD (POSTGRESQL)
# ==========================================
c.execute('''CREATE TABLE IF NOT EXISTS hoa_don (
                id SERIAL PRIMARY KEY,
                ngay TEXT,
                so_phieu TEXT,
                ten_kh TEXT,
                tong_tien REAL,
                da_thu REAL,
                con_no REAL,
                import_thue TEXT DEFAULT 'Không',
                ghi_chu TEXT
            )''')

# Ép nâng cấp cột cho an toàn (Thay thế hoàn toàn lệnh PRAGMA cũ của SQLite)
try:
    c.execute("ALTER TABLE hoa_don ADD COLUMN import_thue TEXT DEFAULT 'Không'")
except:
    pass

# ==========================================

tab1, tab2, tab3 = st.tabs(["📝 Lập Hóa Đơn", "📊 Bảng Kê Hóa Đơn & Công Nợ", "📑 Import Thuế (Mẫu Kế Toán)"])

# ==========================================
# TAB 1: LẬP HÓA ĐƠN
# ==========================================
with tab1:
    st.subheader("1. Tìm Kiếm & Khai Báo Khách Hàng")
    so_phieu_input = st.text_input("🔍 Nhập Số Phiếu cần lập hóa đơn:")
    
    if so_phieu_input:
        # ĐÃ ĐỔI DẤU ? THÀNH %s
        df_don_hang = pd.read_sql("SELECT * FROM don_hang WHERE so_phieu = %s", conn, params=(so_phieu_input,))
        
        if df_don_hang.empty:
            st.warning("⚠️ Không tìm thấy đơn hàng nào với Số Phiếu này!")
        else:
            ten_kh = df_don_hang.iloc[0]['ten_kh']

            st.markdown("---")
            st.subheader(f"2. Chi Tiết Sản Phẩm - Khách Hàng: **{ten_kh}**")

            df_hien_thi = df_don_hang[['ten_sp', 'so_luong', 'don_gia', 'doanh_thu']].copy()
            df_hien_thi.columns = ["Tên Sản Phẩm", "Số Lượng", "Đơn Giá", "Thành Tiền"]
            
            st.dataframe(
                df_hien_thi.style.format({
                    "Số Lượng": "{:,.0f}", 
                    "Đơn Giá": "{:,.0f}", 
                    "Thành Tiền": "{:,.0f}"
                }),
                use_container_width=True, hide_index=True
            )

            tong_tien_chot = float(df_don_hang['doanh_thu'].sum())
            st.markdown(f"### 💰 TỔNG CỘNG HÓA ĐƠN: **{tong_tien_chot:,.0f} VNĐ**")

            st.markdown("---")
            st.subheader("3. Ghi Nhận Thanh Toán & Công Nợ")
            
            col_nhap1, col_nhap2, col_nhap3 = st.columns(3)
            with col_nhap1:
                ngay_hd = st.date_input("Ngày lập hóa đơn", date.today())
                da_thu = st.number_input("Số tiền khách ĐÃ THANH TOÁN (VNĐ)", min_value=0.0, value=0.0, step=100000.0)
            with col_nhap2:
                import_thue = st.selectbox("Đánh dấu Import Thuế", ["Không", "Có"])
            with col_nhap3:
                ghi_chu = st.text_area("Ghi chú hóa đơn")

            con_no = tong_tien_chot - da_thu
            if con_no > 0:
                st.warning(f"🚨 Khách còn nợ: **{con_no:,.0f} VNĐ**")
            elif con_no < 0:
                st.success(f"Khách đưa dư: {-con_no:,.0f} VNĐ")
            else:
                st.success("✅ Khách đã thanh toán đủ 100%.")

            if st.button("💾 LƯU HÓA ĐƠN & CÔNG NỢ", type="primary"):
                # ĐÃ ĐỔI DẤU ? THÀNH %s
                check_hd = pd.read_sql("SELECT so_phieu FROM hoa_don WHERE so_phieu = %s", conn, params=(so_phieu_input,))
                if not check_hd.empty:
                    st.error(f"⚠️ Hóa đơn cho Số Phiếu {so_phieu_input} đã được lưu trước đó!")
                else:
                    try:
                        # ĐÃ ĐỔI 8 DẤU ? THÀNH %s
                        c.execute("""INSERT INTO hoa_don 
                                     (ngay, so_phieu, ten_kh, tong_tien, da_thu, con_no, import_thue, ghi_chu) 
                                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                                  (ngay_hd.strftime("%Y-%m-%d"), so_phieu_input, ten_kh, tong_tien_chot, da_thu, con_no, import_thue, ghi_chu))
                        st.success(f"🎉 Đã lưu thành công hóa đơn Phiếu {so_phieu_input}!")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Lỗi hệ thống: {e}")

# ==========================================
# TAB 2: BẢNG KÊ HÓA ĐƠN & BỘ LỌC TỔNG HỢP
# ==========================================
with tab2:
    st.subheader("Bảng Kê Hóa Đơn & Quản Lý Công Nợ")
    
    df_hd = pd.read_sql("SELECT * FROM hoa_don ORDER BY id DESC", conn)
    
    if df_hd.empty:
        st.info("Chưa có dữ liệu hóa đơn nào được lưu.")
    else:
        col_loc1, col_loc2 = st.columns(2)
        with col_loc1:
            loc_kh = st.selectbox("🔍 Lọc theo Khách hàng", ["Tất cả"] + df_hd['ten_kh'].unique().tolist())
        with col_loc2:
            loc_thue = st.selectbox("🏷️ Lọc theo Import Thuế", ["Tất cả", "Có", "Không"])

        df_hien_thi_hd = df_hd.copy()
        if loc_kh != "Tất cả":
            df_hien_thi_hd = df_hien_thi_hd[df_hien_thi_hd['ten_kh'] == loc_kh]
        if loc_thue != "Tất cả":
            df_hien_thi_hd = df_hien_thi_hd[df_hien_thi_hd['import_thue'] == loc_thue]

        df_hien_thi_hd = df_hien_thi_hd[['ngay', 'so_phieu', 'ten_kh', 'tong_tien', 'da_thu', 'con_no', 'import_thue', 'ghi_chu']]
        df_hien_thi_hd.columns = ['Ngày Lập', 'Số Phiếu', 'Khách Hàng', 'Tổng Tiền', 'Đã Thu', 'Còn Nợ', 'Import Thuế', 'Ghi Chú']

        st.dataframe(
            df_hien_thi_hd.style.format({
                "Tổng Tiền": "{:,.0f}", 
                "Đã Thu": "{:,.0f}", 
                "Còn Nợ": "{:,.0f}"
            }),
            use_container_width=True, hide_index=True
        )

        st.markdown("---")
        tong_no = df_hien_thi_hd['Còn Nợ'].sum()
        tong_doanh = df_hien_thi_hd['Tổng Tiền'].sum()
        
        col_tk1, col_tk2 = st.columns(2)
        col_tk1.metric("📊 TỔNG DOANH THU ĐANG LỌC", f"{tong_doanh:,.0f} VNĐ")
        if tong_no > 0:
            col_tk2.error(f"🚨 TỔNG TIỀN KHÁCH ĐANG NỢ: {tong_no:,.0f} VNĐ")
        else:
            col_tk2.success("✅ Không có công nợ.")

# ==========================================
# TAB 3: IMPORT THUẾ CHUẨN FORM KẾ TOÁN
# ==========================================
with tab3:
    st.subheader("Trích Xuất Dữ Liệu Khai Báo Thuế")
    st.markdown("💡 *Nhập số phiếu đã tạo để trích xuất form tự động chuẩn xác theo phần mềm kế toán (MISA, FAST...)*")
    
    col_p1, col_p2 = st.columns([1, 2])
    with col_p1:
        so_phieu_import = st.text_input("📝 Phiếu:", key="import_thue_phieu")

    if so_phieu_import:
        # Lấy dữ liệu đơn hàng (ĐÃ ĐỔI DẤU ? THÀNH %s)
        df_dh_import = pd.read_sql("SELECT ten_sp, so_luong, don_gia, doanh_thu FROM don_hang WHERE so_phieu = %s", conn, params=(so_phieu_import,))

        if df_dh_import.empty:
            st.warning(f"⚠️ Không tìm thấy dữ liệu cho Phiếu số {so_phieu_import}")
        else:
            # Lấy thêm Mã SP từ bảng dm_san_pham
            try:
                df_sp_ma = pd.read_sql("SELECT ma_sp, ten_sp FROM dm_san_pham", conn)
                df_merged = pd.merge(df_dh_import, df_sp_ma, on='ten_sp', how='left')
            except:
                df_merged = df_dh_import.copy()
                df_merged['ma_sp'] = ""

            tong_tien_import = df_merged['doanh_thu'].sum()

            with col_p2:
                # Hiển thị tổng tiền màu xanh nổi bật giống y chang file Excel của bạn
                st.markdown(f"<h3 style='color: #0066cc; margin-top: 25px;'>Tổng tiền: {tong_tien_import:,.0f}</h3>", unsafe_allow_html=True)

            # Tạo khung xương bảng chuẩn 100% form kế toán bạn gửi
            df_import_thue = pd.DataFrame({
                "Mã vt": df_merged.get('ma_sp', ""),
                "Tên vt": df_merged['ten_sp'],
                "Đvt": "Cái",
                "Số lượng": df_merged['so_luong'],
                "Giá": df_merged['don_gia'],
                "Tiền": df_merged['doanh_thu'],
                "Giá ngoại tệ": "",
                "Tiền ngoại tệ": "",
                "%CK": "",
                "Chiết khấu": "",
                "Thuế suất": "",
                "Thuế": ""
            })

            # Hiển thị bảng
            st.dataframe(
                df_import_thue.style.format({
                    "Số lượng": "{:,.0f}",
                    "Giá": "{:,.0f}",
                    "Tiền": "{:,.0f}"
                }),
                use_container_width=True, hide_index=True
            )

            # Tích hợp thêm Nút Tải về định dạng CSV chuẩn Unicode để ném vào Excel/Phần mềm
            st.markdown("---")
            csv_data = df_import_thue.to_csv(index=False).encode('utf-8-sig') # utf-8-sig giúp Excel đọc tiếng Việt không bị lỗi font
            st.download_button(
                label="📥 Tải File Excel (CSV) Để Import",
                data=csv_data,
                file_name=f"Import_Thue_Phieu_{so_phieu_import}.csv",
                mime="text/csv",
                type="primary"
            )