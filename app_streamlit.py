# -*- coding: utf-8 -*-
"""
app.py — Аналитик банковских выписок.
Полная рабочая версия + интеграция DeepSeek AI.

FIX-пакет v4:
  [FIX-SYNTAX-MASHREQ]        — устранена слипшаяся строка
  [FIX-TRANSLATE-FULL]        — многословные фразы переводятся ПОЛНОСТЬЮ
  [FIX-TRANSLATE-WORDBOUND]   — перевод слов только по границам слова
  [FIX-TRANSLATE-CLEAN]       — перевод не попадает внутрь оригинала
  [FIX-TRANSLATE-LV-V4]       — расширены латвийский/чешский/венгерский словари
  [FIX-BG-BASE64]             — фон: SVG в base64
  [FIX-BUTTONS-SMALL]         — уменьшен шрифт кнопок
  [FIX-COUNTERPARTY-2]        — чистка имени контрагента
  [FIX-COUNTERPARTY-FULL-V4]  — ПРИОРИТЕТ Beneficiary/Payer, полные имена Revolut/Paysera/Industra
  [NEW-NORMALIZE-ACCOUNT]     — приведение наименований счетов к эталону
  [NEW-GORODETS-TEA]          — фон: городецкая роспись
  [NEW-TRANSLATE-INLINE]      — Оригинал + (перевод) в одной ячейке
  [NEW-AMOUNT-FORMAT]         — Суммы на экране: 1 234,56
  [NEW-EXCEL-NUMERIC]         — В Excel суммы — числа с форматом # ##0.00
  [FIX-KAPITAL-XLSX]          — Kapital bank Saida AZN (XLSX)
  [FIX-KAPITAL-PDF]           — Kapital bank (PDF)
  [FIX-KAPITAL-DOCX-ERROR]    — Исправлена ошибка парсера DOCX
  [FIX-UI-RUSSIAN]            — Русский текст везде
  [FIX-RENAME-COLUMN-V4]      — "Наименование счета" → "Наименование банка"
  [DEEPSEEK-INTEGRATION]      — AI-ассистент DeepSeek
"""

import streamlit as st
import pandas as pd
import os
import re
import hashlib
import csv
import base64
import json
import streamlit.components.v1 as components
from datetime import datetime
from io import BytesIO, StringIO
from typing import Dict, List, Tuple, Callable, Optional
from docx import Document
import pdfplumber

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


# ==================== [NEW-GORODETS-TEA] ФОН ====================

_GORODETS_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='520' height='460'>"
    "<defs><pattern id='gorodets' x='0' y='0' width='520' height='460' "
    "patternUnits='userSpaceOnUse'>"
    "<g opacity='0.55'>"
    "<g fill='none' stroke='#2C3E50' stroke-width='2' stroke-linecap='round'>"
    "<path d='M10 380 Q120 320 240 360 Q360 400 510 340'/>"
    "<path d='M5 120 Q90 70 190 100 Q290 130 390 90 Q470 55 520 85'/>"
    "<path d='M60 250 Q160 210 260 245 Q360 280 460 240'/>"
    "<path d='M0 445 Q130 415 260 440 Q400 465 520 430'/>"
    "</g>"
    "<g fill='#43A047' stroke='#1B5E20' stroke-width='1.6'>"
    "<path d='M120 350 q18 -28 46 -18 q-4 26 -24 34 q-24 10 -22 -16 z'/>"
    "<path d='M340 365 q20 -26 50 -16 q-4 26 -26 34 q-26 10 -24 -18 z'/>"
    "<path d='M180 80 q16 -22 40 -12 q-4 22 -22 30 q-22 8 -18 -18 z'/>"
    "</g>"
    "<g fill='#26A69A' stroke='#00695C' stroke-width='1.6'>"
    "<path d='M260 320 q18 -24 44 -14 q-4 22 -24 30 q-24 8 -20 -16 z'/>"
    "<path d='M460 330 q16 -22 40 -12 q-4 22 -22 30 q-22 8 -18 -18 z'/>"
    "</g>"
    "<g transform='translate(260,360)'>"
    "<ellipse cx='0' cy='0' rx='170' ry='34' fill='#8D6E63' stroke='#4E342E' stroke-width='2'/>"
    "<ellipse cx='0' cy='-6' rx='170' ry='30' fill='#A1887F' stroke='#4E342E' stroke-width='1.6'/>"
    "<ellipse cx='0' cy='-12' rx='160' ry='24' fill='#D7CCC8' stroke='#4E342E' stroke-width='1.2'/>"
    "</g>"
    "<g transform='translate(260,300)'>"
    "<path d='M-30 0 q-8 -55 30 -60 q38 5 30 60 z' fill='#FBC02D' stroke='#F57F17' stroke-width='2'/>"
    "<ellipse cx='0' cy='-60' rx='30' ry='8' fill='#FDD835' stroke='#F57F17' stroke-width='1.8'/>"
    "<path d='M30 -30 q14 10 0 20' fill='none' stroke='#F57F17' stroke-width='3'/>"
    "</g>"
    "<g transform='translate(180,340)'>"
    "<ellipse cx='0' cy='0' rx='24' ry='7' fill='#FFFFFF' stroke='#1565C0' stroke-width='1.6'/>"
    "<path d='M-20 -2 q0 -18 20 -18 q20 0 20 18 z' fill='#FFFFFF' stroke='#1565C0' stroke-width='1.8'/>"
    "</g>"
    "<g transform='translate(340,340)'>"
    "<ellipse cx='0' cy='0' rx='24' ry='7' fill='#FFFFFF' stroke='#C62828' stroke-width='1.6'/>"
    "<path d='M-20 -2 q0 -18 20 -18 q20 0 20 18 z' fill='#FFFFFF' stroke='#C62828' stroke-width='1.8'/>"
    "</g>"
    "</g></pattern></defs>"
    "<rect width='100%' height='100%' fill='url(%23gorodets)'/></svg>"
)

_GORODETS_SVG_B64 = base64.b64encode(_GORODETS_SVG.encode('utf-8')).decode('ascii')


# ==================== [NEW-NORMALIZE-ACCOUNT] ЭТАЛОННЫЙ СПИСОК СЧЕТОВ ====================

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

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root {
    --grass-dark: #1B5E20;
    --grass: #2E7D32;
    --grass-light: #4CAF50;
    --grass-accent: #81C784;
    --mint-light: #C8E6C9;
    --mint-soft: #E8F5E9;
    --ink: #1A2E1F;
    --ink-soft: #3E5042;
    --ink-muted: #6E8072;
    --border: #C8E6C9;
}

html, body {
    background-color: #FFFDF2 !important;
}

.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
[data-testid="stToolbar"] {
    background-image:
        url("data:image/svg+xml;base64,__GORODETS_B64__"),
        radial-gradient(circle at 20% 20%, #FFF6DE 0%, transparent 45%),
        radial-gradient(circle at 80% 75%, #FFE9C8 0%, transparent 50%),
        linear-gradient(180deg, #FFFDF2 0%, #FFF6DE 50%, #FDEBC8 100%);
    background-repeat: repeat, no-repeat, no-repeat, no-repeat;
    background-size: 520px 460px, cover, cover, cover;
    background-attachment: fixed, fixed, fixed, fixed;
    background-position: 0 0, 0 0, 0 0, 0 0;
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    color: var(--ink);
}

.main,
.block-container {
    background: transparent !important;
}

footer {visibility: hidden;}
#MainMenu {visibility: hidden;}

.hero {
    background: linear-gradient(135deg, #1B5E20 0%, #2E7D32 50%, #4CAF50 100%);
    padding: 2.2rem 2rem;
    border-radius: 24px;
    color: #FFFFFF;
    margin-bottom: 1.6rem;
    box-shadow: 0 16px 36px rgba(27, 94, 32, 0.30);
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    top: -100px; right: -100px;
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(255,255,255,0.18) 0%, transparent 70%);
    border-radius: 50%;
}
.hero-content { position: relative; z-index: 2; display: flex; align-items: center; gap: 1.6rem; flex-wrap: wrap; }
.hero-text { flex: 1; min-width: 260px; }
.hero-text h1 { font-size: 1.9rem; font-weight: 800; margin: 0 0 0.5rem 0; letter-spacing: -0.5px; }
.hero-text p { font-size: 1rem; margin: 0; opacity: 0.95; }
.hero-chips { display: flex; gap: 0.4rem; margin-top: 1rem; flex-wrap: wrap; }
.chip {
    background: rgba(255,255,255,0.2);
    border: 1px solid rgba(255,255,255,0.3);
    padding: 0.3rem 0.75rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 500;
    backdrop-filter: blur(8px);
}
.hero-illustration { position: relative; z-index: 2; }

.stButton > button,
.stButton > button[kind="primary"],
.stButton > button[kind="secondary"],
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primaryFormSubmit"],
[data-testid="stBaseButton-secondaryFormSubmit"],
.stDownloadButton > button,
[data-testid="stDownloadButton"] > button,
[data-testid="stDownloadButton"] button,
.stFormSubmitButton > button,
[data-testid="stFormSubmitButton"] > button,
.stFileUploader button,
[data-testid="stFileUploader"] button,
[data-testid="stFileUploaderDropzone"] button,
section[data-testid="stFileUploaderDropzone"] button {
    position: relative !important;
    background:
        radial-gradient(circle at 30% 22%, rgba(255,255,255,0.45), rgba(255,255,255,0) 60%),
        linear-gradient(180deg, #3E8E41 0%, #1B5E20 45%, #0D3A12 100%) !important;
    color: #FFFFFF !important;
    border: 3px solid #FBC02D !important;
    border-radius: 12px !important;
    padding: 0.55rem 1.1rem !important;
    font-weight: 800 !important;
    font-size: 1.05rem !important;
    letter-spacing: 0.2px !important;
    line-height: 1.2 !important;
    text-shadow: 0 1px 2px rgba(0,0,0,0.55) !important;
    box-shadow:
        inset 0 2px 0 rgba(255,255,255,0.30),
        inset 0 -4px 0 rgba(0,0,0,0.40),
        0 6px 14px rgba(0,0,0,0.28),
        0 3px 0 #0D3A12 !important;
    transition: transform 0.15s ease, filter 0.20s ease, box-shadow 0.20s ease !important;
    animation: none !important;
    transform: translateZ(0);
    width: auto !important;
    min-width: 8rem !important;
    min-height: 2.6rem !important;
}
.stButton > button p,
.stButton > button span,
.stButton > button div,
[data-testid="stBaseButton-primary"] p,
[data-testid="stBaseButton-secondary"] p,
.stDownloadButton > button p,
[data-testid="stDownloadButton"] > button p {
    font-size: 1.05rem !important;
    font-weight: 800 !important;
    color: #FFFFFF !important;
    margin: 0 !important;
}
.stButton > button:hover,
.stDownloadButton > button:hover,
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-secondary"]:hover,
[data-testid="stDownloadButton"] > button:hover {
    transform: translateY(-1px) !important;
    filter: brightness(1.10) saturate(1.10) !important;
    box-shadow:
        inset 0 2px 0 rgba(255,255,255,0.40),
        inset 0 -4px 0 rgba(0,0,0,0.45),
        0 8px 18px rgba(0,0,0,0.34),
        0 4px 0 #0D3A12 !important;
    color: #FFFFFF !important;
}
.stButton > button:active,
.stDownloadButton > button:active {
    transform: translateY(1px) !important;
    box-shadow:
        inset 0 2px 0 rgba(255,255,255,0.25),
        inset 0 -2px 0 rgba(0,0,0,0.40),
        0 3px 8px rgba(0,0,0,0.25),
        0 1px 0 #0D3A12 !important;
    filter: brightness(0.95) !important;
}
.stButton > button[kind="secondary"],
[data-testid="stBaseButton-secondary"] {
    background:
        radial-gradient(circle at 30% 22%, rgba(255,255,255,0.45), rgba(255,255,255,0) 60%),
        linear-gradient(180deg, #C62828 0%, #8E0000 45%, #5C0000 100%) !important;
    border: 3px solid #FBC02D !important;
    box-shadow:
        inset 0 2px 0 rgba(255,255,255,0.30),
        inset 0 -4px 0 rgba(0,0,0,0.40),
        0 6px 14px rgba(0,0,0,0.28),
        0 3px 0 #5C0000 !important;
}

.stFileUploader {
    background: #FFFFFF;
    border-radius: 16px;
    padding: 1rem;
    border: 2px dashed var(--border);
    box-shadow: 0 4px 16px rgba(27, 94, 32, 0.05);
}
.stFileUploader:hover { border-color: var(--grass-light); }
.stFileUploader section { border: none !important; background: transparent !important; }

.stFileUploader button,
[data-testid="stFileUploader"] button,
[data-testid="stFileUploaderDropzone"] button {
    background:
        radial-gradient(circle at 30% 22%, rgba(255,255,255,0.6), rgba(255,255,255,0) 60%),
        linear-gradient(180deg, #4CAF50 0%, #2E7D32 100%) !important;
    color: #FFFFFF !important;
    border: 2px solid #FBC02D !important;
    border-radius: 10px !important;
    font-size: 1rem !important;
    font-weight: 800 !important;
    padding: 0.55rem 1.1rem !important;
    text-shadow: 0 1px 2px rgba(0,0,0,0.55) !important;
    box-shadow:
        inset 0 2px 0 rgba(255,255,255,0.30),
        inset 0 -3px 0 rgba(0,0,0,0.30),
        0 4px 10px rgba(0,0,0,0.22) !important;
    animation: none !important;
}
.stFileUploader button:hover,
[data-testid="stFileUploader"] button:hover {
    background: linear-gradient(180deg, #66BB6A 0%, #388E3C 100%) !important;
    color: #FFFFFF !important;
}
.stFileUploader button p,
[data-testid="stFileUploader"] button p {
    font-size: 1rem !important;
    font-weight: 800 !important;
    color: #FFFFFF !important;
    margin: 0 !important;
}

[data-testid="stFileUploaderDropzoneInstructions"] > div > span { font-size: 0 !important; }
[data-testid="stFileUploaderDropzoneInstructions"] > div > span::before {
    content: "Перетащите файлы сюда" !important;
    font-size: 0.95rem !important;
    color: var(--ink) !important;
    display: block;
}
[data-testid="stFileUploaderDropzoneInstructions"] > div > small { font-size: 0 !important; }
[data-testid="stFileUploaderDropzoneInstructions"] > div > small::before {
    content: "Лимит 200 МБ на файл • CSV, XLSX, XLS, DOCX, PDF" !important;
    font-size: 0.78rem !important;
    color: var(--ink-muted) !important;
    display: block;
}

.stMetric {
    background: #FFFFFF;
    border-radius: 16px;
    padding: 1.2rem 1.4rem;
    border: 1px solid #E1EEDD;
    box-shadow: 0 6px 22px rgba(27, 94, 32, 0.07);
    position: relative;
    overflow: hidden;
}
.stMetric::before {
    content: '';
    position: absolute;
    top: 0; left: 0; height: 100%; width: 6px;
    background: linear-gradient(180deg, #1B5E20 0%, #4CAF50 100%);
}
.stMetric:hover { transform: translateY(-3px); box-shadow: 0 14px 32px rgba(27, 94, 32, 0.20); }
.stMetric label { color: var(--ink-soft) !important; font-size: 0.85rem !important; text-transform: uppercase; }
.stMetric [data-testid="stMetricValue"] { color: var(--ink) !important; font-weight: 700 !important; font-size: 1.5rem !important; }

.stDataFrame { border-radius: 16px; overflow: hidden; box-shadow: 0 8px 28px rgba(27, 94, 32, 0.10); background: #FFFFFF; }

.stAlert { border-radius: 12px; border: none; }
div[data-baseweb="notification"][kind="positive"] { background: #E8F5E9; color: var(--ink); }
div[data-baseweb="notification"][kind="info"] { background: #FFF6E8; color: var(--ink); }
div[data-baseweb="notification"][kind="warning"] { background: #FBF3E0; color: #7A5B10; }

.stProgress > div > div > div { background: linear-gradient(90deg, #1B5E20 0%, #4CAF50 100%); border-radius: 8px; }

h3 {
    color: var(--ink);
    font-weight: 700;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid #E1EEDD;
    margin-top: 1.6rem;
    margin-bottom: 1rem;
    font-size: 1.15rem;
}

::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: #FFF6E8; }
::-webkit-scrollbar-thumb { background: #F48FB1; border-radius: 5px; }
::-webkit-scrollbar-thumb:hover { background: #E91E63; }

hr { border: none; border-top: 1px solid #E1EEDD; margin: 1.6rem 0; }

.info-card {
    background: #FFFFFF;
    border-radius: 14px;
    padding: 1.2rem 1.3rem;
    border: 1px solid #E1EEDD;
    display: flex;
    align-items: center;
    gap: 1rem;
    box-shadow: 0 4px 16px rgba(27, 94, 32, 0.06);
}
.info-card-icon {
    flex-shrink: 0; width: 48px; height: 48px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 12px;
    background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%);
}
.info-card-text h4 { color: var(--ink); margin: 0 0 0.25rem 0; font-size: 0.95rem; font-weight: 600; }
.info-card-text p { color: var(--ink-muted); margin: 0; font-size: 0.82rem; }
.footer-note { text-align: center; color: var(--ink-muted); font-size: 0.8rem; padding: 1.2rem 0 0.4rem 0; }

.summary-table {
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 8px 28px rgba(27, 94, 32, 0.10);
    background: #FFFFFF;
    margin-bottom: 1rem;
}
.summary-table table {
    border-collapse: collapse;
    width: 100%;
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    font-size: 0.88rem;
}
.summary-table thead th {
    background: linear-gradient(135deg, #1B5E20 0%, #2E7D32 100%);
    color: #FFFFFF;
    padding: 10px 12px;
    text-align: left;
    font-weight: 600;
    border: none;
    white-space: nowrap;
}
.summary-table tbody td {
    padding: 8px 12px;
    border-bottom: 1px solid #E1EEDD;
    color: var(--ink);
    background: #FFFFFF;
}
.summary-table tbody tr:nth-child(even) td { background: #FFF6E8; }
.summary-table tbody tr:hover td { background: #FCE4EC; }
.summary-table tbody tr:last-child td { border-bottom: none; }

.ai-chat-bubble-user {
    background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%);
    border-left: 4px solid #2E7D32;
    border-radius: 12px;
    padding: 0.8rem 1rem;
    margin: 0.5rem 0;
    color: var(--ink);
}
.ai-chat-bubble-assistant {
    background: #FFFFFF;
    border-left: 4px solid #FBC02D;
    border-radius: 12px;
    padding: 0.8rem 1rem;
    margin: 0.5rem 0;
    color: var(--ink);
    box-shadow: 0 2px 8px rgba(27, 94, 32, 0.08);
}
.ai-status-ok {
    background: #E8F5E9;
    color: #1B5E20;
    border-radius: 8px;
    padding: 0.4rem 0.8rem;
    font-size: 0.85rem;
    display: inline-block;
}
.ai-status-warn {
    background: #FBF3E0;
    color: #7A5B10;
    border-radius: 8px;
    padding: 0.4rem 0.8rem;
    font-size: 0.85rem;
    display: inline-block;
}
</style>
"""

st.markdown(_CSS.replace("__GORODETS_B64__", _GORODETS_SVG_B64), unsafe_allow_html=True)


# [FIX-UI-RUSSIAN] JS-локализация
_RU_TRANSLATIONS_JS = """
<script>
(function() {
    const translations = {
        "Browse files": "Выбрать файлы",
        "Drag and drop file here": "Перетащите файлы сюда",
        "Drag and drop files here": "Перетащите файлы сюда",
        "Limit 200MB per file": "Лимит 200 МБ на файл",
        "Press Enter to submit": "Нажмите Enter для отправки",
        "Press Enter to apply": "Нажмите Enter для применения",
        "Clear": "Очистить",
        "Select all": "Выбрать все",
        "Deselect all": "Снять выделение",
        "Search": "Поиск",
        "Sort": "Сортировать",
        "Show fullscreen": "На весь экран",
        "Hide": "Скрыть",
        "Fullscreen": "Во весь экран",
        "Download as CSV": "Скачать CSV",
        "Running": "Выполняется",
        "Stop": "Остановить",
        "Rerun": "Перезапустить",
        "Deploy": "Развернуть",
        "Settings": "Настройки",
        "Print": "Печать",
        "Copy": "Копировать",
        "Copied": "Скопировано",
        "Show more": "Показать больше",
        "Show less": "Показать меньше",
        "Add row": "Добавить строку",
        "Delete row": "Удалить строку",
        "Use fullscreen": "На весь экран",
        "Exit fullscreen": "Выйти из полноэкранного режима"
    };
    function applyTranslations() {
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
        let node; const nodes = [];
        while (node = walker.nextNode()) nodes.push(node);
        nodes.forEach(function(n) {
            const text = n.nodeValue.trim();
            if (translations[text]) n.nodeValue = n.nodeValue.replace(text, translations[text]);
        });
        document.querySelectorAll('[placeholder]').forEach(function(el) {
            const p = el.getAttribute('placeholder');
            if (translations[p]) el.setAttribute('placeholder', translations[p]);
        });
        document.querySelectorAll('[title]').forEach(function(el) {
            const t = el.getAttribute('title');
            if (translations[t]) el.setAttribute('title', translations[t]);
        });
        document.querySelectorAll('[aria-label]').forEach(function(el) {
            const a = el.getAttribute('aria-label');
            if (translations[a]) el.setAttribute('aria-label', translations[a]);
        });
    }
    applyTranslations();
    const observer = new MutationObserver(applyTranslations);
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
})();
</script>
"""

components.html(_RU_TRANSLATIONS_JS, height=0, width=0)


# ==================== [DEEPSEEK-INTEGRATION] НАСТРОЙКИ DEEPSEEK ====================

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"
DEEPSEEK_REASONER_MODEL = "deepseek-reasoner"


def _get_deepseek_api_key() -> str:
    key = ""
    try:
        if "DEEPSEEK_API_KEY" in st.secrets:
            key = str(st.secrets["DEEPSEEK_API_KEY"]).strip()
    except Exception:
        pass
    if not key:
        key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        key = str(st.session_state.get("deepseek_api_key", "")).strip()
    return key


def _get_deepseek_client() -> Optional["OpenAI"]:
    if not _OPENAI_SDK_AVAILABLE:
        return None
    api_key = _get_deepseek_api_key()
    if not api_key:
        return None
    try:
        return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
    except Exception:
        return None


def call_deepseek(
    messages: List[Dict[str, str]],
    model: str = DEEPSEEK_DEFAULT_MODEL,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    json_mode: bool = False,
) -> Tuple[str, Optional[str]]:
    client = _get_deepseek_client()
    if client is None:
        if not _OPENAI_SDK_AVAILABLE:
            return "", "Библиотека openai не установлена. Выполните: pip install openai"
        return "", "API-ключ DeepSeek не задан. Введите его в сайдбаре или в .streamlit/secrets.toml"
    try:
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content or ""
        return content.strip(), None
    except Exception as e:
        return "", f"Ошибка DeepSeek API: {e}"


def call_deepseek_json(
    system_prompt: str,
    user_prompt: str,
    model: str = DEEPSEEK_DEFAULT_MODEL,
) -> Tuple[Optional[dict], Optional[str]]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    raw, err = call_deepseek(messages, model=model, temperature=0.1, json_mode=True)
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
        return None, f"Не удалось распарсить JSON от DeepSeek: {raw[:300]}"


_AI_TRANSACTION_SYSTEM = (
    "Ты — эксперт по банковским выпискам. "
    "На вход получаешь одну транзакцию: оригинальное описание (может быть на английском, "
    "чешском, латышском, венгерском, азербайджанском), имя банка и сумму. "
    "Верни СТРОГО JSON без пояснений:\n"
    "{\n"
    '  "translation": "перевод описания на русский (кратко, по делу)",\n'
    '  "category": "одна из: Зарплата, Аренда, Коммуналка, Продукты, Ресторан, '
    'Транспорт, Такси, Топливо, Банковские комиссии, Перевод между счетами, '
    'Налоги, Страхование, Кредит, Подписка, Покупка, Возврат, Прочее",\n'
    '  "counterparty_clean": "чистое имя контрагента (бренд/ФИО/компания), '
    'если можно выделить, иначе пустая строка",\n'
    '  "is_bank_fee": true/false,\n'
    '  "confidence": 0.0-1.0\n'
    "}\n"
    "Правила:\n"
    "- Если описание — это служебная строка банка (начальный остаток, комиссия за обслуживание), "
    "  поставь is_bank_fee=true и category='Банковские комиссии'.\n"
    "- Не выдумывай контрагента, если его нет в описании.\n"
    "- Отвечай только JSON, без markdown."
)


def ai_enrich_transactions(
    transactions: List[Dict],
    max_items: int = 200,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Tuple[List[Dict], List[str]]:
    errors: List[str] = []
    if not transactions:
        return transactions, ["Нет транзакций для обогащения"]

    client = _get_deepseek_client()
    if client is None:
        return transactions, ["DeepSeek недоступен: нет API-ключа или библиотеки openai"]

    subset = transactions[:max_items]
    enriched = [dict(t) for t in transactions]

    for i, tx in enumerate(subset):
        desc = str(tx.get("Описание", ""))[:1500]
        acc = str(tx.get("Наименование банка", tx.get("Наименование счета", "")))
        amount = tx.get("Сумма", 0)

        user_prompt = (
            f"Банк: {acc}\n"
            f"Сумма: {amount}\n"
            f"Описание: {desc}\n"
        )
        data, err = call_deepseek_json(_AI_TRANSACTION_SYSTEM, user_prompt)
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
    "Пользователь присылает фрагмент кода, ошибку или проблемную транзакцию. "
    "Твоя задача — предложить конкретное исправление. "
    "Если нужно — верни исправленный фрагмент кода с комментариями на русском. "
    "Не читай лекции, отвечай по делу."
)


# ==================== ШАПКА ====================

st.markdown("""
<div class="hero">
<div class="hero-content">
<div class="hero-text">
<h1>💼 Аналитик банковских выписок</h1>
<p>Загружайте выписки — получайте единый отчёт по доходам и расходам</p>
<div class="hero-chips">
<span class="chip">📄 CSV</span>
<span class="chip">📊 XLSX</span>
<span class="chip">📑 XLS</span>
<span class="chip">📝 DOCX</span>
<span class="chip">📕 PDF</span>
<span class="chip">🌐 Перевод в скобках</span>
<span class="chip">🤖 DeepSeek AI</span>
</div>
</div>
<div class="hero-illustration">
<svg width="150" height="150" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
<circle cx="100" cy="100" r="90" fill="rgba(255,255,255,0.15)"/>
<rect x="50" y="110" width="14" height="50" rx="4" fill="rgba(255,255,255,0.85)"/>
<rect x="72" y="90" width="14" height="70" rx="4" fill="rgba(255,255,255,0.95)"/>
<rect x="94" y="70" width="14" height="90" rx="4" fill="rgba(255,255,255,1)"/>
<rect x="116" y="95" width="14" height="65" rx="4" fill="rgba(255,255,255,0.95)"/>
<rect x="138" y="60" width="14" height="100" rx="4" fill="rgba(255,255,255,1)"/>
<path d="M57 100 L79 80 L101 60 L123 85 L145 50" stroke="#FFFFFF" stroke-width="3" fill="none" stroke-linecap="round"/>
<circle cx="57" cy="100" r="5" fill="#FFFFFF"/>
<circle cx="79" cy="80" r="5" fill="#FFFFFF"/>
<circle cx="101" cy="60" r="5" fill="#FFFFFF"/>
<circle cx="123" cy="85" r="5" fill="#FFFFFF"/>
<circle cx="145" cy="50" r="5" fill="#FFFFFF"/>
<circle cx="160" cy="40" r="16" fill="#FFD86B" stroke="#FFFFFF" stroke-width="2"/>
<text x="160" y="46" text-anchor="middle" font-size="16" font-weight="700" fill="#1B5E20">₽</text>
</svg>
</div>
</div>
</div>
""", unsafe_allow_html=True)


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


def parse_date(date_str) -> str:
    if date_str is None or pd.isna(date_str):
        return ''
    s = str(date_str).strip()
    if not s or s in ['nan', '-', 'None', 'null', 'NaT']:
        return ''
    if ' ' in s:
        s = s.split(' ')[0]
    if 'T' in s:
        s = s.split('T')[0]
    if s.endswith('.0'):
        s = s[:-2]
    if s.isdigit() and len(s) == 8:
        return f"{s[6:8]}-{s[4:6]}-{s[:4]}"
    if s.isdigit() and len(s) == 5 and 40000 <= int(s) <= 50000:
        try:
            from datetime import timedelta
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
    if v is None or pd.isna(v):
        return ''
    return str(v).strip()


# ==================== [FIX-TRANSLATE-FULL] ПЕРЕВОД ОПИСАНИЙ ====================

_PHRASE_DICT: Dict[str, str] = {
    # === Английский: банковские термины ===
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

    # === Бренды ===
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

    # === Латышский ===
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

    # === Чешский ===
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

    # === Венгерский ===
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

    # === Азербайджанский ===
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

    # === Русский: служебные строки ===
    "плата за обслуживание счета": "плата за обслуживание счёта",
    "остаток в начале": "остаток на начало",
    "остаток в конце": "остаток на конец",
    "комиссионная плата": "комиссионная плата",
    "назначение платежа": "назначение платежа",
}

_WORD_DICT: Dict[str, str] = {
    # === Английский ===
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

    # === Чешский ===
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

    # === Латышский ===
    "apmaksa": "оплата",
    "apmaksas": "оплаты",
    "apmaksāts": "оплачено",
    "rēķins": "счёт",
    "rēķina": "счёта",
    "rēķinu": "счёт",
    "rēķini": "счета",
    "rekins": "счёт",
    "rekina": "счёта",
    "rekinu": "счёт",
    "rekini": "счета",
    "reķins": "счёт",
    "reķinu": "счёт",
    "rēkins": "счёт",
    "rēkinu": "счёт",

    "maksa": "плата",
    "maksas": "платы",
    "maksājums": "платёж",
    "maksājumi": "платежи",
    "maksājumu": "платежей",

    "alga": "зарплата",
    "algas": "зарплаты",
    "algu": "зарплату",
    "algām": "зарплатам",
    "darba": "рабочей",
    "darba alga": "заработная плата",
    "darba algas": "заработной платы",

    "izmaksa": "выплата",
    "izmaksas": "выплаты",
    "izmaksu": "выплат",
    "izmaksāt": "выплатить",

    "īre": "аренда",
    "īres": "аренды",
    "īri": "аренду",
    "ire": "аренда",
    "ires": "аренды",
    "noma": "аренда",
    "nomas": "аренды",
    "nomas maksa": "арендная плата",

    "dzīvoklis": "квартира",
    "dzīvokli": "квартиру",
    "dzīvokļa": "квартиры",
    "dzivoklis": "квартира",
    "dzivokli": "квартиру",
    "dzivokla": "квартиры",

    "māja": "дом",
    "mājas": "дома",
    "iela": "улица",
    "ielas": "улицы",
    "ielā": "на улице",

    "periods": "период",
    "periodu": "период",
    "perioda": "периода",
    "no": "с",
    "līdz": "до",
    "lidz": "до",

    "komunālie": "коммунальные",
    "komunalie": "коммунальные",
    "komunālo": "коммунальных",
    "komunāliem": "коммунальным",
    "pakalpojumi": "услуги",
    "pakalpojumu": "услуг",
    "pakalpojumiem": "услуг",
    "pakalpojums": "услуга",

    "procenti": "проценты",
    "procentu": "процентов",
    "procents": "процент",

    "nodoklis": "налог",
    "nodokļi": "налоги",
    "nodokļa": "налога",
    "nodokļu": "налогов",

    "apdrošināšana": "страхование",
    "apdrošināšanas": "страхования",
    "aizdevums": "кредит",
    "aizdevuma": "кредита",
    "kredīts": "кредит",
    "kredīta": "кредита",

    "komisija": "комиссия",
    "komisijas": "комиссии",
    "komisiju": "комиссию",
    "komisijas maksa": "комиссионный сбор",

    "atlikums": "остаток",
    "atlikuma": "остатка",
    "atlikumu": "остаток",
    "sākuma": "начальный",
    "beigu": "конечный",

    "ienākumi": "доходы",
    "izdevumi": "расходы",
    "ienākumu": "доходов",
    "izdevumu": "расходов",

    "saņēmējs": "получатель",
    "saņēmēja": "получателя",
    "maksātājs": "плательщик",
    "maksātāja": "плательщика",
    "mērķis": "назначение",
    "mērķa": "назначения",
    "datums": "дата",
    "datuma": "даты",
    "summa": "сумма",
    "summas": "суммы",
    "valūta": "валюта",
    "valūtas": "валюты",
    "veids": "тип",
    "veida": "типа",
    "statuss": "статус",
    "numurs": "номер",
    "numura": "номера",
    "kods": "код",
    "koda": "кода",

    "konts": "счёт",
    "konta": "счёта",
    "kontā": "на счёте",
    "kontu": "счёт",
    "kontiem": "счетам",

    "bankas": "банковские",
    "banka": "банк",
    "bankā": "в банке",
    "banku": "банк",

    "pārskaitījums": "перевод",
    "pārskaitījuma": "перевода",
    "pārskaitīt": "перевести",
    "pārskaitīts": "переведено",

    # === Венгерский ===
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


def _build_translation_patterns():
    phrase_patterns = []
    for key in sorted(_PHRASE_DICT.keys(), key=len, reverse=True):
        esc = re.escape(key)
        esc = esc.replace(r'\ ', r'\s+')
        pattern = re.compile(
            r'(?<![A-Za-zÀ-ÖØ-öø-ÿĀ-žА-Яа-я])'
            + esc +
            r'(?![A-Za-zÀ-ÖØ-öø-ÿĀ-žА-Яа-я])',
            re.IGNORECASE
        )
        phrase_patterns.append((pattern, key))

    word_patterns = []
    for key in sorted(_WORD_DICT.keys(), key=len, reverse=True):
        pattern = re.compile(
            r'(?<![A-Za-zÀ-ÖØ-öø-ÿĀ-žА-Яа-я])'
            + re.escape(key) +
            r'(?![A-Za-zÀ-ÖØ-öø-ÿĀ-žА-Яа-я])',
            re.IGNORECASE
        )
        word_patterns.append((pattern, key))

    return phrase_patterns, word_patterns


_PHRASE_PATTERNS, _WORD_PATTERNS = _build_translation_patterns()


def translate_to_russian(text: str) -> str:
    if not text:
        return text
    s = str(text)

    for pattern, key in _PHRASE_PATTERNS:
        translated = _PHRASE_DICT.get(key, key)
        s = pattern.sub(translated, s)

    for pattern, key in _WORD_PATTERNS:
        translated = _WORD_DICT.get(key, key)
        s = pattern.sub(translated, s)

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


# ==================== [FIX-COUNTERPARTY-FULL-V4] ====================

_BANK_SERVICE_MARKERS = [
    'начальный остаток', 'конечный остаток', 'входящий остаток', 'исходящий остаток',
    'opening balance', 'closing balance', 'starting balance', 'ending balance',
    'saldo počáteční', 'saldo konečné', 'sākuma atlikums', 'beigu atlikums',
    'nyitó egyenleg', 'záró egyenleg',
    'acc. maintenance', 'account maintenance', 'banking charges',
    'account maintenance charges', 'netbankár havi díj', 'netbankar havi dij',
    'subscription fee for', 'popl.', 'poplatek', 'urok do', 'úrok do',
    'úrok', 'kamatjóváírás', 'kamat',
    'txn fee', 'transaction fee', 'foreign exchange transaction fee',
    'tranzakciós díj', 'tranzakcios dij', 'tranzakciós díjrész',
    'comission', 'commission', 'charge for', 'charges',
    'dövrün sonuna balans', 'dovrun sonuna balans',
    'hesaba mədaxil', 'hesaba medaxil',
    'internal payment', 'outgoing xohks payment', 'incoming swift payment',
    'outward clearing cheque', 'online international money transfer',
    'funds transfer charges', 'corr.bank.charges', 'value added tax - output',
    'currency exchange', 'sepa átutalás jóváírása', 'sepa átutalás',
    'giro átutalás', 'bankon belüli átutalás', 'napközbeni forint átvezetés',
    'sms service fee', 'sms service', 'metal membership',
    'charge accounting', 'místo:', 'misto:',
    'transfer own funds', 'перевод own funds',
    'message', 'notprovided',
    'bankon belüli', 'átutalás', 'jóváírása', 'terhelése',
    'készpénzfelvétel', 'készpénzbefizetés',
    'atm withdrawal', 'cash withdrawal', 'cash deposit',
    'card payment', 'pos payment',
    'grow plan fee', 'expenses app charges', 'revolut business fee',
    'interest payment for loan',
    'плата за обслуживание счета',
]


def _is_service_description(desc: str) -> bool:
    if not desc:
        return False
    low = desc.lower().strip()
    for m in _BANK_SERVICE_MARKERS:
        if m in low:
            return True
    return False


_JUNK_PATTERNS = [
    r'\b[A-Z]{2}\d{2}[A-Z0-9]{10,}\b',
    r'\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2,5}\b',
    r'\bREF\b[^\s]*', r'\bSRN\b[^\s]*', r'\bREC\b[^\s]*',
    r'\bROC\b[^\s]*', r'\bMCC\d+\b', r'\bTOC-[A-Z0-9\-]+\b',
    r'\bT_[A-F0-9]{10,}\b',
    r'\b\d{10,}\b',
    r'\+\d[\d\s\(\)\-]{6,}',
    r'\b[A-Z]{2}\d{2}[A-Z]{4}\d{10,}\b',
    r'\bLV\d{2}[A-Z]{4}\d{10,}\b',
    r'\bLT\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b',
    r'\bEE\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b',
    r'\bAZ\d{2}[A-Z]{4}\d{16,}\b',
    r'\bAE\d{2}\s?\d{3,}\b',
    r'\b[A-Z]{2}\d{2}\s?[A-Z0-9 ]{10,}\b',
    r'_x000D_', r'\r', r'\n',
    r'\b[A-Z0-9]{4,}\*[A-Z0-9]+\b',
    r'\\[a-zA-Z]{2,}\b',
    r'\b[A-Z]-\d+[A-Z0-9]*\b',
    r'\b[A-Z]-\d+[A-Z0-9]*/[A-Z0-9]*\b',
    r'/[A-Z]/?',
    r'\\',
    r'\b\d{5,}(?:[A-Z0-9]*)\b',
]


def _strip_junk(s: str) -> str:
    if not s:
        return ''
    out = s
    for pat in _JUNK_PATTERNS:
        out = re.sub(pat, ' ', out, flags=re.IGNORECASE)
    out = re.sub(r'[\*\|<>]+', ' ', out)
    out = re.sub(r'[,;:]+', ' ', out)
    out = re.sub(r'\s+', ' ', out).strip(' .,;:-–—/\\')
    return out


def _clean_counterparty_name(name: str, keep_full: bool = False) -> str:
    """
    [FIX-COUNTERPARTY-FULL-V4]
    keep_full=True: не режем по ' | ', ' • ', ' — ' — оставляем как есть.
    """
    if not name:
        return ''
    s = str(name).strip()
    s = _strip_junk(s)
    if not keep_full:
        for sep in [' | ', ' • ', ' — ', ' – ']:
            if sep in s:
                parts = [p.strip() for p in s.split(sep) if p.strip()]
                candidates = [p for p in parts if not _is_service_description(p)]
                if candidates:
                    candidates.sort(key=len, reverse=True)
                    s = candidates[0]
                else:
                    s = parts[0]
                break
    s = re.sub(r'\s*\([^)]*\)\s*$', '', s).strip()
    s = s.strip(' .,;:-–—/\\')
    if len(s) < 2:
        return ''
    if re.fullmatch(r'[\d\s.,\-/\\]+', s):
        return ''
    return s


def _looks_like_bank_name(s: str) -> bool:
    if not s:
        return False
    low = s.lower()
    bank_words = [
        'bank', 'payments', 'finance', 'revolut', 'paysera', 'wise',
        'sepa', 'transfer', 'csob', 'unicredit', 'tinkoff', 'bluor',
        'industra', 'pasha', 'mashreq', 'wio', 'n26', 'mkb', 'fio',
        'kapital', 'rak', 'fio banka',
    ]
    return any(w in low for w in bank_words)


_NAME_PATTERNS = [
    (r'\bMoney added from\s+(.+)$', 1),
    (r'\bMoney received from\s+(.+)$', 1),
    (r'\bMoney sent to\s+(.+)$', 1),
    (r'^\s*From\s+(.+)$', 1),
    (r'^\s*To\s+(.+)$', 1),
    (r'\bсписан[ао]?\s+(?:на\s+сумму\s+[\d\s.,]+\s*[A-Z]{0,3},?\s*)?(.+)$', 1),
    (r'\bоплата\s+(.+)$', 1),
    (r'\bперевод\s+в\s+адрес\s+(.+)$', 1),
    (r'\b(?:payment|transfer|paid|sent)\s+to\s+(.+)$', 1),
    (r'\bFrom:\s*(.+)$', 1),
    (r'\bTo:\s*(.+)$', 1),
    (r'\bсписана\s+(?:у\s+)?(.+)$', 1),
]


def _extract_name_by_patterns(desc: str) -> str:
    if not desc:
        return ''
    for pat, grp in _NAME_PATTERNS:
        m = re.search(pat, desc, re.IGNORECASE)
        if m:
            cand = m.group(grp).strip()
            if ' | ' in cand:
                cand = cand.split(' | ', 1)[0].strip()
            cand = _clean_counterparty_name(cand, keep_full=True)
            if cand and len(cand) >= 2 and not _looks_like_bank_name(cand) \
                    and not _is_service_description(cand):
                return cand
    return ''


# ==================== [FIX-COUNTERPARTY-FULL-V4] ПОЛНЫЕ ИМЕНА ПО БАНКАМ ====================

def _extract_revolut_name(desc: str,
                           account_name: str = '',
                           payer: str = '',
                           beneficiary: str = '') -> str:
    """
    [FIX-COUNTERPARTY-FULL-V4]
    Для Revolut в CSV есть явные поля Payer и Beneficiary name.
    Они ВСЕГДА приоритетнее, чем разбор Description, потому что
    Description часто содержит обрезанный ник ("Sintija Z"),
    а полное имя ("Sintija Zalumska") — в Beneficiary name.
    """
    # 1) Beneficiary name
    if beneficiary:
        c = str(beneficiary).strip()
        if c and c.lower() not in ('nan', 'none', 'n/a', '-'):
            cleaned = _clean_counterparty_name(c, keep_full=True)
            if cleaned and len(cleaned) >= 2:
                return cleaned
    # 2) Payer
    if payer:
        c = str(payer).strip()
        if c and c.lower() not in ('nan', 'none', 'n/a', '-'):
            cleaned = _clean_counterparty_name(c, keep_full=True)
            if cleaned and len(cleaned) >= 2:
                return cleaned
    # 3) Только если полей нет — из Description
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

    # Fallback: ищем в любом месте строки
    for prefix in ['Money added from ', 'Money received from ', 'Money sent to ']:
        m = re.search(re.escape(prefix) + r'(.+)$', s, re.IGNORECASE)
        if m:
            rest = m.group(1).strip()
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
                           beneficiary: str = '') -> str:
    """
    [FIX-COUNTERPARTY-FULL-V4]
    Для Paysera: имя из колонки "Получатель / Плательщик".
    Убираем хвост (Код) ДО очистки, чтобы не потерять имя.
    """
    for cand in (beneficiary, payer):
        if cand:
            c = str(cand).strip()
            if c.lower() in ('nan', 'none', 'n/a', '-', ''):
                continue
            # Убираем хвост (Код) и P12345
            c = re.sub(r'\(\s*[A-Z0-9]+\s*\)\s*$', '', c)
            c = re.sub(r'\s+\(.*?\)\s*$', '', c)
            c = re.sub(r'\s+[A-Z]\d{4,}\s*$', '', c)
            c = re.sub(r'\s+', ' ', c).strip(' .,;:-')
            cleaned = _clean_counterparty_name(c, keep_full=True)
            if cleaned and len(cleaned) >= 3:
                return cleaned

    if not desc:
        return ''
    s = str(desc).strip()
    if re.match(r'^(sent|sutits|inviato)\s+', s, re.IGNORECASE):
        return ''
    if 'плата за обслуживание' in s.lower():
        return 'Paysera LT'
    return ''


def _extract_industra_name(desc: str,
                            account_name: str = '',
                            payer: str = '',
                            beneficiary: str = '') -> str:
    """
    [FIX-COUNTERPARTY-FULL-V4]
    Для Industra: имя из колонки "Получатель / Плательщик".
    В описании — "Исходящее перечисление, ИМЯ", "Зачисление входящего платежа на счет клиента, ИМЯ".
    """
    for cand in (beneficiary, payer):
        if cand:
            c = str(cand).strip()
            if c.lower() in ('nan', 'none', 'n/a', '-', ''):
                continue
            c = re.sub(r'\s+\d{6,}.*$', '', c)
            c = re.sub(r'\s+', ' ', c).strip(' .,;:-')
            cleaned = _clean_counterparty_name(c, keep_full=True)
            if cleaned and len(cleaned) >= 3:
                return cleaned

    if not desc:
        return ''
    low = desc.lower()
    if 'комиссия за банковскую операцию' in low:
        return 'Industra Bank'
    if 'проводка мемориальным ордером' in low:
        return 'Industra Bank'
    m = re.search(r'Перечисление между клиентами банка[,\s]+([^,]+)', desc, re.IGNORECASE)
    if m:
        return _clean_counterparty_name(m.group(1), keep_full=True)
    m = re.search(r'Исходящее перечисление[,\s]+([^,]+)', desc, re.IGNORECASE)
    if m:
        return _clean_counterparty_name(m.group(1), keep_full=True)
    m = re.search(r'Зачисление входящего платежа на счет клиента[,\s]+([^,]+)', desc, re.IGNORECASE)
    if m:
        return _clean_counterparty_name(m.group(1), keep_full=True)
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
    m = re.match(r'^(GOOGLE|FACEBOOK|FACEBK|APPLE|AMAZON|MICROSOFT|TIKTOK|META|DEBCARD|VISA|MASTERCARD)\b',
                 s, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    s = _strip_junk(s)
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
        mcc = re.search(r'MCC(\d{4})', s)
        place = re.search(r'место совершения операции:\s*(.+?)(?:MCC|$)', s)
        if place:
            place_s = place.group(1).strip()
            place_s = re.sub(r'^[0-9A-Z]{4,}\\[A-Z]{2}\\', '', place_s)
            place_s = _clean_counterparty_name(place_s, keep_full=True)
            if place_s:
                return place_s
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
        r'(?:\s+(?:Qeyri|Köçürmə|Kocurma|Əməliyyat|Emeliyyat|Kart|Hesab|Оплата|Перевод|Комиссия|Mədaxil|Medaxil|Məxaric|Mexaric|->|→|>).*)?$',
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


# ==================== [FIX-COUNTERPARTY-FULL-V4] ГЛАВНАЯ ФУНКЦИЯ ====================

def extract_counterparty_smart(description: str,
                                account_name: str = '',
                                payer: str = '',
                                beneficiary: str = '') -> Tuple[str, str]:
    """
    [FIX-COUNTERPARTY-FULL-V4]
    Умное извлечение контрагента. Порядок:
      1) Явные поля beneficiary / payer — ВСЕГДА приоритетны.
      2) Спец-парсеры по банку.
      3) Шаблоны "from"/"to".
      4) Эвристика.
      5) Имя банка из account_name.
    """
    desc = (description or '').strip()
    acc_low = (account_name or '').lower()

    # --- 1) Явные поля ВСЕГДА приоритетны ---
    if beneficiary:
        b = str(beneficiary).strip()
        if b and b.lower() not in ('nan', 'none', 'n/a', '-'):
            cleaned = _clean_counterparty_name(b, keep_full=True)
            # Отрезаем (Код) и P12345
            cleaned = re.sub(r'\(\s*[A-Z0-9]+\s*\)\s*$', '', cleaned).strip()
            cleaned = re.sub(r'\s+[A-Z]\d{4,}\s*$', '', cleaned).strip()
            if cleaned and len(cleaned) >= 2 and not _looks_like_bank_name(cleaned):
                return (cleaned, desc)
    if payer:
        p = str(payer).strip()
        if p and p.lower() not in ('nan', 'none', 'n/a', '-'):
            cleaned = _clean_counterparty_name(p, keep_full=True)
            cleaned = re.sub(r'\(\s*[A-Z0-9]+\s*\)\s*$', '', cleaned).strip()
            cleaned = re.sub(r'\s+[A-Z]\d{4,}\s*$', '', cleaned).strip()
            if cleaned and len(cleaned) >= 2 and not _looks_like_bank_name(cleaned):
                return (cleaned, desc)

    # --- 2) Спец-парсеры по банку ---
    cp = ''

    if 'wise' in acc_low or 'saida wise' in acc_low:
        cp = _extract_wio_name(desc)
        if not cp:
            m = re.search(r'списан[ао]?\s+(.+?)(?:\s*\(|$)', desc, re.IGNORECASE)
            if m:
                cp = _clean_counterparty_name(m.group(1), keep_full=True)

    if not cp and 'wio' in acc_low:
        cp = _extract_wio_name(desc)

    if not cp and ('pasha' in acc_low or 'bunda' in acc_low):
        cp = _extract_pasha_name(desc)

    if not cp and ('mashreq' in acc_low or 'nomiqa' in acc_low):
        cp = _extract_mashreq_name(desc)

    if not cp and ('regina alfa' in acc_low):
        cp = _extract_regina_alfa_name(desc)

    if not cp and ('revolut' in acc_low):
        cp = _extract_revolut_name(desc, account_name, payer, beneficiary)

    if not cp and ('paysera' in acc_low):
        cp = _extract_paysera_name(desc, account_name, payer, beneficiary)

    if not cp and ('industra' in acc_low or 'plavas' in acc_low or 'kl59' in acc_low):
        cp = _extract_industra_name(desc, account_name, payer, beneficiary)

    if not cp and ('csob' in acc_low or 'jenhor' in acc_low or 'jenisov' in acc_low
                   or 'dzibik' in acc_low or 'džibik' in acc_low
                   or 'rr ' in acc_low or 'koruna strojka' in acc_low):
        cp = _extract_csob_name(desc)

    if not cp and ('unicredit' in acc_low or 'garpiz' in acc_low or 'twohills' in acc_low
                   or 'koruna' in acc_low or 'b1 estate' in acc_low):
        cp = _extract_unicredit_name(desc)

    if not cp and 'bluor' in acc_low:
        cp = _extract_bluor_name(desc)

    if not cp and ('mkb' in acc_low or 'budapest' in acc_low):
        cp = _extract_mkb_name(desc)

    if not cp and 'tinkoff' in acc_low:
        cp = _extract_tinkoff_name(desc)

    if not cp and ('kapital' in acc_low or ('saida' in acc_low and 'azn' in acc_low)):
        cp = _extract_kapital_name(desc)

    # --- 3) Шаблоны ---
    if not cp:
        cp = _extract_name_by_patterns(desc)

    # --- 4) Эвристика ---
    if not cp:
        m = re.match(r'^\s*To\s+([^|•]+)', desc, re.IGNORECASE)
        if m:
            cp = _clean_counterparty_name(m.group(1), keep_full=True)
        if not cp:
            m = re.match(r'^\s*From\s+([^|•]+)', desc, re.IGNORECASE)
            if m:
                cp = _clean_counterparty_name(m.group(1), keep_full=True)
    if not cp:
        parts = re.split(r'[|•;]', desc)
        for p in parts:
            p_clean = _strip_junk(p.strip())
            if not p_clean or len(p_clean) < 3:
                continue
            if _is_service_description(p_clean):
                continue
            if _looks_like_bank_name(p_clean):
                continue
            if re.search(r'[A-Za-zА-Яа-я]{3,}', p_clean) and not re.fullmatch(r'[\d\s.,\-/\\]+', p_clean):
                cp = _clean_counterparty_name(p_clean, keep_full=True)
                if cp:
                    break

    # --- 5) Имя банка ---
    if not cp:
        m = re.search(
            r'\b(CSOB|UniCredit|Revolut|Tinkoff|Paysera|Wise|BluOr|Industra|Pasha|Mashreq|WIO|N26|MKB|FIO|Kapital|RAK|ČSOB)\b',
            account_name, re.IGNORECASE
        )
        if m:
            cp = m.group(1)
        else:
            cp = ''

    return (cp, desc)


def extract_counterparty_from_description(description: str,
                                           payer: str = '',
                                           beneficiary: str = '') -> Tuple[str, str]:
    return extract_counterparty_smart(description, '', payer, beneficiary)


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


def pdf_all_text(file_content: bytes) -> str:
    parts = []
    try:
        with pdfplumber.open(BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
    except Exception:
        return ''
    full = '\n'.join(parts)
    return full.replace('\ufeff', '').replace('\xa0', ' ')


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
    if v is None or pd.isna(v):
        return False
    if isinstance(v, (int, float)):
        return True
    s = str(v).strip()
    if not s:
        return False
    return bool(re.fullmatch(r'^-?[\d\s\u00a0]*[.,]?\d*$', s))


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
            cp_final, _ = extract_counterparty_smart(
                description, account_name, counterparty, counterparty
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
            cp_final, _ = extract_counterparty_smart(desc, account_name, cp, cp)
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
            cp_final, _ = extract_counterparty_smart(m.group(2).strip(), account_name)
            if not cp_final:
                cp_final = 'Česká spořitelna'
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final,
                'Наименование счета': account_name,
                'Описание': m.group(2).strip()
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
            cp_final, _ = extract_counterparty_smart(desc, account_name, cp, cp)
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
    """
    [FIX-COUNTERPARTY-FULL-V4] Industra XLS/XLSX:
    имя из колонки "Получатель / Плательщик", передаётся как beneficiary и payer.
    """
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
                    full_desc = f"{ttype}, {desc}" if ttype and desc else (desc or ttype)
                    cp_final, _ = extract_counterparty_smart(full_desc, account_name, cp, cp)
                    result.append({
                        'Дата': date, 'Сумма': amount,
                        'Контрагент': cp_final if cp_final else '',
                        'Наименование счета': account_name,
                        'Описание': full_desc
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
            full_desc = f"{ttype}, {desc}" if ttype and desc else (desc or ttype)
            cp_final, _ = extract_counterparty_smart(full_desc, account_name, cp, cp)
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp_final if cp_final else '',
                'Наименование счета': account_name,
                'Описание': full_desc
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
    """
    [FIX-COUNTERPARTY-FULL-V4] Industra PDF.
    """
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

        low_block = block_text.lower()
        if any(w in low_block for w in [
            'начальный остаток', 'конечный остаток',
            'итоговый баланс', 'дебетовый оборот',
            'кредитный оборот', 'неоплаченная комиссия',
        ]):
            continue

        amount_matches = list(amount_re.finditer(block_text))
        if not amount_matches:
            continue
        amount = None
        for am in reversed(amount_matches):
            v = parse_amount(am.group(1))
            if v != 0.0 and _is_reasonable_amount(v):
                amount = v
                amount_end = am.end()
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
                'мемориальн', 'перечисление'
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

        if op_type.lower().startswith('комиссия') or 'комиссия за банковскую операцию' in low_block:
            desc = 'Комиссия за банковскую операцию'
            cp = 'Industra Bank'

        low_chunk = block_text.lower()
        if 'дебет' in low_chunk and ('(d)' in low_chunk or ' d ' in low_chunk):
            amount = -abs(amount)

        combined = f"{op_type}, {desc}" if op_type else desc
        cp_final, _ = extract_counterparty_smart(combined, account_name, cp, cp)

        result.append({
            'Дата': date,
            'Сумма': amount,
            'Контрагент': cp_final,
            'Наименование счета': account_name,
            'Описание': combined
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


# ==================== Kapital ====================

def parse_kapital_saida_xlsx(file_content: bytes, account_name: str) -> List[Dict]:
    result: List[Dict] = []

    df = None
    try:
        df = pd.read_excel(BytesIO(file_content), sheet_name='AZ', header=None)
    except Exception:
        df = None
    if df is None or df.empty:
        try:
            df = pd.read_excel(BytesIO(file_content), header=None)
        except Exception:
            return []

    if df is None or df.empty:
        return []

    header_row = -1
    for idx, row in df.iterrows():
        vals = [str(v).strip() if pd.notna(v) else '' for v in row.values]
        joined = ' '.join(vals).lower()
        if ('tarix' in joined) and ('məxaric' in joined or 'mexaric' in joined) \
                and ('mədaxil' in joined or 'medaxil' in joined):
            header_row = idx
            break

    if header_row == -1:
        return []

    hdr_vals = [str(v).strip() if pd.notna(v) else '' for v in df.iloc[header_row].values]

    def _find_col(patterns: List[str]) -> int:
        for i, h in enumerate(hdr_vals):
            hl = h.lower()
            if any(p in hl for p in patterns):
                return i
        return -1

    date_i = _find_col(['tarix'])
    debit_i = _find_col(['məxaric', 'mexaric'])
    credit_i = _find_col(['mədaxil', 'medaxil'])
    desc_i = _find_col(['təsvir', 'tesvir', 'описание', 'description'])
    code_i = _find_col(['kod', 'код', 'code'])

    if date_i == -1:
        date_i = 1
    if debit_i == -1:
        debit_i = 2
    if credit_i == -1:
        credit_i = 3
    if desc_i == -1:
        desc_i = 5
    if code_i == -1:
        code_i = 6

    seen_keys = set()

    for idx in range(header_row + 1, len(df)):
        row = df.iloc[idx]
        n = len(row)

        def _get(ci: int):
            if 0 <= ci < n:
                v = row.iloc[ci]
                if pd.isna(v):
                    return ''
                return str(v).strip()
            return ''

        date_raw = _get(date_i)
        debit_raw = _get(debit_i)
        credit_raw = _get(credit_i)
        desc_raw = _get(desc_i)
        code_raw = _get(code_i)

        joined_row = ' '.join([date_raw, debit_raw, credit_raw, desc_raw]).lower()
        if ('tarix' in joined_row and ('məxaric' in joined_row or 'mexaric' in joined_row)
                and ('mədaxil' in joined_row or 'medaxil' in joined_row)):
            continue

        if not date_raw and not debit_raw and not credit_raw and not desc_raw:
            continue

        date = parse_date(date_raw)
        if not date or not re.match(r'^\d{2}-\d{2}-\d{4}$', date):
            continue

        debit_val = parse_amount(debit_raw) if debit_raw else 0.0
        credit_val = parse_amount(credit_raw) if credit_raw else 0.0

        amount = 0.0
        if credit_val != 0.0 and abs(credit_val) > abs(debit_val):
            amount = abs(credit_val)
        elif debit_val != 0.0:
            amount = -abs(debit_val)
        elif credit_val != 0.0:
            amount = abs(credit_val)
        else:
            continue

        if not _is_reasonable_amount(amount):
            continue

        desc_parts = []
        if desc_raw:
            desc_parts.append(desc_raw)
        if code_raw and code_raw.lower() not in ('nan', 'none'):
            if not desc_raw:
                desc_parts.append(code_raw)
            elif len(code_raw) < 20:
                desc_parts.append(code_raw)

        desc = ' | '.join(desc_parts) if len(desc_parts) > 1 else (desc_parts[0] if desc_parts else '')

        if not desc:
            desc = code_raw or ''

        cp_final, _ = extract_counterparty_smart(desc, account_name)
        if not cp_final:
            cp_final = 'Kapital Bank'

        key = (date, round(amount, 2), cp_final, desc)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        result.append({
            'Дата': date,
            'Сумма': amount,
            'Контрагент': cp_final,
            'Наименование счета': account_name,
            'Описание': desc
        })

    return result


def parse_kapital_saida_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    result: List[Dict] = []

    tables = pdf_all_tables(file_content)
    for table in tables:
        if not table or len(table) < 2:
            continue

        header_idx = -1
        for i, row in enumerate(table):
            joined = ' '.join([str(c or '') for c in row]).lower()
            if 'tarix' in joined and ('məxaric' in joined or 'mexaric' in joined) \
                    and ('mədaxil' in joined or 'medaxil' in joined):
                header_idx = i
                break
        if header_idx == -1:
            continue

        hdr = table[header_idx]
        ci = {}
        for i, h in enumerate(hdr):
            hl = (h or '').lower()
            if 'tarix' in hl and 'date' not in ci:
                ci['date'] = i
            elif ('məxaric' in hl or 'mexaric' in hl) and 'debit' not in ci:
                ci['debit'] = i
            elif ('mədaxil' in hl or 'medaxil' in hl) and 'credit' not in ci:
                ci['credit'] = i
            elif ('təsvir' in hl or 'tesvir' in hl or 'описание' in hl) and 'desc' not in ci:
                ci['desc'] = i

        if 'date' not in ci:
            continue
        if 'debit' not in ci and 'credit' not in ci:
            continue

        for row in table[header_idx + 1:]:
            if not row:
                continue
            cells = [str(c or '').strip() for c in row]
            joined = ' '.join(cells).lower()
            if 'tarix' in joined and ('məxaric' in joined or 'mədaxil' in joined):
                continue

            def _cell(ci_key):
                idx_c = ci.get(ci_key, -1)
                if 0 <= idx_c < len(cells):
                    return cells[idx_c]
                return ''

            date = parse_date(_cell('date'))
            if not date or not re.match(r'^\d{2}-\d{2}-\d{4}$', date):
                continue

            debit_raw = _cell('debit')
            credit_raw = _cell('credit')

            def _split_stuck(s: str) -> Tuple[float, float]:
                s = (s or '').strip()
                if not s:
                    return 0.0, 0.0
                m = re.fullmatch(r'(\d+)[.,](\d{2})(\d)', s)
                if m:
                    a = float(f"{m.group(1)}.{m.group(2)}")
                    b = float(m.group(3))
                    return a, b
                m = re.fullmatch(r'0(\d+[.,]\d{2})', s)
                if m:
                    b = float(m.group(1).replace(',', '.'))
                    return 0.0, b
                v = parse_amount(s)
                return v, 0.0

            d1, c1 = _split_stuck(debit_raw)
            d2, c2 = _split_stuck(credit_raw)

            debit_val = max(d1, d2)
            credit_val = max(c1, c2)

            amount = 0.0
            if credit_val != 0.0 and abs(credit_val) >= abs(debit_val):
                amount = abs(credit_val)
            elif debit_val != 0.0:
                amount = -abs(debit_val)
            else:
                continue

            if not _is_reasonable_amount(amount):
                continue

            desc = _cell('desc')
            cp_final, _ = extract_counterparty_smart(desc, account_name)
            if not cp_final:
                cp_final = 'Kapital Bank'

            result.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': cp_final,
                'Наименование счета': account_name,
                'Описание': desc
            })

    if result:
        return result

    full_text = pdf_all_text(file_content)
    if not full_text:
        return []

    line_re = re.compile(
        r'^\s*(\d{4}-\d{2}-\d{2})\s+'
        r'([\d.,]+)\s+'
        r'([\d.,]+)\s*'
        r'([\d.,]+)\s+'
        r'(.+?)\s*$',
        re.MULTILINE
    )

    for m in line_re.finditer(full_text):
        date = parse_date(m.group(1))
        if not date:
            continue

        g2 = m.group(2)
        g3 = m.group(3)
        g4 = m.group(4)
        desc = m.group(5).strip()

        def _split_stuck(s: str) -> Tuple[float, float]:
            s = (s or '').strip()
            if not s:
                return 0.0, 0.0
            m1 = re.fullmatch(r'(\d+)[.,](\d{2})(\d)', s)
            if m1:
                a = float(f"{m1.group(1)}.{m1.group(2)}")
                b = float(m1.group(3))
                return a, b
            m2 = re.fullmatch(r'0(\d+[.,]\d{2})', s)
            if m2:
                b = float(m2.group(1).replace(',', '.'))
                return 0.0, b
            v = parse_amount(s)
            return v, 0.0

        d1, c1 = _split_stuck(g2)
        d2, c2 = _split_stuck(g3)

        debit_val = max(d1, d2)
        credit_val = max(c1, c2)

        amount = 0.0
        if credit_val != 0.0 and abs(credit_val) >= abs(debit_val):
            amount = abs(credit_val)
        elif debit_val != 0.0:
            amount = -abs(debit_val)
        else:
            continue

        if not _is_reasonable_amount(amount):
            continue

        cp_final, _ = extract_counterparty_smart(desc, account_name)
        if not cp_final:
            cp_final = 'Kapital Bank'

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
        key = (r['Дата'], round(r['Сумма'], 2), r['Контрагент'], r['Описание'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped


def parse_kapital_saida_azn_csv(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    content = read_text_with_encoding(file_content)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if not lines:
        return []

    sample = '\n'.join(lines[:5])
    sep = ';' if sample.count(';') >= sample.count(',') else ','

    header_idx = -1
    for i, l in enumerate(lines[:30]):
        low = l.lower()
        if 'tarix' in low and ('məxaric' in low or 'mexaric' in low) \
                and ('mədaxil' in low or 'medaxil' in low):
            header_idx = i
            break
    if header_idx == -1:
        return []

    hdr = _split_line(lines[header_idx], sep)

    def _find_col(patterns):
        for i, h in enumerate(hdr):
            hl = h.lower().strip()
            if any(p in hl for p in patterns):
                return i
        return -1

    date_i = _find_col(['tarix'])
    debit_i = _find_col(['məxaric', 'mexaric'])
    credit_i = _find_col(['mədaxil', 'medaxil'])
    desc_i = _find_col(['təsvir', 'tesvir'])
    code_i = _find_col(['kod', 'код'])

    if date_i == -1:
        date_i = 0
    if debit_i == -1:
        debit_i = 1
    if credit_i == -1:
        credit_i = 2
    if desc_i == -1:
        desc_i = 4

    for line in lines[header_idx + 1:]:
        parts = _split_line(line, sep)
        if len(parts) <= max(date_i, debit_i, credit_i):
            continue
        joined_low = ' '.join(parts).lower()
        if 'tarix' in joined_low and ('məxaric' in joined_low or 'mədaxil' in joined_low):
            continue

        date = parse_date(parts[date_i])
        if not date or not re.match(r'^\d{2}-\d{2}-\d{4}$', date):
            continue

        debit_val = parse_amount(parts[debit_i]) if debit_i < len(parts) else 0.0
        credit_val = parse_amount(parts[credit_i]) if credit_i < len(parts) else 0.0

        amount = 0.0
        if credit_val != 0.0 and abs(credit_val) > abs(debit_val):
            amount = abs(credit_val)
        elif debit_val != 0.0:
            amount = -abs(debit_val)
        elif credit_val != 0.0:
            amount = abs(credit_val)
        else:
            continue

        if not _is_reasonable_amount(amount):
            continue

        desc = parts[desc_i] if desc_i < len(parts) else ''
        if code_i >= 0 and code_i < len(parts) and parts[code_i]:
            desc = f"{desc} | {parts[code_i]}" if desc else parts[code_i]

        cp_final, _ = extract_counterparty_smart(desc, account_name)
        if not cp_final:
            cp_final = 'Kapital Bank'

        result.append({
            'Дата': date, 'Сумма': amount,
            'Контрагент': cp_final,
            'Наименование счета': account_name,
            'Описание': desc
        })
    return result


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


# ==================== MKB ====================

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
                    cp_final, _ = extract_counterparty_smart(desc, account_name, cp, cp)
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
            cp_final, _ = extract_counterparty_smart(desc, account_name, cp, cp)
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
                cp_final, _ = extract_counterparty_smart(desc, account_name, cp, cp)
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp_final if cp_final else '',
                    'Наименование счета': account_name,
                    'Описание': desc
                })
            except Exception:
                continue
    return result


# ==================== N26 ====================

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


def parse_n26_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    full_text = pdf_all_text(file_content)
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
            if any(w in low for w in ['saldo previo', 'nuevo saldo', 'transacciones',
                                      'extracto', 'espacio', 'deseño']):
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
    if not result:
        pattern2 = re.compile(
            r'(\d{2}\.\d{2}\.\d{4})\s+(\d{2}\.\d{2}\.\d{4})\s+(-?\d[\d\s]*[.,]\d{2})\s*€',
            re.MULTILINE
        )
        for m in pattern2.finditer(full_text):
            try:
                date = parse_date(m.group(1))
                amount = parse_amount(m.group(3))
                if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': 'N26',
                    'Наименование счета': account_name,
                    'Описание': ''
                })
            except Exception:
                continue
    return result


# ==================== Paysera ====================

def parse_paysera_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """
    [FIX-COUNTERPARTY-FULL-V4] Paysera XLSX: имя из колонки "Получатель / Плательщик".
    Передаём его и как beneficiary, и как payer, чтобы приоритет был максимальным.
    """
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
            cp_raw = safe_str(row.iloc[ci['counterparty']]) if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
            cp_raw = re.sub(r'\([^)]*\)', ' ', cp_raw)
            cp_raw = re.sub(r'\s+', ' ', cp_raw).strip()
            desc = safe_str(row.iloc[ci['purpose']]) if 'purpose' in ci and ci['purpose'] < len(row) else ''
            cp_final, _ = extract_counterparty_smart(desc, account_name, cp_raw, cp_raw)
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
            cp_final, _ = extract_counterparty_smart(desc, account_name, counterparty, counterparty)
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
    if not result:
        pattern2 = re.compile(
            r'([A-Za-zА-Яа-я][A-Za-zА-Яа-я\s]{2,40}?)'
            r'\s+'
            r'(\d{4}-\d{2}-\d{2})'
            r'\s+'
            r'(\d{2}:\d{2}:\d{2})'
            r'(?:\s+[+\-]\d{4})?'
            r'\s+'
            r'(\d{6,})'
            r'\s*'
            r'([A-Za-zА-Яа-я][^\d\-+]{2,500}?)'
            r'\s+'
            r'(-?\d[\d\s]*[.,]\d{2})\s*([A-Z]{3})',
            re.MULTILINE
        )
        for m in pattern2.finditer(full_text):
            try:
                date = parse_date(m.group(2))
                amount = parse_amount(m.group(7))
                counterparty = re.sub(r'\s+', ' ', m.group(5)).strip()
                op_type = m.group(1).strip()
                if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                cp_final, _ = extract_counterparty_smart(counterparty, account_name, counterparty, counterparty)
                if not cp_final:
                    cp_final = counterparty
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp_final,
                    'Наименование счета': account_name,
                    'Описание': f"{op_type}: {counterparty}"
                })
            except Exception:
                continue
    return result


def parse_paysera_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    """
    [FIX-COUNTERPARTY-FULL-V4] Paysera PDF.
    """
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
    if current_lines:
        blocks.append(current_lines)

    date_time_re = re.compile(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})')
    amount_re = re.compile(r'(-?\d[\d\s\u00a0]*[.,]\d{2})\s*EUR')
    purpose_re = re.compile(r'Назначение\s+платежа\s*:\s*(.*)$', re.IGNORECASE | re.DOTALL)

    for block in blocks:
        block_text = '\n'.join(block)

        purpose = ''
        pm = purpose_re.search(block_text)
        if pm:
            purpose = re.sub(r'\s+', ' ', pm.group(1)).strip()

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

        cp = ''
        iban_match = re.search(r'([A-Z]{2}\d{2}[A-Z0-9]{10,30})', block_text)
        if iban_match:
            before_iban = block_text[:iban_match.start()]
            m_num = None
            for m in re.finditer(r'\b\d{9,}\b', before_iban):
                m_num = m
            if m_num:
                name_part = before_iban[m_num.end():].strip()
            else:
                name_part = before_iban
            name_part = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', ' ', name_part)
            name_part = re.sub(r'\b\d{2}:\d{2}:\d{2}\b', ' ', name_part)
            name_part = re.sub(r'\+\d{4}', ' ', name_part)
            name_part = re.sub(r'\b(Paysera LT|Комиссионная плата|Перевод)\b', ' ', name_part, flags=re.IGNORECASE)
            name_part = re.sub(r'\(\s*\d+\s*\)', ' ', name_part)
            name_part = re.sub(r'\s+', ' ', name_part).strip(' .,;:-')
            name_part = re.sub(r'\s+[A-Z]\d{4,}\s*$', '', name_part)
            if name_part and len(name_part) >= 3 and not _looks_like_bank_name(name_part):
                cp = name_part

        if not cp:
            for line in block:
                ln = line.strip()
                if not ln:
                    continue
                if re.match(r'^\d{4}-\d{2}-\d{2}', ln):
                    continue
                if 'назначение' in ln.lower():
                    continue
                if re.match(r'^(Перевод|Комиссионная)', ln):
                    continue
                if 'Плата за обслуживание' in ln:
                    cp = 'Paysera LT'
                    break

        cp_final, _ = extract_counterparty_smart(purpose, account_name, cp, cp)

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

def parse_revolut_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """
    [FIX-COUNTERPARTY-FULL-V4] Revolut CSV:
    полные имена из колонок Payer / Beneficiary name.
    """
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
        elif hl == 'payer' and 'payer' not in ci:
            ci['payer'] = i
        elif hl == 'state' and 'state' not in ci:
            ci['state'] = i
        elif hl == 'type' and 'type' not in ci:
            ci['type'] = i
        elif 'beneficiary' in hl and 'name' in hl and 'beneficiary' not in ci:
            ci['beneficiary'] = i
        elif hl == 'beneficiary' and 'beneficiary' not in ci:
            ci['beneficiary'] = i
        elif hl == 'sender name' and 'sender' not in ci:
            ci['sender'] = i
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
            payer = parts[ci['payer']] if 'payer' in ci and ci['payer'] < len(parts) else ''
            beneficiary = parts[ci['beneficiary']] if 'beneficiary' in ci and ci['beneficiary'] < len(parts) else ''
            sender = parts[ci['sender']] if 'sender' in ci and ci['sender'] < len(parts) else ''
            # Если beneficiary пуст, но есть sender — используем sender
            if not beneficiary and sender:
                beneficiary = sender
            desc = parts[ci['description']] if ci['description'] < len(parts) else ''
            reference = parts[ci['reference']] if 'reference' in ci and ci['reference'] < len(parts) else ''

            full_desc = desc
            if reference and reference.strip() and reference.strip() != 'nan':
                full_desc = f"{desc} | {reference}" if desc else reference

            cp_final, _ = extract_counterparty_smart(full_desc, account_name, payer, beneficiary)

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


def parse_revolut_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    """
    [FIX-COUNTERPARTY-FULL-V4] Revolut PDF.
    """
    result = []
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []

    date_re = re.compile(
        r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{4})\s+(.*)$',
        re.IGNORECASE | re.MULTILINE
    )
    type_re = re.compile(r'\b(MOA|MOS|MOR|FEE|CAR|ATM|EXO|EXI|TOPUP|TRANSFER)\b')
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
                    'exchange in', 'revolut fees'
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
            continue
        amount_match = eur_matches[0]
        amount = parse_amount(amount_match.group(0))
        if amount == 0.0 or not _is_reasonable_amount(amount):
            continue
        desc_main = after[:amount_match.start()].strip()
        parts = [desc_main] + op['continuation']
        desc = ' '.join(p for p in parts if p)
        desc = re.sub(r'\s+', ' ', desc).strip()
        desc = desc.strip(' •')

        if ttype in ('MOA', 'MOR', 'TOPUP'):
            amount = abs(amount)
        elif ttype in ('MOS', 'FEE', 'CAR', 'ATM', 'EXO'):
            amount = -abs(amount)

        cp_final, _ = extract_counterparty_smart(desc, account_name)

        result.append({
            'Дата': date,
            'Сумма': amount,
            'Контрагент': cp_final if cp_final else '',
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
            cp_final, _ = extract_counterparty_smart(desc, account_name, cp, cp)
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


def parse_unicredit_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    tables = pdf_all_tables(file_content)
    for table in tables:
        header_idx = -1
        for i, row in enumerate(table):
            joined = ' '.join(row).lower()
            if 'amount' in joined and ('booking' in joined or 'date' in joined):
                header_idx = i
                break
        if header_idx == -1:
            continue
        hdr = table[header_idx]
        ci = {}
        for i, h in enumerate(hdr):
            hl = h.lower()
            if 'amount' in hl:
                ci['amount'] = i
            elif 'booking' in hl or 'date' in hl:
                ci['date'] = i
            elif 'transaction details' in hl or 'details' in hl:
                ci['description'] = i
            elif 'name' in hl:
                ci['counterparty'] = i
        for row in table[header_idx + 1:]:
            try:
                amount = parse_amount(row[ci.get('amount', 1)] if ci.get('amount', 1) < len(row) else '')
                if amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                date = parse_date(row[ci.get('date', 3)] if ci.get('date', 3) < len(row) else '')
                if not date:
                    continue
                cp = row[ci.get('counterparty', 9)] if ci.get('counterparty', 9) < len(row) else ''
                desc = row[ci.get('description', 13)] if ci.get('description', 13) < len(row) else ''
                cp_final, _ = extract_counterparty_smart(desc, account_name, cp, cp)
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp_final if cp_final else '',
                    'Наименование счета': account_name,
                    'Описание': desc
                })
            except Exception:
                continue
    if not result:
        full_text = pdf_all_text(file_content)
        pattern = re.compile(
            r'(-?\d[\d\s]*[.,]\d{2})\s*[;,]?\s*([A-Z]{3})\s*[;,]?\s*(\d{4}-\d{2}-\d{2})\s*[;,]?\s*([^\n;]{3,1000})',
            re.MULTILINE
        )
        for m in pattern.finditer(full_text):
            try:
                amount = parse_amount(m.group(1))
                date = parse_date(m.group(3))
                desc = re.sub(r'\s+', ' ', m.group(4)).strip()
                if not date or amount == 0.0 or not _is_reasonable_amount(amount):
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


# ==================== Saida N26 (CSV) ====================

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


def parse_saida_wise(file_content, account_name):
    return parse_saida_n26_csv(file_content, account_name)


# ==================== Saida Wise XLSX ====================

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
            cp_final, _ = extract_counterparty_smart(desc, account_name, cp, cp)
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
                cp_final, _ = extract_counterparty_smart(desc, account_name, cp, cp)
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


# ==================== Универсальный PDF fallback ====================

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
                cp_final, _ = extract_counterparty_smart(desc, account_name, cp, cp)
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp_final if cp_final else '',
                    'Наименование счета': account_name,
                    'Описание': desc
                })
            except Exception:
                continue
    return result


# ==================== Общие CSV/XLSX/DOCX ====================

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
            cp_final, _ = extract_counterparty_smart(desc, account_name, cp, cp)
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
            cp_final, _ = extract_counterparty_smart(desc, account_name, cp, cp)
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
                cp_final, _ = extract_counterparty_smart(desc, account_name, cp, cp)
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


# ==================== МАРШРУТИЗАЦИЯ ====================

def get_parser_by_ext(account_name: str, ext: str):
    low = account_name.lower()
    is_kapital_saida = ('kapital' in low) or ('saida' in low and 'azn' in low)

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
            return parse_jenhor_unelma_pdf, 'jenhor_unelma_pdf'
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
        if 'unicredit' in low or 'garpiz' in low or 'twohills' in low or 'koruna' in low or 'b1 estate' in low:
            return parse_unicredit_pdf, 'unicredit_pdf'
        if 'wio' in low:
            return parse_wio_pdf, 'wio_pdf'
        if 'pasha' in low or 'bunda' in low:
            return parse_pasha_bank_pdf, 'pasha_bank_pdf'
        return parse_pdf_universal, 'pdf_universal'

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
        if 'unicredit' in low or 'garpiz' in low or 'twohills' in low or 'two hills' in low or 'b1 estate' in low or 'b1_estate' in low:
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
        if 'unicredit' in low or 'garpiz' in low or 'twohills' in low or 'two hills' in low or 'b1 estate' in low or 'b1_estate' in low:
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


# ==================== ЦЕПОЧКА КАНДИДАТОВ ====================

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
        _add(op, ok or f'{oe[1:]} _other')

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
                t['Наименование банка'] = account_name
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
    bank_col = "Наименование банка" if "Наименование банка" in df.columns else "Наименование счета"
    if bank_col not in df.columns or "Сумма" not in df.columns:
        return pd.DataFrame(columns=columns)

    df = df.copy()
    df["Сумма"] = df["Сумма"].map(to_float_amount)
    df[bank_col] = df[bank_col].fillna("").astype(str)

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


# ==================== ЭКСПОРТ ====================

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

    sum_col_name = 'Сумма'
    sum_col_idx = None
    for j, col_name in enumerate(df_export.columns, start=1):
        if col_name == sum_col_name:
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

    bank_series = df_numeric['Наименование банка'] if 'Наименование банка' in df_numeric.columns else df_numeric.get('Наименование счета', pd.Series([''] * len(df_numeric)))

    df_export = pd.DataFrame({
        'Дата': df_numeric['Дата'].astype(str),
        'Сумма': df_numeric['Сумма'].astype(float),
        'Контрагент': df_numeric['Контрагент'].astype(str),
        'Наименование банка': bank_series.astype(str),
        'Описание': df_display['Описание'].astype(str) if 'Описание' in df_display.columns else df_numeric.get('Описание', pd.Series([''] * len(df_numeric))).astype(str),
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

    bank_series = df_numeric['Наименование банка'] if 'Наименование банка' in df_numeric.columns else df_numeric.get('Наименование счета', pd.Series([''] * len(df_numeric)))

    df_export = pd.DataFrame({
        'Дата': df_numeric['Дата'].astype(str),
        'Сумма': df_numeric['Сумма'].astype(float),
        'Контрагент': df_numeric['Контрагент'].astype(str),
        'Наименование банка': bank_series.astype(str),
        'Описание': df_display['Описание'].astype(str) if 'Описание' in df_display.columns else df_numeric.get('Описание', pd.Series([''] * len(df_numeric))).astype(str),
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


# ==================== ОБРАБОТКА ====================

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
            debug_info.append(f"❌ `{uf.name}` → исключение: {e}")

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

    df_raw = pd.DataFrame(all_tx)
    df_raw['Сумма_число'] = df_raw['Сумма'].map(to_float_amount)
    # [FIX-RENAME-COLUMN-V4] Переименовываем в "Наименование банка"
    if 'Наименование счета' in df_raw.columns:
        df_raw = df_raw.rename(columns={'Наименование счета': 'Наименование банка'})

    income = float(df_raw['Сумма_число'][df_raw['Сумма_число'] > 0].sum())
    expense = float(abs(df_raw['Сумма_число'][df_raw['Сумма_число'] < 0].sum()))

    bank_series = df_raw['Наименование банка'].astype(str) if 'Наименование банка' in df_raw.columns else ''

    df_numeric = pd.DataFrame({
        'Дата': df_raw['Дата'].astype(str),
        'Сумма': df_raw['Сумма_число'].astype(float),
        'Контрагент': df_raw['Контрагент'].astype(str) if 'Контрагент' in df_raw.columns else '',
        'Наименование банка': bank_series,
        'Описание': df_raw['Описание'].astype(str) if 'Описание' in df_raw.columns else '',
    })

    df_display = df_raw.drop(columns=['Сумма_число']).copy()
    df_display['Сумма'] = df_raw['Сумма_число'].apply(format_amount)
    if 'Описание' in df_display.columns:
        df_display['Описание'] = df_display['Описание'].apply(
            lambda x: translate_description_inline(str(x)) if x is not None else ''
        )

    st.session_state['df_numeric'] = df_numeric
    st.session_state['df_display'] = df_display
    st.session_state['df_raw'] = df_raw

    st.markdown("---")
    st.markdown("### 📊 Итоги")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("📊 Всего операций", len(all_tx))
    with c2:
        st.metric("📈 Доходы", format_amount(income))
    with c3:
        st.metric("📉 Расходы", format_amount(expense))

    st.markdown("---")
    st.markdown("### 🤖 AI-обогащение транзакций (DeepSeek)")
    st.caption(
        "DeepSeek переведёт описания, определит категорию и вытащит чистое имя "
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
        with st.spinner("DeepSeek обрабатывает транзакции..."):
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
                    'Дата': tx.get('Дата', ''),
                    'Сумма': tx.get('Сумма', 0),
                    'Банк': tx.get('Наименование банка', tx.get('Наименование счета', '')),
                    'Оригинал': tx.get('Описание', ''),
                    'Перевод AI': tx.get('_ai_translation', ''),
                    'Категория AI': tx.get('_ai_category', ''),
                    'Контрагент AI': tx.get('_ai_counterparty_clean', ''),
                    'Банк. комиссия': tx.get('_ai_is_bank_fee', False),
                    'Уверенность': tx.get('_ai_confidence', 0.0),
                })
        if ai_rows:
            ai_df = pd.DataFrame(ai_rows)
            st.dataframe(ai_df, use_container_width=True, hide_index=True)
            st.session_state['ai_df'] = ai_df
        else:
            st.info("AI не вернул данных по этим строкам.")

    st.markdown("---")
    st.markdown("### 🧾 Детализация транзакций")
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### 📁 Сводка по счетам")
    summary_df = build_account_summary(df_raw.to_dict('records'))
    if summary_df.empty:
        st.info("Нет данных для сводки по счетам.")
    else:
        summary_html_df = summary_df.copy()
        for col in ["Сумма приходных операций", "Сумма расходных операций", "Сальдо операций"]:
            summary_html_df[col] = summary_html_df[col].apply(format_amount)
        st.markdown(
            f'<div class="summary-table">{summary_html_df.to_html(index=False, escape=False)}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### 💾 Сохранить результат")
    st.markdown(
        "Скачайте **отдельно операции по выпискам** и **отдельно сводную таблицу**, "
        "или всё вместе одним файлом. В Excel суммы — числа с форматом `0,00`."
    )

    ops_excel = build_operations_excel(df_display, df_numeric)
    summary_excel = build_summary_excel(summary_df) if not summary_df.empty else None
    ai_df_for_excel = st.session_state.get('ai_df')
    combined_excel = build_combined_excel(df_display, df_numeric, summary_df, ai_df_for_excel) if not summary_df.empty else None

    dl1, dl2, dl3 = st.columns(3)

    with dl1:
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
        else:
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
    st.markdown("### 🤖 AI-ассистент (DeepSeek)")
    st.caption(
        "Задавайте вопросы по коду, данным и обработке выписок. "
        "Ассистент видит только то, что вы ему напишите — файлы не отправляются автоматически."
    )

    client = _get_deepseek_client()
    if client is None:
        if not _OPENAI_SDK_AVAILABLE:
            st.markdown(
                '<span class="ai-status-warn">⚠️ Библиотека openai не установлена. '
                'Выполните: <code>pip install openai</code></span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<span class="ai-status-warn">⚠️ API-ключ DeepSeek не задан. '
                'Введите его ниже или в <code>.streamlit/secrets.toml</code></span>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<span class="ai-status-ok">✅ DeepSeek подключён</span>',
            unsafe_allow_html=True,
        )

    with st.expander("🔑 Настройка API-ключа", expanded=(client is None)):
        st.markdown(
            "Получите ключ на [platform.deepseek.com](https://platform.deepseek.com). "
            "Ключ можно хранить в `.streamlit/secrets.toml`:\n\n"
            "```toml\nDEEPSEEK_API_KEY = \"sk-...\"\n```\n\n"
            "Или ввести здесь — он сохранится только в текущей сессии."
        )
        key_input = st.text_input(
            "API-ключ DeepSeek",
            value=st.session_state.get('deepseek_api_key', ''),
            type='password',
            key='deepseek_key_input',
        )
        if st.button("💾 Сохранить ключ в сессии", key='save_deepseek_key'):
            st.session_state['deepseek_api_key'] = key_input.strip()
            st.success("Ключ сохранён в сессии.")
            st.rerun()

    st.markdown("---")

    model_choice = st.selectbox(
        "Модель",
        options=[DEEPSEEK_DEFAULT_MODEL, DEEPSEEK_REASONER_MODEL],
        index=0,
        key='deepseek_model_choice',
        help="deepseek-chat — быстрая; deepseek-reasoner — для отладки кода.",
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
                f'<div class="ai-chat-bubble-assistant"><b>DeepSeek:</b><br>'
                f'{msg["content"]}</div>',
                unsafe_allow_html=True,
            )

    if quick_prompt:
        st.session_state['ai_chat_history'].append({'role': 'user', 'content': quick_prompt})
        with st.spinner("DeepSeek думает..."):
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(st.session_state['ai_chat_history'])
            answer, err = call_deepseek(messages, model=model_choice)
        if err:
            st.session_state['ai_chat_history'].append({'role': 'assistant', 'content': f"❌ {err}"})
        else:
            st.session_state['ai_chat_history'].append({'role': 'assistant', 'content': answer})
        st.rerun()

    user_input = st.chat_input("Спросите DeepSeek о коде, данных или обработке...")
    if user_input:
        st.session_state['ai_chat_history'].append({'role': 'user', 'content': user_input})
        with st.spinner("DeepSeek думает..."):
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(st.session_state['ai_chat_history'])
            answer, err = call_deepseek(messages, model=model_choice)
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
                    answer, err = call_deepseek(messages, model=model_choice, max_tokens=3000)
                if err:
                    st.error(err)
                else:
                    st.markdown("**Ответ DeepSeek:**")
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
        client = _get_deepseek_client()
        if client is not None:
            st.success("✅ Подключён")
        else:
            st.warning("⚠️ Не подключён")
            st.caption("Введите ключ во вкладке «AI-ассистент».")
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
