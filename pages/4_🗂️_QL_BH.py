import streamlit as st
import pandas as pd
from db_utils import get_connection, check_password
import os
import json
from fpdf import FPDF
from datetime import date

st.set_page_config(page_title="Sổ Dữ Liệu Bán Hàng", page_icon="🗂️", layout="wide")

# ==========================================
# Ổ KHÓA BẢO VỆ 2 LỚP
# ==========================================
role = check_password()
if not role:
    st.stop()

if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Sổ Dữ Liệu Bán Hàng là tuyệt mật, chỉ dành cho Quản lý WANCHI.")
    st.stop()
# ==========================================

st.header("🗂️ Sổ Dữ Liệu Bán Hàng (Chi Tiết)")

# Kết nối database
conn = get_connection()
try:
    df_raw = pd.read_sql("SELECT * FROM public.don_hang ORDER BY id DESC", conn)
except:
    df_raw = pd.DataFrame()

if not df_raw.empty:
    # ==========================================
    # CỖ MÁY "RÃ ĐÔNG" DỮ LIỆU JSON ĐỂ TẠO BÁO CÁO
    # ==========================================
    flat_data = []
    for _, row in df_raw.iterrows():
        try:
            if pd.notna(row['chi_tiet']) and str(row['chi_tiet']).strip() != "":
                items = json.loads(row['chi_tiet'])
                for item in items:
                    ten_sp = item.get('Tên Sản Phẩm', item.get('Tên Sản Phẩm OME', 'Không rõ'))
                    don_gia = item.get('Đơn Giá', item.get('Đơn Giá OME', 0))
                    so_luong = item.get('Số Lượng', 0)
                    thanh_tien = item.get('Thành Tiền', 0)
                    
                    flat_data.append({
                        "Ngày": str(row['ngay_tao'])[:10] if pd.notna(row['ngay_tao']) else "",
                        "Mã Đơn": str(row['ma_don']),
                        "Khách Hàng": str(row['ten_kh']),
                        "Loại Đơn": str(row['loai_don']),
                        "Sản Phẩm": str(ten_sp),
                        "Số Lượng": float(so_luong),
                        "Đơn Giá": float(don_gia),
                        "Doanh Thu": float(thanh_tien)
                    })
            else:
                flat_data.append({
                    "Ngày": str(row.get('ngay_tao', ''))[:10],
                    "Mã Đơn": str(row.get('ma_don', '')),
                    "Khách Hàng": str(row.get('ten_kh', '')),
                    "Loại Đơn": str(row.get('loai_don', '')),
                    "Sản Phẩm": "Đơn hàng tổng (Không rõ chi tiết)",
                    "Số Lượng": 1.0,
                    "Đơn Giá": float(row.get('tong_tien', 0)),
                    "Doanh Thu": float(row.get('tong_tien', 0))
                })
        except Exception as e:
            pass
    
    df = pd.DataFrame(flat_data)
    
    if df.empty:
        st.info("Chưa có dữ liệu bán hàng chi tiết.")
        st.stop()

    # Bộ lọc
    col_loc1, col_loc2 = st.columns(2)
    with col_loc1:
        kh_list = df['Khách Hàng'].dropna().unique().tolist()
        kh_filter = st.selectbox("🔍 Lọc theo Khách hàng", ["Tất cả"] + kh_list)
    with col_loc2:
        sp_list = df['Sản Phẩm'].dropna().unique().tolist()
        sp_filter = st.selectbox("🔍 Lọc theo Sản phẩm", ["Tất cả"] + sp_list)

    # Xử lý lọc dữ liệu
    df_hien_thi = df.copy()
    if kh_filter != "Tất cả":
        df_hien_thi = df_hien_thi[df_hien_thi['Khách Hàng'] == kh_filter]
    if sp_filter != "Tất cả":
        df_hien_thi = df_hien_thi[df_hien_thi['Sản Phẩm'] == sp_filter]

    # Định dạng hiển thị đẹp trên Web
    def format_tien_an_toan(val):
        try: return "{:,.0f}".format(float(val))
        except: return val

    format_dict = {'Số Lượng': format_tien_an_toan, 'Đơn Giá': format_tien_an_toan, 'Doanh Thu': format_tien_an_toan}
    st.dataframe(df_hien_thi.style.format(format_dict), use_container_width=True, hide_index=True)

    st.markdown("---")
    
    # Khung chứa nút tải xuống
    col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 6])

    with col_btn1:
        csv = df_hien_thi.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="⬇️ Tải xuống (CSV)",
            data=csv,
            file_name=f"So_Ban_Hang_{date.today().strftime('%d_%m_%Y')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col_btn2:
        def create_report_pdf(dataframe):
            pdf = FPDF(orientation='L', format='A4') # L: Landscape
            pdf.add_page()
            
            if not (os.path.exists("arial.ttf") and os.path.exists("arialbd.ttf")):
                pdf.set_font("Helvetica", "B", 18)
                f_name = "Helvetica"
            else:
                pdf.add_font("Arial", "", "arial.ttf", uni=True)
                pdf.add_font("Arial", "B", "arialbd.ttf", uni=True)
                f_name = "Arial"
            
            pdf.set_font(f_name, "B", 18)
            pdf.cell(0, 10, "BÁO CÁO DỮ LIỆU BÁN HÀNG CHI TIẾT", align="C", ln=True)
            pdf.set_font(f_name, "", 11)
            pdf.cell(0, 6, f"Ngày trích xuất: {date.today().strftime('%d/%m/%Y')}", align="C", ln=True)
            pdf.ln(5)

            w_ngay, w_phieu, w_kh, w_sp, w_sl, w_gia, w_doanhthu = 25, 25, 50, 80, 20, 35, 35

            def draw_header():
                pdf.set_font(f_name, "B", 10)
                pdf.set_fill_color(220, 220, 220)
                pdf.cell(w_ngay, 10, "Ngày", border=1, align="C", fill=True)
                pdf.cell(w_phieu, 10, "Mã Đơn", border=1, align="C", fill=True)
                pdf.cell(w_kh, 10, "Khách Hàng", border=1, align="C", fill=True)
                pdf.cell(w_sp, 10, "Sản Phẩm", border=1, align="C", fill=True)
                pdf.cell(w_sl, 10, "SL", border=1, align="C", fill=True)
                pdf.cell(w_gia, 10, "Đơn Giá", border=1, align="C", fill=True)
                pdf.cell(w_doanhthu, 10, "Doanh Thu", border=1, align="C", fill=True, ln=True)

            draw_header()

            pdf.set_font(f_name, "", 9)
            tong_doanh_thu = 0

            def safe_num(val):
                try: return float(val)
                except: return 0.0

            for index, row in dataframe.iterrows():
                if pdf.get_y() > 180: 
                    pdf.add_page()
                    draw_header()
                    pdf.set_font(f_name, "", 9)

                ngay = str(row['Ngày'])[:10]
                phieu = str(row['Mã Đơn'])
                kh = str(row['Khách Hàng'])[:25]
                sp = str(row['Sản Phẩm'])[:40]
                sl = safe_num(row['Số Lượng'])
                gia = safe_num(row['Đơn Giá'])
                dt = safe_num(row['Doanh Thu'])

                pdf.cell(w_ngay, 8, ngay, border=1, align="C")
                pdf.cell(w_phieu, 8, phieu, border=1, align="C")
                pdf.cell(w_kh, 8, kh, border=1)
                pdf.cell(w_sp, 8, sp, border=1)
                pdf.cell(w_sl, 8, f"{sl:,.0f}", border=1, align="C")
                pdf.cell(w_gia, 8, f"{gia:,.0f}", border=1, align="R")
                pdf.cell(w_doanhthu, 8, f"{dt:,.0f}", border=1, align="R", ln=True)
                
                tong_doanh_thu += dt

            pdf.set_font(f_name, "B", 10)
            pdf.cell(w_ngay + w_phieu + w_kh + w_sp + w_sl + w_gia, 10, "TỔNG CỘNG:", border=1, align="R")
            pdf.cell(w_doanhthu, 10, f"{tong_doanh_thu:,.0f}", border=1, align="R", ln=True)

            # ==========================================
            # BỘ LỌC XUẤT BẢN PDF THÔNG MINH (CHỐNG LỖI ĐỜI FPDF MỚI)
            # ==========================================
            try:
                # Cách 1: Cho FPDF2 (Phiên bản mới nhất trên Streamlit Cloud)
                return bytes(pdf.output())
            except Exception:
                # Cách 2: Cho FPDF bản cũ
                out = pdf.output(dest='S')
                return out.encode('latin-1') if isinstance(out, str) else bytes(out)

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
