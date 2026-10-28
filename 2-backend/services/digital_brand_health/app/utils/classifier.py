from typing import Optional

CATEGORY_KEYWORDS = {
    "Credit Card": [
        "بطاقة ائتمانية", "بطاقة فيزا", "بطاقة ماستر كارد",
        "كريدت كارد", "credit card", "kredit card"
    ],
    "Debit Card": [
        "بطاقة خصم مباشر", "بطاقة صراف", "بطاقة مدى",
        "mada card", "ديبت كارد", "debit card"
    ],
    "Online Banking": [
        "الخدمات المصرفية عبر الإنترنت", "بنك أون لاين",
        "خدمة أون لاين", "اون لاين بنكنج", "online banking"
    ],
    "Mobile App": [
        "تطبيق الجوال", "تطبيق الهاتف المحمول", "تطبيق البنك",
        "أبلكيشن البنك", "ابلكيشن البنك", "app البنك",
        "bank app", "Application Bank"
    ],
    "Forex": [
        "صرف العملات الأجنبية", "الفوركس", "فوركس",
        "تداول العملات", "forex"
    ],
    "Loan Mortgage": [
        "قرض", "قرض loan", "qard",
        "تمويل", "tamweel", "قرض شخصي", "تمويل شخصي",
        "personal loan", "personal تمويل", "قرض personal",
        "قرض سيارة", "تمويل سيارة", "auto loan",
        "car loan", "car تمويل", "قرض منزل", "تمويل منزل",
        "قرض عقاري", "تمويل عقاري", "رهن عقاري",
        "home loan", "mortgage", "mortgage عقاري"
    ],
    "Account": [
        "حساب", "حساب بنكي", "فتح حساب", "hesab",
        "حساب بنك", "حساب جاري", "current account",
        "حساب توفير", "حساب ادخار", "saving account", "savings account",
        "محفظة إلكترونية", "محفظة الجوال", "محفظة رقمية",
        "mobile wallet", "e-wallet", "Apple Pay", "mada Pay", "STC Pay"
    ],
    "Insurance": [
        "تأمين", "تأمين بنكي", "تأمين على الحياة", "تأمين سيارات", "insurance"
    ],
    "Travel & International": [
        "بطاقة سفر", "بطاقة فوركس", "بطاقة العملات الأجنبية",
        "بطاقة متعددة العملات", "بطاقة افتراضية", "بطاقة دولية",
        "صرف العملات", "تحويل العملات", "travel card",
        "forex card", "multi currency card", "virtual card",
        "international card", "exchange card", "بطاقة ترافل",
        "بطاقة فوركس كارد", "multi currency بطاقة",
        "virtual بطاقة", "travel kart", "forex kart",
        "multi currency kart", "bitaqat safar", "bitaqat dawlia"
    ],
}


def classify_keyword(keyword: str) -> Optional[str]:
    if not keyword:
        return None

    keyword_lower = keyword.lower()

    for category, kw_list in CATEGORY_KEYWORDS.items():
        for kw in kw_list:
            if kw.lower() in keyword_lower:
                return category

    return "Other"
