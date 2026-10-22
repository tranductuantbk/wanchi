import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import json
import os
import urllib.request
from fpdf import FPDF
from db_utils import get_connection, check_password

# ==========================================
# CẤU HÌNH MÚI GIỜ & FONT PDF
# ==========================================
VN_TZ = timezone(timedelta(hours=7))
def lay_gio_vn():
    return datetime.now(VN_TZ)

FONT_FILE = "Roboto-Regular.ttf"
FONT_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"

@st.cache_resource
def download_font():
    if not os.path.exists(FONT_FILE):
        try: urllib.request.urlretrieve(FONT_URL, FONT_FILE)
        except: pass
download_font()

# ==========================================
# KHỞI TẠO THƯ VIỆN CHUYỂN PDF SANG ẢNH
# ==========================================
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

def convert_pdf_to_png(pdf_bytes):
    """Hàm phụ trợ chuyển byte PDF thành byte Ảnh PNG độ nét cao"""
    if not HAS_FITZ:
        st.error("⚠️ Hệ thống thiếu thư viện 'PyMuPDF' để xuất ảnh. Vui lòng chạy lệnh: pip install PyMuPDF")
        return None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(0) 
        pix = page.get_pixmap(dpi=200) 
        return pix.tobytes("png")
    except Exception as e:
        st.error(f"Lỗi khi chuyển đổi ảnh: {e}")
        return None

st.set_page_config(page_title="Quản Lý Kho WANCHI", page_icon="📦", layout="wide")

role = check_password()
if not role: st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang Quản Lý Kho chỉ dành cho Quản lý WANCHI.")
    st.stop()

st.header("📦 Quản Lý Kho, Công Nợ")

conn = get_connection()
c = conn.cursor()

# ==========================================
# KHỞI TẠO BẢNG DỮ LIỆU
# ==========================================
try:
    c.execute("CREATE SCHEMA IF NOT EXISTS public;")
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_nguyen_lieu (
                    id SERIAL PRIMARY KEY, ma_nl TEXT UNIQUE, ten_nl TEXT UNIQUE, don_vi TEXT, ton_kho REAL DEFAULT 0
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS public.ls_nhap_xuat_kho (
                    id SERIAL PRIMARY KEY, ngay_thao_tac TEXT, loai_thao_tac TEXT, ten_nl TEXT, 
                    so_luong REAL, don_gia REAL DEFAULT 0, thanh_tien REAL DEFAULT 0, ghi_chu TEXT
                )''')
    c.execute("ALTER TABLE public.dm_san_pham ADD COLUMN IF NOT EXISTS ton_kho REAL DEFAULT 0")
    c.execute("ALTER TABLE public.dm_san_pham_ome ADD COLUMN IF NOT EXISTS ton_kho REAL DEFAULT 0")
    c.execute("ALTER TABLE public.don_hang ADD COLUMN IF NOT EXISTS trang_thai TEXT DEFAULT 'Chờ xuất kho'")
    
    # BẢNG VÀ CỘT MỚI CHO NHÀ CUNG CẤP & THANH TOÁN
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_ncc (
                    id SERIAL PRIMARY KEY, ten_ncc TEXT UNIQUE
                )''')
    c.execute("ALTER TABLE public.ls_nhap_xuat_kho ADD COLUMN IF NOT EXISTS nha_cung_cap TEXT")
    c.execute("ALTER TABLE public.ls_nhap_xuat_kho ADD COLUMN IF NOT EXISTS khach_hang TEXT")
    c.execute("ALTER TABLE public.ls_nhap_xuat_kho ADD COLUMN IF NOT EXISTS trang_thai_tt TEXT")
    
    # BẢNG MỚI ĐỂ LƯU LỊCH SỬ PHIẾU CHI
    c.execute('''CREATE TABLE IF NOT EXISTS public.ls_phieu_chi (
                    id SERIAL PRIMARY KEY, ma_phieu TEXT, ngay_chi TEXT, ten_ncc TEXT, tong_chi REAL, chi_tiet TEXT
                )''')
    conn.commit()
except: 
    conn.rollback()

def format_vn(value):
    try: return "{:,.0f}".format(value).replace(",", ".")
    except: return str(value)

def don_dep_lich_su_chi():
    """Hàm tự động dọn dẹp, chỉ giữ lại 50 phiếu chi gần nhất"""
    try:
        c.execute("""DELETE FROM public.ls_phieu_chi 
                     WHERE id NOT IN (
                         SELECT id FROM public.ls_phieu_chi 
                         ORDER BY id DESC LIMIT 50
                     )""")
        conn.commit()
    except: 
        conn.rollback()

# ==========================================
# HÀM TẠO PHIẾU XUẤT KHO / PHIẾU CHI PDF
# ==========================================
def generate_phieu_xuat_pdf(df_items, ma_don, ten_kh):
    pdf = FPDF()
    pdf.add_page()
    
    has_font = os.path.exists(FONT_FILE)
    if has_font:
        pdf.add_font("Roboto", "", FONT_FILE, uni=True)
        font_name = "Roboto"
    else: font_name = "Helvetica"

    pdf.set_font(font_name, "", 16)
    pdf.cell(0, 10, "PHIẾU XUẤT KHO HÀNG HÓA", ln=True, align="C")
    pdf.set_font(font_name, "", 10)
    pdf.cell(0, 6, f"Mã đơn: {ma_don}", ln=True, align="C")
    pdf.cell(0, 6, f"Khách hàng: {ten_kh}", ln=True, align="C")
    pdf.cell(0, 6, f"Ngày xuất: {lay_gio_vn().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
    pdf.ln(10)

    pdf.set_fill_color(230, 230, 230)
    pdf.cell(10, 10, "STT", 1, 0, "C", True)
    pdf.cell(110, 10, "Tên Sản Phẩm", 1, 0, "C", True)
    pdf.cell(35, 10, "Số Lượng", 1, 0, "C", True)
    pdf.cell(35, 10, "Đơn Vị", 1, 1, "C", True)

    for i, row in df_items.iterrows():
        ten = str(row.get('Tên Sản Phẩm', row.get('Tên Sản Phẩm OME', 'N/A')))
        sl = row.get('Số Lượng', 0)
        pdf.cell(10, 8, str(i+1), 1, 0, "C")
        pdf.cell(110, 8, ten, 1, 0, "L")
        pdf.cell(35, 8, format_vn(sl), 1, 0, "C")
        pdf.cell(35, 8, "Cái/Bộ", 1, 1, "C")
    
    pdf.ln(10)
    pdf.cell(95, 6, "Người lập phiếu", 0, 0, "C")
    pdf.cell(95, 6, "Người nhận hàng", 0, 1, "C")
    
    try: return bytes(pdf.output())
    except:
        out = pdf.output(dest='S')
        return out.encode('latin-1') if isinstance(out, str) else bytes(out)

def generate_phieu_chi_pdf(ten_ncc, ma_phieu, tong_chi, ngay_chi, df_selected=None):
    pdf = FPDF()
    pdf.add_page()
    has_font = os.path.exists(FONT_FILE)
    if has_font:
        pdf.add_font("Roboto", "", FONT_FILE, uni=True)
        pdf.add_font("Roboto", "B", FONT_FILE, uni=True) 
        font_name = "Roboto"
    else: font_name = "Helvetica"

    start_y, start_x = 12, 65  
    try:
        if os.path.exists("logo.jpg"): pdf.image("logo.jpg", x=15, y=start_y, w=40)
        elif os.path.exists("logo.png"): pdf.image("logo.png", x=15, y=start_y, w=40)
        else:
            pdf.set_font(font_name, 'B', 18)
            pdf.set_xy(15, start_y + 3); pdf.cell(40, 10, "WANCHI", align="C")
    except:
        pdf.set_font(font_name, 'B', 18)
        pdf.set_xy(15, start_y + 3); pdf.cell(40, 10, "WANCHI", align="C")
    
    pdf.set_font(font_name, size=10)
    pdf.set_xy(start_x, start_y + 2)
    pdf.multi_cell(0, 5, "775 Võ Hữu Lợi, Xã Lê Minh Xuân, Huyện Bình Chánh, TP.HCM")
    pdf.set_xy(start_x, pdf.get_y() + 1)
    pdf.cell(0, 5, "SĐT: 0902.580.828 - 0937.572.577", ln=True)
    pdf.ln(12)

    pdf.set_font(font_name, 'B' if has_font else '', 16)
    pdf.cell(0, 10, "PHIẾU CHI TIỀN (THANH TOÁN CÔNG NỢ NCC)", ln=True, align="C")
    
    pdf.set_font(font_name, "", 11)
    pdf.cell(0, 6, f"Ngày lập: {ngay_chi}", ln=True, align="C")
    pdf.cell(0, 6, f"Mã Phiếu Thanh Toán: {ma_phieu}", ln=True, align="C")
    pdf.ln(5)
    
    pdf.cell(0, 8, f"Người nhận tiền (Nhà cung cấp): {ten_ncc}", ln=True)
    pdf.cell(0, 8, f"Lý do chi: Thanh toán công nợ tiền vật tư / nguyên liệu nhập kho.", ln=True)
    pdf.ln(3)
    
    if df_selected is not None and not df_selected.empty:
        pdf.set_font(font_name, 'B' if has_font else '', 10)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(15, 10, "STT", border=1, align="C", fill=True)
        pdf.cell(35, 10, "Ngày Nhập", border=1, align="C", fill=True)
        pdf.cell(90, 10, "Thông tin SP (Vật tư)", border=1, align="C", fill=True)
        pdf.cell(50, 10, "Thành Tiền", border=1, ln=True, align="C", fill=True)

        pdf.set_font(font_name, "", 10)
        stt = 1
        for _, row in df_selected.iterrows():
            ngay = str(row.get("Ngày Nhập", ""))
            ten_vt = str(row.get("Tên Vật Tư", ""))
            sl = row.get("Số Lượng", 0)
            sp_info = f"{ten_vt} (SL: {format_vn(sl)})"
            thanh_tien = row.get("Thành Tiền", 0)
            
            pdf.cell(15, 8, str(stt), border=1, align="C")
            pdf.cell(35, 8, ngay, border=1, align="C")
            pdf.cell(90, 8, sp_info, border=1, align="L")
            pdf.cell(50, 8, format_vn(thanh_tien), border=1, ln=True, align="R")
            stt += 1
            
        pdf.set_font(font_name, 'B' if has_font else '', 11)
        pdf.cell(140, 10, "TỔNG CỘNG:", border=1, align="R")
        pdf.cell(50, 10, format_vn(tong_chi) + " VNĐ", border=1, ln=True, align="R")
    else:
        pdf.set_font(font_name, 'B' if has_font else '', 12)
        pdf.cell(0, 10, f"Số tiền thanh toán: {format_vn(tong_chi)} VNĐ", ln=True)

    pdf.ln(10)
    
    pdf.set_font(font_name, "", 11)
    pdf.cell(95, 6, "Người Lập Phiếu", align='C')
    pdf.cell(95, 6, "Người Nhận Tiền", ln=True, align='C')
    pdf.cell(95, 6, "(Ký, ghi rõ họ tên)", align='C')
    pdf.cell(95, 6, "(Ký, ghi rõ họ tên)", align='C')
    
    try: return bytes(pdf.output())
    except:
        out = pdf.output(dest='S')
        return out.encode('latin-1') if isinstance(out, str) else bytes(out)

# ==========================================
# GIAO DIỆN CHÍNH
# ==========================================
tab1, tab2, tab_kh, tab3, tab4 = st.tabs(["📋 NVL, NCC, Công Nợ", "📥 Nhập / Xuất Kho", "👤 Khách Hàng Công Nợ", "📊 Báo Cáo Tồn Kho", "🕰️ Lịch Sử Công Nợ"])

with tab1:
    st.subheader("🏢 Quản Lý Nhà Cung Cấp & Theo Dõi Công Nợ")
    with st.form("form_them_ncc", clear_on_submit=True):
        c_ncc1, c_ncc2 = st.columns([3, 1])
        with c_ncc1: 
            ten_ncc = st.text_input("Tên Nhà Cung Cấp Mới (*)")
        with c_ncc2:
            st.write("") 
            btn_ncc = st.form_submit_button("💾 Lưu NCC", type="primary", use_container_width=True)
        if btn_ncc:
            if ten_ncc.strip():
                try:
                    c.execute("INSERT INTO public.dm_ncc (ten_ncc) VALUES (%s)", (ten_ncc.strip(),))
                    conn.commit()
                    st.success("✅ Đã thêm Nhà Cung Cấp thành công!")
                    time.sleep(1); st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error("⚠️ Lỗi: Tên Nhà Cung Cấp này đã tồn tại!")
            else:
                st.warning("Vui lòng nhập tên Nhà Cung Cấp!")

    st.markdown("**🔍 Theo dõi Hóa đơn & Công Nợ NCC**")
    try:
        df_ncc = pd.read_sql("SELECT ten_ncc FROM public.dm_ncc ORDER BY id DESC", conn)
        danh_sach_ncc = df_ncc['ten_ncc'].tolist() if not df_ncc.empty else []
        
        col_cn1, col_cn2 = st.columns([1, 2])
        with col_cn1:
            ncc_chon_cong_no = st.selectbox("Lọc công nợ theo Nhà Cung Cấp:", ["-- Chọn NCC --"] + danh_sach_ncc)
        
        if ncc_chon_cong_no != "-- Chọn NCC --":
            df_no = pd.read_sql(f"SELECT id, ngay_thao_tac, ten_nl, so_luong, don_gia, thanh_tien, ghi_chu FROM public.ls_nhap_xuat_kho WHERE nha_cung_cap='{ncc_chon_cong_no}' AND trang_thai_tt='Chưa thanh toán' AND loai_thao_tac='Nhập NVL'", conn)
            
            if not df_no.empty:
                tong_no = df_no['thanh_tien'].sum()
                st.warning(f"🚨 **CẢNH BÁO:** Bạn đang nợ {ncc_chon_cong_no} tổng cộng **{format_vn(tong_no)} VNĐ**.")
                
                df_no.insert(0, "Chọn Thanh Toán", False)
                df_hien_thi_no = df_no.copy()
                df_hien_thi_no.columns = ["Chọn Thanh Toán", "Mã Giao Dịch (ID)", "Ngày Nhập", "Tên Vật Tư", "Số Lượng", "Đơn Giá", "Thành Tiền", "Ghi Chú"]
                
                st.write("Tích chọn vào các khoản nợ bên dưới mà bạn muốn thanh toán đợt này:")
                edited_no = st.data_editor(
                    df_hien_thi_no, 
                    hide_index=True, 
                    use_container_width=True,
                    column_config={
                        "Chọn Thanh Toán": st.column_config.CheckboxColumn("Thanh Toán", default=False),
                        "Mã Giao Dịch (ID)": st.column_config.NumberColumn(disabled=True),
                        "Ngày Nhập": st.column_config.TextColumn(disabled=True),
                        "Tên Vật Tư": st.column_config.TextColumn(disabled=True),
                        "Số Lượng": st.column_config.NumberColumn(disabled=True),
                        "Đơn Giá": st.column_config.NumberColumn(disabled=True),
                        "Thành Tiền": st.column_config.NumberColumn(disabled=True),
                        "Ghi Chú": st.column_config.TextColumn(disabled=True)
                    },
                    key=f"editor_no_{ncc_chon_cong_no}"
                )
                
                selected_rows = edited_no[edited_no["Chọn Thanh Toán"] == True]
                tong_chi_chon = selected_rows["Thành Tiền"].sum()
                
                st.info(f"💵 Đang chọn thanh toán: **{format_vn(tong_chi_chon)} VNĐ** / Tổng nợ: **{format_vn(tong_no)} VNĐ**")
                
                st.markdown("**📁 Tùy chọn in phiếu chi:**")
                loai_xuat_chi = st.radio(
                    "Định dạng xuất Phiếu Chi:", 
                    ["Chỉ xuất file PDF", "Chỉ xuất file Ảnh (PNG)", "Xuất cả PDF và Ảnh"], 
                    horizontal=True, 
                    key="radio_xuat_chi",
                    index=1
                )
                
                c_tt1, c_tt2 = st.columns([1, 2])
                with c_tt1:
                    if st.button("💸 XÁC NHẬN THANH TOÁN MỤC ĐÃ CHỌN", type="primary", use_container_width=True):
                        ids_to_pay = selected_rows["Mã Giao Dịch (ID)"].tolist()
                        if not ids_to_pay:
                            st.error("⚠️ Vui lòng tích chọn ít nhất 1 khoản nợ từ bảng trên để thanh toán!")
                        else:
                            ids_tuple = tuple(ids_to_pay)
                            if len(ids_to_pay) == 1:
                                c.execute("UPDATE public.ls_nhap_xuat_kho SET trang_thai_tt='Đã thanh toán' WHERE id = %s", (ids_to_pay[0],))
                            else:
                                c.execute(f"UPDATE public.ls_nhap_xuat_kho SET trang_thai_tt='Đã thanh toán' WHERE id IN {ids_tuple}")
                            
                            ngay_chi_hien_tai = lay_gio_vn().strftime("%d/%m/%Y %H:%M")
                            ma_phieu_chi = f"PC_{int(time.time())}"
                            chi_tiet_json = selected_rows.to_json(orient='records')
                            
                            c.execute("""INSERT INTO public.ls_phieu_chi (ma_phieu, ngay_chi, ten_ncc, tong_chi, chi_tiet) 
                                         VALUES (%s, %s, %s, %s, %s)""", 
                                      (ma_phieu_chi, ngay_chi_hien_tai, ncc_chon_cong_no, float(tong_chi_chon), chi_tiet_json))
                            conn.commit()
                            don_dep_lich_su_chi()
                            
                            st.session_state['pdf_phieu_chi'] = generate_phieu_chi_pdf(ncc_chon_cong_no, ma_phieu_chi, tong_chi_chon, ngay_chi_hien_tai, selected_rows)
                            st.session_state['ten_file_chi'] = f"PhieuChi_{ncc_chon_cong_no}.pdf"
                            
                            img_chi = convert_pdf_to_png(st.session_state['pdf_phieu_chi'])
                            if img_chi:
                                st.session_state['img_phieu_chi'] = img_chi
                                
                            st.success(f"✅ Đã thanh toán công nợ thành công. Hệ thống đã gạch nợ.")
                
                if 'pdf_phieu_chi' in st.session_state:
                    st.markdown("---")
                    dl_c1, dl_c2 = st.columns(2)
                    if "PDF" in loai_xuat_chi or "Cả" in loai_xuat_chi:
                        with dl_c1:
                            st.download_button("🖨️ TẢI PHIẾU CHI (PDF)", data=st.session_state['pdf_phieu_chi'], file_name=st.session_state['ten_file_chi'], mime="application/pdf", type="primary", use_container_width=True)
                    if ("Ảnh" in loai_xuat_chi or "Cả" in loai_xuat_chi) and st.session_state.get('img_phieu_chi'):
                        with dl_c2:
                            st.download_button("🖼️ TẢI PHIẾU CHI (ẢNH)", data=st.session_state['img_phieu_chi'], file_name=st.session_state['ten_file_chi'].replace('.pdf','.png'), mime="image/png", type="primary", use_container_width=True)
            else:
                st.success(f"✅ Tuyệt vời! Hiện tại bạn không nợ công ty {ncc_chon_cong_no} đồng nào.")
    except Exception as e: pass

    st.markdown("---")
    st.subheader("➕ Thêm Nguyên Vật Liệu Mới")
    with st.form("form_them_nl", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1: ma_nl = st.text_input("Mã Vật Tư")
        with c2: ten_nl = st.text_input("Tên Vật Tư (*)")
        with c3: don_vi = st.selectbox("Đơn vị", ["Kg", "Gram", "Cái", "Thùng", "Cuộn", "Mét", "Lít", "Bộ"])
        if st.form_submit_button("💾 Lưu NVL Mới"):
            if ten_nl:
                try:
                    c.execute("INSERT INTO public.dm_nguyen_lieu (ma_nl, ten_nl, don_vi) VALUES (%s, %s, %s)", (ma_nl or f"VT{int(time.time())}", ten_nl.strip(), don_vi))
                    conn.commit(); st.success("✅ Đã thêm!"); time.sleep(1); st.rerun()
                except: st.error("⚠️ Lỗi: Trùng tên hoặc mã vật tư!")
            else: st.warning("Vui lòng nhập Tên Vật Tư!")

    st.markdown("---")
    st.subheader("📄 Danh Sách Nguyên Vật Liệu")
    try:
        df_nl = pd.read_sql("SELECT id, ma_nl, ten_nl, don_vi FROM public.dm_nguyen_lieu ORDER BY id DESC", conn)
        if not df_nl.empty:
            df_nl = df_nl.fillna({"ma_nl": "", "ten_nl": "", "don_vi": ""})
            edited_nl = st.data_editor(
                df_nl,
                column_config={
                    "id": None,
                    "ma_nl": st.column_config.TextColumn("Mã NVL"),
                    "ten_nl": st.column_config.TextColumn("Tên Nguyên Vật Liệu"),
                    "don_vi": st.column_config.TextColumn("Đơn Vị"),
                },
                hide_index=True, use_container_width=True, key="editor_nl"
            )

            diff_mask = (edited_nl['ma_nl'] != df_nl['ma_nl']) | (edited_nl['ten_nl'] != df_nl['ten_nl']) | (edited_nl['don_vi'] != df_nl['don_vi'])

            if diff_mask.any():
                st.warning("⚠️ CHÚ Ý: Bạn vừa chỉnh sửa thông tin vật tư trên bảng. Bạn có muốn lưu lại những thay đổi này không?")
                col_luu1, col_luu2 = st.columns(2)
                with col_luu1:
                    if st.button("💾 ĐỒNG Ý LƯU THAY ĐỔI", type="primary", use_container_width=True):
                        changed_rows = edited_nl[diff_mask]
                        try:
                            count = 0
                            for _, row in changed_rows.iterrows():
                                c.execute("UPDATE public.dm_nguyen_lieu SET ma_nl=%s, ten_nl=%s, don_vi=%s WHERE id=%s",
                                          (str(row['ma_nl']).strip(), str(row['ten_nl']).strip(), str(row['don_vi']).strip(), int(row['id'])))
                                count += 1
                            conn.commit()
                            st.success(f"✅ Đã cập nhật thành công {count} vật tư!"); time.sleep(1.5); st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Lỗi cập nhật: {e}")
                with col_luu2:
                    if st.button("❌ HỦY BỎ", use_container_width=True): st.rerun()
            
            st.markdown("---")
            col_xoa1, col_xoa2 = st.columns([3, 1])
            with col_xoa1: nl_can_xoa = st.selectbox("Chọn NVL cần xóa:", ["-- Chọn --"] + df_nl['ten_nl'].tolist())
            with col_xoa2:
                st.write(""); st.write("")
                if st.button("🚨 Xóa Vĩnh Viễn", type="primary", use_container_width=True):
                    if nl_can_xoa != "-- Chọn --":
                        try:
                            c.execute("DELETE FROM public.dm_nguyen_lieu WHERE ten_nl=%s", (nl_can_xoa,))
                            conn.commit(); st.success(f"✅ Đã xóa: {nl_can_xoa}"); time.sleep(1); st.rerun()
                        except Exception as e:
                            conn.rollback(); st.error(f"Lỗi: {e}")
        else: st.info("Kho NVL đang trống.")
    except Exception as e: st.error(f"Lỗi truy xuất dữ liệu: {e}")

with tab2:
    chuyem_muc = st.radio("Chọn nghiệp vụ Kho:", ["📥 1. Nhập NVL, NCC", "📦 2. Nhập Thành Phẩm", "🚚 3. Xuất Kho (Theo Đơn Hàng)"], horizontal=True)
    st.markdown("---")

    if "3. Xuất Kho" in chuyem_muc:
        st.markdown("#### 🚚 Quản Lý Xuất Kho & Thu Hồi Đơn")
        try:
            df_dh = pd.read_sql("SELECT id, ma_don, ten_kh, ngay_tao, trang_thai, chi_tiet FROM public.don_hang ORDER BY id DESC", conn)
            if not df_dh.empty:
                df_dh['trang_thai'] = df_dh['trang_thai'].fillna('Chờ xuất kho')
                options = [f"[{row['trang_thai']}] {row['ma_don']} - {row['ten_kh']}" for _, row in df_dh.iterrows()]
                
                don_chon_str = st.selectbox("📌 Chọn Số Phiếu Đơn Hàng", options)
                ma_don_chon = don_chon_str.split("] ")[1].split(" - ")[0]
                don_info = df_dh[df_dh['ma_don'] == ma_don_chon].iloc[0]
                
                # Logic xác định trạng thái thanh toán mặc định dựa trên Khách hàng
                ten_khach_hang_hien_tai = don_info['ten_kh']
                la_dai_ly = "đại lý" in ten_khach_hang_hien_tai.lower()
                trang_thai_tt_xuat = st.selectbox(
                    "Trạng thái thanh toán Đơn hàng", 
                    ["Chưa thanh toán", "Đã thanh toán"], 
                    index=0 if la_dai_ly else 1
                )
                
                items = json.loads(don_info['chi_tiet'])
                df_items = pd.DataFrame(items)
                st.dataframe(df_items, use_container_width=True, hide_index=True)
                
                c_btn1, c_btn2 = st.columns([2, 2])
                
                if don_info['trang_thai'] in ['Chờ xuất kho', 'Mới tạo']:
                    with c_btn1:
                        if st.button("📦 XÁC NHẬN XUẤT KHO", type="primary", use_container_width=True):
                            for item in items:
                                ten_sp = item.get('Tên Sản Phẩm', item.get('Tên Sản Phẩm OME'))
                                sl = float(item.get('Số Lượng', 0))
                                don_gia_sp = float(item.get('Đơn Giá', item.get('Giá', 0))) # Lấy giá nếu có
                                thanh_tien_sp = sl * don_gia_sp
                                
                                c.execute("UPDATE public.dm_san_pham SET ton_kho = ton_kho - %s WHERE ten_sp = %s", (sl, ten_sp))
                                c.execute("UPDATE public.dm_san_pham_ome SET ton_kho = ton_kho - %s WHERE ten_sp = %s", (sl, ten_sp))
                                
                                # Ghi nhận xuất kho kèm Khách hàng và Trạng thái thanh toán
                                c.execute("""INSERT INTO public.ls_nhap_xuat_kho 
                                             (ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, don_gia, thanh_tien, ghi_chu, khach_hang, trang_thai_tt) 
                                             VALUES (%s, 'Xuất Bán', %s, %s, %s, %s, %s, %s, %s)""", 
                                          (lay_gio_vn().strftime("%d/%m/%Y %H:%M"), ten_sp, -sl, don_gia_sp, thanh_tien_sp, f"Đơn {ma_don_chon}", ten_khach_hang_hien_tai, trang_thai_tt_xuat))
                                
                            c.execute("UPDATE public.don_hang SET trang_thai = 'Đã xuất kho' WHERE ma_don = %s", (ma_don_chon,))
                            conn.commit(); st.success("Đã xuất kho và lưu công nợ!"); time.sleep(1.5); st.rerun()
                    
                    with c_btn2:
                        if st.button("❌ HỦY ĐƠN NÀY", use_container_width=True):
                            c.execute("UPDATE public.don_hang SET trang_thai = 'Đã hủy' WHERE ma_don = %s", (ma_don_chon,))
                            conn.commit(); st.warning("Đã hủy đơn."); time.sleep(1); st.rerun()

                elif don_info['trang_thai'] == 'Đã xuất kho':
                    with c_btn1:
                        pdf_bytes = generate_phieu_xuat_pdf(df_items, ma_don_chon, don_info['ten_kh'])
                        st.download_button("🖨️ IN PHIẾU XUẤT (PDF)", pdf_bytes, f"PhieuXuat_{ma_don_chon}.pdf", "application/pdf", use_container_width=True)
                    
                    with c_btn2:
                        if st.button("🔄 THU HỒI ĐƠN (Trả hàng)", use_container_width=True):
                            for item in items:
                                ten_sp = item.get('Tên Sản Phẩm', item.get('Tên Sản Phẩm OME'))
                                sl = float(item.get('Số Lượng', 0))
                                c.execute("UPDATE public.dm_san_pham SET ton_kho = ton_kho + %s WHERE ten_sp = %s", (sl, ten_sp))
                                c.execute("UPDATE public.dm_san_pham_ome SET ton_kho = ton_kho + %s WHERE ten_sp = %s", (sl, ten_sp))
                                c.execute("INSERT INTO public.ls_nhap_xuat_kho (ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, ghi_chu) VALUES (%s, 'Thu hồi đơn', %s, %s, %s)", (lay_gio_vn().strftime("%d/%m/%Y %H:%M"), ten_sp, sl, f"Thu hồi đơn {ma_don_chon}"))
                            c.execute("UPDATE public.don_hang SET trang_thai = 'Đã thu hồi' WHERE ma_don = %s", (ma_don_chon,))
                            conn.commit(); st.info("Đã thu hồi hàng về kho."); time.sleep(1.5); st.rerun()
                else:
                    st.info(f"Đơn hàng này đang ở trạng thái: **{don_info['trang_thai']}**")

            else: st.info("Chưa có đơn hàng nào.")
        except Exception as e: st.error(str(e))
    
    elif "1. Nhập NVL, NCC" in chuyem_muc:
        st.markdown("#### 📥 Nhập Nguyên Vật Liệu từ Nhà Cung Cấp")
        try:
            df_nl_ton = pd.read_sql("SELECT ten_nl, don_vi FROM public.dm_nguyen_lieu", conn)
            try: df_ncc = pd.read_sql("SELECT ten_ncc FROM public.dm_ncc", conn)
            except: df_ncc = pd.DataFrame()
            danh_sach_ncc = df_ncc['ten_ncc'].tolist() if not df_ncc.empty else ["-- Chưa có Nhà Cung Cấp --"]

            if not df_nl_ton.empty:
                with st.form("form_nhap_nvl"):
                    col_n1, col_n2 = st.columns(2)
                    with col_n1:
                        ngay_nhap_hd = st.date_input("Ngày nhập hàng", lay_gio_vn().date(), format="DD/MM/YYYY")
                        nl_chon = st.selectbox("Chọn Vật Tư cần nhập", df_nl_ton['ten_nl'].tolist())
                        sl_tt = st.number_input("Số lượng nhập", min_value=1.0, step=1.0)
                    with col_n2:
                        ncc_chon = st.selectbox("Chọn Nhà Cung Cấp", danh_sach_ncc)
                        don_gia = st.number_input("Đơn giá nhập (VNĐ)", min_value=0.0, step=1000.0)
                        trang_thai_tt = st.selectbox("Trạng thái thanh toán", ["Chưa thanh toán", "Đã thanh toán"])
                    
                    ghi_chu = st.text_input("Ghi chú thêm (Số xe, người giao...)")

                    if st.form_submit_button("💾 Xác nhận Nhập NVL", type="primary"):
                        if ncc_chon.startswith("--"):
                            st.error("⚠️ Vui lòng thêm tên Nhà Cung Cấp ở Tab 1 trước khi nhập hàng!")
                        else:
                            thanh_tien = sl_tt * don_gia
                            ngay_tt = ngay_nhap_hd.strftime("%d/%m/%Y")
                            
                            c.execute("""INSERT INTO public.ls_nhap_xuat_kho 
                                         (ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, don_gia, thanh_tien, ghi_chu, nha_cung_cap, trang_thai_tt) 
                                         VALUES (%s, 'Nhập NVL', %s, %s, %s, %s, %s, %s, %s)""", 
                                      (ngay_tt, nl_chon, sl_tt, don_gia, thanh_tien, ghi_chu, ncc_chon, trang_thai_tt))
                            conn.commit()
                            st.success(f"✅ Đã ghi nhận lô hàng từ {ncc_chon} vào Lịch sử & Công nợ!")
                            time.sleep(2); st.rerun()
            else: st.warning("⚠️ Kho chưa có Danh mục Vật tư nào.")
        except Exception as e: st.error(str(e))

    elif "2. Nhập Thành Phẩm" in chuyem_muc:
        st.markdown("#### 📦 Nhập Thành Phẩm Vừa Sản Xuất")
        try:
            df_sp_chuan = pd.read_sql("SELECT ten_sp, ton_kho, 'chuẩn' as loai FROM public.dm_san_pham", conn)
            df_sp_ome = pd.read_sql("SELECT ten_sp, ton_kho, 'ome' as loai FROM public.dm_san_pham_ome", conn)
            df_all_sp = pd.concat([df_sp_chuan, df_sp_ome]).dropna(subset=['ten_sp']).reset_index(drop=True)
            
            if not df_all_sp.empty:
                with st.form("form_nhap_sp"):
                    sp_chon = st.selectbox("Chọn Thành Phẩm đã làm xong", df_all_sp['ten_sp'].unique().tolist())
                    
                    col_sl1, col_sl2 = st.columns([2, 1])
                    with col_sl1:
                        sl_nhap = st.number_input("Số lượng thành phẩm nhập kho", min_value=1.0, step=1.0)
                    with col_sl2:
                        don_vi_nhap = st.selectbox("Đơn vị", ["bộ", "lẻ", "kg"], index=0)

                    if st.form_submit_button("🔄 Lưu Thành Phẩm", type="primary"):
                        sp_info = df_all_sp[df_all_sp['ten_sp'] == sp_chon].iloc[0]
                        loai_sp = sp_info['loai']
                        ngay_tt = lay_gio_vn().strftime("%d/%m/%Y %H:%M")

                        bang_update = "public.dm_san_pham" if loai_sp == 'chuẩn' else "public.dm_san_pham_ome"
                        c.execute(f"UPDATE {bang_update} SET ton_kho = ton_kho + %s WHERE ten_sp = %s", (sl_nhap, sp_chon))
                        
                        ghi_chu_sp = f"Sản xuất hoàn thành ({don_vi_nhap})"
                        c.execute("""INSERT INTO public.ls_nhap_xuat_kho (ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, ghi_chu) 
                                     VALUES (%s, 'Nhập Thành Phẩm', %s, %s, %s)""", (ngay_tt, sp_chon, sl_nhap, ghi_chu_sp))
                        
                        conn.commit()
                        st.success(f"✅ Đã nhập {sl_nhap} {don_vi_nhap} {sp_chon} vào kho!")
                        time.sleep(2); st.rerun()
            else: st.info("Chưa có danh mục sản phẩm.")
        except Exception as e: st.error(str(e))

# ------------------------------------------
# TAB KHÁCH HÀNG CÔNG NỢ
# ------------------------------------------
with tab_kh:
    st.subheader("👤 Theo Dõi Công Nợ Khách Hàng / Đại Lý")
    try:
        df_kh_no = pd.read_sql("SELECT id, ngay_thao_tac, khach_hang, ten_nl, so_luong, don_gia, thanh_tien, ghi_chu FROM public.ls_nhap_xuat_kho WHERE loai_thao_tac='Xuất Bán' AND trang_thai_tt='Chưa thanh toán' ORDER BY khach_hang", conn)
        if not df_kh_no.empty:
            danh_sach_kh = df_kh_no['khach_hang'].unique().tolist()
            kh_chon = st.selectbox("🔍 Chọn Khách Hàng / Đại Lý để xem công nợ:", ["-- Tất cả --"] + danh_sach_kh)
            
            if kh_chon != "-- Tất cả --":
                df_hien_thi_kh = df_kh_no[df_kh_no['khach_hang'] == kh_chon].copy()
            else:
                df_hien_thi_kh = df_kh_no.copy()
            
            tong_tien_no_kh = df_hien_thi_kh['thanh_tien'].sum()
            st.warning(f"🚨 Tổng số tiền đang nợ: **{format_vn(tong_tien_no_kh)} VNĐ**")
            
            df_hien_thi_kh.insert(0, "Đã Thu Tiền", False)
            df_hien_thi_kh.columns = ["Đã Thu Tiền", "ID Giao Dịch", "Ngày Xuất", "Khách Hàng", "Sản Phẩm", "SL (Xuất)", "Đơn Giá", "Thành Tiền", "Ghi Chú"]
            
            st.write("Tích chọn vào các đơn hàng đã được thanh toán để gạch nợ:")
            edited_kh_no = st.data_editor(
                df_hien_thi_kh,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Đã Thu Tiền": st.column_config.CheckboxColumn("Xác Nhận Thu", default=False),
                    "ID Giao Dịch": st.column_config.NumberColumn(disabled=True),
                    "Ngày Xuất": st.column_config.TextColumn(disabled=True),
                    "Khách Hàng": st.column_config.TextColumn(disabled=True),
                    "Sản Phẩm": st.column_config.TextColumn(disabled=True),
                    "SL (Xuất)": st.column_config.NumberColumn(disabled=True),
                    "Đơn Giá": st.column_config.NumberColumn(disabled=True),
                    "Thành Tiền": st.column_config.NumberColumn(disabled=True),
                    "Ghi Chú": st.column_config.TextColumn(disabled=True)
                },
                key="editor_kh_no"
            )
            
            selected_kh_rows = edited_kh_no[edited_kh_no["Đã Thu Tiền"] == True]
            if st.button("💰 XÁC NHẬN ĐÃ THU TIỀN CÁC MỤC ĐÃ CHỌN", type="primary", use_container_width=True):
                ids_to_update = selected_kh_rows["ID Giao Dịch"].tolist()
                if not ids_to_update:
                    st.error("⚠️ Vui lòng tích chọn ít nhất 1 dòng từ bảng trên!")
                else:
                    if len(ids_to_update) == 1:
                        c.execute("UPDATE public.ls_nhap_xuat_kho SET trang_thai_tt='Đã thanh toán' WHERE id = %s", (ids_to_update[0],))
                    else:
                        c.execute(f"UPDATE public.ls_nhap_xuat_kho SET trang_thai_tt='Đã thanh toán' WHERE id IN {tuple(ids_to_update)}")
                    conn.commit()
                    st.success("✅ Đã cập nhật trạng thái thu tiền thành công!")
                    time.sleep(1.5); st.rerun()
        else:
            st.success("✅ Tuyệt vời! Hiện tại không có Khách hàng hoặc Đại lý nào nợ tiền.")
    except Exception as e: st.error(f"Lỗi: {e}")

with tab3:
    st.info("💡 **Mẹo:** Bạn có thể chỉnh sửa trực tiếp số liệu ở cột **Tồn Kho (Sửa được)**. Sau khi sửa, hãy bấm nút Lưu xuất hiện bên dưới bảng để cập nhật.")
    
    st.subheader("📦 Tồn Kho Thành Phẩm")
    try:
        df_tc = pd.read_sql("SELECT id, ten_sp, ton_kho, 'chuẩn' as loai FROM public.dm_san_pham", conn)
        df_to = pd.read_sql("SELECT id, ten_sp, ton_kho, 'ome' as loai FROM public.dm_san_pham_ome", conn)
        df_tp = pd.concat([df_tc, df_to]).dropna(subset=['id']).reset_index(drop=True)
        df_tp['ton_kho'] = df_tp['ton_kho'].fillna(0.0) 
        
        edited_tp = st.data_editor(
            df_tp,
            column_config={
                "id": None,
                "loai": None,
                "ten_sp": st.column_config.TextColumn("Tên Sản Phẩm", disabled=True),
                "ton_kho": st.column_config.NumberColumn("Tồn Kho (Sửa được)")
            },
            hide_index=True, use_container_width=True, key="edit_ton_sp"
        )
        
        diff_tp = (edited_tp['ton_kho'] != df_tp['ton_kho'])
        if diff_tp.any():
            if st.button("💾 LƯU TỒN KHO THÀNH PHẨM", type="primary", use_container_width=True):
                changed_tp = edited_tp[diff_tp]
                for _, row in changed_tp.iterrows():
                    bang_update = "public.dm_san_pham" if row['loai'] == 'chuẩn' else "public.dm_san_pham_ome"
                    c.execute(f"UPDATE {bang_update} SET ton_kho=%s WHERE id=%s", (float(row['ton_kho']), int(row['id'])))
                conn.commit()
                st.success("✅ Đã cập nhật tồn kho Thành phẩm!"); time.sleep(1); st.rerun()
    except Exception as e:
        st.error(f"Lỗi truy xuất tồn kho: {e}")

with tab4:
    st.subheader("🕰️ Lịch sử Thanh toán Công nợ (50 phiếu gần nhất)")
    try:
        df_ls_chi = pd.read_sql("SELECT ma_phieu, ngay_chi, ten_ncc, tong_chi, chi_tiet FROM public.ls_phieu_chi ORDER BY id DESC LIMIT 50", conn)
        if not df_ls_chi.empty:
            df_hien_thi = df_ls_chi.drop(columns=['chi_tiet'])
            df_hien_thi.columns = ["Mã Phiếu", "Ngày Chi", "Tên Nhà Cung Cấp", "Tổng Chi (VNĐ)"]
            st.dataframe(df_hien_thi, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader("🖨️ Xuất lại Phiếu Công Nợ / Phiếu Chi")
            options_chi = ["-- Chọn phiếu chi --"] + df_ls_chi['ma_phieu'].tolist()
            chon_phieu = st.selectbox("🔍 Chọn Mã Phiếu để xuất lại:", options_chi)
            
            if chon_phieu != "-- Chọn phiếu chi --":
                row_data = df_ls_chi[df_ls_chi['ma_phieu'] == chon_phieu].iloc[0]
                df_chi_tiet = pd.DataFrame(json.loads(row_data['chi_tiet']))
                
                st.write(f"**Chi tiết các khoản thanh toán của mã {chon_phieu}:**")
                st.dataframe(df_chi_tiet.drop(columns=["Chọn Thanh Toán"], errors="ignore"), use_container_width=True, hide_index=True)
                
                loai_xuat_ls = st.radio(
                    "Định dạng xuất Phiếu Chi (Xuất lại):", 
                    ["Chỉ xuất PDF", "Chỉ xuất Ảnh (PNG)", "Cả PDF và Ảnh"], 
                    horizontal=True, 
                    key=f"radio_ls_{chon_phieu}", 
                    index=1
                )
                
                pdf_re = generate_phieu_chi_pdf(row_data['ten_ncc'], chon_phieu, float(row_data['tong_chi']), row_data['ngay_chi'], df_chi_tiet)
                pdf_name_re = f"PhieuChi_{row_data['ten_ncc']}_{chon_phieu}.pdf"
                
                col_ls1, col_ls2 = st.columns(2)
                if "PDF" in loai_xuat_ls or "Cả" in loai_xuat_ls:
                    with col_ls1:
                        st.download_button("📥 XUẤT LẠI FILE PDF", data=pdf_re, file_name=pdf_name_re, mime="application/pdf", type="primary", use_container_width=True)
                if "Ảnh" in loai_xuat_ls or "Cả" in loai_xuat_ls:
                    img_re = convert_pdf_to_png(pdf_re)
                    if img_re:
                        with col_ls2:
                            st.download_button("🖼️ XUẤT LẠI FILE ẢNH", data=img_re, file_name=pdf_name_re.replace('.pdf','.png'), mime="image/png", type="primary", use_container_width=True)
        else:
            st.info("Hệ thống chưa ghi nhận lịch sử thanh toán công nợ nào.")
    except Exception as e:
        st.error(f"Lỗi: {e}")
