# TIMER MAXDIS — Kivy Android

Project Kivy/Python yang mempertahankan alur timer enam lorong dari TIMER MAXDIS sebelumnya, dengan Android Foreground Service untuk hitung mundur di latar belakang.

## Fitur

- Enam lorong: L01–L06.
- Input Qty lalu tekan ENTER.
- Rumus timer asli: `ceil((Qty / 12) × 60)` detik.
- Popup timer dengan ring progress; tombol LANJUT hanya aktif setelah timer selesai.
- Alarm `assets/notifikasi.mp3` berulang sampai pengguna menekan LANJUT.
- Rekap total Qty, shift, target standar, waktu kerja, gap, waktu aktual, deviasi, dan waktu selesai.
- Status notifikasi Android `TIMER MAXDIS — RUNNING` dengan ikon status kustom.
- `Foreground Service` terpisah dengan deadline absolut tersimpan di app-private storage.
- Partial WakeLock saat countdown aktif untuk menjaga proses timer tetap berjalan ketika layar mati.
- Tombol MENU membuka `https://apktoko.arinex.my.id/menu.html`.
- Custom launcher icon berasal dari desain jam analog yang disediakan sebelumnya.

## Struktur

```text
TIMER_MAXDIS_KIVY/
├── main.py
├── timer_logic.py
├── buildozer.spec
├── assets/
│   ├── icon.png
│   └── notifikasi.mp3
├── services/
│   └── timer_service.py
├── android_resources/
│   ├── drawable/ic_stat_maxdis.png
│   └── extra_manifest_application_arguments.xml
├── android_src/id/arinex/timermaxdis/MaxdisPythonService.java
├── tests/
└── .github/workflows/android.yml
```

## Build APK melalui GitHub Actions

1. Buat repository GitHub baru.
2. Upload **isi folder project ini** ke root repository (bukan membungkus seluruh folder project di dalam folder lain).
3. Pastikan file `.github/workflows/android.yml` ikut ter-upload.
4. Buka tab **Actions**.
5. Pilih **Build TIMER MAXDIS Kivy APK**.
6. Tekan **Run workflow**.
7. Workflow menjalankan compile check dan unit test terlebih dahulu, kemudian membangun APK dengan Buildozer.
8. Setelah sukses, download artifact `TIMER-MAXDIS-KIVY-debug-apk` dari ringkasan run. Artifact berisi APK debug.

Workflow build menggunakan Ubuntu 22.04, Python 3.10, Java 17, Buildozer 1.5.0, Cython 0.29.36, dan python-for-android tag `v2026.05.09`.

## Izin Android

- `POST_NOTIFICATIONS`: agar notifikasi status RUNNING dapat terlihat pada panel notifikasi Android 13+.
- `FOREGROUND_SERVICE` dan `FOREGROUND_SERVICE_SPECIAL_USE`: untuk foreground service.
- `WAKE_LOCK`: partial wake lock selama countdown agar CPU tidak tidur saat layar mati.
- `INTERNET`: membuka halaman MENU.

Foreground service memakai tipe `specialUse` dengan subtype timer hitung mundur yang dimulai oleh pengguna. Android 14+ mengharuskan tipe foreground service dan deklarasi subtype pada manifest. Distribusi Google Play tetap perlu menjelaskan dan memenuhi kebijakan foreground-service yang berlaku.

## Perilaku background dan batasan OS

- Menekan Home, berpindah aplikasi, atau mematikan layar: service tetap berjalan selama Android mengizinkan dan notifikasi RUNNING aktif.
- Swipe aplikasi dari Recent Apps: service memakai mode `sticky`; Buildozer/p4a menjaga service tetap terpisah dari UI task.
- Jika sistem menghentikan proses service, service disetel agar mencoba restart dan membaca kembali deadline yang disimpan.
- **Force stop** dari Settings, penghentian paksa oleh pengguna, pencabutan izin, atau pembatasan OEM dapat menghentikan service. Pengguna harus membuka aplikasi lagi untuk memulai ulang service.
- Saat ponsel benar-benar dimatikan/kehabisan daya, timer tidak dapat menghitung di perangkat. Deadline tersimpan dan dapat diperiksa setelah aplikasi dibuka kembali, tetapi proyek ini belum memasang receiver boot otomatis.
- Partial WakeLock membantu ketepatan saat layar mati tetapi dapat menambah konsumsi baterai selama timer berjalan.

## Ikon notifikasi

`assets/icon.png` adalah ikon aplikasi penuh. `android_resources/drawable/ic_stat_maxdis.png` adalah glyph putih transparan khusus status bar Android. Service memanggil `service.start(..., "ic_stat_maxdis", ...)` sesuai API python-for-android.

## Mengganti alarm

Ganti `assets/notifikasi.mp3` dengan audio milikmu menggunakan nama file yang sama. Jangan menghapus file ini. Aplikasi menyalinnya ke app-private files directory agar proses service terpisah dapat mengaksesnya.

## Pengujian lokal

Jalankan dari root project:

```bash
python -m compileall -q main.py timer_logic.py services tests
python -m unittest discover -s tests -v
```

Unit test memeriksa rumus Qty, pembulatan, deadline, penyelesaian idempoten, enam lorong, kalkulasi target/work/gap/actual/deviasi, mapping shift, format waktu, penyimpanan atomik, file icon/audio, Buildozer config, dan fragmen manifest.

Pengujian lokal di container ini tidak menjalankan emulator Android/Kivy runtime. Build APK Android dan uji perangkat nyata harus dilakukan oleh GitHub Actions dan HP target setelah APK berhasil dibuat.

## Catatan pengujian perangkat

Sebelum dipakai untuk shift/operasional, lakukan uji manual berikut pada HP target:

1. Mulai timer Qty 12 (standar 60 detik).
2. Pastikan notifikasi `RUNNING • HITUNG MUNDUR DI LATAR BELAKANG` terlihat.
3. Tekan Home dan kunci layar selama lebih dari 60 detik.
4. Pastikan alarm MP3 berbunyi dan notifikasi tetap aktif.
5. Buka kembali aplikasi; popup menunjukkan `00:00` dan tombol LANJUT tersedia.
6. Lanjutkan ke L02, lalu pastikan timer baru bisa dimulai.
7. Ulangi sampai L06 dan cocokkan rekap sesi.
8. Uji swipe dari Recent Apps (jangan Force stop) dan ulangi pengamatan.

Untuk Android OEM yang agresif menghemat baterai, atur Battery usage aplikasi ke Unrestricted/Allow background activity. Nama menu dapat berbeda antar merek dan versi Android.
