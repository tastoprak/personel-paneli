# Personel Paneli

[English](README.en.md) · Türkçe

[![testler](https://github.com/tastoprak/personel-paneli/actions/workflows/test.yml/badge.svg)](https://github.com/tastoprak/personel-paneli/actions/workflows/test.yml)

**Tek dosyalık personel takip paneli.** Küçük işletmeler için çalışan, avans, mesai,
hak ediş ve bordro takibi. **Hiçbir üçüncü taraf bağımlılığı yok** — yalnızca Python
standart kütüphanesi ve tek bir HTML dosyası; veri sunucudaki tek bir JSON dosyasında durur.

- Muhasebe/ERP programı **kurmanız gerekmez**, internete veri göndermez, bulut servisi kullanmaz.
- Kasadaki bir defterin dijital hâli: para hareketlerini girin, kimin ne kadar alacağı kaldığını görün.

![Özet sayfası](docs/panel-ozet.png)

## Özellikler

| Sayfa | Ne yapar |
|---|---|
| **Özet** | Toplam personel bakiyesi, kişi bazlı dağılım, bu ayın mesaileri, son avanslar. Bakiye kipi: *tüm kayıtlar* / *bugüne kadar* |
| **Çalışanlar** | Kod, pozisyon, net maaş, saat ücreti, işe giriş / işten çıkış tarihi, güncel bakiye |
| **Avanslar** | Verilen avanslar; ay ve çalışan filtresi, arşiv/silinmiş görünümü |
| **Mesailer** | Saat bazlı mesai kayıtları (sebep + onay durumu); "saat × saat ücreti" bilgi amaçlıdır |
| **Bordro** | Ay seç → hak ediş/ödeme gir; ay ortasında giriş/çıkış varsa **günlük hak ediş** otomatik; ay neti ve ay sonu bakiye |
| **Yedekler** | Otomatik yedekler, indirme, geri yükleme, JSON dışa aktarma |
| **Yardım** | Panel içi kullanım kılavuzu |

Diğer özellikler:

- **Türkçe para yazımı**: `28.000`, `1.234,56`, `₺ 5.000` gibi girişler doğru okunur.
- **Günlük hak ediş**: İşe giriş veya işten çıkış tarihi ayın içindeyse maaş, ayın **gerçek gün sayısı** üzerinden
  günlük hesaplanır (giriş ve çıkış günü dahil) ve hak edişe **otomatik** yazılır. Örn. 30.000 ₺ maaş,
  13–31 Ekim = 19/31 gün → **18.387,10 ₺**. O ay elle hak ediş girildiyse otomatik hesap devre dışı kalır;
  otomatik kayıtlar `kaynak: "gunluk-hesap"` ile işaretlidir ve giriş/çıkış/maaş düzeltilince güncellenir.
  Tam ay çalışanlar için otomatik kayıt açılmaz (maaş hak edişi eskisi gibi elle girilir).
- **Otomatik kaydetme**: her değişiklik ~1 saniye sonra kaydedilir; sağ üstteki nokta durumu gösterir.
- **Veri kaybına karşı korumalar**: yapılmamış değişiklik tarayıcıda *taslak* olarak tutulur; iki cihazda aynı anda
  değişiklik yapılırsa **çakışma (409)** ile uyarır, sessizce üzerine yazmaz; yanlışlıkla tüm çalışan listesini
  boşaltan kayıt reddedilir.
- **Silme yoktur, geri alma vardır**: kayıtlar "silindi" olarak işaretlenir; çalışanlar *pasife alınır*,
  bakiyeleri toplamdan düşmez.
- **Yedekleme**: her kaydetmede yedek (son 60) + günde bir kopya (son 30); geri yükleme öncesi mevcut durum da yedeklenir.
- **Kimlik doğrulama**: çerez tabanlı oturum, 12 saat; 5 hatalı denemede 5 dakika kilit. Parola düz metin
  **veya** PBKDF2 özeti olarak saklanabilir.
- **Mobil uyumlu**, tek HTML dosyası, harici CDN/font/JS yok (CSP ile kilitli).

## Hızlı başlangıç (deneme)

```bash
git clone https://github.com/tastoprak/personel-paneli.git
cd personel-paneli
cp ornek-data.json data.json            # örnek veri (kendi verinizle değiştirin)

PANEL_KULLANICI=admin PANEL_PAROLA=deneme1234 python3 app.py
# tarayıcı: http://127.0.0.1:8090
```

Bitti. Veritabanı, servis, derleme adımı yok. Veriniz `data.json` dosyasıdır — yedeklemek için kopyalamanız yeterli.

## Sunucu kurulumu (kalıcı)

Debian/Ubuntu + systemd varsayımıyla:

```bash
printf '%s' 'guclu-bir-parola' > PAROLA        # tek satır, parola
sudo bash kur.sh
```

Bu komut dosyaları `/opt/personel-panel` altına kurar, `/etc/personel-panel.env` ortam dosyasını
oluşturur, `personel-panel.service` servisini başlatır (yalnızca `127.0.0.1:8090`).

Dışarıya açmak için `deploy/nginx-ornek.conf` dosyasını kendi alan adınızla düzenleyip
`/etc/nginx/sites-available/` altına koyun ve sertifika alın:

```bash
sudo certbot --nginx -d panel.ornek.com
```

## Ayarlar (ortam değişkenleri)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `PANEL_KULLANICI` | `admin` | Kullanıcı adı |
| `PANEL_PAROLA` | — | Parola (düz metin). **Ya bu ya `PANEL_PAROLA_HASH` zorunlu** |
| `PANEL_PAROLA_HASH` | — | `pbkdf2_sha256$iter$tuz$ozet`. `python3 parola-hash.py` ile üretin |
| `PANEL_HOST` | `127.0.0.1` | Dinlenecek adres (dışarı açmayın; nginx kullanın) |
| `PANEL_PORT` | `8090` | Port |
| `PANEL_HTTPS` | `0` | `1` ise çerez yalnızca HTTPS'te gönderilir |
| `PANEL_OTURUM_SAAT` | `12` | Oturum süresi (saat) |
| `PANEL_ADI` | `Personel Paneli` | Panelin görünen adı |
| `PANEL_ALT_BASLIK` | — | Logo altındaki satır (örn. `Yangın Söndürme Cihazları`) |
| `PANEL_IKON` | `📋` | Logo ikonu (emoji) |
| `PANEL_SLUG` | addan üretilir | Yedek/dışa aktarma dosya adı öneki |

Parolayı özet olarak saklamak (önerilir):

```bash
python3 parola-hash.py                 # çıktı: pbkdf2_sha256$600000$...$...
# /etc/personel-panel.env icinde tek tirnak icinde yazin:
#   PANEL_PAROLA_HASH='pbkdf2_sha256$600000$...$...'
# ve PANEL_PAROLA satirini silin
sudo systemctl restart personel-panel
```

## Veri biçimi (`data.json`)

```jsonc
{
  "calisanlar": [ { "kod": "K001", "ad": "Ali Yılmaz", "pozisyon": "Kaynakçı",
                    "maas": 32000, "mesaiSaatUcret": 200, "girisTarihi": "2023-03-15",
                    "cikisTarihi": "", "not": "", "devir": 62400, "aktif": true } ],
  "hakEdisler": [ { "tarih": "2026-10-31", "kod": "K001", "tutar": 32000, "aciklama": "Ekim 2026 hak edişi" },
                  { "tarih": "2026-10-31", "kod": "K006", "tutar": 18387.10,
                    "aciklama": "Ekim 2026 hak edişi (13–31 Eki · 19/31 gün)",
                    "kaynak": "gunluk-hesap", "gun": 19, "ayGun": 31, "maas": 30000 } ],
  "avanslar":   [ { "tarih": "2026-10-05", "kod": "K001", "tutar": 2000, "aciklama": "Nakit avans" } ],
  "odemeler":   [ { "tarih": "2026-10-03", "kod": "K001", "tutar": 32000, "aciklama": "Eylül 2026 maaş ödemesi" } ],
  "mesailer":   [ { "tarih": "2026-10-03", "kod": "K001", "saat": 3, "sebep": "Sevkiyat",
                    "onay": "Onaylı", "aciklama": "Sevkiyat / Onaylı" } ]
}
```

Kurallar:

- **Bakiye = `devir` + Σ hak ediş − Σ avans − Σ ödeme** (yalnızca `arsiv` ve `silindi` işaretli olmayan kayıtlar).
- `devir`: kayıt tutmaya başladığınız andaki (veya devrettiğiniz tarihteki) başlangıç bakiyesi.
  O tarihten önceki hareketleri girmek isterseniz `"arsiv": true` ekleyin — listede görünür ama bakiyeye tekrar eklenmez.
- **Silme yoktur**: silinen kayda `"silindi": true` yazılır, listede geçmişi görünür ve geri alınabilir.
- `aktif: false` olan çalışan listede gizlenir; kayıtları ve bakiyesi toplamdan **düşmez**.
- `cikisTarihi`: işten çıkış tarihi (boş = halen çalışıyor). Giriş/çıkış ayında maaş günlük hesaplanır;
  otomatik oluşan hak ediş kaydı `kaynak: "gunluk-hesap"`, `gun`, `ayGun`, `maas` alanlarını taşır.
  `silindi: true` yapılan otomatik kayıt bir daha üretilmez.
- Sunucu her kaydetmede `_guncelleme` alanını kendisi yazar (çakışma denetimi için).

## Yedekleme

- Her kaydetmede: `yedek/data-<tarih>-<mikrosaniye>.json` (son **60**).
- Günde bir: `gunluk/gunluk-<tarih>.json` (son **30**).
- Panelde **Yedekler** sayfasından indirilebilir, geri yüklenebilir; **JSON dışa aktarma** da var.
- Geri yükleme öncesi mevcut durum otomatik yedeklenir (geri yükleme de geri alınabilir).
- Sunucu tarafında `data.json` (ve `yedek/`, `gunluk/`) dizinini başka bir diske/servise kopyalamak en sağlam yöntemdir.

## Güvenlik notları — lütfen okuyun

- Panelde **maaş verisi** vardır. Mutlaka **HTTPS** arkasında çalıştırın (`PANEL_HTTPS=1` çerezlerin yalnızca
  TLS üzerinden gönderilmesini sağlar) ve uygulamayı `127.0.0.1` dışına **dinletmeyin**.
- Tek kullanıcılıdır (tek kullanıcı adı/parola). Birden fazla kişi aynı anda kullanabilir, ancak ayrı hesap yoktur.
- Parolayı `PANEL_PAROLA_HASH` ile özet olarak saklamanız önerilir; düz metin tercih ederseniz ortam dosyasının
  izinlerini `600` yapın.
- Oturum çerezleri imzalı rastgele değerlerdir, sunucu belleğinde tutulur: **servis yeniden başladığında herkes
  tekrar giriş yapar** (12 saatlik oturum sınırı da vardır).
- Panel, `X-Real-IP` başlığına güvenerek hatalı giriş sayacını IP başına tutar; bu nedenle yalnızca güvendiğiniz
  bir reverse proxy arkasında yayınlayın.
- `data.json` ve yedekleri **şifresiz** düz metindir: bu dizine erişimi olan biri tüm maaş verisini okuyabilir.
- Bu yazılım hiçbir dış servise bağlanmaz, telemetri göndermez, CDN/font kullanmaz.

## Testler

```bash
node test/test_mantik.js        # 101 kontrol: panel mantığı (tarayıcısız)
bash test/test_http.sh          # 34 kontrol: HTTP davranışı (giriş, çakışma, yedek, limitler)
bash test/ekran-goruntusu.sh    # ekran görüntüleri (chromium gerekir)
```

Testler `ornek-data.json` ile çalışır; kendi verinize dokunmaz. GitHub Actions ile her push'ta çalışır.

## Sınırlar

- Tek kullanıcı, tek dosya, tek süreç. Çok kullanıcılı yetkilendirme, çok şubeli yapı, muhasebe entegrasyonu yoktur.
- Bordro, resmi puantaj/İK yazılımı yerine geçmez; prim, kesinti, SGK hesabı yapmaz — elle girilen tutarları takip eder.
- Mesai saatleri bilgi amaçlıdır; ödeme tutarı hak ediş olarak elle girilir (çift sayımı önlemek için).

## Sürüm notları

### v1.1.0 — 2026-10-21
- **Günlük hak ediş (yeni):** İşe giriş veya işten çıkış tarihi ayın içindeyse maaş, ayın gerçek gün sayısı
  üzerinden günlük hesaplanır (giriş ve çıkış günü dahil) ve hak edişe otomatik yazılır.
  - Tam ay çalışanlar için otomatik kayıt açılmaz; o ay için elle hak ediş girildiyse otomatik hesap devre dışı kalır.
  - Otomatik kayıtlar `kaynak: "gunluk-hesap"` ile işaretlidir; giriş/çıkış/maaş düzeltilince güncellenir,
    silinen kayıt geri getirilmez.
  - Yalnızca kayıt tutulan (kesim sonrası) aylar için çalışır; arşiv ve gelecek aylara yazmaz.
- **Çalışanlar:** "İşten çıkış tarihi" alanı (çıkış < giriş doğrulaması), listede "Giriş / Çıkış" sütunu ve
  "ayrıldı" etiketi. Otomatik pasife alma yoktur.
- **Bordro:** "Günlük hesap" sütunu (gün aralığı · n/m gün · tutar · otomatik/elle etiketi) ve güncelleme notu.
- **Düzeltme:** Çalışan düzenlendiğinde pasif kayıt artık istem dışı aktifleşmiyor.
- **Testler:** 63 → **101** mantık kontrolü (giriş/çıkış, Şubat 28/29, 31 günlük ay, aynı ay giriş+çıkış,
  çift kayıt koruması, elle ezme, silinen kaydın geri gelmemesi).

## Katkı

Hata bildirimi ve öneriler için **issue formlarını** kullanın (depoda hazır şablonlar var: *hata bildirimi* ve
*özellik önerisi*; her iki dilde). Bildirimlerde **gerçek çalışan adı, maaş veya müşteri bilgisi paylaşmayın** —
uydurma örnekler (bkz. `ornek-data.json`) sorunu çözmek için yeterlidir. Güvenlikle ilgili konuları
[özel olarak](https://github.com/tastoprak/personel-paneli/security/advisories/new) bildirin.

Kod değişikliği önerirken testleri çalıştırın (`node test/test_mantik.js && bash test/test_http.sh`).

## Lisans

[MIT](LICENSE) — ticari kullanım dahil serbestçe kullanabilir, değiştirebilir, dağıtabilirsiniz.
