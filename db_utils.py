import psycopg2
import streamlit as st

@st.cache_resource
def init_connection():
    DATABASE_URL = st.secrets["DATABASE_URL"]
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True 
    return conn

def get_connection():
    conn = init_connection()
    try:
        # "Ping" thử máy chủ bằng một câu lệnh cực nhẹ
        c = conn.cursor()
        c.execute("SELECT 1")
    except Exception:
        # Nếu máy chủ không trả lời (bị ngủ đông/ngắt mạng), lập tức xóa bộ nhớ và gọi lại
        st.cache_resource.clear()
        conn = init_connection()
    return conn
