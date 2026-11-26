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

## Jonli ovozli suhbat

Mijoz mikrofoni **to‘g‘ridan-to‘g‘ri `gemini-3.8-live`** modeliga 16 kHz PCM sifatida uzatiladi. AI audioni o‘zi eshitadi va tabiiy ovozli javob beradi. Suhbat yo‘lida alohida STT, ikkinchi eshituvchi, natijalarni solishtirish, so‘zlardan qayta audio yaratish yoki butun javobni kutib turish yo‘q. Javob audiosi kelishi bilan 24 kHz dan 48 kHz Telegram ovoziga aylantirilib ijro qilinadi.

`uz-UZ` ovoz sozlamasi va agent siyosati javoblarni o‘zbekcha qiladi. AI ruscha va aralash nutqni ham eshitadi, javobni o‘zbekcha beradi. Ovoz `Kore`. Odam gapga aralashsa, modelning interruption hodisasi oldingi ijro buferini tozalaydi. Audio diskka saqlanmaydi.

Telegram sukut vaqtida paket bermasa, 900 ms audio kelmaganidan keyin bir marta `audio_stream_end` yuboriladi. Bu haqiqiy audioning tugaganini bildiradi; sun’iy mikrofon paketi yoki mijoz nomidan matnli gap yuborilmaydi. Modelning ichki subtitrlari hisob vositalari va suhbat tarixiga yordam beradi, ammo javob berish uchun ular kutilmaydi va alohida transkripsiya xizmatiga uzatilmaydi. Vaqtinchalik mijoz matni saqlanmaydi.

Moliyaviy yozuvlar hali ham alohida server tekshiruvlaridan o‘tadi: aniq summa va sana, ovozli qayta o‘qish, undan keyingi yangi aniq tasdiq kerak. To‘lov qilganini aytishning o‘zi pul tushumini yaratmaydi. Manfiy/shartli javob yoki e’tiroz tasdiq hisoblanmaydi. Model va uning ichki subtitrlari xato qilishi mumkin; xatosizlik kafolati berilmaydi.

`scripts/evaluate_voice_roundtrip.py` modelning haqiqiy kirish/chiqish audiosini va ilovaning jonli suhbat oqimini izolyatsiyalangan bazada tekshiradi. Faqat Telegram transporti simulyatsiya qilinadi; haqiqiy foydalanuvchiga qo‘ng‘iroq qilinmaydi. Sinovda sukut paketlari yuborilmasligi ham tekshiriladi.

### Jadval va suhbatni tiklash

“Mingni”, “millionni”, “uch yuz mingni bugun” kabi qo‘shimchali summa so‘zlari lotin va o‘zbek kirill yozuvida tekshiriladi. “Uch yuz mingni bugun, qolganini ertaga” bitta aniq qism va haqiqiy qarz qoldig‘ining bitta qolgan qismini bildiradi. Qoldiqdan bir nechta aytilmagan to‘lov yaratib bo‘lmaydi. Aniq aytilgan foiz (“o‘ttiz foizini”) haqiqiy qoldiqdan hisoblanib, ovoz chiqarib qayta o‘qiladi; hali tasdiqlanmaguncha va’da yozilmaydi. “Alo”, shartli gap, savol yoki summa tuzatishi tasdiq bo‘lmaydi.

Vositalar `error_code`, `recoverable` va kerak bo‘lsa `ask_customer` qaytaradi. Summa/sana yetishmasligi, bo‘sh qoldiq yoki tasdiq yetishmasligi texnik nosozlik deb aytilmaydi. Faqat SQLite/hisob xizmati xatosi `accounting_unavailable` bo‘ladi. Tasdiqlanmagan jadvalni saqlangan deb aytish yoki mijoz so‘ramagan menejerga murojaatni texnik nosozlik bilan izohlash tekshiriladi.

Modelning ichki subtitri va moliyaviy vositasi turli tartibda kelishi mumkin. Alohida vosita navbati audioni qabul qilishni bloklamaydi; faqat dalil yetishmagan xatoda yangi yakuniy subtitrni 650 ms gacha kutib, tekshiruvni bir marta takrorlaydi. Yangi gap kelmasa, dalil to‘qilmaydi. Model bekor qilgan tool ID bajarilmaydi va unga javob yuborilmaydi. Bu alohida STT yoki ikkinchi eshituvchi emas.

Xayrlashuv audiosi allaqachon ijroga berilgan bo‘lsa, keyingi “Tugadi” yoki ikkinchi xayrlashuv ijroga berilmaydi. Navbatdagi haqiqiy audio tugagandan keyin aloqa yopiladi; gapning oxiri kesilmaydi.

`voice_tool_events` faqat vosita nomi, xavfsiz natija kodi va vaqtini saqlaydi. Unda summa, mijoz matni, kalit yoki provayder xabari bo‘lmaydi. Bu kelgusida texnik uzilish bilan oddiy aniqlashtirishni ajratib tekshirishga yordam beradi. Eski suhbatlar natijasi qayta yozilmaydi.

Qo‘shimcha ovozli regressiya namunalarini `scripts/evaluate_voice_roundtrip.py --scenario alo_schedule` orqali bajarish mumkin. Boshqa holatlar: `explicit_schedule`, `disputed`, `opt_out`, `conditional`, `already_paid`, `correction`, `busy`. Bular sun’iy audio va simulyatsiyalangan Telegram transporti; haqiqiy odamlarning nutqidagi xatosizlikni isbotlamaydi.

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
