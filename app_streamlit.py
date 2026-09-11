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

# ==================== CSOB ====================

def parse_csob_generic(file_content: bytes, account_name: str) -> List[Dict]:
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

def parse_regina_alfa_docx(file_content: bytes, account_name: str) -> List[Dict]:
    full_text = docx_all_text(file_content)
    if not full_text:
        return []
    pattern = re.compile(
        r'(\d{2}\.\d{2}\.\d{4})\s*([A-Z0-9_]+)\s*(.+?)(-?[\d\s]+,\d{2})\s*RUR',
        re.DOTALL
    )
    result = []
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(1).strip())
            code = m.group(2).strip()
            desc = re.sub(r'\s+', ' ', m.group(3)).strip()
            amount = parse_amount(m.group(4))
            if not date or amount == 0.0:
                continue
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': '', 'Наименование счета': account_name,
                'Описание': f"{code} {desc}"[:500]
            })
        except Exception:
            continue
    return result

def parse_regina_alfa_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []
    pattern = re.compile(
        r'(\d{2}\.\d{2}\.\d{4})\s*([A-Z0-9_]+)\s*(.+?)(-?[\d\s]+,\d{2})\s*RUR',
        re.DOTALL
    )
    result = []
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(1).strip())
            code = m.group(2).strip()
            desc = re.sub(r'\s+', ' ', m.group(3)).strip()
            amount = parse_amount(m.group(4))
            if not date or amount == 0.0:
                continue
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': '', 'Наименование счета': account_name,
                'Описание': f"{code} {desc}"[:500]
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
        r'([^\n]{2,300}?)(?:\s+7596|\s+—|\n|$)',
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
    skip = ['начальный остаток', 'конечный остаток', 'starting balance', 'ending balance',
            'total', 'дебет (d)', 'кредит (c)', 'debit (d)', 'credit (c)']
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
            if any(w in low for w in skip):
                continue
            ttype = parts[6] if len(parts) > 6 else ''
            if ttype == 'D':
                amount = -abs(amount)
            elif ttype == 'C':
                amount = abs(amount)
            cp = 'BluOr Bank' if 'BluOr' in desc or 'Bank' in desc else ''
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
        r'(\d{2}\.\d{2}\.\d{4})\s+(.+?)\s+(-?\d[\d\s]*[,.]\d{2})(?!\d)',
        re.DOTALL
    )
    for m in pattern.finditer(full_text):
        try:
            date = parse_date(m.group(1).strip())
            desc_raw = m.group(2).strip()
            desc = re.sub(r'\s+', ' ', desc_raw)
            amount = parse_amount(m.group(3).strip())
            if not date or amount == 0.0:
                continue
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
        except Exception:
            continue
    if not result:
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells]
                if not cells:
                    continue
                date_found = None
                amount_found = None
                for c in cells:
                    d = parse_date(c)
                    if d and re.match(r'^\d{2}\.\d{2}\.\d{4}$', c):
                        date_found = d
                        break
                for c in cells:
                    if re.match(r'^-?\d[\d\s]*[,.]\d{2}$', c.strip()):
                        amount_found = parse_amount(c)
                        break
                if date_found and amount_found is not None and amount_found != 0.0:
                    desc = ' | '.join([c for c in cells if c and c != date_found][:3])
                    result.append({
                        'Дата': date_found, 'Сумма': amount_found,
                        'Контрагент': 'Česká spořitelna',
                        'Наименование счета': account_name,
                        'Описание': desc[:500]
                    })
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
    header = -1
    for i, l in enumerate(lines):
        low = l.lower()
        if ('date' in low and 'volume' in low) or ('"date"' in low and '"volume"' in low):
            header = i
            break
    if header == -1:
        return []
    for line in lines[header + 1:]:
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

def _parse_industra_generic(file_content: bytes, account_name: str) -> List[Dict]:
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
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': '', 'Наименование счета': account_name,
                'Описание': parts[1][:500] if len(parts) > 1 else ''
            })
        except Exception:
            continue
    return result

def parse_kapital_saida_docx(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []
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
    table_rows_text = []
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            table_rows_text.append(cells)
    pattern = re.compile(
        r'(\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4})\s+'
        r'([\d\s]+[.,]\d{1,2})\s+'
        r'([\d\s]+[.,]\d{1,2})\s+'
        r'([\d\s]+[.,]\d{1,2})\s+'
        r'([A-Za-z][A-Za-z0-9\s\-\./]{2,120})',
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
                low = desc.lower()
                if any(w in low for w in ['balance', 'saldo', 'start', 'end', 'period',
                                           'лимит', 'баланс', 'период', 'available', 'кредитн']):
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
        for cells in table_rows_text:
            try:
                date_cell = None
                desc_cell = None
                amount_cell = None
                for c in cells:
                    d = parse_date(c)
                    if d and re.match(r'^\d{4}-\d{2}-\d{2}$', c.strip()):
                        date_cell = d
                        continue
                    if re.match(r'^-?\d[\d\s]*[.,]\d{2}$', c.strip()) and amount_cell is None:
                        amount_cell = parse_amount(c)
                        continue
                    if c and len(c) > 3 and re.search(r'[A-Za-zА-Яа-я]{3,}', c):
                        if desc_cell is None:
                            desc_cell = c
                if date_cell and amount_cell is not None and amount_cell != 0.0:
                    low = (desc_cell or '').lower()
                    if any(w in low for w in ['balance', 'saldo', 'start', 'end', 'period']):
                        continue
                    result.append({
                        'Дата': date_cell, 'Сумма': -abs(amount_cell),
                        'Контрагент': 'Kapital Bank',
                        'Наименование счета': account_name,
                        'Описание': (desc_cell or '')[:500]
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
                low = (desc or '').lower()
                if any(w in low for w in ['balance', 'saldo', 'start', 'end', 'period']):
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
            r'(\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4})\s+'
            r'([\d\s]+[.,]\d{1,2})\s+'
            r'([\d\s]+[.,]\d{1,2})\s+'
            r'([\d\s]+[.,]\d{1,2})\s+'
            r'([A-Za-z][A-Za-z0-9\s\-\./]{2,80})',
            re.MULTILINE
        )
        for m in pattern.finditer(full_text):
            try:
                date = parse_date(m.group(1).strip())
                amount = parse_amount(m.group(2).strip())
                desc = m.group(5).strip()
                if not date or amount == 0.0:
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

# ==================== MKB ====================

def parse_budapest_eur_mkb(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
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
        low = l.lower()
        if 'sorsz' in low and 'rt' in low and 'knap' in low:
            header = i
            break
    if header == -1:
        return []
    hdr_parts = [p.strip() for p in lines[header].split(';')]
    date_idx = amount_idx = desc_idx = cp_idx = -1
    for i, h in enumerate(hdr_parts):
        hl = h.lower()
        if 'értéknap' in hl or ('rt' in hl and 'knap' in hl):
            date_idx = i
        elif 'összeg' in hl or 'sszeg' in hl:
            amount_idx = i
        elif 'közlemény' in hl or 'kzlem' in hl:
            desc_idx = i
        elif 'kedvezményezett' in hl and 'neve' in hl and cp_idx == -1:
            cp_idx = i
    if date_idx == -1:
        date_idx = 1
    if amount_idx == -1:
        amount_idx = 9
    if desc_idx == -1:
        desc_idx = 11
    for line in lines[header + 1:]:
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
            cp = parts[cp_idx] if cp_idx >= 0 and cp_idx < len(parts) else ''
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp[:200], 'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return result

def parse_budapest_huf_mkb(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
    df = read_xlsx(file_content)
    if df is None or df.empty:
        return []
    header_row = -1
    for idx, row in df.iterrows():
        if idx < 20:
            rs = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Sorszám' in rs and 'Értéknap' in rs:
                header_row = idx
                break
            if 'rt' in rs and 'knap' in rs and 'sszeg' in rs:
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
        elif 'kedvezményezett' in sl and 'neve' in sl and 'counterparty' not in ci:
            ci['counterparty'] = i
    if 'date' not in ci:
        ci['date'] = 1
    if 'amount' not in ci:
        ci['amount'] = 9
    if 'description' not in ci:
        ci['description'] = 11
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
            result.append({
                'Дата': date, 'Сумма': amount,
                'Контрагент': cp[:200], 'Наименование счета': account_name,
                'Описание': desc[:500]
            })
        except Exception:
            continue
    return result

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

def parse_n26_docx(file_content: bytes, account_name: str) -> List[Dict]:
    full_text = docx_all_text(file_content)
    if not full_text:
        return []
    result = []
    pattern = re.compile(
        r'([A-Za-z0-9][^\n]{3,120}?)'
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
            if not date or amount == 0.0:
                continue
            low = desc.lower()
            if any(w in low for w in ['saldo previo', 'nuevo saldo', 'transacciones']):
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
        r'([A-Za-z0-9][^\n]{3,120}?)'
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
            if not date or amount == 0.0:
                continue
            low = desc.lower()
            if any(w in low for w in ['saldo previo', 'nuevo saldo', 'transacciones',
                                       'extracto', 'espacio', 'deseño']):
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
            r'(\d{2}\.\d{2}\.\d{4})\s+(\d{2}\.\d{2}\.\d{4})\s+(-?\d[\d\s]*[.,]\d{2})\s*€',
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
        if idx < 30:
            rs = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Тип' in rs and 'Дата и время' in rs and 'Сумма и валюта' in rs:
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
        elif 'Кредит / Дебет' in s:
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
            if ttype in ('Д', 'D'):
                amount = -abs(amount)
            elif ttype in ('К', 'C'):
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

# ==================== Paysera PDF (НОВЫЙ АЛГОРИТМ) ====================

def parse_paysera_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Paysera PDF.

    pdfplumber отдаёт весь текст одной строкой (таблица склеена), поэтому
    стратегии с '\\n' и MULTILINE не работают. Используем поиск по «окнам»
    между датами.

    Алгоритм:
    1. Находим все даты вида YYYY-MM-DD HH:MM:SS.
    2. Для каждой даты смотрим окно до следующей даты (или +2000 символов).
    3. Внутри окна ищем РОВНО одну отрицательную сумму EUR (-5.00 EUR) —
       это сумма операции (комиссия / платёж).
    4. Исключаем положительные суммы, если рядом (в пределах 60 символов)
       есть слова balance/turnover/final/start/debit/credit.
    5. Описание: 'Purpose of payment:' или ключевые слова.
    """
    result = []
    full_text = pdf_all_text(file_content)
    if not full_text:
        return []

    # Находим все даты с временем
    date_pattern = re.compile(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})')
    date_matches = list(date_pattern.finditer(full_text))
    if not date_matches:
        return []

    # Находим все суммы EUR (и положительные, и отрицательные)
    eur_pattern = re.compile(r'([+\-]?\d[\d\s]*[.,]\d{2})\s*EUR')
    eur_matches = []
    for m in eur_pattern.finditer(full_text):
        eur_matches.append({
            'start': m.start(),
            'end': m.end(),
            'amount': parse_amount(m.group(1)),
            'raw': m.group(1),
        })

    STOP_WORDS = ['balance', 'turnover', 'final', 'start', 'debit', 'credit',
                  'start balance', 'final balance']

    for i, dm in enumerate(date_matches):
        date_str = dm.group(1)
        date = parse_date(date_str)
        if not date:
            continue
        # Окно до следующей даты или +2000 символов
        window_start = dm.end()
        if i + 1 < len(date_matches):
            window_end = date_matches[i + 1].start()
        else:
            window_end = window_start + 2000
        if window_end <= window_start:
            continue

        # Все EUR-суммы в окне
        window_eur = [e for e in eur_matches if window_start <= e['start'] < window_end]

        # Приоритет 1: отрицательная сумма EUR в окне
        negative = [e for e in window_eur if e['amount'] < 0]
        # Приоритет 2: положительная сумма EUR, но не «balance»
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

        # Описание: сначала Purpose of payment:
        desc = ''
        window_text = full_text[window_start:window_end]
        purpose_match = re.search(r'Purpose of payment\s*:\s*([^\.]{1,200}?)(?:\.|$)', window_text, re.IGNORECASE)
        if purpose_match:
            desc = purpose_match.group(1).strip()
        if not desc:
            # Ключевые слова в окне
            head = full_text[max(0, chosen_pos - 120):chosen_pos]
            for marker in ['Commission fee', 'Commission', 'Плата за', 'Плата',
                           'Payment', 'Transfer', 'Fee', 'Sąskaitos palaikymo mokestis']:
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

    # Дедупликация по (дата, сумма)
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
    result = []
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
        if 'Date started' in h:
            ci['date'] = i
        elif h == 'Amount':
            ci['amount'] = i
        elif 'Description' in h:
            ci['description'] = i
        elif 'Payer' in h:
            ci['counterparty'] = i
        elif h == 'State':
            ci['state'] = i
        elif h == 'Type':
            ci['type'] = i
    if 'date' not in ci:
        ci['date'] = 0
    if 'amount' not in ci:
        ci['amount'] = 14
    if 'description' not in ci:
        ci['description'] = 5
    if 'type' not in ci:
        ci['type'] = 3
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
            date = parse_date(parts[ci['date']] if ci['date'] < len(parts) else '')
            if not date:
                continue
            amount = parse_amount(parts[ci['amount']] if ci['amount'] < len(parts) else '')
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

def parse_unicredit_generic(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
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
        if hc == 'Amount':
            ci['amount'] = i
        elif hc == 'Booking Date':
            ci['date'] = i
        elif hc == 'Transaction Details':
            ci['description'] = i
        elif hc == 'Name':
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
        parts = [p.strip() for p in line.split(';')]
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

# ==================== WIO, Saida N26, Wise ====================

def parse_wio_business(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
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

def parse_saida_n26_csv(file_content: bytes, account_name: str) -> List[Dict]:
    result = []
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
    
    # ========== XLSX / XLS / CSV ==========
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
    if 'mkb' in low or 'budapest' in low:
        if 'huf' in low:
            return parse_budapest_huf_mkb, 'budapest_huf_mkb'
        return parse_budapest_eur_mkb, 'budapest_eur_mkb'
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
    if 'revolut' in low:
        if 'nb rev' in low or 'nb_rev' in low:
            return parse_revolut_nb, 'revolut_nb'
        if 'plavas' in low:
            return parse_revolut_plavas, 'revolut_plavas'
        return parse_revolut_an14, 'revolut_an14'
    if 'unicredit' in low or 'garpiz' in low or 'twohills' in low or 'two hills' in low:
        if 'b1 estate' in low:
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
        return parse_saida_wise, 'saida_wise'
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
