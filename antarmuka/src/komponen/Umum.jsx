import { useEffect } from "react";
import { KELAS_KATEGORI } from "../api.js";

// Lencana berwarna untuk kategori kualitas udara.
export function Lencana({ kategori }) {
  if (!kategori) return <span className="lencana abu">Belum ada</span>;
  return (
    <span className={`lencana ${KELAS_KATEGORI[kategori] || "abu"}`}>
      {kategori}
    </span>
  );
}

// Penanda bahwa data sedang dimuat.
export function Memuat({ pesan = "Memuat data…" }) {
  return <div className="tengah">{pesan}</div>;
}

// Kotak pesan galat.
export function Galat({ pesan }) {
  return <div className="catatan galat">{pesan}</div>;
}

// Pesan untuk keadaan tanpa data.
export function Kosong({ pesan }) {
  return <div className="tengah">{pesan}</div>;
}

// Daftar tombol halaman ringkas: selalu tampil halaman pertama, terakhir, dan
// tetangga halaman aktif; sisanya diganti elipsis. Contoh (aktif=6 dari 12):
// 1 … 5 6 7 … 12
function itemHalaman(aktif, total, tetangga = 1, batas = 1) {
  const rentang = (a, b) => Array.from({ length: b - a + 1 }, (_, i) => a + i);
  const awal = rentang(1, Math.min(batas, total));
  const akhir = rentang(Math.max(total - batas + 1, batas + 1), total);
  const mulaiTengah = Math.max(
    Math.min(aktif - tetangga, total - batas - tetangga * 2 - 1),
    batas + 2,
  );
  const akhirTengah = Math.min(
    Math.max(aktif + tetangga, batas + tetangga * 2 + 2),
    akhir.length ? akhir[0] - 2 : total - 1,
  );
  return [
    ...awal,
    ...(mulaiTengah > batas + 2
      ? ["…awal"]
      : batas + 1 < total - batas
        ? [batas + 1]
        : []),
    ...rentang(mulaiTengah, akhirTengah),
    ...(akhirTengah < total - batas - 1
      ? ["…akhir"]
      : total - batas > batas
        ? [total - batas]
        : []),
    ...akhir,
  ];
}

/** Navigasi halaman untuk tabel: ‹ 1 2 3 4 5 … 12 › */
export function Halaman({ aktif, total, onUbah }) {
  if (total <= 1) return null;
  return (
    <nav className="halaman" aria-label="Navigasi halaman">
      <button
        disabled={aktif === 1}
        aria-label="Halaman sebelumnya"
        onClick={() => onUbah(aktif - 1)}
      >
        ‹
      </button>
      {itemHalaman(aktif, total).map((n) =>
        typeof n === "string" ? (
          <span key={n} className="elipsis">
            …
          </span>
        ) : (
          <button
            key={n}
            className={n === aktif ? "aktif" : ""}
            aria-label={`Halaman ${n}`}
            aria-current={n === aktif ? "page" : undefined}
            onClick={() => onUbah(n)}
          >
            {n}
          </button>
        ),
      )}
      <button
        disabled={aktif === total}
        aria-label="Halaman berikutnya"
        onClick={() => onUbah(aktif + 1)}
      >
        ›
      </button>
    </nav>
  );
}

/** Keterangan kemutakhiran data — dijanjikan naskah Subbab 2.1.1. */
export function Kemutakhiran({ data }) {
  if (!data) return null;
  if (data.mutakhir) {
    return (
      <div className="catatan info">
        Data mutakhir. Pengamatan terakhir pukul{" "}
        <b>{new Date(data.waktu_data_terakhir).toLocaleString("id-ID")}</b>.
      </div>
    );
  }
  return (
    <div className="catatan ingat">
      Data belum diperbarui
      {data.waktu_data_terakhir ? (
        <>
          {" "}
          — terakhir tercatat pada{" "}
          <b>{new Date(data.waktu_data_terakhir).toLocaleString("id-ID")}</b>
          {data.tertinggal_jam != null && (
            <> (tertinggal {data.tertinggal_jam} jam)</>
          )}
        </>
      ) : (
        <> — belum ada data pengamatan untuk lokasi ini</>
      )}
      . Prediksi untuk jam yang sudah lewat tidak ditampilkan.
    </div>
  );
}

/** Dialog pemberitahuan mengambang — dipakai sinkronisasi manual Monitoring.
 *
 * Mengganti spanduk statis yang dulu muncul di bawah baris tombol: admin yang
 * sudah menggulir tabel tidak melihatnya, sehingga penarikan yang berjalan
 * belasan detik terasa seperti klik yang tidak berefek. Dialog ini menahan
 * halaman selagi proses berjalan (tanpa tombol tutup), lalu berganti menjadi
 * ringkasan berhasil/gagal yang harus ditutup admin.
 *
 * jenis: 'memuat' | 'berhasil' | 'galat'
 */
export function Sorot({ jenis, judul, pesan, tutup }) {
  const sedang = jenis === "memuat";

  useEffect(() => {
    if (sedang || !tutup) return;
    function padaTombol(e) {
      if (e.key === "Escape") tutup();
    }
    window.addEventListener("keydown", padaTombol);
    return () => window.removeEventListener("keydown", padaTombol);
  }, [sedang, tutup]);

  return (
    <div
      className="sorot-tirai"
      onClick={sedang ? undefined : tutup}
      role="alertdialog"
      aria-modal="true"
      aria-busy={sedang || undefined}
    >
      <div className="sorot-kotak" onClick={(e) => e.stopPropagation()}>
        <div className={`sorot-ikon ${jenis}`} aria-hidden="true">
          {jenis === "memuat" && <span className="sorot-putar" />}
          {jenis === "berhasil" && "✓"}
          {jenis === "galat" && "!"}
        </div>
        <h2>{judul}</h2>
        {pesan && <p>{pesan}</p>}
        {!sedang && (
          <button className="utama" onClick={tutup} autoFocus>
            Tutup
          </button>
        )}
      </div>
    </div>
  );
}
