import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { hapusToken } from "../api.js";
import ProfilAdmin from "./ProfilAdmin.jsx";

// Modul Sidebar: menu menyesuaikan peran pengguna — terbatas bagi pengunjung,
// lengkap bagi admin (naskah Subbab 3.1).
export default function Sidebar({ pengguna, setPengguna }) {
  const navigasi = useNavigate();
  const kelas = ({ isActive }) => (isActive ? "aktif" : "");
  const [bukaProfil, setBukaProfil] = useState(false);

  function keluar() {
    hapusToken();
    setPengguna(null);
    navigasi("/");
  }

  return (
    <aside className="sisi">
      <div className="judul">
        <b>Prediksi SO₂ Jabodetabek</b>
        <span>Satu jam ke depan · sepuluh sel grid</span>
      </div>

      <nav>
        <NavLink to="/" end className={kelas}>
          Beranda
        </NavLink>
        <NavLink to="/prediksi" className={kelas}>
          Prediksi SO₂
        </NavLink>
        <NavLink to="/visualisasi" className={kelas}>
          Visualisasi Riwayat
        </NavLink>
        <NavLink to="/lokasi" className={kelas}>
          Informasi Lokasi
        </NavLink>
        <NavLink to="/faq" className={kelas}>
          FAQ
        </NavLink>
        <NavLink to="/tentang" className={kelas}>
          Tentang
        </NavLink>

        {pengguna && (
          <>
            <div className="kelompok">Admin</div>
            <NavLink to="/monitoring" className={kelas}>
              Monitoring Data
            </NavLink>
            <NavLink to="/riwayat" className={kelas}>
              Riwayat Prediksi
            </NavLink>
          </>
        )}
      </nav>

      <div className="kaki">
        {pengguna ? (
          <>
            {/* Baris nama dibuat tombol supaya pop-up Profil Admin terbuka
                dengan klik maupun dengan papan tuts. */}
            <button
              className="profil-pemicu"
              onClick={() => setBukaProfil(true)}
              aria-haspopup="dialog"
              title="Lihat profil admin"
            >
              <span className="profil-awalan kecil-awalan" aria-hidden="true">
                {(pengguna.nama_lengkap || "?").trim().charAt(0).toUpperCase()}
              </span>
              <span className="profil-pemicu-teks">
                <span className="nama">{pengguna.nama_lengkap}</span>
                <span className="peran">{pengguna.peran}</span>
              </span>
            </button>
            <button onClick={keluar}>Keluar</button>
          </>
        ) : (
          <NavLink to="/masuk" style={{ padding: 0, border: 0 }}>
            Masuk sebagai admin
          </NavLink>
        )}
      </div>

      {bukaProfil && pengguna && (
        <ProfilAdmin
          pengguna={pengguna}
          setPengguna={setPengguna}
          tutup={() => setBukaProfil(false)}
        />
      )}
    </aside>
  );
}
