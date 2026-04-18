import streamlit as st
import pandas as pd
import time
import json
from db_utils import get_connection, check_password

st.set_page_config(page_title="Quản Lý Sản Phẩm", page_icon="📦", layout="wide")

# ==========================================
# Ổ KHÓA BẢO VỆ 2 LỚP
# ==========================================
role = check_password()
if not role: st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang này chứa dữ liệu mật, chỉ dành cho Quản lý WANCHI.")
    st.stop()

st.header("📦 Quản Lý Danh Mục Sản Phẩm & BOM")

conn = get_connection()
c = conn.cursor()

# ==========================================
# CẬP NHẬT DATABASE (THÊM CỘT CHO TÍNH NĂNG BOM)
# ==========================================
try:
    c.execute("CREATE SCHEMA IF NOT EXISTS public;")
    # 1. Bảng Hàng Chuẩn
    c.execute('''CREATE TABLE IF NOT EXISTS dm_san_pham (
                    id SERIAL PRIMARY KEY,
                    ma_sp TEXT UNIQUE,
                    ten_sp TEXT UNIQUE,
                    gia_dai_ly REAL DEFAULT 0,
                    gia_khach_le REAL DEFAULT 0,
                    dinh_muc_nhua REAL DEFAULT 0,
                    don_gia_nhua REAL DEFAULT 0,
                    don_gia_cong REAL DEFAULT 0
                )''')
    
    # Ép thêm các cột mới phục vụ ghép bộ BOM
    cac_cot_sp = {
        "ma_sp": "TEXT",
        "chi_phi_khac": "REAL DEFAULT 0",
        "chi_tiet_bom": "TEXT"
    }
    for cot, kieu in cac_cot_sp.items():
        try: c.execute(f"ALTER TABLE dm_san_pham ADD COLUMN {cot} {kieu}")
        except: pass

    # 2. Bảng Hàng OME
    c.execute('''CREATE TABLE IF NOT EXISTS dm_san_pham_ome (
                    id SERIAL PRIMARY KEY,
                    ten_sp TEXT UNIQUE,
                    gia_ome REAL DEFAULT 0,
                    dinh_muc_nhua REAL DEFAULT 0,
                    don_gia_nhua REAL DEFAULT 0,
                    don_gia_cong REAL DEFAULT 0,
                    chi_phi_khac REAL DEFAULT 0
                )''')
    conn.commit()
except Exception as e: pass

# ==========================================
# GIAO DIỆN 5 TABS (BỔ SUNG TAB GHÉP BỘ BOM)
# ==========================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "➕ Thêm SP Chuẩn", "📋 Danh Sách SP Chuẩn", 
    "➕ Thêm SP OME", "📋 Danh Sách SP OME", 
    "🧩 Ghép Bộ (BOM)"
])

# ------------------------------------------
# TAB 1: THÊM SẢN PHẨM CHUẨN
# ------------------------------------------
with tab1:
    st.subheader("Thêm Cấu Kiện / Sản Phẩm Chuẩn")
    with st.form("form_them_sp"):
        col1, col2, col3 = st.columns(3)
        with col1:
            ma_sp = st.text_input("Mã sản phẩm (VD: NAP-Y) (*)")
            ten_sp = st.text_input("Tên sản phẩm (VD: Nắp Nhựa Y) (*)")
        with col2:
            gia_dai_ly = st.number_input("Đơn giá Đại lý (VNĐ)", min_value=0.0, step=1000.0)
            st.markdown("*(Giá khách lẻ tự động = Giá Đại Lý / 0.6)*")
        with col3:
            dinh_muc_nhua = st.number_input("Định mức nhựa (Gram/cái)", min_value=0.0, step=10.0)
            don_gia_nhua = st.number_input("Đơn giá nhựa (VNĐ/kg)", min_value=0.0, step=1000.0)
            don_gia_cong = st.number_input("Đơn giá công ép (VNĐ/cái)", min_value=0.0, step=100.0)

        if st.form_submit_button("💾 Lưu Cấu Kiện / Sản Phẩm", type="primary"):
            if not ma_sp.strip() or not ten_sp.strip():
                st.warning("⚠️ Vui lòng nhập Mã và Tên sản phẩm!")
            else:
                gia_khach_le_calc = round(gia_dai_ly / 0.6)
                try:
                    c.execute("""INSERT INTO dm_san_pham 
                                 (ma_sp, ten_sp, gia_dai_ly, gia_khach_le, dinh_muc_nhua, don_gia_nhua, don_gia_cong) 
                                 VALUES (%s, %s, %s, %s, %s, %s, %s)""", 
                              (ma_sp.strip(), ten_sp.strip(), gia_dai_ly, gia_khach_le_calc, dinh_muc_nhua, don_gia_nhua, don_gia_cong))
                    st.success(f"✅ Đã thêm {ten_sp} thành công!")
                    time.sleep(1)
                    st.rerun()
                except: st.error("⚠️ Mã hoặc Tên này đã tồn tại!")

# ------------------------------------------
# TAB 2: QUẢN LÝ DANH SÁCH SP CHUẨN
# ------------------------------------------
with tab2:
    st.subheader("Cập Nhật & Sửa Chữa SP Chuẩn")
    try:
        # Chỉ hiển thị các cột cơ bản để bảng không bị rối bởi JSON của BOM
        df_sp = pd.read_sql("SELECT id, ma_sp, ten_sp, gia_dai_ly, gia_khach_le, dinh_muc_nhua, don_gia_nhua, don_gia_cong, chi_tiet_bom FROM dm_san_pham ORDER BY id DESC", conn)
        
        if not df_sp.empty:
            # Tạo cột phân loại BOM để dễ nhìn
            df_sp['Phân loại'] = df_sp['chi_tiet_bom'].apply(lambda x: "📦 SP Bộ (BOM)" if pd.notna(x) else "🧩 Cấu kiện/SP Rời")
            df_hien_thi = df_sp.drop(columns=['chi_tiet_bom'])

            edited_sp = st.data_editor(
                df_hien_thi, key="bang_sua_gia",
                column_config={
                    "id": None, 
                    "Phân loại": st.column_config.TextColumn("Loại Hàng", disabled=True),
                    "ma_sp": st.column_config.TextColumn("Mã SP"),
                    "ten_sp": st.column_config.TextColumn("Tên Sản Phẩm", disabled=True),
                    "gia_dai_ly": st.column_config.NumberColumn("Giá Đại lý", format="%d"),
                    "gia_khach_le": st.column_config.NumberColumn("Giá Khách lẻ", disabled=True, format="%d"),
                    "dinh_muc_nhua": st.column_config.NumberColumn("Định mức nhựa (g)", format="%d"),
                    "don_gia_nhua": st.column_config.NumberColumn("Giá nhựa/kg", format="%d"),
                    "don_gia_cong": st.column_config.NumberColumn("Giá công/cái", format="%d"),
                },
                use_container_width=True, hide_index=True
            )

            if st.button("💾 Lưu Bảng Giá Chuẩn", type="primary"):
                for index, row in edited_sp.iterrows():
                    gia_kl = round(float(row['gia_dai_ly']) / 0.6)
                    c.execute("""UPDATE dm_san_pham 
                                 SET ma_sp=%s, gia_dai_ly=%s, gia_khach_le=%s, dinh_muc_nhua=%s, don_gia_nhua=%s, don_gia_cong=%s 
                                 WHERE id=%s""",
                              (str(row['ma_sp']), float(row['gia_dai_ly']), gia_kl, float(row['dinh_muc_nhua']), float(row['don_gia_nhua']), float(row['don_gia_cong']), int(row['id'])))
                st.success("✅ Đã cập nhật thành công!")
                time.sleep(1)
                st.rerun()

            st.markdown("---")
            st.subheader("🗑️ Xóa Sản Phẩm")
            col_xoa1, col_xoa2 = st.columns([3, 1])
            with col_xoa1: sp_can_xoa = st.selectbox("Chọn SP cần xóa:", ["-- Chọn --"] + df_sp['ten_sp'].tolist())
            with col_xoa2:
                st.write(""); st.write("")
                if st.button("🚨 Xóa Vĩnh Viễn", type="primary", use_container_width=True):
                    if sp_can_xoa != "-- Chọn --":
                        c.execute("DELETE FROM dm_san_pham WHERE ten_sp=%s", (sp_can_xoa,))
                        st.success(f"✅ Đã xóa: {sp_can_xoa}")
                        time.sleep(1)
                        st.rerun()
        else: st.info("Chưa có sản phẩm nào.")
    except Exception as e: st.error(f"Lỗi: {e}")

# ------------------------------------------
# TAB 3: THÊM SP OME
# ------------------------------------------
with tab3:
    st.subheader("Thêm Sản Phẩm OME (Gia Công)")
    with st.form("form_them_ome", clear_on_submit=True):
        col_o1, col_o2, col_o3 = st.columns(3)
        with col_o1:
            ten_sp_ome = st.text_input("Tên sản phẩm OME (*)")
            gia_ome = st.number_input("Đơn giá OME (VNĐ)", min_value=0.0, step=1000.0)
        with col_o2:
            dinh_muc_ome = st.number_input("Định mức nhựa (Gram/cái)", min_value=0.0, step=10.0)
            gia_nhua_ome = st.number_input("Đơn giá nhựa (VNĐ/kg)", min_value=0.0, step=1000.0)
        with col_o3:
            gia_cong_ome = st.number_input("Đơn giá công ép (VNĐ/cái)", min_value=0.0, step=100.0)
            chi_phi_khac_ome = st.number_input("Chi phí khác tạo SP (VNĐ)", min_value=0.0, step=1000.0)

        if st.form_submit_button("💾 Lưu Sản Phẩm OME", type="primary"):
            if not ten_sp_ome.strip(): st.warning("⚠️ Vui lòng nhập Tên sản phẩm OME!")
            else:
                try:
                    c.execute("""INSERT INTO dm_san_pham_ome 
                                 (ten_sp, gia_ome, dinh_muc_nhua, don_gia_nhua, don_gia_cong, chi_phi_khac) 
                                 VALUES (%s, %s, %s, %s, %s, %s)""", 
                              (ten_sp_ome.strip(), gia_ome, dinh_muc_ome, gia_nhua_ome, gia_cong_ome, chi_phi_khac_ome))
                    st.success(f"✅ Đã thêm OME: {ten_sp_ome}!")
                    time.sleep(1)
                    st.rerun()
                except: st.error("⚠️ Tên OME này đã tồn tại!")

# ------------------------------------------
# TAB 4: DS SP OME
# ------------------------------------------
with tab4:
    st.subheader("Cập Nhật SP OME")
    try:
        df_ome = pd.read_sql("SELECT * FROM dm_san_pham_ome ORDER BY id DESC", conn)
        if not df_ome.empty:
            edited_ome = st.data_editor(
                df_ome, key="bang_sua_ome",
                column_config={
                    "id": None, 
                    "ten_sp": st.column_config.TextColumn("Tên SP OME", disabled=True),
                    "gia_ome": st.column_config.NumberColumn("Đơn giá OME", format="%d"),
                    "dinh_muc_nhua": st.column_config.NumberColumn("Định mức nhựa (g)", format="%d"),
                    "don_gia_nhua": st.column_config.NumberColumn("Giá nhựa/kg", format="%d"),
                    "don_gia_cong": st.column_config.NumberColumn("Giá công/cái", format="%d"),
                    "chi_phi_khac": st.column_config.NumberColumn("Chi phí khác", format="%d"),
                }, use_container_width=True, hide_index=True
            )

            if st.button("💾 Lưu Bảng Giá OME", type="primary"):
                for index, row in edited_ome.iterrows():
                    c.execute("""UPDATE dm_san_pham_ome 
                                 SET gia_ome=%s, dinh_muc_nhua=%s, don_gia_nhua=%s, don_gia_cong=%s, chi_phi_khac=%s 
                                 WHERE id=%s""",
                              (float(row['gia_ome']), float(row['dinh_muc_nhua']), float(row['don_gia_nhua']), float(row['don_gia_cong']), float(row['chi_phi_khac']), int(row['id'])))
                st.success("✅ Cập nhật OME thành công!")
                time.sleep(1)
                st.rerun()
                
            st.markdown("---")
            col_oxoa1, col_oxoa2 = st.columns([3, 1])
            with col_oxoa1: ome_can_xoa = st.selectbox("Chọn OME cần xóa:", ["-- Chọn --"] + df_ome['ten_sp'].tolist())
            with col_oxoa2:
                st.write(""); st.write("")
                if st.button("🚨 Xóa Hàng OME", type="primary", use_container_width=True):
                    if ome_can_xoa != "-- Chọn --":
                        c.execute("DELETE FROM dm_san_pham_ome WHERE ten_sp=%s", (ome_can_xoa,))
                        st.success("✅ Đã xóa!")
                        time.sleep(1)
                        st.rerun()
        else: st.info("Chưa có hàng OME.")
    except: pass

# ------------------------------------------
# TAB 5: GHÉP BỘ (BOM) - TÍNH NĂNG MỚI SIÊU VIỆT
# ------------------------------------------
with tab5:
    st.subheader("🧩 Ghép Cấu Kiện Thành Sản Phẩm Bộ (BOM)")
    st.info("Công thức: Giá Vốn 1 cấu kiện = (Định mức nhựa / 1000 * Giá nhựa) + Giá công ép + Chi phí khác.")
    
    # Kéo danh sách Cấu kiện thật (Loại trừ các SP Bộ đã tạo trước đó để tránh lồng nhau gây nhiễu)
    try:
        df_parts_chuan = pd.read_sql("SELECT ten_sp, dinh_muc_nhua, don_gia_nhua, don_gia_cong, 0 as chi_phi_khac FROM dm_san_pham WHERE chi_tiet_bom IS NULL", conn)
        df_parts_ome = pd.read_sql("SELECT ten_sp, dinh_muc_nhua, don_gia_nhua, don_gia_cong, chi_phi_khac FROM dm_san_pham_ome", conn)
        df_all_parts = pd.concat([df_parts_chuan, df_parts_ome], ignore_index=True)
    except: df_all_parts = pd.DataFrame()

    if 'bom_items' not in st.session_state: st.session_state.bom_items = []

    col_bom1, col_bom2 = st.columns([1, 1])
    with col_bom1: ma_bom = st.text_input("Mã Sản Phẩm Bộ (VD: BO-Y)", key="ma_bom")
    with col_bom2: ten_bom = st.text_input("Tên Sản Phẩm Bộ (VD: Sản phẩm Y Hoàn Chỉnh)", key="ten_bom")

    # 1. Thêm Cấu Kiện
    st.markdown("### 1. Nhặt Cấu Kiện Vào Bộ")
    with st.form("form_add_bom", clear_on_submit=True):
        c_p1, c_p2 = st.columns([3, 1])
        part_chon = c_p1.selectbox("Chọn Cấu kiện (Nắp, Thân...):", ["-- Chọn --"] + df_all_parts['ten_sp'].tolist() if not df_all_parts.empty else ["-- Chọn --"])
        sl_part = c_p2.number_input("Số lượng", min_value=1, step=1)
        
        if st.form_submit_button("➕ Thêm vào Bộ"):
            if part_chon != "-- Chọn --":
                info_p = df_all_parts[df_all_parts['ten_sp'] == part_chon].iloc[0]
                # TÍNH GIÁ VỐN THEO ĐÚNG LOGIC NGÀNH NHỰA
                gia_von_1_cai = (float(info_p['dinh_muc_nhua']) / 1000 * float(info_p['don_gia_nhua'])) + float(info_p['don_gia_cong']) + float(info_p['chi_phi_khac'])
                
                st.session_state.bom_items.append({
                    "Tên Cấu Kiện": part_chon,
                    "Số Lượng": sl_part,
                    "Giá Vốn / Cái": gia_von_1_cai,
                    "Thành Tiền": gia_von_1_cai * sl_part
                })
                st.rerun()

    # 2. Hiển thị và Tính toán
    if st.session_state.bom_items:
        df_bom_hien_thi = pd.DataFrame(st.session_state.bom_items)
        st.dataframe(df_bom_hien_thi, use_container_width=True, hide_index=True)
        
        if st.button("🗑️ Xóa sạch cấu kiện"):
            st.session_state.bom_items = []
            st.rerun()

        st.markdown("### 2. Thiết Lập Giá Bán Cuối Cùng")
        col_cp1, col_cp2 = st.columns(2)
        cp_rap_bao_bi = col_cp1.number_input("Chi phí Lắp ráp, Tem, Bao bì (VNĐ/Bộ)", min_value=0, step=1000)
        bien_do_loi_nhuan = col_cp2.number_input("Biên độ lợi nhuận kỳ vọng (%)", value=20, step=5)

        # TOÁN HỌC CHỐT GIÁ
        tong_gia_von_cau_kien = df_bom_hien_thi['Thành Tiền'].sum()
        tong_gia_von_cuoi = tong_gia_von_cau_kien + cp_rap_bao_bi
        gia_dai_ly_chot = tong_gia_von_cuoi * (1 + bien_do_loi_nhuan / 100)
        gia_khach_le_chot = gia_dai_ly_chot / 0.6

        # Hiển thị Real-time
        st.markdown("---")
        m1, m2, m3 = st.columns(3)
        m1.metric("1. TỔNG GIÁ VỐN GỐC", f"{tong_gia_von_cuoi:,.0f} VNĐ")
        m2.metric("2. GIÁ ĐẠI LÝ (Đã + Lợi nhuận)", f"{gia_dai_ly_chot:,.0f} VNĐ")
        m3.metric("3. GIÁ KHÁCH LẺ (/ 0.6)", f"{gia_khach_le_chot:,.0f} VNĐ")

        if st.button("💾 CHỐT & LƯU SẢN PHẨM BỘ NÀY", type="primary", use_container_width=True):
            if not ma_bom.strip() or not ten_bom.strip():
                st.error("⚠️ Vui lòng cuộn lên trên nhập Mã và Tên SP Bộ!")
            else:
                chi_tiet_json = df_bom_hien_thi.to_json(orient='records')
                try:
                    # Đẩy thẳng vào bảng dm_san_pham với cờ chi_tiet_bom để App Tạo Đơn Hàng đọc được ngay
                    c.execute("""INSERT INTO dm_san_pham 
                                 (ma_sp, ten_sp, gia_dai_ly, gia_khach_le, dinh_muc_nhua, don_gia_nhua, don_gia_cong, chi_phi_khac, chi_tiet_bom) 
                                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
                              (ma_bom.strip(), ten_bom.strip(), gia_dai_ly_chot, gia_khach_le_chot, 0, 0, 0, cp_rap_bao_bi, chi_tiet_json))
                    st.success(f"✅ Đã tạo thành công SP Bộ: {ten_bom}! Bạn đã có thể dùng nó ở trang Tạo Đơn Hàng.")
                    st.session_state.bom_items = []
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️ Mã hoặc Tên SP Bộ này đã tồn tại! ({e})")
