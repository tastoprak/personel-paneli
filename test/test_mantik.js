/*
 * index.html icindeki panel mantigini tarayicisiz calistirip dogrular.
 * Veri kaynagi: ornek-data.json (beklenen degerler bu dosyayla uyumludur).
 * Kullanim: node test/test_mantik.js
 */
const fs = require('fs');
const path = require('path');

const kok = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(kok, 'index.html'), 'utf8');
const js = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const veriYolu = path.join(kok, 'ornek-data.json');

const els = {};
function el(id) {
  if (!els[id]) {
    const siniflar = new Set();
    els[id] = {
      id, value: '', checked: false, innerHTML: '', textContent: '', disabled: false,
      className: '', style: {}, addEventListener() {},
      classList: { add: (c) => siniflar.add(c), remove: (c) => siniflar.delete(c), contains: (c) => siniflar.has(c) },
    };
  }
  return els[id];
}
global.document = { getElementById: el, querySelectorAll: () => [], addEventListener() {} };
global.window = { addEventListener() {} };
global.location = { pathname: '/', href: '' };
const uyarilar = [];
const onaylar = [];
const depo = {};
global.localStorage = {
  getItem: (k) => (k in depo ? depo[k] : null),
  setItem: (k, v) => { depo[k] = String(v); },
  removeItem: (k) => { delete depo[k]; },
};
global.alert = (m) => uyarilar.push(String(m));
global.confirm = (m) => { onaylar.push(String(m)); return true; };
let fetchDurumu = 200;
global.fetch = async () => {
  if (fetchDurumu !== 200) return { ok: false, status: fetchDurumu, json: async () => ({ hata: 'test' }) };
  return { ok: true, status: 200, json: async () => JSON.parse(fs.readFileSync(veriYolu, 'utf8')) };
};

const say = (s) => (String(s).match(/<tr/g) || []).length;
const duz = (s) => String(s).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
let hata = 0;
function kontrol(baslik, gelen, beklenen) {
  const uy = String(gelen) === String(beklenen);
  if (!uy) hata++;
  console.log(`${uy ? 'OK  ' : 'HATA'} ${baslik}${uy ? '' : `\n     gelen: ${gelen}\n     beklenen: ${beklenen}`}`);
}

(async () => {
  eval(js + `
    global.__t = { get db(){return db}, set db(v){db=v}, renderAll, bakiye, aySonuBakiye, ayTutar, rB, yukle, tDurum(){
      return { kirlendi, yuklemeHatasi, surum, cakismaVar };
    }, tutarOku, tutarYaz, bAyDegisti, kaydetC, duzenleC, formTemizle, kaydetB, sched, kaydet, taslakOku, taslakKontrol, taslakSil, kipAyarla, fmt };
  `);
  await new Promise((r) => setTimeout(r, 300));
  const t = global.__t;

  console.log('--- TUTAR OKUMA (Turkce yazim) ---');
  kontrol("'28.000' -> 28000", t.tutarOku('28.000'), 28000);
  kontrol("'1.234,56' -> 1234.56", t.tutarOku('1.234,56'), 1234.56);
  kontrol("'1.234.567' -> 1234567", t.tutarOku('1.234.567'), 1234567);
  kontrol("'28000' -> 28000", t.tutarOku('28000'), 28000);
  kontrol("'104' -> 104", t.tutarOku('104'), 104);
  kontrol("'1,5' -> 1.5", t.tutarOku('1,5'), 1.5);
  kontrol("'1.5' -> 1.5", t.tutarOku('1.5'), 1.5);
  kontrol("'₺ 5.000 ' -> 5000", t.tutarOku('₺ 5.000 '), 5000);
  kontrol("'' -> 0", t.tutarOku(''), 0);
  kontrol("'  ' -> 0", t.tutarOku('   '), 0);

  console.log('--- OZET KARTLARI ---');
  kontrol('Toplam personel bakiyesi', el('s-toplam').textContent, '331.050,00 ₺');
  kontrol('Aktif calisan sayisi', el('s-cal').textContent, '5');
  kontrol('Bu ay hak edis', el('s-hak').textContent, '151.500,00 ₺');
  kontrol('Bu ay avans + odeme', el('s-av').textContent, '69.500,00 ₺');
  kontrol('Bakiye kipi yazisi (varsayilan)', el('s-toplam-alt').textContent, 'Tüm kayıtlar dahil');
  kontrol('Kip aciklamasi (varsayilan)', el('kip-aciklama').textContent.includes('Kayıtlı tüm hareketler'), true);

  console.log('--- CALISAN LISTESI ---');
  kontrol('Tablodaki satir sayisi', say(el('ctb').innerHTML), 5);
  kontrol('Toplam satiri', duz(el('ctf').innerHTML), 'Toplam (5 kişi) 331.050,00 ₺');

  console.log('--- CALISAN BAZINDA BAKIYE ---');
  const beklenen = { K001: 60400.0, K002: 72750.0, K003: 81200.0, K004: 33100.0, K005: 83600.0 };
  Object.keys(beklenen).forEach((kod) => {
    kontrol('Bakiye ' + kod, Math.round(t.bakiye(kod) * 100) / 100, beklenen[kod]);
  });

  console.log('--- MUKERRER KOD KORUMASI ---');
  el('ykod').value = 'K001'; el('yad').value = 'Deneme Kisi';
  uyarilar.length = 0;
  t.kaydetC();
  kontrol('Ayni kodla ekleme engellendi (uyari)', uyarilar.length, 1);
  kontrol('Calisan sayisi degismedi', t.db.calisanlar.length, 5);
  t.duzenleC('K002');
  el('ykod').value = 'K001';
  uyarilar.length = 0;
  t.kaydetC();
  kontrol('Duzenlemede mukerrer kod engellendi (uyari)', uyarilar.length, 1);
  kontrol('K002 hala duruyor', t.db.calisanlar.filter((c) => c.kod === 'K002').length, 1);
  kontrol('Kod degismedi', t.db.calisanlar.filter((c) => c.kod === 'K002')[0].ad, 'Ayşe Demir');
  t.formTemizle();

  console.log('--- PASIF CALISAN TOPLAMDA KALIYOR ---');
  const k003 = t.db.calisanlar.find((c) => c.kod === 'K003');
  k003.aktif = false;
  t.renderAll();
  kontrol('Pasifken toplam ayni', el('s-toplam').textContent, '331.050,00 ₺');
  kontrol('Pasif bilgisi yaziliyor', el('s-toplam-alt').textContent.includes('1 pasif'), true);
  kontrol('Aktif sayisi dustu', el('s-cal').textContent, '4');
  el('bay').value = '2026-10';
  t.rB();
  kontrol('Pasif calisan bordroda gorunuyor', el('btb').innerHTML.includes('Mehmet Kaya'), true);
  k003.aktif = true;
  t.renderAll();

  console.log('--- BORDRO (Ekim 2026) ---');
  el('bay').value = '2026-10';
  t.rB();
  kontrol('Bordro satir sayisi', say(el('btb').innerHTML), 5);
  kontrol('Bordro ozeti', duz(el('b-ozet').innerHTML),
    'Hak ediş: 151.500,00 ₺ Avans: 7.500,00 ₺ Ödeme: 62.000,00 ₺ Ay neti: 82.000,00 ₺ Ay sonu toplam bakiye: 331.050,00 ₺');
  kontrol('Bordro toplam satiri', duz(el('btf').innerHTML),
    'Toplam 151.500,00 ₺ 7.500,00 ₺ 62.000,00 ₺ 82.000,00 ₺ 331.050,00 ₺');

  console.log('--- BORDRO: AY SECILINCE TARIH AYIN SONU ---');
  el('bay').value = '2026-09'; t.bAyDegisti();
  kontrol('Eylul -> 2026-09-30', el('btar').value, '2026-09-30');
  el('bay').value = '2026-02'; t.bAyDegisti();
  kontrol('Subat -> 2026-02-28', el('btar').value, '2026-02-28');
  el('bay').value = '2024-02'; t.bAyDegisti();
  kontrol('Subat (artik yil) -> 2024-02-29', el('btar').value, '2024-02-29');
  el('bay').value = '2026-10'; t.bAyDegisti();
  kontrol('Ekim -> 2026-10-31', el('btar').value, '2026-10-31');

  console.log('--- BORDRO (Eylul 2026 - arsiv donem) ---');
  el('bay').value = '2026-09';
  t.rB();
  kontrol('Eylul bordro toplami (arsiv dahil)', duz(el('btf').innerHTML),
    'Toplam 151.500,00 ₺ 5.500,00 ₺ 88.000,00 ₺ 58.000,00 ₺ 249.050,00 ₺');

  console.log('--- MUKERRER AY UYARISI ---');
  el('bay').value = '2026-10'; el('btur').value = 'hakEdisler'; el('bcal').value = 'K001';
  el('btut').value = '1.000'; el('btar').value = '2026-10-15'; el('bac').value = '';
  onaylar.length = 0;
  t.kaydetB();
  kontrol('Mukerrer kayit onayi istendi', onaylar.length, 1);
  kontrol('Onay metni ay/kodu iceriyor', /Ekim 2026/.test(onaylar[0]) && onaylar[0].includes('K001'), true);
  kontrol('Kayit yine de eklendi (onaylandi)', t.db.hakEdisler.filter((r) => r.kod === 'K001' && r.tarih === '2026-10-15').length, 1);
  t.db.hakEdisler.pop();
  t.renderAll();

  console.log('--- BAKIYE KIPI (tum kayitlar / bugune kadar) ---');
  const hepsiToplam = el('s-toplam').textContent;
  const bugunIso = (() => { const d = new Date(); const p = (n) => String(n).padStart(2, '0'); return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()); })();
  const hesap = () => t.db.calisanlar.reduce((s, c) => {
    const k = (r) => !r.arsiv && !r.silindi && (!r.tarih || r.tarih <= bugunIso);
    const tt = (arr) => arr.filter((r) => r.kod === c.kod && k(r)).reduce((x, r) => x + Number(r.tutar || 0), 0);
    return s + Number(c.devir || 0) + tt(t.db.hakEdisler) - tt(t.db.avanslar) - tt(t.db.odemeler);
  }, 0);
  t.kipAyarla('bugun');
  const bugunToplam = el('s-toplam').textContent;
  kontrol('Bugune kadar toplam (bagimsiz hesap)', bugunToplam, t.fmt(hesap()));
  const sayiya = (s) => parseFloat(String(s).replace(/\./g, '').replace(',', '.').replace(/[^\d.-]/g, ''));
  kontrol('Bugune kadar <= tum kayitlar', sayiya(bugunToplam) <= sayiya(hepsiToplam), true);
  kontrol('Bugune kadar butonu secili', el('kip-bugun').classList.contains('on'), true);
  kontrol('Tum kayitlar butonu secili degil', el('kip-hepsi').classList.contains('on'), false);
  kontrol('Alt yazi guncellendi', el('s-toplam-alt').textContent, 'Bugüne kadar');
  kontrol('Kip aciklamasi guncellendi', el('kip-aciklama').textContent.includes('Yalnız'), true);
  // 2099 tarihli kayit: "tum kayitlar"da sayilir, "bugune kadar"da sayilmaz
  t.db.hakEdisler.push({ tarih: '2099-01-01', kod: 'K003', tutar: 10000, aciklama: 'test', arsiv: false });
  t.renderAll();
  kontrol('Bugune kadar kipinde ileri tarihli kayit yok sayildi', el('s-toplam').textContent, bugunToplam);
  t.kipAyarla('hepsi');
  kontrol('Tum kayitlar kipinde ileri tarihli kayit sayildi', el('s-toplam').textContent, t.fmt(sayiya(hepsiToplam) + 10000));
  t.db.hakEdisler.pop(); t.renderAll();
  kontrol('Gercek veriye donuldu', el('s-toplam').textContent, hepsiToplam);
  kontrol('Kayit sayisi bozulmadi', t.db.hakEdisler.length, 15);
  kontrol('Kip donusu aciklamasi', el('kip-aciklama').textContent.includes('Kayıtlı tüm hareketler'), true);

  console.log('--- TEK CALISAN ORNEGI (Ekim) ---');
  kontrol('K001 Ekim hak edis', t.ayTutar(t.db.hakEdisler, 'K001', '2026-10', true), 32000);
  kontrol('K001 Ekim avans', t.ayTutar(t.db.avanslar, 'K001', '2026-10', true), 2000);
  kontrol('K001 Ekim ay sonu bakiye', t.aySonuBakiye('K001', '2026-10'), 60400);
  kontrol('K001 Kasim (hareket yok) ay sonu bakiye', t.aySonuBakiye('K001', '2026-11'), 60400);

  console.log('--- TASLAK (kaydedilmemis degisiklik) KORUMASI ---');
  t.sched();
  await new Promise((r) => setTimeout(r, 50));
  kontrol('Degisiklikte taslak yazildi', !!t.taslakOku(), true);
  await t.kaydet(false);
  kontrol('Basarili kayittan sonra taslak silindi', t.taslakOku(), null);
  fetchDurumu = 500;
  t.sched();
  await new Promise((r) => setTimeout(r, 1400));
  kontrol('Kayit hatasinda taslak korundu', !!t.taslakOku(), true);
  fetchDurumu = 200;
  depo['personel-panel-taslak'] = JSON.stringify({ zaman: '2026-10-19T18:00:00', veri: JSON.parse(fs.readFileSync(veriYolu, 'utf8')) });
  t.taslakKontrol();
  kontrol('Taslak uyarisi gosterildi', el('taslak-alani').innerHTML.includes('taslağı geri yükleyip'), true);
  t.taslakSil();

  console.log('--- YUKLEME HATASI KORUMASI ---');
  fetchDurumu = 500;
  await t.yukle();
  kontrol('Yukleme hatasi isaretlendi', t.tDurum().yuklemeHatasi, true);
  fetchDurumu = 200;

  console.log('\n' + (hata ? hata + ' KONTROL BASARISIZ' : 'TUM KONTROLLER BASARILI'));
  process.exit(hata ? 1 : 0);
})();
