import streamlit as st
import pandas as pd
from datetime import date, datetime
import time
from fpdf import FPDF
import os
from db_utils import get_connection

st.set_page_config(page_title="Quản Lý Đơn Hàng", page_icon="📝", layout="wide")
st.header("📝 Lên Đơn Hàng Đa Sản Phẩm")
conn = get_connection()
c = conn.cursor()

# ==========================================
# KHỞI TẠO BẢNG DON_HANG (SỬA LỖI UNDEFINED TABLE)
# ==========================================
c.execute('''CREATE TABLE IF NOT EXISTS don_hang (
                id SERIAL PRIMARY KEY,
                ngay TEXT,
                so_phieu TEXT,
                ten_kh TEXT,
                ten_sp TEXT,
                so_luong REAL,
                don_gia REAL,
                doanh_thu REAL,
                tong_nvl REAL,
                tong_cong_ep REAL,
                loi_nhuan REAL
            )''')
# ==========================================

# Khởi tạo "Giỏ hàng tạm" trong bộ nhớ của Streamlit
if 'gio_hang' not in st.session_state:
    st.session_state.gio_hang = []

# Đọc dữ liệu an toàn (Chống lỗi nếu chưa tạo danh mục)
try: 
    df_sp = pd.read_sql("SELECT * FROM dm_san_pham", conn)
except: 
    df_sp = pd.DataFrame()

try: 
    df_kh = pd.read_sql("SELECT * FROM dm_khach_hang", conn)
except: 
    df_kh = pd.DataFrame()

# Bây giờ bảng don_hang chắc chắn đã được tạo nên đọc thoải mái
df_dh = pd.read_sql("SELECT * FROM don_hang ORDER BY id DESC", conn)

# ==========================================
# THUẬT TOÁN TÌM SỐ PHIẾU TỰ ĐỘNG
# ==========================================
def lay_so_phieu_ke_tiep(df_don_hang):
    if df_don_hang.empty:
        return "01" # Mặc định nếu xưởng chưa có đơn nào
    try:
        # Chỉ lấy các số phiếu là Dữ liệu Số, tìm số lớn nhất
        cac_so_phieu = pd.to_numeric(df_don_hang['so_phieu'], errors='coerce').dropna()
        if not cac_so_phieu.empty:
            max_phieu = int(cac_so_phieu.max())
            next_phieu = max_phieu + 1
            # Format: Định dạng tối thiểu 2 chữ số (VD: 04, 05... 12, 1374)
            return f"{next_phieu:02d}" 
        return "01"
    except:
        return "01"

next_so_phieu = lay_so_phieu_ke_tiep(df_dh)
# ==========================================

if df_sp.empty or df_kh.empty:
    st.warning("⚠️ Vui lòng cập nhật Danh Mục Khách Hàng và Sản Phẩm trước khi nhập đơn!")
else:
    tab1, tab2, tab3 = st.tabs(["🛒 Lập Phiếu & Chọn Hàng", "📋 Sửa Đơn Hàng", "🖨️ In Phiếu Giao Hàng"])

    # ==========================================
    # TAB 1: LÊN ĐƠN HÀNG (CÓ GIỎ HÀNG KIỂM TRA)
    # ==========================================
    with tab1:
        st.subheader("1. Thông Tin Phiếu (Áp dụng chung)")
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            ngay_tao = st.date_input("Ngày giao dịch", date.today())
        with col_c2:
            # Ô Số Phiếu giờ đã được TỰ ĐỘNG ĐIỀN số mới nhất
            so_phieu = st.text_input("Số phiếu (Tự động tăng)", value=next_so_phieu)
        with col_c3:
            khach_hang = st.selectbox("Khách hàng", df_kh['ten_kh'].tolist())
            nhom_kh = df_kh[df_kh['ten_kh'] == khach_hang].iloc[0]['nhom_kh']

        st.markdown("---")
        st.subheader("2. Thêm Sản Phẩm Vào Danh Sách")
        col_sp1, col_sp2, col_sp3 = st.columns([2, 1, 1])
        
        with col_sp1:
            san_pham = st.selectbox("Chọn Sản phẩm", df_sp['ten_sp'].tolist())
            sp_info = df_sp[df_sp['ten_sp'] == san_pham].iloc[0]
            gia_dai_ly = sp_info.get('gia_dai_ly', 0)
            gia_khach_le = sp_info.get('gia_khach_le', 0)
            gia_goi_y = gia_dai_ly if nhom_kh == "Đại lý" else gia_khach_le
            st.caption(f"💡 Giá hệ thống gợi ý: {gia_goi_y:,.0f} đ/cái")
            
        with col_sp2:
            so_luong = st.number_input("Số lượng (Cái)", min_value=1, step=1, value=1)
        with col_sp3:
            don_gia = st.number_input("Giá bán chốt (VNĐ)", min_value=0.0, value=float(gia_goi_y), step=100.0)

        # Nút Thêm vào giỏ
        if st.button("⬇️ Thêm Vào Danh Sách Kiểm Tra", use_container_width=True):
            doanh_thu = so_luong * don_gia
            tong_nvl = so_luong * (sp_info['dinh_muc_nhua'] / 1000) * sp_info['don_gia_nhua']
            tong_cong_ep = so_luong * sp_info['don_gia_cong']
            loi_nhuan = doanh_thu - tong_nvl - tong_cong_ep

            item = {
                "Sản Phẩm": san_pham,
                "Số Lượng": so_luong,
                "Đơn Giá": don_gia,
                "Thành Tiền": doanh_thu,
                "Lợi Nhuận": loi_nhuan,
                "tong_nvl": tong_nvl,
                "tong_cong_ep": tong_cong_ep
            }
            st.session_state.gio_hang.append(item)
            st.rerun()

        st.markdown("---")
        # ==========================================
        # KHU VỰC KIỂM TRA ĐƠN HÀNG
        # ==========================================
        st.subheader("3. Kiểm Tra Danh Sách & Chốt Phiếu")
        
        if len(st.session_state.gio_hang) > 0:
            df_gio = pd.DataFrame(st.session_state.gio_hang)
            
            st.dataframe(
                df_gio[["Sản Phẩm", "Số Lượng", "Đơn Giá", "Thành Tiền", "Lợi Nhuận"]].style.format(
                    {"Số Lượng": "{:,.0f}", "Đơn Giá": "{:,.0f}", "Thành Tiền": "{:,.0f}", "Lợi Nhuận": "{:,.0f}"}
                ),
                use_container_width=True, hide_index=True
            )
            
            col_x1, col_x2 = st.columns(2)
            with col_x1:
                if st.button("❌ Xóa sản phẩm vừa thêm"):
                    st.session_state.gio_hang.pop()
                    st.rerun()
            with col_x2:
                if st.button("🗑️ Làm mới toàn bộ danh sách"):
                    st.session_state.gio_hang = []
                    st.rerun()

            tong_tien = df_gio["Thành Tiền"].sum()
            tong_loi = df_gio["Lợi Nhuận"].sum()
            st.success(f"💰 **TỔNG GIÁ TRỊ PHIẾU:** {tong_tien:,.0f} VNĐ | **TỔNG LÃI DỰ KIẾN:** {tong_loi:,.0f} VNĐ")

            # Nút CHỐT LƯU 
            if st.button("💾 CHỐT LƯU TOÀN BỘ PHIẾU VÀO HỆ THỐNG", type="primary", use_container_width=True):
                if not so_phieu:
                    st.error("⚠️ Vui lòng nhập Số Phiếu ở Bước 1 trước khi lưu!")
                else:
                    c = conn.cursor()
                    try:
                        for idx, item in df_gio.iterrows():
                            # ĐÃ ĐỔI 10 DẤU ? THÀNH %s
                            c.execute("""INSERT INTO don_hang
                                         (ngay, so_phieu, ten_kh, ten_sp, so_luong, don_gia, doanh_thu, tong_nvl, tong_cong_ep, loi_nhuan)
                                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                                      (ngay_tao.strftime("%Y-%m-%d"), so_phieu, khach_hang, item["Sản Phẩm"], item["Số Lượng"], item["Đơn Giá"], item["Thành Tiền"], item["tong_nvl"], item["tong_cong_ep"], item["Lợi Nhuận"]))
                        st.session_state.gio_hang = [] 
                        st.success(f"🎉 Đã lưu thành công {len(df_gio)} sản phẩm vào Phiếu {so_phieu}!")
                        time.sleep(1.5)
                        st.rerun() # Refresh trang để nó tự động nhảy lên số phiếu tiếp theo
                    except Exception as e:
                        st.error(f"⚠️ Có lỗi xảy ra: {e}")
        else:
            st.info("Danh sách đang trống. Hãy chọn sản phẩm ở trên và bấm 'Thêm Vào Danh Sách Kiểm Tra'.")

    # ==========================================
    # TAB 2: SỬA ĐƠN HÀNG TRỰC TIẾP TRÊN BẢNG
    # ==========================================
    with tab2:
        st.subheader("Sửa Dữ Liệu Các Phiếu Gần Đây")
        if not df_dh.empty:
            phieu_can_sua = st.selectbox("Chọn Số Phiếu cần sửa:", df_dh['so_phieu'].unique().tolist())
            
            df_edit = df_dh[df_dh['so_phieu'] == phieu_can_sua].copy()
            st.info(f"Đang hiển thị {len(df_edit)} sản phẩm của Phiếu: **{phieu_can_sua}** (Click đúp để sửa)")
            
            edited_df = st.data_editor(
                df_edit[['id', 'ten_sp', 'so_luong', 'don_gia']],
                column_config={
                    "id": None,
                    "ten_sp": st.column_config.SelectboxColumn("Sản Phẩm", options=df_sp['ten_sp'].tolist()),
                    "so_luong": st.column_config.NumberColumn("Số Lượng", step=1),
                    "don_gia": st.column_config.NumberColumn("Đơn Giá", step=100)
                },
                use_container_width=True, hide_index=True
            )
            
            if st.button("💾 Cập nhật thay đổi", type="primary"):
                c = conn.cursor()
                try:
                    for index, row in edited_df.iterrows():
                        sp_info_new = df_sp[df_sp['ten_sp'] == row['ten_sp']].iloc[0]
                        new_doanh = row['so_luong'] * row['don_gia']
                        new_nvl = row['so_luong'] * (sp_info_new['dinh_muc_nhua'] / 1000) * sp_info_new['don_gia_nhua']
                        new_cong = row['so_luong'] * sp_info_new['don_gia_cong']
                        new_loi = new_doanh - new_nvl - new_cong
                        
                        # ĐÃ ĐỔI DẤU ? THÀNH %s VÀ ÉP KIỂU id THÀNH int
                        c.execute("""UPDATE don_hang 
                                     SET ten_sp=%s, so_luong=%s, don_gia=%s, doanh_thu=%s, tong_nvl=%s, tong_cong_ep=%s, loi_nhuan=%s 
                                     WHERE id=%s""",
                                  (row['ten_sp'], row['so_luong'], row['don_gia'], new_doanh, new_nvl, new_cong, new_loi, int(row['id'])))
                    st.success("✅ Cập nhật dữ liệu phiếu thành công!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi: {e}")
        else:
            st.info("Chưa có đơn hàng nào.")

    # ==========================================
    # TAB 3: XUẤT FILE PDF FORM DOANH NGHIỆP
    # ==========================================
    with tab3:
        st.subheader("In Phiếu Giao Hàng / Hóa Đơn")
        if not df_dh.empty:
            phieu_in = st.selectbox("Chọn Số Phiếu cần in:", df_dh['so_phieu'].unique().tolist(), key="print_phieu")
            df_phieu_in = df_dh[df_dh['so_phieu'] == phieu_in]
            thong_tin_chung = df_phieu_in.iloc[0]
            
            st.write(f"Đang chuẩn bị in Phiếu **{phieu_in}**. Khách hàng: **{thong_tin_chung['ten_kh']}**.")
            
            def create_delivery_pdf(phieu_id, df_data):
                pdf = FPDF(format='A5')
                pdf.add_page()
                
                if not (os.path.exists("arial.ttf") and os.path.exists("arialbd.ttf")):
                    st.error("🚨 LỖI: Không tìm thấy font chữ arial.ttf!")
                    return None
                
                # BỔ SUNG uni=True ĐỂ TRÁNH LỖI UNICODE TRÊN CLOUD
                pdf.add_font("Arial", "", "arial.ttf", uni=True)
                pdf.add_font("Arial", "B", "arialbd.ttf", uni=True)
                
                # HEADER
                start_y = 10 
                logo_path = 'logo.png'
                if os.path.exists(logo_path):
                    pdf.image(logo_path, x=10, y=start_y, w=40)
                else:
                    pdf.set_xy(10, start_y + 5)
                    pdf.set_font("Arial", "B", 18)
                    pdf.cell(40, 10, "WANCHI", border=0, align="C")
                
                pdf.set_xy(55, start_y)
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 5, "CÔNG TY TNHH WANCHI", ln=True)
                
                pdf.set_xy(55, start_y + 6)
                pdf.set_font("Arial", "", 10)
                pdf.multi_cell(0, 4.5, "775 Võ Hữu Lợi (KCN Lê Minh Xuân 3), Xã Lê Minh Xuân, Huyện Bình Chánh, TP.HCM")
                
                current_y = pdf.get_y() + 1
                pdf.set_xy(55, current_y)
                pdf.cell(0, 5, "Điện thoại: 0902580828 - 0937572577", ln=True)
                
                # TIÊU ĐỀ
                pdf.ln(10) 
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 10, "PHIẾU GIAO HÀNG", align="C", ln=True)
                
                # THÔNG TIN KHÁCH
                pdf.ln(2)
                info = df_data.iloc[0]
                pdf.set_font("Arial", "", 11)
                
                try:
                    ngay_vn = datetime.strptime(info['ngay'], "%Y-%m-%d").strftime("%d/%m/%Y")
                except:
                    ngay_vn = date.today().strftime("%d/%m/%Y")

                pdf.cell(0, 6, f"Số phiếu: {info['so_phieu']}  |  Ngày giao: {ngay_vn}", ln=True)
                pdf.cell(0, 6, f"Khách hàng: {info['ten_kh']}", ln=True)
                
                pdf.ln(3)
                pdf.set_line_width(0.3)
                pdf.line(10, pdf.get_y(), 138, pdf.get_y())
                pdf.ln(5)
                
                # BẢNG SẢN PHẨM
                pdf.set_font("Arial", "B", 10)
                pdf.cell(60, 8, "Tên Sản Phẩm", border=1, align="C")
                pdf.cell(15, 8, "SL", border=1, align="C")
                pdf.cell(25, 8, "Đơn Giá", border=1, align="C")
                pdf.cell(35, 8, "Thành Tiền", border=1, align="C", ln=True)
                
                pdf.set_font("Arial", "", 10)
                tong_cong = 0
                
                for idx, row in df_data.iterrows():
                    ten_sp_ngan = row['ten_sp'][:30] 
                    pdf.cell(60, 10, ten_sp_ngan, border=1)
                    pdf.cell(15, 10, f"{row['so_luong']:,.0f}", border=1, align="C")
                    pdf.cell(25, 10, f"{row['don_gia']:,.0f}", border=1, align="R")
                    pdf.cell(35, 10, f"{row['doanh_thu']:,.0f}", border=1, align="R", ln=True)
                    tong_cong += row['doanh_thu']
                
                pdf.set_font("Arial", "B", 10)
                pdf.cell(100, 10, "TỔNG CỘNG:", border=1, align="R")
                pdf.cell(35, 10, f"{tong_cong:,.0f} VNĐ", border=1, align="R", ln=True)
                
                # CHỮ KÝ
                pdf.ln(8)
                pdf.set_font("Arial", "B", 10)
                pdf.cell(65, 6, "Người Giao Hàng", align="C")
                pdf.cell(70, 6, "Khách Hàng Nhận", align="C", ln=True)
                pdf.set_font("Arial", "", 9)
                pdf.cell(65, 5, "(Ký & ghi rõ họ tên)", align="C")
                pdf.cell(70, 5, "(Ký & ghi rõ họ tên)", align="C", ln=True)
                
                return bytes(pdf.output())

            pdf_bytes = create_delivery_pdf(phieu_in, df_phieu_in)
            
            if pdf_bytes:
                st.download_button(
                    label="📄 Tải Phiếu Giao Hàng (PDF)",
                    data=pdf_bytes,
                    file_name=f"Phieu_Giao_Hang_{phieu_in}.pdf",
                    mime="application/pdf",
                    type="primary"
                )
