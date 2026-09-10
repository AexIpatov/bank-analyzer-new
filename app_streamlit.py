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

# ==================== CSS СТИЛИ + ИЛЛЮСТРАЦИИ ====================
st.markdown("""
<style>
/* ---------- ШРИФТЫ И БАЗОВЫЕ ЦВЕТА ---------- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --mint-light: #A8D5BA;
    --mint-dark: #5D9968;
    --sage: #7BAE7F;
    --cream: #FAF8F3;
    --cream-dark: #F0EDE3;
    --ink: #1F2D23;
    --ink-soft: #4A5A4E;
    --ink-muted: #7A8A7E;
    --border: #D5E5D9;
    --white: #FFFFFF;
}

.stApp {
    background: linear-gradient(180deg, #FAF8F3 0%, #F0F5EE 50%, #E8F2E4 100%);
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    color: var(--ink);
}
.main { background: transparent; }
footer {visibility: hidden;}
#MainMenu {visibility: hidden;}

/* ---------- ШАПКА ---------- */
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
    font-weight: 400;
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
.hero-illustration {
    position: relative;
    z-index: 2;
    flex-shrink: 0;
}

/* ---------- КНОПКИ ---------- */
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

/* ---------- ФАЙЛОВЫЙ ЗАГРУЗЧИК ---------- */
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
.stFileUploader section {
    border: none !important;
    background: transparent !important;
}
.stFileUploader label {
    color: var(--ink) !important;
    font-weight: 500;
}
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

/* ---------- МЕТРИКИ ---------- */
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
    top: 0;
    left: 0;
    height: 100%;
    width: 6px;
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

/* ---------- ТАБЛИЦА ---------- */
.stDataFrame {
    border-radius: 20px;
    overflow: hidden;
    box-shadow: 0 8px 28px rgba(46, 59, 50, 0.08);
    background: #FFFFFF;
}

/* ---------- ПЛАШКИ ---------- */
.stAlert {
    border-radius: 14px;
    border: none;
    padding: 0.9rem 1.3rem;
    box-shadow: 0 3px 12px rgba(46, 59, 50, 0.05);
}
div[data-baseweb="notification"][kind="positive"] {
    background: #E8F5E9;
    color: var(--ink);
}
div[data-baseweb="notification"][kind="info"] {
    background: #EEF4EA;
    color: var(--ink);
}
div[data-baseweb="notification"][kind="warning"] {
    background: #FBF3E0;
    color: #7A5B10;
}

/* ---------- ПРОГРЕСС-БАР ---------- */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #5D9968 0%, #A8D5BA 100%);
    border-radius: 8px;
}

/* ---------- ЗАГОЛОВКИ ---------- */
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

/* ---------- СКРОЛЛБАР ---------- */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: #FAF8F3; }
::-webkit-scrollbar-thumb { background: #C8DECC; border-radius: 5px; }
::-webkit-scrollbar-thumb:hover { background: #A8D5BA; }

/* ---------- РАЗДЕЛИТЕЛИ ---------- */
hr {
    border: none;
    border-top: 1px solid #E8F2E4;
    margin: 2rem 0;
}

/* ---------- КАРТОЧКИ-ПОДСКАЗКИ ---------- */
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
    width: 56px;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 14px;
    background: linear-gradient(135deg, #E8F5E9 0%, #D5EDDA 100%);
}
.info-card-text h4 {
    color: var(--ink);
    margin: 0 0 0.25rem 0;
    font-size: 1rem;
    font-weight: 600;
}
.info-card-text p {
    color: var(--ink-muted);
    margin: 0;
    font-size: 0.88rem;
    line-height: 1.4;
}

/* ---------- STEP-ЧИПСЫ (сколько файлов загружено) ---------- */
.step-chips {
    display: flex;
    gap: 0.6rem;
    margin: 1rem 0;
    flex-wrap: wrap;
}
.step-chip {
    background: #FFFFFF;
    border: 1px solid #E8F2E4;
    border-radius: 999px;
    padding: 0.5rem 1.1rem;
    font-size: 0.88rem;
    font-weight: 500;
    color: var(--ink-soft);
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    box-shadow: 0 2px 8px rgba(46, 59, 50, 0.04);
}
.step-chip.active {
    background: linear-gradient(135deg, #5D9968 0%, #7BAE7F 100%);
    color: #FFFFFF;
    border-color: transparent;
    box-shadow: 0 4px 14px rgba(93, 153, 104, 0.3);
}

/* ---------- ФУТЕР ---------- */
.footer-note {
    text-align: center;
    color: var(--ink-muted);
    font-size: 0.85rem;
    padding: 1.5rem 0 0.5rem 0;
    opacity: 0.8;
}
</style>
""", unsafe_allow_html=True)

# ==================== ШАПКА С ИЛЛЮСТРАЦИЕЙ ====================
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
        <!-- фон круга -->
        <circle cx="100" cy="100" r="90" fill="rgba(255,255,255,0.15)"/>
        <!-- столбики графика -->
        <rect x="50" y="110" width="14" height="50" rx="4" fill="rgba(255,255,255,0.85)"/>
        <rect x="72" y="90" width="14" height="70" rx="4" fill="rgba(255,255,255,0.95)"/>
        <rect x="94" y="70" width="14" height="90" rx="4" fill="rgba(255,255,255,1)"/>
        <rect x="116" y="95" width="14" height="65" rx="4" fill="rgba(255,255,255,0.95)"/>
        <rect x="138" y="60" width="14" height="100" rx="4" fill="rgba(255,255,255,1)"/>
        <!-- линия тренда -->
        <path d="M57 100 L79 80 L101 60 L123 85 L145 50" stroke="#FFFFFF" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>
        <circle cx="57" cy="100" r="5" fill="#FFFFFF"/>
        <circle cx="79" cy="80" r="5" fill="#FFFFFF"/>
        <circle cx="101" cy="60" r="5" fill="#FFFFFF"/>
        <circle cx="123" cy="85" r="5" fill="#FFFFFF"/>
        <circle cx="145" cy="50" r="5" fill="#FFFFFF"/>
        <!-- монетка -->
        <circle cx="160" cy="40" r="16" fill="#FFD86B" stroke="#FFFFFF" stroke-width="2"/>
        <text x="160" y="46" text-anchor="middle" font-size="16" font-weight="700" fill="#5D9968">₽</text>
      </svg>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def detect_file_encoding_from_bytes(file_content: bytes) -> str:
    try:
        raw_data = file_content[:10000]
        result = chardet.detect(raw_data)
        return result['encoding'] if result['encoding'] else 'utf-8'
    except:
        return 'utf-8'

def clean_account_name(filename: str) -> str:
    name = os.path.splitext(filename)[0]
    # Убираем дату ГГГГ-ММ-ДД
    name = re.sub(r'\d{4}-\d{2}-\d{2}', '', name)
    # Убираем IBAN
    name = re.sub(r'LV\d{2}[A-Z]{4}\d{13,}', '', name)
    # Убираем суффиксы типа _01-Jul-2026_31-Jul-2026
    name = re.sub(r'_\d{2}-[A-Za-z]{3}-\d{4}_\d{2}-[A-Za-z]{3}-\d{4}', '', name)
    # Убираем суффиксы _01.08.2026 и похожие
    name = re.sub(r'_\d{2}\.\d{2}\.\d{4}', '', name)
    # Убираем суффиксы с одиночной датой _2026-07-01_2026-07-31 (осталась только одна из-за предыдущего шага)
    name = re.sub(r'_\d{4}_\d{2}_\d{2}', '', name)
    # Заменяем _ и - на пробелы
    name = re.sub(r'[_\-]', ' ', name).strip()
    # Сжимаем пробелы
    name = re.sub(r'\s+', ' ', name)
    # Убираем хвост " 2026"
    name = re.sub(r' 2026$', '', name)
    # Убираем хвост вида " 01.08.2026"
    name = re.sub(r' \d{1,2}\.\d{1,2}\.\d{4}$', '', name)
    # Убираем " (2)" в конце
    name = re.sub(r' \(2\)$', '', name)
    return name.strip() if name else 'Неизвестный счет'

def parse_date(date_str: str) -> str:
    if not date_str or pd.isna(date_str):
        return ''
    date_str = str(date_str).strip()
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    if date_str.endswith('.0'):
        date_str = date_str[:-2]
    if date_str.isdigit() and len(date_str) == 8:
        try:
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            return f"{day}-{month}-{year}"
        except:
            pass
    if '.' in date_str and len(date_str.split('.')) == 3:
        parts = date_str.split('.')
        try:
            day, month, year = parts
            if len(year) == 2:
                year = f"20{year}"
            return f"{day.zfill(2)}-{month.zfill(2)}-{year}"
        except:
            pass
    if '/' in date_str and len(date_str.split('/')) == 3:
        parts = date_str.split('/')
        try:
            day, month, year = parts
            if len(year) == 2:
                year = f"20{year}"
            return f"{day.zfill(2)}-{month.zfill(2)}-{year}"
        except:
            pass
    if '-' in date_str and len(date_str.split('-')) == 3:
        parts = date_str.split('-')
        try:
            year, month, day = parts
            if len(year) == 2:
                year = f"20{year}"
            return f"{day.zfill(2)}-{month.zfill(2)}-{year}"
        except:
            pass
    formats = [
        "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d",
        "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d", "%d.%m.%y",
        "%d/%m/%y", "%y-%m-%d", "%d-%b-%y", "%d-%b-%Y",
        "%b %d, %Y", "%d %b %Y"
    ]
    for fmt in formats:
        try:
            date_obj = datetime.strptime(date_str, fmt)
            return date_obj.strftime("%d-%m-%Y")
        except:
            continue
    return date_str

def parse_amount(amount_str) -> float:
    if amount_str is None or pd.isna(amount_str):
        return 0.0
    amount_str = str(amount_str).strip()
    if amount_str in ['', 'nan', '-', 'None', 'null', 'NaN', 'N/A', 'n/a']:
        return 0.0
    is_negative = False
    if amount_str.startswith('-'):
        is_negative = True
        amount_str = amount_str[1:]
    elif amount_str.startswith('+'):
        amount_str = amount_str[1:]
    elif amount_str.startswith('(') and amount_str.endswith(')'):
        is_negative = True
        amount_str = amount_str[1:-1]
    amount_str = re.sub(r'\s*[₽$€£]\s*$', '', amount_str)
    amount_str = re.sub(r'\s*[A-Z]{3}\s*$', '', amount_str)
    amount_str = re.sub(r'^\s*[A-Z]{3}\s*', '', amount_str)
    amount_str = amount_str.replace(' ', '').replace('\xa0', '')
    if ',' in amount_str and '.' in amount_str:
        if amount_str.rfind('.') < amount_str.rfind(','):
            amount_str = amount_str.replace('.', '').replace(',', '.')
        else:
            amount_str = amount_str.replace(',', '')
    elif ',' in amount_str:
        parts = amount_str.split(',')
        if len(parts) == 2 and len(parts[1]) == 2:
            amount_str = amount_str.replace(',', '.')
        else:
            amount_str = amount_str.replace(',', '')
    amount_str = re.sub(r'[^\d.\-]', '', amount_str)
    if not amount_str or amount_str == '.':
        return 0.0
    try:
        value = float(amount_str)
        return -abs(value) if is_negative else abs(value)
    except:
        return 0.0

def format_amount(amount: float) -> str:
    if amount is None or pd.isna(amount):
        return "0,00"
    sign = "-" if amount < 0 else ""
    amount_abs = abs(amount)
    formatted = f"{amount_abs:.2f}".replace('.', ',')
    if ',' in formatted:
        integer_part, decimal_part = formatted.split(',')
        integer_part = re.sub(r'(?<=\d)(?=(\d{3})+(?!\d))', ' ', integer_part)
        return f"{sign}{integer_part},{decimal_part}"
    return f"{sign}{formatted}"

def read_excel_any_engine(file_content: bytes, sheet_name=None):
    """Универсальное чтение XLSX/XLS независимо от расширения."""
    engines_to_try = ['openpyxl', 'xlrd', None]
    for engine in engines_to_try:
        try:
            kwargs = {'header': None}
            if sheet_name:
                kwargs['sheet_name'] = sheet_name
            if engine:
                kwargs['engine'] = engine
            df = pd.read_excel(BytesIO(file_content), **kwargs)
            if df is not None and not df.empty:
                return df
        except Exception:
            continue
    return None

# ==================== ПАРСЕРЫ ====================

# ---------- Regina Alfa (XLSX) ----------
def parse_regina_alfa(file_content: bytes, account_name: str) -> List[Dict]:
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
    data_start_idx = -1
    for idx, row in df.iterrows():
        if idx < 50:
            row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Операции по счету' in row_str:
                data_start_idx = idx + 1
                break
    if data_start_idx == -1:
        return []
    current_date = None
    current_desc = ''
    current_amount = None
    for idx in range(data_start_idx, len(df)):
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
                        val_str_clean = re.sub(r'\s*RUR\s*$', '', val_str)
                        if re.search(r'[\d,.]', val_str_clean):
                            amount_val = val_str
                            break
        if has_date:
            if current_date is not None and current_amount is not None:
                transactions.append({
                    'Дата': parse_date(str(current_date)),
                    'Сумма': parse_amount(str(current_amount)),
                    'Контрагент': extract_counterparty(current_desc),
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
            'Контрагент': extract_counterparty(current_desc),
            'Наименование счета': account_name,
            'Описание': current_desc[:500]
        })
    return transactions

# ---------- Regina Alfa (DOCX) ----------
def parse_regina_alfa_docx(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []
    all_text_parts = []
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                cell_text = cell.text.strip()
                if cell_text:
                    all_text_parts.append(cell_text)
    for para in doc.paragraphs:
        txt = para.text.strip()
        if txt:
            all_text_parts.append(txt)
    full_text = '\n'.join(all_text_parts)
    full_text = full_text.replace('\ufeff', '').replace('\xa0', ' ')
    pattern = re.compile(
        r'(\d{2}\.\d{2}\.\d{4})\s*'
        r'([A-Z0-9_]+)\s*'
        r'(.+?)'
        r'(-?[\d\s]+,\d{2})\s*RUR',
        re.DOTALL
    )
    for match in pattern.finditer(full_text):
        try:
            date_str = match.group(1).strip()
            code = match.group(2).strip()
            description = match.group(3).strip()
            amount_str = match.group(4).strip()
            description = re.sub(r'\s+', ' ', description).strip()
            date = parse_date(date_str)
            amount = parse_amount(amount_str)
            if not date or amount == 0.0:
                continue
            counterparty = extract_counterparty(description)
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty,
                'Наименование счета': account_name,
                'Описание': f"{code} {description}"[:500]
            })
        except Exception:
            continue
    return transactions

# ---------- Regina Alfa (PDF) ----------
def parse_regina_alfa_pdf(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    full_text_parts = []
    try:
        with pdfplumber.open(BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text_parts.append(text)
    except Exception:
        return []
    full_text = '\n'.join(full_text_parts)
    full_text = full_text.replace('\ufeff', '').replace('\xa0', ' ')
    pattern = re.compile(
        r'(\d{2}\.\d{2}\.\d{4})\s*'
        r'([A-Z0-9_]+)\s*'
        r'(.+?)'
        r'(-?[\d\s]+,\d{2})\s*RUR',
        re.DOTALL
    )
    for match in pattern.finditer(full_text):
        try:
            date_str = match.group(1).strip()
            code = match.group(2).strip()
            description = match.group(3).strip()
            amount_str = match.group(4).strip()
            description = re.sub(r'\s+', ' ', description).strip()
            date = parse_date(date_str)
            amount = parse_amount(amount_str)
            if not date or amount == 0.0:
                continue
            counterparty = extract_counterparty(description)
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty,
                'Наименование счета': account_name,
                'Описание': f"{code} {description}"[:500]
            })
        except Exception:
            continue
    return transactions

# ---------- Тинькофф (DOCX) ----------
def parse_tinkoff_docx(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        doc = Document(BytesIO(file_content))
    except Exception:
        return []
    target_table = None
    for table in doc.tables:
        if not table.rows:
            continue
        first_row_text = ' '.join(cell.text.strip() for cell in table.rows[0].cells)
        if 'Дата и время операции' in first_row_text and 'Сумма' in first_row_text:
            target_table = table
            break
    if target_table is None:
        return []
    header_cells = [cell.text.strip() for cell in target_table.rows[0].cells]
    date_idx = -1
    amount_idx = -1
    desc_idx = -1
    for i, h in enumerate(header_cells):
        h_clean = h.strip()
        if 'Дата и время операции' in h_clean:
            date_idx = i
        elif 'Сумма в валюте операции' in h_clean:
            amount_idx = i
        elif 'Описание операции' in h_clean:
            desc_idx = i
    if date_idx == -1:
        date_idx = 0
    if amount_idx == -1:
        amount_idx = 2
    if desc_idx == -1:
        desc_idx = 4
    for row in target_table.rows[1:]:
        cells = [cell.text.strip() for cell in row.cells]
        if len(cells) < 3:
            continue
        try:
            date_raw = cells[date_idx] if date_idx < len(cells) else ''
            date_match = re.match(r'(\d{2}\.\d{2}\.\d{4})', date_raw)
            if not date_match:
                continue
            date_str = date_match.group(1)
            date = parse_date(date_str)
            if not date:
                continue
            amount_raw = cells[amount_idx] if amount_idx < len(cells) else ''
            amount = parse_amount(amount_raw)
            if amount == 0.0:
                continue
            description = cells[desc_idx] if desc_idx < len(cells) else ''
            description = re.sub(r'\s+', ' ', description).strip()
            counterparty = extract_tinkoff_counterparty(description)
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty,
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception:
            continue
    return transactions

def extract_tinkoff_counterparty(description: str) -> str:
    if not description:
        return ''
    if 'Внутренний перевод' in description:
        return 'Внутренний перевод'
    if 'Внешний перевод' in description:
        return 'Внешний перевод'
    if 'Перевод себе' in description:
        return 'Перевод себе'
    if 'Плата за' in description or 'Комиссия' in description:
        return 'Т-Банк'
    if 'Перевод' in description:
        return 'Перевод'
    return description[:60]

def extract_counterparty(description: str) -> str:
    if not description:
        return ''
    match = re.search(r'от\s+([+\d\s]+)', description)
    if match:
        return match.group(1).strip()
    match = re.search(r'на\s+([+\d\s]+)', description)
    if match:
        return match.group(1).strip()
    if 'Пляцевая' in description:
        return 'Пляцевая Регина Николаевна'
    match = re.search(r'место совершения операции:\s*([^\\]+)', description)
    if match:
        place = match.group(1).strip()
        if '\\' in place:
            parts = place.split('\\')
            if len(parts) >= 2:
                return parts[1] if parts[1] else parts[0]
        return place[:50]
    if 'Перевод денежных средств' in description:
        return 'Перевод'
    return description[:50]

# ---------- Tinkoff RUB (CSV) ----------
def parse_tinkoff(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1250')
        except:
            content = file_content.decode('latin-1')
    lines = content.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    if len(lines) < 3:
        return []
    header_idx = -1
    for i, line in enumerate(lines):
        if 'дата' in line.lower() and 'сумма' in line.lower():
            header_idx = i
            break
    if header_idx == -1:
        return []
    for line_idx in range(header_idx + 1, len(lines)):
        line = lines[line_idx]
        if not line:
            continue
        parts = line.split(';')
        if len(parts) < 3:
            continue
        try:
            date_str = parts[0].strip() if len(parts) > 0 else ''
            date = parse_date(date_str)
            if not date:
                continue
            amount_str = parts[1].strip() if len(parts) > 1 else ''
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            description = ' '.join(parts[2:]) if len(parts) > 2 else ''
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': '',
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except:
            continue
    return transactions

# ---------- BSR Estate EUR BluOr 2 / 3 ----------
def parse_bsr_bluor_2(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1250')
        except:
            content = file_content.decode('latin-1')
    lines = content.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    for line in lines:
        parts = line.split(';')
        if len(parts) < 3:
            continue
        try:
            date_str = parts[0].strip()
            date = parse_date(date_str)
            if not date:
                continue
            amount_str = parts[1].strip().replace(',', '.')
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            description = ' '.join(parts[2:]) if len(parts) > 2 else ''
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': '',
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except:
            continue
    return transactions

def parse_bsr_bluor_3(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_bsr_bluor_2(file_content, account_name)

# ---------- KL59 Rev NB BluOr ----------
def parse_kl59_rev_nb_bluor(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1250')
        except:
            content = file_content.decode('latin-1')
    if content.startswith('\ufeff'):
        content = content[1:]
    lines = content.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    if len(lines) < 2:
        return []
    for line_idx, line in enumerate(lines):
        if not line:
            continue
        parts = []
        current = ''
        in_quotes = False
        for char in line:
            if char == '"':
                in_quotes = not in_quotes
            elif char == ',' and not in_quotes:
                parts.append(current.strip())
                current = ''
            else:
                current += char
        parts.append(current.strip())
        parts = [p.strip('"') for p in parts]
        if len(parts) < 5:
            continue
        try:
            description = parts[3].strip() if len(parts) > 3 else ''
            if 'Starting balance' in description:
                continue
            if 'Total' in description:
                continue
            if description in ['Debit (D)', 'Credit (C)']:
                continue
            date_str = parts[1].strip() if len(parts) > 1 else ''
            date = parse_date(date_str)
            if not date:
                continue
            amount_str = parts[4].strip() if len(parts) > 4 else ''
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            trans_type = ''
            if len(parts) > 6:
                trans_type = parts[6].strip()
            if not trans_type or trans_type == '':
                if 'Debit' in description or 'D)' in description:
                    trans_type = 'D'
                elif 'Credit' in description or 'C)' in description:
                    trans_type = 'C'
            if trans_type == 'D':
                amount = -abs(amount)
            elif trans_type == 'C':
                amount = abs(amount)
            counterparty = ''
            if 'BluOr' in description or 'Bank' in description:
                counterparty = 'BluOr Bank'
            elif trans_type == 'D':
                counterparty = 'Расход'
            elif trans_type == 'C':
                counterparty = 'Доход'
            else:
                counterparty = description[:200]
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty,
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception:
            continue
    return transactions

# ---------- JenHor Unelma ----------
def parse_jenhor_unelma(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1250')
        except:
            content = file_content.decode('latin-1')
    lines = content.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    if len(lines) < 3:
        return []
    header_idx = -1
    for i, line in enumerate(lines):
        if 'account' in line.lower() and 'amount' in line.lower():
            header_idx = i
            break
    if header_idx == -1:
        return []
    for line_idx in range(header_idx + 1, len(lines)):
        line = lines[line_idx]
        if not line:
            continue
        parts = line.split(';')
        if len(parts) < 3:
            continue
        try:
            date_str = parts[0].strip() if len(parts) > 0 else ''
            date = parse_date(date_str)
            if not date:
                continue
            amount_str = parts[1].strip() if len(parts) > 1 else ''
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            counterparty = parts[2].strip() if len(parts) > 2 else ''
            description = ' '.join(parts[3:]) if len(parts) > 3 else ''
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty[:200],
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except:
            continue
    return transactions

# ---------- CSOB general ----------
def parse_csob_general(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1250')
        except:
            content = file_content.decode('latin-1')
    lines = content.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    if len(lines) < 3:
        return []
    header_idx = -1
    for i, line in enumerate(lines):
        if 'account number' in line.lower() and 'posting date' in line.lower():
            header_idx = i
            break
    if header_idx == -1:
        return []
    for line_idx in range(header_idx + 1, len(lines)):
        line = lines[line_idx]
        if not line:
            continue
        parts = line.split(';')
        while parts and parts[-1] == '':
            parts.pop()
        if len(parts) < 7:
            continue
        try:
            date_str = parts[4].strip() if len(parts) > 4 else ''
            date = parse_date(date_str)
            if not date:
                continue
            amount_str = parts[6].strip() if len(parts) > 6 else ''
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
            elif re.search(r'[\d,.]+\s*[A-Z]{3}$', amount_str):
                is_amount = True
            if not is_amount:
                continue
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            counterparty = ''
            if len(parts) > 13:
                counterparty = parts[13].strip()
                if counterparty and counterparty != 'nan':
                    counterparty = counterparty[:200]
            if not counterparty and len(parts) > 3:
                counterparty = parts[3].strip()
                if counterparty and counterparty != 'nan':
                    counterparty = counterparty[:200]
            description = ''
            if len(parts) > 16:
                description = parts[16].strip()
                if description and description != 'nan':
                    description = description
            if not description and len(parts) > 28:
                description = parts[28].strip()
                if description and description != 'nan':
                    description = description
            if not description:
                desc_parts = []
                potential_desc_indices = [2, 10, 11, 12, 15, 19, 20, 21, 22, 23, 28, 29]
                for idx in potential_desc_indices:
                    if idx < len(parts):
                        part = parts[idx].strip()
                        if part and part != 'nan' and len(part) > 1:
                            if not re.match(r'^[\d.,\-]+$', part):
                                desc_parts.append(part)
                if desc_parts:
                    description = ' | '.join(desc_parts[:5])
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty,
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception:
            continue
    return transactions

def parse_csob_dzibik(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_general(file_content, account_name)

def parse_csob_jenisov_czk(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_general(file_content, account_name)

def parse_csob_jenisov_eur(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_general(file_content, account_name)

def parse_csob_rr_strojka_czk(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_general(file_content, account_name)

def parse_csob_rr_strojka_eur(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_general(file_content, account_name)

def parse_csob_koruna_strojka_czk(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_general(file_content, account_name)

def parse_csob_koruna_strojka_eur(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_general(file_content, account_name)

# ---------- FIO Stalkin ----------
def parse_fio_stalkin(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1250')
        except:
            content = file_content.decode('latin-1')
    lines = content.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    if len(lines) < 3:
        return []
    header_idx = -1
    for i, line in enumerate(lines):
        if 'date' in line.lower() and 'volume' in line.lower() and 'currency' in line.lower():
            header_idx = i
            break
    if header_idx == -1:
        return []
    for line_idx in range(header_idx + 1, len(lines)):
        line = lines[line_idx]
        if not line:
            continue
        parts = line.split(';')
        if len(parts) < 3:
            continue
        try:
            date_str = parts[0].strip()
            date = parse_date(date_str)
            if not date:
                continue
            amount_str = parts[1].strip()
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            counterparty = parts[2].strip() if len(parts) > 2 else ''
            description = ' '.join(parts[3:]) if len(parts) > 3 else ''
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty[:200],
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except:
            continue
    return transactions

# ---------- Industra (AN14, Plavas1, KL59) ----------
def parse_industra_an14(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    df = read_excel_any_engine(file_content)
    if df is None or df.empty:
        return []
    header_row_idx = -1
    for idx, row in df.iterrows():
        if idx < 50:
            row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
            has_date = 'Дата транзакции' in row_str
            has_debit = 'Дебет' in row_str
            has_credit = 'Кредит' in row_str
            if has_date and has_debit and has_credit:
                header_row_idx = idx
                break
    if header_row_idx == -1:
        return []
    header_row = df.iloc[header_row_idx]
    col_indices = {}
    for idx, val in enumerate(header_row.values):
        if pd.isna(val):
            continue
        val_str = str(val).strip()
        if 'Дата транзакции' in val_str:
            col_indices['date'] = idx
        elif 'Получатель' in val_str or 'Плательщик' in val_str:
            col_indices['counterparty'] = idx
        elif 'Информация о транзакции' in val_str:
            col_indices['description'] = idx
        elif 'Дебет' in val_str and 'Кредит' not in val_str:
            col_indices['debit'] = idx
        elif 'Кредит' in val_str and 'Дебет' not in val_str:
            col_indices['credit'] = idx
    if 'date' not in col_indices:
        col_indices['date'] = 0
    if 'debit' not in col_indices:
        col_indices['debit'] = 11
    if 'credit' not in col_indices:
        col_indices['credit'] = 12
    for idx in range(header_row_idx + 1, len(df)):
        row = df.iloc[idx]
        row_values = [x for x in row.values if pd.notna(x)]
        if not row_values:
            continue
        try:
            date_str = ''
            if 'date' in col_indices and col_indices['date'] < len(row):
                date_str = str(row.iloc[col_indices['date']]).strip()
                if date_str == 'nan':
                    date_str = ''
            if not date_str:
                continue
            date = parse_date(date_str)
            if not date:
                continue
            amount = 0.0
            amount_found = False
            if 'debit' in col_indices and col_indices['debit'] < len(row):
                debit_val = row.iloc[col_indices['debit']]
                if pd.notna(debit_val) and debit_val != '':
                    debit_str = str(debit_val).strip().replace(',', '.').replace(' ', '')
                    if debit_str and debit_str != 'nan' and debit_str != '-':
                        parsed = parse_amount(debit_str)
                        if parsed != 0.0:
                            amount = -abs(parsed)
                            amount_found = True
            if not amount_found and 'credit' in col_indices and col_indices['credit'] < len(row):
                credit_val = row.iloc[col_indices['credit']]
                if pd.notna(credit_val) and credit_val != '':
                    credit_str = str(credit_val).strip().replace(',', '.').replace(' ', '')
                    if credit_str and credit_str != 'nan' and credit_str != '-':
                        parsed = parse_amount(credit_str)
                        if parsed != 0.0:
                            amount = parsed
                            amount_found = True
            if not amount_found:
                continue
            counterparty = ''
            if 'counterparty' in col_indices and col_indices['counterparty'] < len(row):
                counterparty = str(row.iloc[col_indices['counterparty']]).strip()
                if counterparty == 'nan':
                    counterparty = ''
            description = ''
            if 'description' in col_indices and col_indices['description'] < len(row):
                description = str(row.iloc[col_indices['description']]).strip()
                if description == 'nan':
                    description = ''
            if not description:
                desc_fields = ['description']
                for field in desc_fields:
                    if field in col_indices and col_indices[field] < len(row):
                        val = str(row.iloc[col_indices[field]]).strip()
                        if val and val != 'nan' and len(val) > 1:
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

def parse_industra_plavas1(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_industra_an14(file_content, account_name)

def parse_industra_kl59(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_industra_an14(file_content, account_name)

# ---------- Kapital bank Saida AZN ----------
def parse_kapital_saida_azn(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1250')
        except:
            content = file_content.decode('latin-1')
    lines = content.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    for line in lines:
        parts = line.split(';')
        if len(parts) < 3:
            continue
        try:
            date_str = parts[0].strip()
            date = parse_date(date_str)
            if not date:
                continue
            description = parts[1].strip() if len(parts) > 1 else ''
            amount_str = parts[2].strip().replace(',', '.') if len(parts) > 2 else ''
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': '',
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except:
            continue
    return transactions

def parse_kapital_saida_business(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_kapital_saida_azn(file_content, account_name)

# ---------- MASHREQ ----------
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
    header_row_idx = -1
    for idx, row in df.iterrows():
        if idx < 30:
            row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Date' in row_str and 'Description' in row_str and 'Credit' in row_str:
                header_row_idx = idx
                break
    if header_row_idx == -1:
        return []
    header_row = df.iloc[header_row_idx]
    col_indices = {}
    for idx, val in enumerate(header_row.values):
        if pd.isna(val):
            continue
        val_str = str(val).strip()
        if 'Date' in val_str and 'Value' not in val_str:
            col_indices['date'] = idx
        elif 'Value Date' in val_str:
            col_indices['value_date'] = idx
        elif 'Description' in val_str:
            col_indices['description'] = idx
        elif 'Credit' in val_str:
            col_indices['credit'] = idx
        elif 'Debit' in val_str:
            col_indices['debit'] = idx
        elif 'Balance' in val_str:
            col_indices['balance'] = idx
    if 'date' not in col_indices:
        col_indices['date'] = 0
    if 'credit' not in col_indices:
        col_indices['credit'] = 4
    if 'debit' not in col_indices:
        col_indices['debit'] = 5
    for idx in range(header_row_idx + 1, len(df)):
        row = df.iloc[idx]
        row_values = [x for x in row.values if pd.notna(x)]
        if not row_values:
            continue
        try:
            date_str = ''
            if 'date' in col_indices and col_indices['date'] < len(row):
                date_str = str(row.iloc[col_indices['date']]).strip()
                if date_str == 'nan':
                    date_str = ''
            if not date_str:
                continue
            date = parse_date(date_str)
            if not date:
                continue
            amount = 0.0
            amount_found = False
            if 'credit' in col_indices and col_indices['credit'] < len(row):
                credit_val = row.iloc[col_indices['credit']]
                if pd.notna(credit_val) and credit_val != '':
                    credit_str = str(credit_val).strip().replace(',', '').replace(' ', '')
                    if credit_str and credit_str != 'nan' and credit_str != '-':
                        parsed = parse_amount(credit_str)
                        if parsed != 0.0:
                            amount = parsed
                            amount_found = True
            if not amount_found and 'debit' in col_indices and col_indices['debit'] < len(row):
                debit_val = row.iloc[col_indices['debit']]
                if pd.notna(debit_val) and debit_val != '':
                    debit_str = str(debit_val).strip().replace(',', '').replace(' ', '')
                    if debit_str and debit_str != 'nan' and debit_str != '-':
                        parsed = parse_amount(debit_str)
                        if parsed != 0.0:
                            amount = -abs(parsed)
                            amount_found = True
            if not amount_found:
                continue
            counterparty = ''
            if 'description' in col_indices and col_indices['description'] < len(row):
                desc = str(row.iloc[col_indices['description']]).strip()
                if desc != 'nan':
                    parts = desc.split('/')
                    for part in parts:
                        part_clean = part.strip()
                        if part_clean and len(part_clean) > 2:
                            if 'REF' not in part_clean and 'SRN' not in part_clean and 'REC' not in part_clean:
                                if not re.match(r'^[A-Z0-9]{10,}$', part_clean):
                                    counterparty = part_clean[:200]
                                    break
            description = ''
            if 'description' in col_indices and col_indices['description'] < len(row):
                description = str(row.iloc[col_indices['description']]).strip()
                if description == 'nan':
                    description = ''
            if not description:
                desc_fields = ['description']
                for field in desc_fields:
                    if field in col_indices and col_indices[field] < len(row):
                        val = str(row.iloc[col_indices[field]]).strip()
                        if val and val != 'nan' and len(val) > 1:
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

# ---------- Revolut (AN14, NB, Plavas) ----------
def parse_revolut_an14(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1250')
        except:
            content = file_content.decode('latin-1')
    if content.startswith('\ufeff'):
        content = content[1:]
    lines = content.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    if len(lines) < 3:
        return []
    header_idx = -1
    for i, line in enumerate(lines):
        if 'Date started' in line and 'Description' in line:
            header_idx = i
            break
    if header_idx == -1:
        return []
    header_parts = lines[header_idx].split(',')
    date_idx = -1
    amount_idx = -1
    desc_idx = -1
    counterparty_idx = -1
    state_idx = -1
    type_idx = -1
    for i, col in enumerate(header_parts):
        col_clean = col.strip().strip('"')
        if 'Date started' in col_clean:
            date_idx = i
        elif col_clean == 'Amount':
            amount_idx = i
        elif 'Description' in col_clean:
            desc_idx = i
        elif 'Payer' in col_clean:
            counterparty_idx = i
        elif 'State' in col_clean:
            state_idx = i
        elif col_clean == 'Type':
            type_idx = i
    if date_idx == -1:
        date_idx = 0
    if amount_idx == -1:
        amount_idx = 14
    if desc_idx == -1:
        desc_idx = 5
    if type_idx == -1:
        type_idx = 3
    for line_idx in range(header_idx + 1, len(lines)):
        line = lines[line_idx]
        if not line:
            continue
        parts = []
        current = ''
        in_quotes = False
        for char in line:
            if char == '"':
                in_quotes = not in_quotes
            elif char == ',' and not in_quotes:
                parts.append(current.strip())
                current = ''
            else:
                current += char
        parts.append(current.strip())
        parts = [p.strip('"') for p in parts]
        if len(parts) < 3:
            continue
        try:
            if state_idx != -1 and state_idx < len(parts):
                state = parts[state_idx].strip()
                if state and state != 'COMPLETED':
                    continue
            date_str = parts[date_idx].strip() if date_idx < len(parts) else ''
            date = parse_date(date_str)
            if not date:
                continue
            amount_str = parts[amount_idx].strip() if amount_idx < len(parts) else ''
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            trans_type = ''
            if type_idx < len(parts):
                trans_type = parts[type_idx].strip()
            if trans_type == 'TOPUP':
                amount = abs(amount)
            elif trans_type == 'FEE':
                amount = -abs(amount)
            counterparty = ''
            if counterparty_idx != -1 and counterparty_idx < len(parts):
                counterparty = parts[counterparty_idx].strip()
                if counterparty == '' or counterparty == 'nan':
                    counterparty = ''
            description = parts[desc_idx].strip() if desc_idx < len(parts) else ''
            if not counterparty:
                match = re.search(r'To\s+([^,]+)', description)
                if match:
                    counterparty = match.group(1).strip()
                else:
                    match = re.search(r'from\s+([^,]+)', description)
                    if match:
                        counterparty = match.group(1).strip()
                    else:
                        counterparty = description[:200]
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

def parse_revolut_nb(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_revolut_an14(file_content, account_name)

def parse_revolut_plavas(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_revolut_an14(file_content, account_name)

# ---------- Paysera (общий) ----------
def parse_paysera_general(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    df = read_excel_any_engine(file_content, sheet_name='Worksheet')
    if df is None or df.empty:
        df = read_excel_any_engine(file_content)
    if df is None or df.empty:
        return []
    header_row_idx = -1
    for idx, row in df.iterrows():
        if idx < 30:
            row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
            has_type = 'Тип' in row_str
            has_date = 'Дата и время' in row_str
            has_amount = 'Сумма и валюта' in row_str
            if has_type and has_date and has_amount:
                header_row_idx = idx
                break
    if header_row_idx == -1:
        return []
    header_row = df.iloc[header_row_idx]
    col_indices = {}
    for idx, val in enumerate(header_row.values):
        if pd.isna(val):
            continue
        val_str = str(val).strip()
        if 'Дата и время' in val_str:
            col_indices['date'] = idx
        elif 'Получатель' in val_str or 'Плательщик' in val_str:
            col_indices['counterparty'] = idx
        elif 'Назначение платежа' in val_str:
            col_indices['purpose'] = idx
        elif 'Сумма и валюта' in val_str:
            col_indices['amount'] = idx
        elif 'Кредит / Дебет' in val_str:
            col_indices['type'] = idx
        elif 'Баланс' in val_str:
            col_indices['balance'] = idx
    if 'date' not in col_indices:
        col_indices['date'] = 3
    if 'amount' not in col_indices:
        col_indices['amount'] = 7
    if 'counterparty' not in col_indices:
        col_indices['counterparty'] = 4
    if 'purpose' not in col_indices:
        col_indices['purpose'] = 9
    if 'type' not in col_indices:
        col_indices['type'] = 11
    for idx in range(header_row_idx + 1, len(df)):
        row = df.iloc[idx]
        row_values = [x for x in row.values if pd.notna(x)]
        if not row_values:
            continue
        row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
        if 'Остаток' in row_str or 'Дебетовый оборот' in row_str or 'Кредитовый оборот' in row_str:
            continue
        try:
            date_str = ''
            if 'date' in col_indices and col_indices['date'] < len(row):
                date_str = str(row.iloc[col_indices['date']]).strip()
                if date_str == 'nan':
                    date_str = ''
            if not date_str:
                continue
            date_match = re.match(r'(\d{4}-\d{2}-\d{2})', date_str)
            if date_match:
                date_str = date_match.group(1)
            date = parse_date(date_str)
            if not date:
                continue
            amount = 0.0
            amount_found = False
            if 'amount' in col_indices and col_indices['amount'] < len(row):
                amount_val = row.iloc[col_indices['amount']]
                if pd.notna(amount_val) and amount_val != '':
                    amount_str = str(amount_val).strip().replace(',', '.').replace(' ', '')
                    amount_str = re.sub(r'[A-Za-z]+$', '', amount_str).strip()
                    if amount_str and amount_str != 'nan':
                        parsed = parse_amount(amount_str)
                        if parsed != 0.0:
                            trans_type = ''
                            if 'type' in col_indices and col_indices['type'] < len(row):
                                trans_type = str(row.iloc[col_indices['type']]).strip()
                            if trans_type == 'Д' or trans_type == 'D':
                                amount = -abs(parsed)
                            elif trans_type == 'К' or trans_type == 'C':
                                amount = abs(parsed)
                            else:
                                amount = parsed
                            amount_found = True
            if not amount_found:
                continue
            counterparty = ''
            if 'counterparty' in col_indices and col_indices['counterparty'] < len(row):
                counterparty = str(row.iloc[col_indices['counterparty']]).strip()
                if counterparty == 'nan':
                    counterparty = ''
            description = ''
            if 'purpose' in col_indices and col_indices['purpose'] < len(row):
                description = str(row.iloc[col_indices['purpose']]).strip()
                if description == 'nan':
                    description = ''
            if not description:
                desc_fields = ['purpose']
                for field in desc_fields:
                    if field in col_indices and col_indices[field] < len(row):
                        val = str(row.iloc[col_indices[field]]).strip()
                        if val and val != 'nan' and len(val) > 1:
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

def parse_paysera_baltic(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_general(file_content, account_name)

def parse_paysera_sveciy(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_general(file_content, account_name)

def parse_paysera_property(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_general(file_content, account_name)

def parse_paysera_rerum(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_general(file_content, account_name)

# ---------- WIO Business Bank ----------
def parse_wio_business(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1250')
        except:
            content = file_content.decode('latin-1')
    lines = content.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    if len(lines) < 3:
        return []
    header_idx = -1
    for i, line in enumerate(lines):
        if 'Account name' in line and 'Transaction type' in line:
            header_idx = i
            break
    if header_idx == -1:
        return []
    header_parts = lines[header_idx].split(',')
    amount_idx = -1
    date_idx = -1
    desc_idx = -1
    notes_idx = -1
    for i, col in enumerate(header_parts):
        col_clean = col.strip().strip('"')
        if col_clean == 'Amount':
            amount_idx = i
        elif col_clean == 'Date':
            date_idx = i
        elif col_clean == 'Description':
            desc_idx = i
        elif col_clean == 'Notes':
            notes_idx = i
    if amount_idx == -1:
        amount_idx = 10
    if date_idx == -1:
        date_idx = 7
    if desc_idx == -1:
        desc_idx = 9
    for line_idx in range(header_idx + 1, len(lines)):
        line = lines[line_idx]
        if not line:
            continue
        parts = []
        current = ''
        in_quotes = False
        for char in line:
            if char == '"':
                in_quotes = not in_quotes
            elif char == ',' and not in_quotes:
                parts.append(current.strip())
                current = ''
            else:
                current += char
        parts.append(current.strip())
        parts = [p.strip('"') for p in parts]
        if len(parts) < 3:
            continue
        try:
            date_str = parts[date_idx].strip() if date_idx < len(parts) else ''
            date = parse_date(date_str)
            if not date:
                continue
            amount_str = parts[amount_idx].strip() if amount_idx < len(parts) else ''
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            counterparty = ''
            description = parts[desc_idx].strip() if desc_idx < len(parts) else ''
            if description:
                desc_clean = re.sub(r'/REF/.*$', '', description)
                desc_clean = re.sub(r'FOR \d+$', '', desc_clean)
                desc_clean = desc_clean.strip()
                if desc_clean and len(desc_clean) > 2:
                    counterparty = desc_clean[:200]
                else:
                    counterparty = description[:200]
            full_description = description
            if notes_idx != -1 and notes_idx < len(parts):
                notes = parts[notes_idx].strip()
                if notes and notes != 'N/A' and notes != '':
                    full_description = f"{description} | {notes}" if description else notes
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty,
                'Наименование счета': account_name,
                'Описание': full_description[:500]
            })
        except Exception:
            continue
    return transactions

# ---------- Budapest MKB ----------
def parse_mkb_budapest_eur(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1250')
        except:
            content = file_content.decode('latin-1')
    lines = content.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    start_idx = -1
    for i, line in enumerate(lines):
        parts = line.split(';')
        if parts and re.match(r'^\d+\.?$', parts[0].strip()):
            start_idx = i
            break
    if start_idx == -1:
        return []
    for line_idx in range(start_idx, len(lines)):
        line = lines[line_idx]
        if not line:
            continue
        parts = line.split(';')
        if len(parts) < 10:
            continue
        try:
            if not re.match(r'^\d+\.?$', parts[0].strip()):
                continue
            date_str = parts[1].strip() if len(parts) > 1 else ''
            date = parse_date(date_str)
            if not date:
                continue
            amount_str = parts[9].strip() if len(parts) > 9 else ''
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            trans_type = parts[2].strip() if len(parts) > 2 else ''
            counterparty = parts[4].strip() if len(parts) > 4 else ''
            if counterparty in ['N/A', 'nan', '']:
                counterparty = ''
            description = parts[11].strip() if len(parts) > 11 else ''
            full_description = f"{trans_type} | {counterparty} | {description}" if counterparty else f"{trans_type} | {description}"
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty[:200],
                'Наименование счета': account_name,
                'Описание': full_description[:500]
            })
        except:
            continue
    return transactions

def parse_mkb_budapest_huf(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_mkb_budapest_eur(file_content, account_name)

# ---------- BUNDA LLC Pasha Bank ----------
def parse_bunda_pasha_aed(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1250')
        except:
            content = file_content.decode('latin-1')
    lines = content.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    for line in lines:
        parts = line.split(';')
        if len(parts) < 3:
            continue
        try:
            date_str = parts[0].strip()
            date = parse_date(date_str)
            if not date:
                continue
            description = parts[1].strip() if len(parts) > 1 else ''
            amount_str = parts[2].strip().replace(',', '.') if len(parts) > 2 else ''
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': '',
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except:
            continue
    return transactions

def parse_bunda_pasha_azn(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    df = read_excel_any_engine(file_content, sheet_name='Statement')
    if df is None or df.empty:
        df = read_excel_any_engine(file_content)
    if df is None or df.empty:
        return []
    header_row_idx = -1
    for idx, row in df.iterrows():
        if idx < 30:
            row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Əməliyyat tarixi' in row_str or 'Əməliyyat' in row_str:
                header_row_idx = idx
                break
    if header_row_idx == -1:
        return []
    header_row = df.iloc[header_row_idx]
    col_indices = {}
    for idx, val in enumerate(header_row.values):
        if pd.isna(val):
            continue
        val_str = str(val).strip()
        if 'Əməliyyat tarixi' in val_str or 'Tarix' in val_str:
            col_indices['date'] = idx
        elif 'İcra tarixi' in val_str:
            col_indices['exec_date'] = idx
        elif 'Ödəyən' in val_str or 'Benefisiar' in val_str:
            col_indices['payee'] = idx
        elif 'Təyinat' in val_str:
            col_indices['purpose'] = idx
        elif 'Mədaxil' in val_str:
            col_indices['income'] = idx
        elif 'Məxaric' in val_str:
            col_indices['expense'] = idx
        elif 'Balans' in val_str:
            col_indices['balance'] = idx
    if 'date' not in col_indices:
        col_indices['date'] = 0
    if 'income' not in col_indices:
        col_indices['income'] = 6
    if 'expense' not in col_indices:
        col_indices['expense'] = 7
    for idx in range(header_row_idx + 1, len(df)):
        row = df.iloc[idx]
        row_values = [x for x in row.values if pd.notna(x)]
        if not row_values:
            continue
        row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
        if 'DÖVRÜN SONUNA BALANS' in row_str or 'MÖVCUD BALANS' in row_str:
            continue
        try:
            date_str = ''
            if 'date' in col_indices and col_indices['date'] < len(row):
                date_str = str(row.iloc[col_indices['date']]).strip()
                if date_str == 'nan':
                    date_str = ''
            if not date_str:
                continue
            date = parse_date(date_str)
            if not date:
                continue
            amount = 0.0
            amount_found = False
            if 'income' in col_indices and col_indices['income'] < len(row):
                income_val = row.iloc[col_indices['income']]
                if pd.notna(income_val) and income_val != '':
                    income_str = str(income_val).strip().replace(',', '.').replace(' ', '')
                    if income_str and income_str != 'nan':
                        parsed = parse_amount(income_str)
                        if parsed != 0.0:
                            amount = parsed
                            amount_found = True
            if not amount_found and 'expense' in col_indices and col_indices['expense'] < len(row):
                expense_val = row.iloc[col_indices['expense']]
                if pd.notna(expense_val) and expense_val != '':
                    expense_str = str(expense_val).strip().replace(',', '.').replace(' ', '')
                    if expense_str and expense_str != 'nan':
                        parsed = parse_amount(expense_str)
                        if parsed != 0.0:
                            amount = -abs(parsed)
                            amount_found = True
            if not amount_found:
                continue
            counterparty = ''
            if 'payee' in col_indices and col_indices['payee'] < len(row):
                counterparty = str(row.iloc[col_indices['payee']]).strip()
                if counterparty == 'nan':
                    counterparty = ''
            description = ''
            if 'purpose' in col_indices and col_indices['purpose'] < len(row):
                description = str(row.iloc[col_indices['purpose']]).strip()
                if description == 'nan':
                    description = ''
            if not description:
                desc_fields = ['purpose', 'payee']
                for field in desc_fields:
                    if field in col_indices and col_indices[field] < len(row):
                        val = str(row.iloc[col_indices[field]]).strip()
                        if val and val != 'nan' and len(val) > 1:
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

# ---------- RAK BANK ----------
def parse_rak_bank(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1250')
        except:
            content = file_content.decode('latin-1')
    lines = content.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    for line in lines:
        parts = line.split(';')
        if len(parts) < 3:
            continue
        try:
            date_str = parts[0].strip()
            date = parse_date(date_str)
            if not date:
                continue
            description = parts[1].strip() if len(parts) > 1 else ''
            amount_str = parts[2].strip().replace(',', '.') if len(parts) > 2 else ''
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': '',
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except:
            continue
    return transactions

# ---------- UniCredit (Koruna, B1, Garpiz, TwoHills) ----------
def parse_unicredit_koruna(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1250')
        except:
            content = file_content.decode('latin-1')
    lines = content.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    if len(lines) < 3:
        return []
    header_idx = -1
    for i, line in enumerate(lines):
        if 'From Account' in line and 'Amount' in line and 'Currency' in line:
            header_idx = i
            break
    if header_idx == -1:
        return []
    header_parts = lines[header_idx].split(';')
    amount_idx = -1
    date_idx = -1
    desc_idx = -1
    counterparty_idx = -1
    for i, col in enumerate(header_parts):
        col_clean = col.strip()
        if col_clean == 'Amount':
            amount_idx = i
        elif col_clean == 'Booking Date':
            date_idx = i
        elif col_clean == 'Transaction Details':
            desc_idx = i
        elif col_clean == 'Name':
            counterparty_idx = i
    if amount_idx == -1:
        amount_idx = 1
    if date_idx == -1:
        date_idx = 3
    if desc_idx == -1:
        desc_idx = 13
    if counterparty_idx == -1:
        counterparty_idx = 9
    for line_idx in range(header_idx + 1, len(lines)):
        line = lines[line_idx]
        if not line:
            continue
        parts = line.split(';')
        while parts and parts[-1] == '':
            parts.pop()
        if len(parts) < 3:
            continue
        try:
            amount_str = parts[amount_idx].strip() if amount_idx < len(parts) else ''
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            date_str = parts[date_idx].strip() if date_idx < len(parts) else ''
            date = parse_date(date_str)
            if not date:
                continue
            counterparty = ''
            if counterparty_idx < len(parts):
                counterparty = parts[counterparty_idx].strip()
                if counterparty and counterparty != '' and counterparty != 'nan':
                    counterparty = counterparty[:200]
            if not counterparty:
                if len(parts) > 8:
                    counterparty = parts[8].strip()
                    if counterparty and counterparty != '' and counterparty != 'nan':
                        counterparty = counterparty[:200]
            description = ''
            if desc_idx < len(parts):
                description = parts[desc_idx].strip()
                if description and description != '' and description != 'nan':
                    description = description
            if not description:
                desc_fields = [14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28]
                for idx in desc_fields:
                    if idx < len(parts):
                        val = parts[idx].strip()
                        if val and val != '' and val != 'nan' and len(val) > 1:
                            if not re.match(r'^[\d.,\-]+$', val):
                                if len(val) > 3:
                                    description = val[:500]
                                    break
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty,
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception:
            continue
    return transactions

def parse_unicredit_b1_estate(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unicredit_koruna(file_content, account_name)

def parse_garpiz_unicredit(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unicredit_koruna(file_content, account_name)

def parse_garpiz_pernink(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unicredit_koruna(file_content, account_name)

def parse_unicredit_twohills(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unicredit_koruna(file_content, account_name)

# ---------- Saida N26, Wise ----------
def parse_saida_n26(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1250')
        except:
            content = file_content.decode('latin-1')
    lines = content.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    if len(lines) < 3:
        return []
    header_idx = -1
    for i, line in enumerate(lines):
        if 'date' in line.lower() and 'amount' in line.lower():
            header_idx = i
            break
    if header_idx == -1:
        return []
    for line_idx in range(header_idx + 1, len(lines)):
        line = lines[line_idx]
        if not line:
            continue
        parts = line.split(';')
        if len(parts) < 3:
            continue
        try:
            date_str = parts[0].strip()
            date = parse_date(date_str)
            if not date:
                continue
            amount_str = parts[1].strip().replace(',', '.')
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            description = ' '.join(parts[2:]) if len(parts) > 2 else ''
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': '',
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except:
            continue
    return transactions

def parse_saida_wise(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_saida_n26(file_content, account_name)

# ---------- УНИВЕРСАЛЬНЫЙ ПАРСЕР ----------
def parse_unknown(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1250')
        except:
            content = file_content.decode('latin-1')
    lines = content.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    for line in lines:
        parts = line.split(';')
        if len(parts) < 2:
            continue
        try:
            date = None
            amount = 0.0
            description = ''
            counterparty = ''
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                parsed_date = parse_date(part)
                if parsed_date and parsed_date != part and len(parsed_date) == 10:
                    if not date:
                        date = parsed_date
                    continue
                parsed_amount = parse_amount(part)
                if parsed_amount != 0.0:
                    if amount == 0.0:
                        amount = parsed_amount
                    continue
                if len(part) > 2 and not re.match(r'^[\d.,\-]+$', part):
                    if not counterparty and len(part) < 100:
                        counterparty = part[:200]
                    else:
                        description += part + ' '
            if date and amount != 0.0:
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': counterparty[:200] if counterparty else '',
                    'Наименование счета': account_name,
                    'Описание': description[:500]
                })
        except:
            continue
    return transactions

# ==================== ОСНОВНОЙ ПАРСЕР ====================

def parse_file(file_content: bytes, filename: str) -> Tuple[List[Dict], str]:
    """
    Возвращает (транзакции, имя_парсера).
    Имя парсера полезно для отладки.
    """
    account_name = clean_account_name(filename)
    ext = os.path.splitext(filename)[1].lower()
    
    # ---------- DOCX ----------
    if ext == '.docx':
        if 'Regina Alfa' in account_name:
            return parse_regina_alfa_docx(file_content, account_name), 'parse_regina_alfa_docx'
        if 'Tinkoff' in account_name:
            return parse_tinkoff_docx(file_content, account_name), 'parse_tinkoff_docx'
        return parse_unknown(file_content, account_name), 'parse_unknown'
    
    # ---------- PDF ----------
    if ext == '.pdf':
        if 'Regina Alfa' in account_name:
            return parse_regina_alfa_pdf(file_content, account_name), 'parse_regina_alfa_pdf'
        return parse_unknown(file_content, account_name), 'parse_unknown'
    
    # ---------- XLS / XLSX / CSV ----------
    account_parsers = {
        'Regina Alfa bank NOMIQA RUB': parse_regina_alfa,
        'Tinkoff RUB': parse_tinkoff,
        'BSR Estate EUR BluOr 2': parse_bsr_bluor_2,
        'BSR Estate EUR BluOr 3': parse_bsr_bluor_3,
        'KL59 Rev NB EUR BluOR': parse_kl59_rev_nb_bluor,
        'JenHor Unelma CZK CSAS': parse_jenhor_unelma,
        'DŽIBIK Main CSOB CZK': parse_csob_dzibik,
        'JENISOV HORSKA CSOB CZK': parse_csob_jenisov_czk,
        'JENISOV HORSKA S R EUR': parse_csob_jenisov_eur,
        'RR Strojka CZK CSOB': parse_csob_rr_strojka_czk,
        'RR Strojka EUR CSOB': parse_csob_rr_strojka_eur,
        'Koruna Strojka CZK CSOB': parse_csob_koruna_strojka_czk,
        'Koruna Strojka EUR CSOB': parse_csob_koruna_strojka_eur,
        'Stalkin ML2 CZK FIO': parse_fio_stalkin,
        'AN14 Estate EUR Industra': parse_industra_an14,
        'Plavas1 Estate EUR Industra': parse_industra_plavas1,
        'KL59 Rev NB EUR Industra': parse_industra_kl59,
        'P1 statement': parse_industra_plavas1,   # ← ДОБАВЛЕНО
        'Kapital bank Saida AZN': parse_kapital_saida_azn,
        'Kapital bank Saida AZN бизнес счет': parse_kapital_saida_business,
        'MASHREQ BANK AED NOMIQA': parse_mashreq,
        'Budapest EUR MKB': parse_mkb_budapest_eur,
        'Budapest HUF MKB': parse_mkb_budapest_huf,
        'Saida N26': parse_saida_n26,
        'BUNDA LLC Pasha Bank AED дирхам': parse_bunda_pasha_aed,
        'BUNDA LLC Pasha Bank AZN': parse_bunda_pasha_azn,
        'Paysera Baltic Solutions EUR': parse_paysera_baltic,
        'Paysera Sveciy Namai Lithuania EUR': parse_paysera_sveciy,
        'Paysera BS PROPERTY SIA': parse_paysera_property,
        'Paysera BS RERUM SIA': parse_paysera_rerum,
        'RAK BANK Nomiqa клиенты': parse_rak_bank,
        'AN14 Estate EUR Revolut': parse_revolut_an14,   # ← проверено, есть
        'NB Rev EUR Revolut': parse_revolut_nb,
        'Revolut Plavas 1 SIA': parse_revolut_plavas,
        'B1 Estate CZK UC': parse_unicredit_b1_estate,
        'Garpiz UniCredit Bank CZK': parse_garpiz_unicredit,
        'Garpiz Pernink CZK UC': parse_garpiz_pernink,
        'Koruna UniCredit CZK': parse_unicredit_koruna,
        'TwoHills Molly Unicredit CZK': parse_unicredit_twohills,
        'WIO Business Bank': parse_wio_business,
        'Saida Wise': parse_saida_wise,
    }
    
    # 1) Точное совпадение
    if account_name in account_parsers:
        func = account_parsers[account_name]
        return func(file_content, account_name), f"точное: {func.__name__}"
    
    # 2) Частичное совпадение по ключевым словам
    for acc_name, func in account_parsers.items():
        acc_keywords = set(acc_name.lower().split())
        file_keywords = set(account_name.lower().split())
        common = acc_keywords.intersection(file_keywords)
        if len(common) >= len(acc_keywords) * 0.6 and len(common) > 0:
            return func(file_content, account_name), f"частичное: {acc_name} → {func.__name__}"
    
    # 3) Универсальный
    return parse_unknown(file_content, account_name), 'parse_unknown'

# ==================== ОСНОВНОЙ ИНТЕРФЕЙС ====================

def main():
    # ---- Заголовок раздела ----
    st.markdown("### 📥 Загрузка файлов")
    st.markdown("Перетащите выписки в окно ниже или нажмите **Browse files**.")
    
    uploaded_files = st.file_uploader(
        "Выберите файлы",
        type=['csv', 'xlsx', 'xls', 'docx', 'pdf'],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )
    
    # ---- Подсказки-карточки ----
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
        
        if st.button("🚀 Обработать файлы", use_container_width=False):
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
                    
                    if transactions:
                        all_transactions.extend(transactions)
                        file_stats.append(f"✅ {uploaded_file.name}: {len(transactions)} операций")
                        debug_info.append(f"🔍 {uploaded_file.name} → парсер: `{parser_name}`")
                    else:
                        file_stats.append(f"ℹ️ {uploaded_file.name}: транзакций не найдено")
                        debug_info.append(f"🔍 {uploaded_file.name} → парсер: `{parser_name}` (пусто)")
                        
                except Exception as e:
                    failed_files.append(f"{uploaded_file.name} (ошибка: {str(e)})")
                    debug_info.append(f"❌ {uploaded_file.name} → исключение: {str(e)}")
                
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            status_text.text("✅ Обработка завершена!")
            
            st.markdown("### 📋 Результат обработки")
            for stat in file_stats:
                st.info(stat)
            
            # ---- Отладочная информация ----
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
                
                total_sum = df['Сумма_число'].sum()
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
                
                st.dataframe(
                    df.drop(columns=['Сумма_число']),
                    use_container_width=True,
                    hide_index=True
                )
                
                # ---- Excel ----
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_display = df.drop(columns=['Сумма_число'])
                    df_display.to_excel(writer, sheet_name='Транзакции', index=False)
                    
                    bank_summary = df.groupby('Наименование счета').agg({
                        'Сумма_число': ['count', 'sum']
                    }).round(2)
                    bank_summary.columns = ['Количество операций', 'Сумма']
                    bank_summary['Сумма'] = bank_summary['Сумма'].apply(
                        lambda x: f"{x:,.2f}".replace('.', ',')
                    )
                    bank_summary.to_excel(writer, sheet_name='Сводка по счетам')
                
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
    
    # ---- Футер ----
    st.markdown("""
    <div class="footer-note">
      Работает локально. Данные никуда не отправляются.
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
