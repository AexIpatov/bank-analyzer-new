import streamlit as st
import pandas as pd
import os
import re
import chardet
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Tuple, Optional
from docx import Document
import pdfplumber

# ==================== НАСТРОЙКА СТРАНИЦЫ ====================
st.set_page_config(
    page_title="Аналитик банковских выписок",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==================== CSS СТИЛИ ====================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --mint-light: #A8D5BA;
    --mint-dark: #5D9968;
    --sage: #7BAE7F;
    --cream: #FAF8F3;
    --ink: #1F2D23;
    --ink-soft: #4A5A4E;
    --ink-muted: #7A8A7E;
    --border: #D5E5D9;
}

.stApp {
    background: linear-gradient(180deg, #FAF8F3 0%, #F0F5EE 50%, #E8F2E4 100%);
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    color: var(--ink);
}
.main { background: transparent; }
footer {visibility: hidden;}
#MainMenu {visibility: hidden;}

.hero {
    background: linear-gradient(135deg, #5D9968 0%, #7BAE7F 50%, #A8D5BA 100%);
    padding: 3rem 2.5rem;
    border-radius: 28px;
    color: #FFFFFF;
    margin-bottom: 2rem;
    box-shadow: 0 20px 45px rgba(93, 153, 104, 0.28);
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    top: -100px;
    right: -100px;
    width: 400px;
    height: 400px;
    background: radial-gradient(circle, rgba(255,255,255,0.18) 0%, transparent 70%);
    border-radius: 50%;
    pointer-events: none;
}
.hero::after {
    content: '';
    position: absolute;
    bottom: -140px;
    left: -80px;
    width: 360px;
    height: 360px;
    background: radial-gradient(circle, rgba(255,255,255,0.12) 0%, transparent 70%);
    border-radius: 50%;
    pointer-events: none;
}
.hero-content {
    position: relative;
    z-index: 2;
    display: flex;
    align-items: center;
    gap: 2rem;
    flex-wrap: wrap;
}
.hero-text { flex: 1; min-width: 280px; }
.hero-text h1 {
    font-size: 2.5rem;
    font-weight: 800;
    margin: 0 0 0.6rem 0;
    letter-spacing: -1px;
    line-height: 1.15;
}
.hero-text p {
    font-size: 1.1rem;
    margin: 0;
    opacity: 0.95;
}
.hero-chips {
    display: flex;
    gap: 0.5rem;
    margin-top: 1.2rem;
    flex-wrap: wrap;
}
.chip {
    background: rgba(255,255,255,0.2);
    border: 1px solid rgba(255,255,255,0.3);
    padding: 0.35rem 0.85rem;
    border-radius: 999px;
    font-size: 0.85rem;
    font-weight: 500;
    backdrop-filter: blur(8px);
}
.hero-illustration { position: relative; z-index: 2; flex-shrink: 0; }

.stButton > button {
    background: linear-gradient(135deg, #5D9968 0%, #7BAE7F 100%);
    color: #FFFFFF;
    border: none;
    border-radius: 14px;
    padding: 0.75rem 1.6rem;
    font-weight: 600;
    font-size: 1rem;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 6px 16px rgba(93, 153, 104, 0.28);
}
.stButton > button:hover {
    background: linear-gradient(135deg, #4A8055 0%, #5D9968 100%);
    box-shadow: 0 10px 24px rgba(93, 153, 104, 0.45);
    transform: translateY(-2px);
    color: #FFFFFF;
}

.stDownloadButton > button {
    background: linear-gradient(135deg, #A8D5BA 0%, #7BAE7F 100%);
    color: #FFFFFF;
    border: none;
    border-radius: 14px;
    padding: 0.8rem 1.8rem;
    font-weight: 600;
    font-size: 1rem;
    transition: all 0.25s ease;
    box-shadow: 0 6px 16px rgba(123, 174, 127, 0.3);
}
.stDownloadButton > button:hover {
    background: linear-gradient(135deg, #7BAE7F 0%, #5D9968 100%);
    box-shadow: 0 10px 24px rgba(93, 153, 104, 0.45);
    transform: translateY(-2px);
    color: #FFFFFF;
}

.stFileUploader {
    background: #FFFFFF;
    border-radius: 20px;
    padding: 1.2rem;
    border: 2px dashed var(--border);
    transition: all 0.3s ease;
    box-shadow: 0 4px 20px rgba(46, 59, 50, 0.04);
}
.stFileUploader:hover {
    border-color: var(--mint-light);
    box-shadow: 0 8px 28px rgba(93, 153, 104, 0.12);
}
.stFileUploader section { border: none !important; background: transparent !important; }
.stFileUploader label { color: var(--ink) !important; font-weight: 500; }
.stFileUploader button {
    background: #E8F5E9 !important;
    color: var(--ink) !important;
    border: 1px solid var(--mint-light) !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
}
.stFileUploader button:hover {
    background: var(--mint-light) !important;
    color: #FFFFFF !important;
}

.stMetric {
    background: #FFFFFF;
    border-radius: 20px;
    padding: 1.5rem 1.6rem;
    border: 1px solid #E8F2E4;
    box-shadow: 0 6px 22px rgba(46, 59, 50, 0.06);
    transition: all 0.25s ease;
    position: relative;
    overflow: hidden;
}
.stMetric::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    height: 100%; width: 6px;
    background: linear-gradient(180deg, #5D9968 0%, #A8D5BA 100%);
}
.stMetric:hover {
    transform: translateY(-4px);
    box-shadow: 0 14px 32px rgba(93, 153, 104, 0.18);
}
.stMetric label {
    color: var(--ink-soft) !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}
.stMetric [data-testid="stMetricValue"] {
    color: var(--ink) !important;
    font-weight: 700 !important;
    font-size: 1.7rem !important;
}

.stDataFrame {
    border-radius: 20px;
    overflow: hidden;
    box-shadow: 0 8px 28px rgba(46, 59, 50, 0.08);
    background: #FFFFFF;
}

.stAlert {
    border-radius: 14px;
    border: none;
    padding: 0.9rem 1.3rem;
    box-shadow: 0 3px 12px rgba(46, 59, 50, 0.05);
}
div[data-baseweb="notification"][kind="positive"] { background: #E8F5E9; color: var(--ink); }
div[data-baseweb="notification"][kind="info"]     { background: #EEF4EA; color: var(--ink); }
div[data-baseweb="notification"][kind="warning"]  { background: #FBF3E0; color: #7A5B10; }

.stProgress > div > div > div {
    background: linear-gradient(90deg, #5D9968 0%, #A8D5BA 100%);
    border-radius: 8px;
}

h3 {
    color: var(--ink);
    font-weight: 700;
    padding-bottom: 0.6rem;
    border-bottom: 2px solid #E8F2E4;
    margin-top: 2rem;
    margin-bottom: 1.2rem;
    font-size: 1.25rem;
    letter-spacing: -0.3px;
}

::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: #FAF8F3; }
::-webkit-scrollbar-thumb { background: #C8DECC; border-radius: 5px; }
::-webkit-scrollbar-thumb:hover { background: #A8D5BA; }
hr { border: none; border-top: 1px solid #E8F2E4; margin: 2rem 0; }

.info-card {
    background: #FFFFFF;
    border-radius: 18px;
    padding: 1.4rem 1.5rem;
    border: 1px solid #E8F2E4;
    display: flex;
    align-items: center;
    gap: 1.2rem;
    transition: all 0.25s ease;
    box-shadow: 0 4px 16px rgba(46, 59, 50, 0.05);
}
.info-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 22px rgba(93, 153, 104, 0.12);
}
.info-card-icon {
    flex-shrink: 0;
    width: 56px; height: 56px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 14px;
    background: linear-gradient(135deg, #E8F5E9 0%, #D5EDDA 100%);
}
.info-card-text h4 { color: var(--ink); margin: 0 0 0.25rem 0; font-size: 1rem; font-weight: 600; }
.info-card-text p { color: var(--ink-muted); margin: 0; font-size: 0.88rem; line-height: 1.4; }

.footer-note {
    text-align: center;
    color: var(--ink-muted);
    font-size: 0.85rem;
    padding: 1.5rem 0 0.5rem 0;
    opacity: 0.8;
}
</style>
""", unsafe_allow_html=True)

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
      </div>
    </div>
    <div class="hero-illustration">
      <svg width="180" height="180" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="100" cy="100" r="90" fill="rgba(255,255,255,0.15)"/>
        <rect x="50" y="110" width="14" height="50" rx="4" fill="rgba(255,255,255,0.85)"/>
        <rect x="72" y="90" width="14" height="70" rx="4" fill="rgba(255,255,255,0.95)"/>
        <rect x="94" y="70" width="14" height="90" rx="4" fill="rgba(255,255,255,1)"/>
        <rect x="116" y="95" width="14" height="65" rx="4" fill="rgba(255,255,255,0.95)"/>
        <rect x="138" y="60" width="14" height="100" rx="4" fill="rgba(255,255,255,1)"/>
        <path d="M57 100 L79 80 L101 60 L123 85 L145 50" stroke="#FFFFFF" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>
        <circle cx="57" cy="100" r="5" fill="#FFFFFF"/>
        <circle cx="79" cy="80" r="5" fill="#FFFFFF"/>
        <circle cx="101" cy="60" r="5" fill="#FFFFFF"/>
        <circle cx="123" cy="85" r="5" fill="#FFFFFF"/>
        <circle cx="145" cy="50" r="5" fill="#FFFFFF"/>
        <circle cx="160" cy="40" r="16" fill="#FFD86B" stroke="#FFFFFF" stroke-width="2"/>
        <text x="160" y="46" text-anchor="middle" font-size="16" font-weight="700" fill="#5D9968">₽</text>
      </svg>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ==================== ОБЩИЕ УТИЛИТЫ ====================

def clean_account_name(filename: str) -> str:
    """Убирает расширение, даты, IBAN, суффиксы из имени файла."""
    name = os.path.splitext(filename)[0]
    # Даты с буквенным месяцем 01-Jul-2026
    name = re.sub(r'\d{2}-[A-Za-z]{3}-\d{4}', '', name)
    # ISO-даты
    name = re.sub(r'\d{4}-\d{2}-\d{2}', '', name)
    # Даты ДД.ММ.ГГГГ
    name = re.sub(r'\d{2}\.\d{2}\.\d{4}', '', name)
    # IBAN
    name = re.sub(r'LV\d{2}[A-Z]{4}\d{13,}', '', name)
    # Заменяем _ и - на пробелы
    name = re.sub(r'[_\-]', ' ', name)
    # Убираем лишние точки и сжимаем пробелы
    name = re.sub(r'\.+', ' ', name)
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r' \(2\)$', '', name)
    return name.strip() if name else 'Неизвестный счет'

def parse_date(date_str: str) -> str:
    if date_str is None or pd.isna(date_str):
        return ''
    date_str = str(date_str).strip()
    if not date_str or date_str in ['nan', '-', 'None', 'null', 'NaT']:
        return ''
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    if date_str.endswith('.0'):
        date_str = date_str[:-2]
    # 8-значный (20260831)
    if date_str.isdigit() and len(date_str) == 8:
        return f"{date_str[6:8]}-{date_str[4:6]}-{date_str[:4]}"
    # ДД.ММ.ГГГГ
    m = re.match(r'^(\d{1,2})\.(\d{1,2})\.(\d{2,4})$', date_str)
    if m:
        d, mo, y = m.groups()
        if len(y) == 2:
            y = f"20{y}"
        return f"{d.zfill(2)}-{mo.zfill(2)}-{y}"
    # ДД/ММ/ГГГГ
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', date_str)
    if m:
        d, mo, y = m.groups()
        if len(y) == 2:
            y = f"20{y}"
        return f"{d.zfill(2)}-{mo.zfill(2)}-{y}"
    # ГГГГ-ММ-ДД
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', date_str)
    if m:
        y, mo, d = m.groups()
        return f"{d}-{mo}-{y}"
    # 20260831 12:00
    m = re.match(r'^(\d{4})(\d{2})(\d{2})', date_str)
    if m:
        y, mo, d = m.groups()
        return f"{d}-{mo}-{y}"
    # Стандартные форматы
    for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d", "%d-%m-%Y",
                "%Y%m%d", "%d.%m.%y", "%d/%m/%y", "%d-%b-%Y", "%d-%b-%y"]:
        try:
            return datetime.strptime(date_str, fmt).strftime("%d-%m-%Y")
        except Exception:
            continue
    return date_str

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
    # Убираем валюту
    s = re.sub(r'\s*[₽$€£]\s*$', '', s)
    s = re.sub(r'\s*[A-Z]{3}\s*$', '', s)
    s = s.replace(' ', '').replace('\xa0', '').replace('\u202f', '')
    # Десятичные разделители
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
    if amount is None or pd.isna(amount):
        return "0,00"
    sign = "-" if amount < 0 else ""
    formatted = f"{abs(amount):.2f}".replace('.', ',')
    if ',' in formatted:
        ip, dp = formatted.split(',')
        ip = re.sub(r'(?<=\d)(?=(\d{3})+(?!\d))', ' ', ip)
        return f"{sign}{ip},{dp}"
    return f"{sign}{formatted}"

def safe_str(v) -> str:
    if v is None or pd.isna(v):
        return ''
    return str(v).strip()

# ==================== ОБЩИЕ ВСПОМОГАТЕЛЬНЫЕ ПАРСЕРЫ ====================

def read_xlsx(file_content: bytes, sheet_name=None):
    for engine in ['openpyxl', 'xlrd', None]:
        try:
            kw = {'header': None}
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

def parse_csob_generic(file_content: bytes, account_name: str, flip_sign: bool = False) -> List[Dict]:
    """
    Общий парсер для CSOB-выписок с заголовком:
    account number;account currency;...;payment amount;...
    Работает для DŽIBIK, JENISOV, RR_Strojka, RR_Rev_OSTR, Koruna_Strojka.
    """
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except Exception:
        try:
            content = file_content.decode('cp1250')
        except Exception:
            content = file_content.decode('latin-1')
    if content.startswith('\ufeff'):
        content = content[1:]
    lines = content.split('\n')
    lines = [line.rstrip('\r').strip() for line in lines if line.strip()]
    if len(lines) < 2:
        return []
    # Ищем заголовок с account number + posting date
    header_idx = -1
    for i, line in enumerate(lines):
        low = line.lower()
        if 'account number' in low and 'posting date' in low:
            header_idx = i
            break
    if header_idx == -1:
        return []
    for line_idx in range(header_idx + 1, len(lines)):
        line = lines[line_idx]
        if not line:
            continue
        parts = [p.strip() for p in line.split(';')]
        while parts and parts[-1] == '':
            parts.pop()
        if len(parts) < 7:
            continue
        try:
            date_str = safe_str(parts[4])
            date = parse_date(date_str)
            if not date:
                continue
            amount_str = safe_str(parts[6])
            if not amount_str:
                continue
            # Пропускаем номера счетов
            if re.match(r'^\d{7,}$', amount_str):
                continue
            if re.match(r'^\d+\/\d+$', amount_str):
                continue
            # Признак суммы
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
            if amount == 0.0:
                continue
            if flip_sign:
                amount = -amount
            # Контрагент: индекс 13, при отсутствии — индекс 3
            counterparty = ''
            if len(parts) > 13:
                counterparty = safe_str(parts[13])
            if not counterparty and len(parts) > 3:
                counterparty = safe_str(parts[3])
            # Описание: индекс 16 → 15 → 28 → другие
            description = ''
            for idx in [16, 15, 28, 12, 11, 10, 2]:
                if idx < len(parts) and safe_str(parts[idx]) and safe_str(parts[idx]) != 'nan':
                    val = safe_str(parts[idx])
                    if not re.match(r'^[\d.,\-]+$', val):
                        description = val
                        break
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty[:200],
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception:
            continue
    return transactions

# ==================== ПАРСЕРЫ ПО КАЖДОМУ СЧЁТУ ====================

# ---------- 1. Regina Alfa-bank_NOMIQA_RUB ----------
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
    current_date = None
    current_desc = ''
    current_amount = None
    for idx in range(data_start, len(df)):
        row = df.iloc[idx]
        row_values = [x for x in row.values if pd.notna(x)]
        if not row_values:
            continue
        has_date = False
        date_val = None
        amount_val = None
        if len(row) > 0:
            val = row.iloc[0]
            if pd.notna(val):
                val_str = str(val).strip()
                if re.match(r'^\d{4}-\d{2}-\d{2}', val_str) or re.match(r'^\d{2}\.\d{2}\.\d{4}', val_str):
                    has_date = True
                    date_val = val_str
        for col_idx in range(len(row) - 1, max(0, len(row) - 3), -1):
            if col_idx < len(row):
                val = row.iloc[col_idx]
                if pd.notna(val) and val != '':
                    val_str = str(val).strip()
                    if val_str and val_str != 'nan':
                        val_clean = re.sub(r'\s*RUR\s*$', '', val_str)
                        if re.search(r'[\d,.]', val_clean):
                            amount_val = val_str
                            break
        if has_date:
            if current_date is not None and current_amount is not None:
                transactions.append({
                    'Дата': parse_date(str(current_date)),
                    'Сумма': parse_amount(str(current_amount)),
                    'Контрагент': '',
                    'Наименование счета': account_name,
                    'Описание': current_desc[:500]
                })
            current_date = date_val
            current_desc = ''
            current_amount = amount_val
            desc_parts = []
            for col_idx in range(1, len(row)):
                val = row.iloc[col_idx]
                if pd.notna(val) and val != '':
                    val_str = str(val).strip()
                    if val_str and val_str != 'nan' and val_str != current_date and val_str != current_amount:
                        if not re.search(r'[\d,.]\s*RUR', val_str):
                            desc_parts.append(val_str)
            if desc_parts:
                current_desc = ' '.join(desc_parts)
        else:
            if current_date is not None:
                desc_parts = []
                for val in row.values:
                    if pd.notna(val) and val != '':
                        val_str = str(val).strip()
                        if val_str and val_str != 'nan':
                            desc_parts.append(val_str)
                if desc_parts:
                    current_desc += ' ' + ' '.join(desc_parts)
            if amount_val is not None and current_amount is None:
                current_amount = amount_val
    if current_date is not None and current_amount is not None:
        transactions.append({
            'Дата': parse_date(str(current_date)),
            'Сумма': parse_amount(str(current_amount)),
            'Контрагент': '',
            'Наименование счета': account_name,
            'Описание': current_desc[:500]
        })
    return transactions

def parse_regina_alfa_docx(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []
    all_text = []
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                t = cell.text.strip()
                if t:
                    all_text.append(t)
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            all_text.append(t)
    full_text = '\n'.join(all_text).replace('\ufeff', '').replace('\xa0', ' ')
    pattern = re.compile(
        r'(\d{2}\.\d{2}\.\d{4})\s*'
        r'([A-Z0-9_]+)\s*'
        r'(.+?)'
        r'(-?[\d\s]+,\d{2})\s*RUR',
        re.DOTALL
    )
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(1).strip())
            code = m.group(2).strip()
            desc = re.sub(r'\s+', ' ', m.group(3)).strip()
            amount = parse_amount(m.group(4))
            if not date or amount == 0.0:
                continue
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': '',
                'Наименование счета': account_name,
                'Описание': f"{code} {desc}"[:500]
            })
        except Exception:
            continue
    return transactions

def parse_regina_alfa_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    parts = []
    try:
        with pdfplumber.open(BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
    except Exception:
        return []
    full_text = '\n'.join(parts).replace('\ufeff', '').replace('\xa0', ' ')
    pattern = re.compile(
        r'(\d{2}\.\d{2}\.\d{4})\s*'
        r'([A-Z0-9_]+)\s*'
        r'(.+?)'
        r'(-?[\d\s]+,\d{2})\s*RUR',
        re.DOTALL
    )
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(1).strip())
            code = m.group(2).strip()
            desc = re.sub(r'\s+', ' ', m.group(3)).strip()
            amount = parse_amount(m.group(4))
            if not date or amount == 0.0:
                continue
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': '',
                'Наименование счета': account_name,
                'Описание': f"{code} {desc}"[:500]
            })
        except Exception:
            continue
    return transactions

# ---------- 2. Tinkoff RUB ----------
def parse_tinkoff_docx(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []
    target = None
    for table in doc.tables:
        if not table.rows:
            continue
        first = ' '.join(cell.text.strip() for cell in table.rows[0].cells)
        if 'Дата и время операции' in first and 'Сумма' in first:
            target = table
            break
    if target is None:
        return []
    header_cells = [cell.text.strip() for cell in target.rows[0].cells]
    date_idx = amount_idx = desc_idx = -1
    for i, h in enumerate(header_cells):
        if 'Дата и время операции' in h:
            date_idx = i
        elif 'Сумма в валюте операции' in h:
            amount_idx = i
        elif 'Описание операции' in h:
            desc_idx = i
    if date_idx == -1: date_idx = 0
    if amount_idx == -1: amount_idx = 2
    if desc_idx == -1: desc_idx = 4
    for row in target.rows[1:]:
        cells = [c.text.strip() for c in row.cells]
        if len(cells) < 3:
            continue
        try:
            date_raw = cells[date_idx] if date_idx < len(cells) else ''
            m = re.match(r'(\d{2}\.\d{2}\.\d{4})', date_raw)
            if not m:
                continue
            date = parse_date(m.group(1))
            if not date:
                continue
            amount = parse_amount(cells[amount_idx] if amount_idx < len(cells) else '')
            if amount == 0.0:
                continue
            desc = re.sub(r'\s+', ' ', cells[desc_idx] if desc_idx < len(cells) else '').strip()
            # Контрагент
            if 'Внутренний перевод' in desc: c = 'Внутренний перевод'
            elif 'Внешний перевод' in desc:  c = 'Внешний перевод'
            elif 'Перевод себе' in desc:      c = 'Перевод себе'
            elif 'Плата за' in desc:          c = 'Т-Банк'
            elif 'Перевод' in desc:           c = 'Перевод'
            else:                             c = desc[:60]
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': c,
                'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return transactions

# ---------- 3. BSR_Estate_EUR_BluOr_2 ----------
def parse_bsr_bluor_2(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Формат CSV BluOr Bank:
    "Счет","Дата","Ref","Комиссия банка ...","35.00","EUR","D"
    Служебные строки: Начальный/Конечный остаток, Дебет (D), Кредит (C), Starting/Total — пропускаем.
    """
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except Exception:
        try:
            content = file_content.decode('cp1250')
        except Exception:
            content = file_content.decode('latin-1')
    if content.startswith('\ufeff'):
        content = content[1:]
    lines = content.split('\n')
    lines = [l.strip() for l in lines if l.strip()]
    skip_words = ['начальный остаток', 'конечный остаток', 'starting balance',
                  'ending balance', 'total', 'дебет (d)', 'кредит (c)',
                  'debit (d)', 'credit (c)']
    for line in lines:
        # Парсим CSV с кавычками
        parts = []
        cur = ''
        inq = False
        for ch in line:
            if ch == '"':
                inq = not inq
            elif ch == ',' and not inq:
                parts.append(cur.strip())
                cur = ''
            else:
                cur += ch
        parts.append(cur.strip())
        parts = [p.strip('"') for p in parts]
        if len(parts) < 5:
            continue
        try:
            date = parse_date(parts[1])
            if not date:
                continue
            amount_str = parts[4]
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            description = parts[3] if len(parts) > 3 else ''
            low = description.lower()
            if any(w in low for w in skip_words):
                continue
            # Тип: D → расход, C → доход
            trans_type = parts[6] if len(parts) > 6 else ''
            if trans_type == 'D':
                amount = -abs(amount)
            elif trans_type == 'C':
                amount = abs(amount)
            counterparty = ''
            if 'BluOr' in description or 'Bank' in description:
                counterparty = 'BluOr Bank'
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty[:200],
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception:
            continue
    return transactions

# ---------- 4. BSR_Estate_EUR_BluOr_3 ----------
def parse_bsr_bluor_3(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Файл содержит только служебные строки (Начальный/Конечный остаток, Дебет/Кредит).
    Все транзакции отсутствуют. Возвращаем пустой список — это правильно.
    """
    return parse_bsr_bluor_2(file_content, account_name)

# ---------- 5. KL59_Rev_NB_EUR_BluOR ----------
def parse_kl59_rev_nb_bluor(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Формат: "Account No. (LV60...)", "03.08.2026", "Ref", "Banking charges...", "45.00","EUR","D"
    """
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except Exception:
        try:
            content = file_content.decode('cp1250')
        except Exception:
            content = file_content.decode('latin-1')
    if content.startswith('\ufeff'):
        content = content[1:]
    lines = content.split('\n')
    lines = [l.strip() for l in lines if l.strip()]
    skip_words = ['starting balance', 'ending balance', 'total',
                  'debit (d)', 'credit (c)', 'начальный остаток',
                  'конечный остаток', 'дебет (d)', 'кредит (c)']
    for line in lines:
        parts = []
        cur = ''
        inq = False
        for ch in line:
            if ch == '"':
                inq = not inq
            elif ch == ',' and not inq:
                parts.append(cur.strip())
                cur = ''
            else:
                cur += ch
        parts.append(cur.strip())
        parts = [p.strip('"') for p in parts]
        if len(parts) < 5:
            continue
        try:
            date = parse_date(parts[1])
            if not date:
                continue
            amount = parse_amount(parts[4])
            if amount == 0.0:
                continue
            desc = parts[3] if len(parts) > 3 else ''
            low = desc.lower()
            if any(w in low for w in skip_words):
                continue
            trans_type = parts[6] if len(parts) > 6 else ''
            if trans_type == 'D':
                amount = -abs(amount)
            elif trans_type == 'C':
                amount = abs(amount)
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': 'BluOr Bank' if 'BluOr' in desc or 'Bank' in desc else '',
                'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return transactions

# ---------- 6. JenHor_Unelma_CZK_CSAS ----------
def parse_jenhor_unelma(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except Exception:
        try:
            content = file_content.decode('cp1250')
        except Exception:
            content = file_content.decode('latin-1')
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
            if amount == 0.0:
                continue
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': parts[2][:200] if len(parts) > 2 else '',
                'Наименование счета': account_name,
                'Описание': ' '.join(parts[3:])[:500] if len(parts) > 3 else ''
            })
        except Exception:
            continue
    return transactions

# ---------- 7. DŽIBIK Main CSOB CZK ----------
def parse_dzibik_main_csob(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_generic(file_content, account_name)

# ---------- 8. JENISOV - HORSKA_CSOB_ CZK ----------
def parse_jenisov_horska_csob_czk(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_generic(file_content, account_name)

# ---------- 9. JENISOV - HORSKA S.R EUR ----------
def parse_jenisov_horska_csob_eur(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_generic(file_content, account_name)

# ---------- 10. RR_Strojka_CZK_CSOB ----------
def parse_rr_strojka_czk_csob(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_generic(file_content, account_name)

# ---------- 11. RR_Strojka_EUR_CSOB ----------
def parse_rr_strojka_eur_csob(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_generic(file_content, account_name)

# ---------- 12. Koruna_Strojka_CZK_CSOB ----------
def parse_koruna_strojka_czk_csob(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_generic(file_content, account_name)

# ---------- 13. Koruna_Strojka_EUR_CSOB ----------
def parse_koruna_strojka_eur_csob(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_generic(file_content, account_name)

# ---------- 14. Stalkin_ML2_CZK_FIO ----------
def parse_stalkin_ml2_fio(file_content: bytes, account_name: str) -> List[Dict]:
    """
    CSV с разделителем ';', все поля в кавычках.
    Заголовок: "Date";"Volume";"Currency";"To account";"Bank Code";"Message for beneficiary";"Note";"Type"
    """
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except Exception:
        try:
            content = file_content.decode('cp1250')
        except Exception:
            content = file_content.decode('latin-1')
    if content.startswith('\ufeff'):
        content = content[1:]
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if len(lines) < 2:
        return []
    # Ищем заголовок
    header_idx = -1
    for i, l in enumerate(lines):
        low = l.lower()
        if '"date"' in low and '"volume"' in low:
            header_idx = i
            break
    if header_idx == -1:
        # Пробуем без кавычек
        for i, l in enumerate(lines):
            low = l.lower()
            if 'date' in low and 'volume' in low:
                header_idx = i
                break
    if header_idx == -1:
        return []
    for line in lines[header_idx + 1:]:
        parts = []
        cur = ''
        inq = False
        for ch in line:
            if ch == '"':
                inq = not inq
            elif ch == ';' and not inq:
                parts.append(cur.strip())
                cur = ''
            else:
                cur += ch
        parts.append(cur.strip())
        parts = [p.strip('"') for p in parts]
        if len(parts) < 3:
            continue
        try:
            date = parse_date(parts[0])
            if not date:
                continue
            amount = parse_amount(parts[1])
            if amount == 0.0:
                continue
            # Описание — 6-е поле (Message for beneficiary), если есть; иначе Note
            desc = ''
            if len(parts) > 5 and parts[5]:
                desc = parts[5]
            elif len(parts) > 6 and parts[6]:
                desc = parts[6]
            # Контрагент: 'To account' + 'Bank Code'
            counterparty = ''
            if len(parts) > 3 and parts[3]:
                counterparty = parts[3]
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty[:200],
                'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return transactions

# ---------- 15. AN14_Estate_EUR_Industra ----------
def parse_industra_an14(file_content: bytes, account_name: str) -> List[Dict]:
    return _parse_industra_generic(file_content, account_name)

# ---------- 16. Plavas1_Estate_EUR_Industra ----------
def parse_industra_plavas1(file_content: bytes, account_name: str) -> List[Dict]:
    return _parse_industra_generic(file_content, account_name)

# ---------- 17. KL59_Rev_NB_EUR_Industra ----------
def parse_industra_kl59(file_content: bytes, account_name: str) -> List[Dict]:
    return _parse_industra_generic(file_content, account_name)

def _parse_industra_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Industra Bank XLS/XLSX: заголовки "Дата транзакции","Дебет(D)","Кредит(C)".
    """
    transactions = []
    df = read_xlsx(file_content)
    if df is None or df.empty:
        return []
    header_row = -1
    for idx, row in df.iterrows():
        if idx < 60:
            row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Дата транзакции' in row_str and 'Дебет' in row_str and 'Кредит' in row_str:
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
        if 'Дата транзакции' in s: ci['date'] = i
        elif 'Получатель' in s or 'Плательщик' in s: ci['counterparty'] = i
        elif 'Информация о транзакции' in s: ci['description'] = i
        elif 'Дебет' in s and 'Кредит' not in s: ci['debit'] = i
        elif 'Кредит' in s and 'Дебет' not in s: ci['credit'] = i
    if 'date' not in ci: ci['date'] = 0
    if 'debit' not in ci: ci['debit'] = 11
    if 'credit' not in ci: ci['credit'] = 12
    for idx in range(header_row + 1, len(df)):
        row = df.iloc[idx]
        row_vals = [x for x in row.values if pd.notna(x)]
        if not row_vals:
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
                    ds = str(dv).strip().replace(',', '.').replace(' ', '')
                    p = parse_amount(ds)
                    if p != 0.0:
                        amount = -abs(p)
                        found = True
            if not found and 'credit' in ci and ci['credit'] < len(row):
                cv = row.iloc[ci['credit']]
                if pd.notna(cv) and str(cv).strip() not in ['', 'nan', '-']:
                    cs = str(cv).strip().replace(',', '.').replace(' ', '')
                    p = parse_amount(cs)
                    if p != 0.0:
                        amount = p
                        found = True
            if not found:
                continue
            cp = ''
            if 'counterparty' in ci and ci['counterparty'] < len(row):
                cp = safe_str(row.iloc[ci['counterparty']])
            desc = ''
            if 'description' in ci and ci['description'] < len(row):
                desc = safe_str(row.iloc[ci['description']])
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': cp[:200],
                'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return transactions

# ---------- 18. Kapital bank_Saida_AZN ----------
def parse_kapital_saida_azn(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except Exception:
        try:
            content = file_content.decode('cp1250')
        except Exception:
            content = file_content.decode('latin-1')
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
            if amount == 0.0:
                continue
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': '',
                'Наименование счета': account_name,
                'Описание': parts[1][:500] if len(parts) > 1 else ''
            })
        except Exception:
            continue
    return transactions

# ---------- 19. Kapital bank_Saida_AZN (бизнес-счет) ----------
def parse_kapital_saida_business(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_kapital_saida_azn(file_content, account_name)

# ---------- 20. MASHREQ BANK-AED-NOMIQA ----------
def parse_mashreq(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
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
            row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Date' in row_str and 'Description' in row_str and 'Credit' in row_str:
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
        if s == 'Date': ci['date'] = i
        elif 'Value Date' in s: ci['value_date'] = i
        elif 'Description' in s: ci['description'] = i
        elif s == 'Credit': ci['credit'] = i
        elif s == 'Debit': ci['debit'] = i
        elif 'Balance' in s: ci['balance'] = i
    if 'date' not in ci: ci['date'] = 0
    if 'credit' not in ci: ci['credit'] = 4
    if 'debit' not in ci: ci['debit'] = 5
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
                    cs = str(cv).strip().replace(',', '').replace(' ', '')
                    p = parse_amount(cs)
                    if p != 0.0:
                        amount = p
                        found = True
            if not found and 'debit' in ci and ci['debit'] < len(row):
                dv = row.iloc[ci['debit']]
                if pd.notna(dv) and str(dv).strip() not in ['', 'nan', '-']:
                    ds = str(dv).strip().replace(',', '').replace(' ', '')
                    p = parse_amount(ds)
                    if p != 0.0:
                        amount = -abs(p)
                        found = True
            if not found:
                continue
            desc = ''
            cp = ''
            if 'description' in ci and ci['description'] < len(row):
                desc = safe_str(row.iloc[ci['description']])
                # Контрагент
                parts = desc.split('/')
                for p in parts:
                    p_clean = p.strip()
                    if p_clean and len(p_clean) > 2 and 'REF' not in p_clean and 'SRN' not in p_clean and 'REC' not in p_clean:
                        if not re.match(r'^[A-Z0-9]{10,}$', p_clean):
                            cp = p_clean[:200]
                            break
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': cp,
                'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return transactions

# ---------- 21. Budapest EUR-MKB (CSV) ----------
def parse_budapest_eur_mkb(file_content: bytes, account_name: str) -> List[Dict]:
    return _parse_mkb_csv_generic(file_content, account_name)

# ---------- 22. Budapest HUF-MKB (XLS) ----------
def parse_budapest_huf_mkb(file_content: bytes, account_name: str) -> List[Dict]:
    return _parse_mkb_xls_generic(file_content, account_name)

def _parse_mkb_csv_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """
    CSV-выписка MKB. Разделитель ;, значения через точку.
    Шапка: Sorszám;Értéknap;Tranzakció típusa;...;Összeg;Devizanem;Közlemény;...
    """
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except Exception:
        try:
            content = file_content.decode('cp1250')
        except Exception:
            content = file_content.decode('latin-1')
    if content.startswith('\ufeff'):
        content = content[1:]
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if len(lines) < 3:
        return []
    # Ищем строку заголовка
    header_idx = -1
    for i, l in enumerate(lines):
        low = l.lower()
        if 'sorszám' in low and 'értéknap' in low:
            header_idx = i
            break
        if 'sorsz' in low and 'rt' in low and 'knap' in low:
            header_idx = i
            break
    if header_idx == -1:
        return []
    hdr_parts = [p.strip() for p in lines[header_idx].split(';')]
    date_idx = amount_idx = desc_idx = counterparty_idx = -1
    for i, h in enumerate(hdr_parts):
        hl = h.lower()
        if 'értéknap' in hl or 'rt' in hl and 'knap' in hl:
            date_idx = i
        elif 'összeg' in hl or 'sszeg' in hl:
            amount_idx = i
        elif 'közlemény' in hl or 'kzlem' in hl:
            desc_idx = i
        elif 'kedvezményezett' in hl or 'kedvezm' in hl and 'neve' in hl:
            if counterparty_idx == -1:
                counterparty_idx = i
    if date_idx == -1: date_idx = 1
    if amount_idx == -1: amount_idx = 9
    if desc_idx == -1: desc_idx = 11
    for line in lines[header_idx + 1:]:
        parts = [p.strip() for p in line.split(';')]
        if len(parts) < 10:
            continue
        try:
            date = parse_date(parts[date_idx] if date_idx < len(parts) else '')
            if not date:
                continue
            amount = parse_amount(parts[amount_idx] if amount_idx < len(parts) else '')
            if amount == 0.0:
                continue
            desc = parts[desc_idx] if desc_idx < len(parts) else ''
            cp = parts[counterparty_idx] if counterparty_idx >= 0 and counterparty_idx < len(parts) else ''
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': cp[:200],
                'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return transactions

def _parse_mkb_xls_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """
    XLS-выписка MKB. В шапке несколько строк описания, потом строка заголовков:
    Sorszám | Értéknap | Tranzakció típusa | ... | Összeg | Devizanem | Közlemény | ...
    """
    transactions = []
    df = read_xlsx(file_content)
    if df is None or df.empty:
        return []
    header_row = -1
    for idx, row in df.iterrows():
        if idx < 20:
            row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Sorszám' in row_str and 'Értéknap' in row_str:
                header_row = idx
                break
            if 'rt' in row_str and 'knap' in row_str and 'sszeg' in row_str:
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
        sl = s.lower()
        if 'értéknap' in sl or ('rt' in sl and 'knap' in sl):
            ci['date'] = i
        elif 'összeg' in sl or 'sszeg' in sl:
            ci['amount'] = i
        elif 'közlemény' in sl or 'kzlem' in sl:
            ci['description'] = i
        elif 'kedvezményezett' in sl and 'neve' in sl:
            if 'counterparty' not in ci:
                ci['counterparty'] = i
    if 'date' not in ci: ci['date'] = 1
    if 'amount' not in ci: ci['amount'] = 9
    if 'description' not in ci: ci['description'] = 11
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
            amount = parse_amount(row.iloc[ci['amount']] if ci['amount'] < len(row) else '')
            if amount == 0.0:
                continue
            desc = safe_str(row.iloc[ci['description']]) if 'description' in ci and ci['description'] < len(row) else ''
            cp = safe_str(row.iloc[ci['counterparty']]) if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': cp[:200],
                'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return transactions

# ---------- 23. Saida_N26 ----------
def parse_saida_n26(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except Exception:
        try:
            content = file_content.decode('cp1250')
        except Exception:
            content = file_content.decode('latin-1')
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
            if amount == 0.0:
                continue
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': '',
                'Наименование счета': account_name,
                'Описание': ' '.join(parts[2:])[:500]
            })
        except Exception:
            continue
    return transactions

# ---------- 24. BUNDA LLC-Pasha Bank - AED-дирхам ----------
def parse_bunda_pasha_aed(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except Exception:
        try:
            content = file_content.decode('cp1250')
        except Exception:
            content = file_content.decode('latin-1')
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
            if amount == 0.0:
                continue
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': '',
                'Наименование счета': account_name,
                'Описание': parts[1][:500] if len(parts) > 1 else ''
            })
        except Exception:
            continue
    return transactions

# ---------- 25. BUNDA LLC-Pasha Bank-AZN ----------
def parse_bunda_pasha_azn(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    df = read_xlsx(file_content, sheet_name='Statement')
    if df is None or df.empty:
        df = read_xlsx(file_content)
    if df is None or df.empty:
        return []
    header_row = -1
    for idx, row in df.iterrows():
        if idx < 30:
            s = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Əməliyyat tarixi' in s or 'Əməliyyat' in s:
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
        if 'Əməliyyat tarixi' in s or 'Tarix' in s: ci['date'] = i
        elif 'İcra tarixi' in s: ci['exec_date'] = i
        elif 'Ödəyən' in s or 'Benefisiar' in s: ci['payee'] = i
        elif 'Təyinat' in s: ci['purpose'] = i
        elif 'Mədaxil' in s: ci['income'] = i
        elif 'Məxaric' in s: ci['expense'] = i
        elif 'Balans' in s: ci['balance'] = i
    if 'date' not in ci: ci['date'] = 0
    if 'income' not in ci: ci['income'] = 6
    if 'expense' not in ci: ci['expense'] = 7
    for idx in range(header_row + 1, len(df)):
        row = df.iloc[idx]
        rv = [x for x in row.values if pd.notna(x)]
        if not rv:
            continue
        rstr = ' '.join([str(x) for x in row.values if pd.notna(x)])
        if 'DÖVRÜN SONUNA BALANS' in rstr or 'MÖVCUD BALANS' in rstr:
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
            if 'income' in ci and ci['income'] < len(row):
                v = row.iloc[ci['income']]
                if pd.notna(v) and str(v).strip() not in ['', 'nan']:
                    p = parse_amount(str(v).replace(',', '.').replace(' ', ''))
                    if p != 0.0:
                        amount = p
                        found = True
            if not found and 'expense' in ci and ci['expense'] < len(row):
                v = row.iloc[ci['expense']]
                if pd.notna(v) and str(v).strip() not in ['', 'nan']:
                    p = parse_amount(str(v).replace(',', '.').replace(' ', ''))
                    if p != 0.0:
                        amount = -abs(p)
                        found = True
            if not found:
                continue
            cp = safe_str(row.iloc[ci['payee']]) if 'payee' in ci and ci['payee'] < len(row) else ''
            desc = safe_str(row.iloc[ci['purpose']]) if 'purpose' in ci and ci['purpose'] < len(row) else ''
            if not desc:
                desc = cp
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': cp[:200],
                'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return transactions

# ---------- 26. Paysera Baltic Solutions EUR ----------
def parse_paysera_generic(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    df = read_xlsx(file_content, sheet_name='Worksheet')
    if df is None or df.empty:
        df = read_xlsx(file_content)
    if df is None or df.empty:
        return []
    header_row = -1
    for idx, row in df.iterrows():
        if idx < 30:
            s = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Тип' in s and 'Дата и время' in s and 'Сумма и валюта' in s:
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
        if 'Дата и время' in s: ci['date'] = i
        elif 'Получатель' in s or 'Плательщик' in s: ci['counterparty'] = i
        elif 'Назначение платежа' in s: ci['purpose'] = i
        elif 'Сумма и валюта' in s: ci['amount'] = i
        elif 'Кредит / Дебет' in s: ci['type'] = i
    if 'date' not in ci: ci['date'] = 3
    if 'amount' not in ci: ci['amount'] = 7
    if 'counterparty' not in ci: ci['counterparty'] = 4
    if 'purpose' not in ci: ci['purpose'] = 9
    if 'type' not in ci: ci['type'] = 11
    for idx in range(header_row + 1, len(df)):
        row = df.iloc[idx]
        rv = [x for x in row.values if pd.notna(x)]
        if not rv:
            continue
        rstr = ' '.join([str(x) for x in row.values if pd.notna(x)])
        if 'Остаток' in rstr or 'Дебетовый оборот' in rstr or 'Кредитовый оборот' in rstr:
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
            if amount == 0.0:
                continue
            ttype = safe_str(row.iloc[ci['type']]) if 'type' in ci and ci['type'] < len(row) else ''
            if ttype in ('Д', 'D'):
                amount = -abs(amount)
            elif ttype in ('К', 'C'):
                amount = abs(amount)
            cp = safe_str(row.iloc[ci['counterparty']]) if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
            desc = safe_str(row.iloc[ci['purpose']]) if 'purpose' in ci and ci['purpose'] < len(row) else ''
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': cp[:200],
                'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return transactions

def parse_paysera_baltic(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_generic(file_content, account_name)

# ---------- 27. Paysera Sveciy Namai Lithuania EUR ----------
def parse_paysera_sveciy(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_generic(file_content, account_name)

# ---------- 28. Paysera-BS PROPERTY, SIA ----------
def parse_paysera_property(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_generic(file_content, account_name)

# ---------- 29. Paysera-BS RERUM, SIA ----------
def parse_paysera_rerum(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_generic(file_content, account_name)

# ---------- 30. RAK BANK Nomiqa клиенты ----------
def parse_rak_bank(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except Exception:
        try:
            content = file_content.decode('cp1250')
        except Exception:
            content = file_content.decode('latin-1')
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
            if amount == 0.0:
                continue
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': '',
                'Наименование счета': account_name,
                'Описание': parts[1][:500] if len(parts) > 1 else ''
            })
        except Exception:
            continue
    return transactions

# ---------- 31. AN14_Estate_EUR_Revolut ----------
def parse_revolut_generic(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except Exception:
        try:
            content = file_content.decode('cp1250')
        except Exception:
            content = file_content.decode('latin-1')
    if content.startswith('\ufeff'):
        content = content[1:]
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if len(lines) < 3:
        return []
    header = -1
    for i, l in enumerate(lines):
        if 'Date started' in l and 'Description' in l:
            header = i
            break
    if header == -1:
        return []
    hdr_parts = [p.strip().strip('"') for p in lines[header].split(',')]
    ci = {}
    for i, h in enumerate(hdr_parts):
        if 'Date started' in h: ci['date'] = i
        elif h == 'Amount': ci['amount'] = i
        elif 'Description' in h: ci['description'] = i
        elif 'Payer' in h: ci['counterparty'] = i
        elif h == 'State': ci['state'] = i
        elif h == 'Type': ci['type'] = i
    if 'date' not in ci: ci['date'] = 0
    if 'amount' not in ci: ci['amount'] = 14
    if 'description' not in ci: ci['description'] = 5
    if 'type' not in ci: ci['type'] = 3
    for line in lines[header + 1:]:
        parts = []
        cur = ''
        inq = False
        for ch in line:
            if ch == '"':
                inq = not inq
            elif ch == ',' and not inq:
                parts.append(cur.strip())
                cur = ''
            else:
                cur += ch
        parts.append(cur.strip())
        parts = [p.strip('"') for p in parts]
        if len(parts) < 3:
            continue
        try:
            if 'state' in ci and ci['state'] < len(parts):
                st = parts[ci['state']].strip()
                if st and st != 'COMPLETED':
                    continue
            dstr = parts[ci['date']] if ci['date'] < len(parts) else ''
            date = parse_date(dstr)
            if not date:
                continue
            astr = parts[ci['amount']] if ci['amount'] < len(parts) else ''
            amount = parse_amount(astr)
            if amount == 0.0:
                continue
            ttype = parts[ci['type']] if 'type' in ci and ci['type'] < len(parts) else ''
            if ttype == 'TOPUP':
                amount = abs(amount)
            elif ttype == 'FEE':
                amount = -abs(amount)
            cp = parts[ci['counterparty']] if 'counterparty' in ci and ci['counterparty'] < len(parts) else ''
            if not cp or cp == 'nan':
                cp = ''
            desc = parts[ci['description']] if ci['description'] < len(parts) else ''
            if not cp:
                m = re.search(r'(?:To|from)\s+([^,]+)', desc)
                if m:
                    cp = m.group(1).strip()
                else:
                    cp = desc[:200]
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': cp[:200],
                'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return transactions

def parse_revolut_an14(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_revolut_generic(file_content, account_name)

# ---------- 32. NB_Rev_EUR_Revolut ----------
def parse_revolut_nb(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_revolut_generic(file_content, account_name)

# ---------- 33. Revolut_Plavas 1 SIA ----------
def parse_revolut_plavas(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_revolut_generic(file_content, account_name)

# ---------- 34. B1_Estate_CZK_UC ----------
def parse_unicredit_generic(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except Exception:
        try:
            content = file_content.decode('cp1250')
        except Exception:
            content = file_content.decode('latin-1')
    if content.startswith('\ufeff'):
        content = content[1:]
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if len(lines) < 3:
        return []
    header = -1
    for i, l in enumerate(lines):
        if 'From Account' in l and 'Amount' in l and 'Currency' in l:
            header = i
            break
    if header == -1:
        return []
    hdr_parts = [p.strip() for p in lines[header].split(';')]
    ci = {}
    for i, h in enumerate(hdr_parts):
        hc = h.strip()
        if hc == 'Amount': ci['amount'] = i
        elif hc == 'Booking Date': ci['date'] = i
        elif hc == 'Transaction Details': ci['description'] = i
        elif hc == 'Name': ci['counterparty'] = i
    if 'amount' not in ci: ci['amount'] = 1
    if 'date' not in ci: ci['date'] = 3
    if 'description' not in ci: ci['description'] = 13
    if 'counterparty' not in ci: ci['counterparty'] = 9
    for line in lines[header + 1:]:
        parts = [p.strip() for p in line.split(';')]
        while parts and parts[-1] == '':
            parts.pop()
        if len(parts) < 3:
            continue
        try:
            astr = parts[ci['amount']] if ci['amount'] < len(parts) else ''
            amount = parse_amount(astr)
            if amount == 0.0:
                continue
            date = parse_date(parts[ci['date']] if ci['date'] < len(parts) else '')
            if not date:
                continue
            cp = parts[ci['counterparty']].strip() if ci['counterparty'] < len(parts) else ''
            if not cp and len(parts) > 8:
                cp = parts[8].strip()
            desc = parts[ci['description']].strip() if ci['description'] < len(parts) else ''
            if not desc:
                for idx in [14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28]:
                    if idx < len(parts):
                        v = parts[idx].strip()
                        if v and v != 'nan' and len(v) > 1 and not re.match(r'^[\d.,\-]+$', v):
                            desc = v
                            break
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': cp[:200],
                'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return transactions

def parse_unicredit_b1_estate(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unicredit_generic(file_content, account_name)

# ---------- 35. Garpiz UniCredit Bank CZK ----------
def parse_garpiz_unicredit(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unicredit_generic(file_content, account_name)

# ---------- 36. Garpiz_Pernink_CZK_UC ----------
def parse_garpiz_pernink(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unicredit_generic(file_content, account_name)

# ---------- 37. Koruna UniCredit- CZK ----------
def parse_koruna_unicredit(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unicredit_generic(file_content, account_name)

# ---------- 38. TwoHills_Molly_Unicredit_CZK ----------
def parse_twohills_unicredit(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unicredit_generic(file_content, account_name)

# ---------- 39. WIO Business Bank ----------
def parse_wio_business(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except Exception:
        try:
            content = file_content.decode('cp1250')
        except Exception:
            content = file_content.decode('latin-1')
    if content.startswith('\ufeff'):
        content = content[1:]
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
        if h == 'Amount': ci['amount'] = i
        elif h == 'Date': ci['date'] = i
        elif h == 'Description': ci['description'] = i
        elif h == 'Notes': ci['notes'] = i
    if 'amount' not in ci: ci['amount'] = 10
    if 'date' not in ci: ci['date'] = 7
    if 'description' not in ci: ci['description'] = 9
    for line in lines[header + 1:]:
        parts = []
        cur = ''
        inq = False
        for ch in line:
            if ch == '"':
                inq = not inq
            elif ch == ',' and not inq:
                parts.append(cur.strip())
                cur = ''
            else:
                cur += ch
        parts.append(cur.strip())
        parts = [p.strip('"') for p in parts]
        if len(parts) < 3:
            continue
        try:
            date = parse_date(parts[ci['date']] if ci['date'] < len(parts) else '')
            if not date:
                continue
            amount = parse_amount(parts[ci['amount']] if ci['amount'] < len(parts) else '')
            if amount == 0.0:
                continue
            desc = parts[ci['description']] if ci['description'] < len(parts) else ''
            cp = desc
            if desc:
                d1 = re.sub(r'/REF/.*$', '', desc)
                d1 = re.sub(r'FOR \d+$', '', d1).strip()
                if d1 and len(d1) > 2:
                    cp = d1[:200]
            notes = parts[ci['notes']] if 'notes' in ci and ci['notes'] < len(parts) else ''
            full = desc
            if notes and notes != 'N/A' and notes:
                full = f"{desc} | {notes}" if desc else notes
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': cp[:200],
                'Наименование счета': account_name,
                'Описание': full[:500]
            })
        except Exception:
            continue
    return transactions

# ---------- 40. Saida_Wise ----------
def parse_saida_wise(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_saida_n26(file_content, account_name)

# ==================== МАРШРУТИЗАЦИЯ ====================

def get_parser(account_name: str):
    """Возвращает функцию-парсер по имени счёта."""
    low = account_name.lower()
    
    # ----- Точное соответствие -----
    exact = {
        'Regina Alfa bank NOMIQA RUB': 'regina_alfa',
        'Tinkoff RUB': 'tinkoff',
        'BSR Estate EUR BluOr 2': 'bsr_bluor_2',
        'BSR Estate EUR BluOr 3': 'bsr_bluor_3',
        'KL59 Rev NB EUR BluOR': 'kl59_rev_nb_bluor',
        'JenHor Unelma CZK CSAS': 'jenhor_unelma',
        'DŽIBIK Main CSOB CZK': 'dzibik_main_csob',
        'JENISOV HORSKA CSOB CZK': 'jenisov_horska_csob_czk',
        'JENISOV HORSKA S R EUR': 'jenisov_horska_csob_eur',
        'RR Strojka CZK CSOB': 'rr_strojka_czk_csob',
        'RR Strojka EUR CSOB': 'rr_strojka_eur_csob',
        'Koruna Strojka CZK CSOB': 'koruna_strojka_czk_csob',
        'Koruna Strojka EUR CSOB': 'koruna_strojka_eur_csob',
        'Stalkin ML2 CZK FIO': 'stalkin_ml2_fio',
        'AN14 Estate EUR Industra': 'industra_an14',
        'Plavas1 Estate EUR Industra': 'industra_plavas1',
        'KL59 Rev NB EUR Industra': 'industra_kl59',
        'Kapital bank Saida AZN': 'kapital_saida_azn',
        'Kapital bank Saida AZN бизнес счет': 'kapital_saida_business',
        'MASHREQ BANK AED NOMIQA': 'mashreq',
        'Budapest EUR MKB': 'budapest_eur_mkb',
        'Budapest HUF MKB': 'budapest_huf_mkb',
        'Saida N26': 'saida_n26',
        'BUNDA LLC Pasha Bank AED дирхам': 'bunda_pasha_aed',
        'BUNDA LLC Pasha Bank AZN': 'bunda_pasha_azn',
        'Paysera Baltic Solutions EUR': 'paysera_baltic',
        'Paysera Sveciy Namai Lithuania EUR': 'paysera_sveciy',
        'Paysera BS PROPERTY SIA': 'paysera_property',
        'Paysera BS RERUM SIA': 'paysera_rerum',
        'RAK BANK Nomiqa клиенты': 'rak_bank',
        'AN14 Estate EUR Revolut': 'revolut_an14',
        'NB Rev EUR Revolut': 'revolut_nb',
        'Revolut Plavas 1 SIA': 'revolut_plavas',
        'B1 Estate CZK UC': 'unicredit_b1',
        'Garpiz UniCredit Bank CZK': 'garpiz_unicredit',
        'Garpiz Pernink CZK UC': 'garpiz_pernink',
        'Koruna UniCredit CZK': 'koruna_unicredit',
        'TwoHills Molly Unicredit CZK': 'twohills_unicredit',
        'WIO Business Bank': 'wio_business',
        'Saida Wise': 'saida_wise',
    }
    key = exact.get(account_name)
    
    # ----- Частичное совпадение по ключевым словам -----
    if key is None:
        # Revolut
        if 'revolut' in low:
            if 'nb rev' in low or 'nb_rev' in low:
                key = 'revolut_nb'
            elif 'plavas' in low:
                key = 'revolut_plavas'
            else:
                key = 'revolut_an14'
        # Paysera
        elif 'paysera' in low:
            if 'baltic' in low: key = 'paysera_baltic'
            elif 'sveciy' in low: key = 'paysera_sveciy'
            elif 'property' in low: key = 'paysera_property'
            elif 'rerum' in low: key = 'paysera_rerum'
            else: key = 'paysera_baltic'
        # Industra / Plavas / P1 statement
        elif 'industra' in low or 'plavas' in low or 'kl59' in low or 'an14' in low or 'p1 statement' in low:
            key = 'industra_an14'
        # CSOB
        elif 'csob' in low:
            if 'dzibik' in low: key = 'dzibik_main_csob'
            elif 'jenisov' in low and 'eur' in low: key = 'jenisov_horska_csob_eur'
            elif 'jenisov' in low: key = 'jenisov_horska_csob_czk'
            elif 'rr strojka' in low and 'eur' in low: key = 'rr_strojka_eur_csob'
            elif 'rr strojka' in low: key = 'rr_strojka_czk_csob'
            elif 'koruna strojka' in low and 'eur' in low: key = 'koruna_strojka_eur_csob'
            elif 'koruna strojka' in low: key = 'koruna_strojka_czk_csob'
            elif 'rr rev ostr' in low: key = 'rr_rev_ostr_csob'
            else: key = 'dzibik_main_csob'
        # BluOr
        elif 'bluor' in low:
            if 'kl59' in low: key = 'kl59_rev_nb_bluor'
            elif 'bsr' in low and '3' in low: key = 'bsr_bluor_3'
            elif 'bsr' in low: key = 'bsr_bluor_2'
            else: key = 'kl59_rev_nb_bluor'
        # UniCredit
        elif 'unicredit' in low or 'garpiz' in low or 'twohills' in low or 'two hills' in low or 'b1 estate' in low or 'koruna unicredit' in low:
            if 'b1 estate' in low: key = 'unicredit_b1'
            elif 'pernink' in low: key = 'garpiz_pernink'
            elif 'garpiz' in low and 'unicredit' in low: key = 'garpiz_unicredit'
            elif 'twohills' in low or 'two hills' in low: key = 'twohills_unicredit'
            elif 'koruna' in low: key = 'koruna_unicredit'
            else: key = 'unicredit_b1'
        # MKB
        elif 'mkb' in low or 'budapest' in low:
            if 'huf' in low: key = 'budapest_huf_mkb'
            else: key = 'budapest_eur_mkb'
        # Pasha Bank
        elif 'pasha' in low or 'bunda' in low:
            if 'azn' in low: key = 'bunda_pasha_azn'
            else: key = 'bunda_pasha_aed'
        # MASHREQ
        elif 'mashreq' in low or 'mashr' in low or 'nomiqa' in low and 'aed' in low:
            key = 'mashreq'
        # WIO
        elif 'wio' in low:
            key = 'wio_business'
        # Tinkoff
        elif 'tinkoff' in low or 't-bank' in low:
            key = 'tinkoff'
        # Regina Alfa
        elif 'regina alfa' in low:
            key = 'regina_alfa'
        # FIO
        elif 'fio' in low or 'stalkin' in low:
            key = 'stalkin_ml2_fio'
        # JenHor
        elif 'jenhor' in low or 'unelma' in low:
            key = 'jenhor_unelma'
        # N26 / Wise
        elif 'n26' in low:
            key = 'saida_n26'
        elif 'wise' in low:
            key = 'saida_wise'
        # Kapital / Saida AZN
        elif 'kapital' in low or 'saida' in low:
            if 'бизнес' in low or 'business' in low: key = 'kapital_saida_business'
            else: key = 'kapital_saida_azn'
        # RAK BANK
        elif 'rak bank' in low or ('rak' in low and 'bank' in low):
            key = 'rak_bank'
    
    # ----- Словарь функций -----
    parsers = {
        'regina_alfa': parse_regina_alfa_xlsx,
        'tinkoff': parse_tinkoff_docx,
        'bsr_bluor_2': parse_bsr_bluor_2,
        'bsr_bluor_3': parse_bsr_bluor_3,
        'kl59_rev_nb_bluor': parse_kl59_rev_nb_bluor,
        'jenhor_unelma': parse_jenhor_unelma,
        'dzibik_main_csob': parse_dzibik_main_csob,
        'jenisov_horska_csob_czk': parse_jenisov_horska_csob_czk,
        'jenisov_horska_csob_eur': parse_jenisov_horska_csob_eur,
        'rr_strojka_czk_csob': parse_rr_strojka_czk_csob,
        'rr_strojka_eur_csob': parse_rr_strojka_eur_csob,
        'koruna_strojka_czk_csob': parse_koruna_strojka_czk_csob,
        'koruna_strojka_eur_csob': parse_koruna_strojka_eur_csob,
        'rr_rev_ostr_csob': parse_rr_strojka_czk_csob,
        'stalkin_ml2_fio': parse_stalkin_ml2_fio,
        'industra_an14': parse_industra_an14,
        'industra_plavas1': parse_industra_plavas1,
        'industra_kl59': parse_industra_kl59,
        'kapital_saida_azn': parse_kapital_saida_azn,
        'kapital_saida_business': parse_kapital_saida_business,
        'mashreq': parse_mashreq,
        'budapest_eur_mkb': parse_budapest_eur_mkb,
        'budapest_huf_mkb': parse_budapest_huf_mkb,
        'saida_n26': parse_saida_n26,
        'bunda_pasha_aed': parse_bunda_pasha_aed,
        'bunda_pasha_azn': parse_bunda_pasha_azn,
        'paysera_baltic': parse_paysera_baltic,
        'paysera_sveciy': parse_paysera_sveciy,
        'paysera_property': parse_paysera_property,
        'paysera_rerum': parse_paysera_rerum,
        'rak_bank': parse_rak_bank,
        'revolut_an14': parse_revolut_an14,
        'revolut_nb': parse_revolut_nb,
        'revolut_plavas': parse_revolut_plavas,
        'unicredit_b1': parse_unicredit_b1_estate,
        'garpiz_unicredit': parse_garpiz_unicredit,
        'garpiz_pernink': parse_garpiz_pernink,
        'koruna_unicredit': parse_koruna_unicredit,
        'twohills_unicredit': parse_twohills_unicredit,
        'wio_business': parse_wio_business,
        'saida_wise': parse_saida_wise,
    }
    
    if key is not None and key in parsers:
        return parsers[key], key
    return None, None

def parse_file(file_content: bytes, filename: str) -> Tuple[List[Dict], str]:
    """Возвращает (транзакции, описание_парсера)."""
    account_name = clean_account_name(filename)
    ext = os.path.splitext(filename)[1].lower()
    low = account_name.lower()
    
    # ---- DOCX/PDF ----
    if ext == '.docx':
        if 'regina alfa' in low:
            return parse_regina_alfa_docx(file_content, account_name), 'parse_regina_alfa_docx'
        if 'tinkoff' in low:
            return parse_tinkoff_docx(file_content, account_name), 'parse_tinkoff_docx'
        return [], 'DOCX: парсер не найден'
    if ext == '.pdf':
        if 'regina alfa' in low:
            return parse_regina_alfa_pdf(file_content, account_name), 'parse_regina_alfa_pdf'
        return [], 'PDF: парсер не найден'
    
    # ---- CSV/XLSX/XLS ----
    parser, key = get_parser(account_name)
    if parser is None:
        return [], f'нет парсера для: {account_name}'
    transactions = parser(file_content, account_name)
    return transactions, f'{key} ({account_name})'

# ==================== ИНТЕРФЕЙС ====================

def main():
    st.markdown("### 📥 Загрузка файлов")
    st.markdown("Перетащите выписки в окно ниже или нажмите **Browse files**.")
    
    uploaded_files = st.file_uploader(
        "Выберите файлы",
        type=['csv', 'xlsx', 'xls', 'docx', 'pdf'],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )
    
    if not uploaded_files:
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("""
            <div class="info-card">
              <div class="info-card-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="#5D9968" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </div>
              <div class="info-card-text">
                <h4>Поддержка форматов</h4>
                <p>CSV, XLSX, XLS, DOCX, PDF</p>
              </div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown("""
            <div class="info-card">
              <div class="info-card-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M9 11l3 3L22 4M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" stroke="#5D9968" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </div>
              <div class="info-card-text">
                <h4>Автоопределение</h4>
                <p>Программа сама подберёт парсер по имени файла</p>
              </div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown("""
            <div class="info-card">
              <div class="info-card-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M3 3v18h18M18 17V9M13 17V5M8 17v-3" stroke="#5D9968" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </div>
              <div class="info-card-text">
                <h4>Экспорт в Excel</h4>
                <p>Скачайте итог в один клик</p>
              </div>
            </div>
            """, unsafe_allow_html=True)
    
    if uploaded_files:
        st.markdown("---")
        st.markdown(f"**Загружено файлов:** {len(uploaded_files)}")
        
        if st.button("🚀 Обработать файлы"):
            all_transactions = []
            failed_files = []
            file_stats = []
            debug_info = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Обработка: {uploaded_file.name}")
                
                try:
                    content = uploaded_file.read()
                    transactions, parser_name = parse_file(content, uploaded_file.name)
                    account_name = clean_account_name(uploaded_file.name)
                    debug_info.append(
                        f"🔍 `{uploaded_file.name}` → счёт: `{account_name}` → парсер: `{parser_name}` → **{len(transactions)}** операций"
                    )
                    if transactions:
                        all_transactions.extend(transactions)
                        file_stats.append(f"✅ {uploaded_file.name}: {len(transactions)} операций")
                    else:
                        file_stats.append(f"ℹ️ {uploaded_file.name}: транзакций не найдено")
                except Exception as e:
                    failed_files.append(f"{uploaded_file.name} (ошибка: {e})")
                    debug_info.append(f"❌ `{uploaded_file.name}` → исключение: {e}")
                
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            status_text.text("✅ Обработка завершена!")
            
            st.markdown("### 📋 Результат обработки")
            for stat in file_stats:
                st.info(stat)
            
            with st.expander("🔧 Техническая информация (какой парсер применён)"):
                for line in debug_info:
                    st.markdown(line)
            
            if all_transactions:
                df = pd.DataFrame(all_transactions)
                df['Сумма_число'] = df['Сумма']
                df['Сумма'] = df['Сумма'].apply(format_amount)
                
                st.markdown("---")
                st.markdown("### 📊 Итоги")
                
                col1, col2, col3 = st.columns(3)
                income = df['Сумма_число'][df['Сумма_число'] > 0].sum()
                expense = abs(df['Сумма_число'][df['Сумма_число'] < 0].sum())
                
                with col1:
                    st.metric("📊 Всего операций", len(all_transactions))
                with col2:
                    st.metric("📈 Доходы", f"{income:,.2f}".replace('.', ','))
                with col3:
                    st.metric("📉 Расходы", f"{expense:,.2f}".replace('.', ','))
                
                st.markdown("---")
                st.markdown("### 🧾 Детализация транзакций")
                st.dataframe(df.drop(columns=['Сумма_число']), use_container_width=True, hide_index=True)
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.drop(columns=['Сумма_число']).to_excel(writer, sheet_name='Транзакции', index=False)
                    bs = df.groupby('Наименование счета').agg({'Сумма_число': ['count', 'sum']}).round(2)
                    bs.columns = ['Количество операций', 'Сумма']
                    bs['Сумма'] = bs['Сумма'].apply(lambda x: f"{x:,.2f}".replace('.', ','))
                    bs.to_excel(writer, sheet_name='Сводка по счетам')
                output.seek(0)
                
                st.markdown("### 💾 Сохранить результат")
                st.download_button(
                    label="📥 Скачать Excel",
                    data=output,
                    file_name="анализ_банковских_выписок.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            if failed_files:
                st.warning(f"⚠️ Не удалось обработать: {len(failed_files)} файлов")
                for f in failed_files:
                    st.write(f"- {f}")
    
    st.markdown("""
    <div class="footer-note">
      Работает локально. Данные никуда не отправляются.
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
