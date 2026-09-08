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
    
    if date_str.isdigit() and len(date_str) == 8:
        try:
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            return f"{day}-{month}-{year}"
        except:
            pass
    
    if '.' in date_str and date_str.split('.')[0].isdigit():
        date_str = date_str.split('.')[0]
        if len(date_str) == 8:
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
    
    is_negative = False
    if amount_str.startswith('-'):
        is_negative = True
        amount_str = amount_str[1:]
    elif amount_str.startswith('(') and amount_str.endswith(')'):
        is_negative = True
        amount_str = amount_str[1:-1]
    
    amount_str = re.sub(r'\s*[A-Z]{3}\s*$', '', amount_str)
    amount_str = re.sub(r'^\s*[A-Z]{3}\s*', '', amount_str)
    amount_str = amount_str.replace(' ', '').replace('\xa0', '')
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

def find_header_row(df: pd.DataFrame) -> int:
    for idx in range(min(30, len(df))):
        row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        if any(kw in row_text for kw in ['дата', 'date', 'datum']):
            if any(kw in row_text for kw in ['дебет', 'debit', 'кредит', 'credit', 'amount', 'сумма']):
                return idx
    return -1

# ==================== ПАРСЕР UNICREDIT ====================

def parse_unicredit(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    
    header_row = -1
    for idx in range(min(30, len(df))):
        row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        if 'from account' in row_text and 'amount' in row_text:
            header_row = idx
            break
    
    if header_row >= 0:
        headers = [str(h).strip() if pd.notna(h) else f'col_{i}' for i, h in enumerate(df.iloc[header_row].values)]
        data_rows = []
        for idx in range(header_row + 1, len(df)):
            row = list(df.iloc[idx].values)
            if len(row) < len(headers):
                row.extend([''] * (len(headers) - len(row)))
            data_rows.append(row[:len(headers)])
        df = pd.DataFrame(data_rows, columns=headers)
    else:
        return []
    
    date_col = None
    amount_col = None
    desc_col = None
    counterparty_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        if 'booking date' in col_lower or 'date' in col_lower or 'дата' in col_lower:
            date_col = col
        elif 'amount' in col_lower or 'сумма' in col_lower:
            amount_col = col
        elif 'transaction details' in col_lower or 'details' in col_lower or 'описание' in col_lower:
            desc_col = col
        elif 'name' in col_lower or 'контрагент' in col_lower:
            counterparty_col = col
    
    if date_col is None:
        return []
    
    for idx, row in df.iterrows():
        try:
            if date_col not in row:
                continue
            date_val = row[date_col]
            if pd.isna(date_val):
                continue
            date = parse_date(str(date_val))
            if not date:
                continue
            
            amount = 0.0
            if amount_col and amount_col in row:
                val = row[amount_col]
                if pd.notna(val):
                    amount = parse_amount(val)
            
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
                for col in df.columns:
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
    
    if header_row >= 0:
        headers = [str(h).strip() if pd.notna(h) else f'col_{i}' for i, h in enumerate(df.iloc[header_row].values)]
        data_rows = []
        for idx in range(header_row + 1, len(df)):
            row = list(df.iloc[idx].values)
            if len(row) < len(headers):
                row.extend([''] * (len(headers) - len(row)))
            data_rows.append(row[:len(headers)])
        df = pd.DataFrame(data_rows, columns=headers)
    else:
        return []
    
    date_col = None
    amount_col = None
    desc_col = None
    counterparty_col = None
    credit_debit_col = None
    
    for col in df.columns:
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
    
    for idx, row in df.iterrows():
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
            
            amount_str = str(row[amount_col])
            amount = parse_amount(amount_str)
            
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
                for col in df.columns:
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

# ==================== ПАРСЕР REVOLUT ====================

def parse_revolut(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    
    header_row = -1
    for idx in range(min(30, len(df))):
        row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        if 'date started' in row_text and 'amount' in row_text:
            header_row = idx
            break
    
    if header_row >= 0:
        headers = [str(h).strip() if pd.notna(h) else f'col_{i}' for i, h in enumerate(df.iloc[header_row].values)]
        data_rows = []
        for idx in range(header_row + 1, len(df)):
            row = list(df.iloc[idx].values)
            if len(row) < len(headers):
                row.extend([''] * (len(headers) - len(row)))
            data_rows.append(row[:len(headers)])
        df = pd.DataFrame(data_rows, columns=headers)
    else:
        return []
    
    date_col = None
    amount_col = None
    desc_col = None
    counterparty_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        if 'date started' in col_lower or 'date' in col_lower:
            date_col = col
        elif 'amount' in col_lower:
            amount_col = col
        elif 'description' in col_lower:
            desc_col = col
        elif 'sender name' in col_lower or 'beneficiary name' in col_lower:
            counterparty_col = col
    
    if date_col is None or amount_col is None:
        return []
    
    for idx, row in df.iterrows():
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
                for col in df.columns:
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

# ==================== ПАРСЕР CSOB/INDUSTRA ====================

def parse_csob_industra(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    
    header_row = find_header_row(df)
    
    if header_row >= 0:
        headers = [str(h).strip() if pd.notna(h) else f'col_{i}' for i, h in enumerate(df.iloc[header_row].values)]
        data_rows = []
        for idx in range(header_row + 1, len(df)):
            row = list(df.iloc[idx].values)
            if len(row) < len(headers):
                row.extend([''] * (len(headers) - len(row)))
            data_rows.append(row[:len(headers)])
        df = pd.DataFrame(data_rows, columns=headers)
    else:
        df.columns = [f'col_{i}' for i in range(len(df.columns))]
    
    date_col = None
    debit_col = None
    credit_col = None
    desc_col = None
    counterparty_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in ['дата транзакции', 'дата', 'date', 'datum']):
            date_col = col
        elif any(kw in col_lower for kw in ['дебет', 'debit']):
            debit_col = col
        elif any(kw in col_lower for kw in ['кредит', 'credit']):
            credit_col = col
        elif any(kw in col_lower for kw in ['информация', 'описание', 'description', 'transaction']):
            desc_col = col
        elif any(kw in col_lower for kw in ['получатель', 'плательщик', 'counterparty']):
            counterparty_col = col
    
    if debit_col is None and credit_col is None:
        cols = list(df.columns)
        for col in reversed(cols):
            sample = df[col].dropna()
            if len(sample) > 0:
                val = str(sample.iloc[0]).strip()
                if val and val != '0' and val != '0.0':
                    if '-' in val:
                        debit_col = col
                    else:
                        credit_col = col
                    break
    
    if debit_col is None and credit_col is None:
        cols = list(df.columns)
        if len(cols) >= 2:
            credit_col = cols[-1]
            debit_col = cols[-2]
    
    if date_col is None:
        for col in df.columns:
            sample = df[col].dropna()
            if len(sample) > 0:
                val = str(sample.iloc[0])
                if re.search(r'\d{2}[./]\d{2}[./]\d{4}', val) or (val.isdigit() and len(val) == 8):
                    date_col = col
                    break
        if date_col is None and len(df.columns) > 0:
            date_col = df.columns[0]
    
    for idx, row in df.iterrows():
        try:
            if date_col not in row:
                continue
            date_val = row[date_col]
            if pd.isna(date_val):
                continue
            date = parse_date(str(date_val))
            if not date:
                continue
            
            amount = 0.0
            
            if debit_col and debit_col in row:
                val = row[debit_col]
                if pd.notna(val):
                    parsed = parse_amount(val)
                    if parsed != 0:
                        amount = -abs(parsed)
            
            if amount == 0.0 and credit_col and credit_col in row:
                val = row[credit_col]
                if pd.notna(val):
                    parsed = parse_amount(val)
                    if parsed != 0:
                        amount = abs(parsed)
            
            if amount == 0.0:
                continue
            
            description = ''
            if desc_col and desc_col in row:
                val = row[desc_col]
                if pd.notna(val):
                    description = str(val)
            
            counterparty = ''
            if counterparty_col and counterparty_col in row:
                val = row[counterparty_col]
                if pd.notna(val):
                    counterparty = str(val)
            
            if not description or len(description) < 3:
                desc_parts = []
                for col in df.columns:
                    if col not in [date_col, debit_col, credit_col, counterparty_col]:
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

def parse_generic_excel(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    
    header_row = find_header_row(df)
    
    if header_row >= 0:
        headers = [str(h).strip() if pd.notna(h) else f'col_{i}' for i, h in enumerate(df.iloc[header_row].values)]
        data_rows = []
        for idx in range(header_row + 1, len(df)):
            row = list(df.iloc[idx].values)
            if len(row) < len(headers):
                row.extend([''] * (len(headers) - len(row)))
            data_rows.append(row[:len(headers)])
        df = pd.DataFrame(data_rows, columns=headers)
    
    date_col = None
    amount_col = None
    desc_col = None
    counterparty_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in ['date', 'дата', 'datum', 'posting', 'booking', 'value date']):
            if date_col is None:
                date_col = col
        elif any(kw in col_lower for kw in ['amount', 'сумма', 'volume', 'payment amount', 'total']):
            if amount_col is None:
                amount_col = col
        elif any(kw in col_lower for kw in ['description', 'описание', 'details', 'message', 'note']):
            if desc_col is None:
                desc_col = col
        elif any(kw in col_lower for kw in ['counterparty', 'контрагент', 'payee', 'payer', 'beneficiary']):
            if counterparty_col is None:
                counterparty_col = col
    
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]
    if amount_col is None and len(df.columns) > 1:
        amount_col = df.columns[1]
    
    if date_col is None or amount_col is None:
        return []
    
    for idx, row in df.iterrows():
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
                for col in df.columns:
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

# ==================== ПАРСЕР EXCEL ====================

def parse_excel(file_content: bytes, filename: str) -> List[Dict]:
    account_name = clean_account_name(filename)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        sheets = pd.read_excel(tmp_path, sheet_name=None, header=None, dtype=str)
        all_transactions = []
        
        for sheet_name, df in sheets.items():
            if df.empty:
                continue
            
            # Проверка на UniCredit
            is_unicredit = False
            for idx in range(min(20, len(df))):
                row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
                if 'from account' in row_text and 'amount' in row_text:
                    is_unicredit = True
                    break
            
            if is_unicredit:
                transactions = parse_unicredit(df, account_name)
                all_transactions.extend(transactions)
                continue
            
            # Проверка на Paysera
            is_paysera = False
            for idx in range(min(20, len(df))):
                row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
                if 'дата и время' in row_text and 'сумма и валюта' in row_text:
                    is_paysera = True
                    break
            
            if is_paysera:
                transactions = parse_paysera(df, account_name)
                all_transactions.extend(transactions)
                continue
            
            # Проверка на Revolut
            is_revolut = False
            for idx in range(min(20, len(df))):
                row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
                if 'date started' in row_text and 'amount' in row_text:
                    is_revolut = True
                    break
            
            if is_revolut:
                transactions = parse_revolut(df, account_name)
                all_transactions.extend(transactions)
                continue
            
            # Проверка на CSOB/Industra
            is_csob = False
            for idx in range(min(20, len(df))):
                row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
                if ('дебет' in row_text or 'debit' in row_text) and ('кредит' in row_text or 'credit' in row_text):
                    is_csob = True
                    break
            
            if is_csob:
                transactions = parse_csob_industra(df, account_name)
            else:
                transactions = parse_generic_excel(df, account_name)
            
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
        
        header_row = find_header_row(df)
        if header_row >= 0:
            headers = [str(h).strip() if pd.notna(h) else f'col_{i}' for i, h in enumerate(df.iloc[header_row].values)]
            data_rows = []
            for idx in range(header_row + 1, len(df)):
                row = list(df.iloc[idx].values)
                if len(row) < len(headers):
                    row.extend([''] * (len(headers) - len(row)))
                data_rows.append(row[:len(headers)])
            df = pd.DataFrame(data_rows, columns=headers)
        
        return parse_generic_excel(df, account_name)
                
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
                        failed_files.append(uploaded_file.name)
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
