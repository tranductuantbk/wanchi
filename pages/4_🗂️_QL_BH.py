import streamlit as st
import pandas as pd
from db_utils import get_connection, check_password
import os
from fpdf import FPDF
from datetime import date

st.set_page_config(page_title="Sổ Dữ Liệu Bán Hàng", page_icon="🗂️", layout="wide")

# ==========================================
# Ổ KHÓA BẢO VỆ 2 LỚP
# ==========================================
role = check_password()
if not role:
    st.stop() # Lớp 1: Bắt buộc nhập mật khẩu

if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Sổ Dữ Liệu Bán Hàng là tuyệt mật, chỉ dành cho Quản lý WANCHI.")
    st.stop() # Lớp 2: Đuổi nhân viên ra ngoài
# ==========================================

st.header("🗂️ Sổ Dữ Liệu Bán Hàng")

# Kết nối database thông qua cấu hình Neon
conn = get_connection()
try:
    df = pd.read_sql("SELECT * FROM don_hang ORDER BY id DESC", conn)
except:
    df = pd.DataFrame()

if not df.empty:
    col_loc1, col_loc2 = st.columns(2)
    with col_loc1:
        # Lọc bỏ các ô trống (NaN) để không bị lỗi danh sách
        kh_list = df['ten_kh'].dropna().unique().tolist() if 'ten_kh' in df.columns else []
        kh_filter = st.selectbox("🔍 Lọc theo Khách hàng", ["Tất cả"] + kh_list)
    with col_loc2:
        sp_list = df['ten_sp'].dropna().unique().tolist() if 'ten_sp' in df.columns else []
        sp_filter = st.selectbox("🔍 Lọc theo Sản phẩm", ["Tất cả"] + sp_list)

    # Xử lý lọc dữ liệu
    df_hien_thi = df.copy()
    if kh_filter != "Tất cả":
        df_hien_thi = df_hien_thi[df_hien_thi['ten_kh'] == kh_filter]
    if sp_filter != "Tất cả" and 'ten_sp' in df_hien_thi.columns:
        df_hien_thi = df_hien_thi[df_hien_thi['ten_sp'] == sp_filter]

    # ==========================================
    # CỖ MÁY ĐỊNH DẠNG SỐ AN TOÀN (CHỐNG SẬP WEB)
    # ==========================================
    def format_tien_an_toan(val):
        try:
            return "{:,.0f}".format(float(val))
        except (ValueError, TypeError):
            return val # Nếu là khoảng trống hoặc chữ, giữ nguyên không báo lỗi

    format_dict = {}
    cac_cot_tien = ['so_luong', 'don_gia', 'doanh_thu', 'tong_nvl', 'tong_cong_ep', 'loi_nhuan']
    for col in cac_cot_tien:
        if col in df_hien_thi.columns:
            format_dict[col] = format_tien_an_toan

    st.dataframe(df_hien_thi.style.format(format_dict), use_container_width=True, hide_index=True)

    st.markdown("---")
    
    # Khung chứa 2 nút tải xuống
    col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 6])

    # Nút 1: Tải CSV 
    with col_btn1:
        csv = df_hien_thi.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="⬇️ Tải xuống dữ liệu (CSV)",
            data=csv,
            file_name=f"So_Ban_Hang_{date.today().strftime('%d_%m_%Y')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    # Nút 2: Tải PDF khổ A4 Ngang
    with col_btn2:
        def create_report_pdf(dataframe):
            pdf = FPDF(orientation='L', format='A4') # L: Landscape (Ngang)
            pdf.add_page()
            
            # Xử lý font an toàn
            if not (os.path.exists("arial.ttf") and os.path.exists("arialbd.ttf")):
                pdf.set_font("Helvetica", "B", 18)
                has_font = False
            else:
                pdf.add_font("Arial", "", "arial.ttf", uni=True)
                pdf.add_font("Arial", "B", "arialbd.ttf", uni=True)
                has_font = True
            
            f_name = "Arial" if has_font else "Helvetica"
            
            # Tiêu đề báo cáo
            pdf.set_font(f_name, "B", 18)
            pdf.cell(0, 10, "BÁO CÁO DỮ LIỆU BÁN HÀNG", align="C", ln=True)
            pdf.set_font(f_name, "", 11)
            pdf.cell(0, 6, f"Ngày trích xuất: {date.today().strftime('%d/%m/%Y')}", align="C", ln=True)
            pdf.ln(5)

            # Cài đặt độ rộng các cột (Tổng ~ 277mm)
            w_ngay, w_phieu, w_kh, w_sp, w_sl, w_gia, w_doanhthu, w_loinhuan = 22, 15, 45, 65, 20, 25, 30, 30

            # Hàm vẽ Header (Tiêu đề bảng)
            def draw_header():
                pdf.set_font(f_name, "B", 10)
                pdf.set_fill_color(220, 220, 220)
                pdf.cell(w_ngay, 10, "Ngày", border=1, align="C", fill=True)
                pdf.cell(w_phieu, 10, "Phiếu", border=1, align="C", fill=True)
                pdf.cell(w_kh, 10, "Khách Hàng", border=1, align="C", fill=True)
                pdf.cell(w_sp, 10, "Sản Phẩm", border=1, align="C", fill=True)
                pdf.cell(w_sl, 10, "SL", border=1, align="C", fill=True)
                pdf.cell(w_gia, 10, "Đơn Giá", border=1, align="C", fill=True)
                pdf.cell(w_doanhthu, 10, "Doanh Thu", border=1, align="C", fill=True)
                pdf.cell(w_loinhuan, 10, "Lợi Nhuận", border=1, align="C", fill=True, ln=True)

            draw_header()

            # Vẽ dữ liệu
            pdf.set_font(f_name, "", 9)
            tong_doanh_thu = 0
            tong_loi_nhuan = 0

            # Hàm an toàn lấy số để vẽ PDF
            def safe_num(val):
                try: return float(val)
                except: return 0.0

            for index, row in dataframe.iterrows():
                # Tự động sang trang mới và in lại Header nếu lố trang
                if pdf.get_y() > 180: 
                    pdf.add_page()
                    draw_header()
                    pdf.set_font(f_name, "", 9)

                ngay = str(row.get('ngay_tao', row.get('ngay', '')))[:10] # Lấy ngày từ ngay_tao hoặc ngay
                phieu = str(row.get('ma_don', row.get('so_phieu', '')))
                kh = str(row.get('ten_kh', ''))[:25]
                sp = str(row.get('ten_sp', ''))[:35]
                
                sl = safe_num(row.get('so_luong', 0))
                gia = safe_num(row.get('don_gia', 0))
                dt = safe_num(row.get('tong_tien', row.get('doanh_thu', 0))) # Hỗ trợ cả 2 tên cột
                ln = safe_num(row.get('loi_nhuan', 0))

                pdf.cell(w_ngay, 8, ngay, border=1, align="C")
                pdf.cell(w_phieu, 8, phieu, border=1, align="C")
                pdf.cell(w_kh, 8, kh, border=1)
                pdf.cell(w_sp, 8, sp, border=1)
                pdf.cell(w_sl, 8, f"{sl:,.0f}", border=1, align="C")
                pdf.cell(w_gia, 8, f"{gia:,.0f}", border=1, align="R")
                pdf.cell(w_doanhthu, 8, f"{dt:,.0f}", border=1, align="R")
                pdf.cell(w_loinhuan, 8, f"{ln:,.0f}", border=1, align="R", ln=True)
                
                tong_doanh_thu += dt
                tong_loi_nhuan += ln

            # Dòng Tổng Cộng Cuối Bảng
            pdf.set_font(f_name, "B", 10)
            pdf.cell(w_ngay + w_phieu + w_kh + w_sp + w_sl + w_gia, 10, "TỔNG CỘNG:", border=1, align="R")
            pdf.cell(w_doanhthu, 10, f"{tong_doanh_thu:,.0f}", border=1, align="R")
            pdf.cell(w_loinhuan, 10, f"{tong_loi_nhuan:,.0f}", border=1, align="R", ln=True)

            return bytes(pdf.output())

        # Tạo file PDF từ dữ liệu ĐANG ĐƯỢC LỌC trên màn hình
        pdf_bytes = create_report_pdf(df_hien_thi)
        
        if pdf_bytes:
            st.download_button(
                label="🖨️ Xuất báo cáo (PDF)",
                data=pdf_bytes,
                file_name=f"Bao_Cao_Ban_Hang_{date.today().strftime('%d_%m_%Y')}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
else:
    st.info("Chưa có dữ liệu bán hàng nào trong hệ thống.")
