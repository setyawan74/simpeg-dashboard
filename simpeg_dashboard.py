import streamlit as st
import pandas as pd
import bcrypt
import plotly.express as px
from io import BytesIO
from fpdf import FPDF
import sqlite3
import os
from datetime import date

# ================== Konfigurasi Halaman ==================
st.set_page_config(
    page_title="SIMPEG Dashboard",
    page_icon="👥",
    layout="wide"
)

# ================== Palet Warna Konsisten ==================
COLOR_MAP = {
    "LAKI-LAKI": "#2196f3",
    "PEREMPUAN": "#e91e63",
    "SD": "#8bc34a",
    "SMP": "#4caf50",
    "SMA": "#009688",
    "D1": "#00bcd4",
    "D2": "#03a9f4",
    "D3": "#3f51b5",
    "D4": "#673ab7",
    "S1": "#9c27b0",
    "S2": "#e91e63",
    "S3": "#f44336"
}

# ================== Inisialisasi Data ==================
EXPECTED_COLS = [
    "NAMA","NIP","GELAR DEPAN","GELAR BELAKANG","TEMPAT LAHIR","TANGGAL LAHIR",
    "JENIS KELAMIN","AGAMA","JENIS KAWIN","NIK","NOMOR HP","EMAIL","ALAMAT",
    "NPWP","BPJS","JENIS PEGAWAI","KEDUDUKAN HUKUM","STATUS CPNS PNS",
    "KARTU ASN VIRTUAL","TMT CPNS","TMT PNS","GOL AWAL","GOL AKHIR",
    "TMT GOLONGAN","MK TAHUN","MK BULAN","JENIS JABATAN","NAMA JABATAN",
    "TMT JABATAN","TINGKAT PENDIDIKAN","NAMA PENDIDIKAN","NAMA UNOR","UNOR INDUK"
]

if "pegawai" not in st.session_state:
    st.session_state.pegawai = pd.DataFrame(columns=EXPECTED_COLS)

if "users" not in st.session_state:
    st.session_state.users = {
        "admin": {
            "password_hash": bcrypt.hashpw("admin123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            "role": "Admin"
        }
    }

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "username": None, "role": None}

# ================== Database & storage ==================
DB_FILE = "simpeg.db"
os.makedirs("images", exist_ok=True)

def conn_db():
    return sqlite3.connect(DB_FILE)

def init_db():
    with conn_db() as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS pegawai (
            NIP TEXT PRIMARY KEY,
            NAMA TEXT,
            NAMA_JABATAN TEXT,
            JENIS_JABATAN TEXT,
            UNOR_INDUK TEXT,
            NAMA_UNOR TEXT,
            TMT_JABATAN TEXT,
            JENIS_KELAMIN TEXT,
            TANGGAL_LAHIR TEXT,
            TINGKAT_PENDIDIKAN TEXT,
            NAMA_PENDIDIKAN TEXT,
            EMAIL TEXT,
            NOMOR_HP TEXT,
            ALAMAT TEXT,
            FOTO TEXT
        )
        """)
        conn.commit()

def load_data():
    with conn_db() as conn:
        df = pd.read_sql_query("SELECT * FROM pegawai", conn)
    return df

def save_row(row: dict):
    # Insert or replace single row by NIP
    with conn_db() as conn:
        cols = list(row.keys())
        placeholders = ",".join(["?"] * len(cols))
        values = [row[c] for c in cols]
        conn.execute(
            f"INSERT OR REPLACE INTO pegawai ({','.join(cols)}) VALUES ({placeholders})",
            values
        )
        conn.commit()

def delete_by_nip(nip: str):
    with conn_db() as conn:
        conn.execute("DELETE FROM pegawai WHERE NIP = ?", (nip,))
        conn.commit()

def replace_all(df: pd.DataFrame):
    # Replace entire table with df
    with conn_db() as conn:
        conn.execute("DELETE FROM pegawai")
        if not df.empty:
            df.to_sql("pegawai", conn, if_exists="append", index=False)

# Init DB & session pegawai
init_db()
if "pegawai" not in st.session_state:
    st.session_state.pegawai = load_data()

# ================== Auth helpers ==================
def login(username, password):
    if username in st.session_state.users:
        info = st.session_state.users[username]
        if bcrypt.checkpw(password.encode("utf-8"), info["password_hash"].encode("utf-8")):
            st.session_state.auth = {"logged_in": True, "username": username, "role": info["role"]}
            return True
    return False

def logout():
    st.session_state.auth = {"logged_in": False, "username": None, "role": None}

def is_admin():
    return st.session_state.auth["role"] == "Admin"

def is_supervisor():
    return st.session_state.auth["role"] == "Supervisor"

# ================== CSS ==================
st.markdown("""
    <style>
    .card {
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        text-align: center;
        width: 100%;
        height: 130px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        color: white;
    }
    .card h4 { margin: 0; font-size: 16px; font-weight: bold; }
    .card h2 { margin: 5px 0 0 0; font-size: 28px; }
    </style>
""", unsafe_allow_html=True)

# ================== Header ==================
st.markdown('<h1 style="text-align:center;">SISTEM INFORMASI KEPEGAWAIAN</h1>', unsafe_allow_html=True)
st.markdown('<h3 style="text-align:center;color:gray;">Halaman Admin/User/Supervisor</h3>', unsafe_allow_html=True)

# ================== Login ==================
if not st.session_state.auth["logged_in"]:
    st.sidebar.title("Login")
    with st.sidebar.form("login_form"):
        user = st.text_input("Username")
        pw = st.text_input("Password", type="password")
        submit_login = st.form_submit_button("Masuk")
    if submit_login:
        if login(user, pw):
            st.success(f"Login berhasil! Selamat datang, {user}.")
        else:
            st.error("Login gagal. Periksa username/password.")
    st.stop()

# ================== Sidebar ==================
st.sidebar.title("PANEL")
menu = st.sidebar.radio(
    "Navigasi",
    ["Dashboard", "Pegawai", "Pegawai Grafik", "Laporan", "Rekapitulasi", "Profil Pegawai", "Backup/Hapus Data"]
)
st.sidebar.write(f"Login sebagai: {st.session_state.auth['username']} ({st.session_state.auth['role']})")
if st.sidebar.button("Logout"):
    logout()
    st.stop()

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

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="card" style="background:linear-gradient(135deg,#2196f3,#21cbf3);">👨<h4>LAKI-LAKI</h4><h2>{laki}</h2></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="card" style="background:linear-gradient(135deg,#e91e63,#ff80ab);">👩<h4>PEREMPUAN</h4><h2>{perempuan}</h2></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="card" style="background:linear-gradient(135deg,#9c27b0,#ba68c8);">🔑<h4>USER</h4><h2>{user_count}</h2></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="card" style="background:linear-gradient(135deg,#4caf50,#81c784);">👥<h4>PEGAWAI</h4><h2>{total}</h2></div>', unsafe_allow_html=True)

    # Chart interaktif gender di dashboard
    if not df.empty and "JENIS KELAMIN" in df.columns:
        jk_series = df["JENIS KELAMIN"].astype(str).str.strip().str.upper()
        label_map = {
            "M":"LAKI-LAKI","L":"LAKI-LAKI","PRIA":"LAKI-LAKI","LAKI-LAKI":"LAKI-LAKI",
            "F":"PEREMPUAN","P":"PEREMPUAN","WANITA":"PEREMPUAN","PEREMPUAN":"PEREMPUAN"
        }
        jk_mapped = jk_series.map(lambda x: label_map.get(x, x))
        jk_counts = jk_mapped.value_counts().reset_index()
        jk_counts.columns = ["Jenis Kelamin","Jumlah"]
        fig = px.pie(
            jk_counts,
            names="Jenis Kelamin",
            values="Jumlah",
            color="Jenis Kelamin",
            color_discrete_map={"LAKI-LAKI": COLOR_MAP["LAKI-LAKI"], "PEREMPUAN": COLOR_MAP["PEREMPUAN"]},
            title="Distribusi Gender Pegawai"
        )
        st.plotly_chart(fig, use_container_width=True)

    if is_admin():
        st.markdown("---")
        st.subheader("➕ Tambah pengguna")
        with st.form("add_user_form"):
            u = st.text_input("Username baru")
            p = st.text_input("Password baru", type="password")
            r = st.selectbox("Role", ["Admin", "User", "Supervisor"])
            submit_u = st.form_submit_button("Tambah")
        if submit_u and u and p:
            if u in st.session_state.users:
                st.warning("Username sudah ada.")
            else:
                st.session_state.users[u] = {
                    "password_hash": bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
                    "role": r
                }
                st.success(f"Pengguna {u} ({r}) berhasil ditambahkan!")
        st.dataframe(
            pd.DataFrame([{"Username": uname, "Role": info["role"]} for uname, info in st.session_state.users.items()]),
            use_container_width=True
        )

# ================== Pegawai ==================
elif menu == "Pegawai":
    st.header("Data Pegawai")
    df = st.session_state.pegawai
    st.dataframe(df, use_container_width=True)

    if is_admin():
        st.subheader("Upload data pegawai (CSV/Excel)")
        uploaded_file = st.file_uploader("Pilih file", type=["csv", "xlsx"])
        if uploaded_file:
            df_new = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
            df_new.columns = [str(c).strip().upper() for c in df_new.columns]
            if all(col in df_new.columns for col in EXPECTED_COLS):
                st.session_state.pegawai = df_new
                st.success("Data pegawai berhasil diimpor!")
            else:
                st.error("Kolom file tidak sesuai. Harus ada semua header berikut:")
                st.write(EXPECTED_COLS)

        st.download_button(
            label="Unduh template CSV (header standar)",
            data=",".join(EXPECTED_COLS) + "\n",
            file_name="template_simpeg.csv",
            mime="text/csv"
        )

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
                "NAMA": nama,
                "NIP": nip,
                "NAMA JABATAN": jabatan,
                "NAMA UNOR": nama_unor,
                "UNOR INDUK": unor_induk,
                "TMT JABATAN": str(tmt_jabatan),
            })
            st.session_state.pegawai.loc[len(st.session_state.pegawai)] = new_row
            st.success("Pegawai ditambahkan!")

        st.subheader("Edit / Hapus Pegawai")
        nip_search = st.text_input("Masukkan NIP pegawai untuk edit/hapus")
        if nip_search:
            df_match = st.session_state.pegawai[st.session_state.pegawai["NIP"].astype(str) == str(nip_search)]
            if not df_match.empty:
                st.dataframe(df_match, use_container_width=True)
                idx = df_match.index[0]

                def default_tmt_value(val):
                    try:
                        return pd.to_datetime(val).date()
                    except Exception:
                        return date.today()

                with st.form("edit_pegawai"):
                    nama_edit = st.text_input("NAMA", value=str(df_match.iloc[0].get("NAMA", "")))
                    jabatan_edit = st.text_input("NAMA JABATAN", value=str(df_match.iloc[0].get("NAMA JABATAN", "")))
                    nama_unor_edit = st.text_input("NAMA UNOR", value=str(df_match.iloc[0].get("NAMA UNOR", "")))
                    unor_induk_edit = st.text_input("UNOR INDUK", value=str(df_match.iloc[0].get("UNOR INDUK", "")))
                    tmt_raw = df_match.iloc[0].get("TMT JABATAN", "")
                    tmt_edit = st.date_input("TMT JABATAN", value=default_tmt_value(tmt_raw))
                    submit_edit = st.form_submit_button("Simpan Perubahan")

                if submit_edit:
                    st.session_state.pegawai.at[idx, "NAMA"] = nama_edit
                    st.session_state.pegawai.at[idx, "NAMA JABATAN"] = jabatan_edit
                    st.session_state.pegawai.at[idx, "NAMA UNOR"] = nama_unor_edit
                    st.session_state.pegawai.at[idx, "UNOR INDUK"] = unor_induk_edit
                    st.session_state.pegawai.at[idx, "TMT JABATAN"] = str(tmt_edit)
                    st.success("Data pegawai berhasil diperbarui!")

                if st.button("Hapus Pegawai"):
                    st.session_state.pegawai = st.session_state.pegawai.drop(df_match.index).reset_index(drop=True)
                    st.success("Pegawai berhasil dihapus!")
            else:
                st.warning("Pegawai dengan NIP tersebut tidak ditemukan.")
    elif is_supervisor():
        st.info("Anda login sebagai Supervisor. Hanya bisa melihat data pegawai.")
    else:
        st.info("Anda login sebagai User. Hanya bisa melihat data pegawai.")

# ================== Pegawai Grafik ==================
elif menu == "Pegawai Grafik":
    st.header("Grafik Pegawai")
    df = st.session_state.pegawai

    # 1) Gender (bar chart)
    st.subheader("Distribusi Gender Pegawai")
    if not df.empty and "JENIS KELAMIN" in df.columns:
        jk_series = df["JENIS KELAMIN"].astype(str).str.strip().str.upper()
        label_map = {
            "M":"LAKI-LAKI","L":"LAKI-LAKI","PRIA":"LAKI-LAKI","LAKI-LAKI":"LAKI-LAKI",
            "F":"PEREMPUAN","P":"PEREMPUAN","WANITA":"PEREMPUAN","PEREMPUAN":"PEREMPUAN"
        }
        jk_mapped = jk_series.map(lambda x: label_map.get(x, x))
        jk_counts = jk_mapped.value_counts().reset_index()
        jk_counts.columns = ["Jenis Kelamin","Jumlah"]
        fig_gender = px.bar(
            jk_counts, x="Jenis Kelamin", y="Jumlah", color="Jenis Kelamin",
            color_discrete_map={"LAKI-LAKI": COLOR_MAP["LAKI-LAKI"], "PEREMPUAN": COLOR_MAP["PEREMPUAN"]},
            title="Distribusi Gender Pegawai"
        )
        st.plotly_chart(fig_gender, use_container_width=True)
    else:
        st.info("Data pegawai atau kolom JENIS KELAMIN belum tersedia.")

    # 2) Usia (bar chart per rentang)
    st.subheader("Distribusi Usia Pegawai")
    if not df.empty and "TANGGAL LAHIR" in df.columns:
        df_age = df.copy()
        df_age["TANGGAL LAHIR"] = pd.to_datetime(df_age["TANGGAL LAHIR"], errors="coerce")
        df_age["USIA"] = df_age["TANGGAL LAHIR"].apply(lambda x: (pd.Timestamp.today().year - x.year) if pd.notnull(x) else None)
        usia_series = df_age["USIA"].dropna().astype(int)
        if not usia_series.empty:
            bins = [0, 20, 30, 40, 50, 60, 150]
            labels = ["<20", "20–29", "30–39", "40–49", "50–59", "60+"]
            usia_bucket = pd.cut(usia_series, bins=bins, labels=labels, right=False, include_lowest=True)
            usia_counts = usia_bucket.value_counts().reindex(labels).fillna(0).astype(int).reset_index()
            usia_counts.columns = ["Rentang Usia","Jumlah"]
            fig_age = px.bar(usia_counts, x="Rentang Usia", y="Jumlah", color="Rentang Usia",
                             title="Distribusi Usia Pegawai")
            st.plotly_chart(fig_age, use_container_width=True)
        else:
            st.info("Data usia pegawai tidak tersedia atau tidak valid.")
    else:
        st.info("Kolom TANGGAL LAHIR belum tersedia.")

    # 3) Tingkat pendidikan (bar chart dengan normalisasi)
    st.subheader("Distribusi Tingkat Pendidikan Pegawai")
    if not df.empty and "TINGKAT PENDIDIKAN" in df.columns:
        pend_series = df["TINGKAT PENDIDIKAN"].astype(str).str.strip().str.upper()
        norm_map = {
            "SD":"SD","SEKOLAH DASAR":"SD","ELEMENTARY SCHOOL":"SD",
            "SMP":"SMP","SEKOLAH MENENGAH PERTAMA":"SMP","JUNIOR HIGH":"SMP",
            "SMA":"SMA","SMU":"SMA","SMK":"SMA","MA":"SMA","SEKOLAH MENENGAH ATAS":"SMA","HIGH SCHOOL":"SMA",
            "D1":"D1","DIPLOMA I":"D1",
            "D2":"D2","DIPLOMA II":"D2",
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
        # Multi filter
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

        # Ringkasan
        st.metric("Total Pegawai", len(df_filtered))

        # Grafik jumlah pegawai per UNOR INDUK
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
        # Tabel nominatif + ekspor
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
                               file_name="laporan_nominatif.csv",
                               mime="text/csv")

        # Distribusi Usia
        st.markdown("---")
        st.subheader("Distribusi Usia Pegawai")
        if "TANGGAL LAHIR" in df_filtered.columns:
            df_age = df_filtered.copy()
            df_age["TANGGAL LAHIR"] = pd.to_datetime(df_age["TANGGAL LAHIR"], errors="coerce")
            df_age["USIA"] = df_age["TANGGAL LAHIR"].apply(
                lambda x: (pd.Timestamp.today().year - x.year) if pd.notnull(x) else None
            )
            usia_series = df_age["USIA"].dropna().astype(int)
            if not usia_series.empty:
                bins = [0, 20, 30, 40, 50, 60, 150]
                labels = ["<20", "20–29", "30–39", "40–49", "50–59", "60+"]
                usia_bucket = pd.cut(usia_series, bins=bins, labels=labels, right=False, include_lowest=True)
                usia_counts = usia_bucket.value_counts().reindex(labels).fillna(0).astype(int).reset_index()
                usia_counts.columns = ["Rentang Usia","Jumlah"]
                fig_age = px.bar(usia_counts, x="Rentang Usia", y="Jumlah", color="Rentang Usia",
                                 title="Distribusi Usia Pegawai")
                st.plotly_chart(fig_age, use_container_width=True)
            else:
                st.info("Data usia pegawai tidak tersedia atau tidak valid.")
        else:
            st.info("Kolom TANGGAL LAHIR belum tersedia.")

        # Distribusi Pendidikan
        st.markdown("---")
        st.subheader("Distribusi Tingkat Pendidikan Pegawai")
        if "TINGKAT PENDIDIKAN" in df_filtered.columns:
            pend_series = df_filtered["TINGKAT PENDIDIKAN"].astype(str).str.strip().str.upper()
            norm_map = {
                "SD":"SD","SEKOLAH DASAR":"SD","ELEMENTARY SCHOOL":"SD",
                "SMP":"SMP","SEKOLAH MENENGAH PERTAMA":"SMP","JUNIOR HIGH":"SMP",
                "SMA":"SMA","SMU":"SMA","SMK":"SMA","MA":"SMA","HIGH SCHOOL":"SMA",
                "D1":"D1","DIPLOMA I":"D1",
                "D2":"D2","DIPLOMA II":"D2",
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

        # Tren Jabatan per Tahun & Bulan
        st.markdown("---")
        st.subheader("Tren Jabatan per Tahun (berdasarkan TMT JABATAN)")
        if "TMT JABATAN" in df_filtered.columns:
            df_ts = df_filtered.copy()
            df_ts["TMT JABATAN"] = pd.to_datetime(df_ts["TMT JABATAN"], errors="coerce")
            df_ts = df_ts.dropna(subset=["TMT JABATAN"])
            if not df_ts.empty:
                rekap_tahun = df_ts.groupby(df_ts["TMT JABATAN"].dt.year).size().reset_index(name="JUMLAH")
                rekap_tahun.columns = ["TAHUN","JUMLAH"]
                fig_tren = px.line(rekap_tahun, x="TAHUN", y="JUMLAH", markers=True,
                                   title="Jumlah Pegawai berdasarkan TMT JABATAN per Tahun")
                st.plotly_chart(fig_tren, use_container_width=True)

                tahun_list = sorted(df_ts["TMT JABATAN"].dt.year.unique())
                tahun_pilih = st.selectbox("Pilih Tahun untuk Tren Bulanan", tahun_list) if len(tahun_list) > 0 else None
                if tahun_pilih:
                    df_year = df_ts[df_ts["TMT JABATAN"].dt.year == tahun_pilih]
                    rekap_bulan = df_year.groupby(df_year["TMT JABATAN"].dt.month).size().reset_index(name="JUMLAH")
                    rekap_bulan["BULAN"] = rekap_bulan["TMT JABATAN"].apply(lambda x: f"Bulan {x}")
                    fig_bulan = px.bar(rekap_bulan, x="BULAN", y="JUMLAH", color="BULAN",
                                       title=f"Distribusi Jabatan per Bulan • Tahun {tahun_pilih}")
                    st.plotly_chart(fig_bulan, use_container_width=True)
            else:
                st.info("Tidak ada data TMT JABATAN yang valid.")
        else:
            st.info("Kolom TMT JABATAN belum tersedia.")

        # Tren Pendidikan per Tahun
        st.markdown("---")
        st.subheader("Tren Pendidikan Pegawai per Tahun (berdasarkan TMT JABATAN)")
        if "TMT JABATAN" in df_filtered.columns and "TINGKAT PENDIDIKAN" in df_filtered.columns:
            df_pend_tren = df_filtered.copy()
            df_pend_tren["TMT JABATAN"] = pd.to_datetime(df_pend_tren["TMT JABATAN"], errors="coerce")
            df_pend_tren = df_pend_tren.dropna(subset=["TMT JABATAN"])
            if not df_pend_tren.empty:
                df_pend_tren["TAHUN"] = df_pend_tren["TMT JABATAN"].dt.year
                norm_map = {
                    "SD":"SD","SEKOLAH DASAR":"SD","ELEMENTARY SCHOOL":"SD",
                    "SMP":"SMP","SEKOLAH MENENGAH PERTAMA":"SMP","JUNIOR HIGH":"SMP",
                    "SMA":"SMA","SMU":"SMA","SMK":"SMA","MA":"SMA","HIGH SCHOOL":"SMA",
                    "D1":"D1","DIPLOMA I":"D1",
                    "D2":"D2","DIPLOMA II":"D2",
                    "D3":"D3","DIPLOMA III":"D3","AHLI MADYA":"D3",
                    "D4":"D4","DIPLOMA IV":"D4","SARJANA TERAPAN":"D4",
                    "S1":"S1","SARJANA":"S1","UNDERGRADUATE":"S1","BACHELOR":"S1",
                    "S2":"S2","MAGISTER":"S2","MASTER":"S2","POSTGRADUATE":"S2",
                    "S3":"S3","DOKTOR":"S3","PHD":"S3","DOCTORATE":"S3"
                }
                df_pend_tren["TINGKAT PENDIDIKAN"] = df_pend_tren["TINGKAT PENDIDIKAN"].astype(str).str.strip().str.upper()
                df_pend_tren["TINGKAT PENDIDIKAN"] = df_pend_tren["TINGKAT PENDIDIKAN"].map(lambda x: norm_map.get(x, x))
                rekap_pend_tahun = df_pend_tren.groupby(["TAHUN","TINGKAT PENDIDIKAN"]).size().reset_index(name="JUMLAH")
                fig_pend_tren = px.line(rekap_pend_tahun, x="TAHUN", y="JUMLAH", color="TINGKAT PENDIDIKAN",
                                        markers=True, title="Tren Pendidikan Pegawai per Tahun")
                st.plotly_chart(fig_pend_tren, use_container_width=True)
            else:
                st.info("Tidak ada data TMT JABATAN yang valid untuk rekap pendidikan.")
        else:
            st.info("Kolom TMT JABATAN atau TINGKAT PENDIDIKAN belum tersedia.")

        # Tren Gender per Tahun
        st.markdown("---")
        st.subheader("Tren Gender Pegawai per Tahun (berdasarkan TMT JABATAN)")
        if "TMT JABATAN" in df_filtered.columns and "JENIS KELAMIN" in df_filtered.columns:
            df_gender_tren = df_filtered.copy()
            df_gender_tren["TMT JABATAN"] = pd.to_datetime(df_gender_tren["TMT JABATAN"], errors="coerce")
            df_gender_tren = df_gender_tren.dropna(subset=["TMT JABATAN"])
            if not df_gender_tren.empty:
                df_gender_tren["TAHUN"] = df_gender_tren["TMT JABATAN"].dt.year
                label_map = {
                    "M":"LAKI-LAKI","L":"LAKI-LAKI","PRIA":"LAKI-LAKI","LAKI-LAKI":"LAKI-LAKI",
                    "F":"PEREMPUAN","P":"PEREMPUAN","WANITA":"PEREMPUAN","PEREMPUAN":"PEREMPUAN"
                }
                df_gender_tren["JENIS KELAMIN"] = df_gender_tren["JENIS KELAMIN"].astype(str).str.strip().str.upper()
                df_gender_tren["JENIS KELAMIN"] = df_gender_tren["JENIS KELAMIN"].map(lambda x: label_map.get(x, x))
                rekap_gender_tahun = df_gender_tren.groupby(["TAHUN","JENIS KELAMIN"]).size().reset_index(name="JUMLAH")
                fig_gender_tren = px.line(rekap_gender_tahun, x="TAHUN", y="JUMLAH", color="JENIS KELAMIN",
                                          markers=True, title="Tren Gender Pegawai per Tahun",
                                          color_discrete_map={"LAKI-LAKI": COLOR_MAP["LAKI-LAKI"], "PEREMPUAN": COLOR_MAP["PEREMPUAN"]})
                st.plotly_chart(fig_gender_tren, use_container_width=True)
            else:
                st.info("Tidak ada data TMT JABATAN yang valid untuk rekap gender.")
        else:
            st.info("Kolom TMT JABATAN atau JENIS KELAMIN belum tersedia.")
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
                st.dataframe(rekap_bulan[["BULAN", "JUMLAH"]], use_container_width=True)
                st.line_chart(rekap_bulan.set_index("BULAN")["JUMLAH"])

                st.markdown("---")
                rekap_tahun = df_filtered.groupby(df_filtered["TMT JABATAN"].dt.year).size().reset_index(name="JUMLAH")
                rekap_tahun.columns = ["TAHUN", "JUMLAH"]
                st.subheader("Tren Tahunan" + (f" • UNOR INDUK: {unit_filter}" if unit_filter != "Semua" else ""))
                st.dataframe(rekap_tahun, use_container_width=True)
                st.line_chart(rekap_tahun.set_index("TAHUN")["JUMLAH"])
            else:
                st.info("Tidak ada tahun yang dapat dipilih pada data terfilter.")
    else:
        st.info("Kolom TMT JABATAN belum tersedia atau kosong.")

    # Indikator hak akses di Rekapitulasi
    if is_admin():
        st.success("Anda Admin: punya akses penuh termasuk Backup/Hapus Data.")
    elif is_supervisor():
        st.info("Anda Supervisor: bisa melihat tren, tanpa akses Backup/Hapus Data.")
    else:
        st.info("Anda User: hanya bisa melihat tren.")

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
            nip_val = str(pegawai.get("NIP", ""))

            # Foto
            foto_path = pegawai.get("FOTO", "")
            if isinstance(foto_path, str) and len(foto_path) > 0 and os.path.exists(foto_path):
                st.image(foto_path, caption=f"Foto {pegawai.get('NAMA','')}", width=200)
            else:
                st.info("Belum ada foto untuk pegawai ini.")

            # Detail
            st.markdown(f"""
            <div style="padding:20px;border-radius:12px;background:#f5f5f5;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                <h3 style="color:#2196f3;">{pegawai.get("NAMA","")}</h3>
                <p><b>NIP:</b> {pegawai.get("NIP","")}</p>
                <p><b>Jabatan:</b> {pegawai.get("NAMA_JABATAN","")} • {pegawai.get("JENIS_JABATAN","")}</p>
                <p><b>Unit:</b> {pegawai.get("NAMA_UNOR","")} / {pegawai.get("UNOR_INDUK","")}</p>
                <p><b>TMT Jabatan:</b> {pegawai.get("TMT_JABATAN","")}</p>
                <p><b>Jenis Kelamin:</b> {pegawai.get("JENIS_KELAMIN","")}</p>
                <p><b>Tanggal Lahir:</b> {pegawai.get("TANGGAL_LAHIR","")}</p>
                <p><b>Pendidikan:</b> {pegawai.get("TINGKAT_PENDIDIKAN","")} - {pegawai.get("NAMA_PENDIDIKAN","")}</p>
                <p><b>Email:</b> {pegawai.get("EMAIL","")}</p>
                <p><b>Nomor HP:</b> {pegawai.get("NOMOR_HP","")}</p>
                <p><b>Alamat:</b> {pegawai.get("ALAMAT","")}</p>
            </div>
            """, unsafe_allow_html=True)

            # Upload foto
            if is_admin() or is_supervisor():
                st.subheader("Upload/Update Foto Pegawai")
                foto_file = st.file_uploader("Pilih foto (jpg/png)", type=["jpg","jpeg","png"])
                if foto_file:
                    file_path = os.path.join("images", f"{nip_val}.jpg")
                    with open(file_path, "wb") as f:
                        f.write(foto_file.getbuffer())
                    pegawai["FOTO"] = file_path
                    save_row(pegawai)
                    st.session_state.pegawai = load_data()
                    st.success("Foto disimpan!")

            # Ekspor PDF resmi + foto
            if is_admin() or is_supervisor():
                st.subheader("Ekspor Profil Pegawai ke PDF (Resmi + Foto)")
                def generate_pdf_resmi(data, foto_path=None):
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_fill_color(33, 150, 243)
                    pdf.set_text_color(255, 255, 255)
                    pdf.set_font("Arial", "B", 16)
                    pdf.cell(0, 12, "PROFIL PEGAWAI", ln=True, align="C", fill=True)
                    pdf.ln(8)
                    if foto_path and os.path.exists(foto_path):
                        try:
                            pdf.image(foto_path, x=160, y=22, w=30, h=40)
                        except:
                            pass
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font("Arial", size=12)
                    pdf.ln(20)
                    labels = [
                        "NAMA","NIP","NAMA_JABATAN","JENIS_JABATAN","NAMA_UNOR","UNOR_INDUK","TMT_JABATAN",
                        "JENIS_KELAMIN","TANGGAL_LAHIR","TINGKAT_PENDIDIKAN","NAMA_PENDIDIKAN","EMAIL","NOMOR_HP","ALAMAT"
                    ]
                    for key in labels:
                        val = str(data.get(key, ""))
                        pdf.cell(60, 9, key, border=1)
                        pdf.cell(0, 9, val, border=1, ln=True)
                    return pdf.output(dest="S").encode("latin-1")

                pdf_data = generate_pdf_resmi(pegawai, foto_path=pegawai.get("FOTO", None))
                st.download_button("💾 Unduh Profil (PDF)", pdf_data,
                                   file_name=f"profil_{nip_val}.pdf", mime="application/pdf")
        else:
            st.warning("Pegawai tidak ditemukan. Masukkan NIP atau Nama yang valid.")


# ================== Backup / Hapus Data ==================
elif menu == "Backup/Hapus Data":
    st.header("Backup & Hapus Data Pegawai")
    if is_admin():
        df = st.session_state.pegawai

        if not df.empty:
            csv_data = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="💾 Backup Data Pegawai (CSV)",
                data=csv_data,
                file_name="backup_pegawai.csv",
                mime="text/csv"
            )
            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="Pegawai")
            excel_data = output.getvalue()
            st.download_button(
                label="💾 Backup Data Pegawai (Excel)",
                data=excel_data,
                file_name="backup_pegawai.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Tidak ada data pegawai untuk dibackup.")

        st.markdown("---")
        st.warning("Aksi ini akan menghapus semua data pegawai dan tidak bisa dibatalkan.")
        confirm = st.checkbox("Saya paham dan ingin menghapus semua data.")
        if st.button("🗑️ Hapus Semua Data Pegawai", disabled=not confirm):
            st.session_state.pegawai = pd.DataFrame(columns=EXPECTED_COLS)
            st.success("Semua data pegawai berhasil dihapus!")
    else:
        st.warning("Menu ini hanya bisa diakses oleh Admin.")

# ================== Footer ==================
st.markdown("""
<hr>
<div style="text-align:center;color:gray;font-size:14px;">
    © 2025 SIMPEG Dashboard • Dikembangkan oleh Tim IT • Powered by Streamlit
</div>
""", unsafe_allow_html=True)
