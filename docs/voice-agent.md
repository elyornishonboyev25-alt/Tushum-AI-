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

AI **faqat tabiiy o‘zbek tilida** javob beradi; ruscha va aralash nutqni tushunishi saqlanadi. `speech_config.language_code=uz-UZ` va versiyalangan siyosat birgalikda ishlaydi. Mijoz ruscha javob so‘rasa ham o‘zbekcha javob qaytariladi. Lotincha o‘zbek tilida javob beriladi, kirillcha ism va korxona nomi lotincha aytiladi. Ovoz `Kore`, suhbat modeli `gemini-3.8-live`.

Javobning butun matni tekshirilmaguncha audio ijroga berilmaydi. Kirillcha yoki aniqlangan ruscha javob tashlab yuboriladi va bir marta o‘zbekcha qayta javob so‘raladi; yana xato bo‘lsa `voice_language` bilan suhbat to‘xtaydi. Bu skript/ibora tekshiruvi talaffuzning yoki barcha tillarning matematik isboti emas. Javobni to‘liq tekshirish nutq boshlanishiga qo‘shimcha kutish qo‘shadi.

24 kHz PCM soxr HQ orqali filtr holatini saqlab, 48 kHz Telegram PCM ga aylantiriladi. Bo‘lingan 16-bit namunalar va filtr oxiri saqlanadi; 60 ms ijro buferi tarmoqdagi qisqa tebranishlarni yumshatadi. Mijoz gapirsa, oldingi javob va ijro buferi tozalanadi. Kirish oqimi to‘lsa, so‘zlarni jimgina tashlash o‘rniga suhbat xatolik bilan to‘xtaydi.

### Mijoz nutqi va AI javobi alohida

Mijozning 16 kHz PCM oqimidan **Silero VAD ONNX** odam nutqini aniqlaydi. Model CPU da ishlaydi; GPU, PyTorch va yangi provayder kerak emas. Har bir suhbatning holati alohida. 320 ms boshlang‘ich kontekst va 1.28 soniyalik pauza chegarasi gapdagi tabiiy to‘xtashlar, sonning davomi va tuzatishni birga eshitishga yordam beradi. Shovqin/sukutning o‘zi transkripsiya so‘rovini boshlamaydi. Bir gap uchun ko‘pi bilan 30 soniya audio xotirada turadi; diskka yozilmaydi. Juda uzun gapning oxirgi bo‘lagi alohida kelishuv deb qabul qilinmaydi.

To‘liq gap quyidagi ikki alohida tanish oqimida tekshiriladi:

- `gemini-3.5-transcribe-live`: `VERBATIM`, `uz-UZ` va `ru-RU` til ko‘rsatmalari, qo‘lda belgilanadigan gap boshi/oxiri. Hisobdagi summa, ism, suhbat AI javoblari va kutilayotgan matn unga berilmaydi.
- Alohida `gemini-3.8-live` eshituvchi sessiyasi: **faqat input transkripsiyasi** o‘qiladi. Uning javob matni va audiosi mijoz nutqiga yoki ijroga hech qachon qo‘shilmaydi. Bu sessiyaga hisob va suhbat agenti yo‘riqnomasi berilmaydi.

Sonlar, inkor, shartlilik, tanilgan sana/vaqt belgisi yoki matn sezilarli farq qilsa, ayni audio `uz-UZ` ko‘rsatmasi bilan qayta taniladi. Ikkita natija yetarlicha mos kelmasa, yakuniy matn saqlanmaydi va qayta aytish so‘raladi. Bu moslik tekshiruvi ishonch foizi emas: ikki model bir xil xato qilishi mumkin. So‘zlar yozilishida farq bo‘lsa ham o‘sha audio qayta tanilib, qo‘shimcha natija ikkinchi eshituvchiga yaqinroq bo‘lsa tanlanadi; tayyor matn qo‘lda yoki chat modeli bilan tuzatilmaydi. Imlo uchun qo‘shimcha urinish to‘rt soniya bilan cheklanadi va uning uzilishi allaqachon ikki eshituvchi tekshirgan natijani bekor qilmaydi. Qo‘shimcha o‘zbekcha tanish ulanishi kerak bo‘lganda ochilib, keyin suhbat davomida saqlanadi. Bekor qilingan gapning kechikkan natijasi keyingi gapga biriktirilmaydi. Tanish tugamasdan odam gapini davom ettirsa, oldingi matn bekor qilinib, ikkala bo‘lak birga qayta eshitiladi.

Faqat tekshirilgan yakuniy matn suhbat agentiga beriladi. Vaqtinchalik so‘zlar, AI aytgan “Tushundim” yoki sukut mijoz nutqi sifatida yozilmaydi. Summa kiritish vositasi taklifdagi raqamni mijoz aytgan raqamlarga ham solishtiradi; mijoz aniq “yarmini/hammasini” deganda tegishli ulush ishlatilishi mumkin. Har kelishuv hali ovozli qayta o‘qish va yangi aniq tasdiqdan o‘tadi. To‘lov aytilgani hisobdagi pulni o‘zgartirmaydi.

`voice_transcript.source` yangi yozuvlarda `dedicated_stt_verbatim` yoki `agent_output`. Eski yozuvlar `legacy` bo‘lib qoladi, qayta yozilmaydi. Yangi manba belgisi eski xatolarni orqadan to‘g‘rilagandek ko‘rsatmaydi.

Qo‘ng‘iroqdan oldin VAD va tanish ulanishlari ochiladi. Ulanish uzilsa ayni audio yangi ulanishda bir marta qayta taniladi. Natija baribir olinmasa `stt_unavailable`, kvota tugasa qayta ulanmasdan `ai_quota` qayd etiladi; tasdiqlanmagan natija bilan davom etilmaydi. Tanish va til qayta ishlanayotganida moliyaviy vositalar bloklanadi. Tanish ulanishlari va qo‘shimcha eshituvchining provayder xarajati/kvotasi bor. Qisqa qo‘ng‘iroqda ham qo‘shimcha vaqt va xarajatni amalda kuzatish kerak.

Bu o‘zgarish model vaznlarini o‘qitish emas. Sintetik audio, shovqin, sukut, inkor, tuzatish va aralash til bilan regressiya tekshiriladi. Haqiqiy shevalar, past ovoz, tarmoq siqilishi va shovqinda xato yoki qayta aytish talabi qolishi mumkin; 100% aniqlik kafolati berilmaydi. `scripts/evaluate_voice_roundtrip.py` haqiqiy tanish, suhbat, til tekshiruvi, ijro va hisob vositalarini izolyatsiyalangan bazada ishlatadi; faqat Telegram transporti simulyatsiya qilinadi. Hech kimga qo‘ng‘iroq qilinmaydi.

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
