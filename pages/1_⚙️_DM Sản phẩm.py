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
    
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_nguyen_lieu (
                    id SERIAL PRIMARY KEY,
                    ma_nl TEXT UNIQUE,
                    ten_nl TEXT UNIQUE,
                    don_vi TEXT,
                    ton_kho REAL DEFAULT 0
                )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_san_pham (
                    id SERIAL PRIMARY KEY,
                    ma_sp TEXT UNIQUE,
                    ten_sp TEXT UNIQUE,
                    gia_dai_ly REAL DEFAULT 0,
                    gia_khach_le REAL DEFAULT 0,
                    gia_von REAL DEFAULT 0,
                    chi_phi_khac REAL DEFAULT 0
                )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS public.dm_san_pham_ome (
                    id SERIAL PRIMARY KEY,
                    ten_sp TEXT UNIQUE,
                    gia_ome REAL DEFAULT 0,
                    gia_von REAL DEFAULT 0,
                    chi_phi_khac REAL DEFAULT 0
                )''')
    
    cac_cot_moi = {"gia_von": "REAL DEFAULT 0", "chi_phi_khac": "REAL DEFAULT 0", "ds_nguyen_lieu": "TEXT"}
    for cot, kieu in cac_cot_moi.items():
        try: c.execute(f"ALTER TABLE public.dm_san_pham ADD COLUMN {cot} {kieu}")
        except: pass
        try: c.execute(f"ALTER TABLE public.dm_san_pham_ome ADD COLUMN {cot} {kieu}")
        except: pass

    conn.commit()
except Exception as e: 
    conn.rollback()

# Lấy danh sách nguyên vật liệu từ kho
try:
    df_nl = pd.read_sql("SELECT ten_nl FROM public.dm_nguyen_lieu", conn)
    danh_sach_nl = df_nl['ten_nl'].tolist() if not df_nl.empty else ["-- Kho đang trống --"]
except: danh_sach_nl = ["-- Kho đang trống --"]

# ==========================================
# GIAO DIỆN 4 TABS
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    "➕ Thêm SP", "📋 Danh Sách SP", 
    "➕ Thêm SP OME", "📋 Danh Sách SP OME"
])

# ------------------------------------------
# TAB 1: THÊM SẢN PHẨM & CẬP NHẬT
# ------------------------------------------
with tab1:
    edit_data = st.session_state.get('edit_sp_data', None)
    is_edit = edit_data is not None

    if is_edit:
        st.warning(f"🛠️ **CHẾ ĐỘ SỬA CHỮA TOÀN DIỆN:** Đang chỉnh sửa sản phẩm **{edit_data['ten_sp']}**.")
        if st.button("❌ Hủy chỉnh sửa (Quay về Thêm mới)"):
            st.session_state['edit_sp_data'] = None
            st.rerun()
    else:
        st.subheader("Thêm Sản Phẩm & Khai Báo Định Mức")

    with st.form("form_them_sp", clear_on_submit=not is_edit):
        col1, col2 = st.columns(2)
        with col1:
            ma_sp = st.text_input("Mã sản phẩm (VD: SP01) (*)", value=edit_data['ma_sp'] if is_edit else "")
            ten_sp = st.text_input("Tên sản phẩm (*)", value=edit_data['ten_sp'] if is_edit else "")
            gia_von = st.number_input("Giá Vốn / Giá thành tổng (VNĐ)", min_value=0.0, step=1000.0, value=float(edit_data['gia_von']) if is_edit else 0.0)
        
        with col2:
            gia_dai_ly = st.number_input("Giá bán Đại lý (VNĐ)", min_value=0.0, step=1000.0, value=float(edit_data['gia_dai_ly']) if is_edit else 0.0)
            st.markdown("*(Giá Công ty tự động = Giá Đại Lý / 0.55 - Làm tròn hàng chục)*")
            
        st.markdown("---")
        st.markdown("### 🧬 Thành Phần Nguyên Liệu Cấu Tạo (BOM)")
        st.info("💡 Bấm vào bảng để khai báo lượng vật tư cấu thành sản phẩm này (Nhựa, vít, thùng...).")
        
        if is_edit and edit_data.get('ds_nguyen_lieu'):
            try:
                bom_items = json.loads(edit_data['ds_nguyen_lieu'])
                df_mau_nl = pd.DataFrame(bom_items) if bom_items else pd.DataFrame([{"vat_tu": None, "dinh_muc": 0.0}])
            except: df_mau_nl = pd.DataFrame([{"vat_tu": None, "dinh_muc": 0.0}])
        else:
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

        btn_label = "🔄 CẬP NHẬT SẢN PHẨM NÀY" if is_edit else "💾 Lưu Sản Phẩm & Định Mức"
        
        if st.form_submit_button(btn_label, type="primary"):
            if not ma_sp.strip() or not ten_sp.strip():
                st.warning("⚠️ Vui lòng nhập Mã và Tên sản phẩm!")
            else:
                gia_khach_le_calc = int(round(gia_dai_ly / 0.55, -1))
                
                valid_recipe = edited_recipe.dropna(subset=["vat_tu"])
                valid_recipe = valid_recipe[(valid_recipe["vat_tu"] != "-- Kho đang trống --") & (valid_recipe["dinh_muc"] > 0)]
                json_ds_nguyen_lieu = valid_recipe.to_json(orient="records") if not valid_recipe.empty else ""

                if is_edit:
                    try:
                        c.execute("""UPDATE public.dm_san_pham 
                                     SET ma_sp=%s, ten_sp=%s, gia_dai_ly=%s, gia_khach_le=%s, gia_von=%s, ds_nguyen_lieu=%s 
                                     WHERE id=%s""", 
                                  (ma_sp.strip(), ten_sp.strip(), gia_dai_ly, gia_khach_le_calc, gia_von, json_ds_nguyen_lieu, edit_data['id']))
                        conn.commit()
                        st.success(f"✅ Đã CẬP NHẬT '{ten_sp}' thành công!")
                        st.session_state['edit_sp_data'] = None 
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e: 
                        conn.rollback()
                        st.error(f"⚠️ Mã hoặc Tên bị trùng lặp!")
                else:
                    try:
                        c.execute("""INSERT INTO public.dm_san_pham 
                                     (ma_sp, ten_sp, gia_dai_ly, gia_khach_le, gia_von, chi_phi_khac, ds_nguyen_lieu) 
                                     VALUES (%s, %s, %s, %s, %s, %s, %s)""", 
                                  (ma_sp.strip(), ten_sp.strip(), gia_dai_ly, gia_khach_le_calc, gia_von, 0, json_ds_nguyen_lieu))
                        conn.commit()
                        st.success(f"✅ Đã thêm {ten_sp} cùng bộ định mức thành công!")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e: 
                        conn.rollback()
                        st.error(f"⚠️ Mã hoặc Tên này đã tồn tại!")

# ------------------------------------------
# TAB 2: QUẢN LÝ DANH SÁCH SP
# ------------------------------------------
with tab2:
    try:
        df_sp = pd.read_sql("SELECT id, ma_sp, ten_sp, gia_dai_ly, gia_khach_le, gia_von, chi_phi_khac, ds_nguyen_lieu FROM public.dm_san_pham ORDER BY id DESC", conn)
        
        st.subheader("✏️ Chọn Sản Phẩm Để Sửa Chữa")
        if not df_sp.empty:
            col_s1, col_s2 = st.columns([3, 1])
            with col_s1:
                sp_sua_chon = st.selectbox("Chọn Sản phẩm để nạp vào Form chỉnh sửa:", ["-- Chọn --"] + df_sp['ten_sp'].tolist(), key="chon_sp_sua")
            with col_s2:
                st.write(""); st.write("")
                if st.button("🛠️ Nạp dữ liệu qua Tab Thêm SP", type="primary", use_container_width=True):
                    if sp_sua_chon != "-- Chọn --":
                        st.session_state['edit_sp_data'] = df_sp[df_sp['ten_sp'] == sp_sua_chon].iloc[0].to_dict()
                        st.success("✅ Đã nạp thành công! Hãy bấm sang Tab '➕ Thêm SP' để sửa nhé.")
                        time.sleep(1.5)
                        st.rerun()
        
        st.markdown("---")
        st.subheader("📄 Danh Sách Sản Phẩm")
        if not df_sp.empty:
            def format_recipe(json_str):
                if not json_str or pd.isna(json_str) or json_str == "": return "Không có"
                try:
                    items = json.loads(json_str)
                    return ", ".join([f"{item['vat_tu']} ({item['dinh_muc']})" for item in items])
                except: return "Lỗi hiển thị"

            df_sp['thanh_phan_hien_thi'] = df_sp['ds_nguyen_lieu'].apply(format_recipe)
            df_hien_thi = df_sp.drop(columns=['ds_nguyen_lieu', 'chi_phi_khac'])

            # ĐÃ ĐỔI: Sử dụng dataframe chỉ xem thay vì data_editor
            st.dataframe(
                df_hien_thi,
                column_config={
                    "id": None, 
                    "ma_sp": st.column_config.TextColumn("Mã SP"),
                    "ten_sp": st.column_config.TextColumn("Tên Sản Phẩm"),
                    "thanh_phan_hien_thi": st.column_config.TextColumn("Định mức Vật Tư"),
                    "gia_dai_ly": st.column_config.NumberColumn("Giá Đại lý", format="%d"),
                    "gia_khach_le": st.column_config.NumberColumn("Giá Công ty", format="%d"),
                    "gia_von": st.column_config.NumberColumn("Giá Vốn", format="%d"),
                },
                use_container_width=True, hide_index=True
            )

            st.markdown("---")
            st.subheader("🗑️ Xóa Sản Phẩm")
            col_xoa1, col_xoa2 = st.columns([3, 1])
            with col_xoa1: sp_can_xoa = st.selectbox("Chọn SP cần xóa:", ["-- Chọn --"] + df_sp['ten_sp'].tolist())
            with col_xoa2:
                st.write(""); st.write("")
                if st.button("🚨 Xóa Vĩnh Viễn", type="primary", use_container_width=True):
                    if sp_can_xoa != "-- Chọn --":
                        c.execute("DELETE FROM public.dm_san_pham WHERE ten_sp=%s", (sp_can_xoa,))
                        conn.commit()
                        st.success(f"✅ Đã xóa: {sp_can_xoa}")
                        time.sleep(1)
                        st.rerun()
        else: st.info("Chưa có sản phẩm nào.")
    except Exception as e: st.error(f"Lỗi: {e}")

# ------------------------------------------
# TAB 3: THÊM SP OME & CẬP NHẬT
# ------------------------------------------
with tab3:
    edit_ome = st.session_state.get('edit_ome_data', None)
    is_edit_ome = edit_ome is not None

    if is_edit_ome:
        st.warning(f"🛠️ **CHẾ ĐỘ SỬA CHỮA OME:** Đang chỉnh sửa **{edit_ome['ten_sp']}**.")
        if st.button("❌ Hủy chỉnh sửa OME (Quay về Thêm mới)"):
            st.session_state['edit_ome_data'] = None
            st.rerun()
    else:
        st.subheader("Thêm Sản Phẩm OME & Khai Báo Định Mức")

    with st.form("form_them_ome", clear_on_submit=not is_edit_ome):
        col_o1, col_o2 = st.columns(2)
        with col_o1:
            ten_sp_ome = st.text_input("Tên sản phẩm OME (*)", value=edit_ome['ten_sp'] if is_edit_ome else "")
            gia_ome = st.number_input("Giá bán OME (VNĐ)", min_value=0.0, step=1000.0, value=float(edit_ome['gia_ome']) if is_edit_ome else 0.0)
        with col_o2:
            gia_von_ome = st.number_input("Giá Vốn / Giá thành (VNĐ)", min_value=0.0, step=1000.0, value=float(edit_ome['gia_von']) if is_edit_ome else 0.0)

        st.markdown("---")
        st.markdown("### 🧬 Thành Phần Nguyên Liệu (Trừ Kho Wanchi)")
        st.info("Lưu ý: Chỉ điền các loại vật tư do xưởng Wanchi cung cấp. Vật tư khách mang đến không cần điền.")
        
        if is_edit_ome and edit_ome.get('ds_nguyen_lieu'):
            try:
                bom_items_ome = json.loads(edit_ome['ds_nguyen_lieu'])
                df_mau_nl_ome = pd.DataFrame(bom_items_ome) if bom_items_ome else pd.DataFrame([{"vat_tu": None, "dinh_muc": 0.0}])
            except: df_mau_nl_ome = pd.DataFrame([{"vat_tu": None, "dinh_muc": 0.0}])
        else:
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

        btn_label_ome = "🔄 CẬP NHẬT SP OME NÀY" if is_edit_ome else "💾 Lưu Sản Phẩm OME"
        
        if st.form_submit_button(btn_label_ome, type="primary"):
            if not ten_sp_ome.strip(): st.warning("⚠️ Vui lòng nhập Tên sản phẩm OME!")
            else:
                valid_recipe_ome = edited_recipe_ome.dropna(subset=["vat_tu"])
                valid_recipe_ome = valid_recipe_ome[(valid_recipe_ome["vat_tu"] != "-- Kho đang trống --") & (valid_recipe_ome["dinh_muc"] > 0)]
                json_ds_nguyen_lieu_ome = valid_recipe_ome.to_json(orient="records") if not valid_recipe_ome.empty else ""

                if is_edit_ome:
                    try:
                        c.execute("""UPDATE public.dm_san_pham_ome 
                                     SET ten_sp=%s, gia_ome=%s, gia_von=%s, ds_nguyen_lieu=%s 
                                     WHERE id=%s""", 
                                  (ten_sp_ome.strip(), gia_ome, gia_von_ome, json_ds_nguyen_lieu_ome, edit_ome['id']))
                        conn.commit()
                        st.success(f"✅ Đã CẬP NHẬT '{ten_sp_ome}' thành công!")
                        st.session_state['edit_ome_data'] = None
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e: 
                        conn.rollback()
                        st.error(f"⚠️ Tên bị trùng lặp!")
                else:
                    try:
                        c.execute("""INSERT INTO public.dm_san_pham_ome 
                                     (ten_sp, gia_ome, gia_von, chi_phi_khac, ds_nguyen_lieu) 
                                     VALUES (%s, %s, %s, %s, %s)""", 
                                  (ten_sp_ome.strip(), gia_ome, gia_von_ome, 0, json_ds_nguyen_lieu_ome))
                        conn.commit()
                        st.success(f"✅ Đã thêm OME: {ten_sp_ome}!")
                        time.sleep(1)
                        st.rerun()
                    except: 
                        conn.rollback()
                        st.error("⚠️ Tên OME này đã tồn tại!")

# ------------------------------------------
# TAB 4: DS SP OME
# ------------------------------------------
with tab4:
    try:
        df_ome = pd.read_sql("SELECT id, ten_sp, gia_ome, gia_von, chi_phi_khac, ds_nguyen_lieu FROM public.dm_san_pham_ome ORDER BY id DESC", conn)
        
        st.subheader("✏️ Chọn Sản Phẩm OME Để Sửa Chữa")
        if not df_ome.empty:
            col_so1, col_so2 = st.columns([3, 1])
            with col_so1:
                ome_sua_chon = st.selectbox("Chọn SP OME cần sửa toàn diện:", ["-- Chọn --"] + df_ome['ten_sp'].tolist(), key="chon_sua_ome")
            with col_so2:
                st.write(""); st.write("")
                if st.button("🛠️ Nạp dữ liệu qua Tab Thêm OME", type="primary", use_container_width=True):
                    if ome_sua_chon != "-- Chọn --":
                        st.session_state['edit_ome_data'] = df_ome[df_ome['ten_sp'] == ome_sua_chon].iloc[0].to_dict()
                        st.success("✅ Đã nạp thành công! Hãy bấm sang Tab '➕ Thêm SP OME' để sửa nhé.")
                        time.sleep(1.5)
                        st.rerun()

        st.markdown("---")
        st.subheader("📄 Danh Sách Sản Phẩm OME")
        if not df_ome.empty:
            def format_recipe(json_str):
                if not json_str or pd.isna(json_str) or json_str == "": return "Không có"
                try:
                    items = json.loads(json_str)
                    return ", ".join([f"{item['vat_tu']} ({item['dinh_muc']})" for item in items])
                except: return "Lỗi hiển thị"

            df_ome['thanh_phan_hien_thi'] = df_ome['ds_nguyen_lieu'].apply(format_recipe)
            df_hien_thi_ome = df_ome.drop(columns=['ds_nguyen_lieu', 'chi_phi_khac'])

            # ĐÃ ĐỔI: Sử dụng dataframe chỉ xem thay vì data_editor
            st.dataframe(
                df_hien_thi_ome,
                column_config={
                    "id": None, 
                    "ten_sp": st.column_config.TextColumn("Tên SP OME"),
                    "thanh_phan_hien_thi": st.column_config.TextColumn("Định mức Vật Tư"),
                    "gia_ome": st.column_config.NumberColumn("Giá bán OME", format="%d"),
                    "gia_von": st.column_config.NumberColumn("Giá Vốn", format="%d"),
                }, use_container_width=True, hide_index=True
            )
                
            st.markdown("---")
            st.subheader("🗑️ Xóa Sản Phẩm OME")
            col_oxoa1, col_oxoa2 = st.columns([3, 1])
            with col_oxoa1: ome_can_xoa = st.selectbox("Chọn OME cần xóa:", ["-- Chọn --"] + df_ome['ten_sp'].tolist())
            with col_oxoa2:
                st.write(""); st.write("")
                if st.button("🚨 Xóa Hàng OME", type="primary", use_container_width=True):
                    if ome_can_xoa != "-- Chọn --":
                        c.execute("DELETE FROM public.dm_san_pham_ome WHERE ten_sp=%s", (ome_can_xoa,))
                        conn.commit()
                        st.success("✅ Đã xóa!")
                        time.sleep(1)
                        st.rerun()
        else: st.info("Chưa có hàng OME.")
    except Exception as e: pass
