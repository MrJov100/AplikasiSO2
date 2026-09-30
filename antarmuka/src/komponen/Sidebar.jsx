import { NavLink, useNavigate } from "react-router-dom";
import { hapusToken } from "../api.js";

// Modul Sidebar: menu menyesuaikan peran pengguna — terbatas bagi pengunjung,
// lengkap bagi admin (naskah Subbab 3.1).
export default function Sidebar({ pengguna, setPengguna }) {
  const navigasi = useNavigate();
  const kelas = ({ isActive }) => (isActive ? "aktif" : "");

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
            <div>{pengguna.nama_lengkap}</div>
            <div className="kecil" style={{ opacity: 0.7 }}>
              {pengguna.peran}
            </div>
            <button onClick={keluar}>Keluar</button>
          </>
        ) : (
          <NavLink to="/masuk" style={{ padding: 0, border: 0 }}>
            Masuk sebagai admin
          </NavLink>
        )}
      </div>
    </aside>
  );
}
