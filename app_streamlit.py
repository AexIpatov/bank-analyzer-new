import streamlit as st
import pandas as pd
import os
import re
import tempfile
import chardet
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Tuple, Optional

st.set_page_config(page_title="Аналитик банковских выписок", page_icon="🏦", layout="wide")

st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    padding: 1.5rem;
    border-radius: 20px;
    color: white;
    text-align: center;
    margin-bottom: 2rem;
}
.stButton > button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>🏦 Аналитик банковских выписок</h1><p>Поддержка CSV, XLSX, XLS форматов</p></div>', unsafe_allow_html=True)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def detect_file_encoding(file_path: str) -> str:
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)
        result = chardet.detect(raw_data)
        return result['encoding'] if result['encoding'] else 'utf-8'
    except:
        return 'utf-8'

def detect_csv_delimiter(file_path: str) -> str:
    delimiters = [';', ',', '\t', '|']
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            first_line = f.readline()
        counts = {}
        for delim in delimiters:
            counts[delim] = first_line.count(delim)
        max_delim = max(counts, key=counts.get)
        return max_delim if counts[max_delim] > 0 else ';'
    except:
        return ';'

def clean_account_name(filename: str) -> str:
    name = os.path.splitext(filename)[0]
    name = re.sub(r'\d{4}-\d{2}-\d{2}', '', name)
    name = re.sub(r'[_-]', ' ', name).strip()
    name = re.sub(r'\s+', ' ', name)
    return name if name else 'Неизвестный счет'

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
    
    if amount_str in ['', 'nan', '-', 'None', 'null', 'NaN', 'N/A', 'n/a', '0', '0.0']:
        return 0.0
    
    amount_str = amount_str.replace(' ', '')
    
    is_negative = False
    if amount_str.startswith('-'):
        is_negative = True
        amount_str = amount_str[1:]
    elif amount_str.startswith('(') and amount_str.endswith(')'):
        is_negative = True
        amount_str = amount_str[1:-1]
    
    amount_str = re.sub(r'\s*[A-Z]{3}\s*$', '', amount_str)
    amount_str = re.sub(r'^\s*[A-Z]{3}\s*', '', amount_str)
    amount_str = amount_str.replace(',', '.')
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
    formatted = f"{amount:.2f}".replace('.', ',')
    if ',' in formatted:
        integer_part, decimal_part = formatted.split(',')
        integer_part = re.sub(r'(?<=\d)(?=(\d{3})+(?!\d))', ' ', integer_part)
        return f"{integer_part},{decimal_part}"
    return formatted

# ==================== ПАРСЕР BLUOR EXCEL (ИСПРАВЛЕННЫЙ) ====================

def parse_bluor_excel(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """Парсер для выписок BluOr Bank (формат с Дебет/Кредит)"""
    transactions = []
    
    # Ищем строки с транзакциями
    for idx, row in df.iterrows():
        try:
            if len(row) < 4:
                continue
            
            # Проверяем первую колонку - это должна быть дата
            date_val = row.iloc[0] if len(row) > 0 else None
            if pd.isna(date_val):
                continue
            
            date_str = str(date_val).strip()
            
            # Пропускаем пустые строки
            if not date_str:
                continue
            
            # Пропускаем строки с текстом (не даты)
            skip_text = [
                'выписка', 'направления', 'сумма', 'получатель',
                'информация', 'bs rerum', 'рег', 'счет', 'период',
                'подготовлено', 'точное', 'показывать', 'дата предыдущей',
                'начальный остаток', 'кредитовый оборот', 'дебетовый оборот',
                'конечный остаток', 'per-on', 'per-on::', 'кредитовый', 'дебетовый',
                'дебет (d)', 'кредит (c)'
            ]
            
            date_lower = date_str.lower()
            if any(kw in date_lower for kw in skip_text):
                continue
            
            # Проверяем, что это дата в формате ДД.ММ.ГГГГ
            date_parts = date_str.split('.')
            if len(date_parts) == 3:
                try:
                    day = int(date_parts[0])
                    month = int(date_parts[1])
                    year = int(date_parts[2])
                    if 1 <= day <= 31 and 1 <= month <= 12 and 1000 <= year <= 9999:
                        date = f"{day:02d}-{month:02d}-{year}"
                    else:
                        continue
                except:
                    continue
            else:
                continue
            
            # Описание (колонка 1)
            desc_val = row.iloc[1] if len(row) > 1 else ''
            description = str(desc_val) if pd.notna(desc_val) else ''
            
            if not description:
                continue
            
            # Пропускаем строки с итогами в описании
            if any(kw in description.lower() for kw in [
                'кредитовый оборот', 'дебетовый оборот', 'конечный остаток',
                'начальный остаток', 'дебетовый оборот:', 'кредитовый оборот:'
            ]):
                continue
            
            # Сумма (колонка 2 - Дебет или колонка 3 - Кредит)
            amount = 0.0
            
            # Проверяем Дебет (колонка 2)
            if len(row) > 2:
                debit_val = row.iloc[2]
                if pd.notna(debit_val):
                    debit_str = str(debit_val).strip()
                    # Пропускаем очень большие числа (остатки)
                    if debit_str and '130' not in debit_str:
                        amount = parse_amount(debit_str)
            
            # Если в дебете 0, проверяем Кредит (колонка 3)
            if amount == 0.0 and len(row) > 3:
                credit_val = row.iloc[3]
                if pd.notna(credit_val):
                    credit_str = str(credit_val).strip()
                    # Пропускаем очень большие числа (остатки)
                    if credit_str and '130' not in credit_str:
                        amount = parse_amount(credit_str)
            
            if amount == 0.0:
                continue
            
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': '',
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception as e:
            continue
    
    return transactions

# ==================== ПАРСЕР FIO ====================

def parse_fio(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    
    header_row = -1
    for idx in range(min(10, len(df))):
        row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        if 'date' in row_text and 'volume' in row_text and 'currency' in row_text:
            header_row = idx
            break
    
    if header_row == -1:
        return []
    
    headers = []
    for val in df.iloc[header_row].values:
        if pd.isna(val):
            headers.append('')
        else:
            headers.append(str(val).strip())
    
    data_rows = []
    for idx in range(header_row + 1, len(df)):
        row = list(df.iloc[idx].values)
        if all(pd.isna(x) or str(x).strip() == '' for x in row):
            continue
        if len(row) < len(headers):
            row.extend([''] * (len(headers) - len(row)))
        data_rows.append(row[:len(headers)])
    
    if not data_rows:
        return []
    
    df_clean = pd.DataFrame(data_rows, columns=headers)
    
    date_col = None
    amount_col = None
    desc_col = None
    counterparty_col = None
    
    for col in df_clean.columns:
        col_lower = str(col).lower()
        if col_lower == 'date':
            date_col = col
        elif col_lower == 'volume':
            amount_col = col
        elif col_lower == 'message for beneficiary' or col_lower == 'note':
            if desc_col is None:
                desc_col = col
        elif col_lower == 'note':
            counterparty_col = col
    
    if date_col is None or amount_col is None:
        return []
    
    for idx, row in df_clean.iterrows():
        try:
            if date_col not in row:
                continue
            date_val = row[date_col]
            if pd.isna(date_val):
                continue
            date = parse_date(str(date_val))
            if not date:
                continue
            
            if amount_col not in row:
                continue
            amount = parse_amount(row[amount_col])
            if amount == 0.0:
                continue
            
            description = ''
            if desc_col and desc_col in row and pd.notna(row[desc_col]):
                description = str(row[desc_col])
            
            counterparty = ''
            if counterparty_col and counterparty_col in row and pd.notna(row[counterparty_col]):
                counterparty = str(row[counterparty_col])
            
            if not description:
                desc_parts = []
                for col in df_clean.columns:
                    if col not in [date_col, amount_col, counterparty_col]:
                        val = row[col]
                        if pd.notna(val) and str(val).strip():
                            desc_parts.append(str(val))
                if desc_parts:
                    description = ' '.join(desc_parts)
            
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty[:200] if counterparty else '',
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception as e:
            continue
    
    return transactions

# ==================== ПАРСЕР B1 ESTATE (UniCredit) ====================

def parse_b1_estate(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    
    header_row = -1
    for idx in range(len(df)):
        row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        if 'from account' in row_text and 'amount' in row_text:
            header_row = idx
            break
    
    if header_row == -1:
        return []
    
    headers_raw = []
    for val in df.iloc[header_row].values:
        if pd.isna(val):
            headers_raw.append('')
        else:
            headers_raw.append(str(val).strip())
    
    headers = []
    counter = {}
    for h in headers_raw:
        if h == '':
            headers.append('col')
            continue
        if h in counter:
            counter[h] += 1
            headers.append(f"{h}_{counter[h]}")
        else:
            counter[h] = 1
            headers.append(h)
    
    data_rows = []
    for idx in range(header_row + 1, len(df)):
        row = list(df.iloc[idx].values)
        if len(row) < len(headers):
            row.extend([''] * (len(headers) - len(row)))
        data_rows.append(row[:len(headers)])
    
    if not data_rows:
        return []
    
    df_clean = pd.DataFrame(data_rows, columns=headers)
    
    amount_col = None
    date_col = None
    desc_col = None
    counterparty_col = None
    
    for col in df_clean.columns:
        col_lower = str(col).lower()
        if col_lower == 'amount':
            amount_col = col
        elif col_lower == 'booking date':
            date_col = col
        elif col_lower == 'transaction details':
            if desc_col is None:
                desc_col = col
        elif col_lower == 'name':
            counterparty_col = col
    
    if amount_col is None and len(df_clean.columns) > 1:
        amount_col = df_clean.columns[1]
    if date_col is None and len(df_clean.columns) > 3:
        date_col = df_clean.columns[3]
    if desc_col is None and len(df_clean.columns) > 12:
        desc_col = df_clean.columns[12]
    
    if amount_col is None or date_col is None:
        return []
    
    for idx, row in df_clean.iterrows():
        try:
            if date_col not in row:
                continue
            date_val = row[date_col]
            if pd.isna(date_val):
                continue
            date = parse_date(str(date_val))
            if not date:
                continue
            
            if amount_col not in row:
                continue
            amount = parse_amount(row[amount_col])
            if amount == 0.0:
                continue
            
            description = ''
            if desc_col and desc_col in row and pd.notna(row[desc_col]):
                description = str(row[desc_col])
            
            counterparty = ''
            if counterparty_col and counterparty_col in row and pd.notna(row[counterparty_col]):
                counterparty = str(row[counterparty_col])
            
            if not description:
                desc_parts = []
                for col in df_clean.columns:
                    if col not in [date_col, amount_col, counterparty_col]:
                        val = row[col]
                        if pd.notna(val) and str(val).strip():
                            desc_parts.append(str(val))
                if desc_parts:
                    description = ' '.join(desc_parts)
            
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty[:200] if counterparty else '',
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception as e:
            continue
    
    return transactions

# ==================== ПАРСЕР CSOB ====================

def parse_csob(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    
    header_row = -1
    for idx in range(min(50, len(df))):
        row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        if 'account number' in row_text and 'account currency' in row_text:
            header_row = idx
            break
    
    if header_row == -1:
        return []
    
    headers = []
    for val in df.iloc[header_row].values:
        if pd.isna(val):
            headers.append('')
        else:
            headers.append(str(val).strip())
    
    while headers and headers[-1] == '':
        headers.pop()
    
    data_rows = []
    for idx in range(header_row + 1, len(df)):
        row = list(df.iloc[idx].values)
        if all(pd.isna(x) or str(x).strip() == '' for x in row):
            continue
        if len(row) < len(headers):
            row.extend([''] * (len(headers) - len(row)))
        data_rows.append(row[:len(headers)])
    
    if not data_rows:
        return []
    
    df_clean = pd.DataFrame(data_rows, columns=headers)
    
    date_col = None
    amount_col = None
    desc_col = None
    counterparty_col = None
    
    for col in df_clean.columns:
        col_lower = str(col).lower()
        if 'posting date' in col_lower:
            date_col = col
        elif 'payment amount' in col_lower:
            amount_col = col
        elif 'message to beneficiary' in col_lower or 'note' in col_lower:
            desc_col = col
        elif 'counterparty' in col_lower:
            counterparty_col = col
    
    if date_col is None and len(df_clean.columns) > 4:
        date_col = df_clean.columns[4]
    if amount_col is None and len(df_clean.columns) > 6:
        amount_col = df_clean.columns[6]
    
    if date_col is None or amount_col is None:
        return []
    
    for idx, row in df_clean.iterrows():
        try:
            if date_col not in row:
                continue
            date_val = row[date_col]
            if pd.isna(date_val):
                continue
            date = parse_date(str(date_val))
            if not date:
                continue
            
            if amount_col not in row:
                continue
            amount = parse_amount(row[amount_col])
            if amount == 0.0:
                continue
            
            description = ''
            if desc_col and desc_col in row and pd.notna(row[desc_col]):
                description = str(row[desc_col])
            
            counterparty = ''
            if counterparty_col and counterparty_col in row and pd.notna(row[counterparty_col]):
                counterparty = str(row[counterparty_col])
            
            if not description:
                desc_parts = []
                for col in df_clean.columns:
                    if col not in [date_col, amount_col, counterparty_col]:
                        val = row[col]
                        if pd.notna(val) and str(val).strip():
                            desc_parts.append(str(val))
                if desc_parts:
                    description = ' '.join(desc_parts)
            
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty[:200] if counterparty else '',
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception as e:
            continue
    
    return transactions

# ==================== ПАРСЕР REVOLUT ====================

def parse_revolut(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    
    header_row = -1
    for idx in range(min(30, len(df))):
        row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        if 'date started' in row_text and 'amount' in row_text:
            header_row = idx
            break
    
    if header_row == -1:
        return []
    
    headers = []
    for val in df.iloc[header_row].values:
        if pd.isna(val):
            headers.append('')
        else:
            headers.append(str(val).strip())
    
    data_rows = []
    for idx in range(header_row + 1, len(df)):
        row = list(df.iloc[idx].values)
        if len(row) < len(headers):
            row.extend([''] * (len(headers) - len(row)))
        data_rows.append(row[:len(headers)])
    
    if not data_rows:
        return []
    
    df_clean = pd.DataFrame(data_rows, columns=headers)
    
    date_col = None
    amount_col = None
    desc_col = None
    counterparty_col = None
    
    for col in df_clean.columns:
        col_lower = str(col).lower()
        if 'date started' in col_lower:
            date_col = col
        elif 'amount' in col_lower:
            amount_col = col
        elif 'description' in col_lower:
            desc_col = col
        elif 'beneficiary name' in col_lower or 'sender name' in col_lower:
            counterparty_col = col
    
    if date_col is None or amount_col is None:
        return []
    
    for idx, row in df_clean.iterrows():
        try:
            if date_col not in row:
                continue
            date_val = row[date_col]
            if pd.isna(date_val):
                continue
            date = parse_date(str(date_val))
            if not date:
                continue
            
            if amount_col not in row:
                continue
            amount = parse_amount(row[amount_col])
            if amount == 0.0:
                continue
            
            description = ''
            if desc_col and desc_col in row and pd.notna(row[desc_col]):
                description = str(row[desc_col])
            
            counterparty = ''
            if counterparty_col and counterparty_col in row and pd.notna(row[counterparty_col]):
                counterparty = str(row[counterparty_col])
            
            if not description:
                desc_parts = []
                for col in df_clean.columns:
                    if col not in [date_col, amount_col, counterparty_col]:
                        val = row[col]
                        if pd.notna(val) and str(val).strip():
                            desc_parts.append(str(val))
                if desc_parts:
                    description = ' '.join(desc_parts)
            
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty[:200] if counterparty else '',
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception as e:
            continue
    
    return transactions

# ==================== ПАРСЕР PAYSERA ====================

def parse_paysera(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    
    header_row = -1
    for idx in range(min(30, len(df))):
        row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        if 'дата и время' in row_text and 'сумма и валюта' in row_text:
            header_row = idx
            break
    
    if header_row == -1:
        return []
    
    headers = []
    for val in df.iloc[header_row].values:
        if pd.isna(val):
            headers.append('')
        else:
            headers.append(str(val).strip())
    
    data_rows = []
    for idx in range(header_row + 1, len(df)):
        row = list(df.iloc[idx].values)
        if len(row) < len(headers):
            row.extend([''] * (len(headers) - len(row)))
        data_rows.append(row[:len(headers)])
    
    if not data_rows:
        return []
    
    df_clean = pd.DataFrame(data_rows, columns=headers)
    
    date_col = None
    amount_col = None
    desc_col = None
    counterparty_col = None
    credit_debit_col = None
    
    for col in df_clean.columns:
        col_lower = str(col).lower()
        if 'дата и время' in col_lower or 'дата' in col_lower:
            date_col = col
        elif 'сумма и валюта' in col_lower or 'сумма' in col_lower:
            amount_col = col
        elif 'назначение платежа' in col_lower or 'описание' in col_lower:
            desc_col = col
        elif 'получатель' in col_lower or 'плательщик' in col_lower:
            counterparty_col = col
        elif 'кредит' in col_lower or 'дебет' in col_lower:
            credit_debit_col = col
    
    if date_col is None or amount_col is None:
        return []
    
    for idx, row in df_clean.iterrows():
        try:
            if date_col not in row:
                continue
            date_val = row[date_col]
            if pd.isna(date_val):
                continue
            date = parse_date(str(date_val))
            if not date:
                continue
            
            if amount_col not in row:
                continue
            
            amount = parse_amount(row[amount_col])
            
            if credit_debit_col and credit_debit_col in row:
                cd_val = str(row[credit_debit_col]).strip().lower()
                if cd_val == 'д' or cd_val == 'debit':
                    amount = -abs(amount)
                elif cd_val == 'к' or cd_val == 'credit':
                    amount = abs(amount)
            
            if amount == 0.0:
                continue
            
            description = ''
            if desc_col and desc_col in row and pd.notna(row[desc_col]):
                description = str(row[desc_col])
            
            counterparty = ''
            if counterparty_col and counterparty_col in row and pd.notna(row[counterparty_col]):
                counterparty = str(row[counterparty_col])
            
            if not description:
                desc_parts = []
                for col in df_clean.columns:
                    if col not in [date_col, amount_col, counterparty_col, credit_debit_col]:
                        val = row[col]
                        if pd.notna(val) and str(val).strip():
                            desc_parts.append(str(val))
                if desc_parts:
                    description = ' '.join(desc_parts)
            
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty[:200] if counterparty else '',
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception as e:
            continue
    
    return transactions

# ==================== ПАРСЕР MKB ====================

def parse_mkb(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    
    header_row = -1
    for idx in range(min(50, len(df))):
        row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        if 'sorszám' in row_text and 'értéknap' in row_text:
            header_row = idx
            break
    
    if header_row == -1:
        return []
    
    headers_raw = []
    for val in df.iloc[header_row].values:
        if pd.isna(val):
            headers_raw.append('')
        else:
            headers_raw.append(str(val).strip())
    
    while headers_raw and headers_raw[-1] == '':
        headers_raw.pop()
    
    headers = []
    counter = {}
    for h in headers_raw:
        if h == '':
            headers.append('col')
            continue
        if h in counter:
            counter[h] += 1
            headers.append(f"{h}_{counter[h]}")
        else:
            counter[h] = 1
            headers.append(h)
    
    data_rows = []
    for idx in range(header_row + 1, len(df)):
        row = list(df.iloc[idx].values)
        if all(pd.isna(x) or str(x).strip() == '' for x in row):
            continue
        if len(row) < len(headers):
            row.extend([''] * (len(headers) - len(row)))
        data_rows.append(row[:len(headers)])
    
    if not data_rows:
        return []
    
    df_clean = pd.DataFrame(data_rows, columns=headers)
    
    date_col = None
    amount_col = None
    desc_col = None
    counterparty_col = None
    
    for col in df_clean.columns:
        col_lower = str(col).lower()
        if 'értéknap' in col_lower:
            date_col = col
        elif 'összeg' in col_lower:
            amount_col = col
        elif 'közlemény' in col_lower:
            desc_col = col
        elif 'kezdeményezett neve' in col_lower:
            counterparty_col = col
    
    if date_col is None and len(df_clean.columns) > 1:
        date_col = df_clean.columns[1]
    if amount_col is None and len(df_clean.columns) > 9:
        amount_col = df_clean.columns[9]
    
    if date_col is None or amount_col is None:
        return []
    
    for idx, row in df_clean.iterrows():
        try:
            if date_col not in row:
                continue
            date_val = row[date_col]
            if pd.isna(date_val):
                continue
            
            date_str = str(date_val).strip()
            if date_str.endswith('.0'):
                date_str = date_str[:-2]
            if date_str.isdigit() and len(date_str) == 8:
                date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            
            date = parse_date(date_str)
            if not date:
                continue
            
            if amount_col not in row:
                continue
            amount = parse_amount(row[amount_col])
            if amount == 0.0:
                continue
            
            description = ''
            if desc_col and desc_col in row and pd.notna(row[desc_col]):
                description = str(row[desc_col])
            
            counterparty = ''
            if counterparty_col and counterparty_col in row and pd.notna(row[counterparty_col]):
                counterparty = str(row[counterparty_col])
            
            if not description:
                desc_parts = []
                for col in df_clean.columns:
                    if col not in [date_col, amount_col, counterparty_col]:
                        val = row[col]
                        if pd.notna(val) and str(val).strip():
                            desc_parts.append(str(val))
                if desc_parts:
                    description = ' '.join(desc_parts)
            
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty[:200] if counterparty else '',
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception as e:
            continue
    
    return transactions

# ==================== УНИВЕРСАЛЬНЫЙ ПАРСЕР ====================

def parse_generic(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    
    for idx, row in df.iterrows():
        try:
            date = None
            amount = 0.0
            description = ''
            
            for col in range(len(row)):
                val = str(row.iloc[col]) if pd.notna(row.iloc[col]) else ''
                if not val:
                    continue
                
                parsed_date = parse_date(val)
                if parsed_date and parsed_date != val:
                    date = parsed_date
                    continue
                
                parsed_amount = parse_amount(val)
                if parsed_amount != 0.0:
                    amount = parsed_amount
                    continue
                
                if val and len(val) > 2:
                    description += val + ' '
            
            if date and amount != 0.0:
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': '',
                    'Наименование счета': account_name,
                    'Описание': description[:500]
                })
        except Exception as e:
            continue
    
    return transactions

# ==================== ОСНОВНОЙ ПАРСЕР EXCEL ====================

def parse_excel(file_content: bytes, filename: str) -> List[Dict]:
    account_name = clean_account_name(filename)
    filename_lower = filename.lower()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        sheets = pd.read_excel(tmp_path, sheet_name=None, header=None, dtype=str)
        all_transactions = []
        
        for sheet_name, df in sheets.items():
            if df.empty:
                continue
            
            file_type = 'unknown'
            
            # Проверка на BluOr (счет с LV)
            for idx in range(min(10, len(df))):
                row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
                if 'счет' in row_text and 'lv' in row_text:
                    file_type = 'bluor_excel'
                    break
            
            # Проверка на FIO
            if file_type == 'unknown':
                for idx in range(min(10, len(df))):
                    row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
                    if 'date' in row_text and 'volume' in row_text and 'currency' in row_text:
                        file_type = 'fio'
                        break
            
            # Проверка на CSOB
            if file_type == 'unknown':
                for idx in range(min(50, len(df))):
                    row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
                    if 'account number' in row_text and 'account currency' in row_text:
                        file_type = 'csob'
                        break
            
            # Проверка на MKB
            if file_type == 'unknown':
                for idx in range(min(50, len(df))):
                    row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
                    if 'sorszám' in row_text and 'értéknap' in row_text:
                        file_type = 'mkb'
                        break
            
            # Проверка на Paysera
            if file_type == 'unknown':
                for idx in range(min(10, len(df))):
                    row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
                    if 'дата и время' in row_text and 'сумма и валюта' in row_text:
                        file_type = 'paysera'
                        break
            
            # Проверка на Revolut
            if file_type == 'unknown':
                for idx in range(min(10, len(df))):
                    row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
                    if 'date started' in row_text and 'amount' in row_text:
                        file_type = 'revolut'
                        break
            
            # Проверка на B1 Estate (UniCredit)
            if file_type == 'unknown':
                for idx in range(min(10, len(df))):
                    row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
                    if 'from account' in row_text:
                        file_type = 'b1_estate'
                        break
            
            if file_type == 'bluor_excel':
                transactions = parse_bluor_excel(df, account_name)
                all_transactions.extend(transactions)
            elif file_type == 'fio':
                transactions = parse_fio(df, account_name)
                all_transactions.extend(transactions)
            elif file_type == 'csob':
                transactions = parse_csob(df, account_name)
                all_transactions.extend(transactions)
            elif file_type == 'mkb':
                transactions = parse_mkb(df, account_name)
                all_transactions.extend(transactions)
            elif file_type == 'paysera':
                transactions = parse_paysera(df, account_name)
                all_transactions.extend(transactions)
            elif file_type == 'revolut':
                transactions = parse_revolut(df, account_name)
                all_transactions.extend(transactions)
            elif file_type == 'b1_estate':
                transactions = parse_b1_estate(df, account_name)
                all_transactions.extend(transactions)
            else:
                transactions = parse_generic(df, account_name)
                all_transactions.extend(transactions)
        
        return all_transactions
                
    except Exception as e:
        st.error(f"Ошибка при парсинге Excel {filename}: {str(e)}")
        return []
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass

# ==================== ПАРСЕР CSV ====================

def parse_csv(file_content: bytes, filename: str) -> List[Dict]:
    account_name = clean_account_name(filename)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        encoding = detect_file_encoding(tmp_path)
        delimiter = detect_csv_delimiter(tmp_path)
        
        df = pd.read_csv(
            tmp_path,
            sep=delimiter,
            encoding=encoding,
            header=None,
            dtype=str,
            on_bad_lines='skip'
        )
        
        return parse_generic(df, account_name)
                
    except Exception as e:
        st.error(f"Ошибка при парсинге CSV {filename}: {str(e)}")
        return []
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass

# ==================== ГЛАВНАЯ ФУНКЦИЯ ====================

def parse_file(file_content: bytes, filename: str) -> List[Dict]:
    ext = os.path.splitext(filename)[1].lower()
    
    if ext == '.csv':
        return parse_csv(file_content, filename)
    elif ext in ['.xlsx', '.xls']:
        return parse_excel(file_content, filename)
    else:
        st.warning(f"Неподдерживаемый формат файла: {filename}")
        return []

# ==================== ИНТЕРФЕЙС ====================

def main():
    st.markdown("### 📂 Загрузите банковские выписки")
    st.markdown("Поддерживаются форматы: **CSV, XLSX, XLS**")
    
    uploaded_files = st.file_uploader(
        "Выберите файлы",
        type=['csv', 'xlsx', 'xls'],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        st.success(f"✅ Загружено файлов: {len(uploaded_files)}")
        
        if st.button("🚀 Обработать файлы"):
            all_transactions = []
            failed_files = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Обработка: {uploaded_file.name}")
                
                try:
                    content = uploaded_file.read()
                    transactions = parse_file(content, uploaded_file.name)
                    
                    if transactions:
                        all_transactions.extend(transactions)
                        st.info(f"✅ {uploaded_file.name}: {len(transactions)} операций")
                    else:
                        st.info(f"ℹ️ {uploaded_file.name}: транзакций не найдено")
                except Exception as e:
                    failed_files.append(f"{uploaded_file.name} (ошибка: {str(e)})")
                
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            status_text.text("✅ Обработка завершена!")
            
            if all_transactions:
                df = pd.DataFrame(all_transactions)
                df['Сумма'] = df['Сумма'].apply(format_amount)
                numeric_amounts = pd.to_numeric(
                    df['Сумма'].str.replace(',', '.').str.replace(' ', ''), 
                    errors='coerce'
                )
                
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("📊 Всего операций", len(all_transactions))
                with col2:
                    доход = numeric_amounts[numeric_amounts > 0].sum()
                    st.metric("📈 Доходы", f"{доход:,.2f}".replace('.', ','))
                with col3:
                    расход = abs(numeric_amounts[numeric_amounts < 0].sum())
                    st.metric("📉 Расходы", f"{расход:,.2f}".replace('.', ','))
                
                st.markdown("### 📋 Результат обработки")
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Транзакции', index=False)
                    
                    df_temp = df.copy()
                    df_temp['Сумма_число'] = numeric_amounts
                    
                    bank_summary = df_temp.groupby('Наименование счета').agg({
                        'Сумма_число': ['count', 'sum']
                    }).round(2)
                    bank_summary.columns = ['Количество операций', 'Сумма']
                    bank_summary['Сумма'] = bank_summary['Сумма'].apply(
                        lambda x: f"{x:,.2f}".replace('.', ',')
                    )
                    bank_summary.to_excel(writer, sheet_name='Сводка по счетам')
                
                output.seek(0)
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

if __name__ == "__main__":
    main()
