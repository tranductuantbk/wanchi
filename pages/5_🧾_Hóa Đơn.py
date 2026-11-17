import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import os
import urllib.request
import time
import json
import io 
from db_utils import get_connection, check_password

st.set_page_config(page_title="Hóa Đơn & Công Nợ", page_icon="🧾", layout="wide")

# ==========================================
# CẤU HÌNH FONT PDF & CHUYỂN ĐỔI ẢNH
# ==========================================
FONT_FILE = "Roboto-Regular.ttf"
FONT_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"

@st.cache_resource
def download_font():
    if not os.path.exists(FONT_FILE):
        try: urllib.request.urlretrieve(FONT_URL, FONT_FILE)
        except: return False
    return True
download_font()

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

def convert_pdf_to_png(pdf_bytes):
    """Hàm phụ trợ chuyển byte PDF thành byte Ảnh PNG độ nét cao"""
    if not HAS_FITZ:
        st.error("⚠️ Hệ thống thiếu thư viện 'PyMuPDF' để xuất ảnh. Vui lòng chạy lệnh: pip install PyMuPDF")
        return None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=200)
        return pix.tobytes("png")
    except Exception as e:
        st.error(f"Lỗi khi chuyển đổi ảnh: {e}")
        return None

def generate_doi_chieu_pdf(ten_kh, df_unpaid, tong_tien_hd, tien_no_hien_tai):
    pdf = FPDF()
    pdf.add_page()
    
    has_font = os.path.exists(FONT_FILE)
    if has_font:
        pdf.add_font("Roboto", "", FONT_FILE, uni=True)
        pdf.add_font("Roboto", "B", FONT_FILE, uni=True)
        font_name = "Roboto"
    else:
        font_name = "Helvetica"

    def f_vn(val): return f"{val:,.0f}".replace(",", ".")

    # Tiêu đề phiếu đối chiếu
    pdf.set_font(font_name, 'B' if has_font else '', 15)
    pdf.cell(0, 10, "BẢNG ĐỐI CHIẾU CÔNG NỢ HÓA ĐƠN ĐẠI LÝ", ln=1, align='C')
    
    pdf.set_font(font_name, '', 11)
    pdf.cell(0, 7, f"Ngày lập file: {date.today().strftime('%d/%m/%Y')}", ln=1, align='C')
    pdf.ln(3)
    
    pdf.set_font(font_name, 'B' if has_font else '', 12)
    pdf.cell(0, 8, f"Khách hàng (Đại lý): {ten_kh}", ln=1, align='L')
    pdf.ln(2)

    # Header bảng chi tiết các đơn
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font(font_name, 'B' if has_font else '', 11)
    pdf.cell(15, 9, "STT", border=1, align='C', fill=True)
    pdf.cell(35, 9, "Ngày Lập", border=1, align='C', fill=True)
    pdf.cell(45, 9, "Mã Đơn", border=1, align='C', fill=True)
    pdf.cell(50, 9, "Khách Hàng", border=1, align='C', fill=True)
    pdf.cell(45, 9, "Tổng Tiền Hóa Đơn", border=1, align='C', fill=True, ln=1)

    # Nội dung các dòng hóa đơn
    pdf.set_font(font_name, '', 11)
    for idx, (_, row) in enumerate(df_unpaid.iterrows(), 1):
        pdf.cell(15, 8, str(idx), border=1, align='C')
        pdf.cell(35, 8, str(row['ngay']), border=1, align='C')
        pdf.cell(45, 8, str(row['ma_don']), border=1, align='C')
        pdf.cell(50, 8, str(row['ten_kh']), border=1, align='C')
        pdf.cell(45, 8, f"{f_vn(float(row['tong_tien']))} VNĐ", border=1, align='R', ln=1)

    pdf.ln(4)
    # Tổng kết đối chiếu
    pdf.set_font(font_name, 'B' if has_font else '', 12)
    pdf.cell(145, 9, "Tổng Tiền Hóa Đơn:", border=1, align='R', fill=True)
    pdf.cell(45, 9, f"{f_vn(tong_tien_hd)} VNĐ", border=1, align='R', fill=True, ln=1)

    pdf.cell(145, 9, "Tổng Số Tiền Đại Lý Còn Nợ:", border=1, align='R', fill=True)
    pdf.cell(45, 9, f"{f_vn(tien_no_hien_tai)} VNĐ", border=1, align='R', fill=True, ln=1)

    try:
        return bytes(pdf.output())
    except:
        return pdf.output(dest='S').encode('latin-1')

# ==========================================
# Ổ KHÓA BẢO VỆ 2 LỚP
# ==========================================
role = check_password()
if not role: st.stop()
if role == "employee":
    st.error("🛑 BẠN KHÔNG CÓ QUYỀN TRUY CẬP: Trang Hóa Đơn & Công Nợ là dữ liệu mật, chỉ dành cho Quản lý / Kế toán WANCHI.")
    st.stop()

st.header("🧾 Quản Lý Hóa Đơn & Công Nợ")

# ==========================================
# 🛡️ LÁ CHẮN CHỐNG MẤT DỮ LIỆU (DATABASE GUARD)
# ==========================================
conn = get_connection()

def kiem_tra_du_lieu_thuc_te(connection):
    """Hàm bắn tín hiệu kiểm tra xem Neon có đang ngủ đông không"""
    try:
        if connection.closed != 0:
            return False
        cur = connection.cursor()
        cur.execute("SELECT 1") # Lệnh test nhẹ nhất để gọi Neon dậy
        cur.fetchone()
        return True
    except:
        return False

# Kích hoạt lá chắn
if not kiem_tra_du_lieu_thuc_te(conn):
    # Nếu mất kết nối, thử xóa cache và gọi Neon dậy 1 lần
    st.cache_resource.clear()
    conn = get_connection()
    
    # Nếu gọi lần 2 vẫn không được -> Đóng băng hệ thống
    if not kiem_tra_du_lieu_thuc_te(conn):
        st.error("🚨 LÁ CHẮN BẢO VỆ DỮ LIỆU ĐANG KÍCH HOẠT!")
        st.warning("⚠️ Mạng yếu hoặc Máy chủ Neon đang ngủ đông khiến dữ liệu xưởng chưa được tải về. Để chống tình trạng ghi đè làm mất dữ liệu cũ, hệ thống tạm thời KHÓA toàn bộ thao tác.")
        if st.button("🔄 Bấm vào đây để tải lại kết nối", type="primary"):
            st.rerun()
        st.stop() # 🛑 Lệnh này sẽ chặn đứng mọi code phía dưới, không cho hiện giao diện

c = conn.cursor()
# ==========================================

# ==========================================
# KHỞI TẠO BẢNG DATABASE CHO CLOUD (POSTGRESQL)
# ==========================================
try:
    c.execute('''CREATE TABLE IF NOT EXISTS hoa_don (
                    id SERIAL PRIMARY KEY,
                    ngay TEXT,
                    ma_don TEXT,
                    so_phieu TEXT,
                    ten_kh TEXT,
                    tong_tien REAL,
                    da_thu REAL,
                    con_no REAL,
                    import_thue TEXT DEFAULT 'Không',
                    ghi_chu TEXT
                )''')
    conn.commit()
except Exception as e:
    conn.rollback()

# Ép nâng cấp cột cho an toàn
try:
    c.execute("ALTER TABLE hoa_don ADD COLUMN ma_don TEXT")
    conn.commit()
except: conn.rollback()

try:
    c.execute("ALTER TABLE hoa_don ADD COLUMN import_thue TEXT DEFAULT 'Không'")
    conn.commit()
except: conn.rollback()

# ==========================================

tab1, tab2, tab3 = st.tabs(["📝 Tạo hóa đơn đại lý", "📊 Bảng theo dõi hóa đơn đại lý", "📑 Import Thuế WANCHI"])

# ==========================================
# TAB 1: TẠO HÓA ĐƠN ĐẠI LÝ (BẢNG IMPORT THUẾ)
# ==========================================
with tab1:
    st.subheader("1. Khai Báo Khách Hàng")
    
    # Lấy danh sách Đại lý từ CSDL
    try:
        df_kh_list = pd.read_sql("SELECT ten_kh FROM dm_khach_hang WHERE nhom_kh = 'Đại lý'", conn)
        danh_sach_dai_ly = ["-- Chọn Đại Lý --"] + df_kh_list['ten_kh'].tolist()
    except:
        danh_sach_dai_ly = ["-- Chọn Đại Lý --"]
    
    ten_kh_input = st.selectbox("👤 Chọn Tên Đại Lý:", danh_sach_dai_ly)
    
    st.markdown("---")
    st.subheader("2. Bảng Hóa Đơn / Import Thuế")
    
    # Lấy danh sách sản phẩm, giá công ty và tự động lấy MÃ VẬT TƯ
    try:
        df_sp = pd.read_sql("SELECT ma_sp, ten_sp, gia_khach_le FROM dm_san_pham", conn)
        dict_gia = dict(zip(df_sp['ten_sp'], df_sp['gia_khach_le']))
        dict_gia_lower = {str(k).strip().lower(): v for k, v in dict_gia.items()}
        dict_ma = dict(zip(df_sp['ten_sp'], df_sp['ma_sp']))
        danh_sach_sp = df_sp['ten_sp'].tolist()
    except Exception:
        dict_gia = {}
        dict_gia_lower = {}
        dict_ma = {}
        danh_sach_sp = []

    if 'bang_hoa_don' not in st.session_state:
        st.session_state.bang_hoa_don = []

    # BỘ NHẬP LIỆU NHANH
    with st.form("form_them_sp_hd", clear_on_submit=True):
        c1, c2 = st.columns([3, 1])
        sp_chon = c1.selectbox("📦 Chọn Tên vt (Sản phẩm)", ["-- Chọn Sản Phẩm --"] + danh_sach_sp)
        sl_chon = c2.number_input("Số lượng", min_value=1, step=1)
        
        if st.form_submit_button("➕ Thêm vào bảng Hóa đơn"):
            if sp_chon != "-- Chọn Sản Phẩm --":
                # Xử lý tự động thêm "Hộp Nhựa" nếu chưa có và viết hoa chữ cái đầu mỗi từ
                sp_str = str(sp_chon).strip()
                ten_vt_hien_thi = sp_str.title() if sp_str.lower().startswith("hộp nhựa") else f"Hộp Nhựa {sp_str}".title()
                
                st.session_state.bang_hoa_don.append({
                    "Mã vt": "",  # Bỏ trống cột Mã vt không hiển thị mã
                    "Tên vt": ten_vt_hien_thi,
                    "Đvt": "Cái",
                    "Số lượng": sl_chon,
                    "Giá ngoại tệ": None,  # Để None để Excel nhận diện là ô trống hoàn toàn
                    "Tiền ngoại tệ": None,
                    "%CK": None,
                    "Chiết khấu": None,
                    "Thuế suất": None,
                    "Thuế": None
                })
                st.rerun()

    # HIỂN THỊ VÀ XỬ LÝ BẢNG DỮ LIỆU
    if st.session_state.bang_hoa_don:
        df_bang = pd.DataFrame(st.session_state.bang_hoa_don)
        df_bang.insert(0, "Xóa", False)
        
        # Tự động tính toán Giá và Tiền và làm tròn số
        gia_list = []
        tien_list = []
        for _, row in df_bang.iterrows():
            sp = str(row['Tên vt']).strip()
            # Lọc bỏ "Hộp Nhựa " để tìm về đúng giá gốc trong DB (không phân biệt hoa thường)
            sp_goc = sp[9:].strip() if sp.lower().startswith("hộp nhựa ") else sp
            gia_goc = dict_gia.get(sp, dict_gia.get(sp_goc, dict_gia_lower.get(sp.lower(), dict_gia_lower.get(sp_goc.lower(), 0))))
            
            gia_tinh = round(float(gia_goc), 0)  # Lấy trực tiếp giá công ty
            gia_list.append(gia_tinh)
            tien_list.append(round(gia_tinh * row['Số lượng'], 0))
            
        df_bang['Giá'] = gia_list
        df_bang['Tiền'] = tien_list
        df_bang['Mã vt'] = ""
        df_bang['Tên vt'] = df_bang['Tên vt'].astype(str).apply(lambda x: x.strip().title())
        
        # Sắp xếp đúng thứ tự cột như mẫu Kế toán
        cols = ["Xóa", "Mã vt", "Tên vt", "Đvt", "Số lượng", "Giá", "Tiền", "Giá ngoại tệ", "Tiền ngoại tệ", "%CK", "Chiết khấu", "Thuế suất", "Thuế"]
        df_bang = df_bang[cols]
        
        st.write("💡 *Có thể chỉnh sửa Số lượng trực tiếp trong bảng. Tích vào 'Xóa' để loại bỏ sản phẩm khỏi hóa đơn.*")
        edited_bang = st.data_editor(
            df_bang,
            column_config={
                "Xóa": st.column_config.CheckboxColumn("🗑️ Xóa", default=False),
                "Số lượng": st.column_config.NumberColumn("Số lượng", min_value=1, step=1),
                "Giá": st.column_config.NumberColumn("Giá", format="%.0f", disabled=True),
                "Tiền": st.column_config.NumberColumn("Tiền", format="%.0f", disabled=True),
                "Tên vt": st.column_config.TextColumn(disabled=True),
                "Đvt": st.column_config.TextColumn(disabled=True),
                "Mã vt": st.column_config.TextColumn(disabled=True)
            },
            hide_index=True, use_container_width=True
        )
        
        # Xử lý xóa
        if edited_bang['Xóa'].any():
            df_valid = edited_bang[edited_bang['Xóa'] == False].drop(columns=['Xóa'])
            st.session_state.bang_hoa_don = df_valid.drop(columns=['Giá', 'Tiền']).to_dict('records')
            st.rerun()
            
        # Cập nhật state nếu sửa số lượng
        edited_bang_save = edited_bang.drop(columns=['Xóa', 'Giá', 'Tiền'])
        st.session_state.bang_hoa_don = edited_bang_save.to_dict('records')
        
        tong_tien_chot = float(edited_bang['Tiền'].sum())
        st.markdown(f"### 💰 TỔNG TIỀN HÓA ĐƠN: **{tong_tien_chot:,.0f} VNĐ**")

        st.markdown("---")
        if st.button("💾 LƯU HÓA ĐƠN & TẢI EXCEL IMPORT THUẾ", type="primary"):
            if ten_kh_input == "-- Chọn Đại Lý --":
                st.error("⚠️ Vui lòng chọn Tên Đại Lý để ghi nhận công nợ!")
            else:
                ma_don_chot = f"HD-{int(time.time())}"
                
                check_hd = pd.read_sql("SELECT ma_don FROM hoa_don WHERE ma_don = %s", conn, params=(ma_don_chot,))
                if not check_hd.empty:
                    st.error(f"⚠️ Hóa đơn với mã {ma_don_chot} đã tồn tại! Vui lòng thử lại.")
                else:
                    try:
                        ngay_hd = date.today().strftime("%Y-%m-%d")
                        # Lưu vào theo dõi công nợ
                        c.execute("""INSERT INTO hoa_don 
                                     (ngay, ma_don, so_phieu, ten_kh, tong_tien, da_thu, con_no, import_thue, ghi_chu) 
                                     VALUES (%s, %s, %s, %s, %s, 0, 0, 'Không', '')""",
                                  (ngay_hd, ma_don_chot, ma_don_chot, ten_kh_input, float(tong_tien_chot)))
                        conn.commit()
                        st.success(f"🎉 Đã lưu thành công hóa đơn [{ma_don_chot}] vào Bảng Theo Dõi!")
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Lỗi hệ thống: {e}")
                
                # TẠO FILE EXCEL IMPORT
                df_export = edited_bang.drop(columns=['Xóa']).copy()
                df_export['Mã vt'] = ""
                df_export['Tên vt'] = df_export['Tên vt'].astype(str).apply(lambda x: x.strip().title())
                try:
                    import openpyxl
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_export.to_excel(writer, index=False, sheet_name='Import_Thue')
                    excel_data = output.getvalue()
                    
                    st.download_button(
                        label="📥 BẤM VÀO ĐÂY ĐỂ TẢI FILE EXCEL IMPORT THUẾ",
                        data=excel_data,
                        file_name=f"Import_Thue_{ma_don_chot}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary"
                    )
                    st.session_state.bang_hoa_don = [] # Xóa trống sau khi chốt
                except ImportError:
                    st.error("⚠️ Đám mây đang thiếu thư viện `openpyxl`. Vui lòng cài đặt!")
                    csv_data = df_export.to_csv(index=False).encode('utf-8-sig') 
                    st.download_button("📥 Tải Tạm File CSV", data=csv_data, file_name=f"Import_Thue_{ma_don_chot}.csv", mime="text/csv", type="secondary")

# ==========================================
# TAB 2: BẢNG THEO DÕI HÓA ĐƠN ĐẠI LÝ
# ==========================================
with tab2:
    st.subheader("Bảng Theo Dõi Hóa Đơn Đại Lý")
    
    df_hd = pd.read_sql("SELECT id, ngay, COALESCE(ma_don, so_phieu) as ma_don, ten_kh, tong_tien, da_thu FROM hoa_don ORDER BY id DESC", conn)
    
    if df_hd.empty:
        st.info("Chưa có dữ liệu hóa đơn nào được lưu.")
    else:
        loc_kh = st.selectbox("🔍 Lọc theo Đại lý", ["Tất cả"] + df_hd['ten_kh'].unique().tolist())

        # Bảng kê trên chỉ hiển thị những đơn chưa thanh toán (ẩn các đơn đã thanh toán)
        df_chua_tra = df_hd[df_hd['da_thu'] < df_hd['tong_tien']].copy()

        df_hien_thi_hd = df_chua_tra.copy()
        if loc_kh != "Tất cả":
            df_hien_thi_hd = df_hien_thi_hd[df_hien_thi_hd['ten_kh'] == loc_kh]

        if df_hien_thi_hd.empty:
            st.success("✅ Hiện tại không còn hóa đơn nào chưa thanh toán!")
        else:
            # Chuẩn bị hiển thị, thêm cột chọn tick để thanh toán
            df_hien_thi_hd.insert(0, "Chọn", False)
            
            # Chỉ giữ lại các cột cần thiết cho bảng theo dõi
            df_hien_thi_hd = df_hien_thi_hd[['Chọn', 'ngay', 'ma_don', 'ten_kh', 'tong_tien', 'da_thu']]
            df_hien_thi_hd.columns = ['Chọn', 'Ngày Lập', 'Mã Đơn', 'Khách Hàng', 'Tổng Tiền Hóa Đơn', 'da_thu_hidden']

            # Sử dụng Data Editor để có thể tick chọn
            edited_df = st.data_editor(
                df_hien_thi_hd.drop(columns=['da_thu_hidden']),
                column_config={
                    "Chọn": st.column_config.CheckboxColumn("Tick", default=False),
                    "Ngày Lập": st.column_config.TextColumn(disabled=True),
                    "Mã Đơn": st.column_config.TextColumn(disabled=True),
                    "Khách Hàng": st.column_config.TextColumn(disabled=True),
                    "Tổng Tiền Hóa Đơn": st.column_config.NumberColumn(format="%.0f", disabled=True)
                },
                use_container_width=True, hide_index=True, key="editor_thanh_toan_hd"
            )
            
            # Xử lý Nút Thanh Toán
            don_chon = edited_df[edited_df['Chọn'] == True]['Mã Đơn'].tolist()
            if don_chon:
                if st.button("✅ XÁC NHẬN ĐÃ THANH TOÁN CÁC ĐƠN ĐÃ CHỌN", type="primary"):
                    try:
                        for ma in don_chon:
                            c.execute("UPDATE hoa_don SET da_thu = tong_tien WHERE ma_don = %s", (ma,))
                        conn.commit()
                        st.success(f"🎉 Đã thanh toán thành công các đơn: {', '.join(don_chon)}")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Lỗi thanh toán: {e}")

        # Hiển thị Bảng Công Nợ Thuế & Xuất File Đối Chiếu
        st.markdown("---")
        ten_doi_chieu = loc_kh if loc_kh != "Tất cả" else "Tất cả Đại lý"
        st.subheader(f"📊 Bảng Chi Tiết Công Nợ - Khách Hàng: **{ten_doi_chieu}**")
        
        # Lọc các đơn chưa thanh toán để tính tổng tiền hóa đơn đang nợ và tiền nợ thuế tương ứng
        df_no_hien_tai = df_chua_tra if loc_kh == "Tất cả" else df_chua_tra[df_chua_tra['ten_kh'] == loc_kh]
        df_da_tra = df_hd[df_hd['da_thu'] >= df_hd['tong_tien']] if loc_kh == "Tất cả" else df_hd[(df_hd['ten_kh'] == loc_kh) & (df_hd['da_thu'] >= df_hd['tong_tien'])]
        
        tong_tien_hd = float(df_no_hien_tai['tong_tien'].sum()) if not df_no_hien_tai.empty else 0.0
        tien_no_hien_tai = (tong_tien_hd / 0.95) - tong_tien_hd

        df_summary = pd.DataFrame({
            "Tên Đại Lý": [ten_doi_chieu],
            "Tổng Tiền Hóa Đơn": [tong_tien_hd],
            "Tổng Số Tiền Đại Lý Còn Nợ": [tien_no_hien_tai]
        })
        
        st.dataframe(
            df_summary.style.format({
                "Tổng Tiền Hóa Đơn": "{:,.0f} VNĐ",
                "Tổng Số Tiền Đại Lý Còn Nợ": "{:,.0f} VNĐ"
            }),
            use_container_width=True, hide_index=True
        )
        
        if not df_da_tra.empty:
            danh_sach_ma_da_tra = df_da_tra['ma_don'].tolist()
            st.info(f"✅ Các mã đơn đã thanh toán công nợ: **{', '.join(danh_sach_ma_da_tra)}**")

        # --- TÙY CHỌN XUẤT FILE ĐỐI CHIẾU PDF / ẢNH (MẶC ĐỊNH ẢNH) ---
        if not df_no_hien_tai.empty:
            st.markdown("#### 📁 Xuất File Đối Chiếu Công Nợ:")
            loai_xuat_dc = st.radio(
                "Lựa chọn định dạng xuất file:",
                ["Chỉ xuất file PDF", "Chỉ xuất file Ảnh (PNG)", "Xuất cả PDF và Ảnh"],
                horizontal=True,
                key="radio_xuat_doi_chieu",
                index=1  # Mặc định chọn xuất file Ảnh (PNG)
            )
            
            col_dc1, col_dc2, col_dc3 = st.columns([1, 1, 1])
            with col_dc1:
                if st.button("📄 TẠO FILE ĐỐI CHIẾU CÔNG NỢ", type="primary", use_container_width=True):
                    pdf_bytes = generate_doi_chieu_pdf(ten_doi_chieu, df_no_hien_tai, tong_tien_hd, tien_no_hien_tai)
                    safe_name = ten_doi_chieu.replace(" ", "_")
                    ngay_str = date.today().strftime("%d%m%Y")
                    
                    st.session_state['pdf_doi_chieu'] = pdf_bytes
                    st.session_state['pdf_doi_chieu_name'] = f"Doi_Chieu_Cong_No_{safe_name}_{ngay_str}.pdf"
                    
                    img_bytes = convert_pdf_to_png(pdf_bytes)
                    if img_bytes:
                        st.session_state['img_doi_chieu'] = img_bytes
                    st.success("✅ Đã tạo file đối chiếu! Bấm nút bên cạnh để tải về.")

            if 'pdf_doi_chieu' in st.session_state:
                if "PDF" in loai_xuat_dc or "Cả" in loai_xuat_dc:
                    with col_dc2:
                        st.download_button(
                            label="🖨️ TẢI FILE ĐỐI CHIẾU (PDF)",
                            data=st.session_state['pdf_doi_chieu'],
                            file_name=st.session_state['pdf_doi_chieu_name'],
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True
                        )
                if ("Ảnh" in loai_xuat_dc or "Cả" in loai_xuat_dc) and st.session_state.get('img_doi_chieu'):
                    with col_dc3:
                        img_name_dc = st.session_state['pdf_doi_chieu_name'].replace('.pdf', '.png')
                        st.download_button(
                            label="🖼️ TẢI FILE ĐỐI CHIẾU (ẢNH)",
                            data=st.session_state['img_doi_chieu'],
                            file_name=img_name_dc,
                            mime="image/png",
                            type="primary",
                            use_container_width=True
                        )

# ==========================================
# TAB 3: IMPORT THUẾ WANCHI (CÔNG CỤ PHỤ)
# ==========================================
with tab3:
    st.subheader("Trích Xuất Dữ Liệu Khai Báo Thuế Độc Lập")
    st.markdown("💡 *Đây là công cụ trích xuất độc lập dành cho Kế toán, không lưu vào dữ liệu theo dõi công nợ.*")
    
    col_p1, col_p2 = st.columns([1, 2])
    with col_p1:
        ma_don_import = st.text_input("📝 Nhập Mã Đơn (Từ hệ thống kho - VD: DH-0001):", key="import_thue_phieu").strip()

    if ma_don_import:
        df_dh_import = pd.read_sql("SELECT chi_tiet FROM don_hang WHERE ma_don = %s", conn, params=(ma_don_import,))

        if df_dh_import.empty or pd.isna(df_dh_import.iloc[0]['chi_tiet']):
            st.warning(f"⚠️ Không tìm thấy dữ liệu sản phẩm cho Mã Đơn {ma_don_import}")
        else:
            try:
                items_import = json.loads(df_dh_import.iloc[0]['chi_tiet'])
                df_items_thue = pd.DataFrame(items_import)

                if 'Tên Sản Phẩm' in df_items_thue.columns:
                    sp_col_thue = 'Tên Sản Phẩm'
                elif 'Tên Sản Phẩm OME' in df_items_thue.columns:
                    sp_col_thue = 'Tên Sản Phẩm OME'
                else:
                    sp_col_thue = df_items_thue.columns[0] 

                df_items_thue = df_items_thue.rename(columns={sp_col_thue: 'ten_sp', 'Số Lượng': 'so_luong', 'Đơn Giá': 'don_gia'})
                if 'Đơn Giá OME' in df_items_thue.columns:
                    df_items_thue['don_gia'] = df_items_thue['Đơn Giá OME']

                df_items_thue['don_gia_thue'] = df_items_thue['don_gia'].astype(float).round(0)
                
                df_items_thue['tien_thue'] = (df_items_thue['so_luong'].astype(float) * df_items_thue['don_gia_thue']).round(0)
                tong_tien_import = df_items_thue['tien_thue'].sum()

                with col_p2:
                    st.markdown(f"<h3 style='color: #0066cc; margin-top: 25px;'>Tổng tiền: {tong_tien_import:,.0f}</h3>", unsafe_allow_html=True)
                
                # Bỏ trống hoàn toàn cột Mã vật tư
                ma_vt_list = ["" for _ in df_items_thue['ten_sp']]

                # Tự động thêm "Hộp Nhựa" vào Tên Sản Phẩm nếu chưa có và viết hoa chữ cái đầu mỗi từ
                ten_vt_list = []
                for ten in df_items_thue['ten_sp']:
                    ten_str = str(ten).strip()
                    if not ten_str.lower().startswith("hộp nhựa"):
                        ten_vt_list.append(f"Hộp Nhựa {ten_str}".title())
                    else:
                        ten_vt_list.append(ten_str.title())

                df_import_thue = pd.DataFrame({
                    "Mã vt": ma_vt_list,
                    "Tên vt": ten_vt_list,
                    "Đvt": "Cái",
                    "Số lượng": df_items_thue.get('so_luong', 0),
                    "Giá": df_items_thue.get('don_gia_thue', 0),
                    "Tiền": df_items_thue.get('tien_thue', 0),
                    "Giá ngoại tệ": None,
                    "Tiền ngoại tệ": None,
                    "%CK": None,
                    "Chiết khấu": None,
                    "Thuế suất": None,
                    "Thuế": None
                })

                st.dataframe(
                    df_import_thue.style.format({
                        "Số lượng": "{:,.0f}",
                        "Giá": "{:,.0f}",
                        "Tiền": "{:,.0f}"
                    }),
                    use_container_width=True, hide_index=True
                )

                st.markdown("---")
                
                try:
                    import openpyxl
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_import_thue.to_excel(writer, index=False, sheet_name='Import_Thue')
                    excel_data = output.getvalue()
                    
                    st.download_button(
                        label="📥 Tải File Excel (.xlsx) Để Import Kế Toán",
                        data=excel_data,
                        file_name=f"Import_Thue_{ma_don_import}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary"
                    )
                except ImportError:
                    st.error("⚠️ Đám mây đang thiếu thư viện `openpyxl`. Vui lòng cài đặt!")
                    csv_data = df_import_thue.to_csv(index=False).encode('utf-8-sig') 
                    st.download_button("📥 Tải Tạm File CSV", data=csv_data, file_name=f"Import_Thue_{ma_don_import}.csv", mime="text/csv", type="secondary")

            except Exception as e:
                st.error(f"Lỗi xử lý dữ liệu: {e}")
