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
        conn.cursor().execute("SELECT 1")
    except Exception:
        st.cache_resource.clear()
        conn = init_connection()
    return conn

def check_password():
    def password_entered():
        # Kiểm tra xem nhập mật khẩu của ai
        if st.session_state["password"] == st.secrets.get("APP_PASSWORD"):
            st.session_state["role"] = "admin"
        elif st.session_state["password"] == st.secrets.get("EMP_PASSWORD", "nhanvien123"):
            st.session_state["role"] = "employee"
        else:
            st.session_state["role"] = None
        del st.session_state["password"]

    # Nếu đã đăng nhập thành công
    if st.session_state.get("role"):
        role = st.session_state["role"]
        # CHIÊU THỨC GIẤU MENU CHO NHÂN VIÊN
        if role == "employee":
            st.markdown("""
                <style>
                    [data-testid="stSidebar"] { display: none !important; }
                    [data-testid="collapsedControl"] { display: none !important; }
                </style>
            """, unsafe_allow_html=True)
        return role

    st.markdown("<h2 style='text-align: center;'>🔒 CỔNG ĐĂNG NHẬP WANCHI</h2>", unsafe_allow_html=True)
    st.text_input("Nhập mật khẩu truy cập:", type="password", on_change=password_entered, key="password")
    
    if "role" in st.session_state and st.session_state["role"] is None:
        st.error("❌ Mật khẩu không chính xác!")
    return None
