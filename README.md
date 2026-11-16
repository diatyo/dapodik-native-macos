# Dapodik Native macOS (Intel)

Port eksperimental Dapodik 2027.b untuk macOS Intel, tanpa Windows virtual atau Wine. Skrip membongkar installer yang kamu sediakan, menerapkan patch 2027.a lalu 2027.b, dan menjalankan aplikasi dengan PHP, ionCube, serta PostgreSQL untuk macOS.

Repo ini berisi kode integrasi dan panduan. Siapkan installer resmi Dapodik dari [portal unduhan Kemendikdasmen](https://dapo.kemendikdasmen.go.id/unduhan).

## Instalasi baru

Perlu Mac Intel, Python 3.9+, Xcode Command Line Tools, dan tiga berkas berikut dalam satu folder di Mac:

- `Dapodik_2027.exe`
- `Patch_Dapodik_2027.a.exe`
- `Patch_Dapodik_2027.b.exe`

Jalankan dari folder repo sebagai pengguna macOS biasa:

```sh
python3 tools/build_runtime.py
python3 tools/install.py "/path/ke/folder-installer"
```

Langkah pertama mengunduh paket yang versinya tercatat di `tools/runtime-lock.json`, memeriksa SHA-256, dan membangun ekstensi PHP. Jika sebuah arsip sudah tersedia lokal, taruh di `native-runtime/downloads/` dengan nama di daftar tersebut. Server asal dapat mengganti atau menghapus paket lama. Jika checksum berubah, cari salinan yang cocok dengan daftar sebelum melanjutkan.

Langkah kedua memeriksa SHA-256 ketiga installer yang diuji, menyiapkan salinan aplikasi, dan membuat database baru dari SQL bawaan installer. Skrip berhenti jika tujuan sudah ada. Setelah selesai, buka [Dapodik lokal](http://127.0.0.1:5774/) atau jalankan **Dapodik Native.app** dari folder Applications milik akunmu.

Jika `initdb` gagal dengan pesan `could not create shared memory segment`, periksa apakah ada PostgreSQL 9.2 lain yang sedang berjalan. Pada Mac yang diuji, instalasi aktif memakai hampir seluruh jatah memori bersama yang tersedia. Jalankan pemasangan baru saat layanan lama sedang tidak dipakai dan gunakan direktori tujuan yang kosong.

## Mengelola layanan

File aplikasi dan data berada di `~/Library/Application Support/Dapodik Native`. Gunakan perintah ini untuk melihat status, mencadangkan database, atau menghentikan layanan:

```sh
python3 "$HOME/Library/Application Support/Dapodik Native/control.py" status
python3 "$HOME/Library/Application Support/Dapodik Native/control.py" backup
python3 "$HOME/Library/Application Support/Dapodik Native/control.py" stop
```

Cadangan berada di subfolder `backups/`. Untuk registrasi offline, letakkan salinan prefill di subfolder `prefill_dapodik/`.

## Cakupan

- Instalasi ini menggunakan PHP 7.2.34, PostgreSQL 9.2.24, dan ionCube untuk Intel. Pengaturan bawaan membuka web hanya di loopback dan menghubungkan PostgreSQL lewat soket Unix pribadi.
- Instalasi asli berjalan pada macOS 26.7.2 Intel sampai dashboard Dapodik 2027.b dengan versi database 2.104. Sinkronisasi pusat dan alur impor/ekspor sekolah masih belum diverifikasi.
- Repo ini sudah diuji sampai tahap build runtime, ekstraksi ketiga installer, dan pengujian konektor PHP dengan kueri baca-saja. Uji pemasangan bersih terhenti saat inisialisasi PostgreSQL karena batas memori bersama saat layanan lama berjalan.
- Kedua patch dipasang dengan menyalin payload ke instalasi baru. Patch sesudah 2027.b dan migrasi database dari instalasi lain perlu diperiksa terpisah.
- Pengaturan startup dan LAN dari Mac asal tidak disalin ke instalasi baru.

Dapodik dan komponen pihak ketiga tetap tunduk pada ketentuan masing-masing pemilik. Proyek ini independen dari Kemendikdasmen.
