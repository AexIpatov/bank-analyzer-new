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
    top: -100px; right: -100px;
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(255,255,255,0.18) 0%, transparent 70%);
    border-radius: 50%;
}
.hero-content { position: relative; z-index: 2; display: flex; align-items: center; gap: 2rem; flex-wrap: wrap; }
.hero-text { flex: 1; min-width: 280px; }
.hero-text h1 { font-size: 2.5rem; font-weight: 800; margin: 0 0 0.6rem 0; letter-spacing: -1px; }
.hero-text p { font-size: 1.1rem; margin: 0; opacity: 0.95; }
.hero-chips { display: flex; gap: 0.5rem; margin-top: 1.2rem; flex-wrap: wrap; }
.chip {
    background: rgba(255,255,255,0.2);
    border: 1px solid rgba(255,255,255,0.3);
    padding: 0.35rem 0.85rem;
    border-radius: 999px;
    font-size: 0.85rem;
    font-weight: 500;
    backdrop-filter: blur(8px);
}
.hero-illustration { position: relative; z-index: 2; }
.stButton > button {
    background: linear-gradient(135deg, #5D9968 0%, #7BAE7F 100%);
    color: #FFFFFF;
    border: none;
    border-radius: 14px;
    padding: 0.75rem 1.6rem;
    font-weight: 600;
    font-size: 1rem;
    transition: all 0.25s;
    box-shadow: 0 6px 16px rgba(93, 153, 104, 0.28);
}
.stButton > button:hover {
    background: linear-gradient(135deg, #4A8055 0%, #5D9968 100%);
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
}
.stDownloadButton > button:hover {
    background: linear-gradient(135deg, #7BAE7F 0%, #5D9968 100%);
    transform: translateY(-2px);
    color: #FFFFFF;
}
.stFileUploader {
    background: #FFFFFF;
    border-radius: 20px;
    padding: 1.2rem;
    border: 2px dashed var(--border);
    box-shadow: 0 4px 20px rgba(46, 59, 50, 0.04);
}
.stFileUploader:hover { border-color: var(--mint-light); }
.stFileUploader section { border: none !important; background: transparent !important; }
.stFileUploader button {
    background: #E8F5E9 !important;
    color: var(--ink) !important;
    border: 1px solid var(--mint-light) !important;
    border-radius: 10px !important;
}
.stFileUploader button:hover { background: var(--mint-light) !important; color: #FFFFFF !important; }
.stMetric {
    background: #FFFFFF;
    border-radius: 20px;
    padding: 1.5rem 1.6rem;
    border: 1px solid #E8F2E4;
    box-shadow: 0 6px 22px rgba(46, 59, 50, 0.06);
    position: relative;
    overflow: hidden;
}
.stMetric::before {
    content: '';
    position: absolute;
    top: 0; left: 0; height: 100%; width: 6px;
    background: linear-gradient(180deg, #5D9968 0%, #A8D5BA 100%);
}
.stMetric:hover { transform: translateY(-4px); box-shadow: 0 14px 32px rgba(93, 153, 104, 0.18); }
.stMetric label { color: var(--ink-soft) !important; font-size: 0.9rem !important; text-transform: uppercase; }
.stMetric [data-testid="stMetricValue"] { color: var(--ink) !important; font-weight: 700 !important; font-size: 1.7rem !important; }
.stDataFrame { border-radius: 20px; overflow: hidden; box-shadow: 0 8px 28px rgba(46, 59, 50, 0.08); background: #FFFFFF; }
.stAlert { border-radius: 14px; border: none; }
div[data-baseweb="notification"][kind="positive"] { background: #E8F5E9; color: var(--ink); }
div[data-baseweb="notification"][kind="info"]     { background: #EEF4EA; color: var(--ink); }
div[data-baseweb="notification"][kind="warning"]  { background: #FBF3E0; color: #7A5B10; }
.stProgress > div > div > div { background: linear-gradient(90deg, #5D9968 0%, #A8D5BA 100%); border-radius: 8px; }
h3 {
    color: var(--ink);
    font-weight: 700;
    padding-bottom: 0.6rem;
    border-bottom: 2px solid #E8F2E4;
    margin-top: 2rem;
    margin-bottom: 1.2rem;
    font-size: 1.25rem;
}
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: #FAF8F3; }
::-webkit-scrollbar-thumb { background: #C8DECC; border-radius: 5px; }
hr { border: none; border-top: 1px solid #E8F2E4; margin: 2rem 0; }
.info-card {
    background: #FFFFFF;
    border-radius: 18px;
    padding: 1.4rem 1.5rem;
    border: 1px solid #E8F2E4;
    display: flex;
    align-items: center;
    gap: 1.2rem;
    box-shadow: 0 4px 16px rgba(46, 59, 50, 0.05);
}
.info-card-icon {
    flex-shrink: 0; width: 56px; height: 56px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 14px;
    background: linear-gradient(135deg, #E8F5E9 0%, #D5EDDA 100%);
}
.info-card-text h4 { color: var(--ink); margin: 0 0 0.25rem 0; font-size: 1rem; font-weight: 600; }
.info-card-text p { color: var(--ink-muted); margin: 0; font-size: 0.88rem; }
.footer-note { text-align: center; color: var(--ink-muted); font-size: 0.85rem; padding: 1.5rem 0 0.5rem 0; }
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
        <path d="M57 100 L79 80 L101 60 L123 85 L145 50" stroke="#FFFFFF" stroke-width="3" fill="none" stroke-linecap="round"/>
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

def parse_date(date_str: str) -> str:
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
                "%Y%m%d", "%d.%m.%y", "%d/%m/%y", "%d-%b-%Y", "%d-%b-%y"]:
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

def read_xlsx(file_content: bytes, sheet_name=None, header=None):
    """
    Универсальное чтение табличных файлов.
    Пробует openpyxl, xlrd, потом — без указания движка.
    Дополнительно: если это .xls, но на самом деле HTML — читаем через read_html.
    """
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
    # Fallback: HTML под расширением .xls (иногда так отдают Industra / банки).
    try:
        tables = pd.read_html(BytesIO(file_content))
        for t in tables:
            if t is not None and not t.empty:
                return t
    except Exception:
        pass
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
    """
    Пробуем разные кодировки. Приоритет: UTF-8 (с BOM и без), ISO-8859-2 (latin-2, для венгерского),
    CP1250 (чешский/словацкий/венгерский), CP1251 (кириллица), latin-1 (fallback).

    ВАЖНО: проверка \\ufffd полезна только для многобайтных кодировок.
    Для однобайтных (cp1251, cp1250, iso-8859-2) replacement char не появляется,
    поэтому используем эвристику качества текста: доля «печатных» символов.
    Плюс, если эвристика не дала уверенного результата, пробуем chardet.
    """
    encodings = ['utf-8-sig', 'utf-8', 'iso-8859-2', 'cp1250', 'cp1251', 'latin-1']
    best_text = ''
    best_enc = None
    best_score = -1.0

    for enc in encodings:
        try:
            content = file_content.decode(enc)
        except Exception:
            continue

        score = _text_quality_score(content)
        if score > best_score:
            best_score = score
            best_text = content
            best_enc = enc

    if best_score < 0.5:
        try:
            detected = chardet.detect(file_content[:8192])
            det_enc = (detected.get('encoding') or '').lower()
            if det_enc:
                try:
                    candidate = file_content.decode(det_enc)
                    cand_score = _text_quality_score(candidate)
                    if cand_score > best_score:
                        best_text = candidate
                        best_enc = det_enc
                        best_score = cand_score
                except Exception:
                    pass
        except Exception:
            pass

    if best_enc is None:
        try:
            best_text = file_content.decode('latin-1')
            best_enc = 'latin-1'
        except Exception:
            return ''

    if best_text.startswith('\ufeff'):
        best_text = best_text[1:]
    return best_text


def _text_quality_score(text: str) -> float:
    if not text:
        return 0.0
    sample = text[:5000]
    total = len(sample)
    good = 0.0
    bad = 0.0
    for ch in sample:
        o = ord(ch)
        if ch.isalnum() or ch in " \t\r\n.,;:!?()[]{}\"'+-*/\\|@#$%^&*_=<>~`«»—–№°":
            good += 1
        elif o < 0x20 and ch not in "\t\r\n":
            bad += 2
        elif o == 0xFFFD:
            bad += 3
        elif 0x80 <= o <= 0x9F:
            bad += 2
        else:
            good += 0.5
    return (good - bad) / max(total, 1)


def _is_real_xls(file_content: bytes) -> bool:
    return file_content[:4] == b'\xd0\xcf\x11\xe0'

def _is_real_xlsx(file_content: bytes) -> bool:
    return file_content[:2] == b'PK'

def _split_line(line: str, sep: str) -> List[str]:
    """
    Разбивает строку CSV с учётом кавычек.
    Поддерживает экранированные кавычки "" внутри поля в кавычках.
    """
    parts: List[str] = []
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


def _looks_like_date_cell(s: str) -> bool:
    if not s:
        return False
    return bool(re.match(r'^\d{2}\.\d{2}\.\d{4}\s*$', s.strip()))


def _looks_like_amount_cell(s: str) -> bool:
    if not s:
        return False
    s2 = s.strip()
    s2 = re.sub(r'\s*(RUR|RUB|USD|EUR|GBP|CZK|HUF|AZN|AED|₽|\$|€|£)\s*$', '', s2)
    return bool(re.match(r'^-?\d[\d\s\u00a0]*[.,]\d{2}$', s2))


# ==================== CSOB ====================

def parse_csob_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """
    CSOB «Account Statement» CSV.
    Колонки (0-based): ... parts[4] — дата, parts[6] — сумма.
    Раньше был split(';') — заменено на _split_line.
    """
    transactions = []
    content = read_text_with_encoding(file_content)
    content = content.replace('\ufeff', '')
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
        parts = _split_line(line, ';')
        while parts and parts[-1] == '':
            parts.pop()
        # Терпимость: если частей 6, тоже пробуем (раньше было < 7 -> skip).
        if len(parts) < 6:
            continue
        try:
            date = parse_date(safe_str(parts[4])) if len(parts) > 4 else ''
            if not date:
                continue
            amount_str = safe_str(parts[6]) if len(parts) > 6 else ''
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
            if amount == 0.0:
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
                transactions.append({
                    'Дата': parse_date(str(current_date)),
                    'Сумма': parse_amount(str(current_amount)),
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
        transactions.append({
            'Дата': parse_date(str(current_date)),
            'Сумма': parse_amount(str(current_amount)),
            'Контрагент': '',
            'Наименование счета': account_name,
            'Описание': (current_desc or '')[:500]
        })
    return transactions


def _regina_strip_currency(s: str) -> Tuple[str, Optional[str]]:
    if not s:
        return '', None
    m = re.search(r'\s*(RUR|RUB|USD|EUR|GBP|₽|\$|€)\s*$', s)
    if m:
        return s[:m.start()].strip(), m.group(1)
    return s.strip(), None


def _regina_is_amount(s: str) -> bool:
    if not s:
        return False
    s2 = s.strip()
    s2 = re.sub(r'\s*(RUR|RUB|USD|EUR|GBP|₽|\$|€)\s*$', '', s2)
    return bool(re.search(r'-?\s*\d[\d\s]*[.,]\d{2}\s*$', s2))


def _regina_extract_row_from_line(line: str) -> Optional[Tuple[str, str, str, float]]:
    if not line:
        return None
    line = re.sub(r'^\s*(?:RUR|RUB)\s+', '', line)

    m = re.match(
        r'^[ \t]*(\d{2}\.\d{2}\.\d{4})[ \t]+([A-Z0-9_]+)[ \t]+(.+?)[ \t]+'
        r'(-?[\d \t\u00a0]*[.,]\d{2})'
        r'(?:[ \t]+(RUR|RUB|USD|EUR|₽|\$|€))?[ \t]*$',
        line,
    )
    if m:
        return (
            m.group(1).strip(),
            m.group(2).strip(),
            re.sub(r'\s+', ' ', m.group(3)).strip(),
            parse_amount(m.group(4)),
        )

    m = re.match(
        r'^[ \t]*(\d{2}\.\d{2}\.\d{4})[ \t]+'
        r'(-?[\d \t\u00a0]*[.,]\d{2})'
        r'(?:[ \t]+(RUR|RUB|USD|EUR|₽|\$|€))?[ \t]+(.+?)[ \t]*$',
        line,
    )
    if m:
        return (
            m.group(1).strip(),
            '',
            re.sub(r'\s+', ' ', m.group(4)).strip(),
            parse_amount(m.group(2)),
        )

    return None


def _regina_parse_docx_tables(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Разбор Regina Alfa через таблицы DOCX.
    Таблица операций: Дата проводки | Код операции | Описание | Сумма в валюте счета.
    Описание может занимать несколько строк.
    """
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []

    result: List[Dict] = []

    for table in doc.tables:
        if not table.rows:
            continue
        header_row_idx = -1
        for ri, row in enumerate(table.rows[:5]):
            cells = [c.text.strip().lower() for c in row.cells]
            joined = ' | '.join(cells)
            if 'дата' in joined and ('описан' in joined or 'сумм' in joined):
                header_row_idx = ri
                break
        if header_row_idx == -1:
            continue

        hdr_cells = [c.text.strip().lower() for c in table.rows[header_row_idx].cells]
        date_idx = code_idx = desc_idx = amount_idx = -1
        for i, h in enumerate(hdr_cells):
            h_clean = h.replace('\n', ' ')
            if 'дата' in h_clean and date_idx == -1:
                date_idx = i
            elif 'код' in h_clean and code_idx == -1:
                code_idx = i
            elif 'описан' in h_clean and desc_idx == -1:
                desc_idx = i
            elif 'сумм' in h_clean and amount_idx == -1:
                amount_idx = i

        if date_idx == -1 or amount_idx == -1:
            continue

        current_date = ''
        current_code = ''
        current_desc_parts: List[str] = []
        current_amount = None

        def _flush():
            nonlocal current_date, current_code, current_desc_parts, current_amount
            if current_date and current_amount is not None and current_amount != 0.0:
                desc = ' '.join(p for p in current_desc_parts if p)
                desc = re.sub(r'\s+', ' ', desc).strip()
                prefix = f"{current_code} " if current_code else ''
                result.append({
                    'Дата': parse_date(current_date),
                    'Сумма': current_amount,
                    'Контрагент': '',
                    'Наименование счета': account_name,
                    'Описание': (prefix + desc)[:500]
                })
            current_date = ''
            current_code = ''
            current_desc_parts = []
            current_amount = None

        for row in table.rows[header_row_idx + 1:]:
            cells = [c.text.strip() for c in row.cells]

            date_cell = cells[date_idx] if date_idx < len(cells) else ''
            code_cell = cells[code_idx] if code_idx >= 0 and code_idx < len(cells) else ''
            desc_cell = cells[desc_idx] if desc_idx >= 0 and desc_idx < len(cells) else ''
            amount_cell = cells[amount_idx] if amount_idx < len(cells) else ''

            date_clean = date_cell.replace('\n', ' ').strip()
            desc_clean = desc_cell.replace('\n', ' ').strip()
            amount_clean = amount_cell.replace('\n', ' ').strip()

            is_new_row = bool(re.match(r'^\d{2}\.\d{2}\.\d{4}\s*$', date_clean))

            amount_val = None
            if _regina_is_amount(amount_clean):
                amount_val = parse_amount(amount_clean)

            if is_new_row:
                _flush()
                current_date = date_clean
                current_code = code_cell.strip()
                if desc_clean:
                    current_desc_parts.append(desc_clean)
                if amount_val is not None:
                    current_amount = amount_val
            else:
                if not current_date:
                    continue
                if code_cell.strip() and not current_code:
                    current_code = code_cell.strip()
                if desc_clean:
                    current_desc_parts.append(desc_clean)
                if amount_val is not None and current_amount is None:
                    current_amount = amount_val

        _flush()

    return result


def parse_regina_alfa_docx(file_content: bytes, account_name: str) -> List[Dict]:
    table_result = _regina_parse_docx_tables(file_content, account_name)
    if table_result:
        return table_result

    full_text = docx_all_text(file_content)
    if not full_text:
        return []
    result: List[Dict] = []
    for raw_line in full_text.splitlines():
        parsed = _regina_extract_row_from_line(raw_line)
        if parsed is None:
            continue
        date_str, code, desc, amount = parsed
        date = parse_date(date_str)
        if not date or amount == 0.0:
            continue
        result.append({
            'Дата': date, 'Сумма': amount,
            'Контрагент': '', 'Наименование счета': account_name,
            'Описание': (f"{code} {desc}".strip())[:500]
        })
    return result


def parse_regina_alfa_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    result: List[Dict] = []

    for table in pdf_all_tables(file_content):
        if not table:
            continue
        header_idx = -1
        for i, row in enumerate(table[:5]):
            joined = ' '.join((c or '').lower() for c in row)
            if 'дата' in joined and ('сумм' in joined or 'описан' in joined):
                header_idx = i
                break
        if header_idx == -1:
            continue
        hdr = [(c or '').lower() for c in table[header_idx]]
        date_i = code_i = desc_i = amount_i = -1
        for i, h in enumerate(hdr):
            if 'дата' in h and date_i == -1:
                date_i = i
            elif 'код' in h and code_i == -1:
                code_i = i
            elif 'описан' in h and desc_i == -1:
                desc_i = i
            elif 'сумм' in h and amount_i == -1:
                amount_i = i
        if date_i == -1 or amount_i == -1:
            continue

        current_date = ''
        current_code = ''
        current_desc_parts: List[str] = []
        current_amount = None

        def _flush():
            nonlocal current_date, current_code, current_desc_parts, current_amount
            if current_date and current_amount is not None and current_amount != 0.0:
                desc = re.sub(r'\s+', ' ', ' '.join(current_desc_parts)).strip()
                prefix = f"{current_code} " if current_code else ''
                result.append({
                    'Дата': parse_date(current_date),
                    'Сумма': current_amount,
                    'Контрагент': '',
                    'Наименование счета': account_name,
                    'Описание': (prefix + desc)[:500]
                })
            current_date = ''
            current_code = ''
            current_desc_parts = []
            current_amount = None

        for row in table[header_idx + 1:]:
            row = [(c or '').strip() for c in row]
            date_cell = row[date_i] if date_i < len(row) else ''
            code_cell = row[code_i] if code_i >= 0 and code_i < len(row) else ''
            desc_cell = row[desc_i] if desc_i >= 0 and desc_i < len(row) else ''
            amount_cell = row[amount_i] if amount_i < len(row) else ''

            date_clean = date_cell.replace('\n', ' ').strip()
            desc_clean = desc_cell.replace('\n', ' ').strip()
            amount_clean = amount_cell.replace('\n', ' ').strip()

            is_new_row = bool(re.match(r'^\d{2}\.\d{2}\.\d{4}\s*$', date_clean))
            amount_val = parse_amount(amount_clean) if _regina_is_amount(amount_clean) else None

            if is_new_row:
                _flush()
                current_date = date_clean
                current_code = code_cell.strip()
                if desc_clean:
                    current_desc_parts.append(desc_clean)
                if amount_val is not None:
                    current_amount = amount_val
            else:
                if not current_date:
                    continue
                if code_cell.strip() and not current_code:
                    current_code = code_cell.strip()
                if desc_clean:
                    current_desc_parts.append(desc_clean)
                if amount_val is not None and current_amount is None:
                    current_amount = amount_val

        _flush()

    if result:
        return result

    full_text = pdf_all_text(file_content)
    if not full_text:
        return []
    for raw_line in full_text.splitlines():
        parsed = _regina_extract_row_from_line(raw_line)
        if parsed is None:
            continue
        date_str, code, desc, amount = parsed
        date = parse_date(date_str)
        if not date or amount == 0.0:
            continue
        result.append({
            'Дата': date, 'Сумма': amount,
            'Контрагент': '', 'Наименование счета': account_name,
            'Описание': (f"{code} {desc}".strip())[:500]
        })
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
            if amount == 0.0:
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


def _parse_tinkoff_tabular(rows: List[List[str]], account_name: str) -> List[Dict]:
    result: List[Dict] = []
    if not rows:
        return result

    hdr = [str(c).strip() if c is not None else '' for c in rows[0]]
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

    for cells in rows[1:]:
        cells = [str(c).strip() if c is not None else '' for c in cells]
        if len(cells) < 3:
            continue
        try:
            m = re.match(r'(\d{2}\.\d{2}\.\d{4})', cells[date_idx] if date_idx < len(cells) else '')
            if not m:
                continue
            date = parse_date(m.group(1))
            amount = parse_amount(cells[amount_idx] if amount_idx < len(cells) else '')
            if amount == 0.0:
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


def parse_tinkoff_xlsx(file_content: bytes, account_name: str) -> List[Dict]:
    df = read_xlsx(file_content, sheet_name=None, header=None)
    if df is None or df.empty:
        try:
            xls = pd.ExcelFile(BytesIO(file_content))
            for sh in xls.sheet_names:
                candidate = read_xlsx(file_content, sheet_name=sh, header=None)
                if candidate is not None and not candidate.empty:
                    df = candidate
                    break
        except Exception:
            df = None
    if df is None or df.empty:
        return []

    header_row = -1
    for idx, row in df.iterrows():
        if idx > 50:
            break
        rs = ' '.join(str(x) for x in row.values if pd.notna(x))
        if 'Дата и время операции' in rs and 'Сумма' in rs:
            header_row = idx
            break
    if header_row == -1:
        return []

    rows: List[List[str]] = []
    for i in range(header_row, len(df)):
        row = df.iloc[i].tolist()
        rows.append(['' if pd.isna(c) else str(c) for c in row])
    return _parse_tinkoff_tabular(rows, account_name)


def parse_tinkoff_csv(file_content: bytes, account_name: str) -> List[Dict]:
    content = read_text_with_encoding(file_content)
    lines = [l.rstrip('\r') for l in content.split('\n') if l.strip()]
    if not lines:
        return []

    header_idx = -1
    for i, l in enumerate(lines[:60]):
        low = l.lower()
        if 'дата и время операции' in low and 'сумма' in low:
            header_idx = i
            break
    if header_idx == -1:
        return []

    first = lines[header_idx]
    sep = ',' if first.count(',') >= first.count(';') else ';'
    rows: List[List[str]] = []
    for l in lines[header_idx:]:
        rows.append(_split_line(l, sep))
    return _parse_tinkoff_tabular(rows, account_name)


def parse_tinkoff_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []
    result = []
    pattern = re.compile(
        r'(\d{2}\.\d{2}\.\d{4})[ \t]+\d{2}:\d{2}[ \t]+'
        r'(\d{2}\.\d{2}\.\d{4})[ \t]+\d{2}:\d{2}[ \t]+'
        r'([+\-]?[\d \t\u00a0]+[.,]\d{2})[ \t]*[₽PР][ \t]*'
        r'([+\-]?[\d \t\u00a0]+[.,]\d{2})[ \t]*[₽PР][ \t]*'
        r'([^\n]{2,300}?)(?:[ \t]+7596|[ \t]+—|\n|$)',
        re.MULTILINE
    )
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(1))
            amount = parse_amount(m.group(3))
            desc = re.sub(r'\s+', ' ', m.group(5)).strip()
            if not date or amount == 0.0:
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

def _parse_bluor_csv(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    content = read_text_with_encoding(file_content)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if not lines:
        return []
    first_line = lines[0]
    sep = ';' if first_line.count(';') > first_line.count(',') else ','
    skip_words = ['начальный остаток', 'конечный остаток', 'starting balance', 'ending balance',
                  'total', 'дебет (d)', 'кредит (c)', 'debit (d)', 'credit (c)',
                  'account number', 'balance', 'saldo', 'выписка', 'statement',
                  'iban', 'currency', 'date', 'amount']
    for line in lines:
        parts = _split_line(line, sep)
        if len(parts) < 4:
            continue
        try:
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
            if amount == 0.0:
                continue
            desc = ''
            for i in [3, 2, 1]:
                if i < len(parts) and i not in (date_idx, amount_idx):
                    v = parts[i].strip()
                    if v and v != 'nan' and not re.match(r'^\d{2}\.\d{2}\.\d{4}$', v):
                        desc = v
                        break
            low = desc.lower()
            if any(w in low for w in skip_words):
                continue
            ttype = ''
            for i in [6, 7, 8]:
                if i < len(parts):
                    v = parts[i].strip().upper()
                    if v in ('D', 'C'):
                        ttype = v
                        break
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
            if not date or amount == 0.0:
                continue
            low = desc.lower()
            if any(w in low for w in ['starting balance', 'ending balance', 'total']):
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
        parts = _split_line(line, ';')
        if len(parts) < 3:
            continue
        try:
            date = parse_date(parts[0])
            if not date:
                continue
            amount = parse_amount(parts[1])
            if amount == 0.0:
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


def _jenhor_should_skip(desc: str) -> bool:
    if not desc:
        return False
    low = desc.lower()
    return any(w in low for w in [
        'počáteční zůstatek', 'konečný zůstatek',
        'celkem připsáno', 'celkem odepsáno',
        'přehled pohyb', 'shrnuti pohyb', 'obraty za',
        'výpis z účtu', 'vypis z uctu', 'account statement',
    ])


def _jenhor_parse_docx_tables(file_content: bytes, account_name: str) -> List[Dict]:
    """
    JenHor Unelma DOCX — табличный разбор.
    Сначала пробуем найти заголовок с 'Datum' / 'Částka'.
    Если заголовка нет — идём по значениям: дата dd.mm.yyyy + сумма.
    """
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []

    result: List[Dict] = []

    for table in doc.tables:
        if not table.rows:
            continue

        header_row_idx = -1
        for ri, row in enumerate(table.rows[:6]):
            cells = [c.text.strip().lower() for c in row.cells]
            joined = ' | '.join(cells)
            if ('datum' in joined or 'date' in joined) and (
                'částka' in joined or 'castka' in joined or 'amount' in joined or 'objem' in joined
            ):
                header_row_idx = ri
                break

        if header_row_idx != -1:
            hdr = [c.text.strip().lower() for c in table.rows[header_row_idx].cells]
            date_idx = -1
            amount_idx = -1
            desc_idx = -1
            for i, h in enumerate(hdr):
                if ('datum' in h or 'date' in h) and date_idx == -1:
                    date_idx = i
                elif ('částka' in h or 'castka' in h or 'amount' in h or 'objem' in h) and amount_idx == -1:
                    amount_idx = i
                elif ('popis' in h or 'description' in h or 'zpráva' in h or 'zprava' in h
                      or 'poznámka' in h or 'poznamka' in h or 'protiúčet' in h or 'protiucet' in h) and desc_idx == -1:
                    desc_idx = i
            if date_idx != -1 and amount_idx != -1:
                for row in table.rows[header_row_idx + 1:]:
                    cells = [c.text.strip() for c in row.cells]
                    if len(cells) <= max(date_idx, amount_idx):
                        continue
                    d = parse_date(cells[date_idx])
                    if not d:
                        continue
                    a = parse_amount(cells[amount_idx])
                    if a == 0.0:
                        continue
                    desc = cells[desc_idx] if desc_idx >= 0 and desc_idx < len(cells) else ''
                    desc = re.sub(r'\s+', ' ', desc).strip()
                    if _jenhor_should_skip(desc):
                        continue
                    result.append({
                        'Дата': d, 'Сумма': a,
                        'Контрагент': 'Česká spořitelna',
                        'Наименование счета': account_name,
                        'Описание': desc[:500]
                    })
                continue

        # Fallback: по значениям в ячейках.
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if not cells:
                continue
            date_found = None
            amount_found = None
            desc_parts: List[str] = []
            for c in cells:
                if _looks_like_date_cell(c):
                    if date_found is None:
                        date_found = parse_date(c)
                        continue
                if _looks_like_amount_cell(c):
                    if amount_found is None:
                        amount_found = parse_amount(c)
                        continue
                if c and not re.match(r'^[\d\s.,\-]+$', c):
                    desc_parts.append(c)
            if date_found and amount_found is not None and amount_found != 0.0:
                desc = ' '.join(desc_parts)
                desc = re.sub(r'\s+', ' ', desc).strip()
                if _jenhor_should_skip(desc):
                    continue
                result.append({
                    'Дата': date_found, 'Сумма': amount_found,
                    'Контрагент': 'Česká spořitelna',
                    'Наименование счета': account_name,
                    'Описание': desc[:500]
                })

    return result


def parse_jenhor_unelma_docx(file_content: bytes, account_name: str) -> List[Dict]:
    """
    JenHor Unelma DOCX.
    Основной путь — таблицы. Fallback — regex по тексту.
    """
    table_result = _jenhor_parse_docx_tables(file_content, account_name)
    if table_result:
        return table_result

    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []

    result: List[Dict] = []

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
        r'(\d{2}\.\d{2}\.\d{4})\s+(.+?)\s+(-?\d[\d\s]*[,.]\d{2})(?!\d)',
        re.DOTALL
    )
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(1).strip())
            desc = re.sub(r'\s+', ' ', m.group(2)).strip()
            amount = parse_amount(m.group(3).strip())
            if not date or amount == 0.0:
                continue
            if _jenhor_should_skip(desc):
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
            if not date or amount == 0.0:
                continue
            if _jenhor_should_skip(desc):
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
    """
    FIO CSV.
    Заголовок: Date | Volume | ... | Note ...
    Ищем по 'date'/'datum' и 'volume'/'objem'/'částka'.
    """
    result = []
    content = read_text_with_encoding(file_content)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if len(lines) < 2:
        return []
    header = -1
    for i, l in enumerate(lines):
        low = l.lower()
        if (
            ('date' in low and ('volume' in low or 'objem' in low or 'částka' in low or 'castka' in low))
            or ('datum' in low and ('volume' in low or 'objem' in low or 'částka' in low or 'castka' in low))
        ):
            header = i
            break
    if header == -1:
        return []

    # Определяем разделитель.
    sep = ';' if lines[header].count(';') >= lines[header].count(',') else ','
    hdr_parts = _split_line(lines[header], sep)

    # Ищем индексы колонок: сумма, описание, контрагент.
    amount_idx = -1
    desc_idx = -1
    cp_idx = -1
    for i, h in enumerate(hdr_parts):
        hl = h.lower().strip('"').strip()
        if hl in ('volume', 'objem', 'částka', 'castka', 'amount') and amount_idx == -1:
            amount_idx = i
        elif hl in ('note', 'poznámka', 'poznamka', 'zpráva', 'zprava', 'description', 'message') and desc_idx == -1:
            desc_idx = i
        elif hl in ('counterparty', 'protiúčet', 'protiucet', 'account name') and cp_idx == -1:
            cp_idx = i
    if amount_idx == -1:
        amount_idx = 1
    if desc_idx == -1:
        desc_idx = 5

    for line in lines[header + 1:]:
        parts = _split_line(line, sep)
        if len(parts) < 3:
            continue
        try:
            date = parse_date(parts[0])
            if not date:
                continue
            amount = parse_amount(parts[amount_idx] if amount_idx < len(parts) else '')
            if amount == 0.0:
                continue
            desc = parts[desc_idx] if 0 <= desc_idx < len(parts) else ''
            cp = parts[cp_idx] if 0 <= cp_idx < len(parts) else ''
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp[:200], 'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return result

# ==================== Industra ====================

def _parse_industra_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Industra .xls/.xlsx.
    Заголовок содержит 'Дата транзакции' / 'Дебет' / 'Кредит'.
    Если pandas не смог прочитать .xls (например, HTML внутри .xls) —
    read_xlsx уже пробует read_html.
    """
    result = []
    df = read_xlsx(file_content)
    if df is None or df.empty:
        return []
    header_row = -1
    for idx, row in df.iterrows():
        if idx < 60:
            rs = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Дата транзакции' in rs and 'Дебет' in rs and 'Кредит' in rs:
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
        if 'Дата транзакции' in s:
            ci['date'] = i
        elif 'Получатель' in s or 'Плательщик' in s:
            ci['counterparty'] = i
        elif 'Информация о транзакции' in s:
            ci['description'] = i
        elif 'Дебет' in s and 'Кредит' not in s:
            ci['debit'] = i
        elif 'Кредит' in s and 'Дебет' not in s:
            ci['credit'] = i
    if 'date' not in ci:
        ci['date'] = 0
    if 'debit' not in ci:
        ci['debit'] = 11
    if 'credit' not in ci:
        ci['credit'] = 12
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
            if not found:
                continue
            cp = safe_str(row.iloc[ci['counterparty']]) if 'counterparty' in ci and ci['counterparty'] < len(row) else ''
            desc = safe_str(row.iloc[ci['description']]) if 'description' in ci and ci['description'] < len(row) else ''
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp[:200], 'Наименование счета': account_name,
                'Описание': desc[:500]
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
            elif 'Дебет' in h and 'Кредит' not in h:
                ci['debit'] = i
            elif 'Кредит' in h and 'Дебет' not in h:
                ci['credit'] = i
        for row in table[header_idx + 1:]:
            try:
                dstr = row[ci.get('date', 0)] if ci.get('date', 0) < len(row) else ''
                date = parse_date(dstr)
                if not date:
                    continue
                amount = 0.0
                found = False
                if 'debit' in ci and ci['debit'] < len(row):
                    p = parse_amount(row[ci['debit']].replace(',', '.').replace(' ', ''))
                    if p != 0.0:
                        amount = -abs(p)
                        found = True
                if not found and 'credit' in ci and ci['credit'] < len(row):
                    p = parse_amount(row[ci['credit']].replace(',', '.').replace(' ', ''))
                    if p != 0.0:
                        amount = p
                        found = True
                if not found:
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
    return result

# ==================== Kapital bank Saida AZN ====================

def parse_kapital_saida_azn_csv(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    content = read_text_with_encoding(file_content)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    for line in lines:
        parts = _split_line(line, ';')
        if len(parts) < 3:
            continue
        try:
            date = parse_date(parts[0])
            if not date:
                continue
            amount = parse_amount(parts[2].replace(',', '.'))
            if amount == 0.0:
                continue
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': '', 'Наименование счета': account_name,
                'Описание': parts[1][:500] if len(parts) > 1 else ''
            })
        except Exception:
            continue
    return result


def _kapital_is_skip_desc(desc: str) -> bool:
    if not desc:
        return False
    low = desc.lower()
    return any(w in low for w in [
        'balance', 'saldo', 'start', 'end', 'period',
        'лимит', 'баланс', 'период', 'available', 'кредитн',
        'входящий остаток', 'исходящий остаток', 'текущий баланс',
        'платежный лимит', 'задолженность', 'на дату формирования',
        'общая задолженность',
    ])


def parse_kapital_saida_docx(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Kapital Bank / Saida DOCX.
    Основной путь — таблицы. Fallback — regex по абзацам.
    Жёсткие фильтры: не путать реквизиты и остатки с операциями.
    """
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []

    result: List[Dict] = []

    for table in doc.tables:
        if not table.rows:
            continue
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if not cells:
                continue
            joined_low = ' '.join(cells).lower()
            # Пропускаем строки со служебными словами.
            if _kapital_is_skip_desc(joined_low):
                continue
            date_found = None
            amount_found = None
            desc_parts: List[str] = []
            has_letters = False
            for c in cells:
                c_clean = c.replace('\n', ' ').strip()
                if not c_clean:
                    continue
                d = parse_date(c_clean)
                if d and re.match(r'^\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4}$', c_clean):
                    if date_found is None:
                        date_found = d
                        continue
                if _looks_like_amount_cell(c_clean):
                    if amount_found is None:
                        amount_found = parse_amount(c_clean)
                        continue
                if c_clean and not re.match(r'^[\d\s.,\-/]+$', c_clean):
                    has_letters = True
                    desc_parts.append(c_clean)
            if date_found and amount_found is not None and amount_found != 0.0 and has_letters:
                desc = ' '.join(desc_parts)
                desc = re.sub(r'\s+', ' ', desc).strip()
                if _kapital_is_skip_desc(desc):
                    continue
                result.append({
                    'Дата': date_found, 'Сумма': -abs(amount_found),
                    'Контрагент': 'Kapital Bank',
                    'Наименование счета': account_name,
                    'Описание': desc[:500]
                })

    if result:
        return result

    # Fallback — regex по абзацам.
    lines = []
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            lines.append(t)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                t = cell.text.strip()
                if t:
                    lines.append(t)

    pattern = re.compile(
        r'(\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4})[ \t]+'
        r'([\d \t\u00a0]+[.,]\d{1,2})[ \t]+'
        r'([\d \t\u00a0]+[.,]\d{1,2})[ \t]+'
        r'([\d \t\u00a0]+[.,]\d{1,2})[ \t]+'
        r'([A-Za-z][A-Za-z0-9 \t\-\./]{2,120})',
        re.MULTILINE
    )
    for line in lines:
        for m in pattern.finditer(line):
            try:
                date = parse_date(m.group(1).strip())
                amount = parse_amount(m.group(2).strip())
                desc = m.group(5).strip()
                if not date or amount == 0.0:
                    continue
                if _kapital_is_skip_desc(desc):
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
                if not date or amount == 0.0:
                    continue
                if _kapital_is_skip_desc(desc or ''):
                    continue
                result.append({
                    'Дата': date, 'Сумма': -abs(amount),
                    'Контрагент': 'Kapital Bank',
                    'Наименование счета': account_name,
                    'Описание': desc[:500]
                })
            except Exception:
                continue
    if not result:
        full_text = pdf_all_text(file_content)
        pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4})[ \t]+'
            r'([\d \t\u00a0]+[.,]\d{1,2})[ \t]+'
            r'([\d \t\u00a0]+[.,]\d{1,2})[ \t]+'
            r'([\d \t\u00a0]+[.,]\d{1,2})[ \t]+'
            r'([A-Za-z][A-Za-z0-9 \t\-\./]{2,80})',
            re.MULTILINE
        )
        for m in pattern.finditer(full_text):
            try:
                date = parse_date(m.group(1).strip())
                amount = parse_amount(m.group(2).strip())
                desc = m.group(5).strip()
                if not date or amount == 0.0:
                    continue
                if _kapital_is_skip_desc(desc):
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
            if not found:
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

# ==================== MKB (Budapest) — ЕДИНЫЙ ПАРСЕР ====================

MKB_HEADER_MARKERS_PRIMARY = ('sorsz', 'rt', 'knap')
MKB_HEADER_MARKERS_ALT = ('értéknap', 'ertekna', 'rtéknap', 'erteknap')


def _mkb_is_header_line(low: str) -> bool:
    """Есть ли в строке маркеры MKB-заголовка (с диакритикой и без)."""
    if 'sorsz' in low and ('rt' in low or 'rte' in low) and ('knap' in low or 'kna' in low):
        return True
    if ('érteknap' in low or 'erteknap' in low or 'értéknap' in low) and ('sszeg' in low or 'összeg' in low):
        return True
    return False


def _parse_mkb_any(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Универсальный парсер MKB: CSV, XLS, XLSX.
    Заголовок содержит 'Sorszám' и 'Értéknap' (с диакритикой или без).
    Если .xls не читается pandas — падаем в CSV-путь с восстановлением кодировки.
    """
    result = []
    df = None

    if _is_real_xls(file_content):
        for engine in ('xlrd', 'openpyxl', None):
            try:
                kw = {'header': None}
                if engine:
                    kw['engine'] = engine
                df = pd.read_excel(BytesIO(file_content), **kw)
                if df is not None and not df.empty:
                    # Проверим, что это похоже на MKB: ищем в первых строках маркеры.
                    head_str = ' '.join(str(x) for x in df.head(5).values.flatten() if pd.notna(x))
                    head_low = head_str.lower()
                    if _mkb_is_header_line(head_low):
                        break
                    # Если это явно не MKB-таблица — сбрасываем и пробуем дальше.
                    df = None
            except Exception:
                df = None
    elif _is_real_xlsx(file_content):
        for engine in ('openpyxl', None):
            try:
                kw = {'header': None}
                if engine:
                    kw['engine'] = engine
                df = pd.read_excel(BytesIO(file_content), **kw)
                if df is not None and not df.empty:
                    break
            except Exception:
                df = None

    # CSV-путь (в т. ч. fallback после .xls).
    if df is None or df.empty:
        content = read_text_with_encoding(file_content)
        content = content.replace('\ufeff', '')
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        if not lines:
            return []
        sample = '\n'.join(lines[:8])
        sep = ';' if sample.count(';') >= sample.count(',') else ','
        header_line_idx = -1
        for i, l in enumerate(lines):
            low = l.lower()
            if _mkb_is_header_line(low):
                header_line_idx = i
                break
        if header_line_idx == -1:
            return []
        hdr = _split_line(lines[header_line_idx], sep)
        if len(hdr) < 5:
            return []

        def find_col(patterns):
            for i, h in enumerate(hdr):
                hl = h.lower()
                # Нормализуем диакритику для поиска.
                hl_norm = (
                    hl.replace('é', 'e').replace('á', 'a').replace('ö', 'o')
                      .replace('ü', 'u').replace('ű', 'u').replace('ó', 'o')
                      .replace('í', 'i').replace('ő', 'o')
                )
                for p in patterns:
                    if p in hl or p in hl_norm:
                        return i
            return -1

        date_idx = find_col(['értéknap', 'ertekna', 'erteknap', 'rtéknap', 'ertekn', 'rt', 'knap'])
        amount_idx = find_col(['összeg', 'osszeg', 'sszeg'])
        desc_idx = find_col(['közlemény', 'kozlemeny', 'kzlem', 'kozlem'])
        cp_idx = find_col(['kedvezményezett', 'kedvezmenyezett'])
        type_idx = find_col(['tranzakció típusa', 'tranzakcio tipusa', 'tranzakci', 'tipusa'])
        if date_idx == -1 or amount_idx == -1:
            return []
        for line in lines[header_line_idx + 1:]:
            parts = _split_line(line, sep)
            if len(parts) < max(date_idx, amount_idx) + 1:
                continue
            try:
                date = parse_date(parts[date_idx])
                if not date:
                    continue
                amount = parse_amount(parts[amount_idx])
                if amount == 0.0:
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

    # DataFrame-путь.
    header_row = -1
    for idx, row in df.iterrows():
        if idx < 30:
            rs = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if _mkb_is_header_line(rs.lower()):
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
        sl_norm = (
            sl.replace('é', 'e').replace('á', 'a').replace('ö', 'o')
              .replace('ü', 'u').replace('ű', 'u').replace('ó', 'o')
              .replace('í', 'i').replace('ő', 'o')
        )
        if 'értéknap' in sl or 'erteknap' in sl_norm or ('rt' in sl and 'knap' in sl):
            ci['date'] = i
        elif 'összeg' in sl or 'osszeg' in sl_norm or 'sszeg' in sl:
            ci['amount'] = i
        elif 'közlemény' in sl or 'kozlemeny' in sl_norm or 'kzlem' in sl:
            ci['description'] = i
        elif ('kedvezményezett' in sl or 'kedvezmenyezett' in sl_norm) and 'neve' in sl and 'counterparty' not in ci:
            ci['counterparty'] = i
        elif 'tranzakció típusa' in sl or ('tranzakci' in sl_norm and 'típusa' in sl_norm):
            if 'type' not in ci:
                ci['type'] = i
    if 'date' not in ci:
        ci['date'] = 1
    if 'amount' not in ci:
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
            amount = parse_amount(row.iloc[ci['amount']] if ci['amount'] < len(row) else '')
            if amount == 0.0:
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
            if _mkb_is_header_line(joined):
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
                if amount == 0.0:
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

def _n26_should_skip(desc: str) -> bool:
    if not desc:
        return False
    low = desc.lower()
    return any(w in low for w in [
        'saldo previo', 'nuevo saldo', 'transacciones',
        'extracto', 'espacio', 'deseño',
    ])


def _n26_parse_docx_tables(file_content: bytes, account_name: str) -> List[Dict]:
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []
    result: List[Dict] = []
    for table in doc.tables:
        if not table.rows:
            continue
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if not cells:
                continue
            date_found = None
            amount_found = None
            desc_parts: List[str] = []
            for c in cells:
                c_clean = c.replace('\n', ' ').strip()
                if not c_clean:
                    continue
                if _looks_like_date_cell(c_clean):
                    if date_found is None:
                        date_found = parse_date(c_clean)
                        continue
                # N26 суммы обычно в EUR с €.
                if re.match(r'^-?\d[\d\s]*[.,]\d{2}\s*€?$', c_clean):
                    if amount_found is None:
                        amount_found = parse_amount(c_clean)
                        continue
                if c_clean and not re.match(r'^[\d\s.,€\-]+$', c_clean):
                    desc_parts.append(c_clean)
            if date_found and amount_found is not None and amount_found != 0.0:
                desc = ' '.join(desc_parts)
                desc = re.sub(r'\s+', ' ', desc).strip()
                if _n26_should_skip(desc):
                    continue
                result.append({
                    'Дата': date_found, 'Сумма': amount_found,
                    'Контрагент': 'N26', 'Наименование счета': account_name,
                    'Описание': desc[:500]
                })
    return result


def parse_n26_docx(file_content: bytes, account_name: str) -> List[Dict]:
    """
    N26 DOCX.
    Основной путь — таблицы. Fallback — regex по тексту.
    Regex теперь терпимее к формату дат (dd.mm.yyyy и dd.mm.yy) и пробелам перед €.
    """
    table_result = _n26_parse_docx_tables(file_content, account_name)
    if table_result:
        return table_result

    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []

    result: List[Dict] = []

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
        r'([A-Za-z0-9][^\n]{3,160}?)'
        r'(?:Fecha de valor\s+)?'
        r'(\d{2}\.\d{2}\.\d{2,4})'
        r'\s+'
        r'(\d{2}\.\d{2}\.\d{2,4})?'
        r'\s*'
        r'(-?\d[\d\s]*[.,]\d{2})\s*€',
        re.MULTILINE
    )
    for m in pattern.finditer(full_text):
        try:
            desc = re.sub(r'\s+', ' ', m.group(1)).strip()
            date = parse_date(m.group(2))
            amount = parse_amount(m.group(4))
            if not date or amount == 0.0:
                continue
            if _n26_should_skip(desc):
                continue
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
        r'([A-Za-z0-9][^\n]{3,160}?)'
        r'(?:Fecha de valor\s+)?'
        r'(\d{2}\.\d{2}\.\d{2,4})'
        r'\s+'
        r'(\d{2}\.\d{2}\.\d{2,4})?'
        r'\s*'
        r'(-?\d[\d\s]*[.,]\d{2})\s*€',
        re.MULTILINE
    )
    for m in pattern.finditer(full_text):
        try:
            desc = re.sub(r'\s+', ' ', m.group(1)).strip()
            date = parse_date(m.group(2))
            amount = parse_amount(m.group(4))
            if not date or amount == 0.0:
                continue
            if _n26_should_skip(desc):
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
            r'(\d{2}\.\d{2}\.\d{2,4})\s+(\d{2}\.\d{2}\.\d{2,4})\s+(-?\d[\d\s]*[.,]\d{2})\s*€',
            re.MULTILINE
        )
        for m in pattern2.finditer(full_text):
            try:
                date = parse_date(m.group(1))
                amount = parse_amount(m.group(3))
                if not date or amount == 0.0:
                    continue
                result.append({
                    'Дата': date, 'Сумма': amount,
                    'Контрагент': 'N26', 'Наименование счета': account_name,
                    'Описание': ''
                })
            except Exception:
                continue
    return result

# ==================== Paysera (XLSX/DOCX) ====================

def parse_paysera_generic(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    df = read_xlsx(file_content, sheet_name='Worksheet')
    if df is None or df.empty:
        df = read_xlsx(file_content)
    if df is None or df.empty:
        return []
    header_row = -1
    for idx, row in df.iterrows():
        if idx < 60:
            rs = ' '.join([str(x) for x in row.values if pd.notna(x)])
            # ru / en варианты
            if ('Тип' in rs and 'Дата и время' in rs and 'Сумма и валюта' in rs) or \
               ('Type' in rs and ('Date and time' in rs or 'Date' in rs) and ('Amount' in rs and 'currency' in rs.lower())):
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
        if 'Дата и время' in s or ('date' in sl and 'time' in sl):
            ci['date'] = i
        elif 'Получатель' in s or 'Плательщик' in s or 'Payee' in s or 'Payer' in s:
            ci['counterparty'] = i
        elif 'Назначение платежа' in s or 'Purpose' in s:
            ci['purpose'] = i
        elif 'Сумма и валюта' in s or ('amount' in sl and 'currency' in sl):
            ci['amount'] = i
        elif 'Кредит / Дебет' in s or ('credit' in sl and 'debit' in sl):
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
            if amount == 0.0:
                continue
            ttype = safe_str(row.iloc[ci['type']]) if 'type' in ci and ci['type'] < len(row) else ''
            if ttype in ('Д', 'D', 'Debit'):
                amount = -abs(amount)
            elif ttype in ('К', 'C', 'Credit'):
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
            if not date or amount == 0.0:
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
                if not date or amount == 0.0:
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

# ==================== Paysera PDF ====================

PAYSERA_PDF_DATE_GROUP_WINDOW = 400

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
        if dm.start() - cur['end'] < PAYSERA_PDF_DATE_GROUP_WINDOW:
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
        if chosen_amount is None or chosen_amount == 0.0:
            continue

        desc = ''
        window_text = full_text[window_start:window_end]
        purpose_match = re.search(
            r'Purpose of payment\s*:\s*([^\.]{1,200}?)(?:\.|$)', window_text, re.IGNORECASE
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
        parts = _split_line(line, ';')
        if len(parts) < 3:
            continue
        try:
            date = parse_date(parts[0])
            if not date:
                continue
            amount = parse_amount(parts[2].replace(',', '.'))
            if amount == 0.0:
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
                if amount == 0.0:
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
    Revolut CSV.
    Заголовок: Date started (UTC),Date completed (UTC),ID,Type,State,Description,...,Amount,...
    """
    result = []
    content = read_text_with_encoding(file_content)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if len(lines) < 2:
        return []
    header = -1
    for i, l in enumerate(lines):
        low = l.lower()
        if 'date started' in low and 'amount' in low and 'description' in low:
            header = i
            break
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
        hl = h.lower()
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
                if st and st not in ('COMPLETED', 'REVERTED'):
                    continue
            date = parse_date(parts[ci['date']] if ci['date'] < len(parts) else '')
            if not date:
                continue
            amount = parse_amount(parts[ci['amount']] if ci['amount'] < len(parts) else '')
            if amount == 0.0:
                continue
            ttype = parts[ci['type']].strip().upper() if 'type' in ci and ci['type'] < len(parts) else ''
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
                if amount == 0.0:
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

UNICREDIT_HEADER_MARKERS_EN = ('from account', 'amount', 'booking date')
UNICREDIT_HEADER_MARKERS_CZ = ('datum', 'částka', 'castka', 'zpráva', 'zprava', 'protiúčet', 'protiucet')


def _unicredit_is_header(low: str) -> bool:
    if all(m in low for m in UNICREDIT_HEADER_MARKERS_EN):
        return True
    # Чешские выгрузки: 'Datum' + 'Částka' + что-то из 'Zpráva' / 'Protiúčet'.
    if ('datum' in low) and ('částka' in low or 'castka' in low) and (
        'zpráva' in low or 'zprava' in low or 'protiúčet' in low or 'protiucet' in low
    ):
        return True
    return False


def parse_unicredit_generic(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    content = read_text_with_encoding(file_content)
    content = content.replace('\ufeff', '')
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if len(lines) < 3:
        return []

    header = -1
    for i, l in enumerate(lines[:60]):
        if _unicredit_is_header(l.lower()):
            header = i
            break
    if header == -1:
        return []

    hdr_line = lines[header]
    sep = ';' if hdr_line.count(';') >= hdr_line.count(',') else ','
    hdr_parts = _split_line(hdr_line, sep)

    ci = {}
    for i, h in enumerate(hdr_parts):
        hc = h.strip()
        hcl = hc.lower()
        if (hc == 'Amount' or hc == 'Částka' or hc == 'Castka') and 'amount' not in ci:
            ci['amount'] = i
        elif (hc == 'Booking Date' or hc == 'Datum' or 'Datum' in hc) and 'date' not in ci:
            ci['date'] = i
        elif (hc == 'Transaction Details' or hc == 'Zpráva' or hc == 'Zprava' or 'Zpráva' in hc or 'Zprava' in hc) and 'description' not in ci:
            ci['description'] = i
        elif (hc == 'Name' or hc == 'Protiúčet' or hc == 'Protiucet' or 'Protiúčet' in hc or 'Protiucet' in hc) and 'counterparty' not in ci:
            ci['counterparty'] = i
    if 'amount' not in ci:
        ci['amount'] = 1
    if 'date' not in ci:
        ci['date'] = 3
    if 'description' not in ci:
        ci['description'] = 13
    if 'counterparty' not in ci:
        ci['counterparty'] = 9

    for line in lines[header + 1:]:
        parts = _split_line(line, sep)
        while parts and parts[-1] == '':
            parts.pop()
        if len(parts) < 3:
            continue
        try:
            amount = parse_amount(parts[ci['amount']] if ci['amount'] < len(parts) else '')
            if amount == 0.0:
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
                if amount == 0.0:
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
                if not date or amount == 0.0:
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
    content = content.replace('\ufeff', '')
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
    _wio_sep = ',' if lines[header].count(',') >= lines[header].count(';') else ';'
    hdr_parts = _split_line(lines[header], _wio_sep)
    ci = {}
    for i, h in enumerate(hdr_parts):
        hc = h.strip()
        if hc == 'Amount':
            ci['amount'] = i
        elif hc == 'Date':
            ci['date'] = i
        elif hc == 'Description':
            ci['description'] = i
        elif hc == 'Notes':
            ci['notes'] = i
    if 'amount' not in ci:
        ci['amount'] = 10
    if 'date' not in ci:
        ci['date'] = 7
    if 'description' not in ci:
        ci['description'] = 9
    for line in lines[header + 1:]:
        parts = _split_line(line, _wio_sep)
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
                if amount == 0.0:
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
        parts = _split_line(line, ';')
        if len(parts) < 3:
            continue
        try:
            date = parse_date(parts[0])
            if not date:
                continue
            amount = parse_amount(parts[1].replace(',', '.'))
            if amount == 0.0:
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
            if amount == 0.0:
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

# ==================== Pasha Bank (BUNDA LLC) ====================

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

# ==================== Универсальный PDF fallback ====================

def parse_pdf_universal(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    tables = pdf_all_tables(file_content)
    for table in tables:
        if not table or len(table) < 2:
            continue
        header_idx = -1
        for i, row in enumerate(table):
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
                if amount == 0.0:
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

# ==================== МАРШРУТИЗАЦИЯ ====================

def _route_tabular(account_name: str):
    """
    Общая маршрутизация для .xlsx / .xls / .csv.
    Возвращает (parser, key) или (None, None).
    Для Tinkoff возвращаем '__tinkoff_tabular__'.

    ВАЖНО: порядок проверок имеет значение.
    Revolut идёт ДО Industra, потому что в имени файла Revolut-выгрузки
    часто встречается 'an14' (номер счёта), и раньше он уходил в industra_an14.
    """
    low = account_name.lower()

    if 'regina alfa' in low:
        return parse_regina_alfa_xlsx, 'regina_alfa_xlsx'
    if 'tinkoff' in low:
        return '__tinkoff_tabular__', None

    # --- Revolut до Industra ---
    if 'revolut' in low:
        if 'nb rev' in low or 'nb_rev' in low:
            return parse_revolut_nb, 'revolut_nb'
        if 'plavas' in low:
            return parse_revolut_plavas, 'revolut_plavas'
        return parse_revolut_an14, 'revolut_an14'

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

    # --- Industra после Revolut ---
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
    if 'unicredit' in low or 'garpiz' in low or 'twohills' in low or 'two hills' in low \
            or 'b1 estate' in low or 'b1_estate' in low or 'uc ' in low:
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
    return None, None


def get_parser_by_ext(account_name: str, ext: str):
    low = account_name.lower()

    # ========== PDF ==========
    if ext == '.pdf':
        if 'regina alfa' in low:
            return parse_regina_alfa_pdf, 'regina_alfa_pdf'
        if 'tinkoff' in low:
            return parse_tinkoff_pdf, 'tinkoff_pdf'
        if 'bluor' in low:
            return parse_bluor_pdf, 'bluor_pdf'
        if 'jenhor' in low or 'unelma' in low:
            return parse_jenhor_unelma_pdf, 'jenhor_unelma_pdf'
        if 'revolut' in low:
            return parse_revolut_pdf, 'revolut_pdf'
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
        if 'unicredit' in low or 'garpiz' in low or 'twohills' in low or 'koruna' in low or 'b1 estate' in low:
            return parse_unicredit_pdf, 'unicredit_pdf'
        if 'wio' in low:
            return parse_wio_pdf, 'wio_pdf'
        return parse_pdf_universal, 'pdf_universal'

    # ========== DOCX ==========
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
        return None, None

    # ========== XLSX / XLS ==========
    if ext in ('.xlsx', '.xls'):
        parser, key = _route_tabular(account_name)
        if parser == '__tinkoff_tabular__':
            return parse_tinkoff_xlsx, 'tinkoff_xlsx'
        if parser is not None:
            return parser, key
        return None, None

    # ========== CSV ==========
    if ext == '.csv':
        parser, key = _route_tabular(account_name)
        if parser == '__tinkoff_tabular__':
            return parse_tinkoff_csv, 'tinkoff_csv'
        if parser is not None:
            return parser, key
        return None, None

    return None, None

def parse_file(file_content: bytes, filename: str) -> Tuple[List[Dict], str]:
    account_name = clean_account_name(filename)
    ext = os.path.splitext(filename)[1].lower()
    parser, key = get_parser_by_ext(account_name, ext)
    if parser is None:
        return [], f'нет парсера для {account_name} ({ext})'
    try:
        return parser(file_content, account_name), f'{key} ({account_name})'
    except Exception as e:
        return [], f'{key} упал: {e}'

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
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("""
            <div class="info-card">
              <div class="info-card-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="#5D9968" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
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
                  <path d="M9 11l3 3L22 4M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" stroke="#5D9968" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
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
                  <path d="M3 3v18h18M18 17V9M13 17V5M8 17v-3" stroke="#5D9968" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </div>
              <div class="info-card-text"><h4>Экспорт в Excel</h4><p>Скачайте итог в один клик</p></div>
            </div>
            """, unsafe_allow_html=True)

    if uploaded_files:
        st.markdown("---")
        st.markdown(f"**Загружено файлов:** {len(uploaded_files)}")

        if st.button("🚀 Обработать файлы"):
            all_tx = []
            failed = []
            file_stats = []
            debug_info = []

            progress = st.progress(0)
            status = st.empty()

            for i, uf in enumerate(uploaded_files):
                status.text(f"Обработка: {uf.name}")
                try:
                    content = uf.read()
                    tx, parser_name = parse_file(content, uf.name)
                    account_name = clean_account_name(uf.name)
                    debug_info.append(f"🔍 `{uf.name}` → счёт: `{account_name}` → парсер: `{parser_name}` → **{len(tx)}** операций")
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
                progress.progress((i + 1) / len(uploaded_files))

            status.text("✅ Обработка завершена!")

            st.markdown("### 📋 Результат обработки")
            for s in file_stats:
                st.info(s)

            with st.expander("🔧 Техническая информация"):
                for line in debug_info:
                    st.markdown(line)

            if all_tx:
                df = pd.DataFrame(all_tx)
                df['Сумма_число'] = df['Сумма']
                df['Сумма'] = df['Сумма'].apply(format_amount)

                st.markdown("---")
                st.markdown("### 📊 Итоги")
                c1, c2, c3 = st.columns(3)
                income = df['Сумма_число'][df['Сумма_число'] > 0].sum()
                expense = abs(df['Сумма_число'][df['Сумма_число'] < 0].sum())
                with c1:
                    st.metric("📊 Всего операций", len(all_tx))
                with c2:
                    st.metric("📈 Доходы", f"{income:,.2f}".replace('.', ','))
                with c3:
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

            if failed:
                st.warning(f"⚠️ Не удалось обработать: {len(failed)} файлов")
                for f in failed:
                    st.write(f"- {f}")

    st.markdown("""
    <div class="footer-note">
      Работает локально. Данные никуда не отправляются.
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
