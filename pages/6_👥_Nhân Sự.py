import streamlit as st
import pandas as pd
from datetime import date, datetime
from fpdf import FPDF
import os
import time
from db_utils import get_connection

st.set_page_config(page_title="Hệ Thống Nhân Sự & Lương", page_icon="👥", layout="wide")
st.header("👥 Quản Lý Nhân Sự & Lương WANCHI")
conn = get_connection()
c = conn.cursor()

# --- CỖ MÁY TỰ ĐỘNG KHỞI TẠO & CẬP NHẬT DATABASE (POSTGRESQL) ---
# 1. Tạo bảng gốc nếu chưa có trên Đám mây
c.execute('''CREATE TABLE IF NOT EXISTS nhan_vien (
                id SERIAL PRIMARY KEY,
                ten_nv TEXT UNIQUE,
                bo_phan TEXT,
                luong_cb REAL DEFAULT 0,
                tham_nien REAL DEFAULT 0,
                tien_com REAL DEFAULT 0,
                tc_ngay_thuong_gia REAL DEFAULT 0,
                tc_chu_nhat_gia REAL DEFAULT 0
            )''')

# 2. Tự động thêm các cột mới nếu Database thiếu
try: c.execute("ALTER TABLE nhan_vien ADD COLUMN ngay_vao_lam TEXT")
except: pass
try: c.execute("ALTER TABLE nhan_vien ADD COLUMN luong_nang_luc REAL DEFAULT 0")
except: pass
try: c.execute("ALTER TABLE nhan_vien ADD COLUMN phu_cap_khac REAL DEFAULT 0")
except: pass
# ---------------------------------------------------

tab1, tab2 = st.tabs(["📁 Hồ Sơ Nhân Sự Gốc", "💸 Tính Lương & Xuất Phiếu"])

# ==========================================
# TAB 1: QUẢN LÝ HỒ SƠ NHÂN SỰ
# ==========================================
with tab1:
    st.subheader("1. Thêm Nhân Viên Mới")
    with st.form("form_them_nv"):
        col_n1, col_n2, col_n3 = st.columns(3)
        with col_n1:
            ten_nv = st.text_input("Tên nhân viên (VD: THÁI TRINH)")
            bo_phan = st.text_input("Bộ phận (VD: Quản lý)")
            ngay_vao = st.date_input("Ngày vào làm chính thức", date.today())
        with col_n2:
            luong_cb = st.number_input("Lương cơ bản (VNĐ/ngày)", min_value=0, value=0, step=10000)
            luong_nl = st.number_input("Lương năng lực (VNĐ/ngày)", min_value=0, value=0, step=10000)
            t_nien_fixed = st.number_input("Tiền thâm niên (VNĐ/ngày)", min_value=0, value=0, step=5000)
        with col_n3:
            t_com_fixed = st.number_input("Tiền cơm (VNĐ/ngày)", min_value=0, value=0, step=5000)
            tc_thuong = st.number_input("Giá TC ngày thường (VNĐ/giờ)", min_value=0, value=0, step=1000)
            tc_cn = st.number_input("Giá TC Chủ Nhật (VNĐ/ngày)", min_value=0, value=0, step=10000)
            phu_cap_khac = st.number_input("Phụ cấp cố định (VNĐ)", min_value=0, value=0, step=10000)

        submit_nv = st.form_submit_button("💾 Lưu Hồ Sơ", type="primary")
        if submit_nv and ten_nv:
            try:
                # ĐÃ ĐỔI DẤU ? THÀNH %s (10 DẤU)
                c.execute("""INSERT INTO nhan_vien 
                             (ten_nv, bo_phan, ngay_vao_lam, luong_cb, luong_nang_luc, tham_nien, tien_com, tc_ngay_thuong_gia, tc_chu_nhat_gia, phu_cap_khac) 
                             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
                          (ten_nv, bo_phan, ngay_vao.strftime("%Y-%m-%d"), luong_cb, luong_nl, t_nien_fixed, t_com_fixed, tc_thuong, tc_cn, phu_cap_khac))
                
                st.success(f"✅ Đã lưu hồ sơ nhân sự {ten_nv}!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi thêm mới: Tên nhân viên này có thể đã tồn tại.")

    st.markdown("---")
    st.subheader("2. Danh Sách Nhân Sự Gốc")
    df_nv = pd.read_sql("SELECT * FROM nhan_vien", conn)
    if not df_nv.empty:
        edited_nv = st.data_editor(
            df_nv,
            column_config={
                "id": None,
                "ten_nv": st.column_config.TextColumn("Tên NV", disabled=True),
                "ngay_vao_lam": st.column_config.TextColumn("Ngày Vào Làm"),
                "bo_phan": st.column_config.TextColumn("Bộ phận"),
                "luong_cb": st.column_config.NumberColumn("Lương CB", format="%d"),
                "luong_nang_luc": st.column_config.NumberColumn("Lương Năng Lực", format="%d"),
                "tham_nien": st.column_config.NumberColumn("Thâm niên", format="%d"),
                "tien_com": st.column_config.NumberColumn("Tiền cơm", format="%d"),
                "tc_ngay_thuong_gia": st.column_config.NumberColumn("Giá TC Ngày", format="%d"),
                "tc_chu_nhat_gia": st.column_config.NumberColumn("Giá TC CN", format="%d"),
                "phu_cap_khac": st.column_config.NumberColumn("Phụ cấp", format="%d"),
            },
            use_container_width=True, hide_index=True
        )

        if st.button("Lưu Thay Đổi Bảng Nhân Sự"):
            for index, row in edited_nv.iterrows():
                # Xử lý an toàn nếu dữ liệu cũ bị trống (NULL)
                ng_vao = row['ngay_vao_lam'] if pd.notna(row.get('ngay_vao_lam')) else ""
                l_nl_val = row['luong_nang_luc'] if pd.notna(row.get('luong_nang_luc')) else 0
                pc_khac = row['phu_cap_khac'] if pd.notna(row.get('phu_cap_khac')) else 0
                
                # ĐÃ ĐỔI DẤU ? THÀNH %s VÀ ÉP KIỂU id
                c.execute("""UPDATE nhan_vien 
                             SET bo_phan=%s, ngay_vao_lam=%s, luong_cb=%s, luong_nang_luc=%s, tham_nien=%s, tien_com=%s, tc_ngay_thuong_gia=%s, tc_chu_nhat_gia=%s, phu_cap_khac=%s 
                             WHERE id=%s""",
                          (row['bo_phan'], ng_vao, row['luong_cb'], l_nl_val, row['tham_nien'], row['tien_com'], row['tc_ngay_thuong_gia'], row['tc_chu_nhat_gia'], pc_khac, int(row['id'])))
            
            st.success("Đã cập nhật thay đổi nhân sự!")
            time.sleep(1)
            st.rerun()
    else:
        st.info("Chưa có nhân sự nào. Hãy tạo mới ở biểu mẫu trên.")

# ==========================================
# TAB 2: TÍNH LƯƠNG & XUẤT PDF
# ==========================================
with tab2:
    if df_nv.empty:
        st.warning("⚠️ Vui lòng khai báo nhân sự ở Tab 1 trước!")
    else:
        st.subheader("BƯỚC 1: Chọn Nhân Viên")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            chon_nv = st.selectbox("Chọn nhân viên:", df_nv['ten_nv'].tolist())
            nv_data = df_nv[df_nv['ten_nv'] == chon_nv].iloc[0]
        with col_s2:
            ky_luong_str = st.text_input("Kỳ lương (MM/YYYY)", value=date.today().strftime("%m/%Y"))
            
        # --- XỬ LÝ LỖI NGÀY THÁNG AN TOÀN ---
        ngay_vao_str = nv_data.get('ngay_vao_lam')
        if pd.isna(ngay_vao_str) or not ngay_vao_str:
            ngay_vao_str = date.today().strftime("%Y-%m-%d") # Mặc định lấy ngày hôm nay nếu hồ sơ cũ bị trống

        try:
            d_vao = datetime.strptime(ngay_vao_str, "%Y-%m-%d")
            d_ky_luong = datetime.strptime(ky_luong_str, "%m/%Y")
            
            so_thang_tn = (d_ky_luong.year - d_vao.year) * 12 + (d_ky_luong.month - d_vao.month)
            if so_thang_tn < 0: so_thang_tn = 0
            
            so_nam_tn = round(so_thang_tn / 12, 1)
            hien_thi_nam = f"{int(so_nam_tn)}" if so_nam_tn.is_integer() else f"{so_nam_tn}"
        except:
            hien_thi_nam = "0"
            d_vao = date.today()

        st.info(f"📅 Ngày vào làm: **{d_vao.strftime('%d/%m/%Y')}** | Thâm niên hiện tại: **{hien_thi_nam} năm**")

        st.markdown("---")
        st.subheader("BƯỚC 2: Nhập Biến Số & Tính Toán")
        
        # Hàm ép kiểu an toàn chống lỗi NaN
        def s_int(val): return int(val) if pd.notna(val) else 0

        col_l1, col_l2, col_l3 = st.columns(3)
        with col_l1:
            st.caption("CÁC KHOẢN CỐ ĐỊNH")
            l_cb = st.number_input("Lương cơ bản", value=s_int(nv_data.get('luong_cb', 0)), step=10000)
            l_nl = st.number_input("Lương năng lực", value=s_int(nv_data.get('luong_nang_luc', 0)), step=10000)
            t_nien = st.number_input("Tiền thâm niên", value=s_int(nv_data.get('tham_nien', 0)), step=5000)
            t_com = st.number_input("Tiền cơm", value=s_int(nv_data.get('tien_com', 0)), step=5000)
            p_cap = st.number_input("Phụ cấp cố định", value=s_int(nv_data.get('phu_cap_khac', 0)), step=10000)

        with col_l2:
            st.caption("NHẬP BIẾN SỐ THÁNG NÀY")
            ngay_cong = st.number_input("Ngày công thực tế", min_value=0.0, value=26.0, step=0.5)
            tc_thuong_gio = st.number_input("Giờ TC ngày thường", min_value=0.0, value=0.0, step=0.5)
            tc_cn_ngay = st.number_input("Ngày TC Chủ Nhật", min_value=0.0, value=0.0, step=0.5)

        with col_l3:
            st.caption("THƯỞNG & KHẤU TRỪ")
            thuong = st.number_input("Thưởng thêm", min_value=0, value=0, step=100000)
            tam_ung = st.number_input("Tạm ứng đợt 1", min_value=0, value=0, step=100000)
            khau_tru = st.number_input("Khấu trừ / Phạt", min_value=0, value=0, step=50000)
            ghi_chu = st.text_area("Ghi chú", value="")

        # Tính toán
        tien_cb = l_cb * ngay_cong
        tien_nl = l_nl * ngay_cong
        tien_tn = t_nien * ngay_cong
        tien_com_th = t_com * ngay_cong
        tien_tc_t = float(nv_data.get('tc_ngay_thuong_gia', 0) or 0) * tc_thuong_gio
        tien_tc_c = float(nv_data.get('tc_chu_nhat_gia', 0) or 0) * tc_cn_ngay
        
        gross = tien_cb + tien_nl + tien_tn + tien_com_th + tien_tc_t + tien_tc_c + p_cap + thuong
        tong_kt = tam_ung + khau_tru
        thuc_lanh = gross - tong_kt

        st.markdown(f"### 💰 THỰC LÃNH: **{thuc_lanh:,.0f} VNĐ**")

        # --- XUẤT PDF ---
        def create_payslip_pdf():
            pdf = FPDF(orientation='L', format='A5')
            pdf.add_page()
            if not (os.path.exists("arial.ttf") and os.path.exists("arialbd.ttf")):
                st.error("🚨 Thiếu font arial!")
                return None
                
            # ĐÃ BỔ SUNG uni=True ĐỂ TRÁNH LỖI UNICODE TRÊN CLOUD
            pdf.add_font("Arial", "", "arial.ttf", uni=True)
            pdf.add_font("Arial", "B", "arialbd.ttf", uni=True)

            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, "PHIẾU LƯƠNG NHÂN VIÊN", align="C", ln=True)
            pdf.ln(2)

            pdf.set_font("Arial", "B", 10)
            pdf.cell(25, 6, "Nhân viên:")
            pdf.set_font("Arial", "", 10)
            pdf.cell(65, 6, chon_nv)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(35, 6, "Vào làm chính thức:")
            pdf.set_font("Arial", "", 10)
            pdf.cell(0, 6, d_vao.strftime('%d/%m/%Y'), ln=True)

            pdf.set_font("Arial", "B", 10)
            pdf.cell(25, 6, "Bộ phận:")
            pdf.set_font("Arial", "", 10)
            pdf.cell(65, 6, nv_data.get('bo_phan', ''))
            pdf.set_font("Arial", "B", 10)
            pdf.cell(35, 6, "Thâm niên hiện tại:")
            pdf.set_font("Arial", "B", 10)
            pdf.cell(0, 6, f"{hien_thi_nam} năm", ln=True)
            
            pdf.ln(4)

            w = [10, 65, 25, 35, 55]
            pdf.set_fill_color(220, 220, 220)
            pdf.cell(w[0], 8, "STT", 1, 0, 'C', True)
            pdf.cell(w[1], 8, "KHOẢN MỤC", 1, 0, 'C', True)
            pdf.cell(w[2], 8, "SỐ LƯỢNG", 1, 0, 'C', True)
            pdf.cell(w[3], 8, "ĐƠN GIÁ", 1, 0, 'C', True)
            pdf.cell(w[4], 8, "THÀNH TIỀN", 1, 1, 'C', True)

            def f(n): return f"{n:,.0f}".replace(",", ".")
            def r(s, n, sl, dg, tt):
                pdf.set_font("Arial", "", 10)
                pdf.cell(w[0], 7, s, 1, 0, 'C')
                pdf.cell(w[1], 7, " " + n, 1, 0, 'L')
                pdf.cell(w[2], 7, sl, 1, 0, 'C')
                pdf.cell(w[3], 7, dg, 1, 0, 'R')
                pdf.cell(w[4], 7, tt, 1, 1, 'R')

            def s(n, tt, bold=False):
                pdf.set_font("Arial", "B" if bold else "", 10)
                pdf.cell(sum(w[:4]), 8, n, 1, 0, 'R')
                pdf.cell(w[4], 8, tt, 1, 1, 'R')

            # I. Thu Nhập
            pdf.set_font("Arial", "B", 10)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(sum(w), 8, "  I. THU NHẬP", 1, 1, 'L', True)

            r("1", "Lương cơ bản", f"{ngay_cong}".replace('.', ','), f(l_cb), f(tien_cb))
            r("2", "Lương năng lực", f"{ngay_cong}".replace('.', ','), f(l_nl), f(tien_nl))
            r("3", "Tiền thâm niên", f"{ngay_cong}".replace('.', ','), f(t_nien), f(tien_tn))
            r("4", "Tiền cơm", f"{ngay_cong}".replace('.', ','), f(t_com), f(tien_com_th))
            r("5", "Tăng ca ngày thường", f"{tc_thuong_gio}".replace('.', ','), f(nv_data.get('tc_ngay_thuong_gia',0)), f(tien_tc_t))
            r("6", "Tăng ca chủ nhật", f"{tc_cn_ngay}".replace('.', ','), f(nv_data.get('tc_chu_nhat_gia',0)), f(tien_tc_c))
            r("7", "Phụ cấp cố định", "", "", f(p_cap))
            r("8", "Thưởng thêm", "", "", f(thuong))
            s("Tổng thu nhập (Gross): ", f(gross) + "  ", True)
            
            # II. Khấu trừ
            pdf.set_font("Arial", "B", 10)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(sum(w), 8, "  II. KHẤU TRỪ", 1, 1, 'L', True)
            
            r("9", "Tạm ứng đợt 1", "", "", f(tam_ung))
            r("10", "Khấu trừ / Phạt", "", "", f(khau_tru))
            s("Tổng khấu trừ: ", f(tong_kt) + "  ", True)

            # III. Thực lãnh
            pdf.set_font("Arial", "B", 10)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(sum(w), 8, "  III. THỰC LÃNH", 1, 1, 'L', True)
            
            pdf.set_font("Arial", "B", 11)
            pdf.cell(sum(w[:4]), 10, "THỰC LÃNH (I - II): ", 1, 0, 'R')
            pdf.cell(w[4], 10, f(thuc_lanh) + " đ  ", 1, 1, 'R')

            # Chữ ký
            if ghi_chu:
                pdf.ln(2)
                pdf.set_font("Arial", "B", 10)
                pdf.cell(20, 6, "Nhận xét:")
                pdf.set_font("Arial", "", 10)
                pdf.multi_cell(0, 6, ghi_chu)
                pdf.ln(1)
            else:
                pdf.ln(4)

            pdf.set_font("Arial", "B", 10)
            pdf.cell(63, 6, "Người Lập Phiếu", 0, 0, 'C')
            pdf.cell(63, 6, "Giám Đốc", 0, 0, 'C')
            pdf.cell(64, 6, "Người Nhận", 0, 1, 'C')

            return bytes(pdf.output())

        st.subheader("BƯỚC 3: Tải Phiếu Lương")
        pdf_data = create_payslip_pdf()
        if pdf_data:
            st.download_button(f"🖨️ Tải PDF Phiếu Lương - {chon_nv}", pdf_data, f"Phieu_Luong_{chon_nv}.pdf", "application/pdf")