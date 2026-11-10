"""MIB natijasi bo'yicha qaror qoidalari.

Qoida (do'kon egasi talabi):
  * Undiruv bo'yicha har qanday qarzdorlik bo'lsa -> RAD, sababi aytiladi.
  * Faqat ma'muriy jarimalar bo'lsa va jami 10 000 000 so'mgacha -> LEAD.
  * Ma'muriy jarimalar jami 10 000 000 so'mdan ortiq -> RAD.
  * Qarz yo'q -> LEAD.
"""
from dataclasses import dataclass

MAMURIY_LIMIT = 10_000_000  # so'm, shu summagacha (shu jumladan) ruxsat

# kod -> (nomi, toifa)
DEBT_TYPES = {
    "kredit": ("bank krediti yoki mikroqarz", "undiruv"),
    "nasiya": ("boshqa do'kondagi nasiya", "undiruv"),
    "aliment": ("aliment", "undiruv"),
    "kommunal": ("kommunal to'lovlar (gaz, svet, suv)", "undiruv"),
    "soliq": ("soliq qarzi", "undiruv"),
    "sud": ("sud qarori bo'yicha undiruv", "undiruv"),
    "reyestr": ("MIB Majburiyatlar reyestridagi qarz", "undiruv"),
    "boshqa_undiruv": ("boshqa undiruv", "undiruv"),
    "yol_jarima": ("yo'l harakati jarimasi", "mamuriy"),
    "mamuriy": ("ma'muriy jarima", "mamuriy"),
}


@dataclass
class Debt:
    code: str
    amount: int  # so'm


@dataclass
class Decision:
    approved: bool
    reason: str        # menejer uchun qisqa izoh
    client_text: str   # mijozga yuboriladigan matn


def fmt_sum(n: int) -> str:
    return f"{n:,}".replace(",", " ") + " so'm"


def decide(debts: list[Debt]) -> Decision:
    for d in debts:
        if d.code not in DEBT_TYPES:
            raise ValueError(f"Noma'lum qarz turi: {d.code}")
        if d.amount < 0:
            raise ValueError("Summa manfiy bo'lishi mumkin emas")

    undiruv = [d for d in debts if DEBT_TYPES[d.code][1] == "undiruv"]
    mamuriy = [d for d in debts if DEBT_TYPES[d.code][1] == "mamuriy"]

    if undiruv:
        names = ", ".join(dict.fromkeys(DEBT_TYPES[d.code][0] for d in undiruv))
        total = sum(d.amount for d in undiruv)
        return Decision(
            approved=False,
            reason=f"Undiruv qarzi: {names}, jami {fmt_sum(total)}",
            client_text=(
                f"Afsuski, MIBda {names} bo'yicha undiruv qarzdorligingiz "
                f"(jami {fmt_sum(total)}) borligi sababli hozircha muddatli "
                "to'lovni rasmiylashtira olmaymiz. Qarzni yopganingizdan keyin "
                "qayta murojaat qilsangiz, bajonidil ko'rib chiqamiz. "
                "To'liq to'lov bilan olishingiz ham mumkin."
            ),
        )

    mam_total = sum(d.amount for d in mamuriy)
    if mam_total > MAMURIY_LIMIT:
        return Decision(
            approved=False,
            reason=f"Ma'muriy jarimalar {fmt_sum(mam_total)} > 10 mln",
            client_text=(
                "Afsuski, MIBdagi ma'muriy jarimalaringiz summasi "
                f"({fmt_sum(mam_total)}) 10 mln so'mdan oshgani sababli hozircha "
                "muddatli to'lovni rasmiylashtira olmaymiz. Jarimalarni "
                "kamaytirganingizdan keyin qayta yozing. To'liq to'lov bilan "
                "olishingiz ham mumkin."
            ),
        )

    reason = "Qarz yo'q" if not mamuriy else f"Faqat ma'muriy jarima: {fmt_sum(mam_total)}"
    return Decision(
        approved=True,
        reason=reason,
        client_text=(
            "Tekshiruv yakunlandi, arizangiz qabul qilindi! Menejerimiz "
            "shartnoma va yetkazib berish bo'yicha tez orada siz bilan bog'lanadi."
        ),
    )
