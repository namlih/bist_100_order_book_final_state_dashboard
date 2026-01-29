# BIST100 Emir Yaşam Döngüsü Analizi (Kasım 2025)

Bu proje, **Borsa İstanbul BIST 100 endeksinde yer alan hisselerin 2025 Kasım ayı boyunca emir defteri verileri** üzerinden,
emirlerin **final state (son durum)** dağılımlarını analiz etmek ve hisseleri karşılaştırmalı olarak incelemek amacıyla hazırlanmış bir Streamlit dashboard uygulamasıdır.

Dashboard, emirlerin gün sonundaki final state dağılımlarını temel alarak metrikler üretir ve hem **hisseler arası kıyaslama**
hem de **hisse bazında günlük / haftalık detay analiz** imkânı sunar.

---

## 🎯 Amaç

- BIST100 hisseleri için emir davranışlarını karşılaştırmalı analiz etmek
- Emirlerin final state dağılımlarından türetilen metriklerle “execution kalitesi” benzeri sinyaller üretmek
- Seçilen hisse için haftalık ve günlük kırılımlarda final state dağılımlarını görselleştirmek

---

## 📌 Final State Tanımları

Bu dashboard aşağıdaki final state değerlerini kullanır:

- **Trade**  
  Emir karşı tarafla eşleşmiş ve işlem görerek gerçekleşmiştir.

- **CanceledByUser**  
  Emir kullanıcı (yatırımcı/algoritma) tarafından iptal edilerek sonlandırılmıştır.

- **Expired**  
  Emir gün sonuna kadar işleme dönüşmeden sistem tarafından kapatılmıştır.

- **New**  
  Emir oluşturulmuş ancak analiz snapshot’ında final state olarak “New” kalmıştır (snapshot/veri kapsamı nedeniyle görülebilir).

---

## 📊 Dashboard İçeriği

### 1) BIST100 Karşılaştırma (Ana Sayfa)
- Tek bir metrik üzerinden BIST100 hisselerini karşılaştırır.
- Seçilen metrik örnekleri:
  - **EQS (w.avg)**: Trade% − CanceledByUser% − Expired%
  - Trade%, CanceledByUser%, Expired%
  - Cancel/Trade oranı

### 2) Hisse Detayı
Seçilen hisse için:
- **Hafta hafta ortalama** final state yüzdelikleri
- **Hafta hafta toplam** final state emir sayıları
- **Günlük** final state yüzdelikleri ve emir sayıları
- Ay geneli referansları (benchmark) ile kıyaslama

---

## 🗂 Veri

Uygulama, önceden oluşturulmuş aggregate dataset üzerinden çalışır:

- `final_state_daily_bist100.parquet`  
  Kolonlar:
  - `tarih`
  - `islem_kodu`
  - `final_state`
  - `emir_sayisi`
  - `yuzde`

> Not: Bu repo yalnızca dashboard’u çalıştırmak için gerekli olan aggregate veriyi içerir.

---

## 🚀 Kurulum & Çalıştırma

### 1) Bağımlılıkları yükle
```bash
pip install -r requirements.txt
```

### ✅ Doğrulama (Hızlı Test)

Kurulumdan sonra aşağıdaki komut ile uygulamayı çalıştır:

```bash
streamlit run app.py
```
