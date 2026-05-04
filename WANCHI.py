
import streamlit as st
from db_utils import get_connection, check_password # Gọi thêm hàm check_password

# 1. Cấu hình trang luôn phải nằm trên cùng
st.set_page_config(page_title="WANCHI Management", page_icon="🏭", layout="wide")

# 2. Đặt chốt bảo vệ ở đây!
if not check_password():
    st.stop() # Nếu mật khẩu sai, dừng luôn không chạy phần code bên dưới nữa

# 3. Phần code giao diện của bạn tiếp tục ở bên dưới như bình thường
st.title("🏭 Hệ Thống Quản Lý Sản Xuất & Bán Hàng WANCHI")
st.markdown("""
""")
