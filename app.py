import csv
from datetime import date, datetime, timedelta
from io import StringIO
from flask import Flask, flash, make_response, redirect, render_template, request, url_for
from models import Cek, db
from flask_mail import Mail, Message
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cektakip.db'
app.config['SECRET_KEY'] = 'cektakip_gizli_anahtar_2026'

# --- E-POSTA (Flask-Mail) SSL AYARLARI ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

app.config['MAIL_USERNAME'] = 'senin_eposta_adresin@gmail.com' 
app.config['MAIL_PASSWORD'] = '16_haneli_uygulama_sifren' 
app.config['MAIL_DEFAULT_SENDER'] = 'senin_eposta_adresin@gmail.com'

ALICI_EPOSTA = 'senin_eposta_adresin@gmail.com'

mail = Mail(app)
db.init_app(app)

with app.app_context():
    db.create_all()

# --- OTOMATİK E-POSTA GÖREVİ ---
def vadesi_yaklasan_cekleri_maille():
    with app.app_context():
        bugun = date.today()
        yaklasan_cekler = Cek.query.filter(
            Cek.durum == 'Bekliyor',
            Cek.vade_tarihi <= (bugun + timedelta(days=3))
        ).order_by(Cek.vade_tarihi.asc()).all()

        if yaklasan_cekler:
            icerik = "Merhaba,\n\nAşağıdaki çeklerin vadesi gelmiş veya 3 günden az süre kalmıştır. Lütfen gerekli kontrolleri sağlayın:\n\n"
            for c in yaklasan_cekler:
                kalan_gun = (c.vade_tarihi - bugun).days
                durum_not = f"{abs(kalan_gun)} GÜN GECİKTİ" if kalan_gun < 0 else ("BUGÜN VADESİ" if kalan_gun == 0 else f"{kalan_gun} Gün Kaldı")
                icerik += f"• [{c.cek_turu}] [{durum_not}] | Müşteri: {c.musteri_adi} | Banka: {c.banka_adi} | Tutar: ₺{c.tutar:,.2f} | Vade: {c.vade_tarihi.strftime('%d.%m.%Y')}\n"
            
            icerik += "\nİyi çalışmalar,\nÇek Takip Sistemi"

            msg = Message(subject="⚠️ Acil: Yaklaşan Çek Ödemesi Hatırlatması",
                          recipients=[ALICI_EPOSTA],
                          body=icerik)
            try:
                mail.send(msg)
            except Exception as e:
                print(f"E-posta hatası: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(func=vadesi_yaklasan_cekleri_maille, trigger="cron", hour=9, minute=0)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@app.route('/')
def index():
    q = request.args.get('q', '')
    durum_filtre = request.args.get('durum', '')
    tur_filtre = request.args.get('cek_turu', '')

    query = Cek.query
    if q:
        query = query.filter((Cek.musteri_adi.ilike(f'%{q}%')) | (Cek.banka_adi.ilike(f'%{q}%')))
    if durum_filtre:
        query = query.filter_by(durum=durum_filtre)
    if tur_filtre:
        query = query.filter_by(cek_turu=tur_filtre)

    ceks = query.order_by(Cek.vade_tarihi.asc()).all()

    bugun = date.today()
    toplam_tutar = sum(c.tutar for c in ceks if c.durum == 'Bekliyor')
    toplam_adet = len(ceks)
    
    vadesi_gelenler_adet = sum(1 for c in ceks if c.vade_tarihi <= bugun and c.durum == 'Bekliyor')
    yaklasan_cekler = [c for c in ceks if c.durum == 'Bekliyor' and 0 < (c.vade_tarihi - bugun).days <= 3]
    
    durum_bekliyor = sum(1 for c in ceks if c.durum == 'Bekliyor')
    durum_odendi = sum(1 for c in ceks if c.durum == 'Ödendi')
    durum_yazildi = sum(1 for c in ceks if c.durum == 'Yazıldı')

    # --- KAYITLI KİŞİLER / FİRMALAR LİSTESİ ---
    tum_cekler = Cek.query.all()
    kisiler_dict = {}
    for c in tum_cekler:
        adi = c.musteri_adi.strip()
        if adi not in kisiler_dict:
            kisiler_dict[adi] = {"adet": 0, "toplam_tutar": 0, "tur": c.cek_turu}
        kisiler_dict[adi]["adet"] += 1
        kisiler_dict[adi]["toplam_tutar"] += c.tutar
    
    kayitli_kisiler = [{"isim": k, "adet": v["adet"], "tutar": v["toplam_tutar"], "tur": v["tur"]} for k, v in kisiler_dict.items()]

    return render_template('index.html', ceks=ceks, toplam_tutar=toplam_tutar, toplam_adet=toplam_adet,
                           vadesi_gelenler_adet=vadesi_gelenler_adet, yaklasan_cekler=yaklasan_cekler, bugun=bugun,
                           durum_bekliyor=durum_bekliyor, durum_odendi=durum_odendi, durum_yazildi=durum_yazildi,
                           kayitli_kisiler=kayitli_kisiler)

@app.route('/add', methods=['POST'])
def add_cek():
    vade_tarihi = datetime.strptime(request.form.get('vade_tarihi'), '%Y-%m-%d').date()
    yeni_cek = Cek(
        cek_turu=request.form.get('cek_turu'),
        musteri_adi=request.form.get('musteri_adi'),
        banka_adi=request.form.get('banka_adi'),
        tutar=float(request.form.get('tutar')),
        vade_tarihi=vade_tarihi,
        aciklama=request.form.get('aciklama')
    )
    db.session.add(yeni_cek)
    db.session.commit()
    flash('Çek başarıyla eklendi!', 'success')
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['POST'])
def edit_cek(id):
    cek = Cek.query.get_or_404(id)
    cek.cek_turu = request.form.get('cek_turu')
    cek.musteri_adi = request.form.get('musteri_adi')
    cek.banka_adi = request.form.get('banka_adi')
    cek.tutar = float(request.form.get('tutar'))
    cek.vade_tarihi = datetime.strptime(request.form.get('vade_tarihi'), '%Y-%m-%d').date()
    cek.aciklama = request.form.get('aciklama')
    db.session.commit()
    flash('Çek bilgileri başarıyla güncellendi!', 'success')
    return redirect(url_for('index'))

@app.route('/update_status/<int:id>/<string:yeni_durum>')
def update_status(id, yeni_durum):
    cek = Cek.query.get_or_404(id)
    cek.durum = yeni_durum
    db.session.commit()
    flash(f'Çek durumu "{yeni_durum}" olarak güncellendi.', 'info')
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete_cek(id):
    cek = Cek.query.get_or_404(id)
    db.session.delete(cek)
    db.session.commit()
    flash('Çek sistemden silindi.', 'danger')
    return redirect(url_for('index'))

@app.route('/export_excel')
def export_excel():
    ceks = Cek.query.order_by(Cek.vade_tarihi.asc()).all()
    si = StringIO()
    cw = csv.writer(si, delimiter=';')
    cw.writerow(['Çek Türü', 'Müşteri / Firma', 'Banka Adı', 'Tutar (TL)', 'Vade Tarihi', 'Durum', 'Açıklama'])
    for c in ceks:
        cw.writerow([c.cek_turu, c.musteri_adi, c.banka_adi, f"{c.tutar:.2f}", c.vade_tarihi.strftime('%d.%m.%Y'), c.durum, c.aciklama or ''])
    output = make_response(si.getvalue().encode('utf-8-sig'))
    output.headers["Content-Disposition"] = "attachment; filename=cek_listesi.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8-sig"
    return output

@app.route('/test_mail')
def test_mail():
    vadesi_yaklasan_cekleri_maille()
    flash('Manuel mail testi tetiklendi!', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)