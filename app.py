#!/usr/bin/env python3
"""
Personel Paneli — tek dosyalık, bağımsız personel/avans/bordro takip sunucusu.

Yalnızca Python standart kütüphanesi kullanılır.

Uç noktalar:
    GET  /                 -> giriş yapılmamışsa giriş sayfası, yapılmışsa panel
    POST /giris            -> oturum açar (çerez), 303 ile panele yönlendirir
    POST /cikis            -> oturumu kapatır
    GET  /api/data         -> veriyi döner
    POST /api/data         -> veriyi kaydeder (sürüm çakışması varsa 409)
    GET  /api/yedekler     -> yedek listesi
    GET  /api/yedek?ad=... -> tek yedeği indirir
    POST /api/geri-yukle   -> yedeği geri yükler (önce mevcut durumu yedekler)
    GET  /api/disa-aktar   -> mevcut veriyi dosya olarak indirir
    GET  /saglik           -> "ok" (kimlik doğrulamasız, veri içermez)
"""

import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import shutil
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote_plus

BASE = Path(__file__).resolve().parent
DATA = BASE / "data.json"
INDEX = BASE / "index.html"
YEDEK_DIZIN = BASE / "yedek"          # her kaydetmede alınan yedek
GUNLUK_DIZIN = BASE / "gunluk"        # günde bir alınan yedek

KULLANICI = os.environ.get("PANEL_KULLANICI", "admin")
PAROLA = os.environ.get("PANEL_PAROLA", "")
# Tercih edilen yöntem: parolayı düz metin tutmak yerine PBKDF2 özeti (bkz. parola-hash.py).
PAROLA_HASH = os.environ.get("PANEL_PAROLA_HASH", "").strip()

# Görünüm (marka) — boş bırakılırsa genel "Personel Paneli" görünümü kullanılır.
PANEL_ADI = os.environ.get("PANEL_ADI", "").strip() or "Personel Paneli"
PANEL_ALT_BASLIK = os.environ.get("PANEL_ALT_BASLIK", "").strip()
PANEL_IKON = os.environ.get("PANEL_IKON", "").strip() or "📋"


def _slug(metin: str) -> str:
    """Dosya adlarında kullanılacak güvenli kısa ad."""
    ceviri = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    temiz = re.sub(r"[^a-z0-9]+", "-", metin.translate(ceviri).lower()).strip("-")
    return temiz[:40] or "personel-panel"


PANEL_SLUG = os.environ.get("PANEL_SLUG", "").strip() or _slug(PANEL_ADI)
SUNUCU_ADRES = os.environ.get("PANEL_HOST", "127.0.0.1")
SUNUCU_PORT = int(os.environ.get("PANEL_PORT", "8090"))
HTTPS_MI = os.environ.get("PANEL_HTTPS", "") == "1"
OTURUM_SAAT = float(os.environ.get("PANEL_OTURUM_SAAT", "12"))

MAX_GOVDE = 8 * 1024 * 1024
YEDEK_SAYISI = 60          # kaydetme başına yedekten tutulacak en yeni sayı
GUNLUK_SAYISI = 30         # günlük yedekten tutulacak gün sayısı
GEREKLI_ANAHTARLAR = {"calisanlar", "avanslar", "mesailer", "hakEdisler", "odemeler"}
SURUM_ANAHTARI = "_guncelleme"

COOKIE_ADI = "panel_oturum"
DENEME_SINIRI = 5          # pencere içinde izin verilen hatalı giriş
DENEME_PENCERESI = 300     # saniye
ENGELLEME_SURESI = 300     # saniye

KILIT = threading.Lock()
OTURUMLAR = {}             # token -> son kullanma (epoch)
HATALI_DENEMELER = {}      # ip -> [epoch, ...]
BOS_VERI = {k: [] for k in ("calisanlar", "avanslar", "mesailer", "hakEdisler", "odemeler")}

GIRIS_SAYFASI = """<!DOCTYPE html>
<html lang="tr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__AD__ — Giriş</title>
<style>
 *{box-sizing:border-box;margin:0;padding:0}
 body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f3;color:#1a1a18;
      min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
 .k{background:#fff;border:1px solid #e8e8e5;border-radius:14px;padding:28px;width:100%;max-width:360px;
    box-shadow:0 4px 20px rgba(0,0,0,.06)}
 .l{display:flex;align-items:center;gap:10px;margin-bottom:22px}
 .i{width:38px;height:38px;background:#B33A2B;border-radius:10px;display:flex;align-items:center;
    justify-content:center;font-size:20px}
 h1{font-size:15px;font-weight:600}
 p.a{font-size:11px;color:#888;margin-top:2px}
 label{display:block;font-size:12px;color:#666;font-weight:500;margin-bottom:5px}
 input{width:100%;font-size:14px;padding:10px 12px;border-radius:9px;border:1px solid #e8e8e5;
       font-family:inherit;margin-bottom:14px}
 input:focus{outline:none;border-color:#B33A2B;box-shadow:0 0 0 3px rgba(179,58,43,.1)}
 button{width:100%;background:#B33A2B;color:#fff;border:none;padding:11px;border-radius:9px;font-size:14px;
        font-weight:500;cursor:pointer;font-family:inherit}
 button:hover{opacity:.9}
 .h{background:#fee2e2;color:#b91c1c;border-radius:8px;padding:9px 12px;font-size:12px;margin-bottom:14px}
</style></head><body>
<form class="k" method="post" action="giris">
  <div class="l"><div class="i">__IKON__</div><div><h1>__AD__</h1>
  <p class="a">__ALT__</p></div></div>
  __HATA__
  <label for="k">Kullanıcı adı</label>
  <input id="k" name="kullanici" autocomplete="username" autofocus required>
  <label for="p">Parola</label>
  <input id="p" name="parola" type="password" autocomplete="current-password" required>
  <button type="submit">Giriş yap</button>
</form></body></html>
"""


# --------------------------------------------------------------------------- #
#  Yardımcılar
# --------------------------------------------------------------------------- #
def simdi() -> str:
    return datetime.now().isoformat(timespec="seconds")


def json_oku():
    """Veriyi okur. Dosya yoksa/bozuksa hata verir (sessizce boş dönmez)."""
    if not DATA.exists():
        raise RuntimeError("data.json bulunamadi")
    try:
        with open(DATA, encoding="utf-8") as dosya:
            return json.load(dosya)
    except json.JSONDecodeError as hata:
        raise RuntimeError("data.json bozuk: %s" % hata)


def json_yaz(veri: dict) -> None:
    """Atomik yazma: geçici dosya + yerine taşıma."""
    gecici = DATA.with_suffix(".tmp")
    eski_umask = os.umask(0o077)
    try:
        with open(gecici, "w", encoding="utf-8") as dosya:
            json.dump(veri, dosya, ensure_ascii=False, indent=1)
            dosya.flush()
            os.fsync(dosya.fileno())
        os.chmod(gecici, 0o600)
    finally:
        os.umask(eski_umask)
    os.replace(gecici, DATA)


def _temizle(dizin: Path, kalacak: int, desen: str) -> None:
    dosyalar = sorted(dizin.glob(desen))
    for eski in dosyalar[:-kalacak]:
        try:
            eski.unlink()
        except OSError:
            pass


def yedek_al(tur: str = "kayit") -> str | None:
    """Mevcut veriyi yedekler. tur='kayit' (her kaydetme) veya 'gunluk' (günde bir)."""
    if not DATA.exists():
        return None
    if tur == "gunluk":
        GUNLUK_DIZIN.mkdir(exist_ok=True)
        ad = datetime.now().strftime("gunluk-%Y-%m-%d.json")
        hedef = GUNLUK_DIZIN / ad
        if hedef.exists():                      # gün içinde zaten alınmış
            return ad
        shutil.copy2(DATA, hedef)
        _temizle(GUNLUK_DIZIN, GUNLUK_SAYISI, "gunluk-*.json")
        return ad
    YEDEK_DIZIN.mkdir(exist_ok=True)
    ad = datetime.now().strftime("data-%Y%m%d-%H%M%S-%f.json")
    shutil.copy2(DATA, YEDEK_DIZIN / ad)
    _temizle(YEDEK_DIZIN, YEDEK_SAYISI, "data-*.json")
    return ad


def gunluk_yedek_garanti() -> None:
    try:
        yedek_al("gunluk")
    except OSError:
        pass


def yedek_listesi():
    liste = []
    for dizin, ad_onek, tur in ((YEDEK_DIZIN, "data-", "kayıt"), (GUNLUK_DIZIN, "gunluk-", "günlük")):
        if not dizin.exists():
            continue
        for dosya in dizin.glob("*.json"):
            try:
                durum = dosya.stat()
                kayit = None
                try:
                    icerik = json.loads(dosya.read_text(encoding="utf-8"))
                    kayit = {k: len(icerik.get(k) or []) for k in sorted(GEREKLI_ANAHTARLAR)}
                except Exception:
                    kayit = {"hata": "okunamadi"}
                liste.append({
                    "ad": dosya.name,
                    "tur": tur,
                    "zaman": datetime.fromtimestamp(durum.st_mtime).isoformat(timespec="seconds"),
                    "boyut": durum.st_size,
                    "kayit": kayit,
                })
            except OSError:
                continue
    return sorted(liste, key=lambda x: x["zaman"], reverse=True)


def yedek_oku(ad: str) -> dict:
    """Verilen yedek dosyasını okur; yol kaçışına izin vermez."""
    if not re.fullmatch(r"[A-Za-z0-9._-]+", ad or ""):
        raise ValueError("gecersiz yedek adi")
    for dizin in (YEDEK_DIZIN, GUNLUK_DIZIN):
        dosya = dizin / ad
        if dosya.is_file():
            veri = json.loads(dosya.read_text(encoding="utf-8"))
            if not isinstance(veri, dict) or not GEREKLI_ANAHTARLAR.issubset(veri):
                raise ValueError("yedek dosyasi beklenen yapiyi icermiyor")
            return veri
    raise ValueError("yedek bulunamadi")


# --------------------------------------------------------------------------- #
#  Oturum ve giriş denemesi sınırı
# --------------------------------------------------------------------------- #
def oturum_ac() -> str:
    token = secrets.token_urlsafe(32)
    OTURUMLAR[token] = time.time() + OTURUM_SAAT * 3600
    for eski in [t for t, bitis in OTURUMLAR.items() if bitis < time.time()]:
        OTURUMLAR.pop(eski, None)
    return token


def oturum_gecerli(token: str | None) -> bool:
    if not token:
        return False
    bitis = OTURUMLAR.get(token)
    if not bitis:
        return False
    if bitis < time.time():
        OTURUMLAR.pop(token, None)
        return False
    return True


def engelli_mi(ip: str) -> bool:
    denemeler = [t for t in HATALI_DENEMELER.get(ip, []) if time.time() - t < ENGELLEME_SURESI]
    HATALI_DENEMELER[ip] = denemeler
    return len(denemeler) >= DENEME_SINIRI


def hatali_giris_kaydet(ip: str) -> None:
    pencere = [t for t in HATALI_DENEMELER.get(ip, []) if time.time() - t < DENEME_PENCERESI]
    pencere.append(time.time())
    HATALI_DENEMELER[ip] = pencere
    if len(HATALI_DENEMELER) > 500:          # çok sayıda farklı IP'de bellek şişmesin
        simdi = time.time()
        for eski_ip in [k for k, t in list(HATALI_DENEMELER.items())
                        if not t or simdi - t[-1] > ENGELLEME_SURESI]:
            HATALI_DENEMELER.pop(eski_ip, None)


def parola_hash_dogrula(parola: str, kod: str) -> bool:
    """pbkdf2_sha256$iterasyon$tuz$ozet bicimindeki ozeti dogrular."""
    try:
        algoritma, iterasyon, tuz, ozet = kod.split("$", 3)
        if algoritma != "pbkdf2_sha256":
            return False
        hesaplanan = hashlib.pbkdf2_hmac("sha256", parola.encode("utf-8"), tuz.encode("utf-8"), int(iterasyon))
        return hmac.compare_digest(base64.b64encode(hesaplanan).decode("ascii"), ozet)
    except (ValueError, TypeError):
        return False


def girdi_dogru(kullanici: str, parola: str) -> bool:
    if not (PAROLA_HASH or PAROLA):
        return False
    if not hmac.compare_digest(kullanici, KULLANICI):
        return False
    if PAROLA_HASH:
        return parola_hash_dogrula(parola, PAROLA_HASH)
    return hmac.compare_digest(parola, PAROLA)


def basic_dogru(baslik: str) -> bool:
    """Teknik/otomasyon erişimi için Basic desteği (aynı kullanıcı+parola)."""
    if not baslik.startswith("Basic "):
        return False
    try:
        ham = base64.b64decode(baslik[6:]).decode("utf-8")
    except Exception:
        return False
    kullanici, ayrac, sifre = ham.partition(":")
    return bool(ayrac) and girdi_dogru(kullanici, sifre)


# --------------------------------------------------------------------------- #
#  HTTP işleyici
# --------------------------------------------------------------------------- #
class Isleyici(BaseHTTPRequestHandler):
    server_version = "PersonelPaneli/2.2"
    protocol_version = "HTTP/1.1"

    # ---------------------------------------------------------------- yardımcı
    def log_message(self, kalip, *args):
        print("%s - %s" % (self.address_string(), kalip % args), flush=True)

    def _ip(self) -> str:
        return self.headers.get("X-Real-IP") or self.client_address[0]

    def _cerezler(self) -> dict:
        ham = self.headers.get("Cookie", "")
        cikti = {}
        for parca in ham.split(";"):
            ad, ayrac, deger = parca.strip().partition("=")
            if ayrac:
                cikti[ad] = deger
        return cikti

    def _oturum_token(self) -> str | None:
        return self._cerezler().get(COOKIE_ADI)

    def _yetkili_mi(self) -> bool:
        return oturum_gecerli(self._oturum_token()) or basic_dogru(self.headers.get("Authorization", ""))

    def _gonder(self, kod, govde: bytes, tur="application/json; charset=utf-8", ek=None):
        self._govde_bosalt()
        self.send_response(kod)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for ad, deger in (ek or {}).items():
            self.send_header(ad, deger)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(govde)

    def _json_gonder(self, kod, nesne, ek=None):
        self._gonder(kod, json.dumps(nesne, ensure_ascii=False).encode("utf-8"), ek=ek)

    def _yetkisiz(self, mesaj="Yetkisiz erisim"):
        if self._yol().startswith("/api/"):
            return self._json_gonder(401, {"hata": mesaj, "giris_gerekli": True})
        # sayfa isteklerinde giriş formuna yönlendir
        return self._gonder(303, b"", ek={"Location": "giris"})

    def _yol(self) -> str:
        return unquote_plus(self.path.split("?", 1)[0]).rstrip("/") or "/"

    def _sorgu(self) -> dict:
        if "?" not in self.path:
            return {}
        return {k: v[0] for k, v in parse_qs(self.path.split("?", 1)[1]).items()}

    def _govde_oku(self):
        try:
            uzunluk = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._govde_alindi = True
            return None
        if uzunluk <= 0:
            self._govde_alindi = True
            return None
        if uzunluk > MAX_GOVDE:
            # Gövdeyi boşaltma devralır (çok büyükse bağlantı kapatılır).
            return None
        self._govde_alindi = True
        return self.rfile.read(uzunluk)

    def _govde_bosalt(self):
        """Yanıt göndermeden önce okunmamış istek gövdesini boşaltır.

        Aksi hâlde HTTP/1.1 kalıcı bağlantıda gövde bir sonraki istek gibi
        yorumlanır ve bağlantı bozulur (429/413 gibi erken dönüşlerde olur).
        """
        if getattr(self, "_govde_alindi", False):
            return
        self._govde_alindi = True
        try:
            uzunluk = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return
        if uzunluk > MAX_GOVDE + 4096:
            # Çok büyük gövde: bağlantıyı kapatmak daha güvenli.
            self.close_connection = True
            return
        kalan = uzunluk
        while kalan > 0:
            parca = self.rfile.read(min(65536, kalan))
            if not parca:
                break
            kalan -= len(parca)

    # -------------------------------------------------------------------- GET
    def do_GET(self):
        yol = self._yol()

        if yol == "/saglik":
            return self._json_gonder(200, {"durum": "ok"})

        if yol in ("/giris", "/"):
            if yol == "/giris":
                return self._gonder(200, self._giris_sayfasi().encode("utf-8"), "text/html; charset=utf-8")
            if not self._yetkili_mi():
                return self._gonder(200, self._giris_sayfasi().encode("utf-8"), "text/html; charset=utf-8")

        if not self._yetkili_mi():
            return self._yetkisiz()

        if yol in ("/", "/index.html"):
            if not INDEX.exists():
                return self._json_gonder(500, {"hata": "index.html bulunamadi"})
            return self._gonder(
                200, self._panel_sayfasi(), "text/html; charset=utf-8",
                {"Content-Security-Policy": "default-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"},
            )

        if yol == "/api/data":
            try:
                veri = json_oku()
            except Exception as hata:
                return self._json_gonder(500, {"hata": str(hata), "veri_yok": True})
            gunluk_yedek_garanti()
            return self._json_gonder(200, veri)

        if yol == "/api/yedekler":
            try:
                return self._json_gonder(200, {"yedekler": yedek_listesi(), "simdi": simdi()})
            except Exception as hata:
                return self._json_gonder(500, {"hata": str(hata)})

        if yol == "/api/yedek":
            ad = self._sorgu().get("ad", "")
            try:
                veri = yedek_oku(ad)
            except Exception as hata:
                return self._json_gonder(404, {"hata": str(hata)})
            return self._gonder(
                200, json.dumps(veri, ensure_ascii=False, indent=1).encode("utf-8"),
                ek={"Content-Disposition": 'attachment; filename="%s"' % ad.replace('"', "")},
            )

        if yol == "/api/disa-aktar":
            try:
                veri = json_oku()
            except Exception as hata:
                return self._json_gonder(500, {"hata": str(hata)})
            ad = "%s-%s.json" % (PANEL_SLUG, datetime.now().strftime("%Y%m%d-%H%M"))
            return self._gonder(
                200, json.dumps(veri, ensure_ascii=False, indent=1).encode("utf-8"),
                ek={"Content-Disposition": 'attachment; filename="%s"' % ad},
            )

        return self._json_gonder(404, {"hata": "bulunamadi"})

    def do_HEAD(self):
        self.do_GET()

    # ------------------------------------------------------------------- POST
    def do_POST(self):
        yol = self._yol()

        if yol == "/giris":
            return self._giris_yap()
        if yol == "/cikis":
            return self._cikis_yap()

        if not self._yetkili_mi():
            return self._yetkisiz()

        if yol == "/api/data":
            return self._veri_kaydet()
        if yol == "/api/geri-yukle":
            return self._geri_yukle()

        return self._json_gonder(404, {"hata": "bulunamadi"})

    # -------------------------------------------------------------- giriş/çıkış
    def _giris_sayfasi(self, hata: str = "") -> str:
        blok = '<div class="h">%s</div>' % hata if hata else ""
        return (GIRIS_SAYFASI
                .replace("__HATA__", blok)
                .replace("__AD__", html.escape(PANEL_ADI))
                .replace("__ALT__", html.escape(PANEL_ALT_BASLIK or "personel takip"))
                .replace("__IKON__", html.escape(PANEL_IKON)))

    @staticmethod
    def _panel_sayfasi() -> bytes:
        """index.html'i görünüm değişkenleriyle doldurur (marka adı vb.)."""
        ham = INDEX.read_text(encoding="utf-8")
        alt = PANEL_ALT_BASLIK + " · personel takip" if PANEL_ALT_BASLIK else "personel takip"
        return (ham.replace("__AD__", html.escape(PANEL_ADI))
                   .replace("__ALT_SATIR__", html.escape(alt))
                   .replace("__IKON__", html.escape(PANEL_IKON))
                   .replace("__VERI_DIZINI__", html.escape(str(BASE)))
                   .encode("utf-8"))

    def _giris_yap(self):
        ip = self._ip()
        if engelli_mi(ip):
            return self._gonder(
                429, self._giris_sayfasi("Çok fazla hatalı deneme. Lütfen 5 dakika sonra tekrar deneyin.").encode("utf-8"),
                "text/html; charset=utf-8", {"Retry-After": str(ENGELLEME_SURESI)},
            )
        ham = self._govde_oku()
        if ham is None:
            return self._gonder(400, b"gecersiz istek", "text/plain; charset=utf-8")
        alanlar = parse_qs(ham.decode("utf-8", "replace"))
        kullanici = (alanlar.get("kullanici") or [""])[0]
        parola = (alanlar.get("parola") or [""])[0]

        if not girdi_dogru(kullanici, parola):
            hatali_giris_kaydet(ip)
            print("BASARISIZ GIRIS ip=%s kullanici=%r" % (ip, kullanici[:20]), flush=True)
            return self._gonder(
                401, self._giris_sayfasi("Kullanıcı adı veya parola hatalı.").encode("utf-8"),
                "text/html; charset=utf-8",
            )

        token = oturum_ac()
        cerez = "%s=%s; Path=/; HttpOnly; SameSite=Lax; Max-Age=%d%s" % (
            COOKIE_ADI, token, int(OTURUM_SAAT * 3600), "; Secure" if HTTPS_MI else "")
        print("BASARILI GIRIS ip=%s" % ip, flush=True)
        self._gonder(303, b"", ek={"Location": "/personel/", "Set-Cookie": cerez})

    def _cikis_yap(self):
        token = self._oturum_token()
        if token:
            OTURUMLAR.pop(token, None)
        cerez = "%s=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0%s" % (COOKIE_ADI, "; Secure" if HTTPS_MI else "")
        return self._gonder(303, b"", ek={"Location": "/personel/", "Set-Cookie": cerez})

    # ------------------------------------------------------------- veri işlemleri
    def _veri_kaydet(self):
        ham = self._govde_oku()
        if ham is None:
            return self._json_gonder(413, {"hata": "govde boyutu uygun degil"})
        try:
            veri = json.loads(ham.decode("utf-8"))
        except Exception:
            return self._json_gonder(400, {"hata": "gecersiz JSON"})
        if not isinstance(veri, dict) or not GEREKLI_ANAHTARLAR.issubset(veri):
            return self._json_gonder(400, {"hata": "beklenen anahtarlar eksik",
                                           "gerekli": sorted(GEREKLI_ANAHTARLAR)})
        for anahtar in GEREKLI_ANAHTARLAR:
            if not isinstance(veri[anahtar], list):
                return self._json_gonder(400, {"hata": "%s liste olmali" % anahtar})

        zorla = self.headers.get("X-Panel-Zorla") == "1"
        with KILIT:
            try:
                mevcut = json_oku()
            except Exception as hata:
                mevcut = None
                if not zorla:
                    return self._json_gonder(409, {"hata": str(hata), "durum": "mevcut_veri_okunamadi"})

            if mevcut is not None:
                istemci_surum = self.headers.get("X-Panel-Surum", "")
                sunucu_surum = mevcut.get(SURUM_ANAHTARI) or ""
                # Sürüm başlığı hiç göndermeyen istemciler (eski sayfa/eski sürüm)
                # kilitlenmesin: yalnızca sürüm bildiren istemcilerde çakışma aranır.
                if not zorla and istemci_surum and istemci_surum != sunucu_surum:
                    return self._json_gonder(409, {
                        "hata": "Baska bir cihaz/sekmede degisiklik yapilmis.",
                        "durum": "cakisma",
                        "sunucuSurum": sunucu_surum,
                    })
                # kazara bosaltma koruması
                if not zorla and len(veri["calisanlar"]) == 0 and len(mevcut.get("calisanlar") or []) > 0:
                    return self._json_gonder(409, {
                        "hata": "Bu kayit mevcut calisan listesini bosaltiyor.",
                        "durum": "bosaltma",
                    })

            veri[SURUM_ANAHTARI] = simdi()
            try:
                yedek_al("kayit")
                json_yaz(veri)
            except Exception as hata:
                return self._json_gonder(500, {"hata": str(hata)})

        ozet = {k: len(veri[k]) for k in sorted(GEREKLI_ANAHTARLAR)}
        return self._json_gonder(200, {"tamam": True, "zaman": veri[SURUM_ANAHTARI],
                                       "surum": veri[SURUM_ANAHTARI], "kayit": ozet})

    def _geri_yukle(self):
        ham = self._govde_oku()
        if ham is None:
            return self._json_gonder(400, {"hata": "govde yok"})
        try:
            istek = json.loads(ham.decode("utf-8"))
        except Exception:
            return self._json_gonder(400, {"hata": "gecersiz JSON"})
        ad = str(istek.get("ad", ""))
        with KILIT:
            try:
                veri = yedek_oku(ad)
            except Exception as hata:
                return self._json_gonder(404, {"hata": str(hata)})
            try:
                yedek_al("kayit")          # geri yükleme de geri alınabilir olsun
            except OSError:
                pass
            veri[SURUM_ANAHTARI] = simdi()
            try:
                json_yaz(veri)
            except Exception as hata:
                return self._json_gonder(500, {"hata": str(hata)})
        return self._json_gonder(200, {"tamam": True, "yuklenen": ad, "surum": veri[SURUM_ANAHTARI]})


def main():
    if not (PAROLA_HASH or PAROLA):
        raise SystemExit("PANEL_PAROLA veya PANEL_PAROLA_HASH tanimli degil - servis baslatilamaz.")
    if not DATA.exists():
        json_yaz(dict(BOS_VERI))
        print("data.json olusturuldu (bos).", flush=True)
    YEDEK_DIZIN.mkdir(exist_ok=True)
    GUNLUK_DIZIN.mkdir(exist_ok=True)
    gunluk_yedek_garanti()
    sunucu = ThreadingHTTPServer((SUNUCU_ADRES, SUNUCU_PORT), Isleyici)
    sunucu.daemon_threads = True
    print("Panel hazir: http://%s:%d (oturum suresi %.0f saat)" % (SUNUCU_ADRES, SUNUCU_PORT, OTURUM_SAAT), flush=True)
    sunucu.serve_forever()


if __name__ == "__main__":
    main()
