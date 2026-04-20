import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from db_utils import get_connection, check_password

st.set_page_config(page_title="Dashboard Quản Trị", page_icon="📊", layout="wide")

# ==========================================
# 🔑 CẤU HÌNH MẬT KHẨU GIÁM ĐỐC (ĐỔI TẠI ĐÂY)
# ==========================================
MAT_KHAU_GIAM_DOC = "68688" 

# ==========================================
# Ổ KHÓA BẢO VỆ 1 & 2 (Quyền truy cập chung)
# ==========================================
role = check_password()
if not role: st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Báo cáo tài chính là dữ liệu tuyệt mật của Quản lý.")
    st.stop()

# ==========================================
# Ổ KHÓA BẢO VỆ 3 (KÉT SẮT TÀI CHÍNH)
# ==========================================
if 'dashboard_unlocked' not in st.session_state:
    st.session_state.dashboard_unlocked = False

if not st.session_state.dashboard_unlocked:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col_khoa1, col_khoa2, col_khoa3 = st.columns([1, 2, 1])
    with col_khoa2:
        st.warning("🔒 **BẢO MẬT CẤP CAO:** Vui lòng nhập Mã PIN Giám Đốc để xem Báo cáo tài chính.")
        with st.form("form_mat_khau"):
            pin_input = st.text_input("Mã PIN / Mật khẩu:", type="password")
            if st.form_submit_button("🔓 Mở Khóa Két Sắt", type="primary", use_container_width=True):
                if pin_input == MAT_KHAU_GIAM_DOC:
                    st.session_state.dashboard_unlocked = True
                    st.rerun()
                else:
                    st.error("❌ Mã PIN không chính xác!")
    st.stop() # Chặn đứng mọi đoạn code bên dưới nếu chưa mở khóa

# --- HIỂN THỊ NÚT KHÓA LẠI KHI ĐÃ MỞ KÉT ---
col_t1, col_t2 = st.columns([5, 1])
with col_t1: st.header("📊 Báo Cáo Quản Trị & Hiệu Quả Kinh Doanh WANCHI")
with col_t2:
    st.write("")
    if st.button("🔒 Khóa Màn Hình", use_container_width=True):
        st.session_state.dashboard_unlocked = False
        st.rerun()

conn = get_connection()

# ==========================================
# BƯỚC 1: LẤY DỮ LIỆU TỪ CÁC KHO
# ==========================================
try:
    df_don_hang = pd.read_sql("SELECT ngay_tao, tong_tien, chi_tiet FROM public.don_hang", conn)
    
    df_sp = pd.read_sql("SELECT ten_sp, gia_von FROM public.dm_san_pham", conn)
    df_ome = pd.read_sql("SELECT ten_sp, gia_von FROM public.dm_san_pham_ome", conn)
    
    df_all_sp = pd.concat([df_sp, df_ome])
    dict_gia_von = dict(zip(df_all_sp['ten_sp'], df_all_sp['gia_von']))

except Exception as e:
    st.error(f"Lỗi kết nối cơ sở dữ liệu: {e}")
    st.stop()

# ==========================================
# BƯỚC 2: CỖ MÁY "RÃ ĐÔNG" JSON & TÍNH LỢI NHUẬN
# ==========================================
if not df_don_hang.empty:
    danh_sach_phan_tich = []
    
    for _, row in df_don_hang.iterrows():
        ngay_thang = str(row['ngay_tao'])[:10] if pd.notna(row['ngay_tao']) else "Không rõ"
        try:
            if pd.notna(row['chi_tiet']) and str(row['chi_tiet']).strip() != "":
                items = json.loads(row['chi_tiet'])
                for item in items:
                    ten_sp = item.get('Tên Sản Phẩm', item.get('Tên Sản Phẩm OME', 'Sản phẩm khác'))
                    so_luong = float(item.get('Số Lượng', 0))
                    doanh_thu = float(item.get('Thành Tiền', 0))
                    
                    gia_von_1_cai = float(dict_gia_von.get(ten_sp, 0.0))
                    tong_gia_von = gia_von_1_cai * so_luong
                    loi_nhuan = doanh_thu - tong_gia_von
                    
                    danh_sach_phan_tich.append({
                        "Ngày": ngay_thang,
                        "Sản Phẩm": ten_sp,
                        "Số Lượng": so_luong,
                        "Giá Vốn": tong_gia_von,
                        "Doanh Thu": doanh_thu,
                        "Lợi Nhuận": loi_nhuan
                    })
        except: pass
    
    df_pt = pd.DataFrame(danh_sach_phan_tich)
    
    if df_pt.empty:
        st.info("Chưa có dữ liệu bán hàng chi tiết để phân tích.")
        st.stop()

    df_pt['Ngày'] = pd.to_datetime(df_pt['Ngày'], format="%d/%m/%Y", errors='coerce')

    # ==========================================
    # BƯỚC 3: TÍNH TOÁN KPI TỔNG QUAN
    # ==========================================
    tong_dt = df_pt['Doanh Thu'].sum()
    tong_gv = df_pt['Giá Vốn'].sum()
    tong_ln = df_pt['Lợi Nhuận'].sum()
    tong_sp = df_pt['Số Lượng'].sum()
    ty_suat_ln = (tong_ln / tong_dt * 100) if tong_dt > 0 else 0

    st.markdown("### 🏆 CHỈ SỐ TÀI CHÍNH TỔNG QUAN")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Tổng Doanh Thu", f"{tong_dt:,.0f} đ")
    col2.metric("📦 Giá Vốn Hàng Bán", f"{tong_gv:,.0f} đ")
    col3.metric("📈 Lợi Nhuận Ròng", f"{tong_ln:,.0f} đ")
    col4.metric("🎯 Biên Lợi Nhuận", f"{ty_suat_ln:.1f} %")

    st.markdown("---")

    # ==========================================
    # BƯỚC 4: VẼ BIỂU ĐỒ TRỰC QUAN (PLOTLY)
    # ==========================================
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("#### 📈 Xu Hướng Doanh Thu & Lợi Nhuận")
        df_time = df_pt.groupby('Ngày')[['Doanh Thu', 'Lợi Nhuận']].sum().reset_index()
        df_time = df_time.sort_values('Ngày')
        
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=df_time['Ngày'], y=df_time['Doanh Thu'], mode='lines+markers', name='Doanh Thu', line=dict(color='#1f77b4', width=3)))
        fig1.add_trace(go.Scatter(x=df_time['Ngày'], y=df_time['Lợi Nhuận'], mode='lines+markers', name='Lợi Nhuận', line=dict(color='#2ca02c', width=3)))
        fig1.update_layout(xaxis_title="Thời gian", yaxis_title="VNĐ", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig1, use_container_width=True)

    with col_chart2:
        st.markdown("#### 🥧 Cơ Cấu Chi Phí & Lợi Nhuận")
        df_pie = pd.DataFrame({
            'Hạng mục': ['Giá Vốn (Chi phí SX)', 'Lợi Nhuận Ròng'],
            'Giá trị': [tong_gv, tong_ln]
        })
        df_pie['Giá trị'] = df_pie['Giá trị'].apply(lambda x: x if x > 0 else 0) 
        
        fig2 = px.pie(df_pie, values='Giá trị', names='Hạng mục', hole=0.4,
                      color_discrete_sequence=['#ff9999', '#66b3ff'])
        fig2.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    col_chart3, col_chart4 = st.columns(2)

    with col_chart3:
        st.markdown("#### 🏆 Top 5 Sản Phẩm Bán Chạy Nhất (Số lượng)")
        df_sp_sl = df_pt.groupby('Sản Phẩm')['Số Lượng'].sum().reset_index().sort_values('Số Lượng', ascending=True).tail(5)
        fig3 = px.bar(df_sp_sl, x='Số Lượng', y='Sản Phẩm', orientation='h', text='Số Lượng',
                      color='Số Lượng', color_continuous_scale='Oranges')
        fig3.update_traces(texttemplate='%{text:,.0f}', textposition='inside')
        fig3.update_layout(coloraxis_showscale=False, xaxis_title="Số lượng (Cái)", yaxis_title="")
        st.plotly_chart(fig3, use_container_width=True)

    with col_chart4:
        st.markdown("#### 💎 Top 5 Sản Phẩm Sinh Lời Nhất (VNĐ)")
        df_sp_ln = df_pt.groupby('Sản Phẩm')['Lợi Nhuận'].sum().reset_index().sort_values('Lợi Nhuận', ascending=True).tail(5)
        fig4 = px.bar(df_sp_ln, x='Lợi Nhuận', y='Sản Phẩm', orientation='h', text='Lợi Nhuận',
                      color='Lợi Nhuận', color_continuous_scale='Greens')
        fig4.update_traces(texttemplate='%{text:,.0f} đ', textposition='inside')
        fig4.update_layout(coloraxis_showscale=False, xaxis_title="Lợi nhuận (VNĐ)", yaxis_title="")
        st.plotly_chart(fig4, use_container_width=True)

else:
    st.info("📊 Hệ thống chưa ghi nhận đơn hàng nào. Hãy lên đơn để xem báo cáo tài chính nhé!")
