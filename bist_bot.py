import yfinance as yf
import requests
import datetime
import time
import pandas as pd
import numpy as np

# --- AYARLAR ---
TELEGRAM_TOKEN = "8660550988:AAG1QZRBWwvyuj2VrciQIg1Q9c0AcLMrU0U"
CHAT_ID = "1073612922"

# Genişletilmiş BIST Hisse Listesi (100+ Hisse)
BIST_HISSELERI = [
    
    # Teknoloji ve Yazılım
    "ASELS.IS", "LOGO.IS", "FONET.IS", "ALTNY.IS", "EUPWR.IS","GESAN.IS","HTTBT.IS",
    "NETAS.IS", "LINK.IS", "MTRKS.IS", "PATEK.IS","SDTTR.IS", "ASTOR.IS","SMRTG.IS", 
    "MIATK.IS", "YEOTK.IS", "NETCD.IS", "FORTE.IS", "BETAE.IS",
    
    # Popüler Hisseler
    "AKSA.IS","AKSEN.IS", "AYDEM.IS", "AYEN.IS", "BAKAB.IS", "BNTAS.IS", "BIOEN.IS", 
    "BOSSA.IS","BUCIM.IS","BIENY.IS","BRKSN.IS", "CEMTS.IS","CGCAM.IS", "CIMSA.IS", 
    "CWENE.IS","CVKMD.IS","DNISI.IS", "ELITE.IS",  "ENDAE.IS", "ENERY.IS","EMPAE.IS",
    "EUREN.IS","EKIM.IS", "FADE.IS", "GENIL.IS", "GLYHO.IS", "GOLTS.IS", "GEDZA.IS",
    "GOZDE.IS", "GWIND.IS", "HATSN.IS", "HEKTS.IS", "INVEO.IS", "ISDMR.IS", 
    "KBORU.IS", "KLSER.IS", "KLKIM.IS", "KMPUR.IS", "KORDS.IS","KOPOL.IS", "KRDMB.IS", 
    "KRDMA.IS", "KRDMD.IS", "KRSTL.IS", "KRVGD.IS", "KTLEV.IS", "KUTPO.IS","LILAK.IS", 
    "MAKIM.IS", "MAVI.IS", "MEDTR.IS", "MEGMT.IS", "MEKAG.IS",  "MERCN.IS",
    "MPARK.IS", "MRSHL.IS", "NUHCM.IS","ORZAX.IS", "OBAMS.IS", "QUAGR.IS","ONCSM.IS", 
    "ORGE.IS", "OSMEN.IS", "OTKAR.IS", "PNLSN.IS", "PENGD.IS", "PINSU.IS", "RGYAS.IS",
    "RYGYO.IS", "SANFM.IS", "SARKY.IS","TARKM.IS", "TATGD.IS", "TAVHL.IS", 
    "TMPOL.IS", "TEZOL.IS","TOASO.IS", "TRILC.IS","TTRAK.IS", "TTKOM.IS", "TUKAS.IS",  
    "VESBE.IS", "VESTL.IS","UCAYM.IS", "YATAS.IS",]

def telegram_mesaj_gonder(mesaj):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "HTML"}
        requests.post(url, data=data)
    except Exception as e:
        print(f"Telegram gönderim hatası: {e}")

def rsi_hesapla(veri, periyot=14):
    """RSI (Relative Strength Index) hesaplar"""
    delta = veri['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periyot).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periyot).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def macd_hesapla(veri, fast=12, slow=26, signal=9):
    """MACD hesaplar"""
    ema_fast = veri['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = veri['Close'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]

def tradingview_link_olustur(hisse_kodu):
    """TradingView grafik linki oluşturur"""
    temiz_hisse = hisse_kodu.replace(".IS", "")
    return f"https://www.tradingview.com/chart/?symbol=BIST:{temiz_hisse}"

def hisse_analizi():
    guclu_al = []
    guclu_sat = []
    izleme_listesi = []
    
    print("📊 BIST Gün Sonu Analizi Başlıyor...")
    print(f"📅 Tarih: {datetime.date.today()}")
    print(f"📈 Toplam {len(BIST_HISSELERI)} hisse analiz edilecek...")
    print("-" * 60)
    
    for i, hisse in enumerate(BIST_HISSELERI, 1):
        try:
            # Yeterli veri çek (MACD için en az 200 gün gerekli)
            ticker = yf.Ticker(hisse)
            veri = ticker.history(period="1y")
            
            if len(veri) < 50:
                print(f"⚠️ [{i}/{len(BIST_HISSELERI)}] {hisse}: Yeterli veri yok")
                continue
                
            # Bugün ve Dünün verilerini al
            bugun = veri.iloc[-1]
            dun = veri.iloc[-2]
            
            # Fiyat ve Hacim değişimleri
            fiyat = bugun['Close']
            fiyat_degisim = ((bugun['Close'] - dun['Close']) / dun['Close']) * 100
            hacim_degisim = ((bugun['Volume'] - dun['Volume']) / dun['Volume']) * 100
            
            # RSI hesapla
            rsi = rsi_hesapla(veri)
            
            # MACD hesapla
            macd_line, signal_line, histogram = macd_hesapla(veri)
            
            # Hareketli Ortalamalar
            ma50 = veri['Close'].rolling(window=50).mean().iloc[-1]
            ma200 = veri['Close'].rolling(window=200).mean().iloc[-1] if len(veri) >= 200 else None
            
            # Hisse adını temizle
            temiz_hisse = hisse.replace(".IS", "")
            
            # TradingView linki
            tv_link = tradingview_link_olustur(hisse)
            
            # MACD Yorumu
            if macd_line > signal_line:
                macd_yorum = "🟢 Yükseliş"
            else:
                macd_yorum = "🔴 Düşüş"
            
            # Hisse bilgisi oluştur
            hisse_bilgisi = (
                f"<b>{temiz_hisse}</b>\n"
                f"💰 Fiyat: {fiyat:.2f} TL ({fiyat_degisim:+.2f}%)\n"
                f"📊 Hacim: {hacim_degisim:+.2f}%\n"
                f"📉 RSI(14): {rsi:.1f}\n"
                f"📈 MACD: {macd_line:.3f} | Signal: {signal_line:.3f} ({macd_yorum})\n"
                f"📊 MA50: {ma50:.2f} | MA200: {ma200:.2f if ma200 else 'N/A'}\n"
                f"🔗 <a href='{tv_link}'>Grafik Görüntüle</a>\n"
            )
            
            # AKILLI SİNYAL FİLTRELEME (MACD EKLENDİ)
            # 🟢 GÜÇLÜ AL SİNYALİ: RSI < 35 + Fiyat > MA50 + Hacim Artışı + MACD Yükseliş
            if rsi < 35 and fiyat > ma50 and hacim_degisim > 0 and macd_line > signal_line:
                guclu_al.append(hisse_bilgisi)
                print(f"🟢 [{i}/{len(BIST_HISSELERI)}] {temiz_hisse}: GÜÇLÜ AL SİNYALİ")
                
            # 🔴 GÜÇLÜ SAT SİNYALİ: RSI > 75 + Fiyat < MA50 + Hacim Düşüşü + MACD Düşüş
            elif rsi > 75 and fiyat < ma50 and hacim_degisim < 0 and macd_line < signal_line:
                guclu_sat.append(hisse_bilgisi)
                print(f"🔴 [{i}/{len(BIST_HISSELERI)}] {temiz_hisse}: GÜÇLÜ SAT SİNYALİ")
                
            # ⚪ İZLEME LİSTESİ: Diğerleri
            else:
                izleme_listesi.append(hisse_bilgisi)
                print(f"⚪ [{i}/{len(BIST_HISSELERI)}] {temiz_hisse}: İzleme Listesi")
            
            # Yahoo'nun bizi engellememesi için bekleme
            time.sleep(1.5)
                
        except Exception as e:
            print(f"❌ [{i}/{len(BIST_HISSELERI)}] {hisse} işlenirken hata: {e}")
            continue

    # Telegram Mesajı Oluştur
    mesaj = f"📊 <b>BIST Akıllı Sinyal Raporu</b>\n📅 {datetime.date.today()}\n"
    mesaj += f"📈 Analiz Edilen: {len(guclu_al) + len(guclu_sat) + len(izleme_listesi)} Hisse\n\n"
    
    # Güçlü Al Sinyalleri
    if guclu_al:
        mesaj += "<b>🟢 GÜÇLÜ AL SİNYALLERİ</b>\n"
        mesaj += "<i>(RSI &lt; 35 + Fiyat &gt; MA50 + Hacim ↑ + MACD ↑)</i>\n\n"
        mesaj += "\n".join(guclu_al)
        mesaj += "\n"
    else:
        mesaj += "<b>🟢 Güçlü Al Sinyali Yok</b>\n\n"
    
    # Güçlü Sat Sinyalleri
    if guclu_sat:
        mesaj += "<b>🔴 GÜÇLÜ SAT SİNYALLERİ</b>\n"
        mesaj += "<i>(RSI &gt; 75 + Fiyat &lt; MA50 + Hacim ↓ + MACD ↓)</i>\n\n"
        mesaj += "\n".join(guclu_sat)
        mesaj += "\n"
    else:
        mesaj += "<b>🔴 Güçlü Sat Sinyali Yok</b>\n\n"
    
    # İzleme Listesi (İlk 20 hisse)
    if izleme_listesi:
        mesaj += f"<b>⚪ İZLEME LİSTESİ</b> (İlk 20)\n\n"
        mesaj += "\n".join(izleme_listesi[:20])
        if len(izleme_listesi) > 20:
            mesaj += f"\n\n<i>... ve {len(izleme_listesi) - 20} hisse daha</i>"
    
    mesaj += "\n\n<i>⚠️ Bu veriler yatırım tavsiyesi değildir.</i>"

    # Telegram'a Gönder
    telegram_mesaj_gonder(mesaj)
    print("\n" + "=" * 60)
    print("✅ Rapor Telegram'a gönderildi!")
    print(f"📊 Özet: {len(guclu_al)} Al | {len(guclu_sat)} Sat | {len(izleme_listesi)} İzleme")

if __name__ == "__main__":
    hisse_analizi()