import psycopg2
import streamlit as st

# Hàm tạo kết nối cốt lõi (Lưu vào bộ nhớ đệm)
@st.cache_resource
def init_connection():
    DATABASE_URL = st.secrets["DATABASE_URL"]
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True 
    return conn

# Hàm thông minh: Kiểm tra tình trạng sống/chết của kết nối
def get_connection():
    try:
        conn = init_connection()
        
        # Kiểm tra: Nếu máy chủ Neon đã ngủ đông làm đứt kết nối (closed != 0)
        if conn.closed != 0:
            st.cache_resource.clear()  # Xóa bộ nhớ đệm chứa kết nối chết
            conn = init_connection()   # Đánh thức Neon và tạo kết nối mới
            
        return conn
    except Exception as e:
        st.error(f"Lỗi kết nối Cơ sở dữ liệu: {e}")
        st.stop()
