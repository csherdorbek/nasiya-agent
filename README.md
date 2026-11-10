# Nasiya agenti — Instagram uchun o'z botingiz

Hech qanday pullik platformasiz ishlaydi: Instagram'ga to'g'ridan-to'g'ri Meta API orqali ulanadi,
ma'lumotlar o'z serveringizdagi bazada saqlanadi.

## Nima qiladi

1. Mijoz Instagram Direct'ga yozadi → bot model va muddatni (3/6/9/12 oy) so'raydi.
2. Rozilik oladi ("Roziman").
3. F.I.Sh, **pasport seriyasi va raqami** (AD1234567), **JShShIR** (14 raqam) va telefonni so'raydi,
   formatini tekshiradi, xato bo'lsa qayta so'raydi.
4. Ariza menejer paneliga tushadi (+ ixtiyoriy Telegram xabarnoma).
5. Menejer paneldagi tugma orqali **mib.uz**'ni ochadi, natijani kiritadi (qarz yo'q yoki qarz turi + summa).
6. Agent qoida bo'yicha avtomatik qaror chiqaradi va mijozga o'zi yozadi:

| MIB natijasi | Qaror | Mijozga |
|---|---|---|
| Qarz yo'q | **Lead** | "Arizangiz qabul qilindi" |
| Faqat ma'muriy jarima, jami ≤ 10 mln so'm | **Lead** | "Arizangiz qabul qilindi" |
| Ma'muriy jarima > 10 mln so'm | Rad | sababi bilan |
| Undiruv qarzi (kredit, nasiya, aliment, kommunal, soliq, sud, reyestr) | Rad | qarz turi va summasi bilan |

7. Leadlar panelda va **Excel (CSV)** faylda.

### Nega mib.uz'ni menejer tekshiradi

MIB'ning ochiq API'si yo'q, mib.uz esa avtomatik so'rovlardan himoyalangan. Saytni bot bilan
"aylanib o'tish" qoidaga zid va tez-tez buziladi. Shuning uchun bitta tekshiruv menejerga ~1 daqiqa
oladi, qolgan hamma ishni (suhbat, qaror, mijozga javob, lead) agent qiladi. MIB yoki KATM bilan rasmiy
API shartnomasi bo'lsa, `rules.decide()` ga natijani shu API'dan berish kifoya — qoidalar o'zgarmaydi.

## Ishga tushirish

### 1. Server
Har qanday VPS (masalan, 5–6 $/oy) yoki Render/Railway. HTTPS manzil kerak.

```bash
pip install -r requirements.txt
cp .env.example .env      # qiymatlarni to'ldiring
export $(cat .env | xargs)
uvicorn app:app --host 0.0.0.0 --port 8000
```
yoki Docker: `docker build -t nasiya . && docker run -p 8000:8000 --env-file .env -v nasiya:/data nasiya`  (Railway: Volume /data ga ulanadi)

### 2. Instagram'ni ulash (bir marta)
1. Instagram akkauntni **Professional (Business)** ga o'tkazing.
2. developers.facebook.com → **Create App** → turi "Business".
3. **Instagram** mahsulotini qo'shing → "API setup with Instagram login" → akkauntingizni ulang,
   **Access token** oling → `IG_ACCESS_TOKEN`.
4. App Settings → Basic → **App Secret** → `META_APP_SECRET`.
5. Webhooks: Callback URL = `https://sizning-domen.uz/webhook`, Verify token = `META_VERIFY_TOKEN`
   qiymati. **messages** maydoniga obuna bo'ling.
6. Ilovani **Live** rejimiga o'tkazing (aks holda faqat test foydalanuvchilarga javob beradi).

### 3. Menejer paneli
`https://sizning-domen.uz/admin` — login `ADMIN_USER`, parol `ADMIN_PASSWORD`.

### 4. Telegram xabarnoma (ixtiyoriy)
@BotFather'da bot yarating → token `TELEGRAM_BOT_TOKEN`; o'zingizning chat ID'ingiz `TELEGRAM_CHAT_ID`.
Xabarda pasport va JShShIR yuborilmaydi — faqat ism, model va panelga havola.

## Xavfsizlik
- Pasport va JShShIR faqat serveringizdagi `nasiya.db` da. Serverga kirishni cheklang, zaxira nusxani shifrlang.
- Lead bo'lmagan mijozlar ma'lumotini 30 kunda o'chirish: `POST /admin/cleanup` (cron bilan har kuni).
- Rozilik matnini (`bot.py` → `CONSENT_TEXT`) yuristga tasdiqlating.

## Sozlash
- Matnlar: `bot.py`
- Qarz turlari va 10 mln chegara: `rules.py` (`DEBT_TYPES`, `MAMURIY_LIMIT`)
- Testlar: `pytest tests`
