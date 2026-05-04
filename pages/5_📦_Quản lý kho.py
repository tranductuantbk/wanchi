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

st.set_page_config(page_title="Quản Lý Kho WANCHI", page_icon="📦", layout="wide")

role = check_password()
if not role: st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang Quản Lý Kho chỉ dành cho Quản lý WANCHI.")
    st.stop()

st.header("📦 Quản Lý Kho (Thông Minh & Chống Thất Thoát)")

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
    conn.commit()
except: pass

def format_vn(value):
    try: return "{:,.0f}".format(value).replace(",", ".")
    except: return str(value)

# ==========================================
# HÀM TẠO PHIẾU XUẤT KHO PDF
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

# ==========================================
# GIAO DIỆN CHÍNH
# ==========================================
tab1, tab2, tab3 = st.tabs(["📋 Danh Mục NVL", "📥 Nhập / Xuất Kho (Thông Minh)", "📊 Báo Cáo Tồn Kho"])

with tab1:
    st.subheader("➕ Thêm Nguyên Vật Liệu Mới")
    with st.form("form_them_nl", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1: ma_nl = st.text_input("Mã Vật Tư")
        with c2: ten_nl = st.text_input("Tên Vật Tư (*)")
        with c3: don_vi = st.selectbox("Đơn vị", ["Kg", "Gram", "Cái", "Thùng", "Cuộn", "Mét", "Lít", "Bộ"])
        if st.form_submit_button("💾 Lưu NVL Mới"):
            if ten_nl:
                try:
                    c.execute("INSERT INTO public.dm_nguyen_lieu (ma_nl, ten_nl, don_vi, ton_kho) VALUES (%s, %s, %s, 0)", (ma_nl or f"VT{int(time.time())}", ten_nl.strip(), don_vi))
                    conn.commit(); st.success("✅ Đã thêm!"); time.sleep(1); st.rerun()
                except: st.error("⚠️ Lỗi: Trùng tên hoặc mã vật tư!")
            else: st.warning("Vui lòng nhập Tên Vật Tư!")

    st.markdown("---")
    st.subheader("📄 Danh Sách Nguyên Vật Liệu")
    st.info("💡 **Mẹo:** Nhấp đúp chuột vào các cột **Mã NVL**, **Tên Nguyên Vật Liệu**, **Đơn Vị** để sửa trực tiếp. (Cột Tồn Kho hệ thống tự tính).")
    st.warning("⚠️ **Lưu ý quan trọng:** Nếu bạn ĐỔI TÊN hoặc XÓA một vật tư đã được thiết lập trong 'Định mức cấu tạo' (ở trang Sản phẩm), bạn phải sang đó cập nhật lại công thức để kho trừ đúng tên nhé!")

    try:
        df_nl = pd.read_sql("SELECT id, ma_nl, ten_nl, don_vi, ton_kho FROM public.dm_nguyen_lieu ORDER BY id DESC", conn)
        if not df_nl.empty:
            edited_nl = st.data_editor(
                df_nl,
                column_config={
                    "id": None,
                    "ma_nl": st.column_config.TextColumn("Mã NVL"),
                    "ten_nl": st.column_config.TextColumn("Tên Nguyên Vật Liệu"),
                    "don_vi": st.column_config.TextColumn("Đơn Vị"),
                    "ton_kho": st.column_config.NumberColumn("Tồn Kho Hiện Tại", disabled=True),
                },
                hide_index=True, use_container_width=True, key="editor_nl"
            )

            diff_mask = (edited_nl['ma_nl'] != df_nl['ma_nl']) | \
                        (edited_nl['ten_nl'] != df_nl['ten_nl']) | \
                        (edited_nl['don_vi'] != df_nl['don_vi'])

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
                            st.success(f"✅ Đã cập nhật thành công {count} vật tư!")
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Lỗi cập nhật (có thể trùng tên NVL): {e}")
                with col_luu2:
                    if st.button("❌ HỦY BỎ", use_container_width=True):
                        st.rerun()

            st.markdown("---")
            st.subheader("🗑️ Xóa Nguyên Vật Liệu")
            col_xoa1, col_xoa2 = st.columns([3, 1])
            with col_xoa1: nl_can_xoa = st.selectbox("Chọn NVL cần xóa:", ["-- Chọn --"] + df_nl['ten_nl'].tolist())
            with col_xoa2:
                st.write(""); st.write("")
                if st.button("🚨 Xóa Vĩnh Viễn", type="primary", use_container_width=True):
                    if nl_can_xoa != "-- Chọn --":
                        try:
                            c.execute("DELETE FROM public.dm_nguyen_lieu WHERE ten_nl=%s", (nl_can_xoa,))
                            conn.commit()
                            st.success(f"✅ Đã xóa: {nl_can_xoa}")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Lỗi: {e}")

        else:
            st.info("Kho NVL đang trống.")
    except Exception as e:
        st.error(f"Lỗi truy xuất dữ liệu: {e}")

with tab2:
    chuyem_muc = st.radio("Chọn nghiệp vụ Kho:", ["📥 1. Nhập NVL", "📦 2. Nhập Thành Phẩm", "🚚 3. Xuất Kho (Theo Đơn Hàng)"], horizontal=True)
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
                
                items = json.loads(don_info['chi_tiet'])
                df_items = pd.DataFrame(items)
                st.dataframe(df_items, use_container_width=True, hide_index=True)
                
                c_btn1, c_btn2, c_btn3 = st.columns([2, 2, 2])
                
                if don_info['trang_thai'] in ['Chờ xuất kho', 'Mới tạo']:
                    with c_btn1:
                        if st.button("📦 XÁC NHẬN XUẤT KHO", type="primary", use_container_width=True):
                            for item in items:
                                ten_sp = item.get('Tên Sản Phẩm', item.get('Tên Sản Phẩm OME'))
                                sl = float(item.get('Số Lượng', 0))
                                c.execute("UPDATE public.dm_san_pham SET ton_kho = ton_kho - %s WHERE ten_sp = %s", (sl, ten_sp))
                                c.execute("UPDATE public.dm_san_pham_ome SET ton_kho = ton_kho - %s WHERE ten_sp = %s", (sl, ten_sp))
                                c.execute("INSERT INTO public.ls_nhap_xuat_kho (ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, ghi_chu) VALUES (%s, 'Xuất Bán', %s, %s, %s)", (lay_gio_vn().strftime("%d/%m/%Y %H:%M"), ten_sp, -sl, f"Đơn {ma_don_chon}"))
                            c.execute("UPDATE public.don_hang SET trang_thai = 'Đã xuất kho' WHERE ma_don = %s", (ma_don_chon,))
                            conn.commit(); st.success("Đã xuất kho!"); time.sleep(1.5); st.rerun()
                    
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
    
    elif "1. Nhập NVL" in chuyem_muc:
        st.markdown("#### 📥 Nhập Cấu Kiện / Nguyên Vật Liệu")
        try:
            df_nl_ton = pd.read_sql("SELECT ten_nl, don_vi, ton_kho FROM public.dm_nguyen_lieu", conn)
            if not df_nl_ton.empty:
                with st.form("form_nhap_nvl"):
                    nl_chon = st.selectbox("Chọn Vật Tư", df_nl_ton['ten_nl'].tolist())
                    sl_tt = st.number_input("Số lượng nhập", min_value=1.0, step=1.0)
                    ghi_chu = st.text_input("Ghi chú (Nhà cung cấp / Điều chỉnh)")

                    if st.form_submit_button("💾 Xác nhận Nhập NVL", type="primary"):
                        ngay_tt = lay_gio_vn().strftime("%d/%m/%Y %H:%M")
                        c.execute("UPDATE public.dm_nguyen_lieu SET ton_kho = ton_kho + %s WHERE ten_nl = %s", (sl_tt, nl_chon))
                        # Mặc định đơn giá và thành tiền là 0
                        c.execute("""INSERT INTO public.ls_nhap_xuat_kho (ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, don_gia, thanh_tien, ghi_chu) 
                                     VALUES (%s, 'Nhập NVL', %s, %s, 0, 0, %s)""", (ngay_tt, nl_chon, sl_tt, ghi_chu))
                        conn.commit()
                        st.success(f"✅ Đã nhập {sl_tt} {nl_chon} vào kho!")
                        time.sleep(1); st.rerun()
        except Exception as e: st.error(str(e))

    elif "2. Nhập Thành Phẩm" in chuyem_muc:
        st.markdown("#### 📦 Nhập Thành Phẩm Vừa Sản Xuất (Tự động trừ NVL cấu thành)")
        try:
            df_sp_chuan = pd.read_sql("SELECT ten_sp, ds_nguyen_lieu, ton_kho, 'chuẩn' as loai FROM public.dm_san_pham", conn)
            df_sp_ome = pd.read_sql("SELECT ten_sp, ds_nguyen_lieu, ton_kho, 'ome' as loai FROM public.dm_san_pham_ome", conn)
            df_all_sp = pd.concat([df_sp_chuan, df_sp_ome])
            
            if not df_all_sp.empty:
                with st.form("form_nhap_sp"):
                    sp_chon = st.selectbox("Chọn Thành Phẩm đã làm xong", df_all_sp['ten_sp'].tolist())
                    sl_nhap = st.number_input("Số lượng thành phẩm nhập kho (Cái/Bộ)", min_value=1.0, step=1.0)
                    
                    if st.form_submit_button("🔄 Lưu & Tự Động Cấn Trừ BOM", type="primary"):
                        sp_info = df_all_sp[df_all_sp['ten_sp'] == sp_chon].iloc[0]
                        loai_sp = sp_info['loai']
                        ds_nl_json = sp_info['ds_nguyen_lieu']
                        ngay_tt = lay_gio_vn().strftime("%d/%m/%Y %H:%M")

                        bang_update = "public.dm_san_pham" if loai_sp == 'chuẩn' else "public.dm_san_pham_ome"
                        c.execute(f"UPDATE {bang_update} SET ton_kho = ton_kho + %s WHERE ten_sp = %s", (sl_nhap, sp_chon))
                        c.execute("""INSERT INTO public.ls_nhap_xuat_kho (ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, ghi_chu) 
                                     VALUES (%s, 'Nhập Thành Phẩm', %s, %s, 'Sản xuất hoàn thành')""", (ngay_tt, sp_chon, sl_nhap))
                        
                        try:
                            ds_vat_tu = json.loads(ds_nl_json) if ds_nl_json else []
                            for vt in ds_vat_tu:
                                ten_vt = vt.get('vat_tu')
                                dinh_muc = float(vt.get('dinh_muc', 0))
                                tong_hao_phi = dinh_muc * sl_nhap
                                
                                c.execute("UPDATE public.dm_nguyen_lieu SET ton_kho = ton_kho - %s WHERE ten_nl = %s", (tong_hao_phi, ten_vt))
                                c.execute("""INSERT INTO public.ls_nhap_xuat_kho (ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, ghi_chu) 
                                             VALUES (%s, 'Xuất cấn trừ BOM', %s, %s, %s)""", 
                                          (ngay_tt, ten_vt, -tong_hao_phi, f"Làm {sl_nhap} {sp_chon}"))
                        except: pass
                        
                        conn.commit()
                        st.success(f"✅ Đã nhập {sl_nhap} {sp_chon}. Kho NVL đã được tự động trừ hao phí tương ứng!")
                        time.sleep(2); st.rerun()
            else: st.info("Chưa có danh mục sản phẩm.")
        except Exception as e: st.error(str(e))

with tab3:
    st.info("💡 **Mẹo:** Bạn có thể chỉnh sửa trực tiếp số liệu ở cột **Tồn Kho (Sửa được)**. Sau khi sửa, hãy bấm nút Lưu xuất hiện bên dưới bảng để cập nhật.")
    c_tk1, c_tk2 = st.columns(2)
    
    with c_tk1:
        st.subheader("🧊 Tồn Kho Nguyên Vật Liệu")
        df_ton_nl = pd.read_sql("SELECT id, ten_nl, ton_kho, don_vi FROM public.dm_nguyen_lieu ORDER BY ten_nl", conn)
        
        edited_nl_ton = st.data_editor(
            df_ton_nl,
            column_config={
                "id": None, # Ẩn cột ID
                "ten_nl": st.column_config.TextColumn("Vật Tư", disabled=True),
                "ton_kho": st.column_config.NumberColumn("Tồn Kho (Sửa được)"),
                "don_vi": st.column_config.TextColumn("Đơn Vị", disabled=True)
            },
            hide_index=True, use_container_width=True, key="edit_ton_nl"
        )
        
        diff_nl = (edited_nl_ton['ton_kho'] != df_ton_nl['ton_kho'])
        if diff_nl.any():
            if st.button("💾 LƯU TỒN KHO NVL", type="primary", use_container_width=True):
                changed_nl = edited_nl_ton[diff_nl]
                for _, row in changed_nl.iterrows():
                    c.execute("UPDATE public.dm_nguyen_lieu SET ton_kho=%s WHERE id=%s", (float(row['ton_kho']), int(row['id'])))
                conn.commit()
                st.success("✅ Đã cập nhật tồn kho Nguyên vật liệu!"); time.sleep(1); st.rerun()

    with c_tk2:
        st.subheader("📦 Tồn Kho Thành Phẩm")
        df_tc = pd.read_sql("SELECT id, ten_sp, ton_kho, 'chuẩn' as loai FROM public.dm_san_pham", conn)
        df_to = pd.read_sql("SELECT id, ten_sp, ton_kho, 'ome' as loai FROM public.dm_san_pham_ome", conn)
        df_tp = pd.concat([df_tc, df_to]).dropna().reset_index(drop=True)
        
        edited_tp = st.data_editor(
            df_tp,
            column_config={
                "id": None, # Ẩn cột ID
                "loai": None, # Ẩn cột phân loại bảng
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
