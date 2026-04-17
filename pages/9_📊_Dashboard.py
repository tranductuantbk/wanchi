import streamlit as st
import pandas as pd
import plotly.express as px
from db_utils import get_connection

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
st.header("📊 Báo Cáo Quản Trị WANCHI")

# Kết nối database thông qua cấu hình Neon (Đã chuẩn hóa Cloud)
conn = get_connection()
df = pd.read_sql("SELECT * FROM don_hang", conn)

if not df.empty:
    # Chuyển đổi định dạng ngày tháng để vẽ biểu đồ chính xác
    df['ngay'] = pd.to_datetime(df['ngay'])

    # 1. Thẻ KPI
    tong_dt = df['doanh_thu'].sum()
    tong_ln = df['loi_nhuan'].sum()
    tong_sp = df['so_luong'].sum()
    ty_suat = (tong_ln / tong_dt * 100) if tong_dt > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tổng Doanh Thu", f"{tong_dt:,.0f} đ")
    col2.metric("Tổng Lợi Nhuận", f"{tong_ln:,.0f} đ")
    col3.metric("Sản Lượng Đã Bán", f"{tong_sp:,.0f}")
    col4.metric("Biên Lợi Nhuận", f"{ty_suat:.1f} %")

    st.markdown("---")

    # 2. Biểu đồ trực quan
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.subheader("📈 Xu hướng Doanh thu")
        df_time = df.groupby('ngay')['doanh_thu'].sum().reset_index()
        fig1 = px.line(df_time, x='ngay', y='doanh_thu', markers=True, 
                       labels={'ngay': 'Ngày', 'doanh_thu': 'Doanh thu (VNĐ)'})
        st.plotly_chart(fig1, use_container_width=True)

    with col_chart2:
        st.subheader("🏆 Top Sản phẩm Sinh lời")
        df_sp = df.groupby('ten_sp')['loi_nhuan'].sum().reset_index().sort_values('loi_nhuan', ascending=True).tail(5)
        fig2 = px.bar(df_sp, x='loi_nhuan', y='ten_sp', orientation='h', 
                      labels={'loi_nhuan': 'Lợi nhuận (VNĐ)', 'ten_sp': 'Sản phẩm'},
                      color='loi_nhuan', color_continuous_scale='Blues')
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    
    # Biểu đồ cơ cấu chi phí
    st.subheader("🥧 Cơ cấu Giá vốn & Lợi nhuận")
    tong_nvl = df['tong_nvl'].sum()
    tong_cong = df['tong_cong_ep'].sum()
    
    df_pie = pd.DataFrame({
        'Hạng mục': ['Chi phí NVL', 'Chi phí Công ép', 'Lợi nhuận ròng'],
        'Giá trị': [tong_nvl, tong_cong, tong_ln]
    })
    fig3 = px.pie(df_pie, values='Giá trị', names='Hạng mục', hole=0.4,
                  color_discrete_sequence=['#ff9999','#66b3ff','#99ff99'])
    st.plotly_chart(fig3, use_container_width=True)

else:
    st.info("Chưa có đủ dữ liệu để vẽ biểu đồ. Hãy nhập thêm đơn hàng!")