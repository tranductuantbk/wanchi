import streamlit as st
import pandas as pd
from db_utils import get_connection
import os
from fpdf import FPDF
from datetime import date

st.set_page_config(page_title="Sổ Dữ Liệu Bán Hàng", page_icon="🗂️", layout="wide")
st.header("🗂️ Sổ Dữ Liệu Bán Hàng")

# Kết nối database thông qua cấu hình Neon
conn = get_connection()
df = pd.read_sql("SELECT * FROM don_hang ORDER BY id DESC", conn)

if not df.empty:
    col_loc1, col_loc2 = st.columns(2)
    with col_loc1:
        kh_filter = st.selectbox("🔍 Lọc theo Khách hàng", ["Tất cả"] + df['ten_kh'].unique().tolist())
    with col_loc2:
        sp_filter = st.selectbox("🔍 Lọc theo Sản phẩm", ["Tất cả"] + df['ten_sp'].unique().tolist())

    # Xử lý lọc dữ liệu
    df_hien_thi = df.copy()
    if kh_filter != "Tất cả":
        df_hien_thi = df_hien_thi[df_hien_thi['ten_kh'] == kh_filter]
    if sp_filter != "Tất cả":
        df_hien_thi = df_hien_thi[df_hien_thi['ten_sp'] == sp_filter]

    # Định dạng hiển thị trên web
    format_tien = {'so_luong': '{:,.0f}', 'don_gia': '{:,.0f}', 'doanh_thu': '{:,.0f}', 'tong_nvl': '{:,.0f}', 'tong_cong_ep': '{:,.0f}', 'loi_nhuan': '{:,.0f}'}
    st.dataframe(df_hien_thi.style.format(format_tien), use_container_width=True, hide_index=True)

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
            
            if not (os.path.exists("arial.ttf") and os.path.exists("arialbd.ttf")):
                st.error("🚨 Không tìm thấy font chữ arial!")
                return None
            
            # ĐÃ BỔ SUNG uni=True ĐỂ TRÁNH LỖI UNICODE TRÊN CLOUD
            pdf.add_font("Arial", "", "arial.ttf", uni=True)
            pdf.add_font("Arial", "B", "arialbd.ttf", uni=True)
            
            # Tiêu đề báo cáo
            pdf.set_font("Arial", "B", 18)
            pdf.cell(0, 10, "BÁO CÁO DỮ LIỆU BÁN HÀNG", align="C", ln=True)
            pdf.set_font("Arial", "", 11)
            pdf.cell(0, 6, f"Ngày trích xuất: {date.today().strftime('%d/%m/%Y')}", align="C", ln=True)
            pdf.ln(5)

            # Cài đặt độ rộng các cột (Tổng ~ 277mm)
            w_ngay = 22
            w_phieu = 15
            w_kh = 45
            w_sp = 65
            w_sl = 20
            w_gia = 25
            w_doanhthu = 30
            w_loinhuan = 30

            # Hàm vẽ Header (Tiêu đề bảng)
            def draw_header():
                pdf.set_font("Arial", "B", 10)
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
            pdf.set_font("Arial", "", 9)
            tong_doanh_thu = 0
            tong_loi_nhuan = 0

            for index, row in dataframe.iterrows():
                # Tự động sang trang mới và in lại Header nếu lố trang
                if pdf.get_y() > 180: 
                    pdf.add_page()
                    draw_header()
                    pdf.set_font("Arial", "", 9)

                pdf.cell(w_ngay, 8, row['ngay'], border=1, align="C")
                pdf.cell(w_phieu, 8, row['so_phieu'], border=1, align="C")
                pdf.cell(w_kh, 8, row['ten_kh'][:25], border=1) # Cắt tên dài
                pdf.cell(w_sp, 8, row['ten_sp'][:35], border=1)
                pdf.cell(w_sl, 8, f"{row['so_luong']:,.0f}", border=1, align="C")
                pdf.cell(w_gia, 8, f"{row['don_gia']:,.0f}", border=1, align="R")
                pdf.cell(w_doanhthu, 8, f"{row['doanh_thu']:,.0f}", border=1, align="R")
                pdf.cell(w_loinhuan, 8, f"{row['loi_nhuan']:,.0f}", border=1, align="R", ln=True)
                
                tong_doanh_thu += row['doanh_thu']
                tong_loi_nhuan += row['loi_nhuan']

            # Dòng Tổng Cộng Cuối Bảng
            pdf.set_font("Arial", "B", 10)
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