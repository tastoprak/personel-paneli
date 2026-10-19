#!/usr/bin/env python3
"""PANEL_PAROLA_HASH degeri uretir (parolayi duz metin tutmamak icin).

Kullanim:
    python3 parola-hash.py            # parolayi gizli sorarak okur
    python3 parola-hash.py 1000000    # iterasyon sayisini degistirir

Cikti ornegi:
    pbkdf2_sha256$600000$tUz$OzEt

Bu degeri ortam dosyasina tek tirnak icinde yazin:
    PANEL_PAROLA_HASH='pbkdf2_sha256$600000$tUz$OzEt'
"""
import base64
import getpass
import hashlib
import secrets
import sys


def uret(parola: str, iterasyon: int = 600_000) -> str:
    tuz = secrets.token_urlsafe(12)
    ozet = hashlib.pbkdf2_hmac("sha256", parola.encode("utf-8"), tuz.encode("utf-8"), iterasyon)
    return "pbkdf2_sha256$%d$%s$%s" % (iterasyon, tuz, base64.b64encode(ozet).decode("ascii"))


def main() -> None:
    iterasyon = int(sys.argv[1]) if len(sys.argv) > 1 else 600_000
    parola = getpass.getpass("Parola: ")
    if len(parola) < 8:
        raise SystemExit("Parola en az 8 karakter olmali.")
    if parola != getpass.getpass("Parola (tekrar): "):
        raise SystemExit("Parolalar ayni degil.")
    print(uret(parola, iterasyon))


if __name__ == "__main__":
    main()
