"""Lima lapis validasi pengamatan (naskah Subbab 2.1, "validasi berlapis").

Lapis 1  Batas fisika keras            — kekangan CHECK pada DDL, ditolak saat
                                          penyisipan. Tidak ditangani di sini.
Lapis 2  Aturan fisika lintas variabel — titik embun <= suhu, dan kelembapan
                                          harus konsisten dengan suhu serta
                                          titik embun menurut rumus Magnus.
Lapis 3  Pita tekanan permukaan        — pendeteksi salah sel.
Lapis 4  Persentil aras per sel        — P0,01 dan P99,99 dari data latih.
Lapis 5  Lonjakan SO2 antarjam         — P99,9 per sel, ambang terpisah untuk
                                          jam batas run (07, 08, 09, 19, 20 WIB).

Lapis 2 dan 3 nol pelanggaran sepanjang 363.770 baris data latih, jadi laju
alarm palsunya mendekati nol; pelanggaran di situ berarti data benar-benar
rusak. Lapis 4 dan 5 adalah ekor sebaran, sehingga wajar sesekali menandai
nilai yang sah tetapi luar biasa — itu memang tujuannya, meminta admin melihat.

Ambang dibaca dari ambang_anomali.json yang dihasilkan 08_hitung_ambang_anomali.sql.
"""
import json
import math
from functools import lru_cache

from konfigurasi import BERKAS_AMBANG

# Kolom pengamatan bernama seperti di basis data, bukan seperti di berkas model.
JAM_BATAS_RUN = (7, 8, 9, 19, 20)
BATAS_ALASAN = 100          # lebar kolom pengamatan.alasan_anomali


@lru_cache(maxsize=1)
def muat_ambang():
    """Baca berkas ambang sekali lalu simpan di memori."""
    if not BERKAS_AMBANG.exists():
        raise FileNotFoundError(
            f"Berkas ambang tidak ditemukan: {BERKAS_AMBANG}\n"
            "Hasilkan dengan SQL/08_hitung_ambang_anomali.sql, atau setel "
            "BERKAS_AMBANG pada .env.")
    return json.loads(BERKAS_AMBANG.read_text(encoding="utf-8"))


def _tekanan_uap(t):
    """Tekanan uap jenuh menurut rumus Magnus, dalam hPa."""
    return 6.112 * math.exp(17.67 * t / (t + 243.5))


def kelembapan_magnus(suhu, titik_embun):
    """Kelembapan relatif yang seharusnya, dihitung dari suhu dan titik embun."""
    return 100.0 * _tekanan_uap(titik_embun) / _tekanan_uap(suhu)


def periksa(kode_sel, baris, so2_sebelumnya=None):
    """Terapkan lapis 2 sampai 5 pada satu baris pengamatan.

    baris            dict berkunci nama kolom basis data (so2, suhu, kelembapan,
                     titik_embun, curah_hujan, tekanan_permukaan, tutupan_awan,
                     kecepatan_angin, arah_angin, waktu)
    so2_sebelumnya   nilai SO2 jam sebelumnya, untuk lapis 5. None berarti jam
                     sebelumnya tidak diketahui dan lapis 5 dilewati.

    Return: (status, alasan) — status 'sah' atau 'anomali'; alasan None bila sah.
    """
    a = muat_ambang()
    sel = a["sel"][kode_sel]
    alasan = []

    # --- Lapis 2: aturan fisika lintas variabel -----------------------------
    if baris["titik_embun"] > baris["suhu"] + a["toleransi_titik_embun"]:
        alasan.append("titik embun melebihi suhu")

    selisih_rh = abs(baris["kelembapan"] - kelembapan_magnus(baris["suhu"],
                                                             baris["titik_embun"]))
    if selisih_rh > a["toleransi_magnus_persen"]:
        alasan.append("kelembapan tidak konsisten")

    # --- Lapis 3: pita tekanan, pendeteksi salah sel ------------------------
    if abs(baris["tekanan_permukaan"] - sel["tekanan_median"]) > a["pita_tekanan_hpa"]:
        alasan.append("tekanan di luar pita sel")

    # --- Lapis 4: persentil aras per sel ------------------------------------
    # arah_angin dan tutupan_awan sengaja tidak diberi ambang persentil:
    # yang pertama sirkular, yang kedua dwimodal. Keduanya dijaga kekangan CHECK.
    if baris["so2"] > sel["so2_atas"]:
        alasan.append("SO2 luar kebiasaan")
    if not (sel["suhu_bawah"] <= baris["suhu"] <= sel["suhu_atas"]):
        alasan.append("suhu luar kebiasaan")
    if baris["kelembapan"] < sel["kelembapan_bawah"]:
        alasan.append("kelembapan luar kebiasaan")
    if not (sel["titik_embun_bawah"] <= baris["titik_embun"] <= sel["titik_embun_atas"]):
        alasan.append("titik embun luar kebiasaan")
    if baris["curah_hujan"] > sel["curah_hujan_atas"]:
        alasan.append("curah hujan luar kebiasaan")
    if baris["kecepatan_angin"] > sel["kecepatan_angin_atas"]:
        alasan.append("kecepatan angin luar kebiasaan")

    # --- Lapis 5: lonjakan SO2 antarjam -------------------------------------
    # Ambang dipisah menurut jam. Jam 07 dan 19 WIB adalah 00z dan 12z, waktu
    # inisialisasi run; 81% lonjakan ekstrem terjadi di situ, sehingga ambang
    # gabungan hanya akan mengulang artefak batas run yang sudah diketahui.
    if so2_sebelumnya is not None:
        lonjakan = abs(baris["so2"] - so2_sebelumnya)
        di_batas = baris["waktu"].hour in JAM_BATAS_RUN
        ambang = sel["so2_lonjakan_atas_jam_batas" if di_batas
                     else "so2_lonjakan_atas_jam_lain"]
        if lonjakan > ambang:
            alasan.append("lonjakan SO2 pada batas run" if di_batas
                          else "lonjakan SO2 antarjam")

    if not alasan:
        return "sah", None

    # Kolom alasan_anomali hanya selebar 100 karakter. Kalau gabungan alasannya
    # lebih panjang, sisanya diringkas menjadi jumlah supaya tidak ada informasi
    # yang hilang diam-diam.
    teks = "; ".join(alasan)
    if len(teks) > BATAS_ALASAN:
        dipakai, panjang = [], 0
        for x in alasan:
            tambahan = len(x) + (2 if dipakai else 0)
            if panjang + tambahan > BATAS_ALASAN - 12:
                break
            dipakai.append(x); panjang += tambahan
        sisa = len(alasan) - len(dipakai)
        teks = "; ".join(dipakai) + (f" (+{sisa} lagi)" if sisa else "")
        teks = teks[:BATAS_ALASAN]

    return "anomali", teks
