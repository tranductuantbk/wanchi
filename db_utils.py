import psycopg2
import streamlit as st

# ==========================================
# 🔑 CẤU HÌNH MẬT KHẨU TOÀN HỆ THỐNG
# ==========================================
MAT_KHAU_HE_THONG = "wanchi9187"

# ==========================================
# KẾT NỐI DATABASE
# ==========================================
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

# ==========================================
# HÀM KIỂM TRA MẬT KHẨU XUYÊN SUỐT CÁC TRANG
# ==========================================
def check_password():
    """Returns `True` if the user had a correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == MAT_KHAU_HE_THONG:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # xóa mật khẩu khỏi session state để bảo mật
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # Lần chạy đầu tiên, hiển thị ô nhập mật khẩu
        st.text_input(
            "🔑 Nhập mật khẩu hệ thống", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Mật khẩu sai, hiển thị ô nhập lại
        st.text_input(
            "🔑 Nhập mật khẩu hệ thống", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Mật khẩu không đúng!")
        return False
    else:
        # Đã đăng nhập thành công, thiết lập biến cờ
        st.session_state["logged_in"] = True
        return True
