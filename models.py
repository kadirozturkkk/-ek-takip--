from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Cek(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cek_turu = db.Column(db.String(20), default='Alınan Çek') # Yeni Alan: Alınan Çek veya Verilen Çek
    musteri_adi = db.Column(db.String(100), nullable=False)
    banka_adi = db.Column(db.String(100), nullable=False)
    tutar = db.Column(db.Float, nullable=False)
    vade_tarihi = db.Column(db.Date, nullable=False)
    durum = db.Column(db.String(20), default='Bekliyor')
    aciklama = db.Column(db.String(200), nullable=True)
    olusturma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Cek {self.cek_turu} - {self.musteri_adi} - {self.tutar}>"