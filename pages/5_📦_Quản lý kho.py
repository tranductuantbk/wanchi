import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
from db_utils import get_connection, check_password

# ==========================================
# CẤU HÌNH MÚI GIỜ VIỆT NAM (UTC+7)
# ==========================================
VN_TZ = timezone(timedelta(hours=7))
def lay_gio_vn():
    return datetime.now(VN_TZ)

st.set_page_config(page_title="Quản Lý Kho Vật Tư", page_icon="📦", layout="wide")

# ==========================================
# Ổ KHÓA BẢO VỆ 2 LỚP
# ==========================================
role = check_password()
if not role: st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang Quản Lý Kho chỉ dành cho Quản lý WANCHI.")
    st.stop()

st.header("📦 Quản Lý Kho Nguyên Vật Liệu (Đồng bộ Sản Phẩm)")

conn = get_connection()
c = conn.cursor()

# ==========================================
# KHỞI TẠO BẢNG DỮ LIỆU ĐỒNG BỘ VỚI FILE SẢN PHẨM
# ==========================================
try:
    c.execute("CREATE SCHEMA IF NOT EXISTS public;")
    # Bảng này chính là bảng mà File Sản Phẩm đang đọc
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_nguyen_lieu (
                    id SERIAL PRIMARY KEY,
                    ma_nl TEXT UNIQUE,
                    ten_nl TEXT UNIQUE,
                    don_vi TEXT,
                    ton_kho REAL DEFAULT 0
                )''')
    
    # Bảng Lịch sử Nhập/Xuất kho
    c.execute('''CREATE TABLE IF NOT EXISTS public.ls_nhap_xuat_kho (
                    id SERIAL PRIMARY KEY,
                    ngay_thao_tac TEXT,
                    loai_thao_tac TEXT,
                    ten_nl TEXT,
                    so_luong REAL,
                    don_gia REAL DEFAULT 0,
                    thanh_tien REAL DEFAULT 0,
                    ghi_chu TEXT
                )''')
    conn.commit()
except Exception as e: pass

# ==========================================
# GIAO DIỆN 3 TABS QUẢN LÝ KHO
# ==========================================
tab1, tab2, tab3 = st.tabs(["📋 Danh Mục Vật Tư", "📥 Nhập / Xuất Kho", "📊 Báo Cáo Tồn Kho"])

# ------------------------------------------
# TAB 1: DANH MỤC VẬT TƯ (Nguồn cấp cho file Sản Phẩm)
# ------------------------------------------
with tab1:
    st.subheader("1. Khai báo Nguyên Vật Liệu Mới")
    st.info("💡 Lưu ý: Các vật tư tạo ở đây sẽ tự động xuất hiện bên mục 'Nguyên liệu cấu tạo' của trang Thêm Sản Phẩm.")
    with st.form("form_them_nl", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1: ma_nl = st.text_input("Mã Vật Tư (VD: NHUA-PP)")
        with c2: ten_nl = st.text_input("Tên Vật Tư (VD: Hạt nhựa PP trắng) (*)")
        with c3: don_vi = st.selectbox("Đơn vị tính", ["Kg", "Gram", "Cái", "Thùng", "Cuộn", "Mét"])
        
        if st.form_submit_button("💾 Lưu Danh Mục Vật Tư", type="primary"):
            if ten_nl.strip():
                try:
                    c.execute("INSERT INTO public.dm_nguyen_lieu (ma_nl, ten_nl, don_vi, ton_kho) VALUES (%s, %s, %s, 0)", 
                              (ma_nl.strip(), ten_nl.strip(), don_vi))
                    st.success(f"✅ Đã thêm '{ten_nl}' vào danh mục! Bạn có thể sang trang Sản phẩm để kiểm tra.")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e: 
                    st.error("⚠️ Mã hoặc tên vật tư này đã tồn tại trong hệ thống!")
            else: st.warning("⚠️ Vui lòng nhập Tên Vật Tư!")
    
    st.markdown("---")
    st.subheader("2. Cập nhật & Xóa Danh Mục")
    try:
        df_dm = pd.read_sql("SELECT id, ma_nl, ten_nl, don_vi FROM public.dm_nguyen_lieu ORDER BY id DESC", conn)
        if not df_dm.empty:
            edited_nl = st.data_editor(
                df_dm, key="bang_sua_nl",
                column_config={
                    "id": None, 
                    "ma_nl": st.column_config.TextColumn("Mã Vật Tư"),
                    "ten_nl": st.column_config.TextColumn("Tên Vật Tư", disabled=True),
                    "don_vi": st.column_config.SelectboxColumn("Đơn vị", options=["Kg", "Gram", "Cái", "Thùng", "Cuộn", "Mét"]),
                }, use_container_width=True, hide_index=True
            )

            if st.button("💾 Lưu Bảng Danh Mục", type="primary"):
                for index, row in edited_nl.iterrows():
                    c.execute("UPDATE public.dm_nguyen_lieu SET ma_nl=%s, don_vi=%s WHERE id=%s", (str(row['ma_nl']), str(row['don_vi']), int(row['id'])))
                st.success("✅ Đã cập nhật thành công!")
                time.sleep(1); st.rerun()
                
            col_xoa1, col_xoa2 = st.columns([3, 1])
            with col_xoa1: nl_can_xoa = st.selectbox("Chọn Vật Tư cần xóa:", ["-- Chọn --"] + df_dm['ten_nl'].tolist())
            with col_xoa2:
                st.write(""); st.write("")
                if st.button("🚨 Xóa Vật Tư", type="primary", use_container_width=True):
                    if nl_can_xoa != "-- Chọn --":
                        c.execute("DELETE FROM public.dm_nguyen_lieu WHERE ten_nl=%s", (nl_can_xoa,))
                        st.success("✅ Đã xóa!")
                        time.sleep(1); st.rerun()
        else: st.info("Chưa có vật tư nào. Hãy thêm ở form phía trên.")
    except Exception as e: st.error(f"Lỗi hiển thị: {e}")

# ------------------------------------------
# TAB 2: NHẬP XUẤT KHO THỦ CÔNG
# ------------------------------------------
with tab2:
    st.subheader("Nhập / Xuất Kho Thủ Công")
    try:
        df_nl_ton = pd.read_sql("SELECT ten_nl, don_vi, ton_kho FROM public.dm_nguyen_lieu", conn)
        if not df_nl_ton.empty:
            with st.form("form_nhap_xuat", clear_on_submit=True):
                c_a, c_b, c_c = st.columns(3)
                loai_tt = c_a.selectbox("Loại thao tác", ["Nhập Kho (Mua vào)", "Xuất Kho (Trừ hao/Hư hỏng)"])
                nl_chon = c_b.selectbox("Chọn Vật Tư", df_nl_ton['ten_nl'].tolist())
                sl_tt = c_c.number_input("Số lượng", min_value=0.0, step=1.0)
                
                don_gia = st.number_input("Đơn giá nhập (VNĐ) - Chỉ điền khi Mua vào", min_value=0.0, step=1000.0)
                ghi_chu = st.text_input("Ghi chú (Nhà cung cấp / Lý do xuất)")

                if st.form_submit_button("💾 Xác nhận Thao Tác", type="primary"):
                    if sl_tt > 0:
                        ton_hien_tai = df_nl_ton[df_nl_ton['ten_nl'] == nl_chon].iloc[0]['ton_kho']
                        if loai_tt == "Xuất Kho (Trừ hao/Hư hỏng)" and sl_tt > ton_hien_tai:
                            st.error(f"⚠️ Vượt quá số lượng tồn! Trong kho chỉ còn **{ton_hien_tai}**.")
                        else:
                            sl_thay_doi = sl_tt if "Nhập Kho" in loai_tt else -sl_tt
                            thanh_tien = sl_tt * don_gia if "Nhập Kho" in loai_tt else 0
                            ngay_tt = lay_gio_vn().strftime("%d/%m/%Y %H:%M")
                            
                            # 1. Cập nhật tồn kho
                            c.execute("UPDATE public.dm_nguyen_lieu SET ton_kho = ton_kho + %s WHERE ten_nl = %s", (sl_thay_doi, nl_chon))
                            # 2. Ghi lịch sử
                            c.execute("""INSERT INTO public.ls_nhap_xuat_kho 
                                         (ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, don_gia, thanh_tien, ghi_chu) 
                                         VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                                      (ngay_tt, loai_tt, nl_chon, sl_tt, don_gia, thanh_tien, ghi_chu))
                            conn.commit()
                            st.success(f"✅ Đã {loai_tt.split()[0].lower()} thành công {sl_tt} {nl_chon}!")
                            time.sleep(1.5); st.rerun()
                    else: st.warning("⚠️ Số lượng phải lớn hơn 0!")
        else: st.info("⚠️ Vui lòng qua Tab 1 khai báo danh mục vật tư trước khi nhập kho.")
    except Exception as e: st.error(f"Lỗi hệ thống: {e}")

# ------------------------------------------
# TAB 3: BÁO CÁO TỒN KHO & LỊCH SỬ
# ------------------------------------------
with tab3:
    col_tk1, col_tk2 = st.columns([1, 2])
    with col_tk1:
        st.subheader("📦 Tồn Kho Hiện Tại")
        try:
            df_ton = pd.read_sql("SELECT ten_nl as \"Tên Vật Tư\", ton_kho as \"Tồn Kho\", don_vi as \"Đơn vị\" FROM public.dm_nguyen_lieu ORDER BY ten_nl ASC", conn)
            st.dataframe(df_ton, use_container_width=True, hide_index=True)
        except: pass

    with col_tk2:
        st.subheader("📜 Lịch Sử Nhập/Xuất Mới Nhất")
        try:
            df_ls = pd.read_sql("SELECT ngay_thao_tac, loai_thao_tac, ten_nl, so_luong, thanh_tien, ghi_chu FROM public.ls_nhap_xuat_kho ORDER BY id DESC LIMIT 50", conn)
            if not df_ls.empty:
                df_ls.columns = ["Thời gian", "Thao tác", "Vật tư", "Số lượng", "Thành tiền (VNĐ)", "Ghi chú"]
                
                # Format số tiền cho đẹp
                df_ls['Thành tiền (VNĐ)'] = df_ls['Thành tiền (VNĐ)'].apply(lambda x: f"{x:,.0f}" if x > 0 else "-")
                st.dataframe(df_ls, use_container_width=True, hide_index=True)
            else: st.info("Chưa có phát sinh nhập/xuất.")
        except: pass
