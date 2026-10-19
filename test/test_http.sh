#!/usr/bin/env bash
# HTTP davranis testleri (sunucuya/veriye dokunmaz; gecici kopyada calisir).
# Kullanim: bash test/test_http.sh
set -u
KOK=$(cd "$(dirname "$0")/.." && pwd)

TESTDIR=$(mktemp -d /tmp/panel-test.XXXXXX)
cp "$KOK/app.py" "$KOK/index.html" "$TESTDIR"/
cp "$KOK/ornek-data.json" "$TESTDIR/data.json"
cd "$TESTDIR"

export PANEL_PAROLA=test1234 PANEL_PORT=8099
python3 app.py > "$TESTDIR/log.txt" 2>&1 &
PID=$!
sleep 1.2
trap 'kill $PID ${PID2:-} 2>/dev/null; rm -rf "$TESTDIR"' EXIT

T=cookie.txt
kod() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
ok=0; hata=0
kontrol() { # ad, gelen, beklenen
  if [ "$2" = "$3" ]; then ok=$((ok+1)); printf '  ok    %s\n' "$1"
  else hata=$((hata+1)); printf '  HATA  %s (gelen: %s, beklenen: %s)\n' "$1" "$2" "$3"; fi
}

echo "--- KIMLIK DOGRULAMA ---"
kontrol "sifresiz ana sayfa giris formu" "$(curl -s http://127.0.0.1:8099/ | grep -c 'Giriş yap')" "1"
kontrol "sifresiz api/data 401"          "$(kod http://127.0.0.1:8099/api/data)" "401"
kontrol "sifresiz api/yedekler 401"      "$(kod http://127.0.0.1:8099/api/yedekler)" "401"
kontrol "saglik ucu (sifresiz)"          "$(curl -s http://127.0.0.1:8099/saglik)" '{"durum": "ok"}'
kontrol "yanlis parola 401"              "$(kod -X POST -d 'kullanici=admin&parola=yanlis' http://127.0.0.1:8099/giris)" "401"
GIRIS=$(kod -c $T -X POST -d 'kullanici=admin&parola=test1234' http://127.0.0.1:8099/giris)
kontrol "dogru parola 303"               "$GIRIS" "303"
kontrol "oturum cerezi yazildi"          "$(grep -c panel_oturum $T)" "1"
kontrol "cerezle api/data 200"           "$(kod -b $T http://127.0.0.1:8099/api/data)" "200"
kontrol "cerezle panel aciliyor"         "$(curl -s -b $T http://127.0.0.1:8099/ | grep -c 'pg-dashboard')" "1"
kontrol "Basic auth ile api/data 200"    "$(kod -u admin:test1234 http://127.0.0.1:8099/api/data)" "200"

echo "--- KAYDETME / CAKISMA ---"
SURUM=$(curl -s -b $T http://127.0.0.1:8099/api/data | python3 -c 'import json,sys; print(json.load(sys.stdin).get("_guncelleme",""))')
kontrol "dogru surumle kaydet 200"       "$(kod -b $T -H 'Content-Type: application/json' -H "X-Panel-Surum: $SURUM" --data @data.json http://127.0.0.1:8099/api/data)" "200"
kontrol "eski surumle kaydet 409"        "$(kod -b $T -H 'Content-Type: application/json' -H 'X-Panel-Surum: 2020-01-01T00:00:00' --data @data.json http://127.0.0.1:8099/api/data)" "409"
CEVAP=$(curl -s -b $T -H 'Content-Type: application/json' -H 'X-Panel-Surum: 2020-01-01T00:00:00' --data @data.json http://127.0.0.1:8099/api/data)
kontrol "cakisma durumu bildiriliyor"    "$(echo "$CEVAP" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("durum",""))')" "cakisma"
kontrol "zorla kaydet 200"               "$(kod -b $T -H 'Content-Type: application/json' -H 'X-Panel-Surum: 2020-01-01T00:00:00' -H 'X-Panel-Zorla: 1' --data @data.json http://127.0.0.1:8099/api/data)" "200"
kontrol "surum basligi yok (eski sayfa)" "$(kod -b $T -H 'Content-Type: application/json' --data @data.json http://127.0.0.1:8099/api/data)" "200"
GUNCEL=$(curl -s -b $T http://127.0.0.1:8099/api/data | python3 -c 'import json,sys; print(json.load(sys.stdin).get("_guncelleme",""))')
kontrol "bos calisan listesi korumasi"   "$(kod -b $T -H "X-Panel-Surum: $GUNCEL" -H 'Content-Type: application/json' --data '{"calisanlar":[],"avanslar":[],"mesailer":[],"hakEdisler":[],"odemeler":[]}' http://127.0.0.1:8099/api/data)" "409"

echo "--- GECERSIZ ISTEKLER ---"
kontrol "bozuk JSON 400"                 "$(kod -b $T -H 'Content-Type: application/json' --data '{bozuk' http://127.0.0.1:8099/api/data)" "400"
kontrol "eksik anahtar 400"              "$(kod -b $T -H 'Content-Type: application/json' --data '{}' http://127.0.0.1:8099/api/data)" "400"
kontrol "calisanlar liste degil 400"     "$(kod -b $T -H 'Content-Type: application/json' --data '{"calisanlar":{},"avanslar":[],"mesailer":[],"hakEdisler":[],"odemeler":[]}' http://127.0.0.1:8099/api/data)" "400"
kontrol "bilinmeyen yol 404"             "$(kod -b $T http://127.0.0.1:8099/yok)" "404"
python3 -c "open('buyuk.txt','w').write('x'*9000000)"
kontrol "8 MB ustu govde 413"            "$(kod -b $T -H 'Content-Type: application/json' --data-binary @buyuk.txt http://127.0.0.1:8099/api/data)" "413"

echo "--- YEDEKLER ---"
kontrol "yedek listesi dolu"             "$(curl -s -b $T http://127.0.0.1:8099/api/yedekler | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["yedekler"])>0)')" "True"
AD=$(curl -s -b $T http://127.0.0.1:8099/api/yedekler | python3 -c 'import json,sys; print(json.load(sys.stdin)["yedekler"][0]["ad"])')
kontrol "tek yedek indirme 200"          "$(kod -b $T "http://127.0.0.1:8099/api/yedek?ad=$AD")" "200"
kontrol "yol kacisi engeli 404"          "$(kod -b $T 'http://127.0.0.1:8099/api/yedek?ad=../../etc/passwd')" "404"
kontrol "yedekten geri yukleme 200"      "$(kod -b $T -H 'Content-Type: application/json' --data "{\"ad\":\"$AD\"}" http://127.0.0.1:8099/api/geri-yukle)" "200"
kontrol "disa aktarma 200"               "$(kod -b $T http://127.0.0.1:8099/api/disa-aktar)" "200"

echo "--- BOZUK VERI DOSYASI ---"
mv data.json data.json.gizli
kontrol "veri dosyasi yoksa 500"         "$(kod -u admin:test1234 http://127.0.0.1:8099/api/data)" "500"
kontrol "bozuk dosyayla kaydet 409"      "$(kod -u admin:test1234 -H 'Content-Type: application/json' --data '{"calisanlar":[],"avanslar":[],"mesailer":[],"hakEdisler":[],"odemeler":[]}' http://127.0.0.1:8099/api/data)" "409"
mv data.json.gizli data.json

echo "--- OTURUM / HATALI GIRIS SINIRI ---"
kontrol "cikis 303"                      "$(kod -b $T -c $T -X POST http://127.0.0.1:8099/cikis)" "303"
kontrol "cikistan sonra 401"             "$(kod -b $T http://127.0.0.1:8099/api/data)" "401"
SON=""
for i in 1 2 3 4 5 6; do SON="$(kod -X POST -d 'kullanici=admin&parola=yanlis' http://127.0.0.1:8099/giris)"; done
kontrol "6. hatali giris 429 (kilit)"    "$SON" "429"

echo "--- PBKDF2 PAROLA OZETI ---"
HASH=$(python3 - <<'PY'
import base64, hashlib
tuz = "testtuz"
ozet = base64.b64encode(hashlib.pbkdf2_hmac("sha256", b"test1234", tuz.encode(), 200000)).decode()
print("pbkdf2_sha256$200000$%s$%s" % (tuz, ozet))
PY
)
PANEL_PAROLA= PANEL_PAROLA_HASH="$HASH" PANEL_PORT=8098 python3 app.py > "$TESTDIR/hashlog.txt" 2>&1 &
PID2=$!
sleep 1.2
kontrol "hash ile dogru parola 303"      "$(kod -X POST -d 'kullanici=admin&parola=test1234' http://127.0.0.1:8098/giris)" "303"
kontrol "hash ile yanlis parola 401"     "$(kod -X POST -d 'kullanici=admin&parola=yanlis' http://127.0.0.1:8098/giris)" "401"
kill $PID2 2>/dev/null; wait $PID2 2>/dev/null

echo ""
echo "--- SUNUCU LOGUNDA HATA ---"
kontrol "logda traceback yok"            "$(grep -ciE 'traceback|exception' "$TESTDIR/log.txt")" "0"

echo ""
echo "$ok kontrol gecti, $hata hata"
[ "$hata" -eq 0 ] || exit 1
