from flask import Flask
import os

from app import app

if __name__ == '__main__':
    current_dir = os.path.dirname(os.path.abspath(__file__))
    cert_path = os.path.join(current_dir, 'origin.pem')
    key_path = os.path.join(current_dir, 'origin.key')

    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        print("HATA: SSL sertifika dosyaları bulunamadı!")
        print(f"Aranan dosyalar: \n{cert_path}\n{key_path}")
        exit(1)

    print("HTTPS Sunucu başlatılıyor (port 443)...")
    
    try:
        app.run(
            host='0.0.0.0',
            port=443,
            ssl_context=(cert_path, key_path),
            threaded=True,
            debug=False  
        )
    except Exception as e:
        if "Permission denied" in str(e):
            print("HATA: 443 portu için yönetici hakları gerekiyor!")
            print("Lütfen programı yönetici olarak çalıştırın.")
        else:
            print(f"HATA: {str(e)}")