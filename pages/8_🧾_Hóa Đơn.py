import streamlit as st
import pandas as pd
from datetime import date
import time
import json
from db_utils import get_connection, check_password

st.set_page_config(page_title="Hóa Đơn & Công Nợ", page_icon="🧾", layout="wide")

# ==========================================
# Ổ KHÓA BẢO VỆ 2 LỚP
# ==========================================
role = check_password()
if not role: st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang Hóa Đơn & Công Nợ là dữ liệu mật, chỉ dành cho Quản lý / Kế toán WANCHI.")
    st.stop()

st.header("🧾 Quản Lý Hóa Đơn & Công Nợ")
conn = get_connection()
c = conn.cursor()

# ==========================================
# KHỞI TẠO BẢNG DATABASE CHO CLOUD (POSTGRESQL)
# ==========================================
try:
    c.execute('''CREATE TABLE IF NOT EXISTS hoa_don (
                    id SERIAL PRIMARY KEY,
                    ngay TEXT,
                    ma_don TEXT,
                    so_phieu TEXT,
                    ten_kh TEXT,
                    tong_tien REAL,
                    da_thu REAL,
                    con_no REAL,
                    import_thue TEXT DEFAULT 'Không',
                    ghi_chu TEXT
                )''')
    conn.commit()
except Exception as e:
    conn.rollback()

# Ép nâng cấp cột cho an toàn
try:
    c.execute("ALTER TABLE hoa_don ADD COLUMN ma_don TEXT")
    conn.commit()
except: conn.rollback()

try:
    c.execute("ALTER TABLE hoa_don ADD COLUMN import_thue TEXT DEFAULT 'Không'")
    conn.commit()
except: conn.rollback()

# ==========================================

tab1, tab2, tab3 = st.tabs(["📝 Lập Hóa Đơn", "📊 Bảng Kê Hóa Đơn & Công Nợ", "📑 Import Thuế (Mẫu Kế Toán)"])

# ==========================================
# TAB 1: LẬP HÓA ĐƠN
# ==========================================
with tab1:
    st.subheader("1. Tìm Kiếm & Khai Báo Khách Hàng")
    ma_don_input = st.text_input("🔍 Nhập Mã Đơn (VD: DH-0001) cần lập hóa đơn:").strip()
    
    if ma_don_input:
        # Lấy dữ liệu từ bảng don_hang chuẩn xác
        df_don_hang = pd.read_sql("SELECT ten_kh, tong_tien, chi_tiet FROM don_hang WHERE ma_don = %s", conn, params=(ma_don_input,))
        
        if df_don_hang.empty:
            st.warning(f"⚠️ Không tìm thấy đơn hàng nào với Mã Đơn '{ma_don_input}'! Hãy kiểm tra lại Tab Lịch Sử bên file Tạo Đơn.")
        else:
            ten_kh = df_don_hang.iloc[0]['ten_kh']
            tong_tien_chot = float(df_don_hang.iloc[0]['tong_tien'])
            chi_tiet_json = df_don_hang.iloc[0]['chi_tiet']

            st.markdown("---")
            st.subheader(f"2. Chi Tiết Sản Phẩm - Khách Hàng: **{ten_kh}**")

            # Rã đông JSON để vẽ bảng
            if pd.notna(chi_tiet_json) and chi_tiet_json:
                try:
                    items = json.loads(chi_tiet_json)
                    df_hien_thi = pd.DataFrame(items)
                    
                    st.dataframe(
                        df_hien_thi.style.format({
                            "Số Lượng": "{:,.0f}", 
                            "Đơn Giá": "{:,.0f}", 
                            "Thành Tiền": "{:,.0f}",
                            "Đơn Giá OME": "{:,.0f}" 
                        }, na_rep=""),
                        use_container_width=True, hide_index=True
                    )
                except:
                    st.error("Lỗi đọc chi tiết đơn hàng (Dữ liệu JSON bị hỏng).")

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
                # Kiểm tra trùng lặp Hóa đơn
                check_hd = pd.read_sql("SELECT ma_don FROM hoa_don WHERE ma_don = %s OR so_phieu = %s", conn, params=(ma_don_input, ma_don_input))
                if not check_hd.empty:
                    st.error(f"⚠️ Hóa đơn cho Mã Đơn {ma_don_input} đã được lập và lưu trước đó!")
                else:
                    try:
                        c.execute("""INSERT INTO hoa_don 
                                     (ngay, ma_don, so_phieu, ten_kh, tong_tien, da_thu, con_no, import_thue, ghi_chu) 
                                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                                  (ngay_hd.strftime("%Y-%m-%d"), ma_don_input, ma_don_input, ten_kh, tong_tien_chot, da_thu, con_no, import_thue, ghi_chu))
                        conn.commit()
                        st.success(f"🎉 Đã lưu thành công hóa đơn cho Mã Đơn {ma_don_input}!")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Lỗi hệ thống: {e}")

# ==========================================
# TAB 2: BẢNG KÊ HÓA ĐƠN & BỘ LỌC TỔNG HỢP
# ==========================================
with tab2:
    st.subheader("Bảng Kê Hóa Đơn & Quản Lý Công Nợ")
    
    df_hd = pd.read_sql("SELECT id, ngay, COALESCE(ma_don, so_phieu) as ma_don, ten_kh, tong_tien, da_thu, con_no, import_thue, ghi_chu FROM hoa_don ORDER BY id DESC", conn)
    
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

        df_hien_thi_hd = df_hien_thi_hd[['ngay', 'ma_don', 'ten_kh', 'tong_tien', 'da_thu', 'con_no', 'import_thue', 'ghi_chu']]
        df_hien_thi_hd.columns = ['Ngày Lập', 'Mã Đơn', 'Khách Hàng', 'Tổng Tiền', 'Đã Thu', 'Còn Nợ', 'Import Thuế', 'Ghi Chú']

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
    st.markdown("💡 *Nhập Mã Đơn đã tạo để trích xuất form tự động chuẩn xác theo phần mềm kế toán (MISA, FAST...)*")
    
    col_p1, col_p2 = st.columns([1, 2])
    with col_p1:
        ma_don_import = st.text_input("📝 Mã Đơn (VD: DH-0001):", key="import_thue_phieu").strip()

    if ma_don_import:
        # Query lấy chi tiết từ JSON
        df_dh_import = pd.read_sql("SELECT chi_tiet FROM don_hang WHERE ma_don = %s", conn, params=(ma_don_import,))

        if df_dh_import.empty or pd.isna(df_dh_import.iloc[0]['chi_tiet']):
            st.warning(f"⚠️ Không tìm thấy dữ liệu sản phẩm cho Mã Đơn {ma_don_import}")
        else:
            try:
                items_import = json.loads(df_dh_import.iloc[0]['chi_tiet'])
                df_items = pd.DataFrame(items_import)

                # Chuẩn hóa tên cột để xuất Excel do có 2 loại đơn (Chuẩn và OME)
                if 'Tên Sản Phẩm' in df_items.columns:
                    sp_col = 'Tên Sản Phẩm'
                elif 'Tên Sản Phẩm OME' in df_items.columns:
                    sp_col = 'Tên Sản Phẩm OME'
                else:
                    sp_col = df_items.columns[0] 

                df_items = df_items.rename(columns={sp_col: 'ten_sp', 'Số Lượng': 'so_luong', 'Đơn Giá': 'don_gia', 'Thành Tiền': 'doanh_thu'})
                if 'Đơn Giá OME' in df_items.columns:
                    df_items['don_gia'] = df_items['Đơn Giá OME']

                # Nối với danh mục để lấy Mã SP
                try:
                    df_sp_ma = pd.read_sql("SELECT ma_sp, ten_sp FROM dm_san_pham", conn)
                    df_merged = pd.merge(df_items, df_sp_ma, on='ten_sp', how='left')
                except:
                    df_merged = df_items.copy()
                    df_merged['ma_sp'] = ""

                tong_tien_import = df_merged['doanh_thu'].sum()

                with col_p2:
                    st.markdown(f"<h3 style='color: #0066cc; margin-top: 25px;'>Tổng tiền: {tong_tien_import:,.0f}</h3>", unsafe_allow_html=True)

                # Form Excel chuẩn Kế toán Wanchi
                df_import_thue = pd.DataFrame({
                    "Mã vt": df_merged.get('ma_sp', ""),
                    "Tên vt": df_merged.get('ten_sp', ""),
                    "Đvt": "Cái",
                    "Số lượng": df_merged.get('so_luong', 0),
                    "Giá": df_merged.get('don_gia', 0),
                    "Tiền": df_merged.get('doanh_thu', 0),
                    "Giá ngoại tệ": "",
                    "Tiền ngoại tệ": "",
                    "%CK": "",
                    "Chiết khấu": "",
                    "Thuế suất": "",
                    "Thuế": ""
                })

                st.dataframe(
                    df_import_thue.style.format({
                        "Số lượng": "{:,.0f}",
                        "Giá": "{:,.0f}",
                        "Tiền": "{:,.0f}"
                    }),
                    use_container_width=True, hide_index=True
                )

                st.markdown("---")
                csv_data = df_import_thue.to_csv(index=False).encode('utf-8-sig') 
                st.download_button(
                    label="📥 Tải File Excel (CSV) Để Import",
                    data=csv_data,
                    file_name=f"Import_Thue_{ma_don_import}.csv",
                    mime="text/csv",
                    type="primary"
                )
            except Exception as e:
                st.error(f"Lỗi xử lý dữ liệu: {e}")
