"""Buat akun admin pertama. Tabel PENGGUNA kosong sampai ini dijalankan.

    python buat_admin.py --username admin --nama "Jovandi Todana"

Kata sandi ditanyakan tanpa ditampilkan di layar dan tidak pernah tercatat di
mana pun; yang disimpan hanya hash bcrypt-nya.
"""
import argparse
import getpass
import sys

import basis_data as bd
from api import keamanan


def main():
    p = argparse.ArgumentParser(description="Buat akun admin")
    p.add_argument("--username", required=True)
    p.add_argument("--nama", required=True)
    p.add_argument("--ganti", action="store_true",
                   help="ganti kata sandi akun yang sudah ada")
    a = p.parse_args()

    username = a.username.strip().lower()
    # Kekangan ck_pengguna_username menuntut huruf kecil dan minimal 4 karakter.
    if len(username) < 4:
        print("Username minimal empat karakter."); return 1

    sandi = getpass.getpass("Kata sandi        : ")
    ulang = getpass.getpass("Ulangi kata sandi : ")
    if sandi != ulang:
        print("Kata sandi tidak sama."); return 1
    if len(sandi) < 8:
        print("Kata sandi minimal delapan karakter."); return 1

    with bd.koneksi() as s, s.cursor() as k:
        k.execute("SELECT id_pengguna FROM pengguna WHERE username=%s", (username,))
        ada = k.fetchone()
        if ada and not a.ganti:
            print(f"Pengguna '{username}' sudah ada. "
                  "Tambahkan --ganti untuk mengganti kata sandinya."); return 1

        if ada:
            k.execute("""UPDATE pengguna SET kata_sandi_hash=%s, nama_lengkap=%s,
                         aktif=true WHERE username=%s""",
                      (keamanan.hash_kata_sandi(sandi), a.nama, username))
            print(f"Kata sandi '{username}' diganti.")
        else:
            k.execute("""INSERT INTO pengguna (username, kata_sandi_hash,
                         nama_lengkap, peran) VALUES (%s, %s, %s, 'admin')
                         RETURNING id_pengguna""",
                      (username, keamanan.hash_kata_sandi(sandi), a.nama))
            print(f"Admin '{username}' dibuat, id {k.fetchone()['id_pengguna']}.")
        s.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
