#!/usr/bin/env bash
#
# Personel Paneli — tek komutla kurulum (Debian/Ubuntu + systemd + nginx).
#
#   sudo bash kur.sh
#
# Varsayilanlar:
#   kurulum dizini : /opt/personel-panel
#   ortam dosyasi  : /etc/personel-panel.env
#   servis         : personel-panel.service (127.0.0.1:8090)
#
# Kurulumdan ONCE ayni dizinde "PAROLA" dosyasi olusturun (tek satir, parola):
#   printf '%s' 'guclu-bir-parola' > PAROLA
#
# Not: Parolayi duz metin yerine ozet olarak tutmak icin (onerilir) once
#      "python3 parola-hash.py" calistirip cikan degeri PANEL_PAROLA_HASH
#      olarak /etc/personel-panel.env icine yazin, PANEL_PAROLA satirini silin.
#
set -euo pipefail
export TZ=${TZ:-Europe/Istanbul}

KAYNAK=$(cd "$(dirname "$0")" && pwd)
HEDEF=${PANEL_DIZIN:-/opt/personel-panel}
ENV_DOSYA=${PANEL_ENV:-/etc/personel-panel.env}
KULLANICI=${PANEL_KULLANICI:-admin}
PORT=${PANEL_PORT:-8090}
SERVIS=personel-panel

echo "1) Dosyalar $HEDEF altina kopyalaniyor"
mkdir -p "$HEDEF/yedek" "$HEDEF/gunluk"
install -o www-data -g www-data -m 644 "$KAYNAK/app.py"     "$HEDEF/app.py"
install -o www-data -g www-data -m 644 "$KAYNAK/index.html" "$HEDEF/index.html"
if [ -f "$HEDEF/data.json" ]; then
  install -o www-data -g www-data -m 600 "$HEDEF/data.json" \
          "$HEDEF/yedek/kurulum-oncesi-$(date +%Y%m%d-%H%M%S).json" || true
  echo "   mevcut data.json korundu (yedek alindi)"
elif [ -f "$KAYNAK/data.json" ]; then
  install -o www-data -g www-data -m 600 "$KAYNAK/data.json" "$HEDEF/data.json"
  echo "   data.json kuruldu"
elif [ -f "$KAYNAK/ornek-data.json" ]; then
  install -o www-data -g www-data -m 600 "$KAYNAK/ornek-data.json" "$HEDEF/data.json"
  echo "   ornek-data.json kuruldu (demo veri — panelden silebilirsiniz)"
fi
chown -R www-data:www-data "$HEDEF"

echo "2) Ortam dosyasi ($ENV_DOSYA)"
if [ -f "$ENV_DOSYA" ]; then
  echo "   zaten var, dokunulmadi (parolayi degistirmek icin elle duzenleyin)"
else
  PAROLA=$(cat "$KAYNAK/PAROLA" 2>/dev/null || true)
  if [ -z "$PAROLA" ]; then
    echo "   HATA: PAROLA dosyasi yok. Once: printf '%s' 'parola' > PAROLA" >&2
    exit 1
  fi
  umask 077
  cat > "$ENV_DOSYA" <<EOF
PANEL_KULLANICI=$KULLANICI
PANEL_PAROLA=$PAROLA
PANEL_HOST=127.0.0.1
PANEL_PORT=$PORT
PANEL_HTTPS=0
PANEL_OTURUM_SAAT=12
EOF
  chmod 600 "$ENV_DOSYA"
  echo "   olusturuldu"
fi

echo "3) systemd servisi ($SERVIS)"
cat > "/etc/systemd/system/$SERVIS.service" <<UNIT
[Unit]
Description=Personel Paneli (bagimsiz, tek dosya)
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=$HEDEF
EnvironmentFile=$ENV_DOSYA
Environment=TZ=Europe/Istanbul
ExecStart=/usr/bin/python3 $HEDEF/app.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now "$SERVIS"
sleep 1

echo "4) nginx (istege bagli)"
if command -v nginx >/dev/null && [ -d /etc/nginx/sites-available ]; then
  echo "   nginx kurulu. Ornek yapilandirma: deploy/nginx-ornek.conf"
  echo "   (alan adinizi ve sertifikanizi girip /etc/nginx/sites-available/ altina kopyalayin)"
fi

echo "5) Dogrulama"
echo "   servis durumu       : $(systemctl is-active $SERVIS)"
echo "   yerel giris sayfasi : $(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/")  (200 beklenir)"
echo "   sifresiz veri       : $(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/api/data")  (401 beklenir)"
echo ""
echo "Panel calisiyor: http://127.0.0.1:$PORT/"
echo "Disariya acmak icin nginx + HTTPS (orn: certbot --nginx -d panel.ornek.com) kullanin."
echo "Kullanici adi: $KULLANICI  |  Parola: $ENV_DOSYA icinde"
