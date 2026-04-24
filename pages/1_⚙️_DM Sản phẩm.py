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

st.header("📦 Quản Lý Danh Mục Sản Phẩm (BOM Đa Vật Tư)")

conn = get_connection()
c = conn.cursor()

# ==========================================
# CẬP NHẬT DATABASE 
# ==========================================
try:
    c.execute("CREATE SCHEMA IF NOT EXISTS public;")
    
    # --- 1. BẢNG DANH MỤC NGUYÊN LIỆU ---
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_nguyen_lieu (
                    id SERIAL PRIMARY KEY,
                    ma_nl TEXT UNIQUE,
                    ten_nl TEXT UNIQUE,
                    don_vi TEXT,
                    ton_kho REAL DEFAULT 0
                )''')
    
    # --- 2. BẢNG HÀNG CHUẨN ---
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_san_pham (
                    id SERIAL PRIMARY KEY,
                    ma_sp TEXT UNIQUE,
                    ten_sp TEXT UNIQUE,
                    gia_dai_ly REAL DEFAULT 0,
                    gia_khach_le REAL DEFAULT 0,
                    gia_von REAL DEFAULT 0,
                    chi_phi_khac REAL DEFAULT 0
                )''')
    
    # --- 3. BẢNG HÀNG OME ---
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_san_pham_ome (
                    id SERIAL PRIMARY KEY,
                    ten_sp TEXT UNIQUE,
                    gia_ome REAL DEFAULT 0,
                    gia_von REAL DEFAULT 0,
                    chi_phi_khac REAL DEFAULT 0
                )''')
    
    # --- 4. ÉP THÊM CỘT LƯU DANH SÁCH ĐA VẬT TƯ ---
    cac_cot_moi = {
        "gia_von": "REAL DEFAULT 0",
        "chi_phi_khac": "REAL DEFAULT 0",
        "ds_nguyen_lieu": "TEXT"
    }
    for cot, kieu in cac_cot_moi.items():
        try: c.execute(f"ALTER TABLE public.dm_san_pham ADD COLUMN {cot} {kieu}")
        except: pass
        try: c.execute(f"ALTER TABLE public.dm_san_pham_ome ADD COLUMN {cot} {kieu}")
        except: pass

    conn.commit()
except Exception as e: pass

# Lấy danh sách nguyên vật liệu từ kho
try:
    df_nl = pd.read_sql("SELECT ten_nl FROM public.dm_nguyen_lieu", conn)
    danh_sach_nl = df_nl['ten_nl'].tolist() if not df_nl.empty else ["-- Kho đang trống --"]
except: danh_sach_nl = ["-- Kho đang trống --"]

# ==========================================
# GIAO DIỆN 4 TABS (ĐÃ ĐỔI TÊN BỎ CHỮ "CHUẨN")
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    "➕ Thêm SP", "📋 Danh Sách SP", 
    "➕ Thêm SP OME", "📋 Danh Sách SP OME"
])

# ------------------------------------------
# TAB 1: THÊM SẢN PHẨM
# ------------------------------------------
with tab1:
    st.subheader("Thêm Sản Phẩm & Khai Báo Định Mức")
    with st.form("form_them_sp", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            ma_sp = st.text_input("Mã sản phẩm (VD: SP01) (*)")
            ten_sp = st.text_input("Tên sản phẩm (*)")
            gia_von = st.number_input("Giá Vốn / Giá thành tổng (VNĐ)", min_value=0.0, step=1000.0)
        
        with col2:
            gia_dai_ly = st.number_input("Giá bán Đại lý (VNĐ)", min_value=0.0, step=1000.0)
            st.markdown("*(Giá Công ty tự động = Giá Đại Lý / 0.6 - Làm tròn hàng chục)*")
            chi_phi_khac_chuan = st.number_input("Chi phí khác (Tem, thùng, công...) (VNĐ)", min_value=0.0, step=1000.0)
            
        st.markdown("---")
        st.markdown("### 🧬 Thành Phần Nguyên Liệu Cấu Tạo (BOM)")
        st.info("💡 Bạn có thể bấm vào bảng bên dưới để thêm nhiều loại vật tư cho sản phẩm này (VD: Dòng 1 chọn ABS, Dòng 2 chọn Vít...). Bấm dấu + hoặc click đúp vào dòng trắng để thêm.")
        
        df_mau_nl = pd.DataFrame([{"vat_tu": None, "dinh_muc": 0.0}])
        edited_recipe = st.data_editor(
            df_mau_nl,
            num_rows="dynamic",
            column_config={
                "vat_tu": st.column_config.SelectboxColumn("Tên Vật Tư (Lấy từ Kho)", options=danh_sach_nl, required=True),
                "dinh_muc": st.column_config.NumberColumn("Định mức hao phí (g, cái...)", min_value=0.0)
            },
            hide_index=True,
            use_container_width=True
        )

        if st.form_submit_button("💾 Lưu Sản Phẩm & Định Mức", type="primary"):
            if not ma_sp.strip() or not ten_sp.strip():
                st.warning("⚠️ Vui lòng nhập Mã và Tên sản phẩm!")
            else:
                # ĐÃ SỬA: LÀM TRÒN HÀNG CHỤC (Dùng round(..., -1))
                gia_khach_le_calc = int(round(gia_dai_ly / 0.6, -1))
                
                valid_recipe = edited_recipe.dropna(subset=["vat_tu"])
                valid_recipe = valid_recipe[(valid_recipe["vat_tu"] != "-- Kho đang trống --") & (valid_recipe["dinh_muc"] > 0)]
                json_ds_nguyen_lieu = valid_recipe.to_json(orient="records") if not valid_recipe.empty else ""

                try:
                    c.execute("""INSERT INTO public.dm_san_pham 
                                 (ma_sp, ten_sp, gia_dai_ly, gia_khach_le, gia_von, chi_phi_khac, ds_nguyen_lieu) 
                                 VALUES (%s, %s, %s, %s, %s, %s, %s)""", 
                              (ma_sp.strip(), ten_sp.strip(), gia_dai_ly, gia_khach_le_calc, gia_von, chi_phi_khac_chuan, json_ds_nguyen_lieu))
                    st.success(f"✅ Đã thêm {ten_sp} cùng bộ định mức thành công!")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e: st.error(f"⚠️ Mã hoặc Tên này đã tồn tại!")

# ------------------------------------------
# TAB 2: QUẢN LÝ DANH SÁCH SP
# ------------------------------------------
with tab2:
    st.subheader("Cập Nhật & Sửa Chữa SP")
    try:
        df_sp = pd.read_sql("SELECT id, ma_sp, ten_sp, gia_dai_ly, gia_khach_le, gia_von, chi_phi_khac, ds_nguyen_lieu FROM public.dm_san_pham ORDER BY id DESC", conn)
        
        if not df_sp.empty:
            def format_recipe(json_str):
                if not json_str or pd.isna(json_str) or json_str == "": return "Không có"
                try:
                    items = json.loads(json_str)
                    return ", ".join([f"{item['vat_tu']} ({item['dinh_muc']})" for item in items])
                except: return "Lỗi hiển thị"

            df_sp['thanh_phan_hien_thi'] = df_sp['ds_nguyen_lieu'].apply(format_recipe)
            df_edit = df_sp.drop(columns=['ds_nguyen_lieu'])

            edited_sp = st.data_editor(
                df_edit, key="bang_sua_gia",
                column_config={
                    "id": None, 
                    "ma_sp": st.column_config.TextColumn("Mã SP", disabled=True),
                    "ten_sp": st.column_config.TextColumn("Tên Sản Phẩm", disabled=True),
                    "thanh_phan_hien_thi": st.column_config.TextColumn("Thành Phần Vật Tư", disabled=True),
                    "gia_dai_ly": st.column_config.NumberColumn("Giá Đại lý", format="%d"),
                    "gia_khach_le": st.column_config.NumberColumn("Giá Công ty", disabled=True, format="%d"),
                    "gia_von": st.column_config.NumberColumn("Giá Vốn", format="%d"),
                    "chi_phi_khac": st.column_config.NumberColumn("Chi phí khác", format="%d"),
                },
                use_container_width=True, hide_index=True
            )

            if st.button("💾 Lưu Bảng Thay Đổi", type="primary"):
                for index, row in edited_sp.iterrows():
                    # ĐÃ SỬA: LÀM TRÒN HÀNG CHỤC (Dùng round(..., -1))
                    gia_kl = int(round(float(row['gia_dai_ly']) / 0.6, -1))
                    c.execute("""UPDATE public.dm_san_pham 
                                 SET gia_dai_ly=%s, gia_khach_le=%s, gia_von=%s, chi_phi_khac=%s 
                                 WHERE id=%s""",
                              (float(row['gia_dai_ly']), gia_kl, float(row['gia_von']), float(row['chi_phi_khac']), int(row['id'])))
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
                        c.execute("DELETE FROM public.dm_san_pham WHERE ten_sp=%s", (sp_can_xoa,))
                        st.success(f"✅ Đã xóa: {sp_can_xoa}")
                        time.sleep(1)
                        st.rerun()
        else: st.info("Chưa có sản phẩm nào.")
    except Exception as e: st.error(f"Lỗi: {e}")

# ------------------------------------------
# TAB 3: THÊM SP OME (GIA CÔNG)
# ------------------------------------------
with tab3:
    st.subheader("Thêm Sản Phẩm OME & Khai Báo Định Mức")
    with st.form("form_them_ome", clear_on_submit=True):
        col_o1, col_o2 = st.columns(2)
        with col_o1:
            ten_sp_ome = st.text_input("Tên sản phẩm OME (*)")
            gia_ome = st.number_input("Giá bán OME (VNĐ)", min_value=0.0, step=1000.0)
        with col_o2:
            gia_von_ome = st.number_input("Giá Vốn / Giá thành (VNĐ)", min_value=0.0, step=1000.0)
            chi_phi_khac_ome = st.number_input("Chi phí khác (Tem, bao bì...) (VNĐ)", min_value=0.0, step=1000.0)

        st.markdown("---")
        st.markdown("### 🧬 Thành Phần Nguyên Liệu (Trừ Kho Wanchi)")
        st.info("Lưu ý: Chỉ điền các loại vật tư do xưởng Wanchi cung cấp. Vật tư khách mang đến không cần điền.")
        
        df_mau_nl_ome = pd.DataFrame([{"vat_tu": None, "dinh_muc": 0.0}])
        edited_recipe_ome = st.data_editor(
            df_mau_nl_ome,
            num_rows="dynamic",
            column_config={
                "vat_tu": st.column_config.SelectboxColumn("Tên Vật Tư (Lấy từ Kho)", options=danh_sach_nl, required=True),
                "dinh_muc": st.column_config.NumberColumn("Định mức hao phí (g, cái...)", min_value=0.0)
            },
            hide_index=True,
            use_container_width=True
        )

        if st.form_submit_button("💾 Lưu Sản Phẩm OME", type="primary"):
            if not ten_sp_ome.strip(): st.warning("⚠️ Vui lòng nhập Tên sản phẩm OME!")
            else:
                valid_recipe_ome = edited_recipe_ome.dropna(subset=["vat_tu"])
                valid_recipe_ome = valid_recipe_ome[(valid_recipe_ome["vat_tu"] != "-- Kho đang trống --") & (valid_recipe_ome["dinh_muc"] > 0)]
                json_ds_nguyen_lieu_ome = valid_recipe_ome.to_json(orient="records") if not valid_recipe_ome.empty else ""

                try:
                    c.execute("""INSERT INTO public.dm_san_pham_ome 
                                 (ten_sp, gia_ome, gia_von, chi_phi_khac, ds_nguyen_lieu) 
                                 VALUES (%s, %s, %s, %s, %s)""", 
                              (ten_sp_ome.strip(), gia_ome, gia_von_ome, chi_phi_khac_ome, json_ds_nguyen_lieu_ome))
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
        df_ome = pd.read_sql("SELECT id, ten_sp, gia_ome, gia_von, chi_phi_khac, ds_nguyen_lieu FROM public.dm_san_pham_ome ORDER BY id DESC", conn)
        if not df_ome.empty:
            def format_recipe(json_str):
                if not json_str or pd.isna(json_str) or json_str == "": return "Không có"
                try:
                    items = json.loads(json_str)
                    return ", ".join([f"{item['vat_tu']} ({item['dinh_muc']})" for item in items])
                except: return "Lỗi hiển thị"

            df_ome['thanh_phan_hien_thi'] = df_ome['ds_nguyen_lieu'].apply(format_recipe)
            df_edit_ome = df_ome.drop(columns=['ds_nguyen_lieu'])

            edited_ome = st.data_editor(
                df_edit_ome, key="bang_sua_ome",
                column_config={
                    "id": None, 
                    "ten_sp": st.column_config.TextColumn("Tên SP OME", disabled=True),
                    "thanh_phan_hien_thi": st.column_config.TextColumn("Thành Phần Vật Tư", disabled=True),
                    "gia_ome": st.column_config.NumberColumn("Giá bán OME", format="%d"),
                    "gia_von": st.column_config.NumberColumn("Giá Vốn", format="%d"),
                    "chi_phi_khac": st.column_config.NumberColumn("Chi phí khác", format="%d"),
                }, use_container_width=True, hide_index=True
            )

            if st.button("💾 Lưu Bảng OME", type="primary"):
                for index, row in edited_ome.iterrows():
                    c.execute("""UPDATE public.dm_san_pham_ome 
                                 SET gia_ome=%s, gia_von=%s, chi_phi_khac=%s 
                                 WHERE id=%s""",
                              (float(row['gia_ome']), float(row['gia_von']), float(row['chi_phi_khac']), int(row['id'])))
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
                        c.execute("DELETE FROM public.dm_san_pham_ome WHERE ten_sp=%s", (ome_can_xoa,))
                        st.success("✅ Đã xóa!")
                        time.sleep(1)
                        st.rerun()
        else: st.info("Chưa có hàng OME.")
    except: pass
