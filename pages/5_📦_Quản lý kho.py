import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import json
from db_utils import get_connection, check_password

# ==========================================
# CẤU HÌNH MÚI GIỜ VIỆT NAM (UTC+7)
# ==========================================
VN_TZ = timezone(timedelta(hours=7))
def lay_gio_vn():
    return datetime.now(VN_TZ)

st.set_page_config(page_title="Quản Lý Kho Toàn Diện", page_icon="📦", layout="wide")

# ==========================================
# Ổ KHÓA BẢO VỆ 2 LỚP
# ==========================================
role = check_password()
if not role: st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang Quản Lý Kho chỉ dành cho Quản lý WANCHI.")
    st.stop()

st.header("📦 Quản Lý Kho (Nguyên Vật Liệu & Thành Phẩm)")

conn = get_connection()
c = conn.cursor()

# ==========================================
# KHỞI TẠO BẢNG DỮ LIỆU & NÂNG CẤP SCHEMA
# ==========================================
try:
    c.execute("CREATE SCHEMA IF NOT EXISTS public;")
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_nguyen_lieu (
                    id SERIAL PRIMARY KEY,
                    ma_nl TEXT UNIQUE,
                    ten_nl TEXT UNIQUE,
                    don_vi TEXT,
                    ton_kho REAL DEFAULT 0
                )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS public.ls_nhap_xuat_kho (
                    id SERIAL PRIMARY KEY,
                    ngay_thao_tac TEXT,
                    loai_thao_tac TEXT,
                    ten_vat_tu TEXT,
                    so_luong REAL,
                    don_gia REAL DEFAULT 0,
                    thanh_tien REAL DEFAULT 0,
                    ghi_chu TEXT
                )''')
    
    # Nâng cấp bảng sản phẩm và đơn hàng để phục vụ Xuất/Nhập kho
    c.execute("ALTER TABLE public.dm_san_pham ADD COLUMN IF NOT EXISTS ton_kho REAL DEFAULT 0")
    c.execute("ALTER TABLE public.dm_san_pham_ome ADD COLUMN IF NOT EXISTS ton_kho REAL DEFAULT 0")
    c.execute("ALTER TABLE public.don_hang ADD COLUMN IF NOT EXISTS trang_thai TEXT DEFAULT 'Chờ xuất kho'")
    conn.commit()
except Exception as e: pass

# ==========================================
# GIAO DIỆN 3 TABS QUẢN LÝ KHO
# ==========================================
tab1, tab2, tab3 = st.tabs(["📋 Danh Mục NVL", "📥 Nhập / Xuất Kho (Thông Minh)", "📊 Báo Cáo Tồn Kho"])

# ------------------------------------------
# TAB 1: DANH MỤC NVL (Giữ nguyên)
# ------------------------------------------
with tab1:
    st.subheader("Khai báo Danh Mục Nguyên Vật Liệu")
    with st.form("form_them_nl", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1: ma_nl = st.text_input("Mã Vật Tư (Tùy chọn)")
        with c2: ten_nl = st.text_input("Tên Vật Tư (VD: Hạt nhựa PP trắng) (*)")
        with c3: don_vi = st.selectbox("Đơn vị tính", ["Kg", "Gram", "Cái", "Thùng", "Cuộn", "Mét"])
        
        if st.form_submit_button("💾 Lưu Danh Mục Vật Tư", type="primary"):
            if not ten_nl.strip(): st.warning("⚠️ Vui lòng nhập Tên Vật Tư!")
            else:
                ma_luu = ma_nl.strip()
                if not ma_luu: ma_luu = f"VT{int(time.time())}" 
                try:
                    c.execute("INSERT INTO public.dm_nguyen_lieu (ma_nl, ten_nl, don_vi, ton_kho) VALUES (%s, %s, %s, 0)", (ma_luu, ten_nl.strip(), don_vi))
                    st.success(f"✅ Đã thêm '{ten_nl}' vào danh mục!")
                    time.sleep(1); st.rerun()
                except Exception as e: st.error("⚠️ Tên hoặc mã vật tư đã tồn tại!")
    
    try:
        df_dm = pd.read_sql("SELECT id, ma_nl, ten_nl, don_vi FROM public.dm_nguyen_lieu ORDER BY id DESC", conn)
        if not df_dm.empty:
            edited_nl = st.data_editor(df_dm, key="bang_sua_nl", use_container_width=True, hide_index=True)
            if st.button("💾 Lưu Cập Nhật Đơn Vị"):
                for index, row in edited_nl.iterrows():
                    c.execute("UPDATE public.dm_nguyen_lieu SET don_vi=%s WHERE id=%s", (str(row['don_vi']), int(row['id'])))
                st.success("✅ Đã cập nhật!"); time.sleep(1); st.rerun()
    except Exception as e: pass

# ------------------------------------------
# TAB 2: NHẬP XUẤT KHO THÔNG MINH (3 CHẾ ĐỘ)
# ------------------------------------------
with tab2:
    st.subheader("Hệ Thống Nhập / Xuất Kho Tự Động")
    
    chuyem_muc = st.radio("Chọn nghiệp vụ Kho:", 
                          ["📥 1. Nhập NVL (Mua ngoài)", 
                           "📦 2. Nhập Thành Phẩm (Xưởng sx xong)", 
                           "🚚 3. Xuất Kho (Theo Đơn Đặt Hàng)"], 
                          horizontal=True)
    st.markdown("---")

    # --- CHẾ ĐỘ 1: NHẬP NVL ---
    if "1. Nhập NVL" in chuyem_muc:
        st.markdown("#### 📥 Nhập Cấu Kiện / Nguyên Vật Liệu")
        try:
            df_nl_ton = pd.read_sql("SELECT ten_nl, don_vi, ton_kho FROM public.dm_nguyen_lieu", conn)
            if not df_nl_ton.empty:
                with st.form("form_nhap_nvl"):
                    nl_chon = st.selectbox("Chọn Vật Tư", df_nl_ton['ten_nl'].tolist())
                    c_sl, c_gia = st.columns(2)
                    sl_tt = c_sl.number_input("Số lượng nhập", min_value=1.0, step=1.0)
                    don_gia = c_gia.number_input("Đơn giá nhập (VNĐ)", min_value=0.0, step=1000.0)
                    ghi_chu = st.text_input("Ghi chú (Nhà cung cấp)")

                    if st.form_submit_button("💾 Xác nhận Nhập NVL", type="primary"):
                        ngay_tt = lay_gio_vn().strftime("%d/%m/%Y %H:%M")
                        c.execute("UPDATE public.dm_nguyen_lieu SET ton_kho = ton_kho + %s WHERE ten_nl = %s", (sl_tt, nl_chon))
                        c.execute("""INSERT INTO public.ls_nhap_xuat_kho (ngay_thao_tac, loai_thao_tac, ten_vat_tu, so_luong, don_gia, thanh_tien, ghi_chu) 
                                     VALUES (%s, 'Nhập NVL', %s, %s, %s, %s, %s)""", (ngay_tt, nl_chon, sl_tt, don_gia, sl_tt*don_gia, ghi_chu))
                        conn.commit()
                        st.success(f"✅ Đã nhập {sl_tt} {nl_chon} vào kho!")
                        time.sleep(1); st.rerun()
        except: pass

    # --- CHẾ ĐỘ 2: NHẬP THÀNH PHẨM (TRỪ NVL) ---
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

                        # 1. Tăng tồn kho Thành Phẩm
                        bang_update = "public.dm_san_pham" if loai_sp == 'chuẩn' else "public.dm_san_pham_ome"
                        c.execute(f"UPDATE {bang_update} SET ton_kho = ton_kho + %s WHERE ten_sp = %s", (sl_nhap, sp_chon))
                        c.execute("""INSERT INTO public.ls_nhap_xuat_kho (ngay_thao_tac, loai_thao_tac, ten_vat_tu, so_luong, ghi_chu) 
                                     VALUES (%s, 'Nhập Thành Phẩm', %s, %s, 'Sản xuất hoàn thành')""", (ngay_tt, sp_chon, sl_nhap))
                        
                        # 2. Rã đông BOM và Trừ kho Nguyên Vật Liệu
                        try:
                            ds_vat_tu = json.loads(ds_nl_json) if ds_nl_json else []
                            for vt in ds_vat_tu:
                                ten_vt = vt.get('vat_tu')
                                dinh_muc = float(vt.get('dinh_muc', 0))
                                tong_hao_phi = dinh_muc * sl_nhap
                                
                                # Trừ kho NVL
                                c.execute("UPDATE public.dm_nguyen_lieu SET ton_kho = ton_kho - %s WHERE ten_nl = %s", (tong_hao_phi, ten_vt))
                                # Ghi lịch sử xuất cấn trừ
                                c.execute("""INSERT INTO public.ls_nhap_xuat_kho (ngay_thao_tac, loai_thao_tac, ten_vat_tu, so_luong, ghi_chu) 
                                             VALUES (%s, 'Xuất cấn trừ BOM', %s, %s, %s)""", 
                                          (ngay_tt, ten_vt, -tong_hao_phi, f"Làm {sl_nhap} {sp_chon}"))
                        except Exception as e: st.error(f"Lỗi đọc định mức BOM: {e}")
                        
                        conn.commit()
                        st.success(f"✅ Đã nhập {sl_nhap} {sp_chon}. Kho NVL đã được tự động trừ hao phí tương ứng!")
                        time.sleep(2); st.rerun()
            else: st.info("Chưa có danh mục sản phẩm.")
        except Exception as e: st.error(str(e))

    # --- CHẾ ĐỘ 3: XUẤT KHO THEO ĐƠN HÀNG ---
    elif "3. Xuất Kho" in chuyem_muc:
        st.markdown("#### 🚚 Lấy Phiếu Đơn Hàng Để Xuất Kho")
        try:
            # Chỉ lấy các đơn hàng chưa xuất kho
            df_dh = pd.read_sql("SELECT ma_don, ten_kh, ngay_tao, chi_tiet FROM public.don_hang WHERE trang_thai = 'Chờ xuất kho' OR trang_thai IS NULL", conn)
            if not df_dh.empty:
                don_chon = st.selectbox("📌 Chọn Mã Đơn Hàng cần xuất", df_dh['ma_don'].tolist())
                don_info = df_dh[df_dh['ma_don'] == don_chon].iloc[0]
                
                st.write(f"**Khách hàng:** {don_info['ten_kh']} | **Ngày tạo:** {str(don_info['ngay_tao'])[:10]}")
                
                # Hiển thị giỏ hàng bên trong Đơn hàng
                try: 
                    items = json.loads(don_info['chi_tiet'])
                    df_items = pd.DataFrame(items)
                    st.dataframe(df_items, use_container_width=True)
                    
                    if st.button("📦 XÁC NHẬN XUẤT KHO TOÀN BỘ ĐƠN NÀY", type="primary"):
                        ngay_tt = lay_gio_vn().strftime("%d/%m/%Y %H:%M")
                        
                        for item in items:
                            ten_sp_xuat = item.get('Tên Sản Phẩm', item.get('Tên Sản Phẩm OME'))
                            sl_xuat = float(item.get('Số Lượng', 0))
                            
                            # Trừ Tồn kho Sản phẩm (Thử cả bảng chuẩn và OME)
                            c.execute("UPDATE public.dm_san_pham SET ton_kho = ton_kho - %s WHERE ten_sp = %s", (sl_xuat, ten_sp_xuat))
                            c.execute("UPDATE public.dm_san_pham_ome SET ton_kho = ton_kho - %s WHERE ten_sp = %s", (sl_xuat, ten_sp_xuat))
                            
                            # Ghi lịch sử
                            c.execute("""INSERT INTO public.ls_nhap_xuat_kho (ngay_thao_tac, loai_thao_tac, ten_vat_tu, so_luong, ghi_chu) 
                                         VALUES (%s, 'Xuất Bán Hàng', %s, %s, %s)""", 
                                      (ngay_tt, ten_sp_xuat, -sl_xuat, f"Xuất cho đơn {don_chon}"))
                            
                        # Đổi trạng thái đơn hàng
                        c.execute("UPDATE public.don_hang SET trang_thai = 'Đã xuất kho' WHERE ma_don = %s", (don_chon,))
                        conn.commit()
                        st.success(f"✅ Đã xuất kho thành công Đơn {don_chon}!")
                        time.sleep(2); st.rerun()
                except Exception as e: st.error("Lỗi đọc chi tiết đơn hàng.")
            else: st.success("🎉 Mọi đơn hàng đều đã được xuất kho (hoặc chưa có đơn mới)!")
        except Exception as e: st.error(str(e))

# ------------------------------------------
# TAB 3: BÁO CÁO TỒN KHO & LỊCH SỬ
# ------------------------------------------
with tab3:
    col_tk1, col_tk2 = st.columns(2)
    with col_tk1:
        st.subheader("🧊 Tồn Kho Nguyên Vật Liệu")
        try:
            df_ton_nl = pd.read_sql("SELECT ten_nl as \"Nguyên Vật Liệu\", ton_kho as \"Tồn Kho\", don_vi as \"Đơn vị\" FROM public.dm_nguyen_lieu", conn)
            st.dataframe(df_ton_nl, use_container_width=True, hide_index=True)
        except: pass

    with col_tk2:
        st.subheader("📦 Tồn Kho Thành Phẩm")
        try:
            df_ton_chuan = pd.read_sql("SELECT ten_sp as \"Thành Phẩm\", ton_kho as \"Tồn Kho\" FROM public.dm_san_pham", conn)
            df_ton_ome = pd.read_sql("SELECT ten_sp as \"Thành Phẩm\", ton_kho as \"Tồn Kho\" FROM public.dm_san_pham_ome", conn)
            df_ton_sp = pd.concat([df_ton_chuan, df_ton_ome]).dropna()
            st.dataframe(df_ton_sp, use_container_width=True, hide_index=True)
        except: pass

    st.markdown("---")
    st.subheader("📜 Sổ Lịch Sử Nhập / Xuất (NVL & Sản Phẩm)")
    try:
        df_ls = pd.read_sql("SELECT ngay_thao_tac, loai_thao_tac, ten_vat_tu, so_luong, ghi_chu FROM public.ls_nhap_xuat_kho ORDER BY id DESC LIMIT 100", conn)
        if not df_ls.empty:
            df_ls.columns = ["Thời gian", "Nghiệp vụ", "Tên Món Hàng", "Số lượng (+/-)", "Ghi chú"]
            st.dataframe(df_ls, use_container_width=True, hide_index=True)
    except: pass
