import psycopg2
import streamlit as st

# Câu thần chú giúp lưu trữ kết nối, tăng tốc độ App và chống quá tải máy chủ
@st.cache_resource
def get_connection():
    """
    Hàm kết nối đến cơ sở dữ liệu PostgreSQL trên Neon.tech.
    Sử dụng st.secrets để bảo mật mật khẩu khi đưa lên Cloud.
    """
    try:
        # Lấy chìa khóa từ hệ thống bảo mật của Streamlit
        DATABASE_URL = st.secrets["DATABASE_URL"]
        
        conn = psycopg2.connect(DATABASE_URL)
        
        # PostgreSQL cần bật chế độ tự động lưu (autocommit)
        # để các lệnh CREATE TABLE hoặc INSERT chạy mượt mà
        conn.autocommit = True 
        return conn
    except Exception as e:
        st.error(f"Lỗi kết nối Cơ sở dữ liệu: {e}")
        st.stop()