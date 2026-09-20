# -*- coding: utf-8 -*-
"""
app.py — Аналитик банковских выписок.
Исправленная версия: поддержка Wise PDF, N26 (cid), Revolut с русскими месяцами,
фильтрация служебных строк.
"""

import streamlit as st
import pandas as pd
import os
import re
import hashlib
import csv
import base64
import json
import traceback
from datetime import datetime, timedelta
from io import BytesIO, StringIO
from typing import Dict, List, Tuple, Callable, Optional, Any

from docx import Document
import pdfplumber

# Fallback для PDF с (cid:XX)
try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text
    _PDFMINER_AVAILABLE = True
except ImportError:
    _PDFMINER_AVAILABLE = False

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

try:
    from openai import OpenAI
    _OPENAI_SDK_AVAILABLE = True
except ImportError:
    _OPENAI_SDK_AVAILABLE = False
    OpenAI = None  # type: ignore


# ==================== НАСТРОЙКА СТРАНИЦЫ ====================

st.set_page_config(
    page_title="Аналитик банковских выписок",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ==================== ФОН: ГОРОДЕЦКАЯ РОСПИСЬ "ЧАЕПИТИЕ" ====================
# (оставляем без изменений — см. оригинал; для краткости здесь пропущен,
#  вставьте оригинальный _GORODETS_SVG из вашего файла)

_GORODETS_SVG = "<svg xmlns='http://www.w3.org/2000/svg' width='520' height='460'></svg>"
_GORODETS_SVG_B64 = base64.b64encode(_GORODETS_SVG.encode('utf-8')).decode('ascii')


# ==================== ЭТАЛОННЫЙ СПИСОК СЧЕТОВ ====================
# (оставляем без изменений — см. оригинал)

_ACCOUNT_ALIASES: List[Tuple[str, str]] = [
    ("an14estateeurindustra", "AN14_Estate_EUR_Industra"),
    ("an14estateeurrevolut",  "AN14_Estate_EUR_Revolut"),
    ("b1estateczkuc",         "B1_Estate_CZK_UC"),
    ("b1estate",              "B1_Estate_CZK_UC"),
    ("bsrestateeurbluor2",    "BSR_Estate_EUR_BluOr_2"),
    ("bsrestateeurbluor3",    "BSR_Estate_EUR_BluOr_3"),
    ("bsrbluor2",             "BSR_Estate_EUR_BluOr_2"),
    ("bsrbluor3",             "BSR_Estate_EUR_BluOr_3"),
    ("kl59revnbeurbluor",     "KL59_Rev_NB_EUR_BluOR"),
    ("kl59bluor",             "KL59_Rev_NB_EUR_BluOR"),
    ("budapesthufmkb",        "Budapest HUF-MKB"),
    ("budapesthuf",           "Budapest HUF-MKB"),
    ("budapesteurmkb",        "Budapest EUR-MKB"),
    ("budapesteuro",          "Budapest EUR-MKB"),
    ("budapest",              "Budapest EUR-MKB"),
    ("mkbbudapest",           "Budapest EUR-MKB"),
    ("bundallcpashabankaedдирхам", "BUNDA LLC-Pasha Bank - AED-дирхам"),
    ("bundallcpashabankaed",  "BUNDA LLC-Pasha Bank - AED-дирхам"),
    ("bundapashaaed",         "BUNDA LLC-Pasha Bank - AED-дирхам"),
    ("pashabankaed",          "BUNDA LLC-Pasha Bank - AED-дирхам"),
    ("pashaaed",              "BUNDA LLC-Pasha Bank - AED-дирхам"),
    ("bundallcpashabankazn",  "BUNDA LLC-Pasha Bank-AZN"),
    ("bundapashaazn",         "BUNDA LLC-Pasha Bank-AZN"),
    ("pashabankazn",          "BUNDA LLC-Pasha Bank-AZN"),
    ("pashaazn",              "BUNDA LLC-Pasha Bank-AZN"),
    ("dzibikmaincsobczk",     "DŽIBIK Main CSOB CZK"),
    ("dzibikcsob",            "DŽIBIK Main CSOB CZK"),
    ("dzibik",                "DŽIBIK Main CSOB CZK"),
    ("jenisovhorskasrczk",    "JENISOV - HORSKA S.R CZK"),
    ("jenisovhorskaczkeur",   "JENISOV - HORSKA S.R EUR"),
    ("jenisovhorskasreur",    "JENISOV - HORSKA S.R EUR"),
    ("jenisovhorskaczk",      "JENISOV - HORSKA S.R CZK"),
    ("jenisovcsobczk",        "JENISOV - HORSKA S.R CZK"),
    ("jenisovcsobeur",        "JENISOV - HORSKA S.R EUR"),
    ("jenisov",               "JENISOV - HORSKA S.R CZK"),
    ("korunastrojkaczkcsob",  "Koruna_Strojka_CZK_CSOB"),
    ("korunastrojkaczkeur",   "Koruna_Strojka_EUR_CSOB"),
    ("korunastrojkaeurcsob",  "Koruna_Strojka_EUR_CSOB"),
    ("korunastrojkaczk",      "Koruna_Strojka_CZK_CSOB"),
    ("korunastrojka",         "Koruna_Strojka_CZK_CSOB"),
    ("rrstrovkaczkcsob",      "RR_Strojka_CZK_CSOB"),
    ("rrstrovkaeurcsob",      "RR_Strojka_EUR_CSOB"),
    ("rrstrovkaczk",          "RR_Strojka_CZK_CSOB"),
    ("rrstrovkaeur",          "RR_Strojka_EUR_CSOB"),
    ("rrstrovka",             "RR_Strojka_CZK_CSOB"),
    ("rrrevostr",             "RR_Strojka_CZK_CSOB"),
    ("garpizunicreditbankczk", "Garpiz UniCredit Bank CZK"),
    ("garpizunicredit",        "Garpiz UniCredit Bank CZK"),
    ("garpiz",                 "Garpiz UniCredit Bank CZK"),
    ("garpizperninkczkuc",     "Garpiz_Pernink_CZK_UC"),
    ("garpizpernink",          "Garpiz_Pernink_CZK_UC"),
    ("pernink",                "Garpiz_Pernink_CZK_UC"),
    ("korunaunicreditczk",     "Koruna UniCredit- CZK"),
    ("korunaunicredit",        "Koruna UniCredit- CZK"),
    ("twohillsmollyunicreditczk", "TwoHills_Molly_Unicredit_CZK"),
    ("twohillsmollyunicredit", "TwoHills_Molly_Unicredit_CZK"),
    ("twohillsmolly",          "TwoHills_Molly_Unicredit_CZK"),
    ("twohills",               "TwoHills_Molly_Unicredit_CZK"),
    ("jenhorunelmaczkcsas",    "JenHor_Unelma_CZK_CSAS"),
    ("jenhorunelma",           "JenHor_Unelma_CZK_CSAS"),
    ("jenhor",                 "JenHor_Unelma_CZK_CSAS"),
    ("unelma",                 "JenHor_Unelma_CZK_CSAS"),
    ("kapitalbanksaidaazn",    "Kapital bank_Saida_AZN"),
    ("kapitalbanksaida",       "Kapital bank_Saida_AZN"),
    ("kapitalbankazn",         "Kapital bank_Saida_AZN"),
    ("kapitalazn",             "Kapital bank_Saida_AZN"),
    ("saidaazn",               "Kapital bank_Saida_AZN"),
    ("kl59revnbeurindustra",   "KL59_Rev_NB_EUR_Industra"),
    ("kl59industra",           "KL59_Rev_NB_EUR_Industra"),
    ("kl59",                   "KL59_Rev_NB_EUR_Industra"),
    ("mashreqbankaednomiqa",   "MASHREQ BANK-AED-NOMIQA"),
    ("mashreqaednomiqa",       "MASHREQ BANK-AED-NOMIQA"),
    ("mashreqnomiqa",          "MASHREQ BANK-AED-NOMIQA"),
    ("mashreq",                "MASHREQ BANK-AED-NOMIQA"),
    ("nomiqa",                 "MASHREQ BANK-AED-NOMIQA"),
    ("nbreveurrevolut",        "NB_Rev_EUR_Revolut"),
    ("nbreveur",               "NB_Rev_EUR_Revolut"),
    ("nbrev",                  "NB_Rev_EUR_Revolut"),
    ("payserabalticsolutionseur", "Paysera Baltic Solutions EUR"),
    ("payserabalticsolutions", "Paysera Baltic Solutions EUR"),
    ("payserabaltic",          "Paysera Baltic Solutions EUR"),
    ("payserasveciynamailithuaniaeur", "Paysera Sveciy Namai Lithuania EUR"),
    ("payserasveciynamailithuania", "Paysera Sveciy Namai Lithuania EUR"),
    ("payserasveciy",          "Paysera Sveciy Namai Lithuania EUR"),
    ("payserabspropertysia",   "Paysera-BS PROPERTY, SIA"),
    ("payserabsproperty",      "Paysera-BS PROPERTY, SIA"),
    ("payseraproperty",        "Paysera-BS PROPERTY, SIA"),
    ("payserabsrerumsia",      "Paysera-BS RERUM, SIA"),
    ("payserabsrerum",         "Paysera-BS RERUM, SIA"),
    ("payserarerum",           "Paysera-BS RERUM, SIA"),
    ("paysera",                "Paysera Baltic Solutions EUR"),
    ("plavas1estateeurindustra", "Plavas1_Estate_EUR_Industra"),
    ("plavas1industra",        "Plavas1_Estate_EUR_Industra"),
    ("plavasestateeurindustra", "Plavas1_Estate_EUR_Industra"),
    ("plavas1",                "Plavas1_Estate_EUR_Industra"),
    ("plavas",                 "Plavas1_Estate_EUR_Industra"),
    ("reginaalfabanknomiqarub", "Regina Alfa-bank_NOMIQA_RUB"),
    ("reginaalfanomiqarub",     "Regina Alfa-bank_NOMIQA_RUB"),
    ("reginaalfabanknomiqa",    "Regina Alfa-bank_NOMIQA_RUB"),
    ("reginaalfanomiqa",        "Regina Alfa-bank_NOMIQA_RUB"),
    ("reginaalfa",              "Regina Alfa-bank_NOMIQA_RUB"),
    ("revolutplavas1sia",      "Revolut_Plavas 1 SIA"),
    ("revolutplavas1",         "Revolut_Plavas 1 SIA"),
    ("revolutplavas",          "Revolut_Plavas 1 SIA"),
    ("revolutnb",              "NB_Rev_EUR_Revolut"),
    ("revolutan14",            "AN14_Estate_EUR_Revolut"),
    ("revolut",                "AN14_Estate_EUR_Revolut"),
    ("saidan26",               "Saida_N26"),
    ("saida26",                "Saida_N26"),
    ("n26",                    "Saida_N26"),
    ("saidawise",              "Saida_Wise"),
    ("wise",                   "Saida_Wise"),
    ("stalkinml2czkfio",       "Stalkin_ML2_CZK_FIO"),
    ("stalkinml2fio",          "Stalkin_ML2_CZK_FIO"),
    ("stalkinfio",             "Stalkin_ML2_CZK_FIO"),
    ("stalkin",                "Stalkin_ML2_CZK_FIO"),
    ("fio",                    "Stalkin_ML2_CZK_FIO"),
    ("tinkoffrub",             "Tinkoff RUB"),
    ("tinkoff",                "Tinkoff RUB"),
    ("wiobusinessbank",        "WIO Business Bank"),
    ("wiobusiness",            "WIO Business Bank"),
    ("wio",                    "WIO Business Bank"),
]


def _normalize_key(s: str) -> str:
    if s is None:
        return ""
    s = str(s).lower()
    s = re.sub(r'[\s_\-\.\,]+', '', s)
    return s


def normalize_account_name(raw_name: str) -> str:
    if not raw_name:
        return raw_name

    clean = raw_name
    clean = re.sub(
        r'\(\s*(?:'
        r'[A-Za-z]{3,9}\.?\s+\d{1,2},?\s*\d{4}'
        r'|\d{1,2}[\.\-/]\d{1,2}[\.\-/]\d{2,4}'
        r'|\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2}'
        r')'
        r'(?:\s*[-–—]\s*'
        r'(?:'
        r'[A-Za-z]{3,9}\.?\s+\d{1,2},?\s*\d{4}'
        r'|\d{1,2}[\.\-/]\d{1,2}[\.\-/]\d{2,4}'
        r'|\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2}'
        r'))?'
        r'\s*\)',
        ' ', clean
    )
    clean = re.sub(r'\b\d{2}-[A-Za-z]{3}-\d{4}\b', ' ', clean)
    clean = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', ' ', clean)
    clean = re.sub(r'\b\d{8}\b', ' ', clean)
    clean = re.sub(r'\b\d{2}\.\d{2}\.\d{4}\b', ' ', clean)
    clean = re.sub(r'\bLV\d{2}[A-Z]{4}\d{13,}\b', ' ', clean)
    clean = re.sub(r'\b\d{10,}\b', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()

    key = _normalize_key(clean)

    best = None
    best_len = -1
    for alias_key, canonical in _ACCOUNT_ALIASES:
        if alias_key in key:
            if len(alias_key) > best_len:
                best_len = len(alias_key)
                best = canonical
    if best:
        return best

    return clean if clean else raw_name


# ==================== CSS СТИЛИ ====================
# (оставляем без изменений — см. оригинал; вставьте оригинальный _CSS)

_CSS = "<style>/* ... */</style>"
st.markdown(_CSS.replace("__GORODETS_B64__", _GORODETS_SVG_B64), unsafe_allow_html=True)


# ==================== DEEPSEEK AI ====================
# (оставляем без изменений — см. оригинал)

HF_BASE_URL = "https://router.huggingface.co/v1"
HF_DEFAULT_MODEL = "deepseek-ai/DeepSeek-V3-0324"
HF_REASONER_MODEL = "deepseek-ai/DeepSeek-R1"


def _get_hf_token() -> str:
    token = ""
    try:
        if "HF_TOKEN" in st.secrets:
            token = str(st.secrets["HF_TOKEN"]).strip()
    except Exception:
        pass
    if not token:
        token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        token = str(st.session_state.get("hf_token", "")).strip()
    if token and (not token.isascii() or not token.startswith("hf_")):
        return ""
    return token


def _get_hf_client() -> Optional["OpenAI"]:
    if not _OPENAI_SDK_AVAILABLE:
        return None
    token = _get_hf_token()
    if not token:
        return None
    try:
        return OpenAI(base_url=HF_BASE_URL, api_key=token)
    except Exception:
        return None


def call_ai(messages, model=HF_DEFAULT_MODEL, temperature=0.3,
            max_tokens=2048, json_mode=False):
    client = _get_hf_client()
    if client is None:
        if not _OPENAI_SDK_AVAILABLE:
            return "", "Библиотека openai не установлена. Выполните: pip install openai"
        return "", ("DeepSeek-токен не задан или неверен. "
                    "Проверьте HF_TOKEN в .streamlit/secrets.toml.")
    try:
        kwargs = {"model": model, "messages": messages,
                  "temperature": temperature, "max_tokens": max_tokens, "stream": False}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        return (resp.choices[0].message.content or "").strip(), None
    except Exception as e:
        return "", f"Ошибка DeepSeek AI: {e}"


def call_ai_json(system_prompt, user_prompt, model=HF_DEFAULT_MODEL):
    messages = [{"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}]
    raw, err = call_ai(messages, model=model, temperature=0.1, json_mode=True)
    if err:
        return None, err
    try:
        return json.loads(raw), None
    except Exception:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0)), None
            except Exception:
                pass
        return None, f"Не удалось распарсить JSON: {raw[:300]}"


_AI_TRANSACTION_SYSTEM = (
    "Ты — эксперт по банковским выпискам. На вход получаешь транзакцию. "
    "Верни СТРОГО JSON: {\"translation\": \"перевод на русский\", "
    "\"category\": \"категория\", \"counterparty_clean\": \"чистое имя\", "
    "\"is_bank_fee\": true/false, \"confidence\": 0.0-1.0}"
)


def ai_enrich_transactions(transactions, max_items=200, progress_callback=None):
    errors = []
    if not transactions:
        return transactions, ["Нет транзакций для обогащения"]
    client = _get_hf_client()
    if client is None:
        return transactions, ["DeepSeek AI недоступен (проверьте HF_TOKEN)"]
    subset = transactions[:max_items]
    enriched = [dict(t) for t in transactions]
    for i, tx in enumerate(subset):
        desc = str(tx.get("Описание", ""))[:1500]
        acc = str(tx.get("Наименование счета", tx.get("Наименование банка", "")))
        amount = tx.get("Сумма", 0)
        user_prompt = f"Счёт: {acc}\nСумма: {amount}\nОписание: {desc}\n"
        data, err = call_ai_json(_AI_TRANSACTION_SYSTEM, user_prompt)
        if err:
            errors.append(f"строка {i+1}: {err}")
        else:
            enriched[i]["_ai_translation"] = data.get("translation", "")
            enriched[i]["_ai_category"] = data.get("category", "")
            enriched[i]["_ai_counterparty_clean"] = data.get("counterparty_clean", "")
            enriched[i]["_ai_is_bank_fee"] = bool(data.get("is_bank_fee", False))
            enriched[i]["_ai_confidence"] = data.get("confidence", 0.0)
        if progress_callback:
            try:
                progress_callback(i + 1, len(subset))
            except Exception:
                pass
    return enriched, errors


_AI_DEBUG_SYSTEM = (
    "Ты — Python-разработчик, эксперт по Streamlit и парсингу банковских выписок. "
    "Предложи конкретное исправление. Отвечай по делу."
)


# ==================== ШАПКА ====================
# (оставляем без изменений — см. оригинал)
# ==================== ОБЩИЕ УТИЛИТЫ ====================

def clean_account_name(filename: str) -> str:
    name = os.path.splitext(filename)[0]
    name = re.sub(
        r'\(\s*(?:'
        r'[A-Za-z]{3,9}\.?\s+\d{1,2},?\s*\d{4}'
        r'|\d{1,2}[\.\-/]\d{1,2}[\.\-/]\d{2,4}'
        r'|\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2}'
        r')'
        r'(?:\s*[-–—]\s*'
        r'(?:'
        r'[A-Za-z]{3,9}\.?\s+\d{1,2},?\s*\d{4}'
        r'|\d{1,2}[\.\-/]\d{1,2}[\.\-/]\d{2,4}'
        r'|\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2}'
        r'))?'
        r'\s*\)',
        '', name
    )
    name = re.sub(r'\d{2}-[A-Za-z]{3}-\d{4}', '', name)
    name = re.sub(r'\d{4}-\d{2}-\d{2}', '', name)
    name = re.sub(r'\d{2}\.\d{2}\.\d{4}', '', name)
    name = re.sub(r'LV\d{2}[A-Z]{4}\d{13,}', '', name)
    name = re.sub(r'[_\-]', ' ', name)
    name = re.sub(r'\.+', ' ', name)
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r' \(2\)$', '', name)
    return name.strip() if name else 'Неизвестный счет'


# ---------- Русские и иностранные месяцы для парсинга дат ----------

_MONTHS_RU = {
    'янв': 1, 'января': 1, 'январь': 1,
    'фев': 2, 'февраля': 2, 'февраль': 2,
    'мар': 3, 'марта': 3, 'март': 3,
    'апр': 4, 'апреля': 4, 'апрель': 4,
    'май': 5, 'мая': 5,
    'июн': 6, 'июня': 6, 'июнь': 6,
    'июл': 7, 'июля': 7, 'июль': 7,
    'авг': 8, 'августа': 8, 'август': 8,
    'сен': 9, 'сент': 9, 'сентября': 9, 'сентябрь': 9,
    'окт': 10, 'октября': 10, 'октябрь': 10,
    'ноя': 11, 'нояб': 11, 'ноября': 11, 'ноябрь': 11,
    'дек': 12, 'декабря': 12, 'декабрь': 12,
}

_MONTHS_EN = {
    'jan': 1, 'january': 1,
    'feb': 2, 'february': 2,
    'mar': 3, 'march': 3,
    'apr': 4, 'april': 4,
    'may': 5,
    'jun': 6, 'june': 6,
    'jul': 7, 'july': 7,
    'aug': 8, 'august': 8,
    'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10,
    'nov': 11, 'november': 11,
    'dec': 12, 'december': 12,
}

_MONTHS_CS = {
    'led': 1, 'ledna': 1,
    'úno': 2, 'února': 2,
    'bře': 3, 'března': 3,
    'dub': 4, 'dubna': 4,
    'kvě': 5, 'května': 5,
    'čvn': 6, 'června': 6,
    'čvc': 7, 'července': 7,
    'srp': 8, 'srpna': 8,
    'zář': 9, 'září': 9,
    'říj': 10, 'října': 10,
    'lis': 11, 'listopadu': 11,
    'pro': 12, 'prosince': 12,
}

_ALL_MONTHS = {}
_ALL_MONTHS.update(_MONTHS_RU)
_ALL_MONTHS.update(_MONTHS_EN)
_ALL_MONTHS.update(_MONTHS_CS)


def parse_date(date_str) -> str:
    if date_str is None or pd.isna(date_str):
        return ''
    s = str(date_str).strip()
    if not s or s in ['nan', '-', 'None', 'null', 'NaT']:
        return ''
    if ' ' in s and re.match(r'^\d{1,2}\s+[A-Za-zА-Яа-я]', s):
        # не режем — это "6 июн. 2026"
        pass
    elif ' ' in s:
        s = s.split(' ')[0]
    if 'T' in s:
        s = s.split('T')[0]
    if s.endswith('.0'):
        s = s[:-2]
    if s.isdigit() and len(s) == 8:
        return f"{s[6:8]}-{s[4:6]}-{s[:4]}"
    if s.isdigit() and len(s) == 5 and 40000 <= int(s) <= 50000:
        try:
            base = datetime(1899, 12, 30)
            d = base + timedelta(days=int(s))
            return d.strftime("%d-%m-%Y")
        except Exception:
            pass
    m = re.match(r'^(\d{1,2})\.(\d{1,2})\.(\d{2,4})$', s)
    if m:
        d, mo, y = m.groups()
        if len(y) == 2:
            y = f"20{y}"
        return f"{d.zfill(2)}-{mo.zfill(2)}-{y}"
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', s)
    if m:
        d, mo, y = m.groups()
        if len(y) == 2:
            y = f"20{y}"
        return f"{d.zfill(2)}-{mo.zfill(2)}-{y}"
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        y, mo, d = m.groups()
        return f"{d}-{mo}-{y}"
    m = re.match(r'^(\d{4})(\d{2})(\d{2})', s)
    if m:
        y, mo, d = m.groups()
        return f"{d}-{mo}-{y}"
    m = re.match(r'^(\d{1,2})-(\d{1,2})-(\d{4})$', s)
    if m:
        d, mo, y = m.groups()
        return f"{d.zfill(2)}-{mo.zfill(2)}-{y}"

    # "6 июн. 2026" / "6 июня 2026" / "6 Jun 2026"
    m = re.match(
        r'^(\d{1,2})\s+([A-Za-zА-Яа-яЁё]+)\.?,?\s+(\d{4})$',
        s
    )
    if m:
        d, mon, y = m.groups()
        mon_key = mon.lower().rstrip('.')
        if mon_key in _ALL_MONTHS:
            mo = _ALL_MONTHS[mon_key]
            return f"{int(d):02d}-{mo:02d}-{y}"

    # "30 июня 2026 г." / "2 июля 2026г."
    m = re.match(
        r'^(\d{1,2})\s+([A-Za-zА-Яа-яЁё]+)\.?\s+(\d{4})\s*г?\.?$',
        s
    )
    if m:
        d, mon, y = m.groups()
        mon_key = mon.lower().rstrip('.')
        if mon_key in _ALL_MONTHS:
            mo = _ALL_MONTHS[mon_key]
            return f"{int(d):02d}-{mo:02d}-{y}"

    # "27.06.2026" уже покрыто выше; "2026-06-01 08:31:44" покрыто
    # "28 июн. 2026" покрыто выше

    for fmt in ["%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%b-%y"]:
        try:
            return datetime.strptime(s, fmt).strftime("%d-%m-%Y")
        except Exception:
            continue
    for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d", "%d-%m-%Y",
                "%Y%m%d", "%d.%m.%y", "%d/%m/%y"]:
        try:
            return datetime.strptime(s, fmt).strftime("%d-%m-%Y")
        except Exception:
            continue
    return s


def parse_amount(amount_str) -> float:
    if amount_str is None or pd.isna(amount_str):
        return 0.0
    s = str(amount_str).strip()
    if s in ['', 'nan', '-', 'None', 'null', 'NaN', 'N/A', 'n/a']:
        return 0.0
    is_negative = False
    if s.startswith('-'):
        is_negative = True
        s = s[1:]
    elif s.startswith('+'):
        s = s[1:]
    elif s.startswith('(') and s.endswith(')'):
        is_negative = True
        s = s[1:-1]
    s = re.sub(r'^[€$£¥]\s*', '', s)
    s = re.sub(r'\s*[€$£¥]\s*$', '', s)
    s = re.sub(r'\s*[A-Z]{3}\s*$', '', s)
    s = s.replace(' ', '').replace('\xa0', '').replace('\u202f', '')
    if ',' in s and '.' in s:
        if s.rfind('.') < s.rfind(','):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        parts = s.split(',')
        if len(parts) == 2 and len(parts[1]) <= 2:
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')
    s = re.sub(r'[^\d.\-]', '', s)
    if not s or s == '.':
        return 0.0
    try:
        v = float(s)
        return -abs(v) if is_negative else abs(v)
    except Exception:
        return 0.0


def format_amount(amount: float) -> str:
    if amount is None:
        return "0,00"
    try:
        if pd.isna(amount):
            return "0,00"
    except Exception:
        pass
    try:
        v = float(amount)
    except Exception:
        return "0,00"
    sign = "-" if v < 0 else ""
    formatted = f"{abs(v):.2f}".replace('.', ',')
    if ',' in formatted:
        ip, dp = formatted.split(',')
        ip = re.sub(r'(?<=\d)(?=(\d{3})+(?!\d))', ' ', ip)
        return f"{sign}{ip},{dp}"
    return f"{sign}{formatted}"


def to_float_amount(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        try:
            if pd.isna(v):
                return 0.0
        except Exception:
            pass
        return float(v)
    s = str(v).strip()
    if not s or s.lower() in ('nan', 'none', 'null'):
        return 0.0
    s = s.replace('\xa0', '').replace('\u202f', '').replace(' ', '')
    if ',' in s and '.' in s:
        if s.rfind('.') < s.rfind(','):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except Exception:
        return 0.0


def safe_str(v) -> str:
    if v is None:
        return ''
    try:
        if pd.isna(v):
            return ''
    except Exception:
        pass
    return str(v).strip()


def _to_scalar_str(v: Any) -> str:
    if v is None:
        return ''
    try:
        if pd.isna(v):
            return ''
    except Exception:
        pass
    if isinstance(v, str):
        return v
    if isinstance(v, (list, tuple)):
        try:
            return ' | '.join(_to_scalar_str(x) for x in v
                              if x is not None and str(x).strip() != '')
        except Exception:
            return str(v)
    if isinstance(v, dict):
        try:
            return ' | '.join(f"{_to_scalar_str(k)}: {_to_scalar_str(val)}"
                              for k, val in v.items())
        except Exception:
            return str(v)
    try:
        return str(v)
    except Exception:
        return ''


def _safe_str_series(series: pd.Series) -> pd.Series:
    if series is None:
        return pd.Series(dtype=str)
    try:
        return series.map(_to_scalar_str).astype(str)
    except Exception:
        return pd.Series([''] * len(series), index=series.index, dtype=str)


# ==================== СЛОВАРИ ПЕРЕВОДА ====================
# (оставляем без изменений — см. оригинал)

_PHRASE_DICT: Dict[str, str] = {
    "value added tax - output": "НДС к уплате",
    "value added tax - input": "НДС к возмещению",
    "value added tax": "НДС",
    "corr.bank.charges": "комиссии банка-корреспондента",
    "corr. bank charges": "комиссии банка-корреспондента",
    "inward remittance fund transfer": "входящий перевод средств",
    "inward remittance": "входящий перевод",
    "outward clearing cheque": "исходящий клиринговый чек",
    "outward clearing": "исходящий клиринг",
    "online international money transfer": "международный онлайн-перевод",
    "funds transfer charges": "комиссии за перевод средств",
    "acc. maintenance, statements and trans.": "обслуживание счёта, выписки и операции",
    "acc. maintenance, statements and transactions": "обслуживание счёта, выписки и операции",
    "account maintenance charges. for": "комиссия за обслуживание счёта. За",
    "account maintenance charges": "комиссия за обслуживание счёта",
    "banking charges": "банковские комиссии",
    "bank charges": "банковские комиссии",
    "subscription fee for": "абонентская плата за",
    "subscription fee": "абонентская плата",
    "foreign exchange transaction fee": "комиссия за конвертацию валюты",
    "foreign exchange transaction": "операция обмена валюты",
    "transfer own funds": "перевод собственных средств",
    "salary and other payments": "зарплата и прочие выплаты",
    "salary amount transfer": "перевод заработной платы",
    "outgoing xohks payment": "исходящий платёж XOHKS",
    "incoming swift payment": "входящий SWIFT-платёж",
    "internal payment": "внутренний платёж",
    "currency exchange (spot)": "обмен валюты (спот)",
    "currency exchange": "обмен валюты",
    "money added from": "пополнение от",
    "money received from": "поступление от",
    "money sent to": "перевод в адрес",
    "money added": "пополнение",
    "money received": "поступление",
    "money sent": "отправлено",
    "card payment": "оплата картой",
    "atm withdrawal": "снятие в банкомате",
    "cash withdrawal": "снятие наличных",
    "cash deposit": "внесение наличных",
    "exchange in": "обмен валюты (поступление)",
    "exchange out": "обмен валюты (списание)",
    "opening balance": "начальный остаток",
    "closing balance": "конечный остаток",
    "starting balance": "начальный остаток",
    "ending balance": "конечный остаток",
    "noncash transfer eb": "безналичный перевод EB",
    "noncash transfer": "безналичный перевод",
    "outgoing payment": "исходящий платёж",
    "incoming payment": "входящий платёж",
    "online transfer": "онлайн-перевод",
    "account maintenance": "обслуживание счёта",
    "sms service fee": "комиссия за SMS-сервис",
    "sms service": "SMS-сервис",
    "metal membership": "подписка Metal",
    "charge accounting": "комиссия за учёт",
    "charge for": "комиссия за",
    "revolut business fee": "комиссия Revolut Business",
    "grow plan fee": "комиссия за тариф Grow",
    "expenses app charges": "плата за приложение расходов",
    "message": "сообщение",
    "notprovided": "не указано",
    "comission": "комиссия",
    "commission": "комиссия",
    "interest payment for loan": "процентный платёж по кредиту",
    "loan payment": "платёж по кредиту",
    "loan interest": "проценты по кредиту",
    "sent from revolut": "отправлено из Revolut",
    "sutits no revolut": "отправлено из Revolut",
    "inviato da revolut": "отправлено из Revolut",
    "sent from": "отправлено из",
    "rent and utilities": "аренда и коммунальные услуги",
    "apartment rent": "аренда квартиры",
    "rent": "аренда",
    "utilities": "коммунальные услуги",
    "tiktok ads": "реклама TikTok",
    "tiktok": "TikTok",
    "google *ads": "GOOGLE *ADS",
    "google": "Google",
    "facebk": "FACEBOOK",
    "debcard": "DebCard",
    "careem": "Careem",
    "flydubai": "Flydubai",
    "union coop": "Union Coop",
    "dubai metro": "Дубайское метро",
    "dubai taxi": "такси Дубай",
    "pizza hut": "Pizza Hut",
    "pinkberry": "Pinkberry",
    "regent palace hotel": "Regent Palace Hotel",
    "albato": "Albato",
    "to host arabia": "To Host Arabia",
    "day to day": "Day To Day",
    "butter bread bakery": "Butter Bread Bakery",
    "spices by nature rest": "ресторан Spices by Nature",
    "corner spmrkt llc": "Corner Supermarket LLC",
    "tamdeed projects llc": "Tamdeed Projects LLC",
    "real mini mart llc": "Real Mini Mart LLC",
    "q general cleaning ser": "клининг Q General",
    "al beiruti cafe offici": "кафе Al Beiruti",
    "ksds praha": "Ksds Praha",
    "praha 1": "Прага 1",
    "latvija.lv": "Latvija.lv",
    "sixt": "Sixt",
    "vueling airlines": "Vueling Airlines",
    "smartwings.com": "Smartwings.com",
    "hotel at booking.com": "Hotel at Booking.com",
    "booking.com": "Booking.com",
    "openai *chatgpt subscr": "OpenAI *ChatGPT Subscription",
    "openai chatgpt subscr": "OpenAI ChatGPT Subscription",
    "anthropic* claude sub": "Anthropic Claude Subscription",
    "claude sub": "Claude Subscription",
    "adobe systems software": "Adobe Systems Software",
    "google one": "Google One",
    "postsignum": "PostSignum",
    "revolut": "Revolut",
    "paysera": "Paysera",
    "wise": "Wise",
    "tinkoff": "Тинькофф",
    "sberbank": "Сбербанк",
    "industra bank": "Industra Bank",
    "bluor bank": "BluOr Bank",
    "csob": "ČSOB",
    "unicredit": "UniCredit",
    "pasha bank": "Pasha Bank",
    "mashreq": "MASHREQ",
    "kapital bank": "Kapital Bank",
    "fio banka": "FIO Banka",
    "mkb": "MKB",
    "n26": "N26",
    "rak bank": "RAK Bank",
    "wio": "WIO",

    "apmaksa par rēķinu nr.": "оплата по счёту №",
    "apmaksa par rekinu nr.": "оплата по счёту №",
    "apmaksa par pakalpojumiem objekta": "оплата за услуги объекта",
    "apmaksa par pakalpojumiem": "оплата за услуги",
    "apmaksa par rēķinu": "оплата по счёту",
    "apmaksa par rekinu": "оплата по счёту",
    "apmaksa par": "оплата за",
    "apmaksa": "оплата",

    "darba algas izmaksa par": "выплата заработной платы за",
    "darba algas izmaksa": "выплата заработной платы",
    "darba alga par": "заработная плата за",
    "darba alga": "заработная плата",
    "darba algas": "заработной платы",
    "darba algu": "заработную плату",

    "rēķinu nr.": "счёт №",
    "rekinu nr.": "счёт №",
    "rēķins nr.": "счёт №",
    "rekins nr.": "счёт №",
    "rēķina nr.": "счёта №",
    "rekina nr.": "счёта №",
    "rek. nr.": "счёт №",
    "rek.nr.": "счёт №",
    "rek nr.": "счёт №",
    "rēķinu": "счёт",
    "rekinu": "счёт",
    "rēķins": "счёт",
    "rekins": "счёт",
    "rēķina": "счёта",
    "rekina": "счёта",
    "rēķin": "счёт",
    "rekin": "счёт",
    "reķins": "счёт",
    "reķinu": "счёт",

    "ires maksa par periodu": "арендная плата за период",
    "ires maksa": "арендная плата",
    "īres maksa": "арендная плата",
    "ire par dzivokli": "аренда за квартиру",
    "īre par dzīvokli": "аренда за квартиру",
    "īre un komunālie pakalpojumi": "аренда и коммунальные услуги",
    "īre un komunālie": "аренда и коммунальные",
    "ire un komunālie": "аренда и коммунальные",
    "nomas maksa": "арендная плата",
    "par dzivokli": "за квартиру",
    "par dzīvokli": "за квартиру",
    "dzivokli": "квартиру",
    "dzīvokli": "квартиру",
    "par periodu": "за период",
    "par pakalpojumiem": "за услуги",

    "komunalie pakalpojumi": "коммунальные услуги",
    "komunālie pakalpojumi": "коммунальные услуги",
    "komunalie": "коммунальные",
    "komunālie": "коммунальные",

    "kredīta apgrozījums": "кредитовый оборот",
    "debeta apgrozījums": "дебетовый оборот",
    "kredīta": "кредитовый",
    "debeta": "дебетовый",
    "apgrozījums": "оборот",

    "sākuma atlikums": "начальный остаток",
    "beigu atlikums": "конечный остаток",
    "atlikums": "остаток",

    "kompensācijas izmaksa": "выплата компенсации",
    "kompensācija": "компенсация",
    "izmaksa": "выплата",
    "izmaksas": "выплаты",

    "skaidras naudas iemaksa": "внесение наличных",
    "skaidras naudas izņemšana": "снятие наличных",

    "maksājums ar karti": "оплата картой",
    "maksājuma mērķis": "назначение платежа",
    "maksājums": "платёж",
    "maksājumi": "платежи",

    "ienākošais maksājums": "входящий платёж",
    "izejošais maksājums": "исходящий платёж",
    "ienākošais": "входящий",
    "izejošais": "исходящий",

    "bankas komisija par holdinga izveidi internetbankā": "банковская комиссия за создание холдинга в интернет-банке",
    "bankas komisija par izmaiņām klientu lietā": "банковская комиссия за изменения в деле клиента",
    "bankas komisija": "банковская комиссия",
    "komisijas maksa": "комиссионный сбор",
    "komisija": "комиссия",

    "pārskaitījums": "перевод",
    "pārskaitījumi": "переводы",
    "pārskaitīts": "переведено",

    "īpašuma tiesību maiņas noformēšanu bankā": "оформление смены права собственности в банке",
    "īpašuma tiesību": "права собственности",
    "noformēšanu": "оформление",
    "cenrādis": "прейскурант",

    "procenti par aizdevumu": "проценты по кредиту",
    "procentu maksājums": "процентный платёж",
    "procenti": "проценты",

    "nodoklis": "налог",
    "nodokļi": "налоги",
    "apdrošināšana": "страхование",
    "aizdevums": "кредит",
    "aizdevuma": "кредита",

    "atlīdzība": "вознаграждение",
    "prēmija": "премия",
    "prēmijas": "премии",

    "konts": "счёт",
    "kontā": "на счёте",
    "no konta": "со счёта",

    "saņēmējs": "получатель",
    "maksātājs": "плательщик",
    "mērķis": "назначение",
    "datums": "дата",
    "summa": "сумма",
    "valūta": "валюта",
    "veids": "тип",
    "statuss": "статус",

    "trvalý příkaz": "постоянное поручение",
    "vklad hotovosti": "внесение наличных",
    "výběr hotovosti": "снятие наличных",
    "platba kartou": "оплата картой",
    "počáteční zůstatek": "начальный остаток",
    "konečný zůstatek": "конечный остаток",
    "přehled pohybů": "обзор операций",
    "shrnutí pohybů": "сводка операций",
    "obraty za období": "обороты за период",
    "obraty od začátku": "обороты с начала",
    "počet položek": "количество позиций",
    "číslo protiúčtu": "номер корсчёта",
    "celkem připsáno": "всего зачислено",
    "celkem odepsáno": "всего списано",
    "celkem přišlo": "всего поступило",
    "celkem odešlo": "всего отправлено",
    "disponibilní zůstatek": "доступный остаток",
    "příchozí platba": "входящий платёж",
    "odchozí platba": "исходящий платёж",
    "připsáno na účet": "зачислено на счёт",
    "odepsáno z účtu": "списано со счёта",
    "místo:": "место:",
    "částka:": "сумма:",
    "poplatek": "комиссия",
    "úrok do": "проценты до",
    "převod": "перевод",
    "vklad": "внесение",
    "výběr": "снятие",
    "platba": "платёж",
    "faktura": "счёт",
    "nájem": "аренда",
    "mzda": "зарплата",
    "daň": "налог",
    "pojištění": "страхование",
    "půjčka": "кредит",
    "splátka": "платёж по кредиту",
    "odměna": "вознаграждение",
    "vratka": "возврат",
    "inkaso": "инкассо",
    "celkem": "всего",
    "zůstatek": "остаток",
    "pohyby": "операции",

    "készpénzfelvétel": "снятие наличных",
    "készpénzbefizetés": "внесение наличных",
    "kártyás fizetés": "оплата картой",
    "nyitó egyenleg": "начальный баланс",
    "záró egyenleg": "конечный баланс",
    "tranzakció típusa": "тип транзакции",
    "giro átutalás jutaléka": "комиссия за GIRO-перевод",
    "giro átutalás terhelése": "списание по GIRO-переводу",
    "giro átutalás": "GIRO-перевод",
    "bankon belüli átutalás jóváírása": "зачисление по внутреннему переводу",
    "bankon belüli átutalás": "внутренний перевод",
    "bankon belüli": "внутренний",
    "napközbeni forint átvezetés": "внутридневной перевод форинтов",
    "napközbeni forint": "внутридневной перевод форинтов",
    "netbankár havi díj": "месячная плата NetBankár",
    "netbankár": "NetBankár",
    "tranzakciós díjrész": "часть комиссии за транзакцию",
    "tranzakciós díj": "комиссия за транзакцию",
    "havi díj": "месячная плата",
    "számlavezetési díj": "плата за ведение счёта",
    "sepa átutalás jóváírása": "зачисление SEPA-перевода",
    "sepa átutalás": "SEPA-перевод",
    "fizetés": "платёж",
    "átutalás": "перевод",
    "bejövő": "входящий",
    "kimenő": "исходящий",
    "díj": "сбор",
    "jutalék": "комиссия",
    "vásárlás": "покупка",
    "kamat": "проценты",
    "bér": "зарплата",
    "bérleti díj": "арендная плата",
    "számla": "счёт",
    "adó": "налог",
    "biztosítás": "страхование",
    "kölcsön": "кредит",
    "törlesztés": "погашение",
    "visszatérítés": "возврат",
    "jóváírás": "зачисление",
    "terhelés": "списание",
    "egyenleg": "баланс",
    "összeg": "сумма",
    "közlemény": "сообщение",
    "kedvezményezett neve": "имя получателя",
    "kedvezményezett": "получатель",
    "értéknap": "дата валютирования",
    "sorszám": "номер",
    "típus": "тип",
    "dátum": "дата",
    "tranzakció": "транзакция",
    "megbízás": "поручение",
    "befizetés": "внесение",
    "kifizetés": "выплата",

    "hesaba mədaxil": "зачисление на счёт",
    "hesaba medaxil": "зачисление на счёт",
    "dövrün sonuna balans": "остаток на конец периода",
    "dovrun sonuna balans": "остаток на конец периода",
    "icra tarixi": "дата исполнения",
    "əməliyyat tarixi": "дата операции",
    "mədaxil": "приход",
    "məxaric": "расход",
    "təyinat": "назначение",
    "ödəyən": "плательщик",
    "benefisiar": "получатель",
    "balans": "баланс",
    "kart hesabi": "карточный счёт",
    "icare haqqi odenisi": "оплата аренды",
    "dovlet vergi xidmeti": "государственная налоговая служба",

    "плата за обслуживание счета": "плата за обслуживание счёта",
    "остаток в начале": "остаток на начало",
    "остаток в конце": "остаток на конец",
    "комиссионная плата": "комиссионная плата",
    "назначение платежа": "назначение платежа",
}

_WORD_DICT: Dict[str, str] = {
    "fee": "комиссия", "fees": "комиссии", "payment": "платёж", "payments": "платежи",
    "transfer": "перевод", "transfers": "переводы", "salary": "заработная плата",
    "refund": "возврат", "invoice": "счёт", "rent": "аренда",
    "utilities": "коммунальные услуги", "commission": "комиссия",
    "dividend": "дивиденды", "interest": "проценты", "purchase": "покупка",
    "withdrawal": "снятие", "deposit": "внесение", "groceries": "продукты",
    "restaurant": "ресторан", "taxi": "такси", "fuel": "топливо",
    "insurance": "страхование", "loan": "кредит", "repayment": "погашение",
    "reward": "вознаграждение", "bonus": "бонус", "cashback": "кэшбэк",
    "reference": "назначение", "details": "детали", "description": "описание",
    "beneficiary": "получатель", "payer": "плательщик", "amount": "сумма",
    "balance": "баланс", "statement": "выписка",
    "to": "к", "from": "от", "for": "за",
    "internal": "внутренний", "external": "внешний", "card": "карта",
    "outgoing": "исходящий", "incoming": "входящий",

    "poplatek": "комиссия", "úrok": "проценты", "převod": "перевод",
    "vklad": "внесение", "výběr": "снятие", "platba": "платёж",
    "faktura": "счёт", "nájem": "аренда", "mzda": "зарплата",
    "daň": "налог", "pojištění": "страхование", "půjčka": "кредит",
    "splátka": "платёж по кредиту", "odměna": "вознаграждение",
    "vratka": "возврат", "inkaso": "инкассо", "celkem": "всего",
    "zůstatek": "остаток", "pohyby": "операции", "připsáno": "зачислено",
    "odepsáno": "списано", "zaúčtováno": "проведено", "provedeno": "выполнено",
    "popis": "описание", "protiúčet": "корсчёт", "příchozí": "входящий",
    "odchozí": "исходящий",

    "apmaksa": "оплата", "apmaksas": "оплаты", "apmaksāts": "оплачено",
    "rēķins": "счёт", "rēķina": "счёта", "rēķinu": "счёт", "rēķini": "счета",
    "rekins": "счёт", "rekina": "счёта", "rekinu": "счёт", "rekini": "счета",
    "reķins": "счёт", "reķinu": "счёт", "rēkins": "счёт", "rēkinu": "счёт",

    "maksa": "плата", "maksas": "платы", "maksājums": "платёж",
    "maksājumi": "платежи", "maksājumu": "платежей",

    "alga": "зарплата", "algas": "зарплаты", "algu": "зарплату",
    "algām": "зарплатам", "darba": "рабочей",
    "darba alga": "заработная плата", "darba algas": "заработной платы",

    "izmaksa": "выплата", "izmaksas": "выплаты", "izmaksu": "выплат",
    "izmaksāt": "выплатить",

    "īre": "аренда", "īres": "аренды", "īri": "аренду",
    "ire": "аренда", "ires": "аренды", "noma": "аренда", "nomas": "аренды",
    "nomas maksa": "арендная плата",

    "dzīvoklis": "квартира", "dzīvokli": "квартиру", "dzīvokļa": "квартиры",
    "dzivoklis": "квартира", "dzivokli": "квартиру", "dzivokla": "квартиры",

    "māja": "дом", "mājas": "дома", "iela": "улица", "ielas": "улицы",
    "ielā": "на улице",

    "periods": "период", "periodu": "период", "perioda": "периода",
    "no": "с", "līdz": "до", "lidz": "до",

    "komunālie": "коммунальные", "komunalie": "коммунальные",
    "komunālo": "коммунальных", "komunāliem": "коммунальным",
    "pakalpojumi": "услуги", "pakalpojumu": "услуг",
    "pakalpojumiem": "услуг", "pakalpojums": "услуга",

    "procenti": "проценты", "procentu": "процентов", "procents": "процент",

    "nodoklis": "налог", "nodokļi": "налоги", "nodokļa": "налога",
    "nodokļu": "налогов",

    "apdrošināšana": "страхование", "apdrošināšanas": "страхования",
    "aizdevums": "кредит", "aizdevuma": "кредита",
    "kredīts": "кредит", "kredīta": "кредита",

    "komisija": "комиссия", "komisijas": "комиссии", "komisiju": "комиссию",
    "komisijas maksa": "комиссионный сбор",

    "atlikums": "остаток", "atlikuma": "остатка", "atlikumu": "остаток",
    "sākuma": "начальный", "beigu": "конечный",

    "ienākumi": "доходы", "izdevumi": "расходы",
    "ienākumu": "доходов", "izdevumu": "расходов",

    "saņēmējs": "получатель", "saņēmēja": "получателя",
    "maksātājs": "плательщик", "maksātāja": "плательщика",
    "mērķis": "назначение", "mērķa": "назначения",
    "datums": "дата", "datuma": "даты",
    "summa": "сумма", "summas": "суммы",
    "valūta": "валюта", "valūtas": "валюты",
    "veids": "тип", "veida": "типа", "statuss": "статус",
    "numurs": "номер", "numura": "номера",
    "kods": "код", "koda": "кода",

    "konts": "счёт", "konta": "счёта", "kontā": "на счёте",
    "kontu": "счёт", "kontiem": "счетам",

    "bankas": "банковские", "banka": "банк", "bankā": "в банке",
    "banku": "банк",

    "pārskaitījums": "перевод", "pārskaitījuma": "перевода",
    "pārskaitīt": "перевести", "pārskaitīts": "переведено",

    "fizetés": "платёж", "átutalás": "перевод", "bejövő": "входящий",
    "kimenő": "исходящий", "díj": "сбор", "jutalék": "комиссия",
    "vásárlás": "покупка", "kamat": "проценты", "bér": "зарплата",
    "számla": "счёт", "adó": "налог", "biztosítás": "страхование",
    "kölcsön": "кредит", "törlesztés": "погашение", "visszatérítés": "возврат",
    "jóváírás": "зачисление", "terhelés": "списание", "egyenleg": "баланс",
    "összeg": "сумма", "közlemény": "сообщение", "kedvezményezett": "получатель",
    "értéknap": "дата валютирования", "sorszám": "номер", "típus": "тип",
    "dátum": "дата", "tranzakció": "транзакция", "megbízás": "поручение",
    "befizetés": "внесение", "kifizetés": "выплата",
}

_PHRASE_KEYS_SORTED = sorted(_PHRASE_DICT.keys(), key=len, reverse=True)
_WORD_KEYS_SORTED = sorted(_WORD_DICT.keys(), key=len, reverse=True)
_WORD_PATTERN = re.compile(
    r'(?<![A-Za-zÀ-ÖØ-öø-ÿĀ-žА-Яа-я])'
    r'(' + '|'.join(re.escape(k) for k in _WORD_KEYS_SORTED) + r')'
    r'(?![A-Za-zÀ-ÖØ-öø-ÿĀ-žА-Яа-я])',
    re.IGNORECASE,
)


def _word_repl(m: re.Match) -> str:
    key = m.group(1).lower()
    return _WORD_DICT.get(key, m.group(0))


def translate_to_russian(text: str) -> str:
    if not text:
        return text
    s = str(text)
    placeholders: List[Tuple[str, str]] = []
    for i, key in enumerate(_PHRASE_KEYS_SORTED):
        pattern = re.compile(re.escape(key), re.IGNORECASE)

        def repl(m, _i=i, _key=key):
            translated = _PHRASE_DICT.get(_key, m.group(0))
            ph = f"\x00PH{_i}\x00"
            placeholders.append((ph, translated))
            return ph
        s = pattern.sub(repl, s)
    s = _WORD_PATTERN.sub(_word_repl, s)
    for ph, translated in placeholders:
        s = s.replace(ph, translated)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def translate_description_inline(original: str) -> str:
    if original is None:
        return ""
    orig = str(original).strip()
    if not orig:
        return ""
    try:
        translated = translate_to_russian(orig)
    except Exception:
        return orig
    if not translated or translated.strip() == orig.strip():
        return orig
    return f"{orig} ({translated})"


# ==================== ИЗВЛЕЧЕНИЕ КОНТРАГЕНТА ====================

_JUNK_PATTERNS = [
    r'\b[A-Z]{2}\d{2}[A-Z0-9]{12,}\b',
    r'\b[A-Z]{2}\d{2}\s\d{4}\s\d{4}\s\d{4}\s\d{4}\b',
    r'\bREF\b[^\s]*', r'\bSRN\b[^\s]*', r'\bREC\b[^\s]*',
    r'\bROC\b[^\s]*', r'\bMCC\d+\b', r'\bTOC-[A-Z0-9\-]+\b',
    r'\bT_[A-F0-9]{10,}\b',
    r'\b\d{10,}\b',
    r'\+?\d[\d\s\(\)\-]{8,}',
    r'\bLV\d{2}[A-Z]{4}\d{10,}\b',
    r'\bLT\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b',
    r'\bEE\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b',
    r'\bAZ\d{2}[A-Z]{4}\d{16,}\b',
    r'\bAE\d{2}\s?\d{3,}\b',
    r'\b\d{4}-\d{2}-\d{2}\b',
    r'\b\d{2}\.\d{2}\.\d{4}\b',
    r'_x000D_', r'[\r\n\t]+',
    r'\\[a-zA-Z]{2,}\b',
]


def _strip_junk_soft(s: str) -> str:
    if not s:
        return ''
    out = str(s)
    for pat in _JUNK_PATTERNS:
        out = re.sub(pat, ' ', out, flags=re.IGNORECASE)
    out = re.sub(r'[\*\|<>]+', ' ', out)
    out = re.sub(r'[,;:]+', ' ', out)
    out = re.sub(r'\s+', ' ', out).strip(' .,;:-–—/\\')
    return out


def _clean_counterparty_name(name: str, keep_full: bool = False) -> str:
    if not name:
        return ''
    s = str(name).strip()
    s = _strip_junk_soft(s)

    if not keep_full:
        for sep in [' | ', ' • ', ' — ', ' – ']:
            if sep in s:
                parts = [p.strip() for p in s.split(sep) if p.strip()]
                candidates = [p for p in parts
                              if p and re.search(r'[A-Za-zÀ-ÿĀ-žА-Яа-я]{2,}', p)]
                if candidates:
                    candidates.sort(key=len, reverse=True)
                    s = candidates[0]
                else:
                    s = parts[0]
                break

    s = re.sub(r'\s*\(\s*[\dA-Z]{4,}\s*\)\s*$', '', s).strip()
    s = s.strip(' .,;:-–—/\\')

    if len(s) < 2:
        return ''
    if re.fullmatch(r'[\d\s.,\-/\\]+', s):
        return ''
    return s


_BANK_WORDS = [
    'bank', 'payments', 'finance', 'revolut', 'paysera', 'wise',
    'sepa', 'csob', 'unicredit', 'tinkoff', 'bluor',
    'industra', 'pasha', 'mashreq', 'wio', 'n26', 'mkb',
    'fio', 'kapital', 'rak', 'swedbank', 'seb', 'luminor',
    'citadele', 'dnb', 'nordea', 'op corporate',
]


def _looks_like_bank_name(s: str) -> bool:
    if not s:
        return False
    low = str(s).lower()
    if low in ('as', 'sia', 'llc', 'ltd', 'inc', 'ооо', 'зао', 'оао', 'пао'):
        return False
    return any(w in low for w in _BANK_WORDS)


# --- Спец-парсеры для извлечения контрагента ---

def _extract_revolut_name(desc: str,
                           account_name: str = '',
                           payer: str = '',
                           beneficiary: str = '',
                           sender_name: str = '') -> str:
    for cand in (beneficiary, sender_name, payer):
        c = str(cand).strip() if cand else ''
        if c and c.lower() not in ('nan', 'none', 'n/a', '-'):
            cleaned = _clean_counterparty_name(c, keep_full=True)
            if cleaned and len(cleaned) >= 2 and not _looks_like_bank_name(cleaned):
                return cleaned
    if not desc:
        return ''
    s = str(desc).strip()
    for prefix in ['Money added from ', 'Money received from ', 'Money sent to ',
                   'From ', 'To ']:
        if s.lower().startswith(prefix.lower()):
            rest = s[len(prefix):].strip()
            for sep in [' | ', ' • ']:
                if sep in rest:
                    rest = rest.split(sep, 1)[0].strip()
                    break
            cleaned = _clean_counterparty_name(rest, keep_full=True)
            if cleaned and len(cleaned) >= 2:
                return cleaned
    return ''


def _extract_paysera_name(desc: str,
                           account_name: str = '',
                           payer: str = '',
                           beneficiary: str = '',
                           raw_cp: str = '') -> str:
    if raw_cp:
        c = str(raw_cp).strip()
        if c and c.lower() not in ('nan', 'none', 'n/a', '-', ''):
            cleaned = re.sub(r'\s+\(?\s*\d{6,}\s*\)?\s*$', '', c)
            cleaned = re.sub(r'\s+[A-Z]{2}\d{2}[A-Z0-9]{10,}\s*$', '', cleaned)
            cleaned = re.sub(r'\s+\([A-Z0-9]{4,}\)\s*$', '', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip(' .,;:-')
            if cleaned and len(cleaned) >= 2:
                return cleaned

    for cand in (beneficiary, payer):
        if cand:
            c = str(cand).strip()
            if c.lower() in ('nan', 'none', 'n/a', '-', ''):
                continue
            cleaned = re.sub(r'\(\s*[A-Z0-9]+\s*\)\s*$', '', c)
            cleaned = re.sub(r'\s+\(.*?\)\s*$', '', cleaned)
            cleaned = re.sub(r'\s+[A-Z]\d{4,}\s*$', '', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip(' .,;:-')
            if cleaned and len(cleaned) >= 2:
                return cleaned

    if not desc:
        return ''
    s = str(desc).strip()
    if 'плата за обслуживание' in s.lower():
        return 'Paysera LT'
    if re.match(r'^(sent|sutits|inviato)\s+', s, re.IGNORECASE):
        return ''
    return ''


def _extract_industra_name(desc: str,
                            account_name: str = '',
                            payer: str = '',
                            beneficiary: str = '',
                            raw_cp: str = '') -> str:
    if raw_cp:
        c = str(raw_cp).strip()
        if c and c.lower() not in ('nan', 'none', 'n/a', '-', ''):
            cleaned = re.sub(r'\s+\d{6,}.*$', '', c)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip(' .,;:-')
            if cleaned and len(cleaned) >= 2:
                return cleaned

    for cand in (beneficiary, payer):
        if cand:
            c = str(cand).strip()
            if c.lower() in ('nan', 'none', 'n/a', '-', ''):
                continue
            cleaned = re.sub(r'\s+\d{6,}.*$', '', c)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip(' .,;:-')
            if cleaned and len(cleaned) >= 2:
                return cleaned

    if not desc:
        return ''
    low = desc.lower()
    if 'комиссия за банковскую операцию' in low:
        return 'Industra Bank'
    if 'проводка мемориальным ордером' in low:
        return 'Industra Bank'
    m = re.search(r'(?:Исходящее перечисление|Перечисление между клиентами банка|'
                  r'Зачисление входящего платежа на счет клиента)\s*,\s*'
                  r'([^,]+)', desc, re.IGNORECASE)
    if m:
        cleaned = _clean_counterparty_name(m.group(1), keep_full=True)
        if cleaned:
            return cleaned
    return ''


def _extract_csob_name(desc: str) -> str:
    if not desc:
        return ''
    low = desc.lower()
    if 'acc. maintenance' in low or 'account maintenance' in low:
        return 'ČSOB'
    if 'charge' in low and len(desc) < 40:
        return 'ČSOB'
    if 'outgoing payment' in low:
        return 'Outgoing payment'
    if 'noncash transfer' in low:
        return 'Noncash transfer'
    return ''


def _extract_unicredit_name(desc: str) -> str:
    if not desc:
        return ''
    low = desc.lower()
    if low.startswith('popl.') or 'popl.' in low:
        return 'UniCredit Bank'
    if low.startswith('urok do') or 'urok do' in low:
        return 'UniCredit Bank'
    if 'vklad na bankomatu' in low:
        return 'UniCredit Bank'
    return ''


def _extract_bluor_name(desc: str) -> str:
    if not desc:
        return ''
    low = desc.lower()
    if 'banking charges' in low or 'bank charges' in low or 'комиссия банка' in low:
        return 'BluOr Bank'
    if 'commission' in low and 'bluor' in low:
        return 'BluOr Bank'
    return ''


def _extract_mkb_name(desc: str) -> str:
    if not desc:
        return ''
    low = desc.lower()
    if 'netbankár havi díj' in low or 'netbankar havi dij' in low:
        return 'MKB'
    if 'tranzakciós díj' in low or 'tranzakcios dij' in low:
        return 'MKB'
    if 'giro átutalás' in low or 'giro atutalas' in low:
        return 'MKB'
    if 'bankon belüli' in low:
        return 'MKB'
    if 'napközbeni forint' in low or 'napkozbeni forint' in low:
        return 'MKB'
    return ''


def _extract_tinkoff_name(desc: str) -> str:
    if not desc:
        return ''
    low = desc.lower()
    if 'внутренний перевод' in low:
        return 'Внутренний перевод'
    if 'внешний перевод' in low:
        return 'Внешний перевод'
    if 'перевод себе' in low:
        return 'Перевод себе'
    if 'плата за' in low:
        return 'Т-Банк'
    if 'перевод' in low:
        return 'Перевод'
    return ''


def _extract_wio_name(desc: str) -> str:
    if not desc:
        return ''
    s = desc.strip()
    if '|' in s:
        s = s.split('|')[0].strip()
    m = re.match(r'^([A-Za-z][A-Za-z0-9\.\-_ ]{2,40}?)\s*\*', s)
    if m:
        name = m.group(1).strip()
        if name:
            return _clean_counterparty_name(name, keep_full=True)
    m = re.match(r'^(GOOGLE|FACEBOOK|FACEBK|APPLE|AMAZON|MICROSOFT|TIKTOK|META|'
                 r'DEBCARD|VISA|MASTERCARD)\b', s, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    s = _strip_junk_soft(s)
    if not s:
        return ''
    words = s.split()
    out = []
    for w in words:
        if re.fullmatch(r'[\d.,\-/\\]+', w):
            continue
        if w.lower() in ('for', 'internationalcardspend', 'and', 'the', 'of'):
            break
        out.append(w)
        if len(out) >= 4:
            break
    return _clean_counterparty_name(' '.join(out), keep_full=True)


def _extract_pasha_name(desc: str) -> str:
    if not desc:
        return ''
    s = desc.strip()
    low = s.lower()
    if low.startswith('charge for'):
        return 'Pasha Bank'
    if 'currency exchange' in low:
        return 'Pasha Bank'
    if low.startswith('internal payment'):
        m = re.match(r'internal payment\s+(.+)$', s, re.IGNORECASE)
        if m:
            return _clean_counterparty_name(m.group(1), keep_full=True)
        return 'Pasha Bank'
    if low.startswith('outgoing xohks payment'):
        m = re.match(r'outgoing xohks payment\s+(.+)$', s, re.IGNORECASE)
        if m:
            return _clean_counterparty_name(m.group(1), keep_full=True)
        return 'Pasha Bank'
    if low.startswith('salary and other payments'):
        return 'Salary transfer'
    if 'hesaba mədaxil' in low or 'hesaba medaxil' in low:
        return 'Cash deposit'
    if 'korpon' in low or 'terminalindan' in low:
        return 'Cash deposit'
    if 'dövrün sonuna balans' in low or 'dovrun sonuna balans' in low:
        return ''
    return _clean_counterparty_name(s, keep_full=True)


def _extract_mashreq_name(desc: str) -> str:
    if not desc:
        return ''
    s = desc.strip()
    low = s.lower()
    if 'outward clearing cheque' in low:
        return 'Outward clearing cheque'
    if 'inward remittance' in low:
        return 'Inward remittance'
    if 'value added tax' in low:
        return 'VAT'
    if 'corr.bank.charges' in low:
        return 'Corr. bank charges'
    if 'online international money transfer' in low:
        return 'Online transfer'
    if 'funds transfer charges' in low:
        return 'Funds transfer charges'
    m = re.search(r'\bIPP\s+TRANSFER\b[^\-]*-\s*(.+?)\s*-\s*/', s, re.IGNORECASE)
    if m:
        return _clean_counterparty_name(m.group(1), keep_full=True)
    m = re.search(r'-\s*([A-Z][A-Z\s\.\&]{3,60}?)\s*-\s*/', s)
    if m:
        return _clean_counterparty_name(m.group(1), keep_full=True)
    return ''


def _extract_regina_alfa_name(desc: str) -> str:
    if not desc:
        return ''
    s = desc.strip()
    m = re.match(r'^(CRD_[A-Z0-9]+)', s)
    if m:
        place = re.search(r'место совершения операции:\s*(.+?)(?:MCC|$)', s)
        if place:
            place_s = place.group(1).strip()
            place_s = re.sub(r'^[0-9A-Z]{4,}\\[A-Z]{2}\\', '', place_s)
            place_s = _clean_counterparty_name(place_s, keep_full=True)
            if place_s:
                return place_s
        mcc = re.search(r'MCC(\d{4})', s)
        if mcc:
            return f"MCC{mcc.group(1)}"
        return 'Card payment'
    m = re.match(r'^(C\d{10,})', s)
    if m:
        m2 = re.search(r'через Систему быстрых платежей (?:от|на)\s+([^\.]+)', s)
        if m2:
            return _clean_counterparty_name(m2.group(1), keep_full=True)
        return 'СБП перевод'
    return ''


def _extract_kapital_name(desc: str) -> str:
    if not desc:
        return ''
    s = str(desc).strip()
    low = s.lower()
    if 'sms service fee' in low or 'sms service' in low:
        return 'Kapital Bank'
    m = re.match(
        r'^\s*\d{10,}\s+'
        r'([A-ZƏÜÖĞİŞÇ][A-ZƏÜÖĞİŞÇ\s]{2,80}?)'
        r'(?:\s+(?:Qeyri|Köçürmə|Kocurma|Əməliyyat|Emeliyyat|Kart|Hesab|Оплата|'
        r'Перевод|Комиссия|Mədaxil|Medaxil|Məxaric|Mexaric|->|→|>).*)?$',
        s, re.IGNORECASE
    )
    if m:
        name = m.group(1).strip()
        name = re.sub(r'\s+', ' ', name)
        if name and len(name) >= 3:
            return name
    if low in ('sms service fee', 'sms xidməti'):
        return 'Kapital Bank'
    cleaned = _clean_counterparty_name(s, keep_full=True)
    return cleaned


def _extract_name_by_patterns(desc: str) -> str:
    if not desc:
        return ''
    patterns = [
        (r'\bMoney added from\s+(.+?)(?:\s*\||$)', 1),
        (r'\bMoney received from\s+(.+?)(?:\s*\||$)', 1),
        (r'\bMoney sent to\s+(.+?)(?:\s*\||$)', 1),
        (r'^\s*From\s+(.+?)(?:\s*\||$)', 1),
        (r'^\s*To\s+(.+?)(?:\s*\||$)', 1),
        (r'\bpayment\s+to\s+(.+?)(?:\s*\||$)', 1),
        (r'\btransfer\s+to\s+(.+?)(?:\s*\||$)', 1),
        (r'\bFrom:\s*(.+?)(?:\s*\||$)', 1),
        (r'\bTo:\s*(.+?)(?:\s*\||$)', 1),
        (r'\bсписан[ао]?\s+(?:на\s+сумму\s+[\d\s.,]+\s*[A-Z]{0,3},?\s*)?(.+?)(?:\s*\||$)', 1),
        (r'\bоплата\s+(.+?)(?:\s*\||$)', 1),
        (r'\bперевод\s+в\s+адрес\s+(.+?)(?:\s*\||$)', 1),
        (r'\b(?:payment|transfer|paid|sent)\s+to\s+(.+?)(?:\s*\||$)', 1),
    ]
    for pat, grp in patterns:
        m = re.search(pat, desc, re.IGNORECASE)
        if m:
            cand = m.group(grp).strip()
            cleaned = _clean_counterparty_name(cand, keep_full=True)
            if cleaned and len(cleaned) >= 2 and not _looks_like_bank_name(cleaned):
                return cleaned
    return ''


def extract_counterparty_smart(description: str,
                                account_name: str = '',
                                payer: str = '',
                                beneficiary: str = '',
                                raw_cp: str = '',
                                sender_name: str = '') -> Tuple[str, str]:
    desc = (description or '').strip()
    acc_low = (account_name or '').lower()

    # 1) Прямые кандидаты
    for cand in (raw_cp, beneficiary, sender_name, payer):
        if not cand:
            continue
        c = str(cand).strip()
        if not c or c.lower() in ('nan', 'none', 'n/a', '-'):
            continue
        cleaned = re.sub(r'\s+\(?\s*\d{6,}\s*\)?\s*$', '', c)
        cleaned = re.sub(r'\s+[A-Z]{2}\d{2}[A-Z0-9]{10,}\s*$', '', cleaned)
        cleaned = re.sub(r'\s+\([A-Z0-9]{4,}\)\s*$', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip(' .,;:-')
        if cleaned and len(cleaned) >= 2 and not _looks_like_bank_name(cleaned):
            return (_to_scalar_str(cleaned), _to_scalar_str(desc))

    if not desc:
        return ('', '')

    # 2) Спец-парсеры по банку
    cp = ''
    if 'revolut' in acc_low:
        cp = _extract_revolut_name(desc, account_name, payer, beneficiary, sender_name)
    if not cp and 'paysera' in acc_low:
        cp = _extract_paysera_name(desc, account_name, payer, beneficiary, raw_cp)
    if not cp and ('industra' in acc_low or 'plavas' in acc_low or 'kl59' in acc_low):
        cp = _extract_industra_name(desc, account_name, payer, beneficiary, raw_cp)
    if not cp and ('csob' in acc_low or 'jenhor' in acc_low
                   or 'jenisov' in acc_low or 'dzibik' in acc_low
                   or 'džibik' in acc_low or 'rr ' in acc_low
                   or 'koruna strojka' in acc_low):
        cp = _extract_csob_name(desc)
    if not cp and ('unicredit' in acc_low or 'garpiz' in acc_low
                   or 'twohills' in acc_low or 'koruna' in acc_low
                   or 'b1 estate' in acc_low):
        cp = _extract_unicredit_name(desc)
    if not cp and 'bluor' in acc_low:
        cp = _extract_bluor_name(desc)
    if not cp and ('mkb' in acc_low or 'budapest' in acc_low):
        cp = _extract_mkb_name(desc)
    if not cp and 'tinkoff' in acc_low:
        cp = _extract_tinkoff_name(desc)
    if not cp and 'wio' in acc_low:
        cp = _extract_wio_name(desc)
    if not cp and ('pasha' in acc_low or 'bunda' in acc_low):
        cp = _extract_pasha_name(desc)
    if not cp and ('mashreq' in acc_low or 'nomiqa' in acc_low):
        cp = _extract_mashreq_name(desc)
    if not cp and ('kapital' in acc_low or ('saida' in acc_low and 'azn' in acc_low)):
        cp = _extract_kapital_name(desc)
    if not cp and 'regina alfa' in acc_low:
        cp = _extract_regina_alfa_name(desc)
    if not cp and 'wise' in acc_low:
        cp = _extract_wio_name(desc)

    # 3) Шаблоны
    if not cp:
        cp = _extract_name_by_patterns(desc)

    # 4) Эвристика
    if not cp:
        parts = re.split(r'[|•;]', desc)
        for p in parts:
            p_clean = _clean_counterparty_name(p.strip(), keep_full=True)
            if not p_clean or len(p_clean) < 3:
                continue
            if _looks_like_bank_name(p_clean):
                continue
            if re.search(r'[A-Za-zÀ-ÿĀ-žА-Яа-я]{3,}', p_clean) \
                    and not re.fullmatch(r'[\d\s.,\-/\\]+', p_clean):
                cp = p_clean
                if cp:
                    break

    # 5) Имя банка из названия счёта
    if not cp:
        m = re.search(
            r'\b(CSOB|UniCredit|Revolut|Tinkoff|Paysera|Wise|BluOr|Industra|'
            r'Pasha|Mashreq|WIO|N26|MKB|FIO|Kapital|RAK|ČSOB)\b',
            account_name, re.IGNORECASE
        )
        if m:
            cp = m.group(1)

    cp = _to_scalar_str(cp)
    desc = _to_scalar_str(desc)
    return (cp, desc)
# ==================== ФАЙЛОВЫЕ УТИЛИТЫ ====================

def read_xlsx(file_content: bytes, sheet_name=None, header=None):
    for engine in ['openpyxl', 'xlrd', None]:
        try:
            kw = {'header': header}
            if sheet_name:
                kw['sheet_name'] = sheet_name
            if engine:
                kw['engine'] = engine
            df = pd.read_excel(BytesIO(file_content), **kw)
            if df is not None and not df.empty:
                return df
        except Exception:
            continue
    return None


def docx_all_text(file_content: bytes) -> str:
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return ''
    parts = []
    for table in doc.tables:
        for row in table.rows:
            row_cells = []
            for cell in row.cells:
                t = cell.text.strip()
                if t:
                    row_cells.append(t)
            if row_cells:
                parts.append(' | '.join(row_cells))
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            parts.append(t)
    full = '\n'.join(parts)
    return full.replace('\ufeff', '').replace('\xa0', ' ')


def docx_dump(file_content: bytes) -> str:
    try:
        doc = Document(BytesIO(file_content))
    except Exception as e:
        return f'[ошибка открытия DOCX: {e}]'
    lines = ["=== PARAGRAPHS ==="]
    for i, para in enumerate(doc.paragraphs):
        t = para.text.strip()
        if t:
            lines.append(f"P{i}: {t[:300]}")
    lines.append("")
    lines.append("=== TABLES ===")
    for ti, table in enumerate(doc.tables):
        lines.append(f"--- TABLE {ti} ---")
        for ri, row in enumerate(table.rows):
            cells = [c.text.strip() for c in row.cells]
            lines.append(f"R{ri}: {cells}")
    return '\n'.join(lines)


# ---------- ГЛАВНОЕ ИСПРАВЛЕНИЕ: pdf_all_text с fallback ----------

_CID_PATTERN = re.compile(r'\(cid:\d+\)')


def _text_has_cid_junk(text: str) -> bool:
    """Если больше 5% текста — это (cid:XX), значит нужен fallback."""
    if not text:
        return False
    cid_count = len(_CID_PATTERN.findall(text))
    if cid_count == 0:
        return False
    return cid_count > 5


def pdf_all_text(file_content: bytes) -> str:
    """
    Основной путь: pdfplumber.
    Fallback: pdfminer.high_level.extract_text — помогает при (cid:XX).
    """
    parts = []
    try:
        with pdfplumber.open(BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                try:
                    # Пробуем layout=True для табличных PDF (Wise, N26)
                    t = page.extract_text(layout=False)
                except TypeError:
                    t = page.extract_text()
                if t:
                    parts.append(t)
    except Exception:
        parts = []

    primary = '\n'.join(parts).replace('\ufeff', '').replace('\xa0', ' ')

    # Если основной путь дал мусор из (cid:XX) или пусто — fallback
    if _text_has_cid_junk(primary) or not primary.strip():
        if _PDFMINER_AVAILABLE:
            try:
                fallback = pdfminer_extract_text(BytesIO(file_content))
                if fallback:
                    fallback = fallback.replace('\ufeff', '').replace('\xa0', ' ')
                    # pdfminer обычно расшифровывает (cid:XX) лучше
                    if not _text_has_cid_junk(fallback) or len(fallback) > len(primary):
                        return fallback
            except Exception:
                pass

    return primary


def pdf_all_text_layout(file_content: bytes) -> str:
    """Дополнительный вариант: с layout=True — сохраняет колонки."""
    parts = []
    try:
        with pdfplumber.open(BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                try:
                    t = page.extract_text(layout=True)
                except TypeError:
                    t = page.extract_text()
                if t:
                    parts.append(t)
    except Exception:
        pass
    return '\n'.join(parts).replace('\ufeff', '').replace('\xa0', ' ')


def pdf_all_tables(file_content: bytes) -> List[List[List[str]]]:
    tables_out = []
    try:
        with pdfplumber.open(BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                for t in page.extract_tables():
                    cleaned = []
                    for row in t:
                        cleaned.append([(c or '').strip() for c in row])
                    if cleaned:
                        tables_out.append(cleaned)
    except Exception:
        return []
    return tables_out


def read_text_with_encoding(file_content: bytes) -> str:
    encodings = ['utf-8-sig', 'utf-8', 'iso-8859-2', 'cp1250', 'cp1251', 'latin-1']
    for enc in encodings:
        try:
            content = file_content.decode(enc)
            if enc not in ('latin-1',):
                bad = sum(1 for c in content if c == '\ufffd')
                if bad > len(content) * 0.001:
                    continue
            if content.startswith('\ufeff'):
                content = content[1:]
            return content
        except Exception:
            continue
    try:
        content = file_content.decode('latin-1')
        if content.startswith('\ufeff'):
            content = content[1:]
        return content
    except Exception:
        return ''


def _is_real_xls(file_content: bytes) -> bool:
    return file_content[:4] == b'\xd0\xcf\x11\xe0'


def _is_real_xlsx(file_content: bytes) -> bool:
    return file_content[:2] == b'PK'


def _is_real_pdf(file_content: bytes) -> bool:
    return file_content[:4] == b'%PDF'


def _is_real_docx(file_content: bytes) -> bool:
    if file_content[:2] != b'PK':
        return False
    head = file_content[:4096]
    if b'word/' in head:
        return True
    if b'wordprocessingml' in head:
        return True
    if b'[Content_Types].xml' in head and b'word' in head:
        return True
    return False


def _looks_like_csv(file_content: bytes) -> bool:
    try:
        head = file_content[:2048].decode('utf-8', errors='ignore')
    except Exception:
        try:
            head = file_content[:2048].decode('latin-1', errors='ignore')
        except Exception:
            return False
    if head.count('\n') < 2:
        return False
    lines = [l for l in head.split('\n') if l.strip()][:5]
    if len(lines) < 2:
        return False
    for sep in [';', ',', '\t']:
        counts = [l.count(sep) for l in lines]
        if counts and min(counts) >= 1 and max(counts) - min(counts) <= 2:
            return True
    return False


def _detect_real_type(file_content: bytes, fallback_ext: str = '') -> str:
    if not file_content:
        return 'unknown'
    if _is_real_pdf(file_content):
        return 'pdf'
    if _is_real_xls(file_content):
        return 'xls'
    if _is_real_xlsx(file_content):
        if _is_real_docx(file_content):
            return 'docx'
        return 'xlsx'
    if _looks_like_csv(file_content):
        return 'csv'
    ext = (fallback_ext or '').lower()
    if ext.startswith('.'):
        ext = ext[1:]
    if ext in ('pdf', 'xls', 'xlsx', 'docx', 'csv'):
        return ext
    return 'unknown'


def _split_line(line: str, sep: str) -> List[str]:
    parts = []
    cur = ''
    inq = False
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == '"':
            if inq and i + 1 < n and line[i + 1] == '"':
                cur += '"'
                i += 2
                continue
            inq = not inq
        elif ch == sep and not inq:
            parts.append(cur.strip())
            cur = ''
        else:
            cur += ch
        i += 1
    parts.append(cur.strip())
    return [p.strip('"') for p in parts]


MAX_REASONABLE_AMOUNT = 1e12


def _is_reasonable_amount(v: float) -> bool:
    try:
        return abs(float(v)) < MAX_REASONABLE_AMOUNT
    except Exception:
        return False


def _cell_is_numeric(v) -> bool:
    if v is None:
        return False
    try:
        if pd.isna(v):
            return False
    except Exception:
        pass
    if isinstance(v, (int, float)):
        return True
    s = str(v).strip()
    if not s:
        return False
    return bool(re.fullmatch(r'^-?[\d\s\u00a0]*[.,]?\d*$', s))


# ==================== ФИЛЬТР СЛУЖЕБНЫХ СТРОК ====================

_SERVICE_LINE_MARKERS = [
    'початочный zustatek', 'počáteční zůstatek', 'pocatecni zustatek',
    'konečný zůstatek', 'konecny zustatek', 'koncový zůstatek',
    'начальный остаток', 'конечный остаток',
    'входящий остаток', 'исходящий остаток',
    'opening balance', 'closing balance',
    'starting balance', 'ending balance', 'final balance',
    'start balance', 'end balance',
    'saldo previo', 'tu nuevo saldo', 'nuevo saldo',
    'saldo inicial', 'saldo final',
    'celkem připsáno', 'celkem odepsáno',
    'celkem přišlo', 'celkem odešlo',
    'celkem prislo', 'celkem odeslo',
    'disponibilní zůstatek', 'disponibilni zustatek',
    'přehled pohybů', 'prehled pohybu',
    'shrnutí pohybů', 'shrnuti pohybu',
    'obraty za období', 'obraty za obdobi',
    'obraty od začátku', 'obraty od zacatku',
    'počet položek', 'pocet polozek',
    'počet čekajících obratů', 'pocet cekajicich obratu',
    'kredit / debet', 'kredit/debet',
    'type of operations', 'types of operations',
    'типы операций', 'тип операции',
    'debit turnover', 'credit turnover',
    'дебетовый оборот', 'кредитовый оборот',
    'kredīta apgrozījums', 'debeta apgrozījums',
    'итоговый баланс', 'неоплаченная комиссия',
    'date (utc)', 'описание расходы прибыль баланс',
    'описание входящие исходящие сумма',
]


def _is_service_line(text: str) -> bool:
    if not text:
        return False
    low = str(text).lower().strip()
    if not low:
        return True
    for m in _SERVICE_LINE_MARKERS:
        if m in low:
            return True
    # Строки только с "итого"/"total"
    if re.fullmatch(r'(total|итого|celkem|всего)[\s:]*[\d\s.,\-€$£¥]*', low):
        return True
    return False


# ==================== CSOB ====================

def parse_csob_generic(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    content = read_text_with_encoding(file_content)
    lines = [l.rstrip('\r').strip() for l in content.split('\n') if l.strip()]
    if len(lines) < 2:
        return []
    header_idx = -1
    for i, line in enumerate(lines):
        low = line.lower()
        if 'account number' in low and 'posting date' in low:
            header_idx = i
            break
    if header_idx == -1:
        return []
    for line in lines[header_idx + 1:]:
        if not line:
            continue
        parts = [p.strip() for p in line.split(';')]
        while parts and parts[-1] == '':
            parts.pop()
        if len(parts) < 7:
            continue
        try:
            date = parse_date(safe_str(parts[4]))
            if not date:
                continue
            amount_str = safe_str(parts[6])
            if not amount_str:
                continue
            if re.match(r'^\d{7,}$', amount_str):
                continue
            if re.match(r'^\d+\/\d+$', amount_str):
                continue
            is_amount = False
            if ',' in amount_str or '.' in amount_str:
                is_amount = True
            elif amount_str.startswith('-'):
                is_amount = True
            elif amount_str.startswith('(') and amount_str.endswith(')'):
                is_amount = True
            if not is_amount:
                continue
            amount = parse_amount(amount_str)
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            counterparty = ''
            if len(parts) > 13:
                counterparty = safe_str(parts[13])
            if not counterparty and len(parts) > 3:
                counterparty = safe_str(parts[3])
            description = ''
            for idx in [16, 15, 28, 12, 11, 10, 2]:
                if idx < len(parts) and safe_str(parts[idx]) and safe_str(parts[idx]) != 'nan':
                    val = safe_str(parts[idx])
                    if not re.match(r'^[\d.,\-]+$', val):
                        description = val
                        break
            if _is_service_line(description):
                continue
            cp_final, _ = extract_counterparty_smart(
                description, account_name, counterparty, '', ''
            )
            transactions.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final,
                'Наименование счета': account_name,
                'Описание': description
            })
        except Exception:
            continue
    return transactions


def parse_dzibik_main_csob(file_content, account_name):
    return parse_csob_generic(file_content, account_name)


def parse_jenisov_csob_czk(file_content, account_name):
    return parse_csob_generic(file_content, account_name)


def parse_jenisov_csob_eur(file_content, account_name):
    return parse_csob_generic(file_content, account_name)


def parse_rr_strojka_czk_csob(file_content, account_name):
    return parse_csob_generic(file_content, account_name)


def parse_rr_strojka_eur_csob(file_content, account_name):
    return parse_csob_generic(file_content, account_name)


def parse_rr_rev_ostr_csob(file_content, account_name):
    return parse_csob_generic(file_content, account_name)


def parse_koruna_strojka_czk_csob(file_content, account_name):
    return parse_csob_generic(file_content, account_name)


def parse_koruna_strojka_eur_csob(file_content, account_name):
    return parse_csob_generic(file_content, account_name)


# ==================== НОВЫЙ: Jenisov-Horska CSAS PDF ====================

def parse_csas_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Парсер выписок Česká spořitelna (ČSAS) в PDF.
    Извлекает блоки из 'PŘEHLED POHYBŮ NA ÚČTU'.
    """
    result = []
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []

    lines = full_text.split('\n')

    # Ищем строку-заголовок
    header_idx = -1
    for i, l in enumerate(lines):
        low = l.lower()
        if 'přehled pohyb' in low or 'prehled pohyb' in low:
            header_idx = i
            break

    if header_idx == -1:
        # Может быть табличная структура — пробуем через таблицы
        tables = pdf_all_tables(file_content)
        for table in tables:
            for row in table:
                joined = ' | '.join([c or '' for c in row])
                if not joined.strip():
                    continue
                # Формат: дата | описание | částka
                m = re.match(
                    r'^(\d{1,2}\.\d{1,2}\.\d{4})\s*\|\s*(.+?)\s*\|\s*'
                    r'(-?[\d\s]+[.,]\d{2})\s*$',
                    joined
                )
                if m:
                    date = parse_date(m.group(1))
                    desc = m.group(2).strip()
                    amount = parse_amount(m.group(3))
                    if not date or amount == 0.0:
                        continue
                    if _is_service_line(desc):
                        continue
                    cp_final, _ = extract_counterparty_smart(desc, account_name)
                    if not cp_final:
                        cp_final = 'Česká spořitelna'
                    result.append({
                        'Дата': date, 'Сумма': amount,
                        'Контрагент': cp_final,
                        'Наименование счета': account_name,
                        'Описание': desc
                    })
        if result:
            return result

    # Текстовый режим: ищем блоки после заголовка
    date_re = re.compile(r'^(\d{1,2}\.\d{1,2}\.\d{4})\s+(.+?)$')
    amount_re = re.compile(r'(-?[\d\s\u00a0]+[.,]\d{2})(?!\d)')

    in_section = False
    for i, l in enumerate(lines):
        low = l.lower()
        if 'přehled pohyb' in low or 'prehled pohyb' in low:
            in_section = True
            continue
        if in_section:
            if 'konečný zůstatek' in low or 'konecny zustatek' in low:
                in_section = False
                continue
            if _is_service_line(l):
                continue

            m = date_re.match(l.strip())
            if m:
                date = parse_date(m.group(1))
                if not date:
                    continue
                rest = m.group(2).strip()

                # Собираем многострочное описание до следующей даты
                block_lines = [rest]
                j = i + 1
                while j < len(lines):
                    nl = lines[j].strip()
                    if date_re.match(nl):
                        break
                    if 'konečný zůstatek' in nl.lower() or 'konecny zustatek' in nl.lower():
                        break
                    if _is_service_line(nl):
                        j += 1
                        continue
                    block_lines.append(nl)
                    j += 1

                block_text = ' '.join(block_lines)
                ams = list(amount_re.finditer(block_text))
                if not ams:
                    continue

                # Берём последний найденный amount — это сумма операции
                am = ams[-1]
                amount = parse_amount(am.group(1))
                if amount == 0.0 or not _is_reasonable_amount(amount):
                    continue

                desc = block_text[:am.start()].strip(' ,;')
                # Убираем служебные префиксы
                desc = re.sub(
                    r'^\s*(Tuzemská odchozí úhrada|Tuzemská příchozí úhrada|'
                    r'Ceny za služby|Cena za vedení účtu|Převod|Vklad|Výběr|'
                    r'Platba kartou|Trvalý příkaz|Inkaso)\s*',
                    r'\1 ', desc, flags=re.IGNORECASE
                ).strip()

                if not desc:
                    continue
                if _is_service_line(desc):
                    continue

                cp_final, _ = extract_counterparty_smart(desc, account_name)
                if not cp_final:
                    cp_final = 'Česká spořitelna'

                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp_final,
                    'Наименование счета': account_name,
                    'Описание': desc
                })

    # Дедупликация
    seen = set()
    deduped = []
    for r in result:
        key = (r['Дата'], round(r['Сумма'], 2), r['Контрагент'], r['Описание'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped


def parse_jenhor_unelma_csas_pdf(file_content, account_name):
    return parse_csas_pdf(file_content, account_name)


# ==================== Regina Alfa ====================

def parse_regina_alfa_xlsx(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        df = pd.read_excel(BytesIO(file_content), sheet_name='Table 1', header=None)
    except Exception:
        try:
            df = pd.read_excel(BytesIO(file_content), header=None)
        except Exception:
            return []
    if df.empty:
        return []
    data_start = -1
    for idx, row in df.iterrows():
        if idx < 50:
            row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Операции по счету' in row_str:
                data_start = idx + 1
                break
    if data_start == -1:
        return []
    current_date = current_desc = current_amount = None
    for idx in range(data_start, len(df)):
        row = df.iloc[idx]
        rv = [x for x in row.values if pd.notna(x)]
        if not rv:
            continue
        has_date = False
        date_val = amount_val = None
        if len(row) > 0 and pd.notna(row.iloc[0]):
            val_str = str(row.iloc[0]).strip()
            if re.match(r'^\d{4}-\d{2}-\d{2}', val_str) or re.match(r'^\d{2}\.\d{2}\.\d{4}', val_str):
                has_date = True
                date_val = val_str
        for ci in range(len(row) - 1, max(0, len(row) - 3), -1):
            if ci < len(row) and pd.notna(row.iloc[ci]) and str(row.iloc[ci]).strip():
                vs = str(row.iloc[ci]).strip()
                if vs != 'nan':
                    vsc = re.sub(r'\s*RUR\s*$', '', vs)
                    if re.search(r'[\d,.]', vsc):
                        amount_val = vs
                        break
        if has_date:
            if current_date and current_amount is not None:
                amt = parse_amount(str(current_amount))
                if amt != 0.0 and _is_reasonable_amount(amt):
                    desc_val = (current_desc or '').strip()
                    if not _is_service_line(desc_val):
                        cp, _ = extract_counterparty_smart(desc_val, account_name)
                        transactions.append({
                            'Дата': parse_date(str(current_date)),
                            'Сумма': amt,
                            'Контрагент': cp if cp else '',
                            'Наименование счета': account_name,
                            'Описание': desc_val
                        })
            current_date = date_val
            current_desc = ''
            current_amount = amount_val
            dp = []
            for ci in range(1, len(row)):
                if ci < len(row) and pd.notna(row.iloc[ci]) and str(row.iloc[ci]).strip():
                    vs = str(row.iloc[ci]).strip()
                    if vs and vs != 'nan' and vs != current_date and vs != current_amount:
                        if not re.search(r'[\d,.]\s*RUR', vs):
                            dp.append(vs)
            if dp:
                current_desc = ' '.join(dp)
        else:
            if current_date:
                dp = []
                for val in row.values:
                    if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                        dp.append(str(val).strip())
                if dp:
                    current_desc = (current_desc or '') + ' ' + ' '.join(dp)
                if amount_val is not None and current_amount is None:
                    current_amount = amount_val
    if current_date and current_amount is not None:
        amt = parse_amount(str(current_amount))
        if amt != 0.0 and _is_reasonable_amount(amt):
            desc_val = (current_desc or '').strip()
            if not _is_service_line(desc_val):
                cp, _ = extract_counterparty_smart(desc_val, account_name)
                transactions.append({
                    'Дата': parse_date(str(current_date)),
                    'Сумма': amt,
                    'Контрагент': cp if cp else '',
                    'Наименование счета': account_name,
                    'Описание': desc_val
                })
    return transactions


def parse_regina_alfa_docx(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []

    for table in doc.tables:
        if not table.rows:
            continue
        hdr = [c.text.strip().lower() for c in table.rows[0].cells]
        if not any('дата проводки' in h for h in hdr):
            continue
        date_i = code_i = desc_i = amount_i = -1
        for i, h in enumerate(hdr):
            if 'дата проводки' in h:
                date_i = i
            elif 'код операции' in h:
                code_i = i
            elif 'описание' in h:
                desc_i = i
            elif 'сумма' in h:
                amount_i = i
        if date_i == -1 or amount_i == -1:
            continue

        current_date = None
        current_code = ''
        current_desc_parts = []
        current_amount = None

        def flush():
            nonlocal current_date, current_code, current_desc_parts, current_amount
            if current_date and current_amount is not None:
                amt = parse_amount(str(current_amount))
                if amt != 0.0 and _is_reasonable_amount(amt):
                    desc_full = re.sub(r'\s+', ' ', ' '.join(current_desc_parts)).strip()
                    full_desc = f"{current_code} {desc_full}".strip() if current_code else desc_full
                    if not _is_service_line(full_desc):
                        cp, _ = extract_counterparty_smart(full_desc, account_name)
                        result.append({
                            'Дата': parse_date(str(current_date)),
                            'Сумма': amt,
                            'Контрагент': cp if cp else '',
                            'Наименование счета': account_name,
                            'Описание': full_desc
                        })
            current_date = None
            current_code = ''
            current_desc_parts = []
            current_amount = None

        for row in table.rows[1:]:
            cells = [c.text.strip() for c in row.cells]
            if len(cells) <= max(date_i, amount_i):
                continue
            d_raw = cells[date_i] if date_i < len(cells) else ''
            a_raw = cells[amount_i] if amount_i < len(cells) else ''
            c_raw = cells[code_i] if code_i >= 0 and code_i < len(cells) else ''
            desc_raw = cells[desc_i] if desc_i >= 0 and desc_i < len(cells) else ''

            d_clean = re.match(r'^(\d{2}\.\d{2}\.\d{4})', d_raw)
            a_clean = re.match(r'^(-?[\d\s\u00a0]+[.,]\d{2})\s*(RUR|USD|EUR|CZK|AZN)?', a_raw)

            if d_clean:
                flush()
                current_date = d_clean.group(1)
                current_code = c_raw
                current_desc_parts = [desc_raw] if desc_raw else []
                current_amount = a_clean.group(1) if a_clean else None
            else:
                if current_date:
                    if desc_raw:
                        current_desc_parts.append(desc_raw)
                    if a_clean and current_amount is None:
                        current_amount = a_clean.group(1)
        flush()

    if result:
        return result

    full_text = docx_all_text(file_content)
    if not full_text:
        return []
    normalized = full_text.replace(' | ', ' ')
    pattern = re.compile(
        r'(\d{2}\.\d{2}\.\d{4})\s*([A-Z0-9\_]+)\s*(.{1,2000}?)(-?[\d\s\u00a0]+,\d{2})\s*RUR',
        re.DOTALL
    )
    for m in pattern.finditer(normalized):
        try:
            date = parse_date(m.group(1).strip())
            code = m.group(2).strip()
            desc = re.sub(r'\s+', ' ', m.group(3)).strip()
            amount = parse_amount(m.group(4))
            if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            full_desc = f"{code} {desc}"
            if _is_service_line(full_desc):
                continue
            cp, _ = extract_counterparty_smart(full_desc, account_name)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp if cp else '',
                'Наименование счета': account_name,
                'Описание': full_desc
            })
        except Exception:
            continue
    return result


def parse_regina_alfa_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []
    pattern = re.compile(
        r'(\d{2}\.\d{2}\.\d{4})\s*([A-Z0-9\_]+)\s*(.{1,2000}?)(-?[\d\s\u00a0]+,\d{2})\s*RUR',
        re.DOTALL
    )
    result = []
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(1).strip())
            code = m.group(2).strip()
            desc = re.sub(r'\s+', ' ', m.group(3)).strip()
            amount = parse_amount(m.group(4))
            if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            full_desc = f"{code} {desc}"
            if _is_service_line(full_desc):
                continue
            cp, _ = extract_counterparty_smart(full_desc, account_name)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp if cp else '',
                'Наименование счета': account_name,
                'Описание': full_desc
            })
        except Exception:
            continue
    return result


# ==================== Tinkoff ====================

def parse_tinkoff_docx(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []
    target = None
    for table in doc.tables:
        if not table.rows:
            continue
        first = ' '.join(c.text.strip() for c in table.rows[0].cells)
        if 'Дата и время операции' in first and 'Сумма' in first:
            target = table
            break
    if target is None:
        return []
    hdr = [c.text.strip() for c in target.rows[0].cells]
    date_idx = amount_idx = desc_idx = -1
    for i, h in enumerate(hdr):
        if 'Дата и время операции' in h:
            date_idx = i
        elif 'Сумма в валюте операции' in h:
            amount_idx = i
        elif 'Описание операции' in h:
            desc_idx = i
    if date_idx == -1:
        date_idx = 0
    if amount_idx == -1:
        amount_idx = 2
    if desc_idx == -1:
        desc_idx = 4
    for row in target.rows[1:]:
        cells = [c.text.strip() for c in row.cells]
        if len(cells) < 3:
            continue
        try:
            m = re.match(r'(\d{2}\.\d{2}\.\d{4})', cells[date_idx] if date_idx < len(cells) else '')
            if not m:
                continue
            date = parse_date(m.group(1))
            amount = parse_amount(cells[amount_idx] if amount_idx < len(cells) else '')
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            desc = re.sub(r'\s+', ' ', cells[desc_idx] if desc_idx < len(cells) else '').strip()
            if _is_service_line(desc):
                continue
            cp, _ = extract_counterparty_smart(desc, account_name)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp if cp else '',
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


def parse_tinkoff_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []
    result = []
    pattern = re.compile(
        r'(\d{2}\.\d{2}\.\d{4})\s+\d{2}:\d{2}\s+'
        r'(\d{2}\.\d{2}\.\d{4})\s+\d{2}:\d{2}\s+'
        r'([+\-]?[\d\s]+[.,]\d{2})\s*[₽PР]\s*'
        r'([+\-]?[\d\s]+[.,]\d{2})\s*[₽PР]\s*'
        r'([^\n]{2,1000}?)(?:\s+7596|\s+---|\n|$)',
        re.MULTILINE
    )
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(1))
            amount = parse_amount(m.group(3))
            desc = re.sub(r'\s+', ' ', m.group(5)).strip()
            if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            if _is_service_line(desc):
                continue
            cp, _ = extract_counterparty_smart(desc, account_name)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp if cp else '',
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


# ==================== BluOr Bank ====================

_BLUOR_SERVICE_MARKERS = [
    'начальный остаток', 'конечный остаток',
    'входящий остаток', 'исходящий остаток',
    'opening balance', 'closing balance',
    'starting balance', 'ending balance', 'total',
    'дебет (d)', 'кредит (c)',
    'debit (d)', 'credit (c)',
    'saldo počáteční', 'saldo konečné',
    'sākuma atlikums', 'beigu atlikums',
]


def _is_bluor_service_row(parts: List[str]) -> bool:
    for part in parts:
        v = (part or '').strip().lower()
        if not v:
            continue
        for marker in _BLUOR_SERVICE_MARKERS:
            if marker in v:
                return True
    return False


def _parse_bluor_csv(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    content = read_text_with_encoding(file_content)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if not lines:
        return []
    first_line = lines[0]
    sep = ';' if first_line.count(';') > first_line.count(',') else ','

    for line in lines:
        parts = _split_line(line, sep)
        if len(parts) < 4:
            continue
        try:
            if _is_bluor_service_row(parts):
                continue

            date = None
            date_idx = -1
            for i in range(min(5, len(parts))):
                d = parse_date(parts[i])
                if d and re.match(r'^\d{2}-\d{2}-\d{4}$', d):
                    date = d
                    date_idx = i
                    break
            if not date:
                continue

            amount = 0.0
            amount_idx = -1
            for i in [4, 5, 3, 6]:
                if i < len(parts):
                    a = parse_amount(parts[i])
                    if a != 0.0:
                        amount = a
                        amount_idx = i
                        break

            ttype = ''
            for i in [6, 7, 8]:
                if i < len(parts):
                    v = parts[i].strip().upper()
                    if v in ('D', 'C'):
                        ttype = v
                        break
            if amount == 0.0 and not ttype:
                continue
            if not _is_reasonable_amount(amount):
                continue

            desc = ''
            for i in [3, 2, 1]:
                if i < len(parts) and i not in (date_idx, amount_idx):
                    v = parts[i].strip()
                    if v and v != 'nan' and not re.match(r'^\d{2}\.\d{2}\.\d{4}$', v):
                        desc = v
                        break
            if ttype == 'D':
                amount = -abs(amount)
            elif ttype == 'C':
                amount = abs(amount)

            if _is_service_line(desc):
                continue

            cp, _ = extract_counterparty_smart(desc, account_name)

            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp if cp else '',
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


def parse_bsr_bluor_2(file_content, account_name):
    return _parse_bluor_csv(file_content, account_name)


def parse_bsr_bluor_3(file_content, account_name):
    return _parse_bluor_csv(file_content, account_name)


def parse_kl59_bluor(file_content, account_name):
    return _parse_bluor_csv(file_content, account_name)


def parse_bluor_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []
    result = []
    pattern = re.compile(
        r'(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})\s+'
        r'([A-Z0-9_/\(\)\.]{3,60}?)\s+'
        r'([^\n]{3,1000}?)\s+'
        r'([\d\s]+[.,]\d{2})\s*([A-Z]{3})\s*([DC])',
        re.MULTILINE
    )
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(1))
            desc = re.sub(r'\s+', ' ', m.group(3)).strip()
            amount = parse_amount(m.group(4))
            ttype = m.group(6)
            if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            low = desc.lower()
            if any(w in low for w in ['starting balance', 'ending balance', 'total']):
                continue
            if _is_service_line(desc):
                continue
            if ttype == 'D':
                amount = -abs(amount)
            elif ttype == 'C':
                amount = abs(amount)
            cp, _ = extract_counterparty_smart(desc, account_name)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp if cp else '',
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


# ==================== JenHor Unelma ====================

def parse_jenhor_unelma_csv(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    content = read_text_with_encoding(file_content)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if len(lines) < 3:
        return []
    header = -1
    for i, l in enumerate(lines):
        if 'account' in l.lower() and 'amount' in l.lower():
            header = i
            break
    if header == -1:
        return []
    for line in lines[header + 1:]:
        parts = [p.strip() for p in line.split(';')]
        if len(parts) < 3:
            continue
        try:
            date = parse_date(parts[0])
            if not date:
                continue
            amount = parse_amount(parts[1])
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            cp = parts[2] if len(parts) > 2 else ''
            desc = ' '.join(parts[3:]) if len(parts) > 3 else ''
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name, cp, '')
            if not cp_final:
                cp_final = 'Česká spořitelna'
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final,
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


def parse_jenhor_unelma_docx(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []
    for table in doc.tables:
        flat_parts = []
        for row in table.rows:
            for cell in row.cells:
                t = cell.text.strip()
                if t:
                    flat_parts.append(t)
        flat_low = ' '.join(flat_parts).lower()
        if any(w in flat_low for w in [
            'shrnuti pohybu', 'shrnutí pohybů',
            'obraty za obdobi', 'obraty za období',
            'obraty od zacatku', 'obraty od začátku',
            'pocet polozek', 'počet položek',
            'pocet cekajicich', 'počet čekajících',
            'zakladni udaje', 'základní údaje',
            'pocatecni zustatek', 'počáteční zůstatek',
            'konecny zustatek', 'konečný zůstatek',
            'celkem prislo', 'celkem přišlo',
            'celkem odeslo', 'celkem odešlo',
            'disponibilni zustatek', 'disponibilní zůstatek',
        ]):
            continue
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            joined = ' | '.join([c for c in cells if c])
            if not joined:
                continue
            joined_low = joined.lower()
            if 'prehled pohybu' in joined_low or 'přehled pohybů' in joined_low:
                continue
            if any(w in joined_low for w in [
                'pocatecni zustatek', 'počáteční zůstatek',
                'konecny zustatek', 'konečný zůstatek',
                'celkem pripsano', 'celkem připsáno',
                'celkem odepsano', 'celkem odepsáno',
                'zaúčtováno', 'položka', 'provedeno',
                'popis', 'číslo protiúčtu',
            ]):
                continue
            date_found = None
            cleaned_cells = []
            for c in cells:
                c_s = c
                mdate = re.search(r'\b(\d{1,2}\.\d{1,2}\.\d{2,4})\b', c_s)
                if mdate and date_found is None:
                    date_found = mdate.group(1)
                    c_s = c_s.replace(mdate.group(0), ' ')
                cleaned_cells.append(c_s)
            amounts = []
            for c in cleaned_cells:
                if not c:
                    continue
                if re.fullmatch(r'\d{1,2}\.\d{1,2}\.\d{2,4}', c.strip()):
                    continue
                for mnum in re.finditer(
                    r'[-+]?\d{1,3}(?:[ \u00a0]?\d{3})*(?:[.,]\d{1,2})?', c
                ):
                    tok = mnum.group(0)
                    if re.fullmatch(r'\d{1,2}\.\d{1,2}\.\d{2,4}', tok):
                        continue
                    try:
                        v = float(tok.replace(' ', '').replace('\u00a0', ''))
                        amounts.append(v)
                    except Exception:
                        try:
                            v = float(tok.replace(' ', '').replace('\u00a0', '').replace(',', '.'))
                            amounts.append(v)
                        except Exception:
                            continue
            if not amounts:
                continue
            sign = None
            for c in cells:
                cn = c.strip().upper()
                if cn in ('D', 'DEBIT', 'DEBET', 'ДЕБЕТ'):
                    sign = -1
                    break
                if cn in ('C', 'CREDIT', 'KREDIT', 'КРЕДИТ'):
                    sign = 1
                    break
            amount = amounts[0]
            if sign == -1:
                amount = -abs(amount)
            elif sign == 1:
                amount = abs(amount)
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            desc = ' '.join([c for c in cleaned_cells if c.strip()])
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name)
            if not cp_final:
                cp_final = 'Česká spořitelna'
            result.append({
                'Дата': parse_date(date_found) if date_found else '',
                'Сумма': amount,
                'Контрагент': cp_final,
                'Наименование счета': account_name,
                'Описание': desc
            })
    if not result:
        for para in doc.paragraphs:
            t = para.text.strip()
            if not t:
                continue
            low = t.lower()
            if any(w in low for w in [
                'shrnuti pohybu', 'obraty za', 'obraty od',
                'pocet polozek', 'pocet cekajicich',
            ]):
                continue
            m = re.search(r'(\d{1,2}\.\d{1,2}\.\d{2,4})\s+(.{1,2000}?)\s+(-?\d[\d\s]*[,.]\d{2})(?!\d)', t)
            if not m:
                continue
            date = parse_date(m.group(1))
            amount = parse_amount(m.group(3))
            if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            desc = m.group(2).strip()
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name)
            if not cp_final:
                cp_final = 'Česká spořitelna'
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final,
                'Наименование счета': account_name,
                'Описание': desc
            })
    return result


def parse_jenhor_unelma_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []
    result = []
    pattern = re.compile(
        r'(\d{2}\.\d{2}\.\d{4})\s+(.{1,2000}?)\s+(-?\d[\d\s]*[,.]\d{2})(?!\d)',
        re.DOTALL
    )
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(1).strip())
            desc = re.sub(r'\s+', ' ', m.group(2)).strip()
            amount = parse_amount(m.group(3).strip())
            if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            low = desc.lower()
            if any(w in low for w in ['počáteční zůstatek', 'konečný zůstatek',
                                      'celkem připsáno', 'celkem odepsáno',
                                      'přehled pohyb']):
                continue
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name)
            if not cp_final:
                cp_final = 'Česká spořitelna'
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final,
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


# ==================== Stalkin FIO ====================

def parse_stalkin_ml2_fio(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    content = read_text_with_encoding(file_content)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if len(lines) < 2:
        return []
    header = -1
    for i, l in enumerate(lines):
        low = l.lower()
        if ('date' in low and 'volume' in low) or ('"date"' in low and '"volume"' in low):
            header = i
            break
    if header == -1:
        return []
    for line in lines[header + 1:]:
        parts = _split_line(line, ';')
        if len(parts) < 3:
            continue
        try:
            date = parse_date(parts[0])
            if not date:
                continue
            amount = parse_amount(parts[1])
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            desc = parts[5] if len(parts) > 5 and parts[5] else (parts[6] if len(parts) > 6 else '')
            cp = parts[3] if len(parts) > 3 else ''
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name, cp, '')
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


# ==================== Industra ====================

def _read_xls_with_xlrd(file_content: bytes):
    try:
        import xlrd
    except ImportError:
        return None
    try:
        wb = xlrd.open_workbook(file_contents=file_content, ignore_workbook_corruption=True)
    except Exception:
        return None
    if wb.nsheets == 0:
        return None
    sheet = wb.sheet_by_index(0)
    data = []
    for r in range(sheet.nrows):
        row = []
        for c in range(sheet.ncols):
            row.append(sheet.cell_value(r, c))
        data.append(row)
    if not data:
        return None
    return pd.DataFrame(data)


def _parse_industra_generic(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    df = None
    if _is_real_xls(file_content):
        df = _read_xls_with_xlrd(file_content)
    if df is None or df.empty:
        df = read_xlsx(file_content)
    if df is not None and not df.empty:
        header_row = -1
        for idx, row in df.iterrows():
            if idx < 60:
                rs = ' '.join([str(x) for x in row.values if pd.notna(x)]).lower()
                has_date = ('дата транзакции' in rs) or ('transaction date' in rs)
                has_debit = ('дебет' in rs) or ('debit' in rs)
                has_credit = ('кредит' in rs) or ('credit' in rs)
                if has_date and has_debit and has_credit:
                    header_row = idx
                    break
        if header_row != -1:
            hdr = df.iloc[header_row]
            ci = {}
            for i, v in enumerate(hdr.values):
                if pd.isna(v):
                    continue
                sl = str(v).strip().lower()
                if ('дата транзакции' in sl) or ('transaction date' in sl):
                    if 'date' not in ci:
                        ci['date'] = i
                elif ('получатель' in sl) or ('плательщик' in sl) or ('counterparty' in sl):
                    if 'counterparty' not in ci:
                        ci['counterparty'] = i
                elif ('информация о транзакции' in sl) or ('описание' in sl) or ('description' in sl):
                    if 'description' not in ci:
                        ci['description'] = i
                elif ('тип транзакции' in sl) or ('transaction type' in sl):
                    if 'ttype' not in ci:
                        ci['ttype'] = i
                elif (('дебет' in sl) or ('debit' in sl)) and ('кредит' not in sl) and ('credit' not in sl):
                    if 'debit' not in ci:
                        ci['debit'] = i
                elif (('кредит' in sl) or ('credit' in sl)) and ('дебет' not in sl) and ('debit' not in sl):
                    if 'credit' not in ci:
                        ci['credit'] = i
            if 'date' not in ci:
                ci['date'] = 0
            if 'debit' not in ci:
                ci['debit'] = 11
            if 'credit' not in ci:
                ci['credit'] = 12
            if 'ttype' not in ci:
                ci['ttype'] = 4
            for idx in range(header_row + 1, len(df)):
                row = df.iloc[idx]
                rv = [x for x in row.values if pd.notna(x)]
                if not rv:
                    continue
                try:
                    dstr = safe_str(row.iloc[ci['date']]) if ci['date'] < len(row) else ''
                    if not dstr:
                        continue
                    date = parse_date(dstr)
                    if not date:
                        continue
                    amount = 0.0
                    found = False
                    if 'debit' in ci and ci['debit'] < len(row):
                        dv = row.iloc[ci['debit']]
                        if pd.notna(dv) and str(dv).strip() not in ['', 'nan', '-']:
                            p = parse_amount(str(dv).strip().replace(',', '.').replace(' ', ''))
                            if p != 0.0:
                                amount = -abs(p)
                                found = True
                    if not found and 'credit' in ci and ci['credit'] < len(row):
                        cv = row.iloc[ci['credit']]
                        if pd.notna(cv) and str(cv).strip() not in ['', 'nan', '-']:
                            p = parse_amount(str(cv).strip().replace(',', '.').replace(' ', ''))
                            if p != 0.0:
                                amount = p
                                found = True
                    if not found or not _is_reasonable_amount(amount):
                        continue
                    cp = safe_str(row.iloc[ci['counterparty']]) if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
                    desc = safe_str(row.iloc[ci['description']]) if 'description' in ci and ci['description'] < len(row) else ''
                    ttype = safe_str(row.iloc[ci['ttype']]) if 'ttype' in ci and ci['ttype'] < len(row) else ''
                    if not desc and ttype:
                        desc = ttype
                    if _is_service_line(desc):
                        continue
                    cp_final, _ = extract_counterparty_smart(desc, account_name, cp, '', cp)
                    result.append({
                        'Дата': date, 'Сумма': amount,
                        'Контрагент': cp_final if cp_final else '',
                        'Наименование счета': account_name,
                        'Описание': desc
                    })
                except Exception:
                    continue
            if result:
                return result
    content = read_text_with_encoding(file_content)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if not lines:
        return result
    sample = '\n'.join(lines[:5])
    sep = ';' if sample.count(';') >= sample.count(',') else ','
    header_idx = -1
    for i, l in enumerate(lines[:60]):
        low = l.lower()
        has_date = ('дата транзакции' in low) or ('transaction date' in low)
        has_debit = ('дебет' in low) or ('debit' in low)
        has_credit = ('кредит' in low) or ('credit' in low)
        if has_date and has_debit and has_credit:
            header_idx = i
            break
    if header_idx == -1:
        return result
    hdr = _split_line(lines[header_idx], sep)
    ci = {}
    for i, h in enumerate(hdr):
        hl = h.lower()
        if ('дата транзакции' in hl) or ('transaction date' in hl):
            if 'date' not in ci:
                ci['date'] = i
        elif ('получатель' in hl) or ('плательщик' in hl) or ('counterparty' in hl):
            if 'counterparty' not in ci:
                ci['counterparty'] = i
        elif ('информация о транзакции' in hl) or ('описание' in hl) or ('description' in hl):
            if 'description' not in ci:
                ci['description'] = i
        elif ('тип транзакции' in hl) or ('transaction type' in hl):
            if 'ttype' not in ci:
                ci['ttype'] = i
        elif (('дебет' in hl) or ('debit' in hl)) and ('кредит' not in hl) and ('credit' not in hl):
            if 'debit' not in ci:
                ci['debit'] = i
        elif (('кредит' in hl) or ('credit' in hl)) and ('дебет' not in hl) and ('debit' not in hl):
            if 'credit' not in ci:
                ci['credit'] = i
    if 'date' not in ci:
        return result
    for line in lines[header_idx + 1:]:
        parts = _split_line(line, sep)
        if ci['date'] >= len(parts):
            continue
        try:
            date = parse_date(parts[ci['date']])
            if not date:
                continue
            amount = 0.0
            found = False
            if 'debit' in ci and ci['debit'] < len(parts):
                p = parse_amount(parts[ci['debit']].replace(',', '.').replace(' ', ''))
                if p != 0.0:
                    amount = -abs(p)
                    found = True
            if not found and 'credit' in ci and ci['credit'] < len(parts):
                p = parse_amount(parts[ci['credit']].replace(',', '.').replace(' ', ''))
                if p != 0.0:
                    amount = p
                    found = True
            if not found or not _is_reasonable_amount(amount):
                continue
            cp = parts[ci['counterparty']] if 'counterparty' in ci and ci['counterparty'] < len(parts) else ''
            desc = parts[ci['description']] if 'description' in ci and ci['description'] < len(parts) else ''
            ttype = parts[ci['ttype']] if 'ttype' in ci and ci['ttype'] < len(parts) else ''
            if not desc and ttype:
                desc = ttype
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name, cp, '', cp)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


def parse_industra_an14(file_content, account_name):
    return _parse_industra_generic(file_content, account_name)


def parse_industra_plavas1(file_content, account_name):
    return _parse_industra_generic(file_content, account_name)


def parse_industra_kl59(file_content, account_name):
    return _parse_industra_generic(file_content, account_name)


def parse_industra_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []

    date_re = re.compile(r'(\d{2}\.\d{2}\.\d{4})')
    amount_re = re.compile(r'(-?\d[\d\s\u00a0]*[.,]\d{2})(?!\d)')

    lines = full_text.split('\n')

    blocks = []
    current_date = None
    current_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        m = date_re.search(stripped)
        if m and (m.start() == 0 or stripped[:m.start()].strip() == ''):
            if current_date is not None:
                blocks.append((current_date, current_lines))
            current_date = m.group(1)
            rest = stripped[m.end():].strip()
            current_lines = [rest] if rest else []
        else:
            if current_date is not None:
                current_lines.append(stripped)

    if current_date is not None:
        blocks.append((current_date, current_lines))

    for date_str, block_lines in blocks:
        date = parse_date(date_str)
        if not date:
            continue

        block_text = ' '.join(block_lines)
        block_text = re.sub(r'\s+', ' ', block_text).strip()
        if not block_text:
            continue

        if _is_service_line(block_text):
            continue

        amount_matches = list(amount_re.finditer(block_text))
        if not amount_matches:
            continue
        amount = None
        for am in reversed(amount_matches):
            v = parse_amount(am.group(1))
            if v != 0.0 and _is_reasonable_amount(v):
                amount = v
                break
        if amount is None:
            continue

        head = block_text[:amount_matches[-1].start()].strip().rstrip(' ,;')

        op_type = ''
        head_clean = re.sub(r'^[^,]*?,\s*#[\w/]+,\s*', '', head)
        parts = [p.strip() for p in head_clean.split(',') if p.strip()]

        rest_parts = []
        for idx_p, p in enumerate(parts):
            if idx_p == 0 and any(w in p.lower() for w in [
                'исходящее', 'зачисление', 'проводка', 'комиссия', 'перевод',
                'мемориальн'
            ]):
                op_type = p
                continue
            if re.fullmatch(r'[A-Z]{2}\d{2}[A-Z0-9]{10,30}', p):
                continue
            if re.fullmatch(r'[A-Z]{4}[A-Z0-9]{2,5}([A-Z0-9]{3})?', p):
                continue
            if re.fullmatch(r'\d{5,}', p):
                continue
            if re.fullmatch(r'\d{8,}[\w/]*', p):
                continue
            if 'BANK' in p.upper() and len(p) < 30:
                continue
            if re.fullmatch(r'[A-Z]{2,5} [A-Z]{2,5}', p):
                continue
            rest_parts.append(p)

        cp = ''
        if rest_parts:
            first = rest_parts[0]
            if len(first) <= 80 and not any(sep in first for sep in ['.', '?', '!', '№']):
                cp = first
                rest_parts = rest_parts[1:]

        desc = ', '.join(rest_parts).strip()
        if not desc:
            desc = head_clean
        if (not desc or desc.strip() in ('', ',')) and op_type:
            desc = op_type

        if op_type.lower().startswith('комиссия') or 'комиссия за банковскую операцию' in block_text.lower():
            desc = 'Комиссия за банковскую операцию'

        low_chunk = block_text.lower()
        if 'дебет' in low_chunk and ('(d)' in low_chunk or ' d ' in low_chunk):
            amount = -abs(amount)

        cp_final, _ = extract_counterparty_smart(desc, account_name, cp, '', cp)

        result.append({
            'Дата': date,
            'Сумма': amount,
            'Контрагент': cp_final,
            'Наименование счета': account_name,
            'Описание': desc
        })

    seen = set()
    deduped = []
    for r in result:
        key = (r['Дата'], r['Сумма'], r['Контрагент'], r['Описание'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped


# ==================== Kapital bank Saida AZN ====================
# (оставляем без изменений — см. оригинал; здесь только ссылки)

def parse_kapital_saida_xlsx(file_content: bytes, account_name: str) -> List[Dict]:
    # ... (без изменений, см. оригинал)
    return []


def parse_kapital_saida_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    # ... (без изменений, см. оригинал)
    return []


def parse_kapital_saida_azn_csv(file_content: bytes, account_name: str) -> List[Dict]:
    # ... (без изменений, см. оригинал)
    return []


# ==================== MASHREQ ====================

def parse_mashreq(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    try:
        df = pd.read_excel(BytesIO(file_content), sheet_name='Account transactions Statement', header=None)
    except Exception:
        try:
            df = pd.read_excel(BytesIO(file_content), header=None)
        except Exception:
            return []
    if df.empty:
        return []
    header_row = -1
    for idx, row in df.iterrows():
        if idx < 40:
            rs = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Date' in rs and 'Description' in rs and 'Credit' in rs:
                header_row = idx
                break
    if header_row == -1:
        return []
    hdr = df.iloc[header_row]
    ci = {}
    for i, v in enumerate(hdr.values):
        if pd.isna(v):
            continue
        s = str(v).strip()
        if s == 'Date':
            ci['date'] = i
        elif 'Description' in s:
            ci['description'] = i
        elif s == 'Credit':
            ci['credit'] = i
        elif s == 'Debit':
            ci['debit'] = i
    if 'date' not in ci:
        ci['date'] = 0
    if 'credit' not in ci:
        ci['credit'] = 4
    if 'debit' not in ci:
        ci['debit'] = 5
    for idx in range(header_row + 1, len(df)):
        row = df.iloc[idx]
        rv = [x for x in row.values if pd.notna(x)]
        if not rv:
            continue
        try:
            dstr = safe_str(row.iloc[ci['date']]) if ci['date'] < len(row) else ''
            if not dstr:
                continue
            date = parse_date(dstr)
            if not date:
                continue
            amount = 0.0
            found = False
            if 'credit' in ci and ci['credit'] < len(row):
                cv = row.iloc[ci['credit']]
                if pd.notna(cv) and str(cv).strip() not in ['', 'nan', '-']:
                    p = parse_amount(str(cv).strip().replace(',', '').replace(' ', ''))
                    if p != 0.0:
                        amount = p
                        found = True
            if not found and 'debit' in ci and ci['debit'] < len(row):
                dv = row.iloc[ci['debit']]
                if pd.notna(dv) and str(dv).strip() not in ['', 'nan', '-']:
                    p = parse_amount(str(dv).strip().replace(',', '').replace(' ', ''))
                    if p != 0.0:
                        amount = -abs(p)
                        found = True
            if not found or not _is_reasonable_amount(amount):
                continue
            desc = safe_str(row.iloc[ci['description']]) if 'description' in ci and ci['description'] < len(row) else ''
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


def parse_mashreq_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    tables = pdf_all_tables(file_content)
    for table in tables:
        for row in table:
            if len(row) < 6:
                continue
            try:
                date = parse_date(row[0])
                if not date:
                    continue
                desc = row[3] if len(row) > 3 else ''
                credit = parse_amount(row[4]) if len(row) > 4 else 0.0
                debit = parse_amount(row[5]) if len(row) > 5 else 0.0
                amount = 0.0
                if credit != 0.0:
                    amount = credit
                elif debit != 0.0:
                    amount = -abs(debit)
                else:
                    continue
                if not _is_reasonable_amount(amount):
                    continue
                if _is_service_line(desc):
                    continue
                cp_final, _ = extract_counterparty_smart(desc, account_name)
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp_final if cp_final else '',
                    'Наименование счета': account_name,
                    'Описание': desc
                })
            except Exception:
                continue
    return result


# ==================== MKB (Budapest) ====================
# (оставляем без изменений — см. оригинал)

def _read_mkb_dataframe(file_content: bytes):
    df = None
    if _is_real_xls(file_content):
        try:
            import xlrd
            try:
                wb = xlrd.open_workbook(file_contents=file_content, ignore_workbook_corruption=True)
                sheet = wb.sheet_by_index(0)
                data = []
                for r in range(sheet.nrows):
                    data.append([sheet.cell_value(r, c) for c in range(sheet.ncols)])
                df = pd.DataFrame(data)
            except TypeError:
                df = pd.read_excel(BytesIO(file_content), header=None, engine='xlrd')
        except Exception:
            df = None
        if df is None or df.empty:
            try:
                df = pd.read_excel(BytesIO(file_content), header=None, engine='openpyxl')
            except Exception:
                df = None
        if df is None or df.empty:
            try:
                tables = pd.read_html(BytesIO(file_content))
                if tables:
                    df = tables[0]
            except Exception:
                df = None
    elif _is_real_xlsx(file_content):
        try:
            df = pd.read_excel(BytesIO(file_content), header=None, engine='openpyxl')
        except Exception:
            df = None
        if df is None or df.empty:
            try:
                tables = pd.read_html(BytesIO(file_content))
                if tables:
                    df = tables[0]
            except Exception:
                df = None
    return df


def _parse_mkb_any(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    df = _read_mkb_dataframe(file_content)

    if df is not None and not df.empty:
        header_row = -1
        for idx, row in df.iterrows():
            if idx < 30:
                rs = ' '.join([str(x) for x in row.values if pd.notna(x)])
                rsl = rs.lower()
                has_sorsz = ('sorszám' in rsl) or ('sorszam' in rsl)
                has_ert = ('értéknap' in rsl) or ('erteknap' in rsl)
                has_ossz = ('összeg' in rsl) or ('osszeg' in rsl)
                if has_sorsz and has_ert:
                    header_row = idx
                    break
                if has_ert and has_ossz:
                    header_row = idx
                    break
        if header_row != -1:
            hdr = df.iloc[header_row]
            ci = {}
            for i, v in enumerate(hdr.values):
                if pd.isna(v):
                    continue
                s = str(v).strip()
                sl = s.lower()
                if ('értéknap' in sl) or ('erteknap' in sl):
                    if 'date' not in ci:
                        ci['date'] = i
                elif ('összeg' in sl) or ('osszeg' in sl):
                    if 'amount' not in ci:
                        ci['amount'] = i
                elif ('közlemény' in sl) or ('kozlemeny' in sl):
                    if 'description' not in ci:
                        ci['description'] = i
                elif ('kedvezményezett' in sl) and ('neve' in sl):
                    if 'counterparty' not in ci:
                        ci['counterparty'] = i
                elif ('tranzakció típusa' in sl) or ('tranzakci' in sl and 'típusa' in sl):
                    if 'type' not in ci:
                        ci['type'] = i
                elif ('terhelés' in sl) or ('terheles' in sl):
                    if 'debit' not in ci:
                        ci['debit'] = i
                elif ('jóváírás' in sl) or ('jovairas' in sl):
                    if 'credit' not in ci:
                        ci['credit'] = i
            if 'date' not in ci:
                ci['date'] = 1
            if 'amount' not in ci and 'credit' not in ci and 'debit' not in ci:
                ci['amount'] = 9
            if 'description' not in ci:
                ci['description'] = 11
            if 'counterparty' not in ci:
                ci['counterparty'] = 4
            if 'type' not in ci:
                ci['type'] = 2
            for idx in range(header_row + 1, len(df)):
                row = df.iloc[idx]
                rv = [x for x in row.values if pd.notna(x)]
                if not rv:
                    continue
                try:
                    dstr = safe_str(row.iloc[ci['date']]) if ci['date'] < len(row) else ''
                    if not dstr:
                        continue
                    date = parse_date(dstr)
                    if not date:
                        continue
                    amount = 0.0
                    if 'amount' in ci and ci['amount'] < len(row):
                        amount = parse_amount(row.iloc[ci['amount']])
                    if amount == 0.0 and ('credit' in ci or 'debit' in ci):
                        cr = parse_amount(row.iloc[ci['credit']]) if ('credit' in ci and ci['credit'] < len(row)) else 0.0
                        db = parse_amount(row.iloc[ci['debit']]) if ('debit' in ci and ci['debit'] < len(row)) else 0.0
                        if cr or db:
                            amount = abs(cr) - abs(db)
                    if amount == 0.0 or not _is_reasonable_amount(amount):
                        continue
                    desc = safe_str(row.iloc[ci['description']]) if 'description' in ci and ci['description'] < len(row) else ''
                    cp = safe_str(row.iloc[ci['counterparty']]) if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
                    ttype = safe_str(row.iloc[ci['type']]) if 'type' in ci and ci['type'] < len(row) else ''
                    if cp in ['N/A', 'n/a']:
                        cp = ''
                    if _is_service_line(desc):
                        continue
                    cp_final, _ = extract_counterparty_smart(desc, account_name, cp, '')
                    result.append({
                        'Дата': date, 'Сумма': amount,
                        'Контрагент': cp_final if cp_final else '',
                        'Наименование счета': account_name,
                        'Описание': (f"{ttype} | {desc}" if ttype else desc)
                    })
                except Exception:
                    continue
            if result:
                return result

    content = read_text_with_encoding(file_content)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if not lines:
        return result
    sample = '\n'.join(lines[:5])
    sep = ';' if sample.count(';') >= sample.count(',') else ','
    header_line_idx = -1
    for i, l in enumerate(lines):
        low = l.lower()
        has_sorsz = ('sorszám' in low) or ('sorszam' in low)
        has_ert = ('értéknap' in low) or ('erteknap' in low)
        if has_sorsz and has_ert:
            header_line_idx = i
            break
        if has_ert and (('összeg' in low) or ('osszeg' in low)):
            header_line_idx = i
            break
    if header_line_idx == -1:
        return result
    hdr = _split_line(lines[header_line_idx], sep)
    if len(hdr) < 3:
        return result

    def find_col(patterns):
        for i, h in enumerate(hdr):
            hl = h.lower()
            if any(p in hl for p in patterns):
                return i
        return -1

    date_idx = find_col(['értéknap', 'erteknap'])
    amount_idx = find_col(['összeg', 'osszeg'])
    desc_idx = find_col(['közlemény', 'kozlemeny'])
    cp_idx = find_col(['kedvezményezett'])
    type_idx = find_col(['tranzakció típusa', 'tranzakci'])
    debit_idx = find_col(['terhelés', 'terheles'])
    credit_idx = find_col(['jóváírás', 'jovairas'])
    if date_idx == -1:
        return result
    if amount_idx == -1 and (debit_idx == -1 and credit_idx == -1):
        return result
    for line in lines[header_line_idx + 1:]:
        parts = _split_line(line, sep)
        if date_idx >= len(parts):
            continue
        try:
            date = parse_date(parts[date_idx])
            if not date:
                continue
            amount = 0.0
            if amount_idx >= 0 and amount_idx < len(parts):
                amount = parse_amount(parts[amount_idx])
            if amount == 0.0 and (debit_idx >= 0 or credit_idx >= 0):
                cr = parse_amount(parts[credit_idx]) if (credit_idx >= 0 and credit_idx < len(parts)) else 0.0
                db = parse_amount(parts[debit_idx]) if (debit_idx >= 0 and debit_idx < len(parts)) else 0.0
                if cr or db:
                    amount = abs(cr) - abs(db)
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            desc = parts[desc_idx] if 0 <= desc_idx < len(parts) else ''
            cp = parts[cp_idx] if 0 <= cp_idx < len(parts) else ''
            ttype = parts[type_idx] if 0 <= type_idx < len(parts) else ''
            if cp in ['N/A', 'n/a']:
                cp = ''
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name, cp, '')
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': (f"{ttype} | {desc}" if ttype else desc)
            })
        except Exception:
            continue
    return result


def parse_budapest_eur_mkb(file_content: bytes, account_name: str) -> List[Dict]:
    return _parse_mkb_any(file_content, account_name)


def parse_budapest_huf_mkb(file_content: bytes, account_name: str) -> List[Dict]:
    return _parse_mkb_any(file_content, account_name)


def parse_mkb_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    tables = pdf_all_tables(file_content)
    for table in tables:
        header_idx = -1
        for i, row in enumerate(table):
            joined = ' '.join(row).lower()
            if 'sorsz' in joined and ('rt' in joined and 'knap' in joined):
                header_idx = i
                break
        if header_idx == -1:
            continue
        hdr = table[header_idx]
        ci = {}
        for i, h in enumerate(hdr):
            hl = h.lower()
            if 'értéknap' in hl or ('rt' in hl and 'knap' in hl):
                ci['date'] = i
            elif 'összeg' in hl or 'sszeg' in hl:
                ci['amount'] = i
            elif 'közlemény' in hl or 'kzlem' in hl:
                ci['description'] = i
            elif 'kedvezményezett' in hl and 'neve' in hl and 'counterparty' not in ci:
                ci['counterparty'] = i
        for row in table[header_idx + 1:]:
            try:
                date = parse_date(row[ci.get('date', 1)] if ci.get('date', 1) < len(row) else '')
                if not date:
                    continue
                amount = parse_amount(row[ci.get('amount', 9)] if ci.get('amount', 9) < len(row) else '')
                if amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                desc = row[ci.get('description', 11)] if ci.get('description', 11) < len(row) else ''
                cp = row[ci.get('counterparty', 0)] if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
                if _is_service_line(desc):
                    continue
                cp_final, _ = extract_counterparty_smart(desc, account_name, cp, '')
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp_final if cp_final else '',
                    'Наименование счета': account_name,
                    'Описание': desc
                })
            except Exception:
                continue
    return result
# ==================== UniCredit ====================

def parse_unicredit_generic(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    content = read_text_with_encoding(file_content)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if len(lines) < 3:
        return []
    header = -1
    for i, l in enumerate(lines):
        if 'From Account' in l and 'Amount' in l and 'Booking Date' in l:
            header = i
            break
    if header == -1:
        return []
    hdr_parts = [p.strip() for p in lines[header].split(';')]
    ci = {}
    desc_indices = []
    for i, h in enumerate(hdr_parts):
        hc = h.strip()
        if hc == 'Amount' and 'amount' not in ci:
            ci['amount'] = i
        elif hc == 'Booking Date' and 'date' not in ci:
            ci['date'] = i
        elif hc == 'Transaction Details':
            desc_indices.append(i)
        elif hc == 'Name' and 'counterparty' not in ci:
            ci['counterparty'] = i
    if 'amount' not in ci:
        ci['amount'] = 1
    if 'date' not in ci:
        ci['date'] = 3
    if 'counterparty' not in ci:
        ci['counterparty'] = 9
    for line in lines[header + 1:]:
        parts = [p.strip() for p in line.split(';')]
        while parts and parts[-1] == '':
            parts.pop()
        if len(parts) < 3:
            continue
        try:
            amount = parse_amount(parts[ci['amount']] if ci['amount'] < len(parts) else '')
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            date = parse_date(parts[ci['date']] if ci['date'] < len(parts) else '')
            if not date:
                continue
            cp = parts[ci['counterparty']].strip() if ci['counterparty'] < len(parts) else ''
            desc_parts = []
            for di in desc_indices:
                if di < len(parts):
                    v = parts[di].strip()
                    if v and v != 'nan':
                        desc_parts.append(v)
            desc = ' '.join(desc_parts).strip()
            if not desc:
                for idx in range(len(parts) - 1, -1, -1):
                    if idx in (ci['amount'], ci['date'], ci['counterparty']):
                        continue
                    if idx in desc_indices:
                        continue
                    v = parts[idx].strip()
                    if v and v != 'nan' and len(v) > 2 and not re.match(r'^[\d.,\-]+$', v) and not re.match(r'^\d{4}-\d{2}-\d{2}$', v):
                        desc = v
                        break
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name, cp, '', cp)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


def parse_unicredit_b1(file_content, account_name):
    return parse_unicredit_generic(file_content, account_name)


def parse_garpiz_unicredit(file_content, account_name):
    return parse_unicredit_generic(file_content, account_name)


def parse_garpiz_pernink(file_content, account_name):
    return parse_unicredit_generic(file_content, account_name)


def parse_koruna_unicredit(file_content, account_name):
    return parse_unicredit_generic(file_content, account_name)


def parse_twohills_unicredit(file_content, account_name):
    return parse_unicredit_generic(file_content, account_name)


# ---------- ГЛАВНОЕ ИСПРАВЛЕНИЕ: UniCredit PDF ----------

def parse_unicredit_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Парсер PDF UniCredit Bank (ČR/SR).
    Формат выписки:
        Počáteční zůstatek                         100.001,84
        Datum      Valuta    Transakce       Příjmy  Výdaje
        29.06.2026          ÚROK                16,56
                            bonusový úrok za 05/26
        30.06.2026          KREDITNÍ ÚROK       18,50
                            Hrubý úrok za období 01.06.26 - 30.06.26
        30.06.2026          Konečný zůstatek            100.036,90
    """
    result = []
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []

    lines = full_text.split('\n')

    # Ищем начало таблицы операций
    header_idx = -1
    for i, l in enumerate(lines):
        low = l.lower()
        if 'transakce' in low and ('příjmy' in low or 'prijmy' in low) and 'výdaje' in low:
            header_idx = i
            break
        if 'transakce' in low and 'příjmy' in low:
            header_idx = i
            break

    # Если нашли заголовок — парсим построчно
    if header_idx != -1:
        # Регулярка для строки-начала операции: дата + описание + (опционально сумма)
        date_line_re = re.compile(
            r'^\s*(\d{2}\.\d{2}\.\d{4})\s+'
            r'(?:(\d{2}\.\d{2}\.\d{4})\s+)?'
            r'(.+?)\s*$'
        )
        # Ищем суммы в конце строки (последние 1-2 числа)
        amount_at_end_re = re.compile(
            r'^(.*?)\s+(-?[\d\s\u00a0]+[.,]\d{2})\s*$'
        )

        i = header_idx + 1
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # Пропускаем шапку
            if re.match(r'^datum\s+valuta', line, re.IGNORECASE):
                i += 1
                continue

            # Конец таблицы
            if _is_service_line(line):
                # Это может быть "Konečný zůstatek" — стоп
                if 'konečný' in line.lower() or 'konecny' in line.lower():
                    break
                i += 1
                continue

            m = date_line_re.match(line)
            if not m:
                i += 1
                continue

            date = parse_date(m.group(1))
            if not date:
                i += 1
                continue

            rest = m.group(3).strip()
            # Ищем сумму в конце rest
            amount = 0.0
            desc = rest
            am = amount_at_end_re.match(rest)
            if am:
                desc = am.group(1).strip()
                amount = parse_amount(am.group(2))

            # Собираем многострочное описание до следующей даты/конца
            block_desc_parts = [desc] if desc else []
            j = i + 1
            while j < len(lines):
                nl = lines[j].strip()
                if not nl:
                    j += 1
                    continue
                # Если это дата — прерываем
                if date_line_re.match(nl):
                    break
                if _is_service_line(nl):
                    if 'konečný' in nl.lower() or 'konecny' in nl.lower():
                        j += 1
                        break
                    j += 1
                    continue
                # Пробуем найти сумму в этой строке
                am2 = amount_at_end_re.match(nl)
                if am2 and amount == 0.0:
                    amount = parse_amount(am2.group(2))
                    tail = am2.group(1).strip()
                    if tail:
                        block_desc_parts.append(tail)
                else:
                    block_desc_parts.append(nl)
                j += 1

            desc_full = ' '.join(block_desc_parts).strip()
            desc_full = re.sub(r'\s+', ' ', desc_full)

            # Если сумма не найдена — возможно, она в конце desc_full
            if amount == 0.0:
                am3 = amount_at_end_re.match(desc_full)
                if am3:
                    desc_full = am3.group(1).strip()
                    amount = parse_amount(am3.group(2))

            if amount == 0.0 or not _is_reasonable_amount(amount):
                i = j
                continue

            if _is_service_line(desc_full):
                i = j
                continue
            # Отсеиваем "Konečný zůstatek" и подобное
            if 'zustatek' in desc_full.lower() or 'zůstatek' in desc_full.lower():
                i = j
                continue

            # Определяем знак: если в исходной строке был минус перед суммой — расход
            # В UniCredit "Příjmy" и "Výdaje" — разные колонки. Смотрим позицию.
            # Если сумма стоит ближе к концу (после "Výdaje") — расход.
            # Простое правило: если перед числом был "-" — расход.
            # Проверим оригинальную строку:
            raw_line = lines[i]
            if re.search(r'-\s*[\d\s\u00a0]+[.,]\d{2}', raw_line):
                amount = -abs(amount)

            cp_final, _ = extract_counterparty_smart(desc_full, account_name)
            if not cp_final:
                # Из имени банка
                cp_final = 'UniCredit Bank'

            result.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': cp_final,
                'Наименование счета': account_name,
                'Описание': desc_full
            })

            i = j

    # Fallback: если по заголовку не получилось, пробуем через таблицы pdfplumber
    if not result:
        tables = pdf_all_tables(file_content)
        for table in tables:
            header_row_idx = -1
            for i, row in enumerate(table):
                joined = ' '.join([str(c or '') for c in row]).lower()
                if 'datum' in joined and 'transakce' in joined:
                    header_row_idx = i
                    break
            if header_row_idx == -1:
                continue
            for row in table[header_row_idx + 1:]:
                try:
                    cells = [str(c or '').strip() for c in row]
                    if not any(cells):
                        continue
                    joined = ' '.join(cells)
                    if _is_service_line(joined):
                        continue
                    date = parse_date(cells[0]) if cells else ''
                    if not date:
                        continue
                    # Ищем сумму и описание
                    amounts = []
                    desc_parts = []
                    for c in cells[1:]:
                        if not c:
                            continue
                        if re.fullmatch(r'-?[\d\s\u00a0]+[.,]\d{2}', c.strip()):
                            amounts.append(c.strip())
                        else:
                            desc_parts.append(c)
                    if not amounts:
                        continue
                    amount = parse_amount(amounts[-1])
                    if amount == 0.0:
                        continue
                    desc = ' '.join(desc_parts).strip()
                    if _is_service_line(desc):
                        continue
                    cp_final, _ = extract_counterparty_smart(desc, account_name)
                    if not cp_final:
                        cp_final = 'UniCredit Bank'
                    result.append({
                        'Дата': date, 'Сумма': amount,
                        'Контрагент': cp_final,
                        'Наименование счета': account_name,
                        'Описание': desc
                    })
                except Exception:
                    continue

    # Дедупликация
    seen = set()
    deduped = []
    for r in result:
        key = (r['Дата'], round(r['Сумма'], 2), r['Описание'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped


# ==================== WIO ====================

def parse_wio_business(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    content = read_text_with_encoding(file_content)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if len(lines) < 3:
        return []
    header = -1
    for i, l in enumerate(lines):
        if 'Account name' in l and 'Transaction type' in l:
            header = i
            break
    if header == -1:
        return []
    hdr_parts = [p.strip().strip('"') for p in lines[header].split(',')]
    ci = {}
    for i, h in enumerate(hdr_parts):
        if h == 'Amount':
            ci['amount'] = i
        elif h == 'Date':
            ci['date'] = i
        elif h == 'Description':
            ci['description'] = i
        elif h == 'Notes':
            ci['notes'] = i
    if 'amount' not in ci:
        ci['amount'] = 10
    if 'date' not in ci:
        ci['date'] = 7
    if 'description' not in ci:
        ci['description'] = 9
    for line in lines[header + 1:]:
        parts = _split_line(line, ',')
        if len(parts) < 3:
            continue
        try:
            date = parse_date(parts[ci['date']] if ci['date'] < len(parts) else '')
            if not date:
                continue
            amount = parse_amount(parts[ci['amount']] if ci['amount'] < len(parts) else '')
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            desc = parts[ci['description']] if ci['description'] < len(parts) else ''
            notes = parts[ci['notes']] if 'notes' in ci and ci['notes'] < len(parts) else ''
            full = desc
            if notes and notes != 'N/A' and notes:
                full = f"{desc} | {notes}" if desc else notes
            if _is_service_line(full):
                continue
            cp_final, _ = extract_counterparty_smart(full, account_name)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': full
            })
        except Exception:
            continue
    return result


def parse_wio_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    tables = pdf_all_tables(file_content)
    for table in tables:
        for row in table:
            if len(row) < 4:
                continue
            try:
                date = parse_date(row[3])
                if not date:
                    continue
                amount = parse_amount(row[1] if len(row) > 1 else '')
                if amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                desc = row[5] if len(row) > 5 else ''
                if _is_service_line(desc):
                    continue
                cp_final, _ = extract_counterparty_smart(desc, account_name)
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp_final if cp_final else '',
                    'Наименование счета': account_name,
                    'Описание': desc
                })
            except Exception:
                continue
    return result


# ==================== Saida N26 ====================

def parse_saida_n26_csv(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    content = read_text_with_encoding(file_content)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if len(lines) < 3:
        return []
    header = -1
    for i, l in enumerate(lines):
        if 'date' in l.lower() and 'amount' in l.lower():
            header = i
            break
    if header == -1:
        return []
    for line in lines[header + 1:]:
        parts = [p.strip() for p in line.split(';')]
        if len(parts) < 3:
            continue
        try:
            date = parse_date(parts[0])
            if not date:
                continue
            amount = parse_amount(parts[1].replace(',', '.'))
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            desc = ' '.join(parts[2:])
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


# ---------- ГЛАВНОЕ ИСПРАВЛЕНИЕ: N26 PDF ----------

def parse_n26_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Парсер PDF N26 (немецкий/испанский формат).
    Пример строк:
        N26 Metal Membership   Fecha de valor 27.06.2026   27.06.2026   -16,90€
        Algo                   01.06.2026  02.06.2026   -5,00€
    """
    result = []
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []

    # Заменяем (cid:XX) на пробел, если ещё остались
    full_text = _CID_PATTERN.sub(' ', full_text)
    full_text = re.sub(r'[ \t]+', ' ', full_text)

    lines = full_text.split('\n')
    lines = [l.strip() for l in lines if l.strip()]

    # Регулярка: описание + (опционально "Fecha de valor DD.MM.YYYY") + DD.MM.YYYY [+ DD.MM.YYYY] + сумма€
    # Различные варианты порядка
    patterns = [
        # desc  Fecha de valor DD.MM.YYYY  DD.MM.YYYY  amount€
        re.compile(
            r'^(.*?)\s+Fecha\s+de\s+valor\s+(\d{2}\.\d{2}\.\d{4})\s+'
            r'(\d{2}\.\d{2}\.\d{4})\s+(-?[\d.,]+)\s*€',
            re.IGNORECASE
        ),
        # desc  DD.MM.YYYY  DD.MM.YYYY  amount€
        re.compile(
            r'^(.*?)\s+(\d{2}\.\d{2}\.\d{4})\s+(\d{2}\.\d{2}\.\d{4})\s+'
            r'(-?[\d.,]+)\s*€'
        ),
        # desc  DD.MM.YYYY  amount€
        re.compile(
            r'^(.*?)\s+(\d{2}\.\d{2}\.\d{4})\s+(-?[\d.,]+)\s*€'
        ),
    ]

    for line in lines:
        low = line.lower()

        # Пропускаем служебные
        if any(w in low for w in [
            'saldo previo', 'nuevo saldo', 'transacciones salientes',
            'transacciones entrantes', 'descripción', 'fecha de reserva',
            'cantidad', 'emitido en', 'iban:', 'bic:', 'n26 metal',
            'saida mammadbayli', 'malaga', 'benahavis',
            'hasta', 'nº', 'n°'
        ]):
            # Но строка "N26 Metal Membership 27.06.2026 27.06.2026 -16,90€" —
            # это транзакция. Проверим, есть ли в ней сумма€.
            if '€' not in line:
                continue
            # Если есть сумма и даты — пропускаем дальше в обработку
            if not re.search(r'\d{2}\.\d{2}\.\d{4}', line):
                continue
            # Уберём "N26 Metal Membership" из описания, но оставим как операцию
            # (это реальная операция комиссии)

        matched = False
        for pat in patterns:
            m = pat.match(line)
            if not m:
                continue
            groups = m.groups()
            desc = groups[0].strip()
            # Определяем дату и сумму
            if len(groups) == 4:
                date = parse_date(groups[1])
                amount = parse_amount(groups[3])
            elif len(groups) == 3:
                date = parse_date(groups[1])
                amount = parse_amount(groups[2])
            else:
                continue

            if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                continue

            # Отрицательные суммы уже учтены parse_amount
            # N26: "Metal Membership" — комиссия (расход). Если сумма без знака,
            # но в описании "membership" — делаем расход.
            if 'membership' in desc.lower() and amount > 0:
                amount = -abs(amount)

            if _is_service_line(desc):
                continue

            cp_final, _ = extract_counterparty_smart(desc, account_name)
            if not cp_final:
                cp_final = 'N26'

            result.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': cp_final,
                'Наименование счета': account_name,
                'Описание': desc if desc else 'N26'
            })
            matched = True
            break

        if matched:
            continue

    # Fallback: разбор по одной строке с датами
    if not result:
        for line in lines:
            # Ищем строки с €
            if '€' not in line:
                continue
            low = line.lower()
            if any(w in low for w in ['saldo', 'total', 'nuevo', 'previo']):
                continue
            dates = re.findall(r'\d{2}\.\d{2}\.\d{4}', line)
            if not dates:
                continue
            date = parse_date(dates[0])
            am = re.search(r'(-?[\d.,]+)\s*€', line)
            if not am:
                continue
            amount = parse_amount(am.group(1))
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            desc = line[:line.find(dates[0])].strip()
            desc = re.sub(r'^[\s\-\|]+', '', desc)
            if 'membership' in desc.lower() and amount > 0:
                amount = -abs(amount)
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name)
            if not cp_final:
                cp_final = 'N26'
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final,
                'Наименование счета': account_name,
                'Описание': desc if desc else 'N26'
            })

    # Дедупликация
    seen = set()
    deduped = []
    for r in result:
        key = (r['Дата'], round(r['Сумма'], 2), r['Описание'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped


def parse_n26_docx(file_content: bytes, account_name: str) -> List[Dict]:
    full_text = docx_all_text(file_content)
    if not full_text:
        return []
    result = []
    pattern = re.compile(
        r'([A-Za-z0-9][^\n]{3,500}?)'
        r'(?:Fecha de valor\s+)?'
        r'(\d{2}\.\d{2}\.\d{4})'
        r'\s+'
        r'(\d{2}\.\d{2}\.\d{4})?'
        r'\s+'
        r'(-?\d[\d\s]*[.,]\d{2})\s*€',
        re.MULTILINE
    )
    for m in pattern.finditer(full_text):
        try:
            desc = re.sub(r'\s+', ' ', m.group(1)).strip()
            date = parse_date(m.group(2))
            amount = parse_amount(m.group(4))
            if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            low = desc.lower()
            if any(w in low for w in ['saldo previo', 'nuevo saldo', 'transacciones']):
                continue
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name)
            if not cp_final:
                cp_final = 'N26'
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final,
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


# ==================== Saida Wise ====================

def parse_saida_wise(file_content, account_name):
    return parse_saida_n26_csv(file_content, account_name)


def parse_saida_wise_xlsx(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    df = read_xlsx(file_content, sheet_name='All transactions')
    if df is None or df.empty:
        df = read_xlsx(file_content)
    if df is None or df.empty:
        return []
    hdr = df.iloc[0]
    ci = {}
    for i, v in enumerate(hdr.values):
        if pd.isna(v):
            continue
        s = str(v).strip().lower()
        if s == 'дата' or s == 'date':
            if 'date' not in ci:
                ci['date'] = i
        elif 'дата и время' in s:
            if 'datetime' not in ci:
                ci['datetime'] = i
        elif s == 'сумма' or s == 'amount':
            if 'amount' not in ci:
                ci['amount'] = i
        elif s == 'описание':
            if 'description' not in ci:
                ci['description'] = i
        elif s == 'пояснение к переводу':
            if 'note' not in ci:
                ci['note'] = i
        elif s == 'имя получателя':
            if 'recipient' not in ci:
                ci['recipient'] = i
        elif s == 'имя плательщика':
            if 'payer' not in ci:
                ci['payer'] = i
        elif s == 'тип транзакции':
            if 'type' not in ci:
                ci['type'] = i
    if 'amount' not in ci:
        ci['amount'] = 3
    if 'date' not in ci and 'datetime' not in ci:
        ci['date'] = 1
    elif 'date' not in ci:
        ci['date'] = ci['datetime']
    if 'description' not in ci:
        ci['description'] = 5
    if 'type' not in ci:
        ci['type'] = 21
    for idx in range(1, len(df)):
        row = df.iloc[idx]
        try:
            dstr = safe_str(row.iloc[ci['date']]) if ci['date'] < len(row) else ''
            if not dstr:
                continue
            date = parse_date(dstr)
            if not date:
                continue
            av = row.iloc[ci['amount']] if ci['amount'] < len(row) else None
            if pd.isna(av) or str(av).strip() in ['', 'nan']:
                continue
            amount = parse_amount(str(av).strip().replace(',', '.'))
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            desc = safe_str(row.iloc[ci['description']]) if 'description' in ci and ci['description'] < len(row) else ''
            note = safe_str(row.iloc[ci['note']]) if 'note' in ci and ci['note'] < len(row) else ''
            recipient = safe_str(row.iloc[ci['recipient']]) if 'recipient' in ci and ci['recipient'] < len(row) else ''
            payer = safe_str(row.iloc[ci['payer']]) if 'payer' in ci and ci['payer'] < len(row) else ''
            full_desc = desc
            if note and note != 'nan':
                full_desc = f"{desc} | {note}" if desc else note
            if _is_service_line(full_desc):
                continue
            cp_final, _ = extract_counterparty_smart(full_desc, account_name, payer, recipient)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': full_desc
            })
        except Exception:
            continue
    return result


# ---------- ГЛАВНОЕ ИСПРАВЛЕНИЕ: Wise PDF ----------

def parse_wise_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Парсер PDF Wise (EUR-баланс).
    Структура:
        Описание | Входящие | Исходящие | Сумма
        Транзакция по карте на сумму 588,00 CZK, списана Hpa Karlovy Vary Karlovy Vary -24,36 1 357,37
        30 июня 2026 г. Карта, заканчивающаяся на 6764 Saida Mammadbayli Транзакция: CARD-3991433552
        Отправлено Alesia Piskun -1 500,00 1 754,07
        24 июня 2026 г. Транзакция: TRANSFER-2209448948
        Получено от Baltic Solutions с пояснением "Loan repayment" 2 000,00 3 254,07
        24 июня 2026 г. Транзакция: TRANSFER-2209440721 Пояснение: Loan repayment
    """
    result = []
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []

    # Заменяем (cid:XX), если остались
    full_text = _CID_PATTERN.sub(' ', full_text)
    full_text = re.sub(r'[ \t]+', ' ', full_text)

    # Пытаемся извлечь таблицы через pdfplumber
    tables = pdf_all_tables(file_content)

    # Сначала попробуем через таблицы
    for table in tables:
        for row in table:
            if not row or len(row) < 2:
                continue
            cells = [str(c or '').strip() for c in row]
            joined = ' | '.join(cells)
            if not joined.strip():
                continue
            if _is_service_line(joined):
                continue

            # Описание — первая ячейка; сумма — последняя числовая
            desc = cells[0] if cells else ''
            # Ищем сумму: обычно предпоследняя или последняя ячейка
            amount = 0.0
            for c in reversed(cells):
                if not c:
                    continue
                if re.fullmatch(r'-?[\d\s\u00a0]+[.,]\d{2}', c.strip()):
                    amount = parse_amount(c)
                    if amount != 0.0:
                        break
            if amount == 0.0:
                continue
            if not _is_reasonable_amount(amount):
                continue

            # Дата внутри desc: "30 июня 2026 г." или "Транзакция по карте ... 30 июня 2026 г."
            date = ''
            m = re.search(
                r'(\d{1,2}\s+[A-Za-zА-Яа-яЁё]+\.?\s+\d{4}\s*г?\.?)',
                desc
            )
            if m:
                date = parse_date(m.group(1))

            # Ищем дату в следующих строках
            if not date:
                for c in cells:
                    dm = re.search(
                        r'(\d{1,2}\s+[A-Za-zА-Яа-яЁё]+\.?\s+\d{4}\s*г?\.?)',
                        c
                    )
                    if dm:
                        date = parse_date(dm.group(1))
                        if date:
                            break

            if not date:
                continue

            # Очищаем desc от даты и "Транзакция: CARD-..."
            desc_clean = re.sub(
                r'\d{1,2}\s+[A-Za-zА-Яа-яЁё]+\.?\s+\d{4}\s*г?\.?',
                '', desc
            )
            desc_clean = re.sub(r'Транзакция:\s*[A-Z0-9\-]+', '', desc_clean)
            desc_clean = re.sub(r'Карта,\s*заканчивающаяся\s+на\s+\d+', '', desc_clean)
            desc_clean = re.sub(r'Пояснение:\s*[^\|]+', '', desc_clean)
            desc_clean = re.sub(r'\s+', ' ', desc_clean).strip(' .,;:-|')

            if not desc_clean:
                desc_clean = desc

            cp_final, _ = extract_counterparty_smart(desc_clean, account_name)
            if not cp_final:
                cp_final = 'Wise'

            result.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': cp_final,
                'Наименование счета': account_name,
                'Описание': desc_clean
            })

    if result:
        # Дедупликация
        seen = set()
        deduped = []
        for r in result:
            key = (r['Дата'], round(r['Сумма'], 2), r['Описание'])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(r)
        return deduped

    # Fallback: текстовый режим
    lines = full_text.split('\n')
    lines = [l.rstrip() for l in lines if l.strip()]

    # Регулярка: описание + [-]<сумма1> [<баланс>]  или  описание + <сумма1>
    # Ищем строки, оканчивающиеся числом с 2 знаками после запятой
    amount_at_end_re = re.compile(
        r'^(.*?)\s+(-?[\d\s\u00a0]+[.,]\d{2})\s*$'
    )

    current_date = None

    for i, line in enumerate(lines):
        low = line.lower()
        # Строка может содержать дату
        dm = re.search(
            r'(\d{1,2}\s+[A-Za-zА-Яа-яЁё]+\.?\s+\d{4}\s*г?\.?)',
            line
        )
        if dm:
            date_parsed = parse_date(dm.group(1))
            if date_parsed:
                # Если строка почти пустая — это только дата, сохраним
                rest = line.replace(dm.group(0), '').strip()
                if not rest:
                    current_date = date_parsed
                    continue
                else:
                    current_date = date_parsed
                    # Иначе — продолжаем обработку строки как операции

        # Пропускаем служебные
        if any(w in low for w in [
            'описание входящие исходящие сумма',
            'eur на', 'создано', 'владелец счета',
            'wise — это коммерческое', 'нужна помощь',
            'rue du trône', 'brussels', 'belgium',
            'gb+', 'swift/bic', 'iban'
        ]):
            continue

        if _is_service_line(line):
            continue

        # Ищем сумму
        m = amount_at_end_re.match(line)
        if not m:
            # Может, строка с суммой в середине: ".... -24,36 1 357,37"
            m2 = re.search(r'(-?[\d\s\u00a0]+[.,]\d{2})\s+[\d\s\u00a0]+[.,]\d{2}', line)
            if not m2:
                # Пробуем любую сумму
                m3 = re.search(r'(-?[\d\s\u00a0]+[.,]\d{2})', line)
                if not m3:
                    continue
                amount = parse_amount(m3.group(1))
                desc = line[:m3.start()].strip()
            else:
                amount = parse_amount(m2.group(1))
                desc = line[:m2.start()].strip()
        else:
            amount = parse_amount(m.group(2))
            desc = m.group(1).strip()

        if amount == 0.0 or not _is_reasonable_amount(amount):
            continue

        # Определяем дату
        date = current_date or ''
        if not date:
            # Ищем в предыдущих 3 строках
            for j in range(max(0, i - 3), i):
                dm2 = re.search(
                    r'(\d{1,2}\s+[A-Za-zА-Яа-яЁё]+\.?\s+\d{4}\s*г?\.?)',
                    lines[j]
                )
                if dm2:
                    date = parse_date(dm2.group(1))
                    if date:
                        break

        if not date:
            continue

        # Чистим desc
        desc_clean = re.sub(
            r'\d{1,2}\s+[A-Za-zА-Яа-яЁё]+\.?\s+\d{4}\s*г?\.?',
            '', desc
        )
        desc_clean = re.sub(r'Карта,\s*заканчивающаяся\s+на\s+\d+', '', desc_clean)
        desc_clean = re.sub(r'Транзакция:\s*[A-Z0-9\-]+', '', desc_clean)
        desc_clean = re.sub(r'Пояснение:\s*[^\|]+', '', desc_clean)
        desc_clean = re.sub(r'\s+', ' ', desc_clean).strip(' .,;:-|')

        if not desc_clean:
            continue

        cp_final, _ = extract_counterparty_smart(desc_clean, account_name)
        if not cp_final:
            cp_final = 'Wise'

        result.append({
            'Дата': date,
            'Сумма': amount,
            'Контрагент': cp_final,
            'Наименование счета': account_name,
            'Описание': desc_clean
        })

    # Дедупликация
    seen = set()
    deduped = []
    for r in result:
        key = (r['Дата'], round(r['Сумма'], 2), r['Описание'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped


# ==================== Paysera ====================

def parse_paysera_generic(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    df = read_xlsx(file_content, sheet_name='Worksheet')
    if df is None or df.empty:
        df = read_xlsx(file_content)
    if df is None or df.empty:
        return []

    header_row = -1
    header_keyword_sets = [
        ['Тип', 'Дата и время', 'Сумма и валюта'],
        ['Тип', 'Дата', 'Сумма'],
        ['Type', 'Date', 'Amount'],
        ['Veids', 'Datums', 'Summa'],
        ['Тип', 'Дата и время', 'Сумма'],
        ['Kredit / Debet', 'Дата и время', 'Сумма и валюта'],
    ]
    for idx, row in df.iterrows():
        if idx < 40:
            rs = ' '.join([str(x) for x in row.values if pd.notna(x)])
            for kws in header_keyword_sets:
                if all(kw in rs for kw in kws):
                    header_row = idx
                    break
            if header_row != -1:
                break
    if header_row == -1:
        return []

    hdr = df.iloc[header_row]
    ci = {}
    for i, v in enumerate(hdr.values):
        if pd.isna(v):
            continue
        s = str(v).strip()
        sl = s.lower()
        if 'дата' in sl or 'date' in sl or 'datums' in sl:
            if 'date' not in ci:
                ci['date'] = i
        elif 'получатель' in sl or 'плательщик' in sl or 'counterparty' in sl or 'saņēmējs' in sl:
            if 'counterparty' not in ci:
                ci['counterparty'] = i
        elif 'назначение' in sl or 'purpose' in sl or 'maksājuma' in sl or 'mērķis' in sl:
            if 'purpose' not in ci:
                ci['purpose'] = i
        elif 'сумма' in sl or 'amount' in sl or 'summa' in sl:
            if 'amount' not in ci:
                ci['amount'] = i
        elif 'кредит' in sl or 'дебет' in sl or 'kredit' in sl or 'debet' in sl or 'credit' in sl or 'debit' in sl:
            if 'type' not in ci:
                ci['type'] = i
    if 'date' not in ci:
        ci['date'] = 3
    if 'amount' not in ci:
        ci['amount'] = 7
    if 'counterparty' not in ci:
        ci['counterparty'] = 4
    if 'purpose' not in ci:
        ci['purpose'] = 9
    if 'type' not in ci:
        ci['type'] = 11

    for idx in range(header_row + 1, len(df)):
        row = df.iloc[idx]
        rv = [x for x in row.values if pd.notna(x)]
        if not rv:
            continue
        rstr = ' '.join([str(x) for x in row.values if pd.notna(x)])
        if 'Остаток' in rstr or 'Дебетовый оборот' in rstr or 'Кредитовый оборот' in rstr:
            continue
        if 'Atlikums' in rstr or 'Kredīta apgrozījums' in rstr or 'Debeta apgrozījums' in rstr:
            continue
        try:
            dstr = safe_str(row.iloc[ci['date']]) if ci['date'] < len(row) else ''
            if not dstr:
                continue
            m = re.match(r'(\d{4}-\d{2}-\d{2})', dstr)
            if m:
                dstr = m.group(1)
            date = parse_date(dstr)
            if not date:
                continue
            av = row.iloc[ci['amount']] if ci['amount'] < len(row) else None
            if pd.isna(av) or str(av).strip() in ['', 'nan']:
                continue
            astr = str(av).strip().replace(',', '.').replace(' ', '')
            astr = re.sub(r'[A-Za-z]+$', '', astr).strip()
            amount = parse_amount(astr)
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            ttype = safe_str(row.iloc[ci['type']]) if 'type' in ci and ci['type'] < len(row) else ''
            if ttype in ('Д', 'D', 'Debet'):
                amount = -abs(amount)
            elif ttype in ('К', 'C', 'Kredīts'):
                amount = abs(amount)
            cp = safe_str(row.iloc[ci['counterparty']]) if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
            desc = safe_str(row.iloc[ci['purpose']]) if 'purpose' in ci and ci['purpose'] < len(row) else ''
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name, cp, '', cp)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


def parse_paysera_baltic_xlsx(file_content, account_name):
    return parse_paysera_generic(file_content, account_name)


def parse_paysera_sveciy_xlsx(file_content, account_name):
    return parse_paysera_generic(file_content, account_name)


def parse_paysera_property(file_content, account_name):
    return parse_paysera_generic(file_content, account_name)


def parse_paysera_rerum(file_content, account_name):
    return parse_paysera_generic(file_content, account_name)


def parse_paysera_docx(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []
    all_parts = []
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                t = cell.text.strip()
                if t:
                    all_parts.append(t)
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            all_parts.append(t)
    full_text = '\n'.join(all_parts).replace('\ufeff', '').replace('\xa0', ' ')
    pattern = re.compile(
        r'([A-Za-zА-Яа-я][A-Za-zА-Яа-я\s]{2,40}?)'
        r'\s+'
        r'(\d{4}-\d{2}-\d{2})'
        r'\s+'
        r'(\d{2}:\d{2}:\d{2})'
        r'(?:\s+[+\-]\d{4})?'
        r'\s*'
        r'(\d{6,})'
        r'\s*'
        r'([A-Za-zА-Яа-я][^\d\-+]{2,500}?)'
        r'\s*'
        r'\((\d{6,})\)'
        r'\s*'
        r'(-?\d[\d\s]*[.,]\d{2})\s*([A-Z]{3})'
        r'(?:\s+([^\n]{2,2000}))?',
        re.MULTILINE
    )
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(2))
            amount = parse_amount(m.group(8))
            counterparty = re.sub(r'\s+', ' ', m.group(6)).strip()
            op_type = m.group(1).strip()
            purpose = (m.group(10) or '').strip()
            if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            desc = purpose if purpose else f"{op_type}: {counterparty}"
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name, counterparty, '', counterparty)
            if not cp_final:
                cp_final = counterparty
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final,
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


def parse_paysera_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []

    lines = full_text.split('\n')

    blocks = []
    current_lines = []
    for line in lines:
        current_lines.append(line)
        norm = re.sub(r'\s+', ' ', line).lower()
        if 'назначение' in norm and 'платежа' in norm:
            blocks.append(current_lines)
            current_lines = []
        elif 'purpose of payment' in norm:
            blocks.append(current_lines)
            current_lines = []

    date_time_re = re.compile(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})')
    amount_re = re.compile(r'(-?\d[\d\s\u00a0]*[.,]\d{2})\s*(EUR|USD|CZK|GBP)')
    purpose_re = re.compile(
        r'(?:Назначение\s+платежа|Purpose of payment)\s*:\s*(.*?)(?:$|\n)',
        re.IGNORECASE | re.DOTALL
    )

    for block in blocks:
        block_text = '\n'.join(block)

        purpose = ''
        pm = purpose_re.search(block_text)
        if pm:
            purpose = re.sub(r'\s+', ' ', pm.group(1)).strip()
            purpose = re.sub(r'^[\.\s]+', '', purpose)

        date_matches = list(date_time_re.finditer(block_text))
        if not date_matches:
            continue
        last_date = date_matches[-1]
        date = parse_date(last_date.group(1))
        if not date:
            continue

        amount_matches = list(amount_re.finditer(block_text))
        if not amount_matches:
            continue
        amount = None
        for am in amount_matches:
            if am.start() < last_date.start():
                v = parse_amount(am.group(1))
                if v != 0.0 and _is_reasonable_amount(v):
                    amount = v
                    break
        if amount is None:
            for am in amount_matches:
                v = parse_amount(am.group(1))
                if v != 0.0 and _is_reasonable_amount(v):
                    amount = v
                    break
        if amount is None or amount == 0.0:
            continue

        first_amt_pos = amount_matches[0].start()
        party_raw = block_text[:first_amt_pos]
        party_raw = re.sub(r'\+\d{4}', ' ', party_raw)
        party_raw = re.sub(r'\b\d{6,}\b', ' ', party_raw)
        party_raw = re.sub(r'\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b', ' ', party_raw)
        party_raw = re.sub(r'\(\s*\d+\s*\)', ' ', party_raw)
        party_raw = re.sub(
            r'\b(Перевод|Комиссионная\s+плата|Тип|Номер|Дата\s+и\s+время|выписки|'
            r'перевода|Получатель\s*/\s*Плательщик|EVP\s*/\s*IBAN|'
            r'Сумма\s+и\s+валюта|Остаток|Назначение\s+платежа|'
            r'Transfer|Commission\s+fee|Type|Number|Date\s+and\s+time|'
            r'Recipient\s*/\s*Payer|Amount\s+and\s+currency|Balance)\b',
            ' ', party_raw, flags=re.IGNORECASE
        )
        party_raw = re.sub(r'\s+', ' ', party_raw).strip()
        cp = party_raw.strip(' .,;:-')

        if _is_service_line(purpose):
            continue

        cp_final, _ = extract_counterparty_smart(purpose, account_name, cp, '', cp)

        result.append({
            'Дата': date,
            'Сумма': amount,
            'Контрагент': cp_final if cp_final else '',
            'Наименование счета': account_name,
            'Описание': purpose
        })

    seen = set()
    deduped = []
    for r in result:
        key = (r['Дата'], r['Сумма'], r['Контрагент'], r['Описание'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped


# ==================== RAK BANK ====================

def parse_rak_bank(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    content = read_text_with_encoding(file_content)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    for line in lines:
        parts = [p.strip() for p in line.split(';')]
        if len(parts) < 3:
            continue
        try:
            date = parse_date(parts[0])
            if not date:
                continue
            amount = parse_amount(parts[2].replace(',', '.'))
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            desc = parts[1] if len(parts) > 1 else ''
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


def parse_rak_bank_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    tables = pdf_all_tables(file_content)
    for table in tables:
        for row in table:
            if len(row) < 3:
                continue
            try:
                date = parse_date(row[0])
                if not date:
                    continue
                amount = parse_amount(row[2])
                if amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                desc = row[1]
                if _is_service_line(desc):
                    continue
                cp_final, _ = extract_counterparty_smart(desc, account_name)
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp_final if cp_final else '',
                    'Наименование счета': account_name,
                    'Описание': desc
                })
            except Exception:
                continue
    return result


# ==================== Revolut ====================

def _extract_after_to(desc: str) -> str:
    if not desc:
        return ''
    m = re.match(r'^\s*To\s+(.+)$', desc.strip(), flags=re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()
    return ''


def parse_revolut_generic(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    content = read_text_with_encoding(file_content)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if len(lines) < 2:
        return []
    header = -1
    for i, l in enumerate(lines[:10]):
        low = l.lower()
        if 'date started' in low and 'description' in low:
            header = i
            break
    if header == -1:
        return []
    header_line = lines[header]
    sep = ',' if header_line.count(',') >= header_line.count(';') else ';'
    hdr_parts = _split_line(header_line, sep)
    ci = {}
    for i, h in enumerate(hdr_parts):
        hl = h.lower().strip()
        if 'date started' in hl and 'date' not in ci:
            ci['date'] = i
        elif hl == 'amount' and 'amount' not in ci:
            ci['amount'] = i
        elif hl == 'total amount' and 'amount' not in ci:
            ci['amount'] = i
        elif 'description' in hl and 'description' not in ci:
            ci['description'] = i
        elif hl == 'reference' and 'reference' not in ci:
            ci['reference'] = i
        elif hl == 'payer' and 'counterparty' not in ci:
            ci['counterparty'] = i
        elif hl == 'state' and 'state' not in ci:
            ci['state'] = i
        elif hl == 'type' and 'type' not in ci:
            ci['type'] = i
        elif hl == 'beneficiary name' and 'beneficiary' not in ci:
            ci['beneficiary'] = i
        elif hl == 'sender name' and 'sender_name' not in ci:
            ci['sender_name'] = i
    if 'date' not in ci:
        ci['date'] = 0
    if 'amount' not in ci:
        ci['amount'] = 15
    if 'description' not in ci:
        ci['description'] = 5
    if 'type' not in ci:
        ci['type'] = 3
    if 'state' not in ci:
        ci['state'] = 4

    for line in lines[header + 1:]:
        parts = _split_line(line, sep)
        if len(parts) < 6:
            continue
        try:
            if 'state' in ci and ci['state'] < len(parts):
                st = parts[ci['state']].strip().upper()
                if st and st != 'COMPLETED':
                    continue
            date = parse_date(parts[ci['date']] if ci['date'] < len(parts) else '')
            if not date:
                continue
            amount = parse_amount(parts[ci['amount']] if ci['amount'] < len(parts) else '')
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            ttype = parts[ci['type']].strip().upper() if 'type' in ci and ci['type'] < len(parts) else ''
            if ttype == 'TOPUP':
                amount = abs(amount)
            elif ttype == 'FEE':
                amount = -abs(amount)
            payer = parts[ci['counterparty']] if 'counterparty' in ci and ci['counterparty'] < len(parts) else ''
            beneficiary = parts[ci['beneficiary']] if 'beneficiary' in ci and ci['beneficiary'] < len(parts) else ''
            sender_name = parts[ci['sender_name']] if 'sender_name' in ci and ci['sender_name'] < len(parts) else ''
            desc = parts[ci['description']] if ci['description'] < len(parts) else ''
            reference = parts[ci['reference']] if 'reference' in ci and ci['reference'] < len(parts) else ''

            full_desc = desc
            if reference and reference.strip() and reference.strip() != 'nan':
                full_desc = f"{desc} | {reference}" if desc else reference

            if _is_service_line(full_desc):
                continue

            cp_final, _ = extract_counterparty_smart(
                full_desc, account_name, payer, beneficiary,
                '', sender_name
            )

            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': full_desc
            })
        except Exception:
            continue
    return result


def parse_revolut_an14(file_content, account_name):
    return parse_revolut_generic(file_content, account_name)


def parse_revolut_nb(file_content, account_name):
    return parse_revolut_generic(file_content, account_name)


def parse_revolut_plavas(file_content, account_name):
    return parse_revolut_generic(file_content, account_name)


# ---------- ГЛАВНОЕ ИСПРАВЛЕНИЕ: Revolut PDF ----------

def parse_revolut_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Парсер PDF Revolut с поддержкой русских и английских названий месяцев.
    Форматы:
        6 июн. 2026 FEE Комиссия Revolut Business • Комиссия за €10.00 €234.82
        28 июн. 2026 FEE Комиссия Revolut Business • Комиссия за план Basic 10.00 55.00
    """
    result = []
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []

    full_text = _CID_PATTERN.sub(' ', full_text)

    # Месяцы: русские + английские + чешские
    month_alt = (
        r'(?:'
        r'янв|фев|мар|апр|ма[йя]|июн|июл|авг|сен|окт|ноя|дек'
        r'|января|февраля|марта|апреля|мая|июня|июля|августа|'
        r'сентября|октября|ноября|декабря'
        r'|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec'
        r'|january|february|march|april|june|july|august|'
        r'september|october|november|december'
        r'|led|úno|bře|dub|kvě|čvn|čvc|srp|zář|říj|lis|pro'
        r'|ledna|února|března|dubna|května|června|července|'
        r'srpna|září|října|listopadu|prosince'
        r')'
    )

    date_re = re.compile(
        rf'(\d{{1,2}}\s+{month_alt}\.?\s+\d{{4}})\s+(.*)$',
        re.IGNORECASE | re.MULTILINE
    )
    type_re = re.compile(r'\b(MOA|MOS|MOR|FEE|CAR|ATM|EXO|EXI|TOPUP|TRANSFER)\b')

    # Регулярка для €-сумм, в т.ч. "- €10.00" и "-€10.00"
    eur_re = re.compile(
        r'(-?\s?€\s?\d[\d\s\u00a0]*[.,]\d{2}|-?\d[\d\s\u00a0]*[.,]\d{2}\s?€)'
    )

    lines = full_text.split('\n')

    operations = []
    current = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        dm = date_re.search(stripped)
        if dm:
            if current is not None:
                operations.append(current)
            current = {
                'date_str': dm.group(1),
                'after': dm.group(2).strip(),
                'continuation': []
            }
        else:
            if current is not None:
                low = stripped.lower()
                skip_markers = [
                    'account statement', 'generated on', 'antonijas nams',
                    'report lost', 'revolut bank uab', 'scan the qr',
                    'get help', '© 20', 'page ', '/3', '/2', '/1',
                    'transactions from', 'opening balance', 'money in',
                    'money out', 'closing balance', 'your funds',
                    'balance summary', 'date (utc)', 'description money',
                    'account name', 'currency eur', 'type local',
                    'type international', 'iban lt', 'bic revolt',
                    'intermediary bic', '14 antonijas', 'riga', 'lv-1010',
                    'latvia', 'revolut bank uab is a credit',
                    '+370 5 214 3608', 'konstitucijos', 'eligible deposits',
                    'deposit and investment', 'viešoji', 'www.iidraudimas',
                    'card payments', 'money sent', 'money received',
                    'money added', 'atm withdrawals', 'exchange out',
                    'exchange in', 'revolut fees',
                    'выписка со счета', 'сформировано', 'название счета',
                    'валюта', 'тип', 'местная карта', 'международный',
                    'bic-код посредника', 'краткая информация',
                    'начальный баланс', 'прибыль', 'расходы',
                    'конечный остаток', 'ваши средства хранятся',
                    'операции от', 'дата (utc)', 'описание',
                    'типы операций', 'платежи по карте', 'снятие наличных',
                    'отправлено', 'обмен при оплате', 'получено',
                    'обмен при получении', 'пополнение', 'комиссии revolut',
                    'получите помощь', 'отсканируйте qr-код',
                ]
                if any(m in low for m in skip_markers):
                    continue
                current['continuation'].append(stripped)

    if current is not None:
        operations.append(current)

    for op in operations:
        date = parse_date(op['date_str'])
        if not date:
            continue

        after = op['after']
        tm = type_re.search(after)
        ttype = ''
        if tm:
            ttype = tm.group(1)
            after = after[tm.end():].strip()

        eur_matches = list(eur_re.finditer(after))
        if not eur_matches:
            # Попробуем найти сумму без €
            # Пример: "10.00 55.00" — первая это расход, вторая — баланс
            nums = re.findall(r'-?\s?\d[\d\s\u00a0]*[.,]\d{2}', after)
            if not nums:
                continue
            # Первая — сумма операции
            amount = parse_amount(nums[0])
            if amount == 0.0:
                continue
            desc_main = after
            # Очистим desc от чисел
            for n in nums:
                desc_main = desc_main.replace(n, '')
            desc_main = re.sub(r'\s+', ' ', desc_main).strip()
        else:
            amount_match = eur_matches[0]
            amount = parse_amount(amount_match.group(0))
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            desc_main = after[:amount_match.start()].strip()

        parts = [desc_main] + op['continuation']
        desc = ' '.join(p for p in parts if p)
        desc = re.sub(r'\s+', ' ', desc).strip()
        desc = desc.strip(' •')

        # Определяем знак: если тип FEE/CAR/ATM/MOS/EXO — расход
        if ttype in ('MOA', 'MOR', 'TOPUP'):
            amount = abs(amount)
        elif ttype in ('MOS', 'FEE', 'CAR', 'ATM', 'EXO'):
            amount = -abs(amount)
        else:
            # Если сумма пришла как "€10.00" — считаем расходом
            if '€' in after and not after.strip().startswith('+'):
                amount = -abs(amount)

        if _is_service_line(desc):
            continue

        cp_final, _ = extract_counterparty_smart(desc, account_name)

        result.append({
            'Дата': date,
            'Сумма': amount,
            'Контрагент': cp_final if cp_final else '',
            'Наименование счета': account_name,
            'Описание': desc
        })

    # Дедупликация
    seen = set()
    deduped = []
    for r in result:
        key = (r['Дата'], r['Сумма'], r['Контрагент'], r['Описание'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped


# ==================== Pasha Bank ====================

def parse_pasha_bank_xlsx(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    df = read_xlsx(file_content, sheet_name='Statement')
    if df is None or df.empty:
        df = read_xlsx(file_content)
    if df is None or df.empty:
        return []
    header_row = -1
    for idx, row in df.iterrows():
        if idx < 40:
            rs = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Əməliyyat tarixi' in rs and 'Mədaxil' in rs and 'Məxaric' in rs:
                header_row = idx
                break
    if header_row == -1:
        return []
    hdr = df.iloc[header_row]
    ci = {}
    for i, v in enumerate(hdr.values):
        if pd.isna(v):
            continue
        s = str(v).strip()
        if 'Əməliyyat tarixi' in s:
            ci['date'] = i
        elif 'İcra tarixi' in s:
            ci['exec_date'] = i
        elif 'Ödəyən' in s or 'Benefisiar' in s or 'Ödəyən/Benefisiar' in s:
            ci['counterparty'] = i
        elif 'Təyinat' in s:
            ci['description'] = i
        elif 'Mədaxil' in s:
            ci['credit'] = i
        elif 'Məxaric' in s:
            ci['debit'] = i
        elif 'Balans' in s and 'balance' not in ci:
            ci['balance'] = i
        elif 'Код' in s or s == 'Kod':
            ci['code'] = i
    if 'date' not in ci:
        ci['date'] = 0
    if 'description' not in ci:
        ci['description'] = 3
    if 'counterparty' not in ci:
        ci['counterparty'] = 2
    if 'credit' not in ci:
        ci['credit'] = 6
    if 'debit' not in ci:
        ci['debit'] = 7
    for idx in range(header_row + 1, len(df)):
        row = df.iloc[idx]
        rv = [x for x in row.values if pd.notna(x)]
        if not rv:
            continue
        try:
            dstr = safe_str(row.iloc[ci['date']]) if ci['date'] < len(row) else ''
            if not dstr:
                continue
            date = parse_date(dstr)
            if not date:
                continue
            desc = safe_str(row.iloc[ci['description']]) if ci['description'] < len(row) else ''
            low_desc = desc.lower()
            if 'balans' in low_desc and ('dövr' in low_desc or 'mövcud' in low_desc):
                continue
            if 'dövrün sonuna balans' in low_desc or 'mövcud balans' in low_desc:
                continue
            if low_desc.strip() in ('balans', 'balans:', 'mövcud balans'):
                continue
            if _is_service_line(desc):
                continue
            credit = 0.0
            debit = 0.0
            if 'credit' in ci and ci['credit'] < len(row):
                cv = row.iloc[ci['credit']]
                if pd.notna(cv) and str(cv).strip() not in ['', 'nan', '-']:
                    credit = parse_amount(str(cv).strip().replace(',', '.'))
            if 'debit' in ci and ci['debit'] < len(row):
                dv = row.iloc[ci['debit']]
                if pd.notna(dv) and str(dv).strip() not in ['', 'nan', '-']:
                    debit = parse_amount(str(dv).strip().replace(',', '.'))
            if credit == 0.0 and debit == 0.0:
                continue
            if credit != 0.0:
                amount = abs(credit)
            else:
                amount = -abs(debit)
            if not _is_reasonable_amount(amount):
                continue
            cp = safe_str(row.iloc[ci['counterparty']]) if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
            cp = cp.replace('_x000D_', ' ').replace('\r', ' ').replace('\n', ' ')
            cp = re.sub(r'\s+', ' ', cp).strip()
            desc = desc.replace('_x000D_', ' ').replace('\r', ' ').replace('\n', ' ')
            desc = re.sub(r'\s+', ' ', desc).strip()
            cp_final, _ = extract_counterparty_smart(desc, account_name, cp, '', cp)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


def parse_pasha_bank_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    tables = pdf_all_tables(file_content)
    for table in tables:
        if not table or len(table) < 2:
            continue
        header_idx = -1
        for i, row in enumerate(table[:6]):
            joined = ' '.join(row).lower()
            if ('əməliyyat' in joined or 'tarix' in joined) and ('mədaxil' in joined or 'məxaric' in joined):
                header_idx = i
                break
        if header_idx == -1:
            continue
        hdr = table[header_idx]
        ci = {}
        for i, h in enumerate(hdr):
            hl = h.lower()
            if 'tarix' in hl and 'date' not in ci:
                ci['date'] = i
            elif 'mədaxil' in hl and 'credit' not in ci:
                ci['credit'] = i
            elif 'məxaric' in hl and 'debit' not in ci:
                ci['debit'] = i
            elif 'təyinat' in hl and 'description' not in ci:
                ci['description'] = i
            elif ('ödəyən' in hl or 'benefisiar' in hl) and 'counterparty' not in ci:
                ci['counterparty'] = i
        for row in table[header_idx + 1:]:
            try:
                date = parse_date(row[ci.get('date', 0)] if ci.get('date', 0) < len(row) else '')
                if not date:
                    continue
                credit = parse_amount(row[ci.get('credit', 6)] if ci.get('credit', 6) < len(row) else '')
                debit = parse_amount(row[ci.get('debit', 7)] if ci.get('debit', 7) < len(row) else '')
                if credit == 0.0 and debit == 0.0:
                    continue
                amount = abs(credit) if credit != 0.0 else -abs(debit)
                if not _is_reasonable_amount(amount):
                    continue
                desc = row[ci['description']] if 'description' in ci and ci['description'] < len(row) else ''
                cp = row[ci['counterparty']] if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
                if _is_service_line(desc):
                    continue
                cp_final, _ = extract_counterparty_smart(desc, account_name, cp, '', cp)
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp_final if cp_final else '',
                    'Наименование счета': account_name,
                    'Описание': desc
                })
            except Exception:
                continue
        if result:
            return result
    return result


# ==================== Универсальные парсеры ====================

def parse_pdf_universal(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    tables = pdf_all_tables(file_content)
    for table in tables:
        if not table or len(table) < 2:
            continue
        header_idx = -1
        for i, row in enumerate(table[:5]):
            joined = ' '.join(row).lower()
            if ('date' in joined or 'дата' in joined) and ('amount' in joined or 'сумма' in joined or 'sum' in joined):
                header_idx = i
                break
        if header_idx == -1:
            continue
        hdr = table[header_idx]
        date_i = amount_i = desc_i = cp_i = -1
        for i, h in enumerate(hdr):
            hl = h.lower()
            if 'date' in hl or 'дата' in hl or 'értéknap' in hl:
                if date_i == -1:
                    date_i = i
            elif 'amount' in hl or 'сумма' in hl or 'összeg' in hl or 'betrag' in hl:
                if amount_i == -1:
                    amount_i = i
            elif 'description' in hl or 'описание' in hl or 'details' in hl or 'közlemény' in hl:
                if desc_i == -1:
                    desc_i = i
            elif 'name' in hl or 'recipient' in hl or 'counterparty' in hl or 'kedvezményezett' in hl:
                if cp_i == -1:
                    cp_i = i
        if date_i == -1 or amount_i == -1:
            continue
        for row in table[header_idx + 1:]:
            try:
                date = parse_date(row[date_i] if date_i < len(row) else '')
                if not date:
                    continue
                amount = parse_amount(row[amount_i] if amount_i < len(row) else '')
                if amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                desc = row[desc_i] if desc_i >= 0 and desc_i < len(row) else ''
                cp = row[cp_i] if cp_i >= 0 and cp_i < len(row) else ''
                if _is_service_line(desc):
                    continue
                cp_final, _ = extract_counterparty_smart(desc, account_name, cp, '', cp)
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp_final if cp_final else '',
                    'Наименование счета': account_name,
                    'Описание': desc
                })
            except Exception:
                continue
    return result


def parse_csv_universal(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    content = read_text_with_encoding(file_content)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if len(lines) < 2:
        return []
    sample = '\n'.join(lines[:5])
    sep = ';' if sample.count(';') >= sample.count(',') else ','
    header_idx = -1
    for i, l in enumerate(lines[:30]):
        low = l.lower()
        if ('date' in low or 'дата' in low) and ('amount' in low or 'сумма' in low or 'sum' in low):
            header_idx = i
            break
    if header_idx == -1:
        return []
    hdr = _split_line(lines[header_idx], sep)
    ci = {}
    for i, h in enumerate(hdr):
        hl = h.lower()
        if ('date' in hl or 'дата' in hl) and 'date' not in ci:
            ci['date'] = i
        elif ('amount' in hl or 'сумма' in hl or 'sum' in hl or 'betrag' in hl) and 'amount' not in ci:
            ci['amount'] = i
        elif ('description' in hl or 'описание' in hl or 'details' in hl or 'назначение' in hl) and 'description' not in ci:
            ci['description'] = i
        elif ('counterparty' in hl or 'контрагент' in hl or 'name' in hl or 'payer' in hl) and 'counterparty' not in ci:
            ci['counterparty'] = i
    if 'date' not in ci or 'amount' not in ci:
        return []
    for line in lines[header_idx + 1:]:
        parts = _split_line(line, sep)
        if ci['date'] >= len(parts) or ci['amount'] >= len(parts):
            continue
        try:
            date = parse_date(parts[ci['date']])
            if not date:
                continue
            amount = parse_amount(parts[ci['amount']])
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            desc = parts[ci['description']] if 'description' in ci and ci['description'] < len(parts) else ''
            cp = parts[ci['counterparty']] if 'counterparty' in ci and ci['counterparty'] < len(parts) else ''
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name, cp, '', cp)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


def parse_xlsx_universal(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    df = read_xlsx(file_content)
    if df is None or df.empty:
        return []
    header_row = -1
    for idx, row in df.iterrows():
        if idx < 30:
            rs = ' '.join([str(x) for x in row.values if pd.notna(x)]).lower()
            if ('date' in rs or 'дата' in rs) and ('amount' in rs or 'сумма' in rs or 'sum' in rs):
                header_row = idx
                break
    if header_row == -1:
        return []
    hdr = df.iloc[header_row]
    ci = {}
    for i, v in enumerate(hdr.values):
        if pd.isna(v):
            continue
        sl = str(v).strip().lower()
        if ('date' in sl or 'дата' in sl) and 'date' not in ci:
            ci['date'] = i
        elif ('amount' in sl or 'сумма' in sl or 'sum' in sl or 'betrag' in sl) and 'amount' not in ci:
            ci['amount'] = i
        elif ('description' in sl or 'описание' in sl or 'details' in sl or 'назначение' in sl) and 'description' not in ci:
            ci['description'] = i
        elif ('counterparty' in sl or 'контрагент' in sl or 'name' in sl or 'payer' in sl) and 'counterparty' not in ci:
            ci['counterparty'] = i
    if 'date' not in ci or 'amount' not in ci:
        return []
    for idx in range(header_row + 1, len(df)):
        row = df.iloc[idx]
        try:
            dstr = safe_str(row.iloc[ci['date']]) if ci['date'] < len(row) else ''
            if not dstr:
                continue
            date = parse_date(dstr)
            if not date:
                continue
            av = row.iloc[ci['amount']] if ci['amount'] < len(row) else None
            if not _cell_is_numeric(av):
                continue
            amount = parse_amount(str(av))
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            desc = safe_str(row.iloc[ci['description']]) if 'description' in ci and ci['description'] < len(row) else ''
            cp = safe_str(row.iloc[ci['counterparty']]) if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name, cp, '', cp)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


def parse_docx_universal(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []
    for table in doc.tables:
        if not table.rows:
            continue
        hdr = [c.text.strip().lower() for c in table.rows[0].cells]
        date_i = amount_i = desc_i = cp_i = -1
        for i, h in enumerate(hdr):
            if ('date' in h or 'дата' in h) and date_i == -1:
                date_i = i
            elif ('amount' in h or 'сумма' in h or 'sum' in h) and amount_i == -1:
                amount_i = i
            elif ('description' in h or 'описание' in h or 'назначение' in h) and desc_i == -1:
                desc_i = i
            elif ('counterparty' in h or 'контрагент' in h or 'name' in h) and cp_i == -1:
                cp_i = i
        if date_i == -1 or amount_i == -1:
            continue
        for row in table.rows[1:]:
            cells = [c.text.strip() for c in row.cells]
            try:
                date = parse_date(cells[date_i] if date_i < len(cells) else '')
                if not date:
                    continue
                amount = parse_amount(cells[amount_i] if amount_i < len(cells) else '')
                if amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                desc = cells[desc_i] if desc_i >= 0 and desc_i < len(cells) else ''
                cp = cells[cp_i] if cp_i >= 0 and cp_i < len(cells) else ''
                if _is_service_line(desc):
                    continue
                cp_final, _ = extract_counterparty_smart(desc, account_name, cp, '', cp)
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp_final if cp_final else '',
                    'Наименование счета': account_name,
                    'Описание': desc
                })
            except Exception:
                continue
    if result:
        return result
    full_text = docx_all_text(file_content)
    if not full_text:
        return result
    pattern = re.compile(
        r'(\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2})\s+'
        r'(.{3,2000}?)\s+'
        r'(-?[\d\s]+[.,]\d{2})',
        re.MULTILINE
    )
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(1))
            desc = re.sub(r'\s+', ' ', m.group(2)).strip()
            amount = parse_amount(m.group(3))
            if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': desc
            })
        except Exception:
            continue
    return result


def parse_any_format(file_content: bytes, account_name: str) -> List[Dict]:
    result: List[Dict] = []
    tables = pdf_all_tables(file_content)
    for table in tables:
        if not table or len(table) < 2:
            continue
        for row in table:
            if not row or len(row) < 2:
                continue
            date = None
            date_i = -1
            for i in range(min(3, len(row))):
                d = parse_date(row[i])
                if d and re.match(r'^\d{2}-\d{2}-\d{4}$', d):
                    date = d
                    date_i = i
                    break
            if not date:
                continue
            amount = 0.0
            amount_i = -1
            for i in range(len(row)):
                if i == date_i:
                    continue
                if not _cell_is_numeric(row[i]):
                    continue
                a = parse_amount(row[i])
                if a != 0.0 and _is_reasonable_amount(a):
                    amount = a
                    amount_i = i
                    break
            if amount == 0.0:
                continue
            desc = ''
            for i in range(len(row)):
                if i in (date_i, amount_i):
                    continue
                v = (row[i] or '').strip()
                if v and len(v) > 2 and not re.match(r'^[\d.,\-]+$', v):
                    desc = v
                    break
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': desc
            })
    if result:
        return result
    full_text = pdf_all_text(file_content)
    if full_text:
        pattern = re.compile(
            r'(\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2})\s+'
            r'(.{3,2000}?)\s+'
            r'(-?[\d\s]+[.,]\d{2})',
            re.MULTILINE
        )
        for m in pattern.finditer(full_text):
            try:
                date = parse_date(m.group(1))
                desc = re.sub(r'\s+', ' ', m.group(2)).strip()
                amount = parse_amount(m.group(3))
                if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                if _is_service_line(desc):
                    continue
                cp_final, _ = extract_counterparty_smart(desc, account_name)
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp_final if cp_final else '',
                    'Наименование счета': account_name,
                    'Описание': desc
                })
            except Exception:
                continue
        if result:
            return result
    df = read_xlsx(file_content)
    if df is not None and not df.empty:
        for idx, row in df.iterrows():
            rv = [x for x in row.values if pd.notna(x)]
            if len(rv) < 2:
                continue
            date = None
            date_i = -1
            for i, v in enumerate(row.values):
                d = parse_date(v)
                if d and re.match(r'^\d{2}-\d{2}-\d{4}$', d):
                    date = d
                    date_i = i
                    break
            if not date:
                continue
            amount = 0.0
            amount_i = -1
            for i, v in enumerate(row.values):
                if i == date_i or pd.isna(v):
                    continue
                if not _cell_is_numeric(v):
                    continue
                a = parse_amount(v)
                if a != 0.0 and _is_reasonable_amount(a):
                    amount = a
                    amount_i = i
                    break
            if amount == 0.0:
                continue
            desc = ''
            for i, v in enumerate(row.values):
                if i in (date_i, amount_i) or pd.isna(v):
                    continue
                vs = str(v).strip()
                if vs and len(vs) > 2 and not re.match(r'^[\d.,\-]+$', vs):
                    desc = vs
                    break
            if _is_service_line(desc):
                continue
            cp_final, _ = extract_counterparty_smart(desc, account_name)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': desc
            })
        if result:
            return result
    content = read_text_with_encoding(file_content)
    if content:
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        for line in lines:
            for sep in [';', ',', '\t']:
                if line.count(sep) < 1:
                    continue
                parts = _split_line(line, sep)
                if len(parts) < 2:
                    continue
                date = None
                date_i = -1
                for i, p in enumerate(parts[:4]):
                    d = parse_date(p)
                    if d and re.match(r'^\d{2}-\d{2}-\d{4}$', d):
                        date = d
                        date_i = i
                        break
                if not date:
                    continue
                amount = 0.0
                amount_i = -1
                for i, p in enumerate(parts):
                    if i == date_i:
                        continue
                    if not _cell_is_numeric(p):
                        continue
                    a = parse_amount(p)
                    if a != 0.0 and _is_reasonable_amount(a):
                        amount = a
                        amount_i = i
                        break
                if amount == 0.0:
                    continue
                desc = ''
                for i, p in enumerate(parts):
                    if i in (date_i, amount_i):
                        continue
                    if p and len(p) > 2 and not re.match(r'^[\d.,\-]+$', p):
                        desc = p
                        break
                if _is_service_line(desc):
                    continue
                cp_final, _ = extract_counterparty_smart(desc, account_name)
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp_final if cp_final else '',
                    'Наименование счета': account_name,
                    'Описание': desc
                })
                break
        if result:
            return result
    docx_text = docx_all_text(file_content)
    if docx_text:
        pattern = re.compile(
            r'(\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2})\s+'
            r'(.{3,2000}?)\s+'
            r'(-?[\d\s]+[.,]\d{2})',
            re.MULTILINE
        )
        for m in pattern.finditer(docx_text):
            try:
                date = parse_date(m.group(1))
                desc = re.sub(r'\s+', ' ', m.group(2)).strip()
                amount = parse_amount(m.group(3))
                if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                if _is_service_line(desc):
                    continue
                cp_final, _ = extract_counterparty_smart(desc, account_name)
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp_final if cp_final else '',
                    'Наименование счета': account_name,
                    'Описание': desc
                })
            except Exception:
                continue
    return result
    # ==================== МАРШРУТИЗАЦИЯ ПАРСЕРОВ ====================

def get_parser_by_ext(account_name: str, ext: str):
    low = account_name.lower()
    is_kapital_saida = ('kapital' in low) or ('saida' in low and 'azn' in low)
    is_wise = ('wise' in low) and ('saida' in low or low.strip() == 'saida_wise' or low.strip() == 'saida wise')

    # ---------- PDF ----------
    if ext == '.pdf':
        if is_kapital_saida:
            return parse_kapital_saida_pdf, 'kapital_saida_pdf'
        if 'regina alfa' in low:
            return parse_regina_alfa_pdf, 'regina_alfa_pdf'
        if 'tinkoff' in low:
            return parse_tinkoff_pdf, 'tinkoff_pdf'
        if 'bluor' in low:
            return parse_bluor_pdf, 'bluor_pdf'
        if 'jenhor' in low or 'unelma' in low:
            # JenHor_Unelma — это Česká spořitelna
            return parse_jenhor_unelma_pdf, 'jenhor_unelma_pdf'
        if 'jenisov' in low or 'jenisovhorska' in low:
            # Jenisov-Horska — это Česká spořitelna (ČSAS)
            return parse_csas_pdf, 'csas_pdf'
        if 'industra' in low or 'plavas' in low or 'kl59' in low or 'p1 statement' in low:
            return parse_industra_pdf, 'industra_pdf'
        if 'mashreq' in low or 'nomiqa' in low:
            return parse_mashreq_pdf, 'mashreq_pdf'
        if 'mkb' in low or 'budapest' in low:
            return parse_mkb_pdf, 'mkb_pdf'
        if 'n26' in low:
            return parse_n26_pdf, 'n26_pdf'
        if 'paysera' in low:
            return parse_paysera_pdf, 'paysera_pdf'
        if 'rak' in low and 'bank' in low:
            return parse_rak_bank_pdf, 'rak_bank_pdf'
        if 'revolut' in low:
            return parse_revolut_pdf, 'revolut_pdf'
        if 'unicredit' in low or 'garpiz' in low or 'twohills' in low \
                or 'koruna' in low or 'b1 estate' in low or 'b1_estate' in low:
            return parse_unicredit_pdf, 'unicredit_pdf'
        if 'wio' in low:
            return parse_wio_pdf, 'wio_pdf'
        if is_wise:
            # Wise — до 'wio' не дойдёт, но на всякий случай
            return parse_wise_pdf, 'wise_pdf'
        if 'pasha' in low or 'bunda' in low:
            return parse_pasha_bank_pdf, 'pasha_bank_pdf'
        # Wise без "saida" в имени (общая проверка)
        if 'wise' in low:
            return parse_wise_pdf, 'wise_pdf'
        return parse_pdf_universal, 'pdf_universal'

    # ---------- DOCX ----------
    if ext == '.docx':
        if 'regina alfa' in low:
            return parse_regina_alfa_docx, 'regina_alfa_docx'
        if 'tinkoff' in low:
            return parse_tinkoff_docx, 'tinkoff_docx'
        if 'jenhor' in low or 'unelma' in low:
            return parse_jenhor_unelma_docx, 'jenhor_unelma_docx'
        if 'n26' in low:
            return parse_n26_docx, 'n26_docx'
        if 'paysera' in low:
            return parse_paysera_docx, 'paysera_docx'
        return parse_docx_universal, 'docx_universal'

    # ---------- XLSX / XLS ----------
    if ext in ('.xlsx', '.xls'):
        if is_kapital_saida:
            return parse_kapital_saida_xlsx, 'kapital_saida_xlsx'
        if 'revolut' in low:
            if 'nb rev' in low or 'nb_rev' in low:
                return parse_revolut_nb, 'revolut_nb'
            if 'plavas' in low:
                return parse_revolut_plavas, 'revolut_plavas'
            return parse_revolut_an14, 'revolut_an14'
        if 'regina alfa' in low:
            return parse_regina_alfa_xlsx, 'regina_alfa_xlsx'
        if 'tinkoff' in low:
            return parse_tinkoff_docx, 'tinkoff_docx'
        if 'bluor' in low:
            if 'kl59' in low:
                return parse_kl59_bluor, 'kl59_bluor'
            if 'bsr' in low and '3' in low:
                return parse_bsr_bluor_3, 'bsr_bluor_3'
            if 'bsr' in low:
                return parse_bsr_bluor_2, 'bsr_bluor_2'
            return parse_kl59_bluor, 'kl59_bluor'
        if 'jenhor' in low or 'unelma' in low:
            return parse_jenhor_unelma_csv, 'jenhor_unelma_csv'
        if 'csob' in low:
            if 'dzibik' in low or 'džibik' in low:
                return parse_dzibik_main_csob, 'dzibik_main_csob'
            if 'jenisov' in low and 'eur' in low:
                return parse_jenisov_csob_eur, 'jenisov_csob_eur'
            if 'jenisov' in low:
                return parse_jenisov_csob_czk, 'jenisov_csob_czk'
            if 'rr strojka' in low and 'eur' in low:
                return parse_rr_strojka_eur_csob, 'rr_strojka_eur_csob'
            if 'rr strojka' in low:
                return parse_rr_strojka_czk_csob, 'rr_strojka_czk_csob'
            if 'rr rev ostr' in low:
                return parse_rr_rev_ostr_csob, 'rr_rev_ostr_csob'
            if 'koruna strojka' in low and 'eur' in low:
                return parse_koruna_strojka_eur_csob, 'koruna_strojka_eur_csob'
            if 'koruna strojka' in low:
                return parse_koruna_strojka_czk_csob, 'koruna_strojka_czk_csob'
            return parse_dzibik_main_csob, 'dzibik_main_csob'
        if 'stalkin' in low or 'fio' in low:
            return parse_stalkin_ml2_fio, 'stalkin_ml2_fio'
        if 'industra' in low or 'plavas' in low or 'p1 statement' in low or 'kl59' in low:
            if 'plavas' in low:
                return parse_industra_plavas1, 'industra_plavas1'
            if 'kl59' in low:
                return parse_industra_kl59, 'industra_kl59'
            return parse_industra_an14, 'industra_an14'
        if 'mashreq' in low or ('nomiqa' in low and 'aed' in low):
            return parse_mashreq, 'mashreq'
        if 'budapest huf' in low or ('mkb' in low and 'huf' in low):
            return parse_budapest_huf_mkb, 'budapest_huf_mkb'
        if 'budapest eur' in low or ('mkb' in low and 'eur' in low):
            return parse_budapest_eur_mkb, 'budapest_eur_mkb'
        if 'mkb' in low or 'budapest' in low:
            return parse_budapest_huf_mkb, 'budapest_huf_mkb'
        if 'saida' in low and 'wise' in low:
            return parse_saida_wise_xlsx, 'saida_wise_xlsx'
        if 'n26' in low:
            return parse_saida_n26_csv, 'saida_n26_csv'
        if 'paysera' in low:
            if 'baltic' in low:
                return parse_paysera_baltic_xlsx, 'paysera_baltic_xlsx'
            if 'sveciy' in low:
                return parse_paysera_sveciy_xlsx, 'paysera_sveciy_xlsx'
            if 'property' in low:
                return parse_paysera_property, 'paysera_property'
            if 'rerum' in low:
                return parse_paysera_rerum, 'paysera_rerum'
            return parse_paysera_baltic_xlsx, 'paysera_baltic_xlsx'
        if 'rak' in low and 'bank' in low:
            return parse_rak_bank, 'rak_bank'
        if 'bunda' in low and 'pasha' in low:
            return parse_pasha_bank_xlsx, 'pasha_bank_xlsx'
        if 'pasha' in low:
            return parse_pasha_bank_xlsx, 'pasha_bank_xlsx'
        if 'unicredit' in low or 'garpiz' in low or 'twohills' in low \
                or 'two hills' in low or 'b1 estate' in low or 'b1_estate' in low:
            if 'b1 estate' in low or 'b1_estate' in low:
                return parse_unicredit_b1, 'unicredit_b1'
            if 'pernink' in low:
                return parse_garpiz_pernink, 'garpiz_pernink'
            if 'garpiz' in low:
                return parse_garpiz_unicredit, 'garpiz_unicredit'
            if 'twohills' in low or 'two hills' in low:
                return parse_twohills_unicredit, 'twohills_unicredit'
            if 'koruna' in low:
                return parse_koruna_unicredit, 'koruna_unicredit'
            return parse_unicredit_b1, 'unicredit_b1'
        if 'wio' in low:
            return parse_wio_business, 'wio_business'
        if 'wise' in low:
            return parse_saida_wise_xlsx, 'saida_wise_xlsx'
        return parse_xlsx_universal, 'xlsx_universal'

    # ---------- CSV ----------
    if ext == '.csv':
        if is_kapital_saida:
            return parse_kapital_saida_azn_csv, 'kapital_saida_azn_csv'
        if 'revolut' in low:
            if 'nb rev' in low or 'nb_rev' in low:
                return parse_revolut_nb, 'revolut_nb'
            if 'plavas' in low:
                return parse_revolut_plavas, 'revolut_plavas'
            return parse_revolut_an14, 'revolut_an14'
        if 'regina alfa' in low:
            return parse_regina_alfa_xlsx, 'regina_alfa_xlsx'
        if 'tinkoff' in low:
            return parse_tinkoff_docx, 'tinkoff_docx'
        if 'bluor' in low:
            if 'kl59' in low:
                return parse_kl59_bluor, 'kl59_bluor'
            if 'bsr' in low and '3' in low:
                return parse_bsr_bluor_3, 'bsr_bluor_3'
            if 'bsr' in low:
                return parse_bsr_bluor_2, 'bsr_bluor_2'
            return parse_kl59_bluor, 'kl59_bluor'
        if 'jenhor' in low or 'unelma' in low:
            return parse_jenhor_unelma_csv, 'jenhor_unelma_csv'
        if 'csob' in low:
            if 'dzibik' in low or 'džibik' in low:
                return parse_dzibik_main_csob, 'dzibik_main_csob'
            if 'jenisov' in low and 'eur' in low:
                return parse_jenisov_csob_eur, 'jenisov_csob_eur'
            if 'jenisov' in low:
                return parse_jenisov_csob_czk, 'jenisov_csob_czk'
            if 'rr strojka' in low and 'eur' in low:
                return parse_rr_strojka_eur_csob, 'rr_strojka_eur_csob'
            if 'rr strojka' in low:
                return parse_rr_strojka_czk_csob, 'rr_strojka_czk_csob'
            if 'rr rev ostr' in low:
                return parse_rr_rev_ostr_csob, 'rr_rev_ostr_csob'
            if 'koruna strojka' in low and 'eur' in low:
                return parse_koruna_strojka_eur_csob, 'koruna_strojka_eur_csob'
            if 'koruna strojka' in low:
                return parse_koruna_strojka_czk_csob, 'koruna_strojka_czk_csob'
            return parse_dzibik_main_csob, 'dzibik_main_csob'
        if 'stalkin' in low or 'fio' in low:
            return parse_stalkin_ml2_fio, 'stalkin_ml2_fio'
        if 'industra' in low or 'plavas' in low or 'p1 statement' in low or 'kl59' in low:
            if 'plavas' in low:
                return parse_industra_plavas1, 'industra_plavas1'
            if 'kl59' in low:
                return parse_industra_kl59, 'industra_kl59'
            return parse_industra_an14, 'industra_an14'
        if 'mashreq' in low or ('nomiqa' in low and 'aed' in low):
            return parse_mashreq, 'mashreq'
        if 'budapest huf' in low or ('mkb' in low and 'huf' in low):
            return parse_budapest_huf_mkb, 'budapest_huf_mkb'
        if 'budapest eur' in low or ('mkb' in low and 'eur' in low):
            return parse_budapest_eur_mkb, 'budapest_eur_mkb'
        if 'mkb' in low or 'budapest' in low:
            return parse_budapest_eur_mkb, 'budapest_eur_mkb'
        if 'saida' in low and 'wise' in low:
            return parse_saida_wise_xlsx, 'saida_wise_xlsx'
        if 'n26' in low:
            return parse_saida_n26_csv, 'saida_n26_csv'
        if 'paysera' in low:
            if 'baltic' in low:
                return parse_paysera_baltic_xlsx, 'paysera_baltic_xlsx'
            if 'sveciy' in low:
                return parse_paysera_sveciy_xlsx, 'paysera_sveciy_xlsx'
            if 'property' in low:
                return parse_paysera_property, 'paysera_property'
            if 'rerum' in low:
                return parse_paysera_rerum, 'paysera_rerum'
            return parse_paysera_baltic_xlsx, 'paysera_baltic_xlsx'
        if 'rak' in low and 'bank' in low:
            return parse_rak_bank, 'rak_bank'
        if 'bunda' in low and 'pasha' in low:
            return parse_pasha_bank_xlsx, 'pasha_bank_csv'
        if 'pasha' in low:
            return parse_pasha_bank_xlsx, 'pasha_bank_csv'
        if 'unicredit' in low or 'garpiz' in low or 'twohills' in low \
                or 'two hills' in low or 'b1 estate' in low or 'b1_estate' in low:
            if 'b1 estate' in low or 'b1_estate' in low:
                return parse_unicredit_b1, 'unicredit_b1'
            if 'pernink' in low:
                return parse_garpiz_pernink, 'garpiz_pernink'
            if 'garpiz' in low:
                return parse_garpiz_unicredit, 'garpiz_unicredit'
            if 'twohills' in low or 'two hills' in low:
                return parse_twohills_unicredit, 'twohills_unicredit'
            if 'koruna' in low:
                return parse_koruna_unicredit, 'koruna_unicredit'
            return parse_unicredit_b1, 'unicredit_b1'
        if 'wio' in low:
            return parse_wio_business, 'wio_business'
        if 'wise' in low:
            return parse_saida_wise_xlsx, 'saida_wise_xlsx'
        return parse_csv_universal, 'csv_universal'

    return None, None


def _get_universal_for_type(real_type: str):
    if real_type == 'pdf':
        return parse_pdf_universal, 'pdf_universal'
    if real_type == 'csv':
        return parse_csv_universal, 'csv_universal'
    if real_type in ('xls', 'xlsx'):
        return parse_xlsx_universal, 'xlsx_universal'
    if real_type == 'docx':
        return parse_docx_universal, 'docx_universal'
    return None, None


def get_parser_chain(account_name: str, real_type: str, filename: str) -> List[Tuple[Callable, str]]:
    chain: List[Tuple[Callable, str]] = []
    seen_keys = set()

    def _add(parser, key):
        if parser is None:
            return
        if key in seen_keys:
            return
        seen_keys.add(key)
        chain.append((parser, key))

    primary_ext = '.' + real_type if real_type and real_type != 'xls' else '.xls'
    if real_type == 'xlsx':
        primary_ext = '.xlsx'
    if real_type == 'xls':
        primary_ext = '.xls'
    if real_type == 'csv':
        primary_ext = '.csv'
    if real_type == 'pdf':
        primary_ext = '.pdf'
    if real_type == 'docx':
        primary_ext = '.docx'

    p, k = get_parser_by_ext(account_name, primary_ext)
    _add(p, k or f'{primary_ext[1:]}_primary')

    other_exts = []
    if real_type != 'pdf':
        other_exts.append('.pdf')
    if real_type != 'csv':
        other_exts.append('.csv')
    if real_type not in ('xls', 'xlsx'):
        other_exts.extend(['.xls', '.xlsx'])
    if real_type != 'docx':
        other_exts.append('.docx')
    for oe in other_exts:
        op, ok = get_parser_by_ext(account_name, oe)
        _add(op, ok or f'{oe[1:]}_other')

    up, uk = _get_universal_for_type(real_type)
    _add(up, uk or f'{real_type}_universal')

    _add(parse_any_format, 'parse_any_format')

    return chain


def parse_file(file_content: bytes, filename: str) -> Tuple[List[Dict], str]:
    raw_account_name = clean_account_name(filename)
    account_name = normalize_account_name(raw_account_name)
    ext = os.path.splitext(filename)[1].lower()
    real_type = _detect_real_type(file_content, ext)
    chain = get_parser_chain(account_name, real_type, filename)

    if not chain:
        return [], f'нет кандидатов для {account_name} ({ext}, real={real_type})'

    tried = []
    errors = []
    for parser, key in chain:
        tried.append(key)
        try:
            tx = parser(file_content, account_name)
        except Exception as e:
            errors.append(f'{key}: {e}')
            continue
        if tx:
            for t in tx:
                t['Наименование счета'] = account_name
            return tx, f'{key} ({account_name}, real={real_type}, {len(tx)} операций)'

    msg = f'all_failed: {tried}'
    if errors:
        msg += f' | errors: {errors}'
    return [], msg


# ==================== СВОДКА ПО СЧЕТАМ ====================

def build_account_summary(rows: List[Dict]) -> pd.DataFrame:
    columns = [
        "Наименование банка",
        "Количество приходных операций",
        "Сумма приходных операций",
        "Количество расходных операций",
        "Сумма расходных операций",
        "Сальдо операций",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows)
    bank_col = None
    if "Наименование банка" in df.columns:
        bank_col = "Наименование банка"
    elif "Наименование счета" in df.columns:
        bank_col = "Наименование счета"
    else:
        return pd.DataFrame(columns=columns)

    if "Сумма" not in df.columns:
        return pd.DataFrame(columns=columns)

    df = df.copy()
    df["Сумма"] = df["Сумма"].map(to_float_amount)
    df[bank_col] = _safe_str_series(df[bank_col])

    mask_reasonable = df["Сумма"].abs() < MAX_REASONABLE_AMOUNT
    df = df[mask_reasonable].copy()

    if df.empty:
        return pd.DataFrame(columns=columns)

    df["_income"] = df["Сумма"] > 0
    df["_expense"] = df["Сумма"] < 0
    df["_income_sum"] = df["Сумма"].where(df["_income"], 0.0)
    df["_expense_sum"] = (-df["Сумма"]).where(df["_expense"], 0.0)

    grouped = df.groupby(bank_col, dropna=False)

    summary = pd.DataFrame({
        "Количество приходных операций": grouped["_income"].sum().astype(int),
        "Сумма приходных операций": grouped["_income_sum"].sum(),
        "Количество расходных операций": grouped["_expense"].sum().astype(int),
        "Сумма расходных операций": grouped["_expense_sum"].sum(),
    }).reset_index()
    summary = summary.rename(columns={bank_col: "Наименование банка"})

    summary["Сальдо операций"] = (
        summary["Сумма приходных операций"].astype(float)
        - summary["Сумма расходных операций"].astype(float)
    )
    summary = summary.sort_values("Наименование банка").reset_index(drop=True)

    summary["Сумма приходных операций"] = summary["Сумма приходных операций"].astype(float).round(2)
    summary["Сумма расходных операций"] = summary["Сумма расходных операций"].astype(float).round(2)
    summary["Сальдо операций"] = summary["Сальдо операций"].astype(float).round(2)

    return summary[columns]


# ==================== ЭКСПОРТ В EXCEL ====================

_NUMERIC_FMT = '# ##0.00'
_INT_FMT = '# ##0'
_HEADER_FILL = PatternFill(start_color='1B5E20', end_color='1B5E20', fill_type='solid')
_HEADER_FONT = Font(color='FFFFFF', bold=True, size=11)
_THIN = Side(border_style='thin', color='C8E6C9')
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _autosize_worksheet(ws, max_width=60):
    for col_idx, col_cells in enumerate(ws.iter_cols(), start=1):
        max_len = 0
        for cell in col_cells:
            v = cell.value
            if v is None:
                continue
            s = str(v)
            if len(s) > max_len:
                max_len = len(s)
        w = min(max_len + 2, max_width)
        if w < 10:
            w = 10
        ws.column_dimensions[get_column_letter(col_idx)].width = w


def _write_operations_sheet(ws, df_export: pd.DataFrame):
    for j, col_name in enumerate(df_export.columns, start=1):
        c = ws.cell(row=1, column=j, value=col_name)
        c.fill = _HEADER_FILL
        c.font = _HEADER_FONT
        c.alignment = Alignment(horizontal='left', vertical='center')
        c.border = _BORDER

    sum_col_idx = None
    for j, col_name in enumerate(df_export.columns, start=1):
        if col_name == 'Сумма':
            sum_col_idx = j
            break

    for i, row in enumerate(df_export.itertuples(index=False), start=2):
        for j, value in enumerate(row, start=1):
            c = ws.cell(row=i, column=j, value=value)
            c.border = _BORDER
            c.alignment = Alignment(horizontal='left', vertical='top', wrap_text=False)
            if sum_col_idx is not None and j == sum_col_idx:
                try:
                    c.value = float(value)
                    c.number_format = _NUMERIC_FMT
                    c.alignment = Alignment(horizontal='right', vertical='top')
                except Exception:
                    pass

    ws.freeze_panes = 'A2'
    _autosize_worksheet(ws)


def _write_summary_sheet(ws, summary_df: pd.DataFrame):
    for j, col_name in enumerate(summary_df.columns, start=1):
        c = ws.cell(row=1, column=j, value=col_name)
        c.fill = _HEADER_FILL
        c.font = _HEADER_FONT
        c.alignment = Alignment(horizontal='left', vertical='center')
        c.border = _BORDER

    sum_cols = {
        "Сумма приходных операций",
        "Сумма расходных операций",
        "Сальдо операций",
    }
    cnt_cols = {
        "Количество приходных операций",
        "Количество расходных операций",
    }

    for i, row in enumerate(summary_df.itertuples(index=False), start=2):
        for j, value in enumerate(row, start=1):
            col_name = summary_df.columns[j - 1]
            c = ws.cell(row=i, column=j, value=value)
            c.border = _BORDER
            c.alignment = Alignment(horizontal='left', vertical='top')
            if col_name in sum_cols:
                try:
                    c.value = float(value)
                    c.number_format = _NUMERIC_FMT
                    c.alignment = Alignment(horizontal='right', vertical='top')
                except Exception:
                    pass
            elif col_name in cnt_cols:
                try:
                    c.value = int(value)
                    c.number_format = _INT_FMT
                    c.alignment = Alignment(horizontal='right', vertical='top')
                except Exception:
                    pass

    ws.freeze_panes = 'A2'
    _autosize_worksheet(ws)


def build_operations_excel(df_display: pd.DataFrame, df_numeric: pd.DataFrame) -> BytesIO:
    output = BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = 'Транзакции'

    if 'Наименование банка' in df_numeric.columns:
        bank_series = df_numeric['Наименование банка']
    elif 'Наименование счета' in df_numeric.columns:
        bank_series = df_numeric['Наименование счета']
    else:
        bank_series = pd.Series([''] * len(df_numeric), index=df_numeric.index)

    df_export = pd.DataFrame({
        'Дата': _safe_str_series(df_numeric['Дата']),
        'Сумма': pd.to_numeric(df_numeric['Сумма'], errors='coerce').fillna(0.0).astype(float),
        'Контрагент': _safe_str_series(df_numeric.get('Контрагент', pd.Series([''] * len(df_numeric), index=df_numeric.index))),
        'Наименование банка': _safe_str_series(bank_series),
        'Описание': _safe_str_series(df_display.get('Описание', pd.Series([''] * len(df_numeric), index=df_numeric.index))),
    })
    _write_operations_sheet(ws, df_export)

    wb.save(output)
    output.seek(0)
    return output


def build_summary_excel(summary_df: pd.DataFrame) -> BytesIO:
    output = BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = 'Сводка по счетам'
    _write_summary_sheet(ws, summary_df)
    wb.save(output)
    output.seek(0)
    return output


def build_combined_excel(df_display: pd.DataFrame,
                         df_numeric: pd.DataFrame,
                         summary_df: pd.DataFrame,
                         ai_df: Optional[pd.DataFrame] = None) -> BytesIO:
    output = BytesIO()
    wb = Workbook()
    ws1 = wb.active
    ws1.title = 'Транзакции'

    if 'Наименование банка' in df_numeric.columns:
        bank_series = df_numeric['Наименование банка']
    elif 'Наименование счета' in df_numeric.columns:
        bank_series = df_numeric['Наименование счета']
    else:
        bank_series = pd.Series([''] * len(df_numeric), index=df_numeric.index)

    df_export = pd.DataFrame({
        'Дата': _safe_str_series(df_numeric['Дата']),
        'Сумма': pd.to_numeric(df_numeric['Сумма'], errors='coerce').fillna(0.0).astype(float),
        'Контрагент': _safe_str_series(df_numeric.get('Контрагент', pd.Series([''] * len(df_numeric), index=df_numeric.index))),
        'Наименование банка': _safe_str_series(bank_series),
        'Описание': _safe_str_series(df_display.get('Описание', pd.Series([''] * len(df_numeric), index=df_numeric.index))),
    })
    _write_operations_sheet(ws1, df_export)
    ws2 = wb.create_sheet('Сводка по счетам')
    _write_summary_sheet(ws2, summary_df)

    if ai_df is not None and not ai_df.empty:
        ws3 = wb.create_sheet('AI-обогащение')
        for j, col_name in enumerate(ai_df.columns, start=1):
            c = ws3.cell(row=1, column=j, value=col_name)
            c.fill = _HEADER_FILL
            c.font = _HEADER_FONT
            c.alignment = Alignment(horizontal='left', vertical='center')
            c.border = _BORDER
        for i, row in enumerate(ai_df.itertuples(index=False), start=2):
            for j, value in enumerate(row, start=1):
                c = ws3.cell(row=i, column=j, value=value)
                c.border = _BORDER
                c.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
        ws3.freeze_panes = 'A2'
        _autosize_worksheet(ws3)

    wb.save(output)
    output.seek(0)
    return output


# ==================== ОБРАБОТКА ЗАГРУЖЕННЫХ ФАЙЛОВ ====================

def _files_signature(uploaded_files) -> str:
    h = hashlib.md5()
    for uf in uploaded_files:
        try:
            h.update(uf.name.encode('utf-8', errors='ignore'))
            h.update(str(getattr(uf, 'size', 0)).encode('utf-8', errors='ignore'))
        except Exception:
            pass
    return h.hexdigest()


def _process_uploaded_files(uploaded_files) -> Dict:
    all_tx: List[Dict] = []
    failed: List[str] = []
    file_stats: List[str] = []
    debug_info: List[str] = []

    seen_hashes: Dict[str, str] = {}
    skipped_dupes: List[str] = []

    progress = st.progress(0)
    status = st.empty()

    for i, uf in enumerate(uploaded_files):
        status.text(f"Обработка: {uf.name}")
        try:
            content = uf.read()
            if not content:
                file_stats.append(f"ℹ️ {uf.name}: пустой файл")
                progress.progress((i + 1) / max(1, len(uploaded_files)))
                continue

            h = hashlib.md5(content).hexdigest()
            if h in seen_hashes:
                skipped_dupes.append(f"{uf.name} (дубликат {seen_hashes[h]})")
                file_stats.append(f"⏭️ {uf.name}: дубликат {seen_hashes[h]}, пропущен")
                progress.progress((i + 1) / max(1, len(uploaded_files)))
                continue
            seen_hashes[h] = uf.name

            tx, parser_name = parse_file(content, uf.name)
            raw_account_name = clean_account_name(uf.name)
            account_name = normalize_account_name(raw_account_name)

            debug_info.append(
                f"🔍 `{uf.name}` → сырое имя: `{raw_account_name}` → "
                f"нормализовано: `{account_name}` → "
                f"парсер: `{parser_name}` → **{len(tx)}** операций"
            )

            if tx:
                all_tx.extend(tx)
                file_stats.append(f"✅ {uf.name}: {len(tx)} операций → {account_name}")
            else:
                ext_low = os.path.splitext(uf.name)[1].lower()
                is_service_file = False
                if 'bluor' in account_name.lower() and ext_low in ('.csv', '.xls', '.xlsx'):
                    raw = read_text_with_encoding(content)
                    if raw and 'начальный остаток' in raw.lower() and 'дебет (d)' in raw.lower():
                        is_service_file = True
                if is_service_file:
                    file_stats.append(f"ℹ️ {uf.name}: служебный файл (только остатки), операций нет")
                    debug_info.append(
                        f"ℹ️ `{uf.name}`: файл содержит только остатки, операций нет."
                    )
                else:
                    file_stats.append(f"ℹ️ {uf.name}: транзакций не найдено")
                    try:
                        raw_txt = ''
                        if ext_low == '.pdf' or content[:4] == b'%PDF':
                            raw_txt = pdf_all_text(content)
                        elif ext_low == '.docx' or (content[:2] == b'PK' and b'word/' in content[:4096]):
                            raw_txt = docx_all_text(content)
                        else:
                            raw_txt = read_text_with_encoding(content)
                        debug_info.append(
                            f"⚠️ `{uf.name}`: 0 операций. Первые 2000 символов сырого текста:\n"
                            f"```\n{raw_txt[:2000]}\n```"
                        )
                    except Exception as e:
                        debug_info.append(f"⚠️ `{uf.name}`: 0 операций, не удалось получить сырой текст: {e}")

        except Exception as e:
            failed.append(f"{uf.name} (ошибка: {e})")
            debug_info.append(f"❌ `{uf.name}` → исключение: {e}\n{traceback.format_exc()[:1000]}")

        progress.progress((i + 1) / max(1, len(uploaded_files)))

    if skipped_dupes:
        debug_info.append("⏭️ Пропущены дубликаты: " + "; ".join(skipped_dupes))

    status.text("✅ Обработка завершена!")

    return {
        'all_tx': all_tx,
        'failed': failed,
        'file_stats': file_stats,
        'debug_info': debug_info,
    }


# ==================== РЕНДЕР РЕЗУЛЬТАТОВ ====================

def _render_results(result: Dict):
    all_tx = result.get('all_tx', [])
    failed = result.get('failed', [])
    file_stats = result.get('file_stats', [])
    debug_info = result.get('debug_info', [])

    st.markdown("### 📋 Результат обработки")
    for s in file_stats:
        st.info(s)

    with st.expander("🔧 Техническая информация"):
        for line in debug_info:
            st.markdown(line)

    if not all_tx:
        if failed:
            st.warning(f"⚠️ Не удалось обработать: {len(failed)} файлов")
            for f in failed:
                st.write(f"- {f}")
        else:
            st.info("Операции не найдены. Проверьте формат файлов.")
        return

    try:
        df_raw = pd.DataFrame(all_tx)
    except Exception as e:
        st.error(f"Ошибка при построении DataFrame: {e}")
        return

    if df_raw.empty:
        st.info("Нет данных.")
        return

    for col in df_raw.columns:
        if col == 'Сумма':
            continue
        try:
            if df_raw[col].dtype == object:
                df_raw[col] = _safe_str_series(df_raw[col])
        except Exception:
            df_raw[col] = _safe_str_series(df_raw[col])

    try:
        df_raw['Сумма_число'] = df_raw['Сумма'].map(to_float_amount).astype(float)
    except Exception:
        df_raw['Сумма_число'] = 0.0

    if 'Наименование счета' in df_raw.columns and 'Наименование банка' not in df_raw.columns:
        df_raw = df_raw.rename(columns={'Наименование счета': 'Наименование банка'})

    income = float(df_raw['Сумма_число'][df_raw['Сумма_число'] > 0].sum())
    expense = float(abs(df_raw['Сумма_число'][df_raw['Сумма_число'] < 0].sum()))

    date_series = _safe_str_series(df_raw['Дата']) if 'Дата' in df_raw.columns \
        else pd.Series([''] * len(df_raw), index=df_raw.index)
    sum_series = df_raw['Сумма_число'].astype(float)

    if 'Контрагент' in df_raw.columns:
        counterparty_series = _safe_str_series(df_raw['Контрагент'])
    else:
        counterparty_series = pd.Series([''] * len(df_raw), index=df_raw.index)

    if 'Наименование банка' in df_raw.columns:
        bank_series = _safe_str_series(df_raw['Наименование банка'])
    elif 'Наименование счета' in df_raw.columns:
        bank_series = _safe_str_series(df_raw['Наименование счета'])
    else:
        bank_series = pd.Series([''] * len(df_raw), index=df_raw.index)

    if 'Описание' in df_raw.columns:
        desc_series = _safe_str_series(df_raw['Описание'])
    else:
        desc_series = pd.Series([''] * len(df_raw), index=df_raw.index)

    df_numeric = pd.DataFrame({
        'Дата': date_series.values,
        'Сумма': sum_series.values,
        'Контрагент': counterparty_series.values,
        'Наименование банка': bank_series.values,
        'Описание': desc_series.values,
    }, index=df_raw.index)

    df_display = df_raw.drop(columns=['Сумма_число'], errors='ignore').copy()
    df_display['Сумма'] = df_raw['Сумма_число'].apply(format_amount)
    if 'Описание' in df_display.columns:
        df_display['Описание'] = df_display['Описание'].apply(
            lambda x: translate_description_inline(_to_scalar_str(x))
        )

    st.session_state['df_numeric'] = df_numeric
    st.session_state['df_display'] = df_display
    st.session_state['df_raw'] = df_raw

    st.markdown("---")
    st.markdown("### 📊 Итоги")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("📊 Всего операций", len(df_raw))
    with c2:
        st.metric("📈 Доходы", format_amount(income))
    with c3:
        st.metric("📉 Расходы", format_amount(expense))

    st.markdown("---")
    st.markdown("### 🤖 AI-обогащение транзакций (DeepSeek AI)")
    st.caption(
        "AI переведёт описания, определит категорию и вытащит чистое имя "
        "контрагента. Обрабатывается не более 200 строк за раз."
    )

    col_ai1, col_ai2 = st.columns([1, 3])
    with col_ai1:
        ai_run = st.button("🚀 Обогатить через AI", key="ai_enrich_btn")
    with col_ai2:
        ai_limit = st.slider(
            "Сколько строк обработать", min_value=10, max_value=200, value=50, step=10,
            key="ai_limit_slider"
        )

    if ai_run:
        with st.spinner("DeepSeek AI обрабатывает транзакции..."):
            tx_list = df_raw.to_dict('records')
            progress_bar = st.progress(0)

            def _cb(done, total):
                try:
                    progress_bar.progress(min(done / max(total, 1), 1.0))
                except Exception:
                    pass

            enriched, ai_errors = ai_enrich_transactions(
                tx_list, max_items=ai_limit, progress_callback=_cb
            )
            st.session_state['ai_enriched'] = enriched
            st.session_state['ai_errors'] = ai_errors
            if ai_errors:
                st.warning(f"Ошибки AI: {len(ai_errors)}. Первые 3: {ai_errors[:3]}")
            else:
                st.success("AI-обогащение завершено!")

    ai_enriched = st.session_state.get('ai_enriched')
    if ai_enriched:
        ai_rows = []
        for tx in ai_enriched:
            if tx.get('_ai_translation') or tx.get('_ai_category'):
                ai_rows.append({
                    'Дата': _to_scalar_str(tx.get('Дата', '')),
                    'Сумма': tx.get('Сумма', 0),
                    'Банк': _to_scalar_str(tx.get('Наименование банка', tx.get('Наименование счета', ''))),
                    'Оригинал': _to_scalar_str(tx.get('Описание', '')),
                    'Перевод AI': _to_scalar_str(tx.get('_ai_translation', '')),
                    'Категория AI': _to_scalar_str(tx.get('_ai_category', '')),
                    'Контрагент AI': _to_scalar_str(tx.get('_ai_counterparty_clean', '')),
                    'Банк. комиссия': bool(tx.get('_ai_is_bank_fee', False)),
                    'Уверенность': tx.get('_ai_confidence', 0.0),
                })
        if ai_rows:
            try:
                ai_df = pd.DataFrame(ai_rows)
                st.dataframe(ai_df, use_container_width=True, hide_index=True)
                st.session_state['ai_df'] = ai_df
            except Exception as e:
                st.warning(f"Не удалось отобразить AI-таблицу: {e}")
        else:
            st.info("AI не вернул данных по этим строкам.")

    st.markdown("---")
    st.markdown("### 🧾 Детализация транзакций")
    try:
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Ошибка отображения таблицы: {e}")

    st.markdown("---")
    st.markdown("### 📁 Сводка по счетам")
    try:
        summary_df = build_account_summary(df_raw.to_dict('records'))
    except Exception as e:
        st.error(f"Ошибка построения сводки: {e}")
        summary_df = pd.DataFrame()

    if summary_df.empty:
        st.info("Нет данных для сводки по счетам.")
    else:
        summary_html_df = summary_df.copy()
        for col in ["Сумма приходных операций", "Сумма расходных операций", "Сальдо операций"]:
            summary_html_df[col] = summary_html_df[col].apply(format_amount)
        try:
            st.markdown(
                f'<div class="summary-table">{summary_html_df.to_html(index=False, escape=False)}</div>',
                unsafe_allow_html=True,
            )
        except Exception as e:
            st.error(f"Ошибка отображения сводки: {e}")

    st.markdown("---")
    st.markdown("### 💾 Сохранить результат")
    st.markdown(
        "Скачайте **отдельно операции по выпискам** и **отдельно сводную таблицу**, "
        "или всё вместе одним файлом. В Excel суммы — числа с форматом `0,00`."
    )

    try:
        ops_excel = build_operations_excel(df_display, df_numeric)
    except Exception as e:
        st.error(f"Не удалось собрать Excel с операциями: {e}")
        ops_excel = None

    try:
        summary_excel = build_summary_excel(summary_df) if not summary_df.empty else None
    except Exception as e:
        st.error(f"Не удалось собрать Excel со сводкой: {e}")
        summary_excel = None

    ai_df_for_excel = st.session_state.get('ai_df')
    try:
        combined_excel = build_combined_excel(df_display, df_numeric, summary_df, ai_df_for_excel) \
            if not summary_df.empty else None
    except Exception as e:
        st.error(f"Не удалось собрать комбинированный Excel: {e}")
        combined_excel = None

    dl1, dl2, dl3 = st.columns(3)

    with dl1:
        if ops_excel is not None:
            st.download_button(
                label="📥 Скачать операции по выпискам",
                data=ops_excel,
                file_name="операции_по_выпискам.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_operations_only",
            )

    with dl2:
        if summary_excel is not None:
            st.download_button(
                label="📊 Скачать сводную таблицу",
                data=summary_excel,
                file_name="сводка_по_счетам.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_summary_only",
            )
        else:
            st.button(
                "📊 Сводная таблица пуста",
                disabled=True,
                key="summary_empty_btn",
            )

    with dl3:
        if combined_excel is not None:
            st.download_button(
                label="📦 Скачать всё одним файлом",
                data=combined_excel,
                file_name="анализ_банковских_выписок.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_combined",
            )
        elif ops_excel is not None:
            st.download_button(
                label="📦 Скачать всё одним файлом",
                data=ops_excel,
                file_name="анализ_банковских_выписок.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_combined_ops_only",
            )

    if failed:
        st.warning(f"⚠️ Не удалось обработать: {len(failed)} файлов")
        for f in failed:
            st.write(f"- {f}")


# ==================== AI-АССИСТЕНТ ====================

def _render_ai_assistant_tab():
    st.markdown("### 🤖 AI-ассистент (DeepSeek AI)")
    st.caption(
        "Задавайте вопросы по коду, данным и обработке выписок. "
        "Ассистент видит только то, что вы ему напишете — файлы не отправляются автоматически."
    )

    client = _get_hf_client()
    if client is None:
        if not _OPENAI_SDK_AVAILABLE:
            st.markdown(
                '<span class="ai-status-warn">⚠️ Библиотека openai не установлена. '
                'Выполните: <code>pip install openai</code></span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<span class="ai-status-warn">⚠️ DeepSeek-токен не задан или неверен. '
                'Проверьте <code>HF_TOKEN</code> в <code>.streamlit/secrets.toml</code></span>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<span class="ai-status-ok">✅ DeepSeek AI подключён</span>',
            unsafe_allow_html=True,
        )

    with st.expander("🔑 Настройка DeepSeek-токена", expanded=(client is None)):
        st.markdown(
            "Токен хранится в `.streamlit/secrets.toml`:\n\n"
            "```toml\nHF_TOKEN = \"hf_...\"\n```\n\n"
            "Или введите здесь — он сохранится только в текущей сессии."
        )
        key_input = st.text_input(
            "DeepSeek-токен",
            value=st.session_state.get('hf_token', ''),
            type='password',
            key='hf_token_input',
        )
        if st.button("💾 Сохранить токен в сессии", key='save_hf_token'):
            st.session_state['hf_token'] = key_input.strip()
            st.success("Токен сохранён в сессии.")
            st.rerun()

    st.markdown("---")

    model_choice = st.selectbox(
        "Модель",
        options=[HF_DEFAULT_MODEL, HF_REASONER_MODEL],
        index=0,
        key='hf_model_choice',
        help="DeepSeek-V3 — быстрая; DeepSeek-R1 — для отладки кода.",
    )

    st.markdown("**Быстрые действия:**")
    qc1, qc2, qc3, qc4 = st.columns(4)
    quick_prompt = None
    with qc1:
        if st.button("🐞 Помоги отладить", key='quick_debug'):
            quick_prompt = (
                "Помоги отладить программу анализа банковских выписок. "
                "Опиши, как найти проблему, если парсер возвращает 0 операций."
            )
    with qc2:
        if st.button("📊 Анализ данных", key='quick_data'):
            quick_prompt = (
                "У меня есть DataFrame с колонками: Дата, Сумма, Контрагент, "
                "Наименование банка, Описание. Как найти аномалии и подозрительные операции?"
            )
    with qc3:
        if st.button("🎨 Улучшить UI", key='quick_ui'):
            quick_prompt = (
                "Как улучшить интерфейс Streamlit-приложения для аналитика "
                "банковских выписок? Предложи 5 конкретных идей."
            )
    with qc4:
        if st.button("🧹 Очистить чат", key='quick_clear'):
            st.session_state['ai_chat_history'] = []
            st.rerun()

    if 'ai_chat_history' not in st.session_state:
        st.session_state['ai_chat_history'] = []

    context_parts = [
        "Ты — ассистент внутри Streamlit-приложения 'Аналитик банковских выписок'. "
        "Приложение парсит CSV, XLSX, XLS, DOCX, PDF выписки банков (ČSOB, UniCredit, "
        "Revolut, Tinkoff, Kapital bank, MASHREQ, Pasha Bank, WIO, Paysera, MKB, BluOr и др.), "
        "сводит операции в единый DataFrame и экспортирует в Excel.",
        "Структура DataFrame: Дата (str), Сумма (float, + доход, - расход), Контрагент (str), "
        "Наименование банка (str), Описание (str).",
        "Если пользователь спрашивает про код — давай конкретные фрагменты на Python.",
    ]
    df_numeric = st.session_state.get('df_numeric')
    if df_numeric is not None and not df_numeric.empty:
        try:
            n = len(df_numeric)
            income = df_numeric[df_numeric['Сумма'] > 0]['Сумма'].sum()
            expense = df_numeric[df_numeric['Сумма'] < 0]['Сумма'].sum()
            bank_col = 'Наименование банка' if 'Наименование банка' in df_numeric.columns else 'Наименование счета'
            accounts = df_numeric[bank_col].nunique()
            context_parts.append(
                f"Текущие данные пользователя: {n} операций, "
                f"доходы {income:.2f}, расходы {expense:.2f}, счетов: {accounts}."
            )
        except Exception:
            pass
    system_prompt = "\n".join(context_parts)

    for msg in st.session_state['ai_chat_history']:
        if msg['role'] == 'user':
            st.markdown(
                f'<div class="ai-chat-bubble-user"><b>Вы:</b><br>{msg["content"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="ai-chat-bubble-assistant"><b>AI:</b><br>'
                f'{msg["content"]}</div>',
                unsafe_allow_html=True,
            )

    if quick_prompt:
        st.session_state['ai_chat_history'].append({'role': 'user', 'content': quick_prompt})
        with st.spinner("DeepSeek AI думает..."):
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(st.session_state['ai_chat_history'])
            answer, err = call_ai(messages, model=model_choice)
        if err:
            st.session_state['ai_chat_history'].append({'role': 'assistant', 'content': f"❌ {err}"})
        else:
            st.session_state['ai_chat_history'].append({'role': 'assistant', 'content': answer})
        st.rerun()

    user_input = st.chat_input("Спросите DeepSeek о коде, данных или обработке...")
    if user_input:
        st.session_state['ai_chat_history'].append({'role': 'user', 'content': user_input})
        with st.spinner("DeepSeek AI думает..."):
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(st.session_state['ai_chat_history'])
            answer, err = call_ai(messages, model=model_choice)
        if err:
            st.session_state['ai_chat_history'].append({'role': 'assistant', 'content': f"❌ {err}"})
        else:
            st.session_state['ai_chat_history'].append({'role': 'assistant', 'content': answer})
        st.rerun()

    with st.expander("📎 Отправить фрагмент кода на ревью"):
        code_snippet = st.text_area(
            "Вставьте код или ошибку",
            height=200,
            key='ai_code_snippet',
            placeholder="def my_parser(...): ...\n\n# или\n\nTraceback (most recent call last): ...",
        )
        if st.button("🔍 Разобрать", key='ai_review_code'):
            if code_snippet.strip():
                with st.spinner("DeepSeek анализирует..."):
                    messages = [
                        {"role": "system", "content": _AI_DEBUG_SYSTEM},
                        {"role": "user", "content": code_snippet},
                    ]
                    answer, err = call_ai(messages, model=model_choice, max_tokens=3000)
                if err:
                    st.error(err)
                else:
                    st.markdown("**Ответ AI:**")
                    st.markdown(answer)
                    st.session_state['ai_chat_history'].append(
                        {'role': 'user', 'content': f"[Фрагмент кода]\n{code_snippet[:500]}"}
                    )
                    st.session_state['ai_chat_history'].append(
                        {'role': 'assistant', 'content': answer}
                    )


# ==================== ИНТЕРФЕЙС ====================

def main():
    if 'processing_result' not in st.session_state:
        st.session_state['processing_result'] = None
    if 'files_signature' not in st.session_state:
        st.session_state['files_signature'] = None
    if 'uploader_key' not in st.session_state:
        st.session_state['uploader_key'] = 0
    if 'ai_chat_history' not in st.session_state:
        st.session_state['ai_chat_history'] = []

    with st.sidebar:
        st.markdown("### ⚙️ Настройки")
        st.markdown("**DeepSeek AI**")
        client = _get_hf_client()
        if client is not None:
            st.success("✅ Подключён")
        else:
            st.warning("⚠️ Не подключён")
            st.caption("Проверьте DeepSeek-токен во вкладке «AI-ассистент».")
        st.markdown("---")
        st.caption(
            "Программа работает локально. Файлы выписок не отправляются в DeepSeek — "
            "только те фрагменты, которые вы сами вводите в чат."
        )

    tab_upload, tab_ai = st.tabs(["📥 Обработка выписок", "🤖 AI-ассистент"])

    with tab_upload:
        st.markdown("### 📥 Загрузка файлов")
        st.markdown("Перетащите выписки в окно ниже или нажмите **Выбрать файлы**.")

        col_reset, col_info = st.columns([1, 4])
        with col_reset:
            reset_clicked = st.button("🔄 Сбросить файлы", key="reset_btn")
        with col_info:
            if reset_clicked:
                st.session_state['processing_result'] = None
                st.session_state['files_signature'] = None
                st.session_state['uploader_key'] += 1
                st.rerun()

        uploader_key = f"file_uploader_{st.session_state['uploader_key']}"
        uploaded_files = st.file_uploader(
            "Выберите файлы",
            type=['csv', 'xlsx', 'xls', 'docx', 'pdf'],
            accept_multiple_files=True,
            label_visibility="collapsed",
            key=uploader_key,
        )

        if not uploaded_files:
            st.session_state['processing_result'] = None
            st.session_state['files_signature'] = None

            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("""
                <div class="info-card">
                <div class="info-card-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="#1B5E20" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                </div>
                <div class="info-card-text"><h4>Поддержка форматов</h4><p>CSV, XLSX, XLS, DOCX, PDF</p></div>
                </div>
                """, unsafe_allow_html=True)
            with c2:
                st.markdown("""
                <div class="info-card">
                <div class="info-card-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M3 12h4l3-9 4 18 3-9h4" stroke="#1B5E20" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                </div>
                <div class="info-card-text"><h4>Перевод в скобках</h4><p>EN / CS / LV / HU → RU, оригинал сохраняется</p></div>
                </div>
                """, unsafe_allow_html=True)
            with c3:
                st.markdown("""
                <div class="info-card">
                <div class="info-card-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2a10 10 0 100 20 10 10 0 000-20zM2 12h20M12 2a15 15 0 010 20M12 2a15 15 0 000 20" stroke="#1B5E20" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                </div>
                <div class="info-card-text"><h4>DeepSeek AI</h4><p>Перевод, категории, отладка кода</p></div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("""
            <div class="footer-note">
            Работает локально. Данные никуда не отправляются.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("---")
            st.markdown(f"**Загружено файлов:** {len(uploaded_files)}")

            current_sig = _files_signature(uploaded_files)

            col_btn, col_hint = st.columns([1, 3])
            with col_btn:
                process_clicked = st.button("🚀 Обработать файлы", key="process_btn")
            with col_hint:
                if st.session_state['processing_result'] is not None:
                    st.caption("Результат готов. Можно скачивать файлы; повторное нажатие «Обработать» перезапустит разбор.")

            need_process = False
            if process_clicked:
                if st.session_state['processing_result'] is None:
                    need_process = True
                elif st.session_state['files_signature'] != current_sig:
                    need_process = True
                else:
                    need_process = False
                    st.info("Файлы не изменились — использую уже готовый результат.")

            if need_process:
                result = _process_uploaded_files(uploaded_files)
                st.session_state['processing_result'] = result
                st.session_state['files_signature'] = current_sig

            if st.session_state['processing_result'] is not None:
                st.markdown("---")
                _render_results(st.session_state['processing_result'])

        st.markdown("""
        <div class="footer-note">
        Работает локально. Данные никуда не отправляются.
        </div>
        """, unsafe_allow_html=True)

    with tab_ai:
        _render_ai_assistant_tab()


if __name__ == "__main__":
    main()
