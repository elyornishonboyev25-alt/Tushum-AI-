# Tushum AI

Ulgurji savdo uchun nasiya, tushum va mijoz bilan kelishuvlarni boshqaruvchi Flutter ilova. Android va brauzer interfeysi bir kod bazasidan yig‘iladi. Server Python FastAPI va SQLite asosida ishlaydi.

## Noutbukda ochish

`Ishga-tushirish.cmd` faylini ishga tushiring yoki PowerShell orqali quyidagi buyruqni bajaring.

```powershell
cd "Tushum-AI-"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1 -OpenBrowser
```

Brauzer manzili `http://localhost:8000`. **Demo ma’lumotlar bilan sinash** tugmasi namunaviy mijozlari bor alohida sinov biznesini yaratadi. Haqiqiy yozuvlar uchun yangi biznes hisobini oching.

Server fonda ishlaydi. Jurnallar `backend/data/server.log` va `backend/data/server-error.log` fayllarida saqlanadi. Old planda ishlatish uchun quyidagi buyruq mavjud.

```powershell
.venv/Scripts/python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Fonda ishga tushirilgan serverni to‘xtatish uchun quyidagi buyruqni bajaring. Keyin `Ishga-tushirish.cmd` orqali qayta ochishingiz mumkin.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop.ps1
```

## Android telefon

1. `scripts/build.ps1 -Target apk` orqali APK yig‘ing. Keyin `releases/tushum-ai-test.apk` faylini telefonga ko‘chiring va o‘rnating.
2. Telefon va noutbukni bir Wi-Fi tarmog‘iga ulang.
3. Noutbukda serverni ishga tushiring. Skript telefon uchun mahalliy IP manzilni chiqaradi.
4. Kirish ekranida **Ulanish sozlamalari** orqali shu manzilni kiriting. Misol `http://192.168.1.10:8000`.
5. Hisobga kiring yoki demo biznes yarating.

Windows tarmoq ruxsati so‘ralsa, foydalanayotgan xususiy tarmoq uchun Python serveriga ruxsat bering. Android emulyatori uchun standart manzil `http://10.0.2.2:8000`.

APK ishlab chiqish imzosi bilan yig‘ilgan sinov versiyasidir. Mahalliy HTTP ulanishi debug yig‘ilishida yoqilgan. Ommaviy tarqatish bosqichida HTTPS server va egasiga tegishli release imzosi sozlanadi. iOS loyiha skeleti mavjud. Uni yig‘ish va qurilmada tekshirish uchun macOS hamda Xcode kerak.

## Funksiyalar

| Bo‘lim | Amallar |
| --- | --- |
| Hisob | Telefon va parol bilan ro‘yxatdan o‘tish, kirish, chiqish, parolni almashtirish |
| Biznes | Nomi, telefoni, sohasi va manzilini tahrirlash |
| Jamoa | Menejer va kuzatuvchi yaratish, huquqini o‘zgartirish, faolsizlantirish |
| Mijozlar | Qo‘shish, tahrirlash, qidirish, filtrlash, saralash, izoh va arxiv |
| Nasiya | Bir mijozga bir nechta nasiya, summa, savdo sanasi, muddat, hujjat raqami, tahrirlash va arxiv |
| To‘lov | Qabul qilingan to‘lovni qo‘lda qayd etish, qisman to‘lov, sana va usul |
| Qaytarim | Biznes egasi orqali qisman yoki to‘liq qaytarim, sabab va audit tarixi |
| Va’dalar | Summa va sana bo‘yicha kelishuv, bo‘lib to‘lash, tahrirlash, bekor qilish va bajarilish holati |
| E’tirozlar | Nasiya bo‘yicha e’tiroz va uning yechimini saqlash |
| Import | XLSX va UTF-8 CSV, ustun moslash, oldindan tekshirish, qator tanlash va takroriy import nazorati |
| Hisobot | Davr tanlash, tushum, qaytarim, sof tushum, kunlik grafik, joriy qoldiq va kechikish muddati |
| Eksport | Excel hisobot va biznes yozuvlarining JSON nusxasi |
| Faoliyat | Amal, foydalanuvchi, sana va izoh bo‘yicha tarix, oldingi amallarni bosqichma-bosqich yuklash |
| Bildirishnoma | Muddati kelgan nasiya, va’da va ochiq e’tiroz, o‘qilganini belgilash |
| Oflayn | Oxirgi nusxani ko‘rish, mijoz, nasiya, to‘lov, yangi va’da, qaytarim va izoh qoralamasini tiklash |

Telegram orqali ovozli AI suhbat, jonli suhbat matni va tasdiqlangan kelishuvni saqlash moduli qo‘shilgan. Uning ishlashi uchun serverdagi Telegram sessiyasi, Gemini API kaliti va biznes ulanishi sozlanadi. Batafsil yo‘riqnoma [ovozli agent hujjatida](docs/voice-agent.md). Oddiy telefon tarmog‘i orqali qo‘ng‘iroq va onlayn karta to‘lovi keyingi integratsiyaga tegishli. Kirish telefon va parol bilan bajariladi. To‘lovni xodim qabul qilingan pulga asoslanib kiritadi.

## Hisob-kitob

- Pul serverda butun tiyin ko‘rinishida saqlanadi. Yozish API so‘rovlarida summa so‘mdagi o‘nlik matn orqali uzatiladi, masalan `"150000.50"`. Javobdagi `amount`, `balance` va `paid` tiyin birligida qaytadi.
- Qoldiq savdo summasidan to‘lovlar ayirilib, qaytarimlar qo‘shilishi orqali hisoblanadi.
- Va’da qoldiqni kamaytirmaydi. Yangi to‘lov ochiq va’dalarga muddati bo‘yicha taqsimlanadi. Qaytarim tegishli taqsimotni yangilaydi.
- Ochiq va’dalar joriy qoldiqqa sig‘ishi kerak. Qoldiqdan ortiq to‘lov va to‘langan summadan ortiq qaytarim rad etiladi.
- Moliyaviy amallar bitta SQLite tranzaksiyasida bajariladi. `X-Operation-Id` bir xil so‘rov qayta yuborilganda uni bir marta qo‘llaydi.
- Nasiya, va’da va e’tiroz tahrirlarida versiya tekshiriladi. Eskirgan shakl boshqa xodimning o‘zgarishini bosib yuborishdan himoyalanadi.
- Arxivlash uchun qoldiq yopilishi kerak. Qaytarim qoldiqni qayta ochsa, mijoz va nasiya ham faol holatga qaytadi.
- Hisobotdagi tushum va qaytarimlar tanlangan davrga tegishli. **Hozirgi nasiya holati** joriy qoldiqni ko‘rsatadi.

## Huquqlar

Biznes egasi barcha amallarni bajaradi. Menejer mijozlar, nasiyalar, to‘lovlar, va’dalar, import va e’tirozlarni boshqaradi. Kuzatuvchi ma’lumotlarni ko‘radi va Excel hisobot yuklaydi. Qaytarim, biznes sozlamalari, jamoa boshqaruvi hamda JSON nusxasi biznes egasiga berilgan. Har bir xodim o‘z parolini almashtirishi mumkin.

API resurslari foydalanuvchining biznesi doirasida tekshiriladi. Parollar `scrypt`, sessiya tokenlari xesh ko‘rinishida saqlanadi. Telefon ro‘yxatdan o‘tishda foydalanuvchi kiritgan identifikator sifatida ishlatiladi. SMS tasdiqlash keyingi integratsiyaga tegishli.

## Qayta yig‘ish va tekshirish

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Target check
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Target all
.venv/Scripts/python.exe -m unittest backend.test_app -v
```

`apk` yoki `web` qiymati bilan alohida platformani yig‘ish mumkin. Web fayllar `mobile/build/web`, APK nusxasi `releases` papkasiga chiqadi. Web yig‘ilishidan keyin serverni qayta ishga tushiring.

Repozitoriyada manba kod, paketlar, ishga tushirish/yig‘ish skriptlari, testlar va yo‘riqnomalar bor. Baza, Telegram sessiyasi, maxfiy kalitlar, `.tooling`, `.venv`, keshlar, dizayn qoralamalari va tayyor APK kiritilmagan. Yangi kompyuterda Python 3.11 yoki yangiroq versiya va Git orqali quyidagi qadamlarni bajaring.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
python scripts/prepare_tools.py flutter
python scripts/prepare_tools.py android
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Target all
```

Tekshirilgan backend paketlari `backend/requirements-lock.txt` faylida qayd etiladi. API tavsifi `/docs` manzilida. Baza `backend/data/tushum.sqlite3` faylida saqlanadi. `TUSHUM_DATABASE` muhit o‘zgaruvchisi orqali boshqa joy tanlanadi. SQLite WAL rejimida ishlaydi. Ishlayotgan bazadan texnik zaxira olishda SQLite backup API orqali izchil nusxa oling.

Brauzer versiyasi FastAPI bilan bir manzildan beriladi. Qurilma nusxasi va sessiya xavfsiz saqlash imkoniyatlariga tayanadi. Lokal ko‘rishda `localhost`, tashqi serverda HTTPS ishlatiladi.

## Kod tuzilishi

- `backend/database.py` — sxema va tranzaksiyalar.
- `backend/domain.py` — pul, qoldiq, va’da va audit qoidalari.
- `backend/security.py` — parol, sessiya va kirish urinishlari.
- `backend/schemas.py` — API so‘rov shartnomalari.
- `backend/imports.py` — XLSX/CSV tekshirish va import.
- `backend/main.py` — API, hisobot va eksport.
- `mobile/lib/core.dart` — API, sessiya va ish maydoni holati.
- `mobile/lib/app.dart` — kirish, navigatsiya va bosh ekran.
- `mobile/lib/customers.dart` — mijoz va moliyaviy yozuv ekranlari.
- `mobile/lib/forms.dart` — tekshiriladigan shakllar va amallar.
- `mobile/lib/insights.dart` — hisobot va faoliyat tarixi.
- `mobile/lib/spreadsheet_import.dart` — import interfeysi.
- `mobile/lib/settings.dart` — biznes, jamoa va hisob sozlamalari.
- `mobile/lib/ui.dart` — umumiy dizayn komponentlari.

Joriy server bitta ilova serveri bilan ishlaydigan SQLite muhitiga mo‘ljallangan. Internetga chiqarishda domen, HTTPS, doimiy saqlash diski, zaxiralash, monitoring va release imzosi sozlanadi.

## Railway orqali joylash

Repozitoriy ildizidagi `Dockerfile` Flutter 3.50.0 bilan veb-interfeysni yig‘adi va Python 3.14 konteynerida FastAPI orqali taqdim etadi. `.railway/railway.ts` yangi `striking-youth / production / Tushum-AI-` servisini boshqaradi: Dockerfile build, `/api/health` tekshiruvi, bitta replica, deploylar orasida nol overlap va `/data` ga ulangan 500 MB doimiy disk.

Ishlayotgan manzil: https://tushum-ai-production-fe6eb70d.up.railway.app. `PORT=8080` va `TUSHUM_DATABASE=/data/tushum.sqlite3` Railway Variables orqali beriladi. Shu HTTPS manzilni APK ichidagi Ulanish sozlamalariga ham kiritish mumkin.

Railway konfiguratsiyasini mahalliy tekshirish uchun Railway CLI va Node.js kerak. SDK versiyasi `package.json` va `package-lock.json` da qayd etilgan. Tekshirilgan versiyalar: Railway CLI 5.75.0 va Railway SDK 3.17.0.

```powershell
npm ci --ignore-scripts
railway link --project a8ae508f-716e-4333-83c8-050b0c6c479a --environment production --service Tushum-AI-
railway config plan
railway config apply --yes
```

Rejani tekshirgandan keyin apply bajariladi. SDK rejasida diskni uzish yoki o‘chirish bo‘lmasligi kerak. Maxfiy o‘zgaruvchilar IaC tomonidan boshqarilmaydi (`variables.managed=false`); Telegram sessiyasi, Gemini API kaliti va USMS rekvizitlari faqat Railway Variables da saqlanadi. Baza, sessiya va maxfiy qiymatlar Git’ga kiritilmaydi. Server bitta worker bilan ishlaydi; bir Telegram sessiyasini bir nechta serverda parallel yoqmang.

## USMS ulanishi

Railway Variables bo‘limida `USMS_LOGIN`, `USMS_SECRET` va `USMS_SENDER` saqlanadi. Biznes egasi ilovadagi Sozlamalar → SMS integratsiyasi sahifasidan biznes identifikatorini nusxalab, `USMS_BUSINESS_ID` ga kiritadi. Shu biznes egasi USMS balansidan foydalanadi. API kalitlari serverda saqlanadi.

Mijoz kartasidagi SMS eslatma orqali tasdiqlangan servis shabloni tanlanadi, o‘zgaruvchilar to‘ldiriladi va haqiqiy narx olinadi. Foydalanuvchi yuborishni tasdiqlaydi. Xabar identifikatori va o‘zgarmas USMS `idem_key` bazada saqlanadi. Yetkazilish holati SMS tarixidan tekshiriladi. USMS hisob tasdig‘i, yetarli balans, servis shabloni va jo‘natuvchi tasdig‘i real yuborish uchun talab qilinadi. Rasmiy API hujjatlari https://api.usms.uz/ manzilida.

SMS sinovlari `python -m unittest backend.test_sms` orqali bajariladi. Ular soxta provayder bilan ishlaydi.

## Joriy tekshirishlar

- Server uchun 56 ta regressiya sinovi bor. Ular parallel to‘lovlar, takroriy so‘rovlar, qaytarimlar, va’da taqsimoti, huquqlar, bizneslar ajratilishi va importni qamrab oladi.
- Flutter uchun 4 ta sinov bor. Aloqa uzilgan saqlashni bir identifikator bilan takrorlash, pul formati, kirish validatsiyasi va kichik ekran tekshiriladi.
- Ro‘yxatdan o‘tish, biznes profilini tahrirlash, xodim qo‘shish, parol almashtirish, chiqish, qayta kirish va menejer huquqlari ham brauzerda tekshirildi.
- APK yig‘ilishi debug sinov imzosi bilan bajariladi. Haqiqiy Android telefonda o‘rnatish va ishlatish sinovi keyingi tekshiruv bosqichidir.


### Qo‘ng‘iroqqa tayyorgarlik va menejer nazorati

AI suhbatlarda birinchi qo‘ng‘iroqdan oldin biznes egasi do‘kon/korxona nomi, mas’ul menejer ismi va biznes aloqa raqamini tasdiqlaydi. Manzil, pasport va karta ma’lumoti so‘ralmaydi. Mijoz, joriy qarz qoldig‘i, nasiya mazmuni va muddati serverdagi hisobdan olinadi; ulanishdan oldin qayta tekshiriladi. Har bir suhbatda o‘sha paytdagi ma’lumotlar nusxasi ko‘rinadi.

Agent avval faqat “Assalomu alaykum” deydi. Salom ijro bo‘lib tugagach javobni kutadi; sukut davom etsa 1,5 soniyadan keyin tanishuv boshlanadi. Javob kelgan bo‘lsa alohida taymer ishorasi yuborilmaydi. Agent kompaniya va AI ekanini aytib, shaxsni aniqlagachgina qarz haqida gaplashadi. Nutqni tanish uchun o‘zbek tili tanlangan. Noaniq summa/sana va kelishuv qayta aniqlashtiriladi; mutlaq ASR aniqligi kafolatlanmaydi.

E’tiroz, to‘langanlik da’vosi, menejer so‘rovi, qayta bog‘lanish, noto‘g‘ri shaxs, aloqa bekor qilinishi va kelishuvsiz yakun uchun alohida menejer murojaati saqlanadi. Bosh sahifada mijoz, holat, xulosa va suhbatga havola ko‘rinadi. Menejer tekshiruv natijasini yozib murojaatni yopadi. Bu amal qarz/to‘lovni o‘zgartirmaydi. E’tiroz ochiq turganda mijoz va nasiya e’tirozli deb belgilanadi. Tasdiqlangan AI va’dalari summa va sanasi bilan dashboard hamda Va’dalar bo‘limida ko‘rinadi.

Suhbat yakunida agent murojaat saqlanganini tasdiqlab xayrlashadi. Server model javobi va navbatdagi ovoz ijrosi tugashini kutadi. Provayder javob bermasa kutish cheklangan. Dashboard ochiq turganda har 5 soniyada yangilanadi. Murojaatlar bizneslar orasida ajratilgan, yakunlar takroriy yozilishdan himoyalangan. Yangi jadvallar mavjud bazaga qo‘shiladi; mavjud qarzlar o‘chirilmaydi.

Tekshiruv: `python -m unittest backend.test_app backend.test_sms backend.test_voice backend.test_voice_turns -q`. Taymer sinovlari haqiqiy ovoz ijrosi navbatini hisobga oladi. Model sinovlari vaqtinchalik bazada bajariladi; Telegram qo‘ng‘irog‘i yuborilmaydi.
