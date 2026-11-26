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

Standart model `gemini-3.8-live`, ovoz `Kore`. `TUSHUM_VOICE_NAME` orqali boshqa qo‘llanadigan ovozni tanlash mumkin. O‘zbekcha va ruscha javoblar hamda aralash nutq qo‘llanadi. Yetti ovoz bir xil ikki tilli matn bilan solishtirildi; bu kichik, sintetik sinov, insonlar baholagan MOS tadqiqoti emas. Talaffuz va tabiiylik uchun haqiqiy foydalanuvchi ovozi bilan tekshiruv kerak.

24 kHz PCM ovoz soxr HQ orqali holatni saqlagan holda 48 kHz PCM ga aylantiriladi. Paket o‘rtasida bo‘lingan 16-bit namunalar tashlab yuborilmaydi; oqim tugaganda filtr qoldig‘i ham chiqariladi. 60 ms boshlang‘ich bufer tarmoqdagi qisqa tebranishlarni yumshatadi. Gap bo‘linganda bufer va filtr birga tozalanadi. Mijoz ovozi 16 kHz PCM orqali uzatiladi. Kirish oqimi to‘lib ketsa, nutqni yashirin kesib davom etish o‘rniga suhbat `audio_quality` kodi bilan yakunlanadi. Audio fayl saqlanmaydi.

`backend/voice_policy.py` versiyalangan suhbat yo‘riqnomasi. Bu model vaznlarini qayta o‘qitish emas. Yo‘riqnoma mijozning savoliga birinchi javob berish, takrorlashni tushunish, tabiiy qisqa gapirish, tanaffusni kutish va noaniq gapni aniqlashtirishni belgilaydi. Birinchi tanishtiruvda AI ekanini ochiq aytadi.

2026-11-26 dan nutqni yozib olish suhbat modelidan ajratilgan. Oqim: **mijoz PCM ovozi → `gemini-3.5-transcribe-live` → yakuniy matn → `gemini-3.8-live` javobi**. STT faqat audio oladi; unga suhbat tarixi, qarz summasi, mijoz nomi, tayyor gaplar yoki system prompt yuborilmaydi. `VERBATIM`, `uz-UZ` va `ru-RU` ishlatiladi. `SMART` tahrirlash, tarjima va matnni generativ to‘ldirish qo‘llanmaydi. Suhbat modeli audio olmaydi va uning hech bir input/output subtitri mijoz gapi sifatida yozilmaydi.

Faqat STT’ning yakuniy `input_transcription` hodisasi mijoz matni bo‘ladi. Vaqtinchalik `interim_input_transcription` faqat gapni bo‘lishni aniqlashga xizmat qiladi; dashboard yoki bazaga mijozning yakuniy gapi sifatida saqlanmaydi. Matn qayta yozilmaydi, o‘zbek lotin/kirill yozuvi va sonlarning xizmat qaytargan shakli saqlanadi. Masalan, mijoz haqiqatan “Tushundim” desa, bu so‘z o‘chirilmaydi; AI aytgan “Tushundim” esa faqat AI tomonida turadi.

`voice_transcript.source` yangi yozuvlarda `dedicated_stt_verbatim` yoki `agent_output` bo‘ladi. Migratsiya avvalgi matnlarni o‘zgartirmasdan `legacy` bilan belgilaydi. Dashboard mijoz nutqi va AI javobini alohida ko‘rsatadi; avvalgi yozuvlar qayta eshitilgandek ko‘rsatilmaydi.

320 ms boshlang‘ich audio konteksti, 900 ms provider sukut chegarasi va bir soniyalik mahalliy pauzadan keyingi yakunlash signali ishlatiladi. Sukut va juda past signal matn uchun dalil bo‘lmaydi. Bu signal tekshiruvi so‘zlarning semantik aniqligi yoki ishonch balli emas. Pauzadan keyin olti soniyada yakuniy matn kelmasa, AI qayta aytishni so‘raydi; vaqtinchalik taxmin tasdiqqa aylantirilmaydi. STT uzilsa, `stt_unavailable` qayd etiladi va suhbat modeli taxminiy transkript bilan uning o‘rnini bosmaydi. Kutish paytida moliyaviy vositalar bloklanadi.

Bu ajratish alohida STT API oqimidan foydalanadi va uning kvotasi/xarajati bor; yangi provayder akkaunti talab qilinmaydi. Shovqin, juda past ovoz, sheva va aralash tildagi nutqda STT ham xato qilishi mumkin. Qo‘ng‘iroqdan oldin STT ulanishi ochiladi, ammo faqat yakuniy matn mavjudligi uning barcha so‘zlari to‘g‘ri ekanini anglatmaydi.

Nutqni tanish va model qarorlarida xato bo‘lishi mumkin. Pul yozuvlari alohida server tekshiruvlaridan o‘tadi. “Да, всё правильно, спасибо” kabi aniq tasdiqlar tushuniladi; “да, но…”, shartli javob, summa/sana tuzatishi yoki savol ko‘rinishidagi “Да?” tasdiq sifatida saqlanmaydi. Inson kabi xatosiz gapirish yoki tushunish kafolati berilmaydi. Bu yangilanish model vaznlarini qayta o‘qitish emas: oqim, tanish sozlamalari va versiyalangan suhbat yo‘riqnomasi yaxshilangan.

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
| `TUSHUM_VOICE_NAME` | Ixtiyoriy; standart `Kore`. API qo‘llaydigan ovoz nomi |
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
.venv/Scripts/python.exe -m unittest discover -s backend -t . -v
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Target check
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Target web
```

Server testlari bizneslar orasidagi ajratish, rozilik, ruxsat etilgan manzil, bir marta boshlash, bekor qilish, aniq tasdiq, muddat, qoldiq, to‘lovni taxmin qilmaslik va bo‘lib to‘lashning tranzaksiya yaxlitligini tekshiradi. `backend.test_voice_audio` ovoz uzunligi, spektr, paket chegaralari, gap oxiri va bo‘lishni; `backend.test_voice_stt` alohida STT sozlamasi, manbalar ajratilishi, sukut/shovqin, vaqtinchalik matnni saqlamaslik, pauza va qayta so‘rashni tekshiradi. `backend.test_voice_transcription` eski oqimning yordamchi funksiyasini tekshiradi; yangi runtime undan foydalanmaydi.

Sintetik ovoz va real API tekshiruvi noutbukdan bajariladi; Telegram sessiyasi ulanmaydi va hech kimga qo‘ng‘iroq yuborilmaydi:

```powershell
.venv/Scripts/python.exe scripts/evaluate_voice_quality.py --out backend/data/voice-evaluation
.venv/Scripts/python.exe scripts/evaluate_voice_roundtrip.py --out backend/data/voice-evaluation --language uz
.venv/Scripts/python.exe scripts/evaluate_voice_roundtrip.py --out backend/data/voice-evaluation --language ru
```

Kalit `GEMINI_API_KEY` orqali yoki Gitga kirmaydigan mahalliy JSON uchun `--credentials` bilan beriladi. Sinov API kvotasidan foydalanadi. Sakkiz tanish holati o‘zbekcha, ruscha, aralash nutq, inkor, summa tuzatishi va ikki shovqinli variantni qamrab oladi. Sintetik namunalar real suhbat aniqligini to‘liq o‘lchamaydi. Avtomatik talaffuz bahosi tanlovga yordamchi bo‘lib, mutaxassisning eshitib baholashini almashtirmaydi.

Haqiqiy demo oldidan rozilik bergan telefon bilan quyidagilarni tekshiring

- Gapni bo‘lish, “eshitmadim”, “sekinroq”, boshqa tilda gapirish yoki fon shovqini.
- Noaniq vaqt, summa, qisman to‘lov, bir nechta muddat, oldingi gapni tuzatish.
- Tasdiqlash, rad etish, shartli “ha, lekin…” va tasdiqsiz uzib qo‘yish.
- To‘laganini aytish, hisobga e’tiroz, noto‘g‘ri odam, aloqadan voz kechish.
- Internet uzilishi, model kvotasi, telefonning javob bermasligi va server qayta ishga tushishi.

Dashboarddagi birinchi ovoz vaqti — buferdan chiqqan birinchi model PCM paketi Telegramga yuborilguncha o‘lchangan vaqt. Kutish paytidagi sun’iy sukut paketi bu hisobga kirmaydi. Telefon qurilmasidagi yakuniy eshitish kechikishi alohida. Keyingi javoblarning kechikishi, talaffuz sifati va tabiiyligi haqiqiy ovoz sinovida baholanadi. Barcha gaplarni xatosiz tushunish yoki odamdan farqsiz bo‘lish kafolati yo‘q.
