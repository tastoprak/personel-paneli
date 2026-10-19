#!/usr/bin/env bash
# Paneli basit bir statik sunucuda acip her sayfanin ekran goruntusunu alir.
# Gereksinim: chromium (veya chromium-browser), python3. Ekran goruntuleri
# "docs/" klasorune panel-<sayfa>.png olarak yazilir.
set -u
KOK=$(cd "$(dirname "$0")/.." && pwd)
HEDEF=$(mktemp -d /tmp/panel-shot.XXXXXX)
CIKTI=${1:-$KOK/docs}
mkdir -p "$HEDEF/api" "$CIKTI"

python3 - "$KOK" "$HEDEF" <<'PY'
import datetime, json, pathlib, sys
kok = pathlib.Path(sys.argv[1]); hedef = pathlib.Path(sys.argv[2])

html = (kok / 'index.html').read_text(encoding='utf-8')
# app.py normalde bu yer tutuculari doldurur; statik gosterim icin burada dolduruyoruz.
html = (html.replace('__AD__', 'Personel Paneli')
            .replace('__ALT_SATIR__', 'personel takip')
            .replace('__IKON__', '📋')
            .replace('__VERI_DIZINI__', '/opt/personel-panel'))

veri = json.loads((kok / 'ornek-data.json').read_text(encoding='utf-8'))
(hedef / 'api' / 'data').write_text(json.dumps(veri), encoding='utf-8')

sayfalar = [('ozet', 'dashboard', 0, ''), ('calisanlar', 'calisanlar', 1, ''),
            ('avanslar', 'avanslar', 2, ''), ('mesailer', 'mesailer', 3, ''),
            ('bordro', 'bordro', 4, ''), ('yedekler', 'yedekler', 5, ''),
            ('yardim', 'yardim', 6, ''), ('ozet-bugun', 'dashboard', 0, 'kipAyarla("bugun");')]
for ad, sayfa, idx, ekjs in sayfalar:
    ek = ("<script>setTimeout(function(){var b=document.querySelectorAll('.nb')[%d];"
          "pg('%s',b);%s},500);</script>" % (idx, sayfa, ekjs))
    (hedef / (ad + '.html')).write_text(html.replace('</body>', ek + '\n</body>'), encoding='utf-8')

# Yedekler sayfasi icin ornek liste (statik sunucuda API yok)
simdi = datetime.datetime.now()
sayilar = {k: len(v) for k, v in veri.items()}
def yedek(ad, tur, dk_once):
    return {"ad": ad, "tur": tur, "boyut": 28658,
            "zaman": (simdi - datetime.timedelta(minutes=dk_once)).isoformat(timespec='seconds'),
            "kayit": sayilar}
liste = [yedek("data-20261019-191529-557217.json", "kayıt", 3),
         yedek("data-20261019-184002-133901.json", "kayıt", 34),
         yedek("gunluk-2026-10-19.json", "günlük", 120),
         yedek("gunluk-2026-10-18.json", "günlük", 1560)]
(hedef / 'api' / 'yedekler').write_text(json.dumps({"yedekler": liste, "simdi": simdi.isoformat()}), encoding='utf-8')
print('sayfa dosyalari olusturuldu')
PY

cd "$HEDEF" || exit 1
python3 -m http.server 8097 --bind 127.0.0.1 > "$HEDEF/sunucu.log" 2>&1 &
SUNUCU=$!
sleep 1.5
trap 'kill $SUNUCU 2>/dev/null; rm -rf "$HEDEF"' EXIT

TARAYICI=$(command -v chromium || command -v chromium-browser || command -v google-chrome || true)
if [ -z "$TARAYICI" ]; then
  echo "chromium bulunamadi — ekran goruntusu alinamadi." >&2
  exit 1
fi

for ad in ozet calisanlar avanslar mesailer bordro yedekler yardim ozet-bugun; do
  timeout 60 "$TARAYICI" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
      --window-size=1440,1750 --virtual-time-budget=4000 \
      --screenshot="$CIKTI/panel-$ad.png" "http://127.0.0.1:8097/$ad.html" > /dev/null 2>&1
  echo "$ad : $(ls -la "$CIKTI/panel-$ad.png" 2>/dev/null | awk '{print $5}') bayt"
done

timeout 60 "$TARAYICI" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
    --window-size=420,1100 --virtual-time-budget=4000 \
    --screenshot="$CIKTI/panel-mobil.png" "http://127.0.0.1:8097/ozet.html" > /dev/null 2>&1
echo "mobil : $(ls -la "$CIKTI/panel-mobil.png" 2>/dev/null | awk '{print $5}') bayt"
