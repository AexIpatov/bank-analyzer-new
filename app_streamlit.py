# [FIX-2026-09-11-FINAL] Полная переработка парсеров:
#   - Revolut: pandas.read_csv с корректной обработкой кавычек
#   - Industra: знак по колонке Debit/Credit, нормализация -+/+-
#   - CSOB: csv.DictReader
#   - Paysera: не переворачивать знак, если он уже есть
#   - BluOr: маркеры Total / Конечный остаток
#   - Pasha Bank: маркеры MÖVCUD BALANS / DÖVRÜN SONUNA BALANS
#   - JenHor/Kapital: разбор через doc.tables
#   - parse_amount: корректен для '-+0.36', '+700', '-2000.0'

import streamlit as st
import pandas as pd
import os
import re
import csv
import hashlib
from datetime import datetime
from io import BytesIO, StringIO
from typing import Dict, List, Tuple, Callable
from docx import Document
import pdfplumber

st.set_page_config(
    page_title="Аналитик банковских выписок",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root {
    --grass-dark: #1B5E20; --grass: #2E7D32; --grass-light: #4CAF50;
    --grass-accent: #81C784; --mint-light: #C8E6C9; --mint-soft: #E8F5E9;
    --ink: #1A2E1F; --ink-soft: #3E5042; --ink-muted: #6E8072; --border: #C8E6C9;
}
.stApp { background: linear-gradient(180deg, #F7FAF5 0%, #EEF6EA 50%, #E1EEDD 100%);
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif; color: var(--ink); }
.main { background: transparent; }
footer {visibility: hidden;} #MainMenu {visibility: hidden;}
.hero { background: linear-gradient(135deg, #1B5E20 0%, #2E7D32 50%, #4CAF50 100%);
    padding: 3rem 2.5rem; border-radius: 28px; color: #FFFFFF; margin-bottom: 2rem;
    box-shadow: 0 20px 45px rgba(27, 94, 32, 0.32); position: relative; overflow: hidden; }
.hero::before { content: ''; position: absolute; top: -100px; right: -100px;
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(255,255,255,0.18) 0%, transparent 70%);
    border-radius: 50%; }
.hero-content { position: relative; z-index: 2; display: flex; align-items: center; gap: 2rem; flex-wrap: wrap; }
.hero-text { flex: 1; min-width: 280px; }
.hero-text h1 { font-size: 2.5rem; font-weight: 800; margin: 0 0 0.6rem 0; letter-spacing: -1px; }
.hero-text p { font-size: 1.1rem; margin: 0; opacity: 0.95; }
.hero-chips { display: flex; gap: 0.5rem; margin-top: 1.2rem; flex-wrap: wrap; }
.chip { background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3);
    padding: 0.35rem 0.85rem; border-radius: 999px; font-size: 0.85rem; font-weight: 500;
    backdrop-filter: blur(8px); }
.hero-illustration { position: relative; z-index: 2; }
.stButton > button { background: linear-gradient(135deg, #1B5E20 0%, #2E7D32 100%);
    color: #FFFFFF; border: none; border-radius: 14px; padding: 0.75rem 1.6rem;
    font-weight: 600; font-size: 1rem; transition: all 0.25s;
    box-shadow: 0 6px 16px rgba(27, 94, 32, 0.32); }
.stButton > button:hover { background: linear-gradient(135deg, #124A17 0%, #1B5E20 100%);
    transform: translateY(-2px); color: #FFFFFF; }
.stDownloadButton > button { background: linear-gradient(135deg, #2E7D32 0%, #4CAF50 100%);
    color: #FFFFFF; border: none; border-radius: 14px; padding: 0.8rem 1.8rem; font-weight: 600; }
.stDownloadButton > button:hover { background: linear-gradient(135deg, #1B5E20 0%, #2E7D32 100%);
    transform: translateY(-2px); color: #FFFFFF; }
.stFileUploader { background: #FFFFFF; border-radius: 20px; padding: 1.2rem;
    border: 2px dashed var(--border); box-shadow: 0 4px 20px rgba(27, 94, 32, 0.05); }
.stFileUploader:hover { border-color: var(--grass-light); }
.stFileUploader section { border: none !important; background: transparent !important; }
.stFileUploader button { background: #E8F5E9 !important; color: var(--ink) !important;
    border: 1px solid var(--grass-accent) !important; border-radius: 10px !important; }
.stFileUploader button:hover { background: var(--grass-light) !important; color: #FFFFFF !important; }
.stMetric { background: #FFFFFF; border-radius: 20px; padding: 1.5rem 1.6rem;
    border: 1px solid #E1EEDD; box-shadow: 0 6px 22px rgba(27, 94, 32, 0.07);
    position: relative; overflow: hidden; }
.stMetric::before { content: ''; position: absolute; top: 0; left: 0; height: 100%; width: 6px;
    background: linear-gradient(180deg, #1B5E20 0%, #4CAF50 100%); }
.stMetric:hover { transform: translateY(-4px); box-shadow: 0 14px 32px rgba(27, 94, 32, 0.20); }
.stMetric label { color: var(--ink-soft) !important; font-size: 0.9rem !important; text-transform: uppercase; }
.stMetric [data-testid="stMetricValue"] { color: var(--ink) !important; font-weight: 700 !important; font-size: 1.7rem !important; }
.stDataFrame { border-radius: 20px; overflow: hidden; box-shadow: 0 8px 28px rgba(27, 94, 32, 0.10); background: #FFFFFF; }
.stAlert { border-radius: 14px; border: none; }
div[data-baseweb="notification"][kind="positive"] { background: #E8F5E9; color: var(--ink); }
div[data-baseweb="notification"][kind="info"] { background: #EEF6EA; color: var(--ink); }
div[data-baseweb="notification"][kind="warning"] { background: #FBF3E0; color: #7A5B10; }
.stProgress > div > div > div { background: linear-gradient(90deg, #1B5E20 0%, #4CAF50 100%); border-radius: 8px; }
h3 { color: var(--ink); font-weight: 700; padding-bottom: 0.6rem; border-bottom: 2px solid #E1EEDD;
    margin-top: 2rem; margin-bottom: 1.2rem; font-size: 1.25rem; }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: #F7FAF5; }
::-webkit-scrollbar-thumb { background: #A5D6A7; border-radius: 5px; }
::-webkit-scrollbar-thumb:hover { background: #4CAF50; }
hr { border: none; border-top: 1px solid #E1EEDD; margin: 2rem 0; }
.info-card { background: #FFFFFF; border-radius: 18px; padding: 1.4rem 1.5rem;
    border: 1px solid #E1EEDD; display: flex; align-items: center; gap: 1.2rem;
    box-shadow: 0 4px 16px rgba(27, 94, 32, 0.06); }
.info-card-icon { flex-shrink: 0; width: 56px; height: 56px; display: flex; align-items: center;
    justify-content: center; border-radius: 14px;
    background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%); }
.info-card-text h4 { color: var(--ink); margin: 0 0 0.25rem 0; font-size: 1rem; font-weight: 600; }
.info-card-text p { color: var(--ink-muted); margin: 0; font-size: 0.88rem; }
.footer-note { text-align: center; color: var(--ink-muted); font-size: 0.85rem; padding: 1.5rem 0 0.5rem 0; }
.summary-table { border-radius: 16px; overflow: hidden;
    box-shadow: 0 8px 28px rgba(27, 94, 32, 0.10); background: #FFFFFF; margin-bottom: 1rem; }
.summary-table table { border-collapse: collapse; width: 100%;
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif; font-size: 0.92rem; }
.summary-table thead th { background: linear-gradient(135deg, #1B5E20 0%, #2E7D32 100%);
    color: #FFFFFF; padding: 12px 14px; text-align: left; font-weight: 600; border: none; white-space: nowrap; }
.summary-table tbody td { padding: 10px 14px; border-bottom: 1px solid #E1EEDD;
    color: var(--ink); background: #FFFFFF; }
.summary-table tbody tr:nth-child(even) td { background: #F7FAF5; }
.summary-table tbody tr:hover td { background: #E8F5E9; }
.summary-table tbody tr:last-child td { border-bottom: none; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
<div class="hero-content">
<div class="hero-text">
<h1>💼 Аналитик банковских выписок</h1>
<p>Загружайте выписки — получайте единый отчёт по доходам и расходам</p>
<div class="hero-chips">
<span class="chip">📄 CSV</span><span class="chip">📊 XLSX</span>
<span class="chip">📑 XLS</span><span class="chip">📝 DOCX</span><span class="chip">📕 PDF</span>
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
<path d="M57 100 L79 80 L101 60 L123 85 L145 50" stroke="#FFFFFF" stroke-width="3" fill="none" stroke-linecap="round"/>
<circle cx="57" cy="100" r="5" fill="#FFFFFF"/><circle cx="79" cy="80" r="5" fill="#FFFFFF"/>
<circle cx="101" cy="60" r="5" fill="#FFFFFF"/><circle cx="123" cy="85" r="5" fill="#FFFFFF"/>
<circle cx="145" cy="50" r="5" fill="#FFFFFF"/>
<circle cx="160" cy="40" r="16" fill="#FFD86B" stroke="#FFFFFF" stroke-width="2"/>
<text x="160" y="46" text-anchor="middle" font-size="16" font-weight="700" fill="#1B5E20">₽</text>
</svg>
</div>
</div>
</div>
""", unsafe_allow_html=True)

# ==================== УТИЛИТЫ ====================

def clean_account_name(filename: str) -> str:
    name = os.path.splitext(filename)[0]
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
    for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d", "%d-%m-%Y",
                "%Y%m%d", "%d.%m.%y", "%d/%m/%y", "%d-%b-%Y", "%d-%b-%y",
                "%d %b %Y", "%d %b %y"]:
        try:
            return datetime.strptime(s, fmt).strftime("%d-%m-%Y")
        except Exception:
            continue
    return s


def parse_amount(amount_str) -> float:
    """
    [FIX-FINAL] Корректная обработка двойных знаков '-+22.39', '+-', '--'.
    Нечётное число минусов → отрицательное.
    """
    if amount_str is None or pd.isna(amount_str):
        return 0.0
    s = str(amount_str).strip()
    if s in ['', 'nan', '-', 'None', 'null', 'NaN', 'N/A', 'n/a', '--', '-+', '+-']:
        return 0.0

    # Собираем все ведущие знаки
    sign_match = re.match(r'^([+\-\s]*)(.*)$', s)
    if sign_match:
        signs, rest = sign_match.groups()
        minus_count = signs.count('-')
        is_negative = (minus_count % 2 == 1)
        s = rest
    else:
        is_negative = False

    if s.startswith('(') and s.endswith(')'):
        is_negative = not is_negative
        s = s[1:-1]

    s = re.sub(r'\s*[₽$€£]\s*$', '', s)
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
    s = re.sub(r'[^\d.]', '', s)
    if not s or s == '.':
        return 0.0
    try:
        v = float(s)
        return -v if is_negative else v
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
    if b'word/' in head or b'wordprocessingml' in head:
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


# ==================== УНИВЕРСАЛЬНЫЙ CSV ЧЕРЕЗ PANDAS ====================

def _read_csv_pandas(file_content: bytes, sep: str = None):
    """
    Читает CSV через pandas с автоопределением разделителя.
    Корректно обрабатывает кавычки и запятые внутри полей.
    """
    # Пробуем разные кодировки
    for enc in ['utf-8-sig', 'utf-8', 'cp1251', 'latin-1']:
        try:
            text = file_content.decode(enc)
            break
        except Exception:
            continue
    else:
        return None

    if sep is None:
        # Автоопределение
        first_lines = '\n'.join([l for l in text.split('\n') if l.strip()][:5])
        if first_lines.count(';') > first_lines.count(','):
            sep = ';'
        elif first_lines.count('\t') > 0:
            sep = '\t'
        else:
            sep = ','

    for engine in ['python', 'c']:
        try:
            df = pd.read_csv(
                StringIO(text),
                sep=sep,
                engine=engine,
                on_bad_lines='skip',
                dtype=str,
                keep_default_na=False,
                skipinitialspace=True,
            )
            if df is not None and not df.empty:
                return df
        except Exception:
            continue
    return None


# ==================== CSOB ====================

def parse_csob_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """
    [FIX-FINAL] CSOB через csv.DictReader / pandas.
    Заголовок: account number;account currency;alias;account name;posting date;
               value date;payment amount;...
    """
    transactions = []
    content = read_text_with_encoding(file_content)
    if not content:
        return []
    lines = [l.rstrip('\r') for l in content.split('\n') if l.strip()]
    if len(lines) < 2:
        return []

    # Разделитель
    sep = ';' if lines[0].count(';') >= lines[0].count(',') else ','

    header_idx = -1
    for i, line in enumerate(lines):
        low = line.lower()
        if ('account number' in low and 'posting date' in low) \
           or ('account number' in low and 'payment amount' in low):
            header_idx = i
            break
    if header_idx == -1:
        return []

    # Через csv.reader — корректно обрабатывает кавычки
    reader = csv.reader(lines[header_idx:], delimiter=sep, quotechar='"')
    rows = list(reader)
    if not rows:
        return []
    hdr = [h.strip().lstrip('\ufeff') for h in rows[0]]

    ci = {}
    for i, h in enumerate(hdr):
        hl = h.strip().lower()
        if 'account number' in hl and 'account' not in ci:
            ci['account'] = i
        elif hl == 'account currency' and 'currency' not in ci:
            ci['currency'] = i
        elif hl == 'account name' and 'account_name' not in ci:
            ci['account_name'] = i
        elif 'posting date' in hl and 'date' not in ci:
            ci['date'] = i
        elif 'value date' in hl and 'value_date' not in ci:
            ci['value_date'] = i
        elif 'payment amount' in hl and 'amount' not in ci:
            ci['amount'] = i
        elif hl == 'payment currency' and 'pay_currency' not in ci:
            ci['pay_currency'] = i
        elif hl == 'balance' and 'balance' not in ci:
            ci['balance'] = i
        elif 'transaction type' in hl and 'type' not in ci:
            ci['type'] = i
        elif hl == 'counterparty' and 'counterparty' not in ci:
            ci['counterparty'] = i
        elif "counterparty's account" in hl and 'counterparty_account' not in ci:
            ci['counterparty_account'] = i
        elif 'message to beneficiary' in hl and 'message' not in ci:
            ci['message'] = i
        elif hl == 'note' and 'note' not in ci:
            ci['note'] = i

    if 'date' not in ci or 'amount' not in ci:
        return []

    for parts in rows[1:]:
        if not parts:
            continue
        while parts and parts[-1] == '':
            parts.pop()
        if len(parts) <= max(ci.get('date', 0), ci.get('amount', 0)):
            continue
        try:
            date = parse_date(safe_str(parts[ci['date']]))
            if not date:
                continue
            amount_str = safe_str(parts[ci['amount']])
            if not amount_str:
                continue
            if re.match(r'^\d{7,}$', amount_str):
                continue
            amount = parse_amount(amount_str)
            if amount == 0.0 or not _is_reasonable_amount(amount):
                continue

            counterparty = ''
            if 'counterparty' in ci and ci['counterparty'] < len(parts):
                counterparty = safe_str(parts[ci['counterparty']])
            description = ''
            for key in ['note', 'message', 'type']:
                if key in ci and ci[key] < len(parts):
                    v = safe_str(parts[ci[key]])
                    if v and v != 'nan' and v not in ['-'] and not re.match(r'^[\d.,\-]+$', v):
                        description = v
                        break
            if not description:
                for i, p in enumerate(parts):
                    if i in (ci.get('date'), ci.get('amount'), ci.get('balance'),
                             ci.get('value_date'), ci.get('currency'),
                             ci.get('pay_currency'), ci.get('counterparty_account')):
                        continue
                    if p and p != 'nan' and len(p) > 2 and not re.match(r'^[\d.,\-]+$', p) \
                       and not re.match(r'^\d{4}-\d{2}-\d{2}$', p):
                        description = p
                        break

            transactions.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': counterparty[:200],
                'Наименование счета': account_name,
                'Описание': description[:500]
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
                    transactions.append({
                        'Дата': parse_date(str(current_date)),
                        'Сумма': amt,
                        'Контрагент': '',
                        'Наименование счета': account_name,
                        'Описание': (current_desc or '')[:500]
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
            transactions.append({
                'Дата': parse_date(str(current_date)),
                'Сумма': amt,
                'Контрагент': '',
                'Наименование счета': account_name,
                'Описание': (current_desc or '')[:500]
            })
    return transactions


def parse_regina_alfa_docx(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []

    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if not cells:
                continue
            joined = ' | '.join([c for c in cells if c])
            m = re.search(
                r'(\d{2}\.\d{2}\.\d{4})\s*\|?\s*([A-Z0-9_]+)\s*\|?\s*(.*?)\s*\|?\s*(-?[\d\s]+[.,]\d{2})\s*RUR',
                joined, re.DOTALL
            )
            if m:
                try:
                    date = parse_date(m.group(1))
                    code = m.group(2).strip()
                    desc = re.sub(r'\s+', ' ', m.group(3)).strip()
                    amount = parse_amount(m.group(4))
                    if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                        continue
                    result.append({
                        'Дата': date, 'Сумма': amount,
                        'Контрагент': '', 'Наименование счета': account_name,
                        'Описание': f"{code} {desc}"[:500]
                    })
                except Exception:
                    continue

    if not result:
        full_text = docx_all_text(file_content)
        if not full_text:
            return []
        for line in full_text.split('\n'):
            m = re.search(
                r'(\d{2}\.\d{2}\.\d{4})\s+([A-Z0-9_]+)\s+(.+?)\s+(-?[\d\s]+[.,]\d{2})\s*RUR',
                line
            )
            if m:
                try:
                    date = parse_date(m.group(1))
                    code = m.group(2).strip()
                    desc = re.sub(r'\s+', ' ', m.group(3)).strip()
                    amount = parse_amount(m.group(4))
                    if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                        continue
                    result.append({
                        'Дата': date, 'Сумма': amount,
                        'Контрагент': '', 'Наименование счета': account_name,
                        'Описание': f"{code} {desc}"[:500]
                    })
                except Exception:
                    continue

    if not result:
        full_text = docx_all_text(file_content)
        pattern = re.compile(
            r'(\d{2}\.\d{2}\.\d{4})\s+(.+?)\s+(-?[\d\s]+[.,]\d{2})\s*RUR',
            re.DOTALL
        )
        for m in pattern.finditer(full_text):
            try:
                date = parse_date(m.group(1).strip())
                desc = re.sub(r'\s+', ' ', m.group(2)).strip()
                amount = parse_amount(m.group(3))
                if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': '', 'Наименование счета': account_name,
                    'Описание': desc[:500]
                })
            except Exception:
                continue

    return result


def parse_regina_alfa_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []
    pattern = re.compile(
        r'(\d{2}\.\d{2}\.\d{4})\s*([A-Z0-9\_]+)?\s*(.+?)\s*(-?[\d\s]+[.,]\d{2})\s*RUR',
        re.DOTALL
    )
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(1).strip())
            code = (m.group(2) or '').strip()
            desc = re.sub(r'\s+', ' ', m.group(3)).strip()
            amount = parse_amount(m.group(4))
            if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': '', 'Наименование счета': account_name,
                'Описание': (f"{code} {desc}" if code else desc)[:500]
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
        for table in doc.tables:
            if not table.rows:
                continue
            first = ' '.join(c.text.strip() for c in table.rows[0].cells)
            if 'Описание операции' in first and 'Сумма' in first:
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
            if 'Внутренний перевод' in desc:
                cp = 'Внутренний перевод'
            elif 'Внешний перевод' in desc:
                cp = 'Внешний перевод'
            elif 'Перевод себе' in desc:
                cp = 'Перевод себе'
            elif 'Плата за' in desc:
                cp = 'Т-Банк'
            elif 'Перевод' in desc:
                cp = 'Перевод'
            else:
                cp = desc[:60]
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp, 'Наименование счета': account_name,
                'Описание': desc[:500]
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
        r'([^\n]{2,300}?)(?:\s+7596|\s+---|\n|$)',
        re.MULTILINE
    )
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(1))
            amount = parse_amount(m.group(3))
            desc = re.sub(r'\s+', ' ', m.group(5)).strip()
            if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            if 'Внутренний перевод' in desc:
                cp = 'Внутренний перевод'
            elif 'Внешний перевод' in desc:
                cp = 'Внешний перевод'
            elif 'Перевод себе' in desc:
                cp = 'Перевод себе'
            elif 'Плата за' in desc:
                cp = 'Т-Банк'
            elif 'Перевод' in desc:
                cp = 'Перевод'
            else:
                cp = desc[:60]
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp, 'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return result


# ==================== BluOr Bank ====================

_BLUOR_SERVICE_MARKERS = [
    'начальный остаток', 'конечный остаток',
    'входящий остаток', 'исходящий остаток',
    'opening balance', 'closing balance',
    'starting balance', 'ending balance',
    'дебет (d)', 'кредит (c)',
    'debit (d)', 'credit (c)',
    'saldo počáteční', 'saldo konečné',
    'sākuma atlikums', 'beigu atlikums',
    'total',
]


def _is_bluor_service_row(parts: List[str]) -> bool:
    for idx in (2, 3, 4):
        if idx < len(parts):
            v = parts[idx].strip().lower()
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
            low = desc.lower()
            if ttype == 'D':
                amount = -abs(amount)
            elif ttype == 'C':
                amount = abs(amount)

            cp = 'BluOr Bank' if 'bluor' in low or 'bank' in low else ''

            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp[:200], 'Наименование счета': account_name,
                'Описание': desc[:500]
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
        r'([^\n]{3,300}?)\s+'
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
            if any(w in low for w in ['starting balance', 'ending balance', 'total',
                                      'начальный остаток', 'конечный остаток',
                                      'дебет (d)', 'кредит (c)']):
                continue
            if ttype == 'D':
                amount = -abs(amount)
            elif ttype == 'C':
                amount = abs(amount)
            cp = 'BluOr Bank' if 'bluor' in low or 'bank' in low else ''
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp[:200], 'Наименование счета': account_name,
                'Описание': desc[:500]
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
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': parts[2][:200] if len(parts) > 2 else '',
                'Наименование счета': account_name,
                'Описание': ' '.join(parts[3:])[:500] if len(parts) > 3 else ''
            })
        except Exception:
            continue
    return result


def parse_jenhor_unelma_docx(file_content: bytes, account_name: str) -> List[Dict]:
    """
    [FIX-FINAL] JenHor Unelma — разбираем таблицы напрямую.
    Формат таблицы: Дата | Описание | Сумма
    """
    result = []
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []

    # Основной путь: таблицы
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if len(cells) < 3:
                continue
            # Ищем дату в первой ячейке
            m = re.match(r'^(\d{2}\.\d{2}\.\d{4})$', cells[0])
            if not m:
                continue
            date = parse_date(m.group(1))
            # Ищем сумму в последней ячейке
            amount = None
            for c in reversed(cells):
                if re.match(r'^-?\d[\d\s]*[,.]\d{2}$', c):
                    amount = parse_amount(c)
                    break
            if amount is None or amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            # Описание — всё, кроме даты и суммы
            desc_parts = []
            for c in cells[1:]:
                if c and not re.match(r'^-?\d[\d\s]*[,.]\d{2}$', c):
                    desc_parts.append(c)
            desc = ' '.join(desc_parts).strip()
            low = desc.lower()
            if any(w in low for w in ['počáteční zůstatek', 'konečný zůstatek',
                                      'celkem připsáno', 'celkem odepsáno',
                                      'přehled pohyb', 'shrnuti pohyb', 'obraty za']):
                continue
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': 'Česká spořitelna',
                'Наименование счета': account_name,
                'Описание': desc[:500]
            })

    # Fallback — текст
    if not result:
        full_text = docx_all_text(file_content)
        pattern = re.compile(
            r'(\d{2}\.\d{2}\.\d{4})\s+(.+?)\s+(-?\d[\d\s]*[,.]\d{2})(?!\d)',
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
                                          'celkem připsáno', 'celkem odepsáno']):
                    continue
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': 'Česká spořitelna',
                    'Наименование счета': account_name,
                    'Описание': desc[:500]
                })
            except Exception:
                continue
    return result


def parse_jenhor_unelma_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []
    result = []
    pattern = re.compile(
        r'(\d{2}\.\d{2}\.\d{4})\s+(.+?)\s+(-?\d[\d\s]*[,.]\d{2})(?!\d)',
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
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': 'Česká spořitelna',
                'Наименование счета': account_name,
                'Описание': desc[:500]
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
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp[:200], 'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return result


# ==================== Industra ====================

_INDUSTRA_SERVICE_DESC = [
    'начальный остаток', 'конечный остаток',
    'дебетовый оборот', 'кредитный оборот',
    'неоплаченная комиссия',
]


def _is_industra_service_desc(desc: str) -> bool:
    low = (desc or '').lower()
    return any(w in low for w in _INDUSTRA_SERVICE_DESC)


def _industra_amount_from_columns(debit_val: float, credit_val: float):
    """
    [FIX-FINAL] Возвращает (amount, found) по колонкам Debit/Credit.
    Debit → минус. Credit → плюс. Знак в самой ячейке игнорируется
    (кроме случая, когда в ячейке явно 0).
    """
    has_debit = abs(debit_val) > 0.0001
    has_credit = abs(credit_val) > 0.0001
    if has_debit and not has_credit:
        return -abs(debit_val), True
    if has_credit and not has_debit:
        return abs(credit_val), True
    if has_debit and has_credit:
        # Оба ненулевые — берём большее по модулю, но знак определяем по колонке
        if abs(debit_val) >= abs(credit_val):
            return -abs(debit_val), True
        else:
            return abs(credit_val), True
    return 0.0, False


def _parse_industra_generic(file_content: bytes, account_name: str) -> List[Dict]:
    result = []

    # --- 1) XLSX ---
    df = read_xlsx(file_content)
    if df is not None and not df.empty:
        header_row = -1
        for idx, row in df.iterrows():
            if idx < 80:
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
                s = str(v).strip()
                sl = s.lower()
                if ('дата транзакции' in sl) or ('transaction date' in sl) or (sl == 'date'):
                    if 'date' not in ci:
                        ci['date'] = i
                elif ('получатель' in sl) or ('плательщик' in sl) or ('counterparty' in sl) or ('payee' in sl):
                    if 'counterparty' not in ci:
                        ci['counterparty'] = i
                elif ('информация о транзакции' in sl) or ('описание' in sl) or ('description' in sl) or ('details' in sl):
                    if 'description' not in ci:
                        ci['description'] = i
                elif ('тип транзакции' in sl) or ('transaction type' in sl):
                    if 'type' not in ci:
                        ci['type'] = i
                elif (('дебет' in sl) or ('debit' in sl)) and ('кредит' not in sl) and ('credit' not in sl):
                    if 'debit' not in ci:
                        ci['debit'] = i
                elif (('кредит' in sl) or ('credit' in sl)) and ('дебет' not in sl) and ('debit' not in sl):
                    if 'credit' not in ci:
                        ci['credit'] = i
            if 'date' in ci and ('debit' in ci or 'credit' in ci):
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
                        ttype = safe_str(row.iloc[ci['type']]) if 'type' in ci and ci['type'] < len(row) else ''
                        desc = safe_str(row.iloc[ci['description']]) if 'description' in ci and ci['description'] < len(row) else ''
                        if _is_industra_service_desc(desc):
                            continue
                        debit_val = 0.0
                        credit_val = 0.0
                        if 'debit' in ci and ci['debit'] < len(row):
                            dv = row.iloc[ci['debit']]
                            if pd.notna(dv) and str(dv).strip() not in ['', 'nan', '-']:
                                debit_val = parse_amount(str(dv).strip().replace(',', '.'))
                        if 'credit' in ci and ci['credit'] < len(row):
                            cv = row.iloc[ci['credit']]
                            if pd.notna(cv) and str(cv).strip() not in ['', 'nan', '-']:
                                credit_val = parse_amount(str(cv).strip().replace(',', '.'))
                        amount, found = _industra_amount_from_columns(debit_val, credit_val)
                        if not found or not _is_reasonable_amount(amount):
                            continue
                        cp = safe_str(row.iloc[ci['counterparty']]) if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
                        full_desc = desc
                        if ttype and ttype not in ['nan', '']:
                            full_desc = f"{ttype} | {desc}" if desc else ttype
                        result.append({
                            'Дата': date, 'Сумма': amount,
                            'Контрагент': cp[:200], 'Наименование счета': account_name,
                            'Описание': full_desc[:500]
                        })
                    except Exception:
                        continue
                if result:
                    return result

    # --- 2) CSV ---
    content = read_text_with_encoding(file_content)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if not lines:
        return result
    sample = '\n'.join(lines[:8])
    sep = ';' if sample.count(';') >= sample.count(',') else ','
    header_idx = -1
    for i, l in enumerate(lines[:80]):
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
            if 'type' not in ci:
                ci['type'] = i
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
            desc = parts[ci['description']] if 'description' in ci and ci['description'] < len(parts) else ''
            if _is_industra_service_desc(desc):
                continue
            ttype = parts[ci['type']] if 'type' in ci and ci['type'] < len(parts) else ''
            debit_val = 0.0
            credit_val = 0.0
            if 'debit' in ci and ci['debit'] < len(parts):
                debit_val = parse_amount(parts[ci['debit']].replace(',', '.').replace(' ', ''))
            if 'credit' in ci and ci['credit'] < len(parts):
                credit_val = parse_amount(parts[ci['credit']].replace(',', '.').replace(' ', ''))
            amount, found = _industra_amount_from_columns(debit_val, credit_val)
            if not found or not _is_reasonable_amount(amount):
                continue
            cp = parts[ci['counterparty']] if 'counterparty' in ci and ci['counterparty'] < len(parts) else ''
            full_desc = desc
            if ttype and ttype not in ['nan', '']:
                full_desc = f"{ttype} | {desc}" if desc else ttype
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp[:200], 'Наименование счета': account_name,
                'Описание': full_desc[:500]
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
    tables = pdf_all_tables(file_content)
    for table in tables:
        header_idx = -1
        for i, row in enumerate(table):
            joined = ' '.join(row)
            if 'Дата транзакции' in joined and 'Дебет' in joined and 'Кредит' in joined:
                header_idx = i
                break
        if header_idx == -1:
            continue
        hdr = table[header_idx]
        ci = {}
        for i, h in enumerate(hdr):
            if 'Дата транзакции' in h:
                ci['date'] = i
            elif 'Получатель' in h or 'Плательщик' in h:
                ci['counterparty'] = i
            elif 'Информация о транзакции' in h:
                ci['description'] = i
            elif 'Тип транзакции' in h:
                ci['type'] = i
            elif 'Дебет' in h and 'Кредит' not in h:
                ci['debit'] = i
            elif 'Кредит' in h and 'Дебет' not in h:
                ci['credit'] = i
        for row in table[header_idx + 1:]:
            try:
                date = parse_date(row[ci.get('date', 0)] if ci.get('date', 0) < len(row) else '')
                if not date:
                    continue
                desc = row[ci.get('description', 0)] if 'description' in ci and ci['description'] < len(row) else ''
                if _is_industra_service_desc(desc):
                    continue
                debit_val = 0.0
                credit_val = 0.0
                if 'debit' in ci and ci['debit'] < len(row):
                    debit_val = parse_amount(row[ci['debit']].replace(',', '.').replace(' ', ''))
                if 'credit' in ci and ci['credit'] < len(row):
                    credit_val = parse_amount(row[ci['credit']].replace(',', '.').replace(' ', ''))
                amount, found = _industra_amount_from_columns(debit_val, credit_val)
                if not found or not _is_reasonable_amount(amount):
                    continue
                cp = row[ci['counterparty']] if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp[:200], 'Наименование счета': account_name,
                    'Описание': desc[:500]
                })
            except Exception:
                continue
    return result


# ==================== Kapital bank ====================

def _kapital_should_skip(desc: str) -> bool:
    low = (desc or '').lower()
    keywords = [
        'balance', 'saldo', 'start', 'end', 'period',
        'лимит', 'баланс', 'период', 'available', 'кредитн',
        'сумма зачислений', 'сумма списаний', 'баланс на начало',
        'баланс на конец', 'заблокированные',
        'информация по карте', 'выписка', 'владелец',
    ]
    return any(w in low for w in keywords)


def parse_kapital_saida_azn_csv(file_content: bytes, account_name: str) -> List[Dict]:
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
            if _kapital_should_skip(desc):
                continue
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': '', 'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return result


def parse_kapital_saida_docx(file_content: bytes, account_name: str) -> List[Dict]:
    """
    [FIX-FINAL] Kapital Bank — операции имеют структуру:
    <дата> | <сумма списания> | ... | <описание>
    Всегда расход (минус).
    """
    result = []
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []

    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if not cells:
                continue
            # Ищем дату в формате YYYY-MM-DD
            date_cell = None
            date_idx = -1
            for i, c in enumerate(cells):
                if re.match(r'^\d{4}-\d{2}-\d{2}$', c):
                    date_cell = c
                    date_idx = i
                    break
            if not date_cell:
                continue
            # Ищем сумму в первых 3 ячейках после даты
            amount = None
            for c in cells[date_idx + 1:date_idx + 5]:
                if re.match(r'^-?\d[\d\s]*[.,]\d{2}$', c):
                    amount = parse_amount(c)
                    break
            if amount is None or amount == 0.0:
                continue
            # Описание — первая ячейка с буквами и без цифр-сумм
            desc = ''
            for c in reversed(cells):
                if c and re.search(r'[A-Za-zА-Яа-я]{3,}', c):
                    desc = c
                    break
            if _kapital_should_skip(desc):
                continue
            date = parse_date(date_cell)
            if not date or not _is_reasonable_amount(amount):
                continue
            result.append({
                'Дата': date, 'Сумма': -abs(amount),
                'Контрагент': 'Kapital Bank',
                'Наименование счета': account_name,
                'Описание': desc[:500]
            })

    if not result:
        full_text = docx_all_text(file_content)
        pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2})\s*\|?\s*'
            r'([\d\s]+[.,]\d{1,2})\s*\|?\s*'
            r'([\d\s]+[.,]\d{1,2})\s*\|?\s*'
            r'([\d\s]+[.,]\d{1,2})\s*\|?\s*'
            r'([A-Za-zА-Яа-я][^\n|]{2,120})',
            re.MULTILINE
        )
        for m in pattern.finditer(full_text):
            try:
                date = parse_date(m.group(1).strip())
                amount = parse_amount(m.group(2).strip())
                desc = m.group(5).strip()
                if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                if _kapital_should_skip(desc):
                    continue
                result.append({
                    'Дата': date, 'Сумма': -abs(amount),
                    'Контрагент': 'Kapital Bank',
                    'Наименование счета': account_name,
                    'Описание': desc[:500]
                })
            except Exception:
                continue
    return result


def parse_kapital_saida_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    tables = pdf_all_tables(file_content)
    for table in tables:
        for row in table:
            if len(row) < 5:
                continue
            try:
                date = parse_date(row[0])
                if not date:
                    continue
                amount = parse_amount(row[1])
                desc = row[4] if len(row) > 4 else ''
                if amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                if _kapital_should_skip(desc):
                    continue
                result.append({
                    'Дата': date, 'Сумма': -abs(amount),
                    'Контрагент': 'Kapital Bank',
                    'Наименование счета': account_name,
                    'Описание': desc[:500]
                })
            except Exception:
                continue
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
            cp = ''
            for p in desc.split('/'):
                p_clean = p.strip()
                if p_clean and len(p_clean) > 2 and 'REF' not in p_clean and 'SRN' not in p_clean and 'REC' not in p_clean:
                    if not re.match(r'^[A-Z0-9]{10,}$', p_clean):
                        cp = p_clean[:200]
                        break
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp, 'Наименование счета': account_name,
                'Описание': desc[:500]
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
                cp = ''
                for p in desc.split('/'):
                    p_clean = p.strip()
                    if p_clean and len(p_clean) > 2 and 'REF' not in p_clean and 'SRN' not in p_clean and 'REC' not in p_clean:
                        if not re.match(r'^[A-Z0-9]{10,}$', p_clean):
                            cp = p_clean[:200]
                            break
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp, 'Наименование счета': account_name,
                    'Описание': desc[:500]
                })
            except Exception:
                continue
    return result


# ==================== MKB ====================

def _parse_mkb_any(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    df = None
    if _is_real_xls(file_content):
        try:
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
                    result.append({
                        'Дата': date, 'Сумма': amount,
                        'Контрагент': cp[:200], 'Наименование счета': account_name,
                        'Описание': (f"{ttype} | {desc}" if ttype else desc)[:500]
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
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp[:200], 'Наименование счета': account_name,
                'Описание': (f"{ttype} | {desc}" if ttype else desc)[:500]
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
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp[:200], 'Наименование счета': account_name,
                    'Описание': desc[:500]
                })
            except Exception:
                continue
    return result


# ==================== N26 ====================

_N26_SERVICE_MARKERS = [
    'saldo previo', 'nuevo saldo', 'transacciones salientes',
    'transacciones entrantes', 'saldo anterior', 'saldo final',
    'extracto', 'espacio', 'deseño', 'emitido en',
    'saldo', 'balance',
]


def _is_n26_service_line(line: str) -> bool:
    low = line.lower()
    return any(m in low for m in _N26_SERVICE_MARKERS)


def parse_n26_docx(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []

    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            joined = ' | '.join([c for c in cells if c])
            if _is_n26_service_line(joined):
                continue
            m = re.search(
                r'(Fecha de valor\s+)?(\d{2}\.\d{2}\.\d{4})'
                r'\s*\|?\s*'
                r'(\d{2}\.\d{2}\.\d{4})?'
                r'\s*\|?\s*'
                r'(-?\d[\d\s]*[.,]\d{2})\s*€',
                joined
            )
            if m:
                try:
                    date = parse_date(m.group(2))
                    amount = parse_amount(m.group(4))
                    if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                        continue
                    desc = ''
                    for c in cells:
                        if c and not re.match(r'^\d{2}\.\d{2}\.\d{4}$', c) \
                           and not re.match(r'^-?\d[\d\s]*[.,]\d{2}\s*€?$', c) \
                           and not _is_n26_service_line(c):
                            desc = c
                            break
                    result.append({
                        'Дата': date, 'Сумма': amount,
                        'Контрагент': 'N26', 'Наименование счета': account_name,
                        'Описание': desc[:500]
                    })
                except Exception:
                    continue

    if not result:
        for para in doc.paragraphs:
            line = para.text.strip()
            if not line or _is_n26_service_line(line):
                continue
            m = re.search(
                r'(\d{2}\.\d{2}\.\d{4})\s+'
                r'(\d{2}\.\d{2}\.\d{4})?\s*'
                r'(-?\d[\d\s]*[.,]\d{2})\s*€\s*$',
                line
            )
            if m:
                try:
                    date = parse_date(m.group(1))
                    amount = parse_amount(m.group(3))
                    if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                        continue
                    desc = re.sub(r'\d{2}\.\d{2}\.\d{4}', '', line)
                    desc = re.sub(r'-?\d[\d\s]*[.,]\d{2}\s*€', '', desc).strip()
                    result.append({
                        'Дата': date, 'Сумма': amount,
                        'Контрагент': 'N26', 'Наименование счета': account_name,
                        'Описание': desc[:500]
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
        r'^(.+?)\s+'
        r'(\d{2}\.\d{2}\.\d{4})\s+'
        r'(\d{2}\.\d{2}\.\d{4})?\s*'
        r'(-?\d[\d\s]*[.,]\d{2})\s*€\s*$',
        re.MULTILINE
    )
    for m in pattern.finditer(full_text):
        try:
            desc_raw = m.group(1)
            if _is_n26_service_line(desc_raw):
                continue
            desc = re.sub(r'\s+', ' ', desc_raw).strip()
            date = parse_date(m.group(2))
            amount = parse_amount(m.group(4))
            if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': 'N26', 'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    if not result:
        pattern2 = re.compile(
            r'^(\d{2}\.\d{2}\.\d{4})\s+(\d{2}\.\d{2}\.\d{4})\s+(-?\d[\d\s]*[.,]\d{2})\s*€\s*$',
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
                    'Контрагент': 'N26', 'Наименование счета': account_name,
                    'Описание': ''
                })
            except Exception:
                continue
    return result


# ==================== Paysera ====================

def parse_paysera_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """
    [FIX-FINAL] Paysera через pandas.read_excel.
    Правила: 'Д' = расход, 'К' = приход.
    В колонке 'Сумма и валюта' уже есть знак — не переворачиваем.
    """
    result = []
    df = read_xlsx(file_content, sheet_name='Worksheet')
    if df is None or df.empty:
        df = read_xlsx(file_content, sheet_name='Sheet1')
    if df is None or df.empty:
        df = read_xlsx(file_content)
    if df is None or df.empty:
        return []
    header_row = -1
    for idx, row in df.iterrows():
        if idx < 30:
            rs = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Тип' in rs and ('Дата и время' in rs or 'Сумма и валюта' in rs):
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
        if 'Дата и время' in s:
            ci['date'] = i
        elif 'Получатель' in s or 'Плательщик' in s:
            ci['counterparty'] = i
        elif 'Назначение платежа' in s:
            ci['purpose'] = i
        elif 'Сумма и валюта' in s:
            ci['amount'] = i
        elif 'Кредит / Дебет' in s or 'Кредит/Дебет' in s:
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
            # Знак по типу: Д → минус, К → плюс. Но если в сумме уже есть знак — не переворачиваем.
            if ttype in ('Д', 'D') and amount > 0:
                amount = -abs(amount)
            elif ttype in ('К', 'C') and amount < 0:
                amount = abs(amount)
            cp = safe_str(row.iloc[ci['counterparty']]) if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
            desc = safe_str(row.iloc[ci['purpose']]) if 'purpose' in ci and ci['purpose'] < len(row) else ''
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp[:200], 'Наименование счета': account_name,
                'Описание': desc[:500]
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
        r'([A-Za-zА-Яа-я][^\d\-+]{2,80}?)'
        r'\s*'
        r'\((\d{6,})\)'
        r'\s*'
        r'(-?\d[\d\s]*[.,]\d{2})\s*([A-Z]{3})',
        re.MULTILINE
    )
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(2))
            amount = parse_amount(m.group(8))
            counterparty = re.sub(r'\s+', ' ', m.group(6)).strip()
            op_type = m.group(1).strip()
            if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': counterparty[:200],
                'Наименование счета': account_name,
                'Описание': f"{op_type}: {counterparty}"[:500]
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
            r'([A-Za-zА-Яа-я][^\d\-+]{2,80}?)'
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
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': counterparty[:200],
                    'Наименование счета': account_name,
                    'Описание': f"{op_type}: {counterparty}"[:500]
                })
            except Exception:
                continue
    return result


def parse_paysera_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []
    date_pattern = re.compile(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})')
    raw_dates = list(date_pattern.finditer(full_text))
    if not raw_dates:
        return []
    groups = []
    cur = {'date': raw_dates[0].group(1), 'start': raw_dates[0].start(), 'end': raw_dates[0].end()}
    for dm in raw_dates[1:]:
        if dm.start() - cur['end'] < 400:
            cur['end'] = dm.end()
        else:
            groups.append(cur)
            cur = {'date': dm.group(1), 'start': dm.start(), 'end': dm.end()}
    groups.append(cur)

    eur_pattern = re.compile(r'([+\-]?\d[\d\s]*[.,]\d{2})\s*EUR')
    eur_matches = []
    for m in eur_pattern.finditer(full_text):
        eur_matches.append({
            'start': m.start(),
            'end': m.end(),
            'amount': parse_amount(m.group(1)),
        })

    STOP_WORDS = ['balance', 'turnover', 'final', 'start', 'debit', 'credit']

    for gi, g in enumerate(groups):
        date = parse_date(g['date'])
        if not date:
            continue
        window_start = g['end']
        window_end = groups[gi + 1]['start'] if gi + 1 < len(groups) else window_start + 2000
        if window_end <= window_start:
            continue
        window_eur = [e for e in eur_matches if window_start <= e['start'] < window_end]
        negative = [e for e in window_eur if e['amount'] < 0]
        positive = [e for e in window_eur if e['amount'] > 0]
        chosen_amount = None
        chosen_pos = None
        if negative:
            chosen = negative[0]
            chosen_amount = chosen['amount']
            chosen_pos = chosen['start']
        elif positive:
            for e in positive:
                pre = full_text[max(0, e['start'] - 60):e['start']].lower()
                if any(w in pre for w in STOP_WORDS):
                    continue
                chosen_amount = e['amount']
                chosen_pos = e['start']
                break
        if chosen_amount is None or chosen_amount == 0.0 or not _is_reasonable_amount(chosen_amount):
            continue
        desc = ''
        window_text = full_text[window_start:window_end]
        purpose_match = re.search(
            r'Purpose of payment\s*:\s*([^\.]{1,200}?)(?:\.|$)',
            window_text, re.IGNORECASE
        )
        if purpose_match:
            desc = purpose_match.group(1).strip()
        if not desc:
            head = full_text[max(0, chosen_pos - 120):chosen_pos]
            for marker in ['Commission fee', 'Commission', 'Плата за', 'Плата',
                           'Payment', 'Transfer', 'Fee',
                           'Sąskaitos palaikymo mokestis']:
                if marker.lower() in head.lower() or marker.lower() in window_text.lower():
                    desc = marker
                    break
        if not desc:
            desc = 'Paysera operation'
        result.append({
            'Дата': date, 'Сумма': chosen_amount,
            'Контрагент': 'Paysera LT',
            'Наименование счета': account_name,
            'Описание': desc[:500]
        })

    seen = set()
    deduped = []
    for r in result:
        key = (r['Дата'], r['Сумма'])
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
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': '', 'Наименование счета': account_name,
                'Описание': parts[1][:500] if len(parts) > 1 else ''
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
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': '', 'Наименование счета': account_name,
                    'Описание': row[1][:500]
                })
            except Exception:
                continue
    return result


# ==================== Revolut ====================

def parse_revolut_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """
    [FIX-FINAL] Revolut — используем pandas.read_csv с quotechar='"'.
    Это корректно обрабатывает запятые внутри описаний.
    Сумма берётся из колонки 'Amount' (не 'Total amount'), чтобы сохранить знак.
    """
    result = []

    # Пытаемся через pandas
    df = _read_csv_pandas(file_content, sep=',')
    if df is not None and not df.empty:
        # Нормализуем имена столбцов
        cols_lower = {str(c).strip().lower(): c for c in df.columns}
        def find_col(*patterns):
            for p in patterns:
                for low, orig in cols_lower.items():
                    if p in low:
                        return orig
            return None

        date_col = find_col('date started')
        amount_col = find_col('amount')  # 'Amount' — точное совпадение приоритетнее
        # Уточняем: 'amount' должен быть именно 'Amount', а не 'orig amount'/'total amount'
        for low, orig in cols_lower.items():
            if low == 'amount':
                amount_col = orig
                break
        total_amount_col = None
        for low, orig in cols_lower.items():
            if 'total amount' in low:
                total_amount_col = orig
                break
        desc_col = find_col('description')
        cp_col = find_col('payer')
        benef_col = find_col('beneficiary name')
        state_col = find_col('state')
        type_col = find_col('type')

        if date_col and amount_col:
            for idx, row in df.iterrows():
                try:
                    if state_col:
                        st = safe_str(row.get(state_col, '')).upper()
                        if st and st != 'COMPLETED':
                            continue
                    date = parse_date(row.get(date_col, ''))
                    if not date:
                        continue
                    amount = parse_amount(row.get(amount_col, ''))
                    if amount == 0.0 or not _is_reasonable_amount(amount):
                        continue
                    ttype = safe_str(row.get(type_col, '')).upper() if type_col else ''
                    if ttype == 'TOPUP':
                        amount = abs(amount)
                    elif ttype == 'FEE':
                        amount = -abs(amount)
                    cp = ''
                    if cp_col:
                        cp = safe_str(row.get(cp_col, ''))
                    if (not cp or cp == 'nan') and benef_col:
                        cp = safe_str(row.get(benef_col, ''))
                    desc = safe_str(row.get(desc_col, '')) if desc_col else ''
                    if not cp:
                        m = re.search(r'(?:To|from)\s+([^,]+)', desc)
                        cp = m.group(1).strip() if m else desc[:200]
                    result.append({
                        'Дата': date, 'Сумма': amount,
                        'Контрагент': cp[:200], 'Наименование счета': account_name,
                        'Описание': desc[:500]
                    })
                except Exception:
                    continue
            if result:
                return result

    # Fallback — ручной разбор
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

    # CSV-разбор через csv.reader
    reader = csv.reader(lines[header:], delimiter=',', quotechar='"')
    rows = list(reader)
    if not rows:
        return []
    hdr = [h.strip().lstrip('\ufeff') for h in rows[0]]
    ci = {}
    for i, h in enumerate(hdr):
        hl = h.lower().strip()
        if 'date started' in hl and 'date' not in ci:
            ci['date'] = i
        elif hl == 'amount' and 'amount' not in ci:
            ci['amount'] = i
        elif hl == 'total amount' and 'amount' not in ci:
            ci['amount'] = i
        elif 'description' in hl and 'description' not in ci:
            ci['description'] = i
        elif hl == 'payer' and 'counterparty' not in ci:
            ci['counterparty'] = i
        elif hl == 'state' and 'state' not in ci:
            ci['state'] = i
        elif hl == 'type' and 'type' not in ci:
            ci['type'] = i
        elif hl == 'beneficiary name' and 'beneficiary' not in ci:
            ci['beneficiary'] = i
    if 'date' not in ci:
        ci['date'] = 0
    if 'amount' not in ci:
        ci['amount'] = 14
    if 'description' not in ci:
        ci['description'] = 5
    if 'type' not in ci:
        ci['type'] = 3
    if 'state' not in ci:
        ci['state'] = 4
    for parts in rows[1:]:
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
            cp = ''
            if 'counterparty' in ci and ci['counterparty'] < len(parts):
                cp = parts[ci['counterparty']].strip()
            if (not cp or cp == 'nan') and 'beneficiary' in ci and ci['beneficiary'] < len(parts):
                cp = parts[ci['beneficiary']].strip()
            desc = parts[ci['description']] if ci['description'] < len(parts) else ''
            if not cp:
                m = re.search(r'(?:To|from)\s+([^,]+)', desc)
                cp = m.group(1).strip() if m else desc[:200]
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp[:200], 'Наименование счета': account_name,
                'Описание': desc[:500]
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
    result = []
    tables = pdf_all_tables(file_content)
    for table in tables:
        for row in table:
            if len(row) < 6:
                continue
            try:
                dstr = row[0]
                m = re.match(r'(\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4})', dstr)
                if not m:
                    continue
                date = parse_date(m.group(1))
                if not date:
                    continue
                amount = 0.0
                for cell in row[2:8]:
                    p = parse_amount(cell)
                    if p != 0.0:
                        amount = p
                        break
                if amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                desc = row[5] if len(row) > 5 else ''
                cp = ''
                m2 = re.search(r'(?:To|from)\s+([^,]+)', desc)
                if m2:
                    cp = m2.group(1).strip()
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp[:200], 'Наименование счета': account_name,
                    'Описание': desc[:500]
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
    # Используем csv.reader для корректного разбора
    reader = csv.reader(lines[header:], delimiter=';', quotechar='"')
    rows = list(reader)
    if not rows:
        return []
    hdr = [h.strip().lstrip('\ufeff') for h in rows[0]]
    ci = {}
    for i, h in enumerate(hdr):
        hc = h.strip()
        if hc == 'Amount' and 'amount' not in ci:
            ci['amount'] = i
        elif hc == 'Booking Date' and 'date' not in ci:
            ci['date'] = i
        elif hc == 'Transaction Details' and 'description' not in ci:
            ci['description'] = i
        elif hc == 'Name' and 'counterparty' not in ci:
            ci['counterparty'] = i
    if 'amount' not in ci:
        ci['amount'] = 1
    if 'date' not in ci:
        ci['date'] = 3
    if 'description' not in ci:
        ci['description'] = 13
    if 'counterparty' not in ci:
        ci['counterparty'] = 9
    for parts in rows[1:]:
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
            desc = parts[ci['description']].strip() if ci['description'] < len(parts) else ''
            if not desc:
                for idx in range(len(parts) - 1, -1, -1):
                    if idx in (ci['amount'], ci['date'], ci['counterparty']):
                        continue
                    v = parts[idx].strip()
                    if v and v != 'nan' and len(v) > 2 and not re.match(r'^[\d.,\-]+$', v) and not re.match(r'^\d{4}-\d{2}-\d{2}$', v):
                        desc = v
                        break
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp[:200], 'Наименование счета': account_name,
                'Описание': desc[:500]
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
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp[:200], 'Наименование счета': account_name,
                    'Описание': desc[:500]
                })
            except Exception:
                continue
    if not result:
        full_text = pdf_all_text(file_content)
        pattern = re.compile(
            r'(-?\d[\d\s]*[.,]\d{2})\s*[;,]?\s*([A-Z]{3})\s*[;,]?\s*(\d{4}-\d{2}-\d{2})\s*[;,]?\s*([^\n;]{3,300})',
            re.MULTILINE
        )
        for m in pattern.finditer(full_text):
            try:
                amount = parse_amount(m.group(1))
                date = parse_date(m.group(3))
                desc = re.sub(r'\s+', ' ', m.group(4)).strip()
                if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': '', 'Наименование счета': account_name,
                    'Описание': desc[:500]
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
    reader = csv.reader(lines[header:], delimiter=',', quotechar='"')
    rows = list(reader)
    if not rows:
        return []
    hdr = [h.strip().lstrip('\ufeff') for h in rows[0]]
    ci = {}
    for i, h in enumerate(hdr):
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
    for parts in rows[1:]:
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
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp[:200], 'Наименование счета': account_name,
                'Описание': full[:500]
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
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': '', 'Наименование счета': account_name,
                    'Описание': desc[:500]
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
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': '', 'Наименование счета': account_name,
                'Описание': ' '.join(parts[2:])[:500]
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
            cp = safe_str(row.iloc[ci['recipient']]) if 'recipient' in ci and ci['recipient'] < len(row) else ''
            if not cp:
                cp = safe_str(row.iloc[ci['payer']]) if 'payer' in ci and ci['payer'] < len(row) else ''
            full_desc = desc
            if note and note != 'nan':
                full_desc = f"{desc} | {note}" if desc else note
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp[:200], 'Наименование счета': account_name,
                'Описание': full_desc[:500]
            })
        except Exception:
            continue
    return result


# ==================== Pasha Bank ====================

def _is_pasha_service_row(desc: str) -> bool:
    low = (desc or '').lower()
    markers = [
        'dövrün sonuna balans', 'dövrün əvvəlinə balans',
        'mövcud balans', 'balans',
        'hesab üzrə çıxarış',
    ]
    return any(m in low for m in markers)


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
            if _is_pasha_service_row(desc):
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
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp[:200], 'Наименование счета': account_name,
                'Описание': desc[:500]
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
                desc = row[ci['description']] if 'description' in ci and ci['description'] < len(row) else ''
                if _is_pasha_service_row(desc):
                    continue
                credit = parse_amount(row[ci.get('credit', 6)] if ci.get('credit', 6) < len(row) else '')
                debit = parse_amount(row[ci.get('debit', 7)] if ci.get('debit', 7) < len(row) else '')
                if credit == 0.0 and debit == 0.0:
                    continue
                amount = abs(credit) if credit != 0.0 else -abs(debit)
                if not _is_reasonable_amount(amount):
                    continue
                cp = row[ci['counterparty']] if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp[:200], 'Наименование счета': account_name,
                    'Описание': desc[:500]
                })
            except Exception:
                continue
        if result:
            return result
    full_text = pdf_all_text(file_content)
    if not full_text:
        return result
    pattern = re.compile(
        r'(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})\s+'
        r'([^\n;]{3,150}?)\s+'
        r'(-?[\d\s]+[.,]\d{2})\s+'
        r'(-?[\d\s]+[.,]\d{2})',
        re.MULTILINE
    )
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(1))
            desc = re.sub(r'\s+', ' ', m.group(2)).strip()
            if _is_pasha_service_row(desc):
                continue
            v1 = parse_amount(m.group(3))
            v2 = parse_amount(m.group(4))
            amount = abs(v1) if v1 != 0.0 else -abs(v2)
            if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': 'Pasha Bank', 'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return result


# ==================== Универсальные парсеры ====================

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
    reader = csv.reader(lines[header_idx:], delimiter=sep, quotechar='"')
    rows = list(reader)
    if not rows:
        return []
    hdr = [h.strip().lstrip('\ufeff') for h in rows[0]]
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
    for parts in rows[1:]:
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
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp[:200], 'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return result


_NUMERIC_CELL_RE = re.compile(r'^-?[\d\s\u00a0]*[.,]?\d*$')


def _cell_is_numeric(v) -> bool:
    if v is None or pd.isna(v):
        return False
    if isinstance(v, (int, float)):
        return True
    s = str(v).strip()
    if not s:
        return False
    return bool(_NUMERIC_CELL_RE.match(s))


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
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp[:200], 'Наименование счета': account_name,
                'Описание': desc[:500]
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
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp[:200], 'Наименование счета': account_name,
                    'Описание': desc[:500]
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
        r'([^\n;]{3,200}?)\s+'
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
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': '', 'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return result


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
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp[:200], 'Наименование счета': account_name,
                    'Описание': desc[:500]
                })
            except Exception:
                continue
    return result


def parse_csob_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    tables = pdf_all_tables(file_content)
    for table in tables:
        if not table or len(table) < 2:
            continue
        header_idx = -1
        for i, row in enumerate(table[:6]):
            joined = ' '.join(row).lower()
            if 'account number' in joined and 'posting date' in joined:
                header_idx = i
                break
        if header_idx == -1:
            continue
        hdr = table[header_idx]
        ci = {}
        for i, h in enumerate(hdr):
            hl = h.lower()
            if 'account number' in hl and 'account' not in ci:
                ci['account'] = i
            elif 'posting date' in hl and 'date' not in ci:
                ci['date'] = i
            elif 'amount' in hl and 'amount' not in ci:
                ci['amount'] = i
            elif 'counterparty' in hl and 'counterparty' not in ci:
                ci['counterparty'] = i
            elif 'description' in hl and 'description' not in ci:
                ci['description'] = i
        for row in table[header_idx + 1:]:
            try:
                dstr = row[ci.get('date', 4)] if ci.get('date', 4) < len(row) else ''
                date = parse_date(dstr)
                if not date:
                    continue
                astr = row[ci.get('amount', 6)] if ci.get('amount', 6) < len(row) else ''
                amount = parse_amount(astr)
                if amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                cp = row[ci['counterparty']] if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
                desc = row[ci['description']] if 'description' in ci and ci['description'] < len(row) else ''
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp[:200], 'Наименование счета': account_name,
                    'Описание': desc[:500]
                })
            except Exception:
                continue
        if result:
            return result
    full_text = pdf_all_text(file_content)
    if not full_text:
        return result
    pattern = re.compile(
        r'(\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2})\s+'
        r'([^\n;]{3,120}?)\s+'
        r'(-?[\d\s]+[.,]\d{2})\s*([A-Z]{3})?',
        re.MULTILINE
    )
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(1))
            desc = re.sub(r'\s+', ' ', m.group(2)).strip()
            amount = parse_amount(m.group(3))
            if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            low = desc.lower()
            if any(w in low for w in ['počáteční zůstatek', 'konečný zůstatek',
                                      'opening balance', 'closing balance',
                                      'celkem', 'total']):
                continue
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': '', 'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return result


def parse_stalkin_fio_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    tables = pdf_all_tables(file_content)
    for table in tables:
        if not table or len(table) < 2:
            continue
        header_idx = -1
        for i, row in enumerate(table[:6]):
            joined = ' '.join(row).lower()
            if 'date' in joined and ('volume' in joined or 'amount' in joined):
                header_idx = i
                break
        if header_idx == -1:
            continue
        hdr = table[header_idx]
        ci = {}
        for i, h in enumerate(hdr):
            hl = h.lower()
            if 'date' in hl and 'date' not in ci:
                ci['date'] = i
            elif ('volume' in hl or 'amount' in hl) and 'amount' not in ci:
                ci['amount'] = i
            elif 'counterparty' in hl or 'account' in hl:
                if 'counterparty' not in ci:
                    ci['counterparty'] = i
            elif 'description' in hl or 'details' in hl:
                if 'description' not in ci:
                    ci['description'] = i
        for row in table[header_idx + 1:]:
            try:
                date = parse_date(row[ci.get('date', 0)] if ci.get('date', 0) < len(row) else '')
                if not date:
                    continue
                amount = parse_amount(row[ci.get('amount', 1)] if ci.get('amount', 1) < len(row) else '')
                if amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                cp = row[ci['counterparty']] if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
                desc = row[ci['description']] if 'description' in ci and ci['description'] < len(row) else ''
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp[:200], 'Наименование счета': account_name,
                    'Описание': desc[:500]
                })
            except Exception:
                continue
        if result:
            return result
    return result


def parse_saida_wise_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    tables = pdf_all_tables(file_content)
    for table in tables:
        if not table or len(table) < 2:
            continue
        header_idx = -1
        for i, row in enumerate(table[:6]):
            joined = ' '.join(row).lower()
            if 'date' in joined and ('amount' in joined or 'sum' in joined):
                header_idx = i
                break
        if header_idx == -1:
            continue
        hdr = table[header_idx]
        ci = {}
        for i, h in enumerate(hdr):
            hl = h.lower()
            if 'date' in hl and 'date' not in ci:
                ci['date'] = i
            elif ('amount' in hl or 'sum' in hl) and 'amount' not in ci:
                ci['amount'] = i
            elif 'description' in hl or 'details' in hl:
                if 'description' not in ci:
                    ci['description'] = i
            elif 'recipient' in hl or 'payer' in hl or 'name' in hl:
                if 'counterparty' not in ci:
                    ci['counterparty'] = i
        for row in table[header_idx + 1:]:
            try:
                date = parse_date(row[ci.get('date', 0)] if ci.get('date', 0) < len(row) else '')
                if not date:
                    continue
                amount = parse_amount(row[ci.get('amount', 1)] if ci.get('amount', 1) < len(row) else '')
                if amount == 0.0 or not _is_reasonable_amount(amount):
                    continue
                desc = row[ci['description']] if 'description' in ci and ci['description'] < len(row) else ''
                cp = row[ci['counterparty']] if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': cp[:200], 'Наименование счета': account_name,
                    'Описание': desc[:500]
                })
            except Exception:
                continue
        if result:
            return result
    full_text = pdf_all_text(file_content)
    if not full_text:
        return result
    pattern = re.compile(
        r'(\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2})\s+'
        r'([^\n;]{3,120}?)\s+'
        r'(-?[\d\s]+[.,]\d{2})\s*([A-Z]{3})',
        re.MULTILINE
    )
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(1))
            desc = re.sub(r'\s+', ' ', m.group(2)).strip()
            amount = parse_amount(m.group(3))
            if not date or amount == 0.0 or not _is_reasonable_amount(amount):
                continue
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': 'Wise', 'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return result


# ==================== Маршрутизация ====================

def get_parser_by_ext(account_name: str, ext: str):
    low = account_name.lower()

    if ext == '.pdf':
        if 'regina alfa' in low:
            return parse_regina_alfa_pdf, 'regina_alfa_pdf'
        if 'tinkoff' in low:
            return parse_tinkoff_pdf, 'tinkoff_pdf'
        if 'bluor' in low:
            return parse_bluor_pdf, 'bluor_pdf'
        if 'jenhor' in low or 'unelma' in low:
            return parse_jenhor_unelma_pdf, 'jenhor_unelma_pdf'
        if 'industra' in low or 'plavas' in low or 'kl59' in low or 'an14' in low or 'p1 statement' in low:
            return parse_industra_pdf, 'industra_pdf'
        if 'kapital' in low or ('saida' in low and 'azn' in low):
            return parse_kapital_saida_pdf, 'kapital_saida_pdf'
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
        if 'csob' in low:
            return parse_csob_pdf, 'csob_pdf'
        if 'stalkin' in low or 'fio' in low:
            return parse_stalkin_fio_pdf, 'stalkin_fio_pdf'
        if 'wise' in low or ('saida' in low and 'wise' in low):
            return parse_saida_wise_pdf, 'saida_wise_pdf'
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
        if 'kapital' in low or ('saida' in low and 'azn' in low):
            return parse_kapital_saida_docx, 'kapital_saida_docx'
        return parse_docx_universal, 'docx_universal'

    if ext in ('.xlsx', '.xls'):
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
            if 'dzibik' in low:
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
        if 'industra' in low or 'plavas' in low or 'p1 statement' in low or 'kl59' in low or 'an14' in low:
            if 'plavas' in low:
                return parse_industra_plavas1, 'industra_plavas1'
            if 'kl59' in low:
                return parse_industra_kl59, 'industra_kl59'
            return parse_industra_an14, 'industra_an14'
        if 'kapital' in low or ('saida' in low and 'azn' in low):
            return parse_kapital_saida_azn_csv, 'kapital_saida_azn_csv'
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
            if 'dzibik' in low:
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
        if 'industra' in low or 'plavas' in low or 'p1 statement' in low or 'kl59' in low or 'an14' in low:
            if 'plavas' in low:
                return parse_industra_plavas1, 'industra_plavas1'
            if 'kl59' in low:
                return parse_industra_kl59, 'industra_kl59'
            return parse_industra_an14, 'industra_an14'
        if 'kapital' in low or ('saida' in low and 'azn' in low):
            return parse_kapital_saida_azn_csv, 'kapital_saida_azn_csv'
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

    return chain


def parse_file(file_content: bytes, filename: str) -> Tuple[List[Dict], str]:
    account_name = clean_account_name(filename)
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
            return tx, f'{key} ({account_name}, real={real_type}, {len(tx)} операций)'

    msg = f'all_failed: {tried}'
    if errors:
        msg += f' | errors: {errors}'
    return [], msg


# ==================== Сводка ====================

def build_account_summary(rows: List[Dict]) -> pd.DataFrame:
    columns = [
        "Наименование счета",
        "Количество приходных операций",
        "Сумма приходных операций",
        "Количество расходных операций",
        "Сумма расходных операций",
        "Сальдо операций",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows)
    if "Наименование счета" not in df.columns or "Сумма" not in df.columns:
        return pd.DataFrame(columns=columns)

    def _to_float(v):
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            try:
                if pd.isna(v):
                    return 0.0
            except Exception:
                pass
            return float(v)
        s = str(v).strip().replace(" ", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return 0.0

    df = df.copy()
    df["Сумма"] = df["Сумма"].map(_to_float)
    df["Наименование счета"] = df["Наименование счета"].fillna("").astype(str)

    mask_reasonable = df["Сумма"].abs() < MAX_REASONABLE_AMOUNT
    df = df[mask_reasonable].copy()

    if df.empty:
        return pd.DataFrame(columns=columns)

    df["_income"] = df["Сумма"] > 0
    df["_expense"] = df["Сумма"] < 0
    df["_income_sum"] = df["Сумма"].where(df["_income"], 0.0)
    df["_expense_sum"] = (-df["Сумма"]).where(df["_expense"], 0.0)

    grouped = df.groupby("Наименование счета", dropna=False)

    summary = pd.DataFrame({
        "Количество приходных операций": grouped["_income"].sum().astype(int),
        "Сумма приходных операций": grouped["_income_sum"].sum(),
        "Количество расходных операций": grouped["_expense"].sum().astype(int),
        "Сумма расходных операций": grouped["_expense_sum"].sum(),
    }).reset_index()

    summary["Сальдо операций"] = (
        summary["Сумма приходных операций"].astype(float)
        - summary["Сумма расходных операций"].astype(float)
    )

    summary = summary.sort_values("Наименование счета").reset_index(drop=True)

    summary["Сумма приходных операций"] = summary["Сумма приходных операций"].astype(float).round(2)
    summary["Сумма расходных операций"] = summary["Сумма расходных операций"].astype(float).round(2)
    summary["Сальдо операций"] = summary["Сальдо операций"].astype(float).round(2)

    return summary[columns]


# ==================== Excel ====================

def build_operations_excel(df_display: pd.DataFrame) -> BytesIO:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_display.to_excel(writer, sheet_name='Транзакции', index=False)
    output.seek(0)
    return output


def build_summary_excel(summary_df: pd.DataFrame) -> BytesIO:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Сводка по счетам', index=False)
    output.seek(0)
    return output


def build_combined_excel(df_display: pd.DataFrame, summary_df: pd.DataFrame) -> BytesIO:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_display.to_excel(writer, sheet_name='Транзакции', index=False)
        summary_df.to_excel(writer, sheet_name='Сводка по счетам', index=False)
    output.seek(0)
    return output


# ==================== Обработка ====================

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

    progress = st.progress(0)
    status = st.empty()

    for i, uf in enumerate(uploaded_files):
        status.text(f"Обработка: {uf.name}")
        try:
            content = uf.read()
            tx, parser_name = parse_file(content, uf.name)
            account_name = clean_account_name(uf.name)

            debug_info.append(
                f"🔍 `{uf.name}` → счёт: `{account_name}` → "
                f"парсер: `{parser_name}` → **{len(tx)}** операций"
            )

            if tx:
                all_tx.extend(tx)
                file_stats.append(f"✅ {uf.name}: {len(tx)} операций")
            else:
                file_stats.append(f"ℹ️ {uf.name}: транзакций не найдено")

            if uf.name.lower().endswith('.docx'):
                try:
                    dump = docx_dump(content)
                    debug_info.append(f"📄 ДАМП `{uf.name}`:\n```\n{dump[:3000]}\n```")
                except Exception as e:
                    debug_info.append(f"📄 Ошибка дампа: {e}")
            elif uf.name.lower().endswith('.pdf'):
                try:
                    txt = pdf_all_text(content)
                    debug_info.append(f"📄 PDF-текст `{uf.name}` (первые 3000):\n```\n{txt[:3000]}\n```")
                except Exception as e:
                    debug_info.append(f"📄 Ошибка дампа PDF: {e}")
            else:
                try:
                    txt = read_text_with_encoding(content)
                    debug_info.append(f"📄 Текст `{uf.name}` (первые 2000):\n```\n{txt[:2000]}\n```")
                except Exception as e:
                    debug_info.append(f"📄 Ошибка чтения: {e}")

        except Exception as e:
            failed.append(f"{uf.name} (ошибка: {e})")
            debug_info.append(f"❌ `{uf.name}` → исключение: {e}")

        progress.progress((i + 1) / max(1, len(uploaded_files)))

    status.text("✅ Обработка завершена!")

    return {
        'all_tx': all_tx,
        'failed': failed,
        'file_stats': file_stats,
        'debug_info': debug_info,
    }


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
    df_raw['Сумма_число'] = pd.to_numeric(df_raw['Сумма'], errors='coerce').fillna(0.0)

    income = float(df_raw['Сумма_число'][df_raw['Сумма_число'] > 0].sum())
    expense = float(abs(df_raw['Сумма_число'][df_raw['Сумма_число'] < 0].sum()))

    df_display = df_raw.drop(columns=['Сумма_число']).copy()
    df_display['Сумма'] = df_display['Сумма'].apply(format_amount)

    st.markdown("---")
    st.markdown("### 📊 Итоги")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("📊 Всего операций", len(all_tx))
    with c2:
        st.metric("📈 Доходы", f"{income:,.2f}".replace('.', ','))
    with c3:
        st.metric("📉 Расходы", f"{expense:,.2f}".replace('.', ','))

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
            summary_html_df[col] = summary_html_df[col].apply(
                lambda x: f"{x:,.2f}".replace(",", " ").replace(".", ",")
            )
        st.markdown(
            f'<div class="summary-table">{summary_html_df.to_html(index=False, escape=False)}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### 💾 Сохранить результат")
    st.markdown(
        "Скачайте **отдельно операции по выпискам** и **отдельно сводную таблицу**, "
        "или всё вместе одним файлом."
    )

    ops_excel = build_operations_excel(df_display)
    summary_excel = build_summary_excel(summary_df) if not summary_df.empty else None
    combined_excel = build_combined_excel(df_display, summary_df) if not summary_df.empty else None

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


# ==================== main ====================

def main():
    if 'processing_result' not in st.session_state:
        st.session_state['processing_result'] = None
    if 'files_signature' not in st.session_state:
        st.session_state['files_signature'] = None

    st.markdown("### 📥 Загрузка файлов")
    st.markdown("Перетащите выписки в окно ниже или нажмите **Browse files**.")

    uploaded_files = st.file_uploader(
        "Выберите файлы",
        type=['csv', 'xlsx', 'xls', 'docx', 'pdf'],
        accept_multiple_files=True,
        label_visibility="collapsed"
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
            <path d="M9 11l3 3L22 4M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" stroke="#1B5E20" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            </div>
            <div class="info-card-text"><h4>Автоопределение</h4><p>Программа сама подберёт парсер по имени файла</p></div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown("""
            <div class="info-card">
            <div class="info-card-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M3 3v18h18M18 17V9M13 17V5M8 17v-3" stroke="#1B5E20" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            </div>
            <div class="info-card-text"><h4>Экспорт в Excel</h4><p>Скачайте итог в один клик</p></div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("""
        <div class="footer-note">Работает локально. Данные никуда не отправляются.</div>
        """, unsafe_allow_html=True)
        return

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
    <div class="footer-note">Работает локально. Данные никуда не отправляются.</div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
