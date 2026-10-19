# Dağ Evi · YouTube Video Arşivi

Bilgisayarında çalışan Türkçe Python uygulaması. YouTube bağlantılarını sıraya alır, 360p–1080p arasında seçtiğin üst kalite sınırında sesli MP4 indirir. Videolar `downloads/` klasörüne kaydedilir; uygulamadan veya VLC/QuickTime gibi bir oynatıcıdan internet olmadan izlenebilir.

## macOS kurulumu

Bu Mac için proje içine ARM64 Python 3.13 (`.python/`) ve yeni bir sanal ortam (`.venv/`) kuruldu. Önceki bilgisayara ait ortam `.venv-incompatible-backup/` klasöründe saklanır. Python ve sanal ortam klasörlerini başka bilgisayara taşımak yerine o bilgisayarda yeniden kurulum yap.

Bu bilgisayarda Python bağımlılıkları ve projeye özel FFmpeg kuruldu; JavaScript işlemleri için mevcut Node.js kullanılır. Başlatmak için:

```sh
.venv/bin/python app.py
```

Yeni kurulumlarda Python 3.10 veya üzeri ve Deno ya da Node.js 22+ gerekir. FFmpeg, Python bağımlılıklarıyla birlikte gelir; sistemde kurulu FFmpeg varsa öncelikle o kullanılır. Homebrew ile sistem araçlarını kurmak istersen:

```sh
brew install python ffmpeg deno
```

Bu proje klasöründe terminal açıp çalıştır:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

Tarayıcı otomatik açılır: http://127.0.0.1:8765. Sonraki açılışlarda `start.command` dosyasına çift tıklayabilirsin. Terminali kapatmak indirmeyi durdurur; durdurmak için Ctrl+C kullan. Port doluysa `PORT=8766 .venv/bin/python app.py` çalıştır.

## Windows / Linux

Python 3.10+, FFmpeg ve Deno kur; `ffmpeg` ve `deno` komutlarının PATH üzerinde erişilebilir olduğundan emin ol. Windows'ta `py -m venv .venv`, `.venv\Scripts\activate`, `python -m pip install -r requirements.txt`, `python app.py` komutlarını kullan. Linux'ta macOS bölümündeki sanal ortam komutları geçerlidir; sistem araçlarını dağıtımının paket yöneticisiyle kur.

## Kullanım

1. İnternet varken her satıra bir YouTube video bağlantısı yapıştır.
2. Kaliteyi seçip **İndirme sırasına ekle** düğmesine bas.
3. Tamamlanan videoları indirilenler bölümünden oynat. Dağ evine gitmeden önce dosyaları açıp ses ve görüntüyü kontrol et.

Bağlantılar sırayla indirilir. Seçilen kalite üst sınırdır; kaynakta bulunmayan kalite yükseltilmez. Uyumluluk için H.264/AAC MP4 seçilir. Uygun format yoksa hata gösterilir. Dosya başına sınır 5 GB'dır. Sıra bellekte tutulur; yeniden başlatınca sıfırlanır, indirilen dosyalar kalır. Yarım kalan indirmeyi aynı bağlantıyı ekleyerek yeniden deneyebilirsin. Oynatma listeleri topluca indirilmez; canlı yayın bağlantıları arşiv için önerilmez.

YouTube zaman zaman indirme yöntemlerini değiştirebilir. Hata alırsan internet bağlıyken `.venv/bin/python -m pip install -U -r requirements.txt` ile güncelle. Giriş, yaş kısıtlaması veya bot doğrulaması isteyen videolar indirilemeyebilir; uygulama oturum çerezi toplamaz. Yalnızca indirme hakkın veya iznin olan içerikleri kullan.

Uygulama yalnızca `127.0.0.1` üzerinde çalışır. İnternete açma. Arayüz için harici servis veya CDN gerekmez. İndirmeler için internet gerekir; çevrimdışıyken yeni video alınamaz.

İndirme motoru ve bağımlılık bilgisi: [yt-dlp resmi belgeleri](https://github.com/yt-dlp/yt-dlp#readme).
