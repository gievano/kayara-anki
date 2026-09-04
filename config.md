# Kayara — Konfigurasi

Cara termudah: menu **🌸 Kayara → Settings…** di menubar Anki.
File ini hanya untuk edit manual lanjutan (Tools → Add-ons → Kayara → Config).

## Kunci utama
- `api_endpoint`: URL API kompatibel OpenAI (default: OmniRoute `http://localhost:20128/v1`)
- `api_key`: API key untuk endpoint di atas
- `models`: daftar model di dropdown panel — `id` harus sama persis dengan nama model di endpoint
- `default_model_index`: index model default (0 = model pertama)
- `system_prompt`: instruksi kepribadian + aturan blok aksi (SAVE/SET/ASK/BATCH/CARD)
- `keybinds.open_empty` / `keybinds.open_with_selection`: shortcut buka panel (default `Ctrl+Alt+K` / `Ctrl+Alt+L`)

## Blok aksi (dikeluarkan AI, dieksekusi addon)
- `[[SAVE:Field]]...[[/SAVE]]` — tambah konten ke field kartu aktif
- `[[SET:Field]]...[[/SET]]` — ganti seluruh isi field
- `[[ASK:...]]` — baca Anki (decks/notetypes/find/note), auto-dieksekusi
- `[[BATCH]]...[[/BATCH]]` — transformasi massal per kartu (deck/notetype/source/target/task)
- `[[CARD]]` — tandai jawaban layak jadi kartu baru (munculkan tombol +Card)
