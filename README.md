# SitWatch-Legacy
Python + Flask ile yapılan SitWatch.



## Kurulum

```bash
pip install -r requirements.txt
```



## Veri Tabanı Oluşturma

```bash
flask db init
flask db migrate
flask db upgrade
```

site.db dosyası oluşturulur.


## Waitress ile Çalıştırma

```bash
waitress-serve --listen=*:5000 app:app
```
(Nginx veya Apache gibi bir web server gerektirmiyor.)


## .env dosyasını düzenleme

```bash
SECRET_KEY=gizli_anahtarınız
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/buraya_discord_webhook_url_yazın
```


### Temel Özellikler
1. **Kullanıcı Sistemi**
- Kayıt ve giriş sistemi
- Profil yönetimi
- Şifre değiştirme
- Profil açıklaması ve banner düzenleme
- Arkadaşlık sistemi

2. **Video Sistemi**
- Video yükleme ve paylaşma
- Video görüntüleme
- Beğeni sistemi (like, mid-like, dislike)
- Video yorumları
- Thumbnail oluşturma

3. **Moderasyon Özellikleri**
- Admin paneli
- Kullanıcı rollerini yönetme (founder, admin)
- IP bazlı yasaklama sistemi
- Kullanıcı raporlama sistemi

4. **Bildirim Sistemi**
- Kanal yorumları bildirimleri
- Video yorumları bildirimleri
- Rapor sonuç bildirimleri
- Arkadaşlık istekleri bildirimleri

5. **Güvenlik Özellikleri**
- SSL yönlendirme
- Rate limiting (istek sınırlama)
- VPN/Proxy kontrolü
- Güvenli oturum yönetimi

6. **API Desteği**
- Video bilgilerini getirme
- Yorum sistemi API'leri
- Bildirim sistemi API'leri

7. **Diğer Özellikler**
- Önbellek sistemi
- Bakım modu
- Ziyaretçi takibi
- Discord webhook entegrasyonu
- KVKK, Gizlilik Politikası ve Kullanım Şartları sayfaları

### Teknik Özellikler
- Flask web framework'ü
- SQLite veritabanı
- Waitress WSGI sunucusu
- Flask-Login kullanıcı yönetimi
- Flask-Migrate veritabanı migrasyonları
- Jinja2 şablon motoru

