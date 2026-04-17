import psycopg2
import streamlit as st

# =========================================
# 1. HÀM KẾT NỐI DATABASE (Chống sập mạng)
# =========================================
@st.cache_resource
def init_connection():
    DATABASE_URL = st.secrets["DATABASE_URL"]
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True 
    return conn

def get_connection():
    conn = init_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT 1")
    except Exception:
        st.cache_resource.clear()
        conn = init_connection()
    return conn

# =========================================
# 2. HÀM KIỂM TRA MẬT KHẨU ĐĂNG NHẬP
# =========================================
def check_password():
    """Trả về True nếu người dùng đã nhập đúng mật khẩu."""
    
    def password_entered():
        """Kiểm tra mật khẩu người dùng nhập vào."""
        # So sánh với mật khẩu cất trong két sắt
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Xóa mật khẩu khỏi bộ nhớ để an toàn
        else:
            st.session_state["password_correct"] = False

    # Nếu đã đăng nhập đúng từ trước, cho phép đi qua luôn
    if st.session_state.get("password_correct", False):
        return True

    # Nếu chưa đăng nhập, hiển thị form yêu cầu nhập mật khẩu
    st.markdown("<h2 style='text-align: center;'>🔒 HỆ THỐNG QUẢN TRỊ WANCHI</h2>", unsafe_allow_html=True)
    st.text_input("Vui lòng nhập mật khẩu để truy cập phần mềm:", type="password", on_change=password_entered, key="password")
    
    # Báo lỗi nếu nhập sai
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("❌ Mật khẩu không chính xác. Vui lòng thử lại!")
    
    return False
