# -*- coding: utf-8 -*-
"""
app.py — Аналитик банковских выписок.
FIX-пакет v5:
  [FIX-RENDER-SCALAR-V5] — устранена ошибка pd.DataFrame при list/None в колонках.
                            Добавлена функция _to_scalar_str(), все колонки
                            приводятся к строкам ДО построения df_numeric.
  [FIX-RENAME-COLUMN-V4]  — "Наименование счета" → "Наименование банка"
  [FIX-COUNTERPARTY-FULL-V4] — приоритет Beneficiary/Payer
  ... (остальные фиксы из v4)
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
from typing import Dict, List, Tuple, Callable, Optional, Any
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


# ==================== DEEPSEEK ====================

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
        return "", "API-ключ DeepSeek не задан."
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
        return None, f"Не удалось распарсить JSON: {raw[:300]}"


_AI_TRANSACTION_SYSTEM = (
    "Ты — эксперт по банковским выпискам. "
    "На вход получаешь транзакцию. Верни СТРОГО JSON:\n"
    "{\n"
    '  "translation": "перевод описания на русский",\n'
    '  "category": "категория",\n'
    '  "counterparty_clean": "чистое имя контрагента",\n'
    '  "is_bank_fee": true/false,\n'
    '  "confidence": 0.0-1.0\n'
    "}\n"
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
        return transactions, ["DeepSeek недоступен"]

    subset = transactions[:max_items]
    enriched = [dict(t) for t in transactions]

    for i, tx in enumerate(subset):
        desc = str(tx.get("Описание", ""))[:1500]
        acc = str(tx.get("Наименование банка", tx.get("Наименование счета", "")))
        amount = tx.get("Сумма", 0)
        user_prompt = f"Банк: {acc}\nСумма: {amount}\nОписание: {desc}\n"
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
    "Предложи конкретное исправление. Не читай лекции, отвечай по делу."
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


# ==================== [FIX-RENDER-SCALAR-V5] САНИТАЙЗЕР ====================

def _to_scalar_str(v: Any) -> str:
    """
    [FIX-RENDER-SCALAR-V5]
    Превращает любое значение (включая list, tuple, dict, None, NaN)
    в СКАЛЯРНУЮ строку. Используется перед построением DataFrame,
    чтобы избежать ValueError при сборке pd.DataFrame из series,
    содержащих не-скалярные элементы.
    """
    if v is None:
        return ''
    # NaN / NaT
    try:
        if pd.isna(v):
            return ''
    except Exception:
        pass
    if isinstance(v, str):
        return v
    if isinstance(v, (list, tuple)):
        try:
            return ' | '.join(_to_scalar_str(x) for x in v if x is not None and str(x).strip() != '')
        except Exception:
            return str(v)
    if isinstance(v, dict):
        try:
            return ' | '.join(f"{_to_scalar_str(k)}: {_to_scalar_str(val)}" for k, val in v.items())
        except Exception:
            return str(v)
    try:
        return str(v)
    except Exception:
        return ''


def _safe_str_series(series: pd.Series) -> pd.Series:
    """
    [FIX-RENDER-SCALAR-V5]
    Приводит pandas.Series к строковому типу, безопасно обрабатывая
    списки, dict, None, NaN.
    """
    if series is None:
        return pd.Series(dtype=str)
    try:
        return series.map(_to_scalar_str).astype(str)
    except Exception:
        return pd.Series([''] * len(series), index=series.index, dtype=str)


# ==================== [FIX-TRANSLATE-FULL] СЛОВАРИ ====================

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
    low = str(desc).lower().strip()
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
    low = str(s).lower()
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


def _extract_revolut_name(desc: str,
                           account_name: str = '',
                           payer: str = '',
                           beneficiary: str = '') -> str:
    if beneficiary:
        c = str(beneficiary).strip()
        if c and c.lower() not in ('nan', 'none', 'n/a', '-'):
            cleaned = _clean_counterparty_name(c, keep_full=True)
            if cleaned and len(cleaned) >= 2:
                return cleaned
    if payer:
        c = str(payer).strip()
        if c and c.lower() not in ('nan', 'none', 'n/a', '-'):
            cleaned = _clean_counterparty_name(c, keep_full=True)
            if cleaned and len(cleaned) >= 2:
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
    for cand in (beneficiary, payer):
        if cand:
            c = str(cand).strip()
            if c.lower() in ('nan', 'none', 'n/a', '-', ''):
                continue
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
    Возвращает КОРТЕЖ (cp, desc). cp — строка или ''.
    [FIX-RENDER-SCALAR-V5]: всегда возвращает скалярные строки.
    """
    desc = (description or '').strip()
    acc_low = (account_name or '').lower()

    # --- 1) Явные поля ВСЕГДА приоритетны ---
    if beneficiary:
        b = str(beneficiary).strip()
        if b and b.lower() not in ('nan', 'none', 'n/a', '-'):
            cleaned = _clean_counterparty_name(b, keep_full=True)
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

    # --- 2) Спец-парсеры ---
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

    # [FIX-RENDER-SCALAR-V5] гарантируем скаляр
    cp = _to_scalar_str(cp)
    desc = _to_scalar_str(desc)
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


# ==================== ПАРСЕРЫ (без изменений от v4) ====================

# ... (все парсеры CSOB, Tinkoff, BluOr, JenHor, Stalkin, Industra, Kapital,
#      MASHREQ, MKB, N26, Paysera, RAK, Revolut, UniCredit, WIO, Saida,
#      Pasha, Universal — идентичны v4)

# Для краткости я опускаю их здесь, но они ДОЛЖНЫ присутствовать в файле
# полностью — как в предыдущем ответе v4. Ниже только ключевые для
# рендера функции, которые изменились.


# ==================== ФУНКЦИИ РЕНДЕРА (С ИСПРАВЛЕНИЯМИ v5) ====================

def build_account_summary(rows: List[Dict]) -> pd.DataFrame:
    """
    [FIX-RENDER-SCALAR-V5]
    Работает и с 'Наименование банка', и с 'Наименование счета'.
    """
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
    # Безопасно приводим к строкам
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

    # [FIX-RENDER-SCALAR-V5] Безопасно выбираем колонку банка
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
                            f"⚠️ `{uf.name}`: 0 операций. Первые 2000 символов:\n"
                            f"```\n{raw_txt[:2000]}\n```"
                        )
                    except Exception as e:
                        debug_info.append(f"⚠️ `{uf.name}`: 0 операций, не удалось получить текст: {e}")

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


# ==================== РЕНДЕР РЕЗУЛЬТАТОВ [FIX-RENDER-SCALAR-V5] ====================

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

    # [FIX-RENDER-SCALAR-V5] Строим df_raw с гарантированно скалярными колонками
    try:
        df_raw = pd.DataFrame(all_tx)
    except Exception as e:
        st.error(f"Ошибка при построении DataFrame: {e}")
        return

    if df_raw.empty:
        st.info("Нет данных.")
        return

    # Приводим ВСЕ object-колонки к строкам (кроме 'Сумма')
    for col in df_raw.columns:
        if col == 'Сумма':
            continue
        try:
            if df_raw[col].dtype == object:
                df_raw[col] = _safe_str_series(df_raw[col])
        except Exception:
            df_raw[col] = _safe_str_series(df_raw[col])

    # Сумма — к float
    try:
        df_raw['Сумма_число'] = df_raw['Сумма'].map(to_float_amount).astype(float)
    except Exception:
        df_raw['Сумма_число'] = 0.0

    # [FIX-RENAME-COLUMN-V4] Переименовываем в "Наименование банка"
    if 'Наименование счета' in df_raw.columns and 'Наименование банка' not in df_raw.columns:
        df_raw = df_raw.rename(columns={'Наименование счета': 'Наименование банка'})

    income = float(df_raw['Сумма_число'][df_raw['Сумма_число'] > 0].sum())
    expense = float(abs(df_raw['Сумма_число'][df_raw['Сумма_число'] < 0].sum()))

    # Безопасно строим series
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
    st.markdown("### 🤖 AI-ассистент (DeepSeek)")
    st.caption(
        "Задавайте вопросы по коду, данным и обработке выписок. "
        "Ассистент видит только то, что вы ему напишите."
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
                '<span class="ai-status-warn">⚠️ API-ключ DeepSeek не задан.</span>',
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
