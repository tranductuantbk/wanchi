import streamlit as st
import pandas as pd
from datetime import date
import time
import json
import io 
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

tab1, tab2, tab3 = st.tabs(["📝 Tạo hóa đơn đại lý", "📊 Bảng theo dõi hóa đơn đại lý", "📑 Import Thuế WANCHI"])

# ==========================================
# TAB 1: TẠO HÓA ĐƠN ĐẠI LÝ (BẢNG IMPORT THUẾ)
# ==========================================
with tab1:
    st.subheader("1. Chọn Đơn Hàng & Chế Độ Giá")
    
    # Lấy danh sách các đơn hàng chưa được tạo hóa đơn để chọn cho nhanh
    df_all_dh = pd.read_sql("SELECT d.ma_don, d.ten_kh FROM don_hang d ORDER BY d.id DESC", conn)
    danh_sach_don = ["-- Chọn Mã Đơn --"]
    if not df_all_dh.empty:
        danh_sach_don += df_all_dh['ma_don'].tolist()
        
    col_chon1, col_chon2 = st.columns([1, 1])
    with col_chon1:
        ma_don_input = st.selectbox("🔍 Chọn Mã Đơn (Thay cho nhập tay):", danh_sach_don)
    with col_chon2:
        chon_che_do = st.radio("Chọn phương thức tính giá:", ["Giữ nguyên giá", "Chia 0.95"], index=0, horizontal=True)
    
    if ma_don_input != "-- Chọn Mã Đơn --":
        # Lấy dữ liệu từ bảng don_hang chuẩn xác
        df_don_hang = pd.read_sql("SELECT ten_kh, tong_tien, chi_tiet FROM don_hang WHERE ma_don = %s", conn, params=(ma_don_input,))
        
        if df_don_hang.empty:
            st.warning(f"⚠️ Không tìm thấy chi tiết cho Mã Đơn '{ma_don_input}'.")
        else:
            ten_kh = df_don_hang.iloc[0]['ten_kh']
            chi_tiet_json = df_don_hang.iloc[0]['chi_tiet']
            tong_tien_chot = 0 

            st.markdown("---")
            st.subheader(f"2. Bảng Import Thuế - Khách Hàng: **{ten_kh}**")

            # Rã đông JSON để vẽ bảng
            if pd.notna(chi_tiet_json) and chi_tiet_json:
                try:
                    items = json.loads(chi_tiet_json)
                    df_items = pd.DataFrame(items)
                    
                    # Chuẩn hóa tên cột
                    if 'Tên Sản Phẩm' in df_items.columns:
                        sp_col = 'Tên Sản Phẩm'
                    elif 'Tên Sản Phẩm OME' in df_items.columns:
                        sp_col = 'Tên Sản Phẩm OME'
                    else:
                        sp_col = df_items.columns[0] 

                    df_items = df_items.rename(columns={sp_col: 'ten_sp', 'Số Lượng': 'so_luong', 'Đơn Giá': 'don_gia'})
                    if 'Đơn Giá OME' in df_items.columns:
                        df_items['don_gia'] = df_items['Đơn Giá OME']

                    # Logic tính giá
                    if chon_che_do == "Chia 0.95":
                        df_items['don_gia_thue'] = df_items['don_gia'].astype(float) / 0.95
                    else:
                        df_items['don_gia_thue'] = df_items['don_gia'].astype(float)
                    
                    df_items['tien_thue'] = df_items['so_luong'].astype(float) * df_items['don_gia_thue']
                    tong_tien_chot = df_items['tien_thue'].sum()

                    # Bảng kê chuẩn Import Thuế
                    df_hien_thi = pd.DataFrame({
                        "Mã vt": "",
                        "Tên vt": df_items.get('ten_sp', ""),
                        "Đvt": "Cái",
                        "Số lượng": df_items.get('so_luong', 0),
                        "Giá": df_items.get('don_gia_thue', 0),
                        "Tiền": df_items.get('tien_thue', 0),
                        "Giá ngoại tệ": "",
                        "Tiền ngoại tệ": "",
                        "%CK": "",
                        "Chiết khấu": "",
                        "Thuế suất": "",
                        "Thuế": ""
                    })
                    
                    st.dataframe(
                        df_hien_thi.style.format({
                            "Số lượng": "{:,.0f}", 
                            "Giá": "{:,.0f}", 
                            "Tiền": "{:,.0f}"
                        }, na_rep=""),
                        use_container_width=True, hide_index=True
                    )
                except Exception as e:
                    st.error(f"Lỗi đọc chi tiết đơn hàng: {e}")
                    tong_tien_chot = float(df_don_hang.iloc[0]['tong_tien'])

            st.markdown(f"### 💰 TỔNG TIỀN HÓA ĐƠN: **{tong_tien_chot:,.0f} VNĐ**")

            st.markdown("---")
            if st.button("💾 LƯU HÓA ĐƠN & TẢI EXCEL", type="primary"):
                check_hd = pd.read_sql("SELECT ma_don FROM hoa_don WHERE ma_don = %s", conn, params=(ma_don_input,))
                if not check_hd.empty:
                    st.error(f"⚠️ Hóa đơn cho Mã Đơn {ma_don_input} đã được lập và lưu trước đó!")
                else:
                    try:
                        ngay_hd = date.today().strftime("%Y-%m-%d")
                        # Lưu với các giá trị mặc định cho da_thu, con_no (vì quản lý nợ qua công thức thuế)
                        c.execute("""INSERT INTO hoa_don 
                                     (ngay, ma_don, so_phieu, ten_kh, tong_tien, da_thu, con_no, import_thue, ghi_chu) 
                                     VALUES (%s, %s, %s, %s, %s, 0, 0, 'Không', '')""",
                                  (ngay_hd, ma_don_input, ma_don_input, ten_kh, tong_tien_chot))
                        conn.commit()
                        st.success(f"🎉 Đã lưu thành công hóa đơn cho Mã Đơn {ma_don_input} vào Bảng Theo Dõi!")
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Lỗi hệ thống: {e}")
                
                # TỰ ĐỘNG TẠO FILE EXCEL TẢI XUỐNG
                try:
                    import openpyxl
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_hien_thi.to_excel(writer, index=False, sheet_name='Import_Thue')
                    excel_data = output.getvalue()
                    
                    st.download_button(
                        label="📥 BẤM VÀO ĐÂY ĐỂ TẢI FILE EXCEL IMPORT THUẾ",
                        data=excel_data,
                        file_name=f"Import_Thue_{ma_don_input}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary"
                    )
                except ImportError:
                    st.error("⚠️ Đám mây đang thiếu thư viện `openpyxl`. Vui lòng cài đặt!")
                    csv_data = df_hien_thi.to_csv(index=False).encode('utf-8-sig') 
                    st.download_button("📥 Tải Tạm File CSV", data=csv_data, file_name=f"Import_Thue_{ma_don_input}.csv", mime="text/csv", type="secondary")

# ==========================================
# TAB 2: BẢNG THEO DÕI HÓA ĐƠN ĐẠI LÝ
# ==========================================
with tab2:
    st.subheader("Bảng Theo Dõi Hóa Đơn Đại Lý")
    
    df_hd = pd.read_sql("SELECT id, ngay, COALESCE(ma_don, so_phieu) as ma_don, ten_kh, tong_tien FROM hoa_don ORDER BY id DESC", conn)
    
    if df_hd.empty:
        st.info("Chưa có dữ liệu hóa đơn nào được lưu.")
    else:
        loc_kh = st.selectbox("🔍 Lọc theo Khách hàng", ["Tất cả"] + df_hd['ten_kh'].unique().tolist())

        df_hien_thi_hd = df_hd.copy()
        if loc_kh != "Tất cả":
            df_hien_thi_hd = df_hien_thi_hd[df_hien_thi_hd['ten_kh'] == loc_kh]

        # Chỉ giữ lại 4 cột theo yêu cầu
        df_hien_thi_hd = df_hien_thi_hd[['ngay', 'ma_don', 'ten_kh', 'tong_tien']]
        df_hien_thi_hd.columns = ['Ngày Lập', 'Mã Đơn', 'Khách Hàng', 'Tổng Tiền Hóa Đơn']

        st.dataframe(
            df_hien_thi_hd.style.format({
                "Tổng Tiền Hóa Đơn": "{:,.0f}"
            }),
            use_container_width=True, hide_index=True
        )

        # Nếu đang lọc 1 Khách hàng cụ thể, hiển thị Bảng Công Nợ Thuế
        if loc_kh != "Tất cả":
            st.markdown("---")
            st.subheader(f"📊 Bảng Chi Tiết Công Nợ - Khách Hàng: **{loc_kh}**")
            
            tong_tien_hd = df_hien_thi_hd['Tổng Tiền Hóa Đơn'].sum()
            # Logic tính toán nợ: Tổng tiền / 0.95 - Tổng tiền
            tien_no = (tong_tien_hd / 0.95) - tong_tien_hd
            
            df_summary = pd.DataFrame({
                "Tên Khách Hàng": [loc_kh],
                "Tổng Tiền Hóa Đơn": [tong_tien_hd],
                "Số Tiền Khách Còn Nợ": [tien_no]
            })
            
            st.dataframe(
                df_summary.style.format({
                    "Tổng Tiền Hóa Đơn": "{:,.0f} VNĐ",
                    "Số Tiền Khách Còn Nợ": "{:,.0f} VNĐ"
                }),
                use_container_width=True, hide_index=True
            )

# ==========================================
# TAB 3: IMPORT THUẾ WANCHI (CÔNG CỤ PHỤ)
# ==========================================
with tab3:
    st.subheader("Trích Xuất Dữ Liệu Khai Báo Thuế Độc Lập")
    st.markdown("💡 *Đây là công cụ trích xuất độc lập dành cho Kế toán, không lưu vào dữ liệu theo dõi công nợ.*")
    
    col_p1, col_p2 = st.columns([1, 2])
    with col_p1:
        ma_don_import = st.text_input("📝 Nhập Mã Đơn (VD: DH-0001):", key="import_thue_phieu").strip()
        chon_che_do_thue = st.radio("Chọn phương thức tính giá:", ["Giữ nguyên giá", "Chia 0.95"], index=1, horizontal=True, key="radio_thue")

    if ma_don_import:
        df_dh_import = pd.read_sql("SELECT chi_tiet FROM don_hang WHERE ma_don = %s", conn, params=(ma_don_import,))

        if df_dh_import.empty or pd.isna(df_dh_import.iloc[0]['chi_tiet']):
            st.warning(f"⚠️ Không tìm thấy dữ liệu sản phẩm cho Mã Đơn {ma_don_import}")
        else:
            try:
                items_import = json.loads(df_dh_import.iloc[0]['chi_tiet'])
                df_items_thue = pd.DataFrame(items_import)

                if 'Tên Sản Phẩm' in df_items_thue.columns:
                    sp_col_thue = 'Tên Sản Phẩm'
                elif 'Tên Sản Phẩm OME' in df_items_thue.columns:
                    sp_col_thue = 'Tên Sản Phẩm OME'
                else:
                    sp_col_thue = df_items_thue.columns[0] 

                df_items_thue = df_items_thue.rename(columns={sp_col_thue: 'ten_sp', 'Số Lượng': 'so_luong', 'Đơn Giá': 'don_gia', 'Thành Tiền': 'doanh_thu'})
                if 'Đơn Giá OME' in df_items_thue.columns:
                    df_items_thue['don_gia'] = df_items_thue['Đơn Giá OME']

                if chon_che_do_thue == "Chia 0.95":
                    df_items_thue['don_gia_thue'] = df_items_thue['don_gia'].astype(float) / 0.95
                else:
                    df_items_thue['don_gia_thue'] = df_items_thue['don_gia'].astype(float)
                
                df_items_thue['tien_thue'] = df_items_thue['so_luong'].astype(float) * df_items_thue['don_gia_thue']
                tong_tien_import = df_items_thue['tien_thue'].sum()

                with col_p2:
                    st.markdown(f"<h3 style='color: #0066cc; margin-top: 25px;'>Tổng tiền: {tong_tien_import:,.0f}</h3>", unsafe_allow_html=True)

                df_import_thue = pd.DataFrame({
                    "Mã vt": "",
                    "Tên vt": df_items_thue.get('ten_sp', ""),
                    "Đvt": "Cái",
                    "Số lượng": df_items_thue.get('so_luong', 0),
                    "Giá": df_items_thue.get('don_gia_thue', 0),
                    "Tiền": df_items_thue.get('tien_thue', 0),
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
                
                try:
                    import openpyxl
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_import_thue.to_excel(writer, index=False, sheet_name='Import_Thue')
                    excel_data = output.getvalue()
                    
                    st.download_button(
                        label="📥 Tải File Excel (.xlsx) Để Import Kế Toán",
                        data=excel_data,
                        file_name=f"Import_Thue_{ma_don_import}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary"
                    )
                except ImportError:
                    st.error("⚠️ Đám mây đang thiếu thư viện `openpyxl`. Vui lòng cài đặt!")
                    csv_data = df_import_thue.to_csv(index=False).encode('utf-8-sig') 
                    st.download_button("📥 Tải Tạm File CSV", data=csv_data, file_name=f"Import_Thue_{ma_don_import}.csv", mime="text/csv", type="secondary")

            except Exception as e:
                st.error(f"Lỗi xử lý dữ liệu: {e}")
