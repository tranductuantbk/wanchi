
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
Chào mừng đến với hệ thống quản lý nội bộ...
# (Giữ nguyên toàn bộ code cũ ở dưới đây)
""")
# Cấu hình trang hiển thị toàn màn hình
st.set_page_config(page_title="WANCHI Management", page_icon="🏭", layout="wide")

st.title("🏭 Hệ Thống Quản Lý Sản Xuất & Bán Hàng WANCHI")
st.markdown("""
Chào mừng đến với hệ thống quản lý doanh nghiệp. Toàn bộ dữ liệu của bạn giờ đây được lưu trữ an toàn trên **Đám mây PostgreSQL (Neon Cloud)** và xử lý tốc độ cao, cho phép truy cập mượt mà từ bất kỳ thiết bị nào!

Vui lòng chọn các module ở thanh menu bên trái để bắt đầu:
* **📝 1. Nhập Liệu:** Lên đơn hàng mới, hệ thống sẽ tự động tính toán giá vốn và lợi nhuận.
* **🗂️ 2. Quản Lý:** Xem lại danh sách đơn hàng, lọc tìm kiếm và xuất file PDF/CSV.
* **📊 3. Dashboard:** Báo cáo quản trị, biểu đồ trực quan tự động cập nhật.
* **⚙️ 4. Danh Mục:** Nơi cài đặt gốc cho thông tin khách hàng, sản phẩm, máy ép và nhân sự.
* **🤝 5. Báo Giá:** Lập và trích xuất file PDF báo giá khách hàng linh hoạt.

*Lưu ý: Nếu đây là lần đầu sử dụng trên Cloud, vui lòng vào các Tab **⚙️ Danh Mục** để thiết lập lại dữ liệu gốc trước khi lên đơn nhé!*
""")
