import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import Swal from "sweetalert2";
import { hapusToken } from "../api.js";
import ProfilAdmin from "./ProfilAdmin.jsx";

// Batas lebar layar ponsel/tablet; harus sama dengan @media di gaya.css.
const MEDIA_PONSEL = "(max-width: 860px)";

// Modul Sidebar: menu menyesuaikan peran pengguna — terbatas bagi pengunjung,
// lengkap bagi admin (naskah Subbab 3.1). Pada layar sempit sidebar berubah
// menjadi bilah atas dengan menu hamburger yang meluncur dari atas.
export default function Sidebar({ pengguna, setPengguna }) {
  const navigasi = useNavigate();
  const lokasi = useLocation();
  const kelas = ({ isActive }) => (isActive ? "aktif" : "");
  const [bukaProfil, setBukaProfil] = useState(false);
  const [bukaMenu, setBukaMenu] = useState(false);
  const pemicuMenu = useRef(null);

  // Menu ditutup setiap kali halaman berpindah.
  useEffect(() => {
    setBukaMenu(false);
  }, [lokasi.pathname]);

  // Selama menu terbuka: halaman di belakang tidak ikut tergulir, tombol Esc
  // menutup menu, dan menu ikut tertutup bila layar dilebarkan ke mode desktop.
  useEffect(() => {
    if (!bukaMenu) return;
    const media = window.matchMedia(MEDIA_PONSEL);
    const tutupBilaLebar = () => !media.matches && setBukaMenu(false);
    const tekanTuts = (e) => {
      if (e.key === "Escape") {
        setBukaMenu(false);
        pemicuMenu.current?.focus();
      }
    };
    const luapanSemula = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", tekanTuts);
    media.addEventListener("change", tutupBilaLebar);
    return () => {
      document.body.style.overflow = luapanSemula;
      document.removeEventListener("keydown", tekanTuts);
      media.removeEventListener("change", tutupBilaLebar);
    };
  }, [bukaMenu]);

  // Keluar: meminta konfirmasi lebih dulu, lalu menghapus token,
  // mengosongkan pengguna, dan kembali ke Beranda.
  async function keluar() {
    const hasil = await Swal.fire({
      title: "Yakin ingin keluar?",
      text: "Anda harus masuk lagi untuk membuka menu admin.",
      icon: "warning",
      width: 360,
      customClass: {
        popup: "swal-ringkas",
        title: "swal-ringkas-judul",
        htmlContainer: "swal-ringkas-teks",
        icon: "swal-ringkas-ikon",
        actions: "swal-ringkas-aksi",
        confirmButton: "swal-ringkas-tombol",
        cancelButton: "swal-ringkas-tombol",
      },
      showCancelButton: true,
      confirmButtonText: "Ya, keluar",
      cancelButtonText: "Batal",
      confirmButtonColor: "#c62828",
      cancelButtonColor: "#5b6b7a",
      reverseButtons: true,
      focusCancel: true,
    });
    if (!hasil.isConfirmed) return;
    setBukaMenu(false);
    hapusToken();
    setPengguna(null);
    navigasi("/");
  }

  function lihatProfil() {
    setBukaMenu(false);
    setBukaProfil(true);
  }

  return (
    <aside className={bukaMenu ? "sisi menu-terbuka" : "sisi"}>
      {/* Blok merek. Lambang yang dipakai di sini versi monokrom putih:
          sidebar berlatar --biru (#16507a) dan lambang berwarna penuh
          bernavy, rasio kontras keduanya hanya sekitar 1,3:1 sehingga
          lambang berwarna akan tenggelam. Versi berwarna penuh dipakai
          pada latar terang (favicon, halaman Tentang).
          Kata SELTERRA ditulis sebagai teks, bukan gambar wordmark, supaya
          tetap tajam di segala ukuran, terbaca pembaca layar, dan bisa
          diputihkan lewat CSS — berkas wordmark yang ada bernavy. */}
      <div className="judul">
        {/* Tombol hamburger hanya tampil di layar sempit (lihat gaya.css). */}
        <button
          ref={pemicuMenu}
          type="button"
          className="menu-pemicu"
          onClick={() => setBukaMenu((b) => !b)}
          aria-expanded={bukaMenu}
          aria-controls="sisi-panel"
          aria-label={bukaMenu ? "Tutup menu" : "Buka menu"}
        >
          <span aria-hidden="true" />
          <span aria-hidden="true" />
          <span aria-hidden="true" />
        </button>
        <Link to="/" className="merek" aria-label="SELTERRA — ke Beranda">
          <img
            src="/logo-putih.png"
            alt=""
            aria-hidden="true"
            className="merek-logo"
          />
          <span className="merek-nama">
            <b>SEL</b>TERRA
          </span>
        </Link>
      </div>

      {/* Tirai gelap di belakang menu ponsel; mengetuknya menutup menu. */}
      <div
        className="sisi-tirai"
        onClick={() => setBukaMenu(false)}
        aria-hidden="true"
      />

      {/* Di desktop pembungkus ini memakai display: contents sehingga nav dan
          kaki tetap tersusun seperti sidebar biasa; di ponsel ia menjadi panel
          yang meluncur turun dari bawah bilah atas. */}
      <div className="sisi-panel" id="sisi-panel">
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
              <NavLink to="/monev" className={kelas}>
                MonEv SO₂
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
                onClick={lihatProfil}
                aria-haspopup="dialog"
                title="Lihat profil admin"
              >
                <span className="profil-awalan kecil-awalan" aria-hidden="true">
                  {(pengguna.nama_lengkap || "?")
                    .trim()
                    .charAt(0)
                    .toUpperCase()}
                </span>
                <span className="profil-pemicu-teks">
                  <span className="nama">{pengguna.nama_lengkap}</span>
                  <span className="peran">{pengguna.peran}</span>
                </span>
              </button>
              <button className="tombol-keluar" onClick={keluar}>
                Keluar
              </button>
            </>
          ) : (
            <NavLink to="/masuk" style={{ padding: 0, border: 0 }}>
              Masuk sebagai admin
            </NavLink>
          )}
        </div>
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
