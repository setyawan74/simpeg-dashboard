import streamlit as st
import pandas as pd
import bcrypt
import plotly.express as px
from io import BytesIO
from fpdf import FPDF
import sqlite3
import os
import re
from datetime import date
import datetime

# ================== Konfigurasi Halaman ==================
st.set_page_config(page_title="SIMPEG Dashboard", page_icon="👥", layout="wide")

# ================== Struktur Data ==================
EXPECTED_COLS = [
    "NAMA","NIP","GELAR DEPAN","GELAR BELAKANG","TEMPAT LAHIR","TANGGAL LAHIR",
    "JENIS KELAMIN","AGAMA","JENIS KAWIN","NIK","NOMOR HP","EMAIL","ALAMAT",
    "NPWP","BPJS","JENIS PEGAWAI","KEDUDUKAN HUKUM","STATUS CPNS PNS",
    "KARTU ASN VIRTUAL","TMT CPNS","TMT PNS","GOL AWAL","GOL AKHIR",
    "TMT GOLONGAN","MK TAHUN","MK BULAN","JENIS JABATAN","NAMA JABATAN",
    "TMT JABATAN","TINGKAT PENDIDIKAN","NAMA PENDIDIKAN","NAMA UNOR","UNOR INDUK","FOTO"
]

# ================== Helpers Keamanan ==================
def is_strong_password(pw: str) -> bool:
    if len(pw) < 8: return False
    if not re.search(r"[A-Z]", pw): return False
    if not re.search(r"[a-z]", pw): return False
    if not re.search(r"[0-9]", pw): return False
    if not re.search(r"[^A-Za-z0-9]", pw): return False
    return True

# ================== Session State ==================
os.makedirs("images", exist_ok=True)
os.makedirs("backups", exist_ok=True)

if "users" not in st.session_state:
    st.session_state.users = {
        "admin": {
            "password_hash": bcrypt.hashpw("admin123!".encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            "role": "Admin"
        },
        "supervisor": {
            "password_hash": bcrypt.hashpw("Super123!".encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            "role": "Supervisor"
        },
        "user": {
            "password_hash": bcrypt.hashpw("User123!".encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            "role": "User"
        }
    }

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "username": None, "role": None}

# ================== Database ==================
DB_FILE = "simpeg.db"

def conn_db(): return sqlite3.connect(DB_FILE)

def init_db():
    with conn_db() as conn:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS pegawai (NIP TEXT PRIMARY KEY)")
        cur.execute("""CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT, role TEXT, action TEXT, target TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit()
    ensure_columns()

def ensure_columns():
    with conn_db() as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(pegawai)")
        existing_cols = [row[1] for row in cur.fetchall()]
        for col in EXPECTED_COLS:
            if col not in existing_cols:
                cur.execute(f"ALTER TABLE pegawai ADD COLUMN '{col}' TEXT")
        conn.commit()

def load_data():
    with conn_db() as conn: return pd.read_sql_query("SELECT * FROM pegawai", conn)

def save_row(row: dict):
    for col in EXPECTED_COLS: row.setdefault(col, "")
    with conn_db() as conn:
        cols = list(row.keys())
        placeholders = ",".join(["?"] * len(cols))
        values = [row.get(c, "") for c in cols]
        quoted_cols = ",".join([f'"{c}"' for c in cols])
        conn.execute(f"INSERT OR REPLACE INTO pegawai ({quoted_cols}) VALUES ({placeholders})", values)
        conn.commit()

def delete_by_nip(nip: str):
    with conn_db() as conn:
        conn.execute("DELETE FROM pegawai WHERE NIP = ?", (nip,))
        conn.commit()

def replace_all(df: pd.DataFrame):
    for col in EXPECTED_COLS:
        if col not in df.columns: df[col] = ""
    df = df[EXPECTED_COLS]
    with conn_db() as conn:
        conn.execute("DELETE FROM pegawai")
        if not df.empty: df.to_sql("pegawai", conn, if_exists="append", index=False)

# ================== Audit Log ==================
def log_action(user, role, action, target=""):
    with conn_db() as conn:
        conn.execute("INSERT INTO audit_log (user, role, action, target) VALUES (?,?,?,?)", (user, role, action, target))
        conn.commit()

def load_today_logs():
    with conn_db() as conn: df_log = pd.read_sql_query("SELECT * FROM audit_log", conn)
    if df_log.empty: return pd.DataFrame()
    df_log["timestamp"] = pd.to_datetime(df_log["timestamp"], errors="coerce")
    today = pd.Timestamp.today().normalize()
    return df_log[df_log["timestamp"].dt.date == today.date()]

def count_today_logs(): return len(load_today_logs())

# ================== Modul PDF (fix bytes encoding) ==================
def generate_pdf_resmi(data, foto_path=None):
    pdf = FPDF(); pdf.add_page()
    pdf.set_fill_color(33,150,243); pdf.set_text_color(255,255,255); pdf.set_font("Arial","B",16)
    pdf.cell(0,12,"PROFIL PEGAWAI",ln=True,align="C",fill=True); pdf.ln(8)
    if foto_path and os.path.exists(foto_path):
        try: pdf.image(foto_path,x=160,y=22,w=30,h=40)
        except: pass
    pdf.set_text_color(0,0,0); pdf.set_font("Arial",size=12); pdf.ln(20)
    labels=["NAMA","NIP","NAMA_JABATAN","JENIS_JABATAN","NAMA_UNOR","UNOR INDUK","TMT_JABATAN",
            "JENIS_KELAMIN","TANGGAL_LAHIR","TINGKAT_PENDIDIKAN","NAMA_PENDIDIKAN","EMAIL","NOMOR HP","ALAMAT"]
    for key in labels:
        key_db=key.replace("_"," "); val=str(data.get(key,data.get(key_db,"")))
        pdf.cell(60,9,key_db,border=1); pdf.cell(0,9,val,border=1,ln=True)
    return pdf.output(dest="S").encode("latin-1")

def generate_id_card(pegawai):
    pdf=FPDF("P","mm",(85,54)); pdf.add_page(); pdf.set_fill_color(33,150,243); pdf.rect(0,0,85,54,"F")
    foto_path=pegawai.get("FOTO","")
    if foto_path and os.path.exists(foto_path):
        try: pdf.image(foto_path,x=5,y=6,w=18,h=22)
        except: pass
    nama=str(pegawai.get("NAMA","")).strip()
    nip=str(pegawai.get("NIP","")).strip()
    jabatan=str(pegawai.get("NAMA JABATAN","")).strip()
    unit=str(pegawai.get("NAMA UNOR","")).strip()
    pdf.set_text_color(255,255,255)
    pdf.set_font("Arial","B",10); pdf.text(28,12,nama[:30])
    pdf.set_font("Arial","",8)
    pdf.text(28,17,f"NIP: {nip[:28]}")
    pdf.text(28,22,f"Jabatan: {jabatan[:28]}")
    pdf.text(28,27,f"Unit: {unit[:28]}")
    pdf.set_font("Arial","B",8); pdf.text(5,50,"SIMPEG - Kartu Pegawai")
    return pdf.output(dest="S").encode("latin-1")

# ================== Auth helpers (tanpa OTP) ==================
def login(u, p):
    if u in st.session_state.users:
        info = st.session_state.users[u]
        if bcrypt.checkpw(p.encode("utf-8"), info["password_hash"].encode("utf-8")):
            st.session_state.auth={"logged_in":True,"username":u,"role":info["role"]}
            log_action(u, info["role"], "LOGIN", u)
            return True
        else:
            st.error("Password salah.")
            return False
    else:
        st.error("Username tidak ditemukan.")
        return False

def logout():
    if st.session_state.auth["logged_in"]:
        log_action(st.session_state.auth["username"], st.session_state.auth["role"], "LOGOUT", st.session_state.auth["username"])
    st.session_state.auth={"logged_in":False,"username":None,"role":None}

def is_admin(): return st.session_state.auth["role"]=="Admin"
def is_supervisor(): return st.session_state.auth["role"]=="Supervisor"

# ================== Init DB ==================
init_db()
if "pegawai" not in st.session_state: st.session_state.pegawai=load_data()

# ================== Halaman Login + Reset Password ==================
if not st.session_state.auth["logged_in"]:
    st.markdown("<h2 style='text-align:center;color:#2196f3;'>SISTEM INFORMASI KEPEGAWAIAN</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>Halaman Login • Admin • Supervisor • User</p>", unsafe_allow_html=True)

    # Form login
    st.sidebar.title("Login")
    with st.sidebar.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        submit_login = st.form_submit_button("Masuk")
    if submit_login:
        if login(u, p):
            st.success(f"Selamat datang, {u}")
        else:
            st.error("Login gagal. Periksa username/password.")

    # Bantuan reset sebelum login
    st.markdown("---")
    st.subheader("🔐 Bantuan Login")
    st.info("Jika lupa password, reset di sini.")

    with st.form("reset_pw_form"):
        target_user = st.text_input("Username")
        new_pw = st.text_input("Password baru", type="password")
        submit_pw = st.form_submit_button("Reset Password")
    if submit_pw:
        if target_user not in st.session_state.users:
            st.error("Username tidak ditemukan.")
        elif not is_strong_password(new_pw):
            st.error("Password terlalu lemah. Minimal 8 karakter dan wajib ada huruf besar, kecil, angka, dan simbol.")
        else:
            st.session_state.users[target_user]["password_hash"] = bcrypt.hashpw(new_pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            log_action("SYSTEM", "Admin", "RESET_PASSWORD", target_user)
            st.success(f"Password {target_user} berhasil direset!")

    st.stop()

# ================== Sidebar ==================
st.sidebar.title("PANEL")
if is_admin():
    menu = st.sidebar.radio("Navigasi",
        ["Dashboard","Pegawai","Pegawai Grafik","Laporan","Rekapitulasi",
         "Profil Pegawai","ID Card","Backup/Hapus Data","Audit Log","Keamanan"])
elif is_supervisor():
    menu = st.sidebar.radio("Navigasi",
        ["Dashboard","Pegawai","Pegawai Grafik","Laporan","Rekapitulasi","Profil Pegawai","ID Card","Backup/Hapus Data"])
else:
    menu = st.sidebar.radio("Navigasi",
        ["Dashboard","Pegawai","Pegawai Grafik","Laporan","Rekapitulasi","Profil Pegawai","Backup/Hapus Data"])

st.sidebar.write(f"Login sebagai: {st.session_state.auth['username']} ({st.session_state.auth['role']})")
if is_supervisor():
    st.sidebar.markdown("🕵️ Anda login sebagai **Supervisor**")
    st.sidebar.info("Hak akses: lihat data, grafik, laporan, profil, cetak ID Card")
if st.sidebar.button("Logout"):
    logout(); st.stop()

# Badge aktivitas baru (Admin)
if is_admin():
    today_count = count_today_logs()
    if today_count > 0:
        st.sidebar.markdown(
            f"<span style='color:white;background:red;padding:4px 8px;border-radius:12px;'>🔔 {today_count} aktivitas baru</span>",
            unsafe_allow_html=True
        )

# ================== CSS ==================
st.markdown("""
<style>
.card {
    padding:20px;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.15);
    text-align:center;width:100%;height:130px;display:flex;flex-direction:column;
    justify-content:center;color:white;
}
.card h4 {margin:0;font-size:16px;font-weight:bold;}
.card h2 {margin:5px 0 0 0;font-size:28px;}
</style>
""", unsafe_allow_html=True)

# ================== Dashboard ==================
if menu == "Dashboard":
    df = st.session_state.pegawai
    total = len(df)
    user_count = len(st.session_state.users)

    if "JENIS KELAMIN" in df.columns and not df.empty:
        jk = df["JENIS KELAMIN"].astype(str).str.strip().str.upper()
        laki = jk.isin(["M","LAKI-LAKI","L","PRIA"]).sum()
        perempuan = jk.isin(["F","PEREMPUAN","P","WANITA"]).sum()
    else:
        laki, perempuan = 0, 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="card" style="background:linear-gradient(135deg,#2196f3,#21cbf3);">👨<h4>LAKI-LAKI</h4><h2>{laki}</h2></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="card" style="background:linear-gradient(135deg,#e91e63,#ff80ab);">👩<h4>PEREMPUAN</h4><h2>{perempuan}</h2></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="card" style="background:linear-gradient(135deg,#9c27b0,#ba68c8);">🔑<h4>USER</h4><h2>{user_count}</h2></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="card" style="background:linear-gradient(135deg,#4caf50,#81c784);">👥<h4>PEGAWAI</h4><h2>{total}</h2></div>', unsafe_allow_html=True)

    if not df.empty and "JENIS KELAMIN" in df.columns:
        jk_series = df["JENIS KELAMIN"].astype(str).str.strip().str.upper()
        label_map = {"M":"LAKI-LAKI","L":"LAKI-LAKI","PRIA":"LAKI-LAKI","LAKI-LAKI":"LAKI-LAKI",
                     "F":"PEREMPUAN","P":"PEREMPUAN","WANITA":"PEREMPUAN","PEREMPUAN":"PEREMPUAN"}
        jk_mapped = jk_series.map(lambda x: label_map.get(x, x))
        jk_counts = jk_mapped.value_counts().reset_index()
        jk_counts.columns = ["Jenis Kelamin","Jumlah"]
        fig = px.pie(jk_counts, names="Jenis Kelamin", values="Jumlah",
                     color="Jenis Kelamin",
                     color_discrete_map={"LAKI-LAKI":"#2196f3","PEREMPUAN":"#e91e63"},
                     title="Distribusi Gender Pegawai")
        st.plotly_chart(fig, use_container_width=True)

    # Ringkasan aktivitas hari ini (Admin)
    if is_admin():
        st.markdown("---")
        st.subheader("📢 Aktivitas Hari Ini")
        st.info("Refresh halaman untuk melihat aktivitas terbaru.")
        df_today = load_today_logs()
        if df_today.empty:
            st.info("Belum ada aktivitas tercatat hari ini.")
        else:
            colA, colB, colC, colD, colE = st.columns(5)
            colA.metric("Total", len(df_today))
            colB.metric("Tambah", (df_today["action"]=="INSERT").sum())
            colC.metric("Edit", (df_today["action"]=="UPDATE").sum())
            colD.metric("Hapus", (df_today["action"]=="DELETE").sum())
            colE.metric("Restore", (df_today["action"]=="RESTORE").sum())
            st.dataframe(df_today[["user","role","action","target","timestamp"]], use_container_width=True)

    # Tambah user (Admin)
    if is_admin():
        st.markdown("---")
        st.subheader("➕ Tambah pengguna")
        with st.form("add_user_form"):
            u = st.text_input("Username baru")
            p = st.text_input("Password baru", type="password")
            r = st.selectbox("Role", ["Admin","User","Supervisor"])
            submit_u = st.form_submit_button("Tambah")
        if submit_u and u and p:
            if u in st.session_state.users:
                st.warning("Username sudah ada.")
            elif not is_strong_password(p):
                st.error("Password terlalu lemah. Minimal 8 karakter, huruf besar/kecil, angka, simbol.")
            else:
                st.session_state.users[u] = {
                    "password_hash": bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
                    "role": r
                }
                log_action(st.session_state.auth["username"], st.session_state.auth["role"], "ADD_USER", u)
                st.success(f"Pengguna {u} ({r}) berhasil ditambahkan!")
        st.dataframe(pd.DataFrame(
            [{"Username": uname, "Role": info["role"]} for uname, info in st.session_state.users.items()]),
            use_container_width=True
        )

# ================== Pegawai (CRUD + View) ==================
elif menu == "Pegawai":
    st.header("Data Pegawai")
    df = st.session_state.pegawai
    st.dataframe(df, use_container_width=True)

    if is_admin():
        st.subheader("Upload data pegawai (CSV/Excel)")
        uploaded_file = st.file_uploader("Pilih file", type=["csv","xlsx"])
        if uploaded_file:
            df_new = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
            df_new.columns = [str(c).strip().upper() for c in df_new.columns]
            for col in EXPECTED_COLS:
                if col not in df_new.columns: df_new[col] = ""
            replace_all(df_new[EXPECTED_COLS])
            log_action(st.session_state.auth["username"], st.session_state.auth["role"], "RESTORE", "UPLOAD")
            st.session_state.pegawai = load_data()
            st.success("Data pegawai berhasil diimpor!")

        st.download_button("Unduh template CSV (header standar)",
                           (",".join(EXPECTED_COLS) + "\n"),
                           file_name="template_simpeg.csv", mime="text/csv")

        st.subheader("Tambah pegawai baru")
        with st.form("tambah_pegawai"):
            nama = st.text_input("NAMA")
            nip = st.text_input("NIP")
            jabatan = st.text_input("NAMA JABATAN")
            nama_unor = st.text_input("NAMA UNOR")
            unor_induk = st.text_input("UNOR INDUK")
            tmt_jabatan = st.date_input("TMT JABATAN")
            submit = st.form_submit_button("Tambah")
        if submit and nama and nip:
            new_row = {col: "" for col in EXPECTED_COLS}
            new_row.update({
                "NAMA": nama, "NIP": nip, "NAMA JABATAN": jabatan,
                "NAMA UNOR": nama_unor, "UNOR INDUK": unor_induk,
                "TMT JABATAN": str(tmt_jabatan),
            })
            save_row(new_row)
            log_action(st.session_state.auth["username"], st.session_state.auth["role"], "INSERT", nip)
            st.session_state.pegawai = load_data()
            st.success("Pegawai ditambahkan!")

        st.subheader("Edit / Hapus Pegawai")
        nip_search = st.text_input("Masukkan NIP pegawai untuk edit/hapus")
        if nip_search:
            df_match = st.session_state.pegawai[st.session_state.pegawai["NIP"].astype(str) == str(nip_search)]
            if not df_match.empty:
                st.dataframe(df_match, use_container_width=True)
                def default_tmt_value(val):
                    try: return pd.to_datetime(val).date()
                    except Exception: return date.today()
                with st.form("edit_pegawai"):
                    nama_edit = st.text_input("NAMA", value=str(df_match.iloc[0].get("NAMA","")))
                    jabatan_edit = st.text_input("NAMA JABATAN", value=str(df_match.iloc[0].get("NAMA JABATAN","")))
                    nama_unor_edit = st.text_input("NAMA UNOR", value=str(df_match.iloc[0].get("NAMA UNOR","")))
                    unor_induk_edit = st.text_input("UNOR INDUK", value=str(df_match.iloc[0].get("UNOR INDUK","")))
                    tmt_raw = df_match.iloc[0].get("TMT JABATAN","")
                    tmt_edit = st.date_input("TMT JABATAN", value=default_tmt_value(tmt_raw))
                    submit_edit = st.form_submit_button("Simpan Perubahan")
                if submit_edit:
                    updated_row = {col: str(df_match.iloc[0].get(col,"")) for col in EXPECTED_COLS}
                    updated_row.update({
                        "NIP": str(df_match.iloc[0].get("NIP", nip_search)),
                        "NAMA": nama_edit,
                        "NAMA JABATAN": jabatan_edit,
                        "NAMA UNOR": nama_unor_edit,
                        "UNOR INDUK": unor_induk_edit,
                        "TMT JABATAN": str(tmt_edit),
                    })
                    save_row(updated_row)
                    log_action(st.session_state.auth["username"], st.session_state.auth["role"], "UPDATE", nip_search)
                    st.session_state.pegawai = load_data()
                    st.success("Data pegawai berhasil diperbarui!")
                st.write("Aksi hapus memerlukan konfirmasi:")
                if st.button("Hapus Pegawai"):
                    st.warning("Klik tombol konfirmasi di bawah untuk menghapus.")
                    if st.button("Konfirmasi Hapus", type="primary"):
                        delete_by_nip(nip_search)
                        log_action(st.session_state.auth["username"], st.session_state.auth["role"], "DELETE", nip_search)
                        st.session_state.pegawai = load_data()
                        st.success("Pegawai berhasil dihapus!")
            else:
                st.warning("Pegawai dengan NIP tersebut tidak ditemukan.")
    elif is_supervisor():
        st.info("Anda login sebagai Supervisor. Hanya bisa melihat data pegawai (tanpa CRUD).")
    else:
        st.info("Anda login sebagai User. Hanya bisa melihat data pegawai.")

# ================== Pegawai Grafik ==================
elif menu == "Pegawai Grafik":
    st.header("Grafik Pegawai")
    df = st.session_state.pegawai

    st.subheader("Distribusi Gender")
    if not df.empty and "JENIS KELAMIN" in df.columns:
        jk_series = df["JENIS KELAMIN"].astype(str).str.strip().str.upper()
        label_map = {"M":"LAKI-LAKI","L":"LAKI-LAKI","PRIA":"LAKI-LAKI","LAKI-LAKI":"LAKI-LAKI",
                     "F":"PEREMPUAN","P":"PEREMPUAN","WANITA":"PEREMPUAN","PEREMPUAN":"PEREMPUAN"}
        jk_mapped = jk_series.map(lambda x: label_map.get(x, x))
        jk_counts = jk_mapped.value_counts().reset_index()
        jk_counts.columns = ["Jenis Kelamin","Jumlah"]
        fig_gender = px.bar(jk_counts, x="Jenis Kelamin", y="Jumlah", color="Jenis Kelamin",
                            color_discrete_map={"LAKI-LAKI":"#2196f3","PEREMPUAN":"#e91e63"},
                            title="Distribusi Gender Pegawai")
        st.plotly_chart(fig_gender, use_container_width=True)
    else:
        st.info("Data pegawai atau kolom JENIS KELAMIN belum tersedia.")

    st.subheader("Distribusi Usia")
    if not df.empty and "TANGGAL LAHIR" in df.columns:
        df_age = df.copy()
        df_age["TANGGAL LAHIR"] = pd.to_datetime(df_age["TANGGAL LAHIR"], errors="coerce")
        df_age["USIA"] = df_age["TANGGAL LAHIR"].apply(lambda x: (pd.Timestamp.today().year - x.year) if pd.notnull(x) else None)
        usia_series = df_age["USIA"].dropna().astype(int)
        if not usia_series.empty:
            bins = [0, 20, 30, 40, 50, 60, 150]
            labels = ["<20","20–29","30–39","40–49","50–59","60+"]
            usia_bucket = pd.cut(usia_series, bins=bins, labels=labels, right=False, include_lowest=True)
            usia_counts = usia_bucket.value_counts().reindex(labels).fillna(0).astype(int).reset_index()
            usia_counts.columns = ["Rentang Usia","Jumlah"]
            fig_age = px.bar(usia_counts, x="Rentang Usia", y="Jumlah", color="Rentang Usia", title="Distribusi Usia Pegawai")
            st.plotly_chart(fig_age, use_container_width=True)
        else:
            st.info("Data usia pegawai tidak tersedia atau tidak valid.")
    else:
        st.info("Kolom TANGGAL LAHIR belum tersedia.")

    st.subheader("Distribusi Tingkat Pendidikan")
    if not df.empty and "TINGKAT PENDIDIKAN" in df.columns:
        pend_series = df["TINGKAT PENDIDIKAN"].astype(str).str.strip().str.upper()
        norm_map = {
            "SD":"SD","SEKOLAH DASAR":"SD","ELEMENTARY SCHOOL":"SD",
            "SMP":"SMP","SEKOLAH MENENGAH PERTAMA":"SMP","JUNIOR HIGH":"SMP",
            "SMA":"SMA","SMU":"SMA","SMK":"SMA","MA":"SMA","HIGH SCHOOL":"SMA",
            "D1":"D1","DIPLOMA I":"D1","D2":"D2","DIPLOMA II":"D2",
            "D3":"D3","DIPLOMA III":"D3","AHLI MADYA":"D3",
            "D4":"D4","DIPLOMA IV":"D4","SARJANA TERAPAN":"D4",
            "S1":"S1","SARJANA":"S1","UNDERGRADUATE":"S1","BACHELOR":"S1",
            "S2":"S2","MAGISTER":"S2","MASTER":"S2","POSTGRADUATE":"S2",
            "S3":"S3","DOKTOR":"S3","PHD":"S3","DOCTORATE":"S3"
        }
        pend_norm = pend_series.map(lambda x: norm_map.get(x, x))
        pend_counts = pend_norm.value_counts().reset_index()
        pend_counts.columns = ["Tingkat Pendidikan","Jumlah"]
        fig_pend = px.bar(pend_counts, x="Tingkat Pendidikan", y="Jumlah", color="Tingkat Pendidikan",
                          title="Distribusi Tingkat Pendidikan Pegawai")
        st.plotly_chart(fig_pend, use_container_width=True)
    else:
        st.info("Kolom TINGKAT PENDIDIKAN belum tersedia.")

# ================== Laporan ==================
elif menu == "Laporan":
    st.header("Laporan Pegawai")
    df = st.session_state.pegawai
    if not df.empty:
        units = df["UNOR INDUK"].dropna().unique() if "UNOR INDUK" in df.columns else []
        jabatans = df["NAMA JABATAN"].dropna().unique() if "NAMA JABATAN" in df.columns else []
        pendidikans = df["TINGKAT PENDIDIKAN"].dropna().unique() if "TINGKAT PENDIDIKAN" in df.columns else []

        unit_filter = st.multiselect("Filter UNOR INDUK", sorted(list(units)))
        jabatan_filter = st.multiselect("Filter Jabatan", sorted(list(jabatans)))
        pendidikan_filter = st.multiselect("Filter Pendidikan", sorted(list(pendidikans)))
        search_term = st.text_input("Pencarian global (Nama/NIP)")

        df_filtered = df.copy()
        if unit_filter: df_filtered = df_filtered[df_filtered["UNOR INDUK"].isin(unit_filter)]
        if jabatan_filter: df_filtered = df_filtered[df_filtered["NAMA JABATAN"].isin(jabatan_filter)]
        if pendidikan_filter: df_filtered = df_filtered[df_filtered["TINGKAT PENDIDIKAN"].isin(pendidikan_filter)]
        if search_term:
            df_filtered = df_filtered[
                df_filtered["NIP"].astype(str).str.contains(search_term, case=False, na=False) |
                df_filtered["NAMA"].astype(str).str.contains(search_term, case=False, na=False)
            ]

        st.metric("Total Pegawai", len(df_filtered))

        if "UNOR INDUK" in df_filtered.columns and not df_filtered.empty:
            chart_df = df_filtered["UNOR INDUK"].astype(str).str.strip().value_counts().reset_index()
            chart_df.columns = ["UNOR INDUK","JUMLAH"]
            fig = px.bar(chart_df, x="UNOR INDUK", y="JUMLAH", color="UNOR INDUK",
                         title="Pegawai per Unit Organisasi",
                         color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Kolom UNOR INDUK tidak ditemukan atau data kosong.")

        st.markdown("---")
        cols_show = ["NAMA","NIP","NAMA JABATAN","JENIS JABATAN","UNOR INDUK","NAMA UNOR","TMT JABATAN"]
        cols_show = [c for c in cols_show if c in df_filtered.columns]
        st.dataframe(df_filtered[cols_show], use_container_width=True)

        if not df_filtered.empty and (is_admin() or is_supervisor()):
            out_xlsx = BytesIO()
            with pd.ExcelWriter(out_xlsx, engine="xlsxwriter") as writer:
                df_filtered[cols_show].to_excel(writer, index=False, sheet_name="Nominatif")
                workbook = writer.book
                worksheet = writer.sheets["Nominatif"]
                header_format = workbook.add_format({"bold": True, "bg_color": "#DCE6F1"})
                for col_num, value in enumerate(df_filtered[cols_show].columns.values):
                    worksheet.write(0, col_num, value, header_format)
            st.download_button("💾 Unduh Excel", out_xlsx.getvalue(),
                               file_name="laporan_nominatif.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            st.download_button("💾 Unduh CSV",
                               df_filtered[cols_show].to_csv(index=False).encode("utf-8"),
                               file_name="laporan_nominatif.csv", mime="text/csv")
    else:
        st.info("Belum ada data pegawai untuk ditampilkan.")

# ================== Rekapitulasi ==================
elif menu == "Rekapitulasi":
    st.header("Rekapitulasi Tren TMT JABATAN")
    df = st.session_state.pegawai
    if "TMT JABATAN" in df.columns and not df.empty:
        df_ts = df.copy()
        df_ts["TMT JABATAN"] = pd.to_datetime(df_ts["TMT JABATAN"], errors="coerce")
        df_ts = df_ts.dropna(subset=["TMT JABATAN"])
        if df_ts.empty:
            st.info("Tidak ada TMT JABATAN yang valid untuk direkap.")
        else:
            units = sorted([u for u in df_ts["UNOR INDUK"].dropna().astype(str).str.strip().unique()]) if "UNOR INDUK" in df_ts.columns else []
            unit_filter = st.selectbox("Filter UNOR INDUK (opsional)", ["Semua"] + units) if len(units) > 0 else "Semua"
            df_filtered = df_ts.copy()
            if unit_filter != "Semua" and "UNOR INDUK" in df_filtered.columns:
                df_filtered = df_filtered[df_filtered["UNOR INDUK"].astype(str).str.strip() == unit_filter]

            tahun_list = sorted(df_filtered["TMT JABATAN"].dt.year.unique())
            tahun = st.selectbox("Pilih Tahun", tahun_list) if len(tahun_list) > 0 else None

            if tahun is not None:
                df_year = df_filtered[df_filtered["TMT JABATAN"].dt.year == tahun]
                rekap_bulan = df_year.groupby(df_year["TMT JABATAN"].dt.month).size().reset_index(name="JUMLAH")
                rekap_bulan["BULAN"] = rekap_bulan["TMT JABATAN"].apply(lambda x: f"Bulan {x}")
                st.subheader(f"Tren Bulanan Tahun {tahun}" + (f" • UNOR INDUK: {unit_filter}" if unit_filter != "Semua" else ""))
                st.dataframe(rekap_bulan[["BULAN","JUMLAH"]], use_container_width=True)
                st.line_chart(rekap_bulan.set_index("BULAN")["JUMLAH"])

                st.markdown("---")
                rekap_tahun = df_filtered.groupby(df_filtered["TMT JABATAN"].dt.year).size().reset_index(name="JUMLAH")
                rekap_tahun.columns = ["TAHUN","JUMLAH"]
                st.subheader("Tren Tahunan" + (f" • UNOR INDUK: {unit_filter}" if unit_filter != "Semua" else ""))
                st.dataframe(rekap_tahun, use_container_width=True)
                st.line_chart(rekap_tahun.set_index("TAHUN")["JUMLAH"])
            else:
                st.info("Tidak ada tahun yang dapat dipilih pada data terfilter.")
    else:
        st.info("Kolom TMT JABATAN belum tersedia atau kosong.")

# ================== Profil Pegawai ==================
elif menu == "Profil Pegawai":
    st.header("Profil Pegawai")
    df = st.session_state.pegawai
    if df.empty:
        st.info("Belum ada data pegawai.")
    else:
        search_nip = st.text_input("Masukkan NIP pegawai")
        search_nama = st.text_input("Atau masukkan Nama pegawai")
        df_match = pd.DataFrame()
        if search_nip:
            df_match = df[df["NIP"].astype(str) == search_nip]
        elif search_nama:
            df_match = df[df["NAMA"].astype(str).str.contains(search_nama, case=False, na=False)]

        if not df_match.empty:
            pegawai = df_match.iloc[0].to_dict()
            nip_val = str(pegawai.get("NIP",""))

            foto_path = pegawai.get("FOTO","")
            if isinstance(foto_path, str) and len(foto_path) > 0 and os.path.exists(foto_path):
                st.image(foto_path, caption=f"Foto {pegawai.get('NAMA','')}", width=200)
            else:
                st.info("Belum ada foto untuk pegawai ini.")

            st.markdown(f"""
            <div style="padding:20px;border-radius:12px;background:#f5f5f5;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                <h3 style="color:#2196f3;">{pegawai.get("NAMA","")}</h3>
                <p><b>NIP:</b> {pegawai.get("NIP","")}</p>
                <p><b>Jabatan:</b> {pegawai.get("NAMA JABATAN","")} • {pegawai.get("JENIS JABATAN","")}</p>
                <p><b>Unit:</b> {pegawai.get("NAMA UNOR","")} / {pegawai.get("UNOR INDUK","")}</p>
                <p><b>TMT Jabatan:</b> {pegawai.get("TMT JABATAN","")}</p>
                <p><b>Jenis Kelamin:</b> {pegawai.get("JENIS KELAMIN","")}</p>
                <p><b>Tanggal Lahir:</b> {pegawai.get("TANGGAL LAHIR","")}</p>
                <p><b>Pendidikan:</b> {pegawai.get("TINGKAT PENDIDIKAN","")} - {pegawai.get("NAMA PENDIDIKAN","")}</p>
                <p><b>Email:</b> {pegawai.get("EMAIL","")}</p>
                <p><b>Nomor HP:</b> {pegawai.get("NOMOR HP","")}</p>
                <p><b>Alamat:</b> {pegawai.get("ALAMAT","")}</p>
            </div>
            """, unsafe_allow_html=True)

            if is_admin() or is_supervisor():
                st.subheader("Upload/Update Foto Pegawai")
                foto_file = st.file_uploader("Pilih foto (jpg/png)", type=["jpg","jpeg","png"])
                if foto_file:
                    file_path = os.path.join("images", f"{nip_val}.jpg")
                    with open(file_path, "wb") as f: f.write(foto_file.getbuffer())
                    pegawai["FOTO"] = file_path
                    save_row(pegawai)
                    log_action(st.session_state.auth["username"], st.session_state.auth["role"], "UPDATE", f"{nip_val}-FOTO")
                    st.session_state.pegawai = load_data()
                    st.success("Foto disimpan!")

            if is_admin() or is_supervisor():
                st.subheader("Ekspor Profil (PDF)")
                pdf_data = generate_pdf_resmi(pegawai, foto_path=pegawai.get("FOTO", None))
                st.download_button("💾 Unduh Profil (PDF)", pdf_data, file_name=f"profil_{nip_val}.pdf", mime="application/pdf")
        else:
            st.warning("Pegawai tidak ditemukan. Masukkan NIP atau Nama yang valid.")

# ================== ID Card ==================
elif menu == "ID Card":
    st.header("Cetak ID Card Pegawai")
    df = st.session_state.pegawai
    if df.empty:
        st.info("Belum ada data pegawai.")
    else:
        nip_input = st.text_input("Masukkan NIP pegawai untuk ID Card")
        df_match = df[df["NIP"].astype(str) == str(nip_input)] if nip_input else pd.DataFrame()
        if not df_match.empty:
            pegawai = df_match.iloc[0].to_dict()
            st.write(f"Pegawai: {pegawai.get('NAMA','')} • NIP: {pegawai.get('NIP','')}")
            pdf_data = generate_id_card(pegawai)
            st.download_button("💳 Unduh ID Card (PDF)", pdf_data, file_name=f"idcard_{pegawai.get('NIP','')}.pdf", mime="application/pdf")
        else:
            if nip_input:
                st.warning("Pegawai tidak ditemukan. Periksa NIP.")

# ================== Backup/Hapus Data ==================
elif menu == "Backup/Hapus Data":
    st.header("Backup & Restore Data Pegawai")
    if is_admin():
        st.subheader("Backup Data Pegawai")
        df = load_data()
        if not df.empty:
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
            with open(os.path.join("backups", f"backup_pegawai_{ts}.csv"), "wb") as f: f.write(csv_bytes)
            out = BytesIO()
            with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="Pegawai")
            st.download_button("💾 Backup CSV", csv_bytes, file_name="backup_pegawai.csv", mime="text/csv")
            st.download_button("💾 Backup Excel", out.getvalue(), file_name="backup_pegawai.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("Tidak ada data pegawai untuk dibackup.")

        st.markdown("---")
        st.subheader("Restore Data Pegawai dari Backup")
        uploaded_file = st.file_uploader("Pilih file backup (CSV/Excel)", type=["csv","xlsx"])
        if uploaded_file:
            df_new = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
            df_new.columns = [str(c).strip().upper() for c in df_new.columns]
            for col in EXPECTED_COLS:
                if col not in df_new.columns: df_new[col] = ""
            st.warning("Restore akan menimpa seluruh data pegawai yang ada.")
            if st.button("Konfirmasi Restore", type="primary"):
                replace_all(df_new[EXPECTED_COLS])
                log_action(st.session_state.auth["username"], st.session_state.auth["role"], "RESTORE", "ALL")
                st.session_state.pegawai = load_data()
                st.success("Data pegawai berhasil direstore!")

        st.markdown("---")
        st.warning("Aksi ini akan menghapus semua data pegawai di SQLite dan tidak bisa dibatalkan.")
        confirm = st.checkbox("Saya paham dan ingin menghapus semua data.")
        if st.button("🗑️ Hapus Semua Data Pegawai", disabled=not confirm):
            replace_all(pd.DataFrame(columns=EXPECTED_COLS))
            log_action(st.session_state.auth["username"], st.session_state.auth["role"], "DELETE", "ALL")
            st.session_state.pegawai = load_data()
            st.success("Semua data pegawai berhasil dihapus!")
    else:
        st.warning("Menu ini hanya bisa diakses oleh Admin.")

# ================== Audit Log ==================
elif menu == "Audit Log":
    st.header("Audit Log Aktivitas")
    with conn_db() as conn:
        df_log = pd.read_sql_query("SELECT * FROM audit_log ORDER BY timestamp DESC", conn)
    if df_log.empty:
        st.info("Belum ada aktivitas tercatat.")
    else:
        role_filter = st.multiselect("Filter Role", sorted([r for r in df_log["role"].dropna().unique()]))
        action_filter = st.multiselect("Filter Action", sorted([a for a in df_log["action"].dropna().unique()]))
        search_term = st.text_input("Cari Username atau Target (mis. NIP)")
        df_filtered = df_log.copy()
        if role_filter: df_filtered = df_filtered[df_filtered["role"].isin(role_filter)]
        if action_filter: df_filtered = df_filtered[df_filtered["action"].isin(action_filter)]
        if search_term:
            df_filtered = df_filtered[
                df_filtered["user"].astype(str).str.contains(search_term, case=False, na=False) |
                df_filtered["target"].astype(str).str.contains(search_term, case=False, na=False)
            ]
        st.dataframe(df_filtered, use_container_width=True)
        st.markdown("---")
        st.subheader("Ringkasan Aktivitas")
        if not df_filtered.empty:
            summary = df_filtered.groupby("action").size().reset_index(name="Jumlah")
            st.bar_chart(summary.set_index("action"))
        else:
            st.info("Tidak ada data untuk diringkas.")
        st.markdown("---")
        st.subheader("Ekspor Audit Log")
        st.download_button("💾 Unduh CSV", df_filtered.to_csv(index=False).encode("utf-8"),
                           file_name="audit_log.csv", mime="text/csv")
        out_xlsx = BytesIO()
        with pd.ExcelWriter(out_xlsx, engine="xlsxwriter") as writer:
            df_filtered.to_excel(writer, index=False, sheet_name="AuditLog")
            workbook = writer.book; worksheet = writer.sheets["AuditLog"]
            header_format = workbook.add_format({"bold": True, "bg_color": "#DCE6F1"})
            for col_num, value in enumerate(df_filtered.columns.values):
                worksheet.write(0, col_num, value, header_format)
        st.download_button("💾 Unduh Excel", out_xlsx.getvalue(),
                           file_name="audit_log.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ================== Keamanan (Admin) ==================
elif menu == "Keamanan" and is_admin():
    st.header("🔐 Keamanan Sistem")
    st.info("Kelola reset password untuk user.")

    usernames = list(st.session_state.users.keys())
    selected_user = st.selectbox("Pilih User", usernames)

    if selected_user:
        st.subheader(f"Reset Password untuk {selected_user}")
        with st.form(f"reset_pw_{selected_user}"):
            new_pw = st.text_input("Password baru", type="password")
            submit_pw = st.form_submit_button("Reset Password")
        if submit_pw and new_pw:
            if not is_strong_password(new_pw):
                st.error("Password terlalu lemah. Minimal 8 karakter dan wajib ada huruf besar, kecil, angka, dan simbol.")
            else:
                st.session_state.users[selected_user]["password_hash"] = bcrypt.hashpw(new_pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                log_action(st.session_state.auth["username"], st.session_state.auth["role"], "RESET_PASSWORD", selected_user)
                st.success(f"Password {selected_user} berhasil direset!")

# ================== Footer ==================
st.markdown("""
<hr>
<div style="text-align:center;color:gray;font-size:14px;">
    © 2025 SIMPEG Dashboard • Dikembangkan oleh Tim IT • Powered by Streamlit
</div>
""", unsafe_allow_html=True)
