import yfinance as yf
import requests
import datetime
import time
import pandas as pd
import numpy as np
import os

# --- AYARLAR ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
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
    return macd_line.iloc[-1], signal_line.iloc[-1], macd_line.iloc[-2] if len(macd_line) >= 2 else macd_line.iloc[-1]

def bollinger_bands_hesapla(veri, periyot=20, std_dev=2):
    ma = veri['Close'].rolling(window=periyot).mean()
    std = veri['Close'].rolling(window=periyot).std()
    upper = (ma + (std * std_dev))
    lower = (ma - (std * std_dev))
    
    # Band genişliği hesapla (sıkışma tespiti için)
    band_genisligi = (upper - lower) / ma
    
    # Son 20 günün minimum band genişliği
    min_genislik = band_genisligi.rolling(window=20).min().iloc[-1]
    mevcut_genislik = band_genisligi.iloc[-1]
    
    # Sıkışma oranı (1.0 = en dar, 2.0+ = geniş)
    sikisma_orani = mevcut_genislik / min_genislik if min_genislik > 0 else 1.0
    
    return upper.iloc[-1], ma.iloc[-1], lower.iloc[-1], sikisma_orani

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

# ============================================================================
# 🚨 SÜPER SİNYAL KONTROL FONKSİYONU (GÜNCELLENMİŞ)
# ============================================================================
def super_sinyal_kontrol(temiz_hisse, fiyat, fiyat_degisim, hacim_orani, 
                         rsi, macd_line, signal_line, macd_dun, 
                         bb_upper, bb_middle, bb_lower, sikisma_orani):
    """
    Süper sinyal kontrolü - Nadir ve güçlü kombinasyonları tespit eder
    
    KURALLAR:
    1. SÜPER AL: RSI < 30 + Hacim > 2.0x + MACD Al
    2. SÜPER SAT: RSI > 70 + Hacim > 2.0x + MACD Sat
    3. MACD SIFIR KESİŞİMİ (YENİ): MACD sıfırı yukarı/aşağı kesti + Hacim > 1.5x
    4. BB SIKIŞMASI (YENİ): Band sıkışması + Hacim > 1.5x (Büyük hareket habercisi)
    """
    
    super_al = None
    super_sat = None
    sinyal_tipi = []
    
    # 🟢 KURAL 1: SÜPER AL SİNYALİ
    if rsi < 30 and hacim_orani > 2.0 and macd_line > signal_line:
        sinyal_tipi.append("RSI+AşırıSatım+Hacim")
    
    # 🔴 KURAL 2: SÜPER SAT SİNYALİ
    if rsi > 70 and hacim_orani > 2.0 and macd_line < signal_line:
        sinyal_tipi.append("RSI+AşırıAlım+Hacim")
    
    # ⚡ KURAL 3: MACD SIFIR KESİŞİMİ (YENİ!)
    # MACD dün negatif, bugün pozitif → Sıfırı yukarı kesti
    if macd_dun < 0 and macd_line > 0 and hacim_orani > 1.5:
        super_al = (
            f"⚡ <b>MACD SIFIR KESİŞİMİ (YUKARI): {temiz_hisse}</b>\n"
            f"🔥 MACD sıfır çizgisini YUKARI kesti!\n"
            f" Hacim: {hacim_orani:.2f}x (Yükselişi destekliyor)\n"
            f"💰 Fiyat: {fiyat:.2f} TL ({fiyat_degisim:+.2f}%)\n"
            f"📈 Bu güçlü bir trend başlangıcı olabilir!"
        )
        sinyal_tipi.append("MACD_Sıfır_Yukarı")
    
    # MACD dün pozitif, bugün negatif → Sıfırı aşağı kesti
    elif macd_dun > 0 and macd_line < 0 and hacim_orani > 1.5:
        super_sat = (
            f"⚡ <b>MACD SIFIR KESİŞİMİ (AŞAĞI): {temiz_hisse}</b>\n"
            f" MACD sıfır çizgisini AŞAĞI kesti!\n"
            f"⚡ Hacim: {hacim_orani:.2f}x (Düşüşü destekliyor)\n"
            f"💰 Fiyat: {fiyat:.2f} TL ({fiyat_degisim:+.2f}%)\n"
            f"📉 Bu güçlü bir düşüş başlangıcı olabilir!"
        )
        sinyal_tipi.append("MACD_Sıfır_Aşağı")
    
    # 🎯 KURAL 4: BOLLINGER BAND SIKIŞMASI (YENİ!)
    # Band sıkışması + Hacim artışı = Büyük hareket habercisi
    if sikisma_orani < 1.3 and hacim_orani > 1.5:
        # Sıkışma var ve hacim artıyor → Patlama yakında!
        if fiyat > bb_middle:
            # Fiyat orta bandın üzerindeyse → Yukarı patlama ihtimali
            super_al = (
                f" <b>BB SIKIŞMASI + HACİM ARTIŞI: {temiz_hisse}</b>\n"
                f" Bollinger Band SIKIŞTI (Sıkışma Oranı: {sikisma_orani:.2f}x)\n"
                f"⚡ Hacim: {hacim_orani:.2f}x (Hareket başlıyor!)\n"
                f"📊 Fiyat orta bandın ÜSTÜNDE → Yukarı patlama bekleniyor\n"
                f"💰 Fiyat: {fiyat:.2f} TL ({fiyat_degisim:+.2f}%)\n"
                f"🚀 Büyük bir yükseliş hareketi gelebilir!"
            )
            sinyal_tipi.append("BB_Sıkışma_Yukarı")
        else:
            # Fiyat orta bandın altındaysa → Aşağı patlama ihtimali
            super_sat = (
                f"🎯 <b>BB SIKIŞMASI + HACİM ARTIŞI: {temiz_hisse}</b>\n"
                f"🔔 Bollinger Band SIKIŞTI (Sıkışma Oranı: {sikisma_orani:.2f}x)\n"
                f"⚡ Hacim: {hacim_orani:.2f}x (Hareket başlıyor!)\n"
                f"📊 Fiyat orta bandın ALTINDA → Aşağı patlama bekleniyor\n"
                f"💰 Fiyat: {fiyat:.2f} TL ({fiyat_degisim:+.2f}%)\n"
                f"⚠️ Büyük bir düşüş hareketi gelebilir!"
            )
            sinyal_tipi.append("BB_Sıkışma_Aşağı")
    
    # Eğer birden fazla kural sağlandıysa, mesajı güçlendir
    if len(sinyal_tipi) > 1:
        print(f"🚨 {temiz_hisse}: {len(sinyal_tipi)} farklı süper sinyal tespit edildi!")
    
    return super_al, super_sat

def hisse_analizi():
    BIST_HISSELERI = takip_listesi_yukle()
    if not BIST_HISSELERI:
        return
    
    rapor_satirlari = []
    super_al_sinyalleri = []
    super_sat_sinyalleri = []
    
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
            
            fiyat = bugun['Close']
            fiyat_degisim = ((bugun['Close'] - dun['Close']) / dun['Close']) * 100
            hacim_degisim = ((bugun['Volume'] - dun['Volume']) / dun['Volume']) * 100
            
            hacim_20g_ort = veri['Volume'].rolling(window=20).mean().iloc[-1]
            hacim_orani = bugun['Volume'] / hacim_20g_ort if hacim_20g_ort > 0 else 0
            
            rsi = rsi_hesapla(veri)
            macd_line, signal_line, macd_dun = macd_hesapla(veri)
            bb_upper, bb_middle, bb_lower, sikisma_orani = bollinger_bands_hesapla(veri)
            obv, obv_ma = obv_hesapla(veri)
            ma50 = veri['Close'].rolling(window=50).mean().iloc[-1]
            
            temiz_hisse = hisse.replace(".IS", "")
            
            # --- NORMAL ETİKETLEME ---
            etiketler = []
            if hacim_orani >= 1.5:
                etiketler.append("🔥 Hacim Patlaması")
            elif hacim_orani <= 0.7:
                etiketler.append("💤 Düşük Hacim")
            if rsi <= 30:
                etiketler.append("🟢 Aşırı Satım")
            elif rsi >= 70:
                etiketler.append("🔴 Aşırı Alım")
            if macd_line > signal_line:
                etiketler.append(" MACD Al")
            else:
                etiketler.append("📉 MACD Sat")
            if fiyat >= bb_upper:
                etiketler.append("⚠️ BB Üst Band")
            elif fiyat <= bb_lower:
                etiketler.append("⚠️ BB Alt Band")
            if obv > obv_ma:
                etiketler.append("💪 OBV Güçlü")
            
            # BB Sıkışma etiketi ekle
            if sikisma_orani < 1.3:
                etiketler.append("🎯 BB Sıkışma")
            
            etiket_metni = " | ".join(etiketler) if etiketler else "⚪ Normal Seyir"
            
            hisse_bilgisi = (
                f"<b>{temiz_hisse}</b> <i>({etiket_metni})</i>\n"
                f"💰 Fiyat: <b>{fiyat:.2f} TL</b> ({fiyat_degisim:+.2f}%)\n"
                f"📊 Hacim: <b>{hacim_degisim:+.1f}%</b> (Ort: {hacim_orani:.2f}x)\n"
                f"📉 RSI: {rsi:.1f} | MACD: {'' if macd_line > signal_line else '🔴'}\n"
                f" MA50: {ma50:.2f} | BB Sıkışma: {sikisma_orani:.2f}x\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
            )
            rapor_satirlari.append(hisse_bilgisi)
            
            # 🚨 SÜPER SİNYAL KONTROLÜ
            super_al, super_sat = super_sinyal_kontrol(
                temiz_hisse, fiyat, fiyat_degisim, hacim_orani,
                rsi, macd_line, signal_line, macd_dun,
                bb_upper, bb_middle, bb_lower, sikisma_orani
            )
            
            if super_al:
                super_al_sinyalleri.append(super_al)
                print(f"🚨 [{i}/{len(BIST_HISSELERI)}] {temiz_hisse}: SÜPER AL SİNYALİ!")
            
            if super_sat:
                super_sat_sinyalleri.append(super_sat)
                print(f"🚨 [{i}/{len(BIST_HISSELERI)}] {temiz_hisse}: SÜPER SAT SİNYALİ!")
            
            print(f"✅ [{i}/{len(BIST_HISSELERI)}] {temiz_hisse} analiz edildi")
            time.sleep(1.2)
                
        except Exception as e:
            print(f"❌ [{i}/{len(BIST_HISSELERI)}] {hisse} hata: {e}")
            continue

    # ========================================================================
    # 🚨 ÖNCE SÜPER SİNYAL ALARMLARINI GÖNDER (Eğer varsa)
    # ========================================================================
    if super_al_sinyalleri or super_sat_sinyalleri:
        alarm_mesaj = f" <b>SÜPER SİNYAL ALARMI!</b>\n📅 {datetime.date.today()}\n\n"
        
        if super_al_sinyalleri:
            alarm_mesaj += "<b>🟢 SÜPER AL SİNYALLERİ:</b>\n\n"
            alarm_mesaj += "\n\n".join(super_al_sinyalleri)
            alarm_mesaj += "\n\n"
        
        if super_sat_sinyalleri:
            alarm_mesaj += "<b>🔴 SÜPER SAT SİNYALLERİ:</b>\n\n"
            alarm_mesaj += "\n\n".join(super_sat_sinyalleri)
        
        alarm_mesaj += "\n\n<i>️ Bu sinyaller nadir kombinasyonlardır. Yatırım tavsiyesi değildir.</i>"
        
        telegram_mesaj_gonder(alarm_mesaj)
        print(f"\n🚨 {len(super_al_sinyalleri) + len(super_sat_sinyalleri)} süper sinyal alarmı gönderildi!")
        time.sleep(2)
    
    # ========================================================================
    # 📊 SONRA NORMAL RAPORU GÖNDER
    # ========================================================================
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