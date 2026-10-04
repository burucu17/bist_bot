import yfinance as yf
import requests
import datetime
import time
import pandas as pd
import numpy as np

# --- AYARLAR ---
TELEGRAM_TOKEN = "8660550988:AAG1QZRBWwvyuj2VrciQIg1Q9c0AcLMrU0U"
CHAT_ID = "1073612922"
WATCHLIST_FILE = "watchlist.txt"

def telegram_mesaj_gonder(mesaj):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "HTML"}
        requests.post(url, data=data)
    except Exception as e:
        print(f"Telegram gönderim hatası: {e}")

def takip_listesi_yukle():
    try:
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            hisseler = [line.strip() for line in f if line.strip()]
        print(f"✅ Takip listesi yüklendi: {len(hisseler)} hisse")
        return hisseler
    except FileNotFoundError:
        print(f"❌ {WATCHLIST_FILE} dosyası bulunamadı!")
        return []

def rsi_hesapla(veri, periyot=14):
    delta = veri['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periyot).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periyot).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def macd_hesapla(veri, fast=12, slow=26, signal=9):
    ema_fast = veri['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = veri['Close'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line.iloc[-1], signal_line.iloc[-1]

def bollinger_bands_hesapla(veri, periyot=20, std_dev=2):
    ma = veri['Close'].rolling(window=periyot).mean()
    std = veri['Close'].rolling(window=periyot).std()
    return (ma + (std * std_dev)).iloc[-1], (ma - (std * std_dev)).iloc[-1]

def obv_hesapla(veri):
    obv = [0]
    for i in range(1, len(veri)):
        if veri['Close'].iloc[i] > veri['Close'].iloc[i-1]:
            obv.append(obv[-1] + veri['Volume'].iloc[i])
        elif veri['Close'].iloc[i] < veri['Close'].iloc[i-1]:
            obv.append(obv[-1] - veri['Volume'].iloc[i])
        else:
            obv.append(obv[-1])
    obv_series = pd.Series(obv, index=veri.index)
    return obv_series.iloc[-1], obv_series.rolling(window=20).mean().iloc[-1]

def hisse_analizi():
    BIST_HISSELERI = takip_listesi_yukle()
    if not BIST_HISSELERI:
        return
    
    rapor_satirlari = []
    
    print("\n📊 BIST Detaylı Takip Raporu Hazırlanıyor...")
    print(f"📅 Tarih: {datetime.date.today()}")
    print("-" * 60)
    
    for i, hisse in enumerate(BIST_HISSELERI, 1):
        try:
            ticker = yf.Ticker(hisse)
            veri = ticker.history(period="1y")
            
            if len(veri) < 50:
                continue
                
            bugun = veri.iloc[-1]
            dun = veri.iloc[-2]
            
            # Temel Değişimler
            fiyat = bugun['Close']
            fiyat_degisim = ((bugun['Close'] - dun['Close']) / dun['Close']) * 100
            hacim_degisim = ((bugun['Volume'] - dun['Volume']) / dun['Volume']) * 100
            
            # Hacim Analizi
            hacim_20g_ort = veri['Volume'].rolling(window=20).mean().iloc[-1]
            hacim_orani = bugun['Volume'] / hacim_20g_ort if hacim_20g_ort > 0 else 0
            
            # İndikatörler
            rsi = rsi_hesapla(veri)
            macd_line, signal_line = macd_hesapla(veri)
            bb_upper, bb_lower = bollinger_bands_hesapla(veri)
            obv, obv_ma = obv_hesapla(veri)
            ma50 = veri['Close'].rolling(window=50).mean().iloc[-1]
            
            temiz_hisse = hisse.replace(".IS", "")
            
            # --- VURGULAMA / ETİKETLEME MANTIĞI ---
            etiketler = []
            
            # Hacim Vurgusu
            if hacim_orani >= 1.5:
                etiketler.append("🔥 Hacim Patlaması")
            elif hacim_orani <= 0.7:
                etiketler.append("💤 Düşük Hacim")
                
            # RSI Vurgusu
            if rsi <= 30:
                etiketler.append("🟢 Aşırı Satım")
            elif rsi >= 70:
                etiketler.append("🔴 Aşırı Alım")
                
            # MACD Vurgusu
            if macd_line > signal_line:
                etiketler.append("📈 MACD Al")
            else:
                etiketler.append("📉 MACD Sat")
                
            # Bollinger Vurgusu
            if fiyat >= bb_upper:
                etiketler.append("⚠️ BB Üst Band")
            elif fiyat <= bb_lower:
                etiketler.append("⚠️ BB Alt Band")
                
            # OBV Vurgusu
            if obv > obv_ma:
                etiketler.append("💪 OBV Güçlü")
                
            etiket_metni = " | ".join(etiketler) if etiketler else "⚪ Normal Seyir"
            
            # Hisse Bilgi Bloğu
            hisse_bilgisi = (
                f"<b>{temiz_hisse}</b> <i>({etiket_metni})</i>\n"
                f"💰 Fiyat: <b>{fiyat:.2f} TL</b> ({fiyat_degisim:+.2f}%)\n"
                f"📊 Hacim: <b>{hacim_degisim:+.1f}%</b> (Ort: {hacim_orani:.2f}x)\n"
                f"📉 RSI: {rsi:.1f} | MACD: {'🟢' if macd_line > signal_line else '🔴'}\n"
                f"📈 MA50: {ma50:.2f}\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
            )
            
            rapor_satirlari.append(hisse_bilgisi)
            print(f"✅ [{i}/{len(BIST_HISSELERI)}] {temiz_hisse} analiz edildi")
            time.sleep(1.2)
                
        except Exception as e:
            print(f"❌ [{i}/{len(BIST_HISSELERI)}] {hisse} hata: {e}")
            continue

    # --- TELEGRAM MESAJINI PARÇALARA BÖLME ---
    mesaj_basi = f"📊 <b>BIST Detaylı Takip Raporu</b>\n📅 {datetime.date.today()}\n📈 Hisse Sayısı: {len(rapor_satirlari)}\n\n"
    
    mesajlar = []
    mevcut_mesaj = mesaj_basi
    
    for satir in rapor_satirlari:
        if len(mevcut_mesaj) + len(satir) > 3800:
            mesajlar.append(mevcut_mesaj + "\n<i>⚠️ Yatırım tavsiyesi değildir.</i>")
            mevcut_mesaj = f"📊 <b>BIST Detaylı Takip Raporu (Devam)</b>\n📅 {datetime.date.today()}\n\n" + satir
        else:
            mevcut_mesaj += satir
            
    mesajlar.append(mevcut_mesaj + "\n\n<i>⚠️ Bu veriler yatırım tavsiyesi değildir.</i>")
    
    for i, mesaj in enumerate(mesajlar, 1):
        if len(mesajlar) > 1:
            mesaj = f"<b>📄 Sayfa {i}/{len(mesajlar)}</b>\n\n" + mesaj
        telegram_mesaj_gonder(mesaj)
        time.sleep(1)
    
    print("\n" + "=" * 60)
    print(f"✅ Rapor başarıyla gönderildi! ({len(mesajlar)} parça)")

if __name__ == "__main__":
    hisse_analizi()