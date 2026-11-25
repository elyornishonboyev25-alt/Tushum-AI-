# Tushum AI ovozli agenti

Telegram orqali rozilik berilgan sinov qo‘ng‘iroqlari. AI ovozli javob beradi, suhbatni matnga aylantiradi va tasdiqlangan kelishuvni mavjud nasiya hisobiga yozadi. Bu versiya oddiy telefon raqamini termaydi va SMS yubormaydi.

## Ish jarayoni

1. Tadbirkor **AI suhbatlar → AI suhbat boshlash** bo‘limida mijoz ismi, Telegram username va qarz summasini kiritadi. Yangi nasiya uchun to‘lov muddati ko‘rsatiladi. **Mavjud nasiyani tanlash** orqali oldingi yozuv bilan ham qo‘ng‘iroq qilish mumkin.
2. Ishtirokchining qo‘ng‘iroq va suhbatni matnga aylantirishga roziligini belgilaydi.
3. Server Telegram foydalanuvchisini tekshirib, qo‘ng‘iroq qiladi. AI o‘zini tanishtiradi va kim javob berganini aniqlaydi.
4. Mijoz aytgan aniq summa va muddat tekshiriladi. Bo‘lib to‘lashda 1–6 ta qism bir jadval sifatida ko‘rib chiqiladi.
5. AI jadvalni ovoz chiqarib qaytaradi. Keyingi aniq tasdiq kelmaguncha va’da yaratilmaydi.
6. Tasdiqlangan qismlar bitta tranzaksiyada **Va’dalar** bo‘limiga saqlanadi. Qarz qoldig‘i o‘zgarmaydi.
7. Suhbat holati va matni **AI suhbatlar** ekranida yangilanadi. Natija faoliyat tarixida ham qayd etiladi.

Mijoz to‘laganini aytsa, bu menejer tekshiruvi uchun belgi bo‘ladi. Ushbu agentda to‘lov yozish vositasi yo‘q. E’tiroz, qayta aloqa va odam bilan gaplashish talablari suhbat natijasida alohida ko‘rsatiladi. Aloqadan voz kechish mijozning `contact_allowed` belgisini o‘chiradi.

Yangi mijoz va nasiya faqat qo‘ng‘iroqni boshlash tasdiqlanganda bitta tranzaksiyada yaratiladi. Ovozli xizmat ishlamasa yoki boshqa suhbat faol bo‘lsa, yangi yozuvlar saqlanmaydi. Telegram kontakti uchun soxta telefon raqami yaratilmaydi. Username alohida `voice_contacts` jadvalida saqlanadi.

Shu username orqali qayta qo‘ng‘iroq qilinganda bitta ochiq nasiyaning aynan joriy qoldig‘i ishlatiladi. Ism yoki summa mos kelmasa, bir nechta ochiq nasiya bo‘lsa yoxud qarz yopilgan bo‘lsa, foydalanuvchiga mavjud yozuvni tanlash tavsiya qilinadi. Qarzni takror qo‘shish yoki yashirin o‘zgartirish bajarilmaydi.

## Suhbat sifati

Standart model `gemini-3.8-live`, ovoz `Aoede`. Tanlov haqiqiy API bilan o‘tkazilgan suhbat va kelishuvni yozish sinovlariga asoslangan. `extended-thinking` varianti til sinovida yaxshi javob bergan bo‘lsa ham, to‘liq kelishuv sinovida vositalarni ishonchli chaqirmagani uchun standart sifatida tanlanmadi. Ovoz 24 kHz PCM dan Telegram uchun 48 kHz PCM ga aylantiriladi. Mijoz ovozi 16 kHz PCM orqali modelga uzatiladi. Audio fayl saqlanmaydi.

`backend/voice_policy.py` versiyalangan suhbat yo‘riqnomasi. Bu model vaznlarini qayta o‘qitish emas. Yo‘riqnoma mijozning savoliga birinchi javob berish, takrorlashni tushunish, tabiiy qisqa gapirish, tanaffusni kutish va noaniq gapni aniqlashtirishni belgilaydi. Birinchi tanishtiruvda AI ekanini ochiq aytadi.

`input_audio_transcription` uchun `uz-UZ` va `ru-RU` til ko‘rsatmalari hamda biznes va mijoz nomlari lug‘ati yuboriladi. Nutqni tanish va model qarorlarida xato bo‘lishi mumkin. Shuning uchun pul yozuvlari model matnidan bevosita olinmaydi, alohida server tekshiruvlaridan o‘tadi. Tasdiq filtri murakkab yoki shartli javobni rad etib, qayta aniqlashtirishni so‘rashi mumkin.

## Railway sozlamalari

Mavjud FastAPI servisida bitta worker ishlaydi. Bitta Telegram sessiyasini turli serverlarda bir vaqtning o‘zida ishga tushirmang. Railway’da replica sonini 1 saqlang va eski deployment to‘xtaganidan keyin yangisini ishga tushiring. Bir xil sessiya bir necha IP manzilida parallel ishlasa, Telegram uning ruxsatini bekor qilishi mumkin.

Server uchun kerakli muhit o‘zgaruvchilari

| Nomi | Vazifasi |
| --- | --- |
| `TELEGRAM_API_ID` | Telegram ilovasi identifikatori |
| `TELEGRAM_API_HASH` | Ilova maxfiy kaliti |
| `TUSHUM_TELEGRAM_SESSION` | Avval tasdiqlangan foydalanuvchi akkauntining StringSession qiymati |
| `GEMINI_API_KEY` | Ovozli AI uchun server kaliti |
| `TUSHUM_VOICE_MODEL` | `gemini-3.8-live` |
| `TUSHUM_VOICE_CALLER` | Kutilayotgan yuboruvchi username |
| `TUSHUM_VOICE_TARGETS` | Vergul bilan ajratilgan ruxsat etilgan username ro‘yxati |
| `TUSHUM_VOICE_OWNER_PHONE` | Ulanish beriladigan faol biznes egasining kirish raqami. Sozlanganda aynan shu hisob biznesiga ovozli ulanish o‘tkaziladi, boshqa bizneslar ma’lumotlari ko‘chirilmaydi |
| `TUSHUM_VOICE_CUSTOM_TARGETS` | `1` qiymati ulangan biznesga username’ni shaklda kiritish imkonini beradi. Boshqa hisoblar qo‘ng‘iroq qila olmaydi |
| `TUSHUM_VOICE_BUSINESS_ID` | Ulanish beriladigan mavjud biznes. `${{USMS_BUSINESS_ID}}` orqali mavjud SMS biznesiga moslash mumkin |
| `TUSHUM_VOICE_SETUP_CODE` | Muqobil ulash shakli uchun maxfiy kod. Faqat biznes egasi ishlatadi |

Bu qiymatlar Git yoki Flutter build ichiga kiritilmaydi. Akkaunt sessiyasi hisobga kirish huquqini beradi. Uni Railway’ga ko‘chirish uchun egasining roziligi kerak. Mahalliy `backend/data/telegram` papkasi Git va Docker kontekstidan chiqarilgan.

Baza `/data/tushum.sqlite3` manzilida saqlanadi. Yangi jadvallar mavjud ma’lumotni o‘chirmasdan qo‘shiladi. Qayta deploy vaqtida uzilgan suhbat muvaffaqiyatsiz deb belgilanadi va avtomatik qayta terilmaydi. JSON zaxira nusxasi suhbat va matn tarixini ham o‘z ichiga oladi.

Ovozli xizmat sozlanmagan yoki Telegram ishlamasa, hisob-kitobning qolgan API funksiyalari ishlashda davom etadi. Ovozli xizmat tarmoq xatosidan keyin 30 soniyada qayta ulanishga urinadi. Biznesga berilgan username ruxsati va bir vaqtning o‘zida bitta faol suhbat limiti serverda tekshiriladi. Suhbatning eng uzun vaqti 5 daqiqa. Mijozning Telegram maxfiylik sozlamalari qo‘ng‘iroqqa ruxsat berishi kerak. Botga yoki qo‘ng‘iroq qiluvchi akkauntning o‘ziga qo‘ng‘iroq boshlanmaydi.

## Tekshirish

```powershell
.venv/Scripts/python.exe -m unittest backend.test_app backend.test_sms backend.test_voice -v
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Target check
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Target web
```

Server testlari bizneslar orasidagi ajratish, rozilik, ruxsat etilgan manzil, bir marta boshlash, bekor qilish, aniq tasdiq, muddat, qoldiq, to‘lovni taxmin qilmaslik va bo‘lib to‘lashning tranzaksiya yaxlitligini tekshiradi.

Haqiqiy demo oldidan rozilik bergan telefon bilan quyidagilarni tekshiring

- Gapni bo‘lish, “eshitmadim”, “sekinroq”, boshqa tilda gapirish yoki fon shovqini.
- Noaniq vaqt, summa, qisman to‘lov, bir nechta muddat, oldingi gapni tuzatish.
- Tasdiqlash, rad etish, shartli “ha, lekin…” va tasdiqsiz uzib qo‘yish.
- To‘laganini aytish, hisobga e’tiroz, noto‘g‘ri odam, aloqadan voz kechish.
- Internet uzilishi, model kvotasi, telefonning javob bermasligi va server qayta ishga tushishi.

Dashboarddagi birinchi ovoz vaqti aynan shu suhbatdagi o‘lchovdir. Keyingi javoblarning kechikishi, talaffuz sifati va tabiiyligi alohida haqiqiy ovoz sinovida baholanadi. Barcha gaplarni xatosiz tushunish yoki odamdan farqsiz bo‘lish kafolati yo‘q.
