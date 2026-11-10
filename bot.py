"""Mijoz bilan suhbat: savollar ketma-ketligi va tekshiruvlar.

handle(ig_id, text) mijozga yuboriladigan javoblar ro'yxatini qaytaradi.
"""
import re
import time

import db

TERMS = {"3", "6", "9", "12"}

CONSENT_TEXT = (
    "Muddatli to'lovni rasmiylashtirish uchun to'liq ismingiz, pasport seriyasi "
    "va raqamingiz, JShShIR (14 xonali shaxsiy raqam) va telefon raqamingiz kerak.\n\n"
    "Bu ma'lumotlar faqat Majburiy ijro byurosida (MIB) qarzdorlikni tekshirish va "
    "shartnoma tuzish uchun ishlatiladi, uchinchi shaxslarga berilmaydi. "
    "Shartnoma tuzilmasa, 30 kun ichida o'chiriladi.\n\n"
    "Rozi bo'lsangiz \"Roziman\", aks holda \"Yo'q\" deb yozing."
)

YES = {"roziman", "ha", "rozi", "xa", "ok", "mayli", "+"}
NO = {"yo'q", "yoq", "yo`q", "yo‘q", "rozi emasman", "yuq", "-"}


def norm_passport(t: str) -> str | None:
    s = re.sub(r"[\s\-]", "", t).upper()
    return s if re.fullmatch(r"[A-Z]{2}\d{7}", s) else None


def norm_pinfl(t: str) -> str | None:
    s = re.sub(r"\D", "", t)
    return s if len(s) == 14 and s[0] in "3456" else None


def norm_phone(t: str) -> str | None:
    s = re.sub(r"\D", "", t)
    if len(s) == 9:
        s = "998" + s
    return "+" + s if re.fullmatch(r"998\d{9}", s) else None


def handle(ig_id: str, text: str) -> list[str]:
    text = (text or "").strip()
    low = text.lower()
    c = db.get_or_create(ig_id)
    st = c["state"]

    if low in {"menejer", "operator", "odam"}:
        return ["Tushundim, menejerimiz tez orada shu yerda javob beradi."]

    if st == "new":
        db.update(ig_id, state="model")
        return [
            "Assalomu alaykum! Telefonlarni muddatli to'lovga (3, 6, 9 yoki 12 oy) "
            "rasmiylashtiramiz.",
            "Qaysi telefon kerak? Model va xotira hajmini yozing (masalan, iPhone 15 128GB).",
        ]

    if st == "model":
        if len(text) < 2:
            return ["Qaysi telefon kerakligini yozing (masalan, Samsung A55 256GB)."]
        db.update(ig_id, model=text[:120], state="term")
        return ["Necha oyga olmoqchisiz? 3, 6, 9 yoki 12 deb yozing."]

    if st == "term":
        n = re.sub(r"\D", "", text)
        if n not in TERMS:
            return ["Iltimos, faqat 3, 6, 9 yoki 12 deb yozing."]
        db.update(ig_id, term=n, state="consent")
        return [CONSENT_TEXT]

    if st == "consent":
        if low in YES:
            db.update(ig_id, consent_at=int(time.time()), state="name")
            return ["Rahmat! Pasportdagidek to'liq ism-familiyangizni yozing."]
        if low in NO:
            db.update(ig_id, state="done", status="rozilik_yoq")
            return [
                "Tushunarli. Roziliksiz muddatli to'lovni rasmiylashtira olmaymiz, "
                "lekin to'liq to'lov bilan olishingiz mumkin. Fikringiz o'zgarsa, "
                "\"yangi\" deb yozing."
            ]
        return ["Iltimos, \"Roziman\" yoki \"Yo'q\" deb javob bering."]

    if st == "name":
        if len(text.split()) < 2:
            return ["Ism va familiyani to'liq yozing (masalan, Aliyev Vali Karimovich)."]
        db.update(ig_id, full_name=text[:120], state="passport")
        return [
            "Pasport yoki ID-karta seriyasi va raqamini yozing — 2 ta harf va 7 ta raqam "
            "(masalan, AD1234567). Rasm shart emas, matn yetarli."
        ]

    if st == "passport":
        p = norm_passport(text)
        if not p:
            return ["Format noto'g'ri. 2 ta lotin harfi va 7 ta raqam yozing, masalan AD1234567."]
        db.update(ig_id, passport=p, state="pinfl")
        return [
            "JShShIR (14 xonali shaxsiy raqam)ni yozing. U pasportning shaxsiy "
            "ma'lumotlar sahifasida yoki ID-kartaning orqa tomonida yozilgan."
        ]

    if st == "pinfl":
        p = norm_pinfl(text)
        if not p:
            return ["JShShIR aniq 14 ta raqamdan iborat bo'lishi kerak. Qayta tekshirib yozing."]
        db.update(ig_id, pinfl=p, state="phone")
        return ["Bog'lanish uchun telefon raqamingizni yozing (masalan, +998 90 123 45 67)."]

    if st == "phone":
        p = norm_phone(text)
        if not p:
            return ["Telefon raqami noto'g'ri. +998 bilan 12 xonali raqam yozing."]
        db.update(ig_id, phone=p, state="waiting", status="mib_tekshiruvida")
        return [
            "Rahmat! Ma'lumotlaringiz qabul qilindi. Hozir MIB orqali tekshiramiz, "
            "natijani shu yerga yozamiz."
        ]

    if st == "waiting":
        return ["Arizangiz tekshirilmoqda, natijani tez orada shu yerga yozamiz."]

    if st == "done":
        if low == "yangi":
            db.update(ig_id, state="model", status="suhbatda", decision=None, mib_debts=None)
            return ["Yaxshi! Qaysi telefon kerak? Model va xotira hajmini yozing."]
        return ["Savollaringiz bo'lsa yozing, menejerimiz javob beradi. Yangi ariza uchun \"yangi\" deb yozing."]

    return ["Kechirasiz, tushunmadim. Menejerimiz tez orada javob beradi."]
