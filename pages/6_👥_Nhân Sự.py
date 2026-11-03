import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta, timezone
from fpdf import FPDF
import os
import urllib.request
import time
import random
from db_utils import get_connection, check_password

# ==========================================
# CẤU HÌNH TRANG, MÚI GIỜ & BẢO MẬT
# ==========================================
st.set_page_config(page_title="Hệ Thống Nhân Sự WANCHI", page_icon="👥", layout="wide")

VN_TZ = timezone(timedelta(hours=7))
def lay_gio_vn():
    return datetime.now(VN_TZ)

# Đã gỡ bỏ biến MAT_KHAU_GIAM_DOC cũ để dùng chung quyền Admin từ db_utils
is_admin = check_password()
if not is_admin: 
    st.stop()

conn = get_connection()
c = conn.cursor()

try:
    c.execute('''CREATE TABLE IF NOT EXISTS public.cau_hinh (
                    id SERIAL PRIMARY KEY, ten_cau_hinh TEXT UNIQUE, gia_tri TEXT
                )''')
    conn.commit()
except: pass

def lay_thong_tin_ma_ca():
    try:
        c.execute("SELECT gia_tri FROM public.cau_hinh WHERE ten_cau_hinh='MA_CA_HIEN_TAI'")
        r1 = c.fetchone()
        c.execute("SELECT gia_tri FROM public.cau_hinh WHERE ten_cau_hinh='THOI_GIAN_TAO_MA'")
        r2 = c.fetchone()
        if r1 and r2: return r1[0], r2[0]
    except: pass
    return None, None

try: df_nv = pd.read_sql("SELECT * FROM public.nhan_vien ORDER BY id DESC", conn)
except: df_nv = pd.DataFrame()

# ==========================================
# GIAO DIỆN CHẤM CÔNG CỦA ADMIN
# ==========================================
st.markdown("<h2 style='text-align: center; color: #4CAF50;'>📱 HỆ THỐNG CHẤM CÔNG WANCHI</h2>", unsafe_allow_html=True)

ma_ca, thoi_gian_tao = lay_thong_tin_ma_ca()
hom_nay = lay_gio_vn().strftime("%d/%m/%Y")
gio_hien_tai = lay_gio_vn().strftime("%H:%M")

st.markdown(f"### 📍 Điểm danh ngày: **{hom_nay}**")

# Hiển thị khu vực quản lý mã cho ADMIN
with st.expander("🔑 QUẢN LÝ MÃ CHẤM CÔNG (Dành cho Chủ xưởng)", expanded=True):
    if ma_ca:
        tg_tao_dt = datetime.fromisoformat(thoi_gian_tao)
        tg_het_han = tg_tao_dt + timedelta(hours=18)
        st.write(f"Mã hiện tại: **{ma_ca}** (Tạo lúc: {tg_tao_dt.strftime('%H:%M %d/%m')})")
        if lay_gio_vn() > tg_het_han: 
            st.error("⚠️ Mã này đã hết hạn 18h! Vui lòng tạo mã mới.")
        else: 
            st.success(f"Mã còn hiệu lực đến: {tg_het_han.strftime('%H:%M %d/%m')}")
    
    # Nút tạo mã mới luôn hiển thị
    if st.button("🔄 TẠO MÃ CA MỚI (Hiệu lực 18h)", type="primary"):
        moi_ma = str(random.randint(1000, 9999))
        bay_gio = lay_gio_vn().isoformat()
        c.execute("INSERT INTO public.cau_hinh (ten_cau_hinh, gia_tri) VALUES ('MA_CA_HIEN_TAI', %s) ON CONFLICT (ten_cau_hinh) DO UPDATE SET gia_tri = EXCLUDED.gia_tri", (moi_ma,))
        c.execute("INSERT INTO public.cau_hinh (ten_cau_hinh, gia_tri) VALUES ('THOI_GIAN_TAO_MA', %s) ON CONFLICT (ten_cau_hinh) DO UPDATE SET gia_tri = EXCLUDED.gia_tri", (bay_gio,))
        conn.commit()
        st.rerun()

st.markdown("---")

# Khu vực nhân viên nhập mã
if not ma_ca:
    st.warning("⚠ Chủ xưởng chưa tạo mã ca làm việc. Vui lòng liên hệ Admin!")
else:
    tg_tao_dt = datetime.fromisoformat(thoi_gian_tao)
    if lay_gio_vn() > (tg_tao_dt + timedelta(hours=18)):
        st.error("🛑 Mã ca làm việc đã hết hạn. Vui lòng báo Admin tạo mã mới!")
    else:
        col_c1, col_c2, col_c3 = st.columns([2, 1, 1])
        with col_c1: nv_cham_cong = st.selectbox("🙋‍♂ Chọn tên của bạn:", ["-- Chọn Tên --"] + df_nv['ten_nv'].tolist() if not df_nv.empty else ["-- Chọn Tên --"])
        with col_c2: pin_nhap = st.text_input("Mã PIN cá nhân:", type="password", max_chars=4)
        with col_c3: ma_ca_nhap = st.text_input("Mã CA tại xưởng:", type="password", max_chars=4)

        if nv_cham_cong != "-- Chọn Tên --" and pin_nhap and ma_ca_nhap:
            real_pin = df_nv[df_nv['ten_nv'] == nv_cham_cong].iloc[0]['ma_pin']
            if ma_ca_nhap == ma_ca:
                if pin_nhap == real_pin:
                    c.execute("SELECT gio_vao, gio_ra FROM public.cham_cong WHERE ten_nv=%s AND ngay=%s", (nv_cham_cong, hom_nay))
                    trang_thai = c.fetchone()
                    
                    col_b1, col_b2 = st.columns(2)
                    if not trang_thai:
                        if col_b1.button("🟢 VÀO CA (Check-in)", type="primary", use_container_width=True):
                            c.execute("INSERT INTO public.cham_cong (ten_nv, ngay, gio_vao) VALUES (%s, %s, %s)", (nv_cham_cong, hom_nay, gio_hien_tai))
                            conn.commit(); st.success(f"✅ Đã vào ca lúc {gio_hien_tai}"); time.sleep(1); st.rerun()
                    elif trang_thai[1] is None:
                        st.info(f"Bạn đã vào ca lúc: {trang_thai[0]}")
                        if col_b2.button("🔴 TAN CA (Check-out)", type="primary", use_container_width=True):
                            c.execute("UPDATE public.cham_cong SET gio_ra=%s WHERE ten_nv=%s AND ngay=%s", (gio_hien_tai, nv_cham_cong, hom_nay))
                            conn.commit(); st.success(f"✅ Đã tan ca lúc {gio_hien_tai}"); time.sleep(1); st.rerun()
                    else:
                        st.success(f"✅ Đã hoàn thành ngày công. ({trang_thai[0]} - {trang_thai[1]})")
                else: st.error("❌ Mã PIN cá nhân sai!")
            else: st.error("❌ Mã CA TẠI XƯỞNG không đúng!")
