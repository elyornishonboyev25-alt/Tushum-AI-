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

`uz-UZ` ovoz sozlamasi va agent siyosati javoblarni o‘zbekcha qiladi. AI ruscha va aralash nutqni ham eshitadi, javobni o‘zbekcha beradi. Ovoz `Kore`. Suhbat navbat bilan bo‘ladi: AI gapini tugatib, ijro navbati bo‘shagach va 200 ms ovoz oxiri o‘tgach mikrofon ochiladi. Shu paytgacha kiruvchi ovoz tashlab yuboriladi; keyin qayta ijro qilinmaydi. API’da `NO_INTERRUPTION` ham yoqilgan. Audio diskka saqlanmaydi.

Ovoz 180 ms boshlang‘ich bufer bilan ijro qilinadi. Oqim vaqtincha yetishmasa, qayta boshlash buferi bosqichma-bosqich 400 ms gacha oshadi; kichik paket kelishi bilanoq qayta-qayta boshlashdan saqlaydi. Tugagan qisqa javob ushbu chegarani kutmaydi. PCM namunalari, balandligi va ohangi o‘zgartirilmaydi; soxr HQ orqali 24 kHz dan 48 kHz ga aylantirish saqlanadi. Tarmoq kechikishidagi 10 soniyalik sun’iy audio taqqoslashida avvalgi 60 ms bufer 2 marta bo‘shagan, 180 ms bufer bo‘shamagan; ikkala holatda ham barcha 1000 audio kadr saqlangan. Bu haqiqiy telefon tarmog‘idagi uzilishsizlik kafolati emas.

Kiruvchi 16 kHz PCM avval CPU’dagi Silero VAD orqali nutq/shovqinga ajratiladi. 96 ms ketma-ket nutq belgisi bo‘lmaguncha model navbati ochilmaydi; 320 ms oldingi ovoz birinchi bo‘g‘inni saqlaydi. Oddiy “ha”, “yo‘q”, “alo” so‘zlari uzun gap talab qilinmasdan o‘tadi. Nutqning asl PCM’i VAD uchun ishlatiladi; modelga uzatiladigan ovozda statsionar fon shovqini yumshoq spektral filtr bilan kamaytiriladi. Filtr shovqinni faqat nutq ehtimoli past bo‘lganda o‘rganadi, so‘z paytida shovqin profilini o‘zgartirmaydi va pasaytirish 8 dB bilan cheklangan. 16 ms overlap/add kechikishi gap oxirida chiqarib yuboriladi. Bu boshqa odamning ovozini har doim ajratadigan tizim emas.

Mijoz gap orasida o‘ylashi uchun oxirgi nutqdan so‘ng 1,28 soniya kutiladi. Telegram sukut paketlarini bermasa ham shu kutishdan keyin filtr oxiri chiqarilib, `activity_end` bir marta yuboriladi. `automatic_activity_detection.disabled=true` bilan `activity_start`/`activity_end` ishlatiladi; `audio_stream_end` yuborilmaydi. Bu [Live API’ning qo‘lda VAD tartibi](https://aistudio.google.com/docs/live-api/capabilities#disable-automatic-vad) va [NO_INTERRUPTION sozlamasi](https://aistudio.google.com/api-reference/live#ActivityHandling)ga mos. Alohida STT yoki mijoz nomidan sun’iy matnli gap qo‘shilmaydi.

Agent “hmm”, nafas, yo‘tal va ma’nosiz fon tovushiga “nima dedingiz?” deb javob bermasdan jim kutishi kerak. Bunday tovushlar to‘lov tasdig‘i emas. Mavjud native subtitrda faqat “hmm/хм/mmm” kabi tovush kelganda qo‘shimcha himoya ortiqcha model javobini ijroga chiqarmaydi va hisob vositalarini bajarmaydi; keyingi haqiqiy gap odatdagidek davom etadi. “Ha”, “yo‘q”, “alo”, “да”, “нет” va tovush ortidan kelgan haqiqiy gap bu to‘siqqa tushmaydi. Bu qo‘shimcha STT yoki subtitrni majburiy kutish emas. Haqiqiy so‘zli murojaat noaniq bo‘lgandagina qisqa aniqlashtirish mumkin. Modelning ichki subtitrlari hisob vositalari va suhbat tarixiga ham yordam beradi. Vaqtinchalik mijoz matni saqlanmaydi.

Moliyaviy yozuvlar hali ham alohida server tekshiruvlaridan o‘tadi: aniq summa va sana, ovozli qayta o‘qish, undan keyingi yangi aniq tasdiq kerak. To‘lov qilganini aytishning o‘zi pul tushumini yaratmaydi. Manfiy/shartli javob yoki e’tiroz tasdiq hisoblanmaydi. Model va uning ichki subtitrlari xato qilishi mumkin; xatosizlik kafolati berilmaydi.

`scripts/evaluate_voice_roundtrip.py` modelning haqiqiy kirish/chiqish audiosini va ilovaning jonli suhbat oqimini izolyatsiyalangan bazada tekshiradi. Faqat Telegram transporti simulyatsiya qilinadi; haqiqiy foydalanuvchiga qo‘ng‘iroq qilinmaydi. Sinovda sukut paketlari yuborilmasligi ham tekshiriladi.

### Jadval va suhbatni tiklash

“Mingni”, “millionni”, “uch yuz mingni bugun” kabi qo‘shimchali summa so‘zlari lotin va o‘zbek kirill yozuvida tekshiriladi. “Uch yuz mingni bugun, qolganini ertaga” bitta aniq qism va haqiqiy qarz qoldig‘ining bitta qolgan qismini bildiradi. Qoldiqdan bir nechta aytilmagan to‘lov yaratib bo‘lmaydi. Aniq aytilgan foiz (“o‘ttiz foizini”) haqiqiy qoldiqdan hisoblanib, ovoz chiqarib qayta o‘qiladi; hali tasdiqlanmaguncha va’da yozilmaydi. “Alo”, shartli gap, savol yoki summa tuzatishi tasdiq bo‘lmaydi.

Vositalar `error_code`, `recoverable` va kerak bo‘lsa `ask_customer` qaytaradi. Summa/sana yetishmasligi, bo‘sh qoldiq yoki tasdiq yetishmasligi texnik nosozlik deb aytilmaydi. Faqat SQLite/hisob xizmati xatosi `accounting_unavailable` bo‘ladi. Tasdiqlanmagan jadvalni saqlangan deb aytish yoki mijoz so‘ramagan menejerga murojaatni texnik nosozlik bilan izohlash tekshiriladi.

Modelning ichki subtitri va moliyaviy vositasi turli tartibda kelishi mumkin. Alohida vosita navbati audioni qabul qilishni bloklamaydi; faqat dalil yetishmagan xatoda yangi yakuniy subtitrni 650 ms gacha kutib, tekshiruvni bir marta takrorlaydi. Yangi gap kelmasa, dalil to‘qilmaydi. Model bekor qilgan tool ID bajarilmaydi va unga javob yuborilmaydi. Bu alohida STT yoki ikkinchi eshituvchi emas.

Xayrlashuv bir qisqa jumla bilan tugaydi: “Rahmat, yaxshi qoling.” Oldin qayta o‘qilgan summa/sana yana sanalmaydi va yangi savol berilmaydi. Model `finish_call` ni yubormasa ham aytilgan xayrlashuv suhbatni yakunlaydi. Mijoz xayrlashsa, yangi takliflar to‘xtaydi; oldingi o‘qilgan loyiha uchun yangi aniq tasdiq bilan birga xayrlashilgan bo‘lsa, o‘sha tasdiq bir marta tekshiriladi.

Audio navbati tugagach 250 ms tinish va monitorning 100 ms tekshiruvidan so‘ng avval Telegram aloqasi uziladi. AI WebSocket yopilishining sekin javobi telefonni ushlab turmaydi. Xayrlashuv matni audio paketidan oldin kelsa, joriy ovozning oxiri saqlanadi. Yakun signali kelmasa, so‘nggi audio paketidan 900 ms sukutda filtr oxiri chiqariladi; model umuman javob bermasa, eski 15 soniyalik kutish o‘rniga 4 soniyalik chegara ishlatiladi. Bu tarmoqdagi haqiqiy uzish vaqti uchun kafolat emas; vaqtlar server va simulyatsiyalangan transportda tekshiriladi.

### Shu suhbat ichidagi xotira

Har qo‘ng‘iroq uchun alohida `CallMemory` bor. Unda mijozning yakuniy qaydidan ism/kimlikka javob, gaplashish qulayligi, summa haqidagi gapi va sana haqidagi gapi kichik hajmda, asl so‘zlari bilan saqlanadi. Bu moliyaviy tasdiq yoki alohida STT emas. Aniqlashtirish so‘rovi javob o‘rniga yozilmaydi; miqdor tuzatilsa, oxirgi gap oldingisini almashtiradi. Boshqa savolga o‘tilganda oldingi summa va sana yo‘qolmaydi. Ma’lumot boshqa qo‘ng‘iroqqa avtomatik ko‘chirilmaydi.

Mavjud native audio sessiyasiga `send_context_update` orqali xotira yangilanadi. Sun’iy mijoz gapi yuborilmaydi, ovoz ijrosi kutib turilmaydi va ikkinchi model chaqirilmaydi. Bir xil yangilanish qayta yuborilmaydi, yaqin hodisalar birlashtiriladi. Yangilash ishlamasa, native ovozli suhbat davom etadi. Modelga oldin javob berilgan savolni qaytarmaslik, faqat yetishmayotgan ma’lumotni so‘rash va bir noma’lum joyni ikki martadan ko‘p so‘ramaslik ko‘rsatiladi. Tanish va suhbat modeli hali ham xato qilishi mumkin; bu qat’iy xatosizlik kafolati emas.

SDK kontekst yangilash tartibi: [Google GenAI `send_context_update`](https://googleapis.github.io/python-genai/genai.html). `--scenario memory_once`, `--scenario memory_partial` va `--scenario confirm_goodbye` ovozli regressiya sinovlari aytilgan ma’lumotni qayta so‘ramaslik va xayrlashuvdan keyingi uzish oralig‘ini tekshiradi.

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

Server testlari bizneslar orasidagi ajratish, rozilik, ruxsat etilgan manzil, bir marta boshlash, bekor qilish, aniq tasdiq, muddat, qoldiq, to‘lovni taxmin qilmaslik va bo‘lib to‘lashning tranzaksiya yaxlitligini tekshiradi. `backend.test_voice_audio` ovoz uzunligi, spektr, paket chegaralari va gap oxirini; `backend.test_voice_input` real Silero bilan shovqin, yumshoq filtr, 1,28 s pauza, mikrofonning ijro oxirida ochilishi va “hmm”ga ortiqcha javobning bloklanishini tekshiradi. `backend.test_voice_transcription` native subtitrning yakuniy/vaqtinchalik matni va qisqa ma’noli so‘zlarni ikkilanishdan ajratishni tekshiradi. Eski alohida STT yordamchilari jonli suhbatga ulanmagan.

Sintetik ovoz va real API tekshiruvi noutbukdan bajariladi; Telegram sessiyasi ulanmaydi va hech kimga qo‘ng‘iroq yuborilmaydi:

```powershell
.venv/Scripts/python.exe scripts/evaluate_voice_quality.py --out backend/data/voice-evaluation
.venv/Scripts/python.exe scripts/evaluate_voice_roundtrip.py --out backend/data/voice-evaluation --language uz
.venv/Scripts/python.exe scripts/evaluate_voice_roundtrip.py --out backend/data/voice-evaluation --language ru
.venv/Scripts/python.exe scripts/evaluate_voice_roundtrip.py --out backend/data/voice-evaluation --scenario noise_patience --noise-snr 12
```

Kalit `GEMINI_API_KEY` orqali yoki Gitga kirmaydigan mahalliy JSON uchun `--credentials` bilan beriladi. Sinov API kvotasidan foydalanadi. Sakkiz tanish holati o‘zbekcha, ruscha, aralash nutq, inkor, summa tuzatishi va ikki shovqinli variantni qamrab oladi. Sintetik namunalar real suhbat aniqligini to‘liq o‘lchamaydi. Avtomatik talaffuz bahosi tanlovga yordamchi bo‘lib, mutaxassisning eshitib baholashini almashtirmaydi.

Haqiqiy demo oldidan rozilik bergan telefon bilan quyidagilarni tekshiring

- Gapni bo‘lish, “eshitmadim”, “sekinroq”, boshqa tilda gapirish yoki fon shovqini.
- Noaniq vaqt, summa, qisman to‘lov, bir nechta muddat, oldingi gapni tuzatish.
- Tasdiqlash, rad etish, shartli “ha, lekin…” va tasdiqsiz uzib qo‘yish.
- To‘laganini aytish, hisobga e’tiroz, noto‘g‘ri odam, aloqadan voz kechish.
- Internet uzilishi, model kvotasi, telefonning javob bermasligi va server qayta ishga tushishi.

Dashboarddagi birinchi ovoz vaqti — buferdan chiqqan birinchi model PCM paketi Telegramga yuborilguncha o‘lchangan vaqt. Kutish paytidagi sun’iy sukut paketi bu hisobga kirmaydi. Telefon qurilmasidagi yakuniy eshitish kechikishi alohida. Keyingi javoblarning kechikishi, talaffuz sifati va tabiiyligi haqiqiy ovoz sinovida baholanadi. Barcha gaplarni xatosiz tushunish yoki odamdan farqsiz bo‘lish kafolati yo‘q.
