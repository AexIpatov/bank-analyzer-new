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
    name = re.sub(r'LV\d{2}[A-Z]{4}\d{13,}', '', name)
    name = re.sub(r'[_\/\\]', ' ', name).strip()
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
    elif amount_str.startswith('(') and amount_str.endswith(')'):
        is_negative = True
        amount_str = amount_str[1:-1]
    amount_str = re.sub(r'\s*[A-Z]{3}\s*\$', '', amount_str)
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
    amount_str = re.sub(r'[^0-9.\-]', '', amount_str)
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
    formatted = f"{abs(amount):.2f}".replace('.', ',')
    if ',' in formatted:
        integer_part, decimal_part = formatted.split(',')
        integer_part = re.sub(r'(?<=\d)(?=(\d{3})+(?!\d))', ' ', integer_part)
        return f"{integer_part},{decimal_part}"
    return formatted
# ==================== УНИВЕРСАЛЬНЫЕ ПАРСЕРЫ И ПОИСК ЗАГОЛОВКОВ ====================

def find_header_by_keywords(df: pd.DataFrame, keywords: List[str]) -> int:
    """
    Ищет строку заголовка в первых 50 строках файла по наличию ключевых слов.
    Возвращает индекс строки или -1, если не найдено.
    """
    for idx in range(min(50, len(df))):
        row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        if all(kw in row_text for kw in keywords):
            return idx
    return -1

def robust_parse_csv_or_excel(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """
    Улучшенный универсальный парсер. 
    Сначала ищет заголовок через ключевые слова, затем работает по индексам колонок.
    Если явного заголовка нет, использует эвристику (ищет даты и суммы по всему листу).
    """
    transactions = []
    
    # Попытка 1: Поиск стандартного заголовка CSV/Excel банковских выписок
    header_row = find_header_by_keywords(df, ['from account', 'amount', 'date'])
    
    if header_row != -1:
        headers = [str(val).strip().lower() if pd.notna(val) else '' for val in df.iloc[header_row]]
        
        col_indices = {
            'date': next((i for i, h in enumerate(headers) if 'date' in h), None),
            'amount': next((i for i, h in enumerate(headers) if 'amount' in h and 'curr' not in h), None),
            'counterparty': next((i for i, h in enumerate(headers) if any(x in h for x in ['name', 'beneficiary', 'sender'])), None),
            'desc': next((i for i, h in enumerate(headers) if any(x in h for x in ['details', 'description', 'info', 'message'])), None)
        }
        
        start_data_row = header_row + 1
    else:
        # Попытка 2: Заголовка нет (типично для выгрузок UniCredit/CZK). Используем фиктивные индексы.
        col_indices = {'date': 0, 'amount': 1, 'counterparty': 2, 'desc': 3}
        start_data_row = 0
        
    # Основной цикл извлечения данных
    for idx in range(start_data_row, len(df)):
        try:
            row = df.iloc[idx]
            
            # Пропускаем пустые строки
            if all(pd.isna(x) or str(x).strip() == '' for x in row):
                continue
                
            date_val = row[col_indices['date']] if col_indices['date'] is not None and col_indices['date'] < len(row) else ''
            amount_val = row[col_indices['amount']] if col_indices['amount'] is not None and col_indices['amount'] < len(row) else ''
            
            if pd.isna(date_val) or pd.isna(amount_val):
                continue
                
            date = parse_date(str(date_val))
            amount = parse_amount(str(amount_val))
            
            if not date or amount == 0.0:
                continue
                
            counterparty = ''
            if col_indices['counterparty'] is not None and col_indices['counterparty'] < len(row):
                cp_val = row[col_indices['counterparty']]
                if pd.notna(cp_val) and str(cp_val).strip().lower() not in ['nan', '', 'none']:
                    counterparty = str(cp_val).strip()
                    
            description = ''
            if col_indices['desc'] is not None and col_indices['desc'] < len(row):
                d_val = row[col_indices['desc']]
                if pd.notna(d_val) and str(d_val).strip().lower() not in ['nan', '', 'none']:
                    description = str(d_val).strip()
                    
            # Резервное описание: собираем всё, что осталось в строке
            if not description:
                desc_parts = []
                used_indices = [v for k,v in col_indices.items() if v is not None]
                for i, cell in enumerate(row):
                    if i not in used_indices and pd.notna(cell):
                        text = str(cell).strip()
                        if text and text.lower() not in ['nan', 'datum', 'suma']:
                            desc_parts.append(text)
                description = ' | '.join(desc_parts[:3])
                
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

def parse_unknown(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """Последний рубеж обороны — перебор всех ячеек на наличие дат и сумм."""
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
        except Exception:
            continue
    return transactions
# ==================== СПЕЦИАЛИЗИРОВАННЫЕ ПАРСЕРЫ ДЛЯ КАЖДОГО СЧЕТА ====================

def parse_regina_alfa(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return robust_parse_csv_or_excel(df, account_name)

def parse_tinkoff(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return robust_parse_csv_or_excel(df, account_name)

def parse_bsr_bluor_2(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return robust_parse_csv_or_excel(df, account_name)

def parse_bsr_bluor_3(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return robust_parse_csv_or_excel(df, account_name)

def parse_kl59_rev_nb_bluor(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return robust_parse_csv_or_excel(df, account_name)

def parse_jenhor_unelma(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return robust_parse_csv_or_excel(df, account_name)

def parse_dzibik_csob(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    header_row = -1
    for idx in range(min(50, len(df))):
        row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        if 'account number' in row_text and 'account currency' in row_text:
            header_row = idx
            break
    if header_row == -1:
        return []
    
    date_idx, amount_idx, counterparty_idx, desc_idx = 4, 6, 13, 15
    for idx in range(header_row + 1, len(df)):
        try:
            row = df.iloc[idx]
            if all(pd.isna(x) or str(x).strip() == '' for x in row): continue
            
            acc_num = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
            if not acc_num or acc_num.lower() in ['account number', 'nan', '']: continue
            
            d_val, a_val = row.iloc[date_idx], row.iloc[amount_idx]
            if pd.isna(d_val) or pd.isna(a_val): continue
            
            date = parse_date(str(d_val))
            amount = parse_amount(str(a_val))
            if not date or amount == 0.0: continue
            
            cp_val = row.iloc[counterparty_idx] if counterparty_idx < len(row) else None
            description = str(row.iloc[desc_idx]) if desc_idx < len(row) else ''
            
            # Фильтр ложных срабатываний по номеру счета в сумме
            amt_str_clean = str(abs(amount)).replace('.', '').replace(',', '')
            if amt_str_clean == acc_num.replace('/', '').replace(' ', ''): continue
                
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': str(cp_val).strip()[:200] if pd.notna(cp_val) else '',
                'Наименование счета': account_name,
                'Описание': str(description).strip()[:500]
            })
        except Exception:
            continue
    return transactions

def parse_stalkin_fio(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    header_row = -1
    for idx in range(min(10, len(df))):
        row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        if 'date' in row_text and 'volume' in row_text and 'currency' in row_text:
            header_row = idx
            break
    if header_row == -1: return []
    
    headers = [str(val).strip() if pd.notna(val) else '' for val in df.iloc[header_row]]
    indices = {h.lower(): i for i, h in enumerate(headers)}
    
    date_idx = indices.get('date')
    amount_idx = indices.get('volume')
    desc_idx = indices.get('message for beneficiary') or indices.get('note')
    cp_idx = indices.get('note')
    
    if date_idx is None or amount_idx is None: return []
    
    for idx in range(header_row + 1, len(df)):
        try:
            row = df.iloc[idx]
            if all(pd.isna(x) or str(x).strip() == '' for x in row): continue
            
            date = parse_date(str(row.iloc[date_idx]))
            amount = parse_amount(str(row.iloc[amount_idx]))
            if not date or amount == 0.0: continue
            
            description = str(row.iloc[desc_idx]).strip() if desc_idx is not None and desc_idx < len(row) else ''
            counterparty = str(row.iloc[cp_idx]).strip() if cp_idx is not None and cp_idx < len(row) else ''
            
            transactions.append({'Дата': date, 'Сумма': amount, 'Контрагент': counterparty, 
                               'Наименование счета': account_name, 'Описание': description[:500]})
        except Exception:
            continue
    return transactions

def parse_an14_industra(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    for idx in range(len(df)):
        try:
            row = df.iloc[idx]
            if len(row) < 3: continue
            
            date_val = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
            if not re.match(r'^\d{2}\.\d{2}\.\d{4}$', date_val): continue
            
            date = parse_date(date_val)
            amount = parse_amount(str(row.iloc[2])) if len(row) > 2 else 0.0
            if not date or amount == 0.0: continue
            
            description = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else ''
            transactions.append({'Дата': date, 'Сумма': amount, 'Контрагент': '', 
                               'Наименование счета': account_name, 'Описание': description[:500]})
        except Exception:
            continue
    return transactions

def parse_budapest_eur_mkb(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    start_row = -1
    for idx in range(min(20, len(df))):
        val0 = str(df.iloc[idx, 0]) if pd.notna(df.iloc[idx, 0]) else ''
        if val0 and re.match(r'^\d+\.?\s*$', val0.strip()):
            start_row = idx
            break
    if start_row == -1: return []
    
    for idx in range(start_row, len(df)):
        try:
            row = df.iloc[idx]
            if len(row) < 10: continue
            
            sorszam = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
            if not sorszam or not re.match(r'^\d+\.?\s*$', sorszam.strip()): continue
            
            date = parse_date(str(row.iloc[1])) if pd.notna(row.iloc[1]) else None
            amount = parse_amount(str(row.iloc[9])) if len(row) > 9 and pd.notna(row.iloc[9]) else 0.0
            if not date or amount == 0.0: continue
            
            trans_type = str(row.iloc[2]) if len(row) > 2 else ''
            counterparty = str(row.iloc[4]) if len(row) > 4 else ''
            description = str(row.iloc[11]) if len(row) > 11 else ''
            
            full_desc = f"{trans_type} | {counterparty} | {description}" if counterparty else f"{trans_type} | {description}"
            transactions.append({'Дата': date, 'Сумма': amount, 'Контрагент': counterparty[:200], 
                               'Наименование счета': account_name, 'Описание': full_desc[:500]})
        except Exception:
            continue
    return transactions

def parse_paysera_generic(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    header_row = find_header_by_keywords(df, ['дата и время', 'сумма и валюта'])
    if header_row == -1: return []
    
    headers = [str(val).strip().lower() if pd.notna(val) else '' for val in df.iloc[header_row]]
    col_indices = {
        'date': next((i for i, h in enumerate(headers) if 'дата' in h), None),
        'amount': next((i for i, h in enumerate(headers) if 'сумма' in h), None),
        'desc': next((i for i, h in enumerate(headers) if 'назначение' in h or 'описание' in h), None),
        'cp': next((i for i, h in enumerate(headers) if 'получатель' in h or 'плательщик' in h), None),
        'cd': next((i for i, h in enumerate(headers) if 'кредит' in h or 'дебет' in h), None)
    }
    if col_indices['date'] is None or col_indices['amount'] is None: return []
    
    for idx in range(header_row + 1, len(df)):
        try:
            row = df.iloc[idx]
            if all(pd.isna(x) or str(x).strip() == '' for x in row): continue
            
            date = parse_date(str(row.iloc[col_indices['date']]))
            raw_amt = str(row.iloc[col_indices['amount']])
            amount = parse_amount(raw_amt)
            
            if col_indices['cd'] is not None and col_indices['cd'] < len(row):
                cd = str(row.iloc[col_indices['cd']]).strip().lower()
                if cd in ['д', 'debit']: amount = -abs(amount)
                elif cd in ['к', 'credit']: amount = abs(amount)
                    
            if amount == 0.0: continue
            
            description = str(row.iloc[col_indices['desc']]).strip() if col_indices['desc'] is not None else ''
            counterparty = str(row.iloc[col_indices['cp']]).strip() if col_indices['cp'] is not None else ''
            
            transactions.append({'Дата': date, 'Сумма': amount, 'Контрагент': counterparty[:200], 
                               'Наименование счета': account_name, 'Описание': description[:500]})
        except Exception:
            continue
    return transactions

def parse_revolut_generic(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    header_row = -1
    for idx in range(min(30, len(df))):
        row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        if 'date started' in row_text and 'amount' in row_text:
            header_row = idx
            break
    if header_row == -1: return []
    
    headers = [str(val).strip().lower() if pd.notna(val) else '' for val in df.iloc[header_row]]
    col_indices = {
        'date': next((i for i, h in enumerate(headers) if 'date' in h), None),
        'amount': next((i for i, h in enumerate(headers) if 'amount' in h), None),
        'desc': next((i for i, h in enumerate(headers) if 'description' in h), None),
        'cp': next((i for i, h in enumerate(headers) if 'beneficiary' in h or 'sender' in h), None)
    }
    if col_indices['date'] is None or col_indices['amount'] is None: return []
    
    for idx in range(header_row + 1, len(df)):
        try:
            row = df.iloc[idx]
            if all(pd.isna(x) or str(x).strip() == '' for x in row): continue
            
            date = parse_date(str(row.iloc[col_indices['date']]))
            amount = parse_amount(str(row.iloc[col_indices['amount']]))
            if amount == 0.0: continue
            
            description = str(row.iloc[col_indices['desc']]).strip() if col_indices['desc'] is not None else ''
            counterparty = str(row.iloc[col_indices['cp']]).strip() if col_indices['cp'] is not None else ''
            
            transactions.append({'Дата': date, 'Сумма': amount, 'Контрагент': counterparty[:200], 
                               'Наименование счета': account_name, 'Описание': description[:500]})
        except Exception:
            continue
    return transactions

def parse_unicredit_generic(df: pd.DataFrame, account_name: str) -> List[Dict]:
    header_row = find_header_by_keywords(df, ['from account', 'amount', 'booking date'])
    if header_row == -1: return robust_parse_csv_or_excel(df, account_name)
    
    headers = [str(val).strip().lower() if pd.notna(val) else '' for val in df.iloc[header_row]]
    col_indices = {
        'acc': next((i for i, h in enumerate(headers) if 'from account' in h), None),
        'amt': next((i for i, h in enumerate(headers) if 'amount' in h and 'curr' not in h), None),
        'date': next((i for i, h in enumerate(headers) if 'booking date' in h), None),
        'name': next((i for i, h in enumerate(headers) if 'name' in h and 'bank' not in h), None),
        'details': next((i for i, h in enumerate(headers) if 'transaction details' in h), None)
    }
    if not all(k in col_indices for k in ['acc', 'amt', 'date']): return robust_parse_csv_or_excel(df, account_name)
    
    transactions = []
    for idx in range(header_row + 1, len(df)):
        try:
            row = df.iloc[idx]
            if all(pd.isna(x) or str(x).strip() == '' for x in row): continue
            
            acc_num = str(row.iloc[col_indices['acc']]).strip()
            if not acc_num or not re.match(r'^\d+$', acc_num): continue
            
            date = parse_date(str(row.iloc[col_indices['date']]))
            amount = parse_amount(str(row.iloc[col_indices['amt']]))
            if not date or amount == 0.0: continue
            
            counterparty = str(row.iloc[col_indices['name']]).strip() if col_indices['name'] is not None else ''
            description = str(row.iloc[col_indices['details']]).strip() if col_indices['details'] is not None else ''
            
            if not description:
                parts = [str(row.iloc[i]).strip() for i in range(len(row)) if i not in list(col_indices.values())]
                description = ' | '.join([p for p in parts if p][:5])
                
            transactions.append({'Дата': date, 'Сумма': amount, 'Контрагент': counterparty[:200], 
                               'Наименование счета': account_name, 'Описание': description[:500]})
        except Exception:
            continue
    return transactions

def parse_garpiz_pernink_pandas(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """
    Целевой парсер для Garpiz_Pernink_CZK_UC.
    Ищет заголовок "From Account | Amount | Currency | Booking Date" и работает строго по индексам.
    """
    transactions = []
    header_row = -1
    for idx in range(min(50, len(df))):
        row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        if 'from account' in row_text and 'amount' in row_text and ('currency' in row_text or 'mena' in row_text):
            header_row = idx
            break
            
    if header_row == -1:
        return [] # Если нет явной шапки, возвращаем пустоту, чтобы вызвать fallback
        
    headers = [str(val).strip().lower() if pd.notna(val) else '' for val in df.iloc[header_row]]
    col_indices = {}
    for i, h in enumerate(headers):
        if 'from account' in h: col_indices['from_account'] = i
        elif 'amount' in h and 'curr' not in h: col_indices['amount'] = i
        elif 'currency' in h or 'mena' in h: col_indices['currency'] = i
        elif 'booking date' in h: col_indices['booking_date'] = i
        elif 'value date' in h: col_indices['value_date'] = i
        elif 'bank name' in h: col_indices['bank_name'] = i
        elif 'transaction details' in h: col_indices['transaction_details'] = i
        
    if 'from_account' not in col_indices or 'amount' not in col_indices or 'booking_date' not in col_indices:
        return []
        
    for idx in range(header_row + 1, len(df)):
        try:
            row = df.iloc[idx]
            if all(pd.isna(x) or str(x).strip() == '' for x in row): continue
            
            acc_num = str(row.iloc[col_indices['from_account']]).strip()
            if not acc_num or not re.match(r'^\d+$', acc_num): continue
            
            date = parse_date(str(row.iloc[col_indices['booking_date']]))
            amount = parse_amount(str(row.iloc[col_indices['amount']]))
            if not date or amount == 0.0: continue
            
            counterparty = ''
            if 'bank_name' in col_indices and col_indices['bank_name'] < len(row):
                val = row.iloc[col_indices['bank_name']]
                if pd.notna(val): counterparty = str(val).strip()[:200]
            if not counterparty and 'transaction_details' in col_indices and col_indices['transaction_details'] < len(row):
                val = row.iloc[col_indices['transaction_details']]
                if pd.notna(val): counterparty = str(val).strip()[:200]
                
            description = ''
            if 'transaction_details' in col_indices and col_indices['transaction_details'] < len(row):
                val = row.iloc[col_indices['transaction_details']]
                if pd.notna(val): description = str(val).strip()
                
            transactions.append({'Дата': date, 'Сумма': amount, 'Контрагент': counterparty, 
                               'Наименование счета': account_name, 'Описание': description[:500]})
        except Exception:
            continue
    return transactions
# ==================== ОСНОВНОЙ ПАРСЕР И МЭППИНГ (ПЕРЕПИСАНО) ====================

def get_parser_for_account(account_name: str):
    """
    Возвращает функцию-парсер для конкретного счета.
    Сравнение идет по строгому соответствию начала строки,
    чтобы избежать конфликтов между похожими названиями (напр. AZN).
    """
    # Список кортежей для точного мэтчинга (префикс имени : функция)
    parsers = [
        ('Regina Alfa-bank_NOMIQA_RUB', parse_regina_alfa),
        ('Tinkoff RUB', parse_tinkoff),
        ('BSR_Estate_EUR_BluOr_2', parse_bsr_bluor_2),
        ('BSR_Estate_EUR_BluOr_3', parse_bsr_bluor_3),
        ('KL59_Rev_NB_EUR_BluOR', parse_kl59_rev_nb_bluor),
        ('JenHor_Unelma_CZK_CSAS', parse_jenhor_unelma),
        ('DŽIBIK Main CSOB CZK', parse_dzibik_csob),
        ('JENISOV - HORSKA_CSOB_', parse_jenisov_csob_czk),
        ('JENISOV - HORSKA S.R EUR', parse_jenisov_csob_eur),
        ('RR_Strojka_CZK_CSOB', parse_rr_strojka_csob_czk),
        ('RR_Strojka_EUR_CSOB', parse_rr_strojka_csob_eur),
        ('Koruna_Strojka_CZK_CSOB', parse_koruna_strojka_csob_czk),
        ('Koruna_Strojka_EUR_CSOB', parse_koruna_strojka_csob_eur),
        ('Stalkin_ML2_CZK_FIO', parse_stalkin_fio),
        ('AN14_Estate_EUR_Industra', parse_an14_industra),
        ('Plavas1_Estate_EUR_Industra', parse_plavas1_industra),
        ('KL59_Rev_NB_EUR_Industra', parse_kl59_industra),
        ('Kapital bank_Saida_AZN', parse_kapital_saida_azn),
        ('Kapital bank_Saida_AZN (бизнес-счет)', parse_kapital_saida_business),
        ('MASHREQ BANK-AED-NOMIQA', parse_mashreq),
        ('Budapest EUR-MKB', parse_budapest_eur_mkb),
        ('Budapest HUF-MKB', parse_budapest_huf_mkb),
        ('Saida_N26', parse_saida_n26),
        ('BUNDA LLC-Pasha Bank - AED-дирхам', parse_bunda_pasha_aed),
        ('BUNDA LLC-Pasha Bank-AZN', parse_bunda_pasha_azn),
        ('Paysera Baltic Solutions EUR', parse_paysera_baltic),
        ('Paysera Sveciy Namai Lithuania EUR', parse_paysera_sveciy),
        ('Paysera-BS PROPERTY, SIA', parse_paysera_property),
        ('Paysera-BS RERUM, SIA', parse_paysera_rerum),
        ('RAK BANK Nomiqa клиенты', parse_rak_bank),
        ('AN14_Estate_EUR_Revolut', parse_an14_revolut),
        ('NB_Rev_EUR_Revolut', parse_nb_revolut),
        ('Revolut_Plavas 1 SIA', parse_revolut_plavas),
        ('B1_Estate_CZK_UC', parse_b1_estate_uc),
        ('Garpiz UniCredit Bank CZK', parse_garpiz_unicredit),
        
        # ВАЖНО: Специальный фиксированный парсер для проблемного счета Garpiz_Pernink_CZK_UC
        ('Garpiz_Pernink_CZK_UC', parse_garpiz_pernink_pandas), 
        
        ('Koruna UniCredit- CZK', parse_koruna_unicredit),
        ('TwoHills_Molly_Unicredit_CZK', parse_twohills_unicredit),
        ('WIO Business Bank', parse_wio_business),
        ('Saida_Wise', parse_saida_wise),
    ]
    
    for prefix, func in parsers:
        if account_name.startswith(prefix):
            return func
            
    # Если точный префикс не найден, используем универсальный как запасной вариант
    return robust_parse_csv_or_excel

def parse_file(file_content: bytes, filename: str) -> List[Dict]:
    account_name = clean_account_name(filename)
    parser_func = get_parser_for_account(account_name)
    
    ext = os.path.splitext(filename)[1].lower()
    
    if ext == '.csv':
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        try:
            encoding = detect_file_encoding(tmp_path)
            delimiter = detect_csv_delimiter(tmp_path)
            
            # Читаем ВСЁ как строки, без попыток автоопределения типов
            df = pd.read_csv(
                tmp_path,
                sep=delimiter,
                encoding=encoding,
                header=None,
                dtype=str,
                on_bad_lines='skip',
                engine='python'
            )
            
            # Для известного спец-парсера передаем DataFrame напрямую
            if parser_func.__name__ in ['parse_garpiz_pernink_pandas']:
                result = parser_func(df, account_name)
                if not result and len(df.columns) > 5:
                    # Fallback на случай, если структура файла изменилась
                    result = robust_parse_csv_or_excel(df, account_name)
                return result
            
            # Для остальных сначала пробуем робастный разбор
            result = robust_parse_csv_or_excel(df, account_name)
            if result:
                return result
                
            # Если робастный парсер ничего не нашел, вызываем кастомную функцию
            return parser_func(df, account_name)
            
        finally:
            os.unlink(tmp_path)

    elif ext in ['.xlsx', '.xls']:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        try:
            xl = pd.ExcelFile(tmp_path)
            all_transactions = []
            
            for sheet_name in xl.sheet_names:
                df = pd.read_excel(tmp_path, sheet_name=sheet_name, header=None, dtype=str)
                if df.empty:
                    continue
                
                # Аналогичная логика приоритизации для Excel
                if parser_func.__name__ in ['parse_garpiz_pernink_pandas']:
                    specific_result = parser_func(df, account_name)
                    all_transactions.extend(specific_result)
                else:
                    general_result = robust_parse_csv_or_excel(df, account_name)
                    if general_result:
                        all_transactions.extend(general_result)
                        continue # Если общие правила нашли данные, другие листы этого файла не трогаем
                        
                    custom_result = parser_func(df, account_name)
                    all_transactions.extend(custom_result)
                    
            return all_transactions
        finally:
            os.unlink(tmp_path)
            
    else:
        st.warning(f"Неподдерживаемый формат файла: {filename}")
        return []
# ==================== ИНТЕРФЕЙС ПОЛЬЗОВАТЕЛЯ ====================

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
            file_stats = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Обработка: {uploaded_file.name}")
                try:
                    content = uploaded_file.read()
                    transactions = parse_file(content, uploaded_file.name)
                    
                    if transactions:
                        all_transactions.extend(transactions)
                        file_stats.append(f"✅ {uploaded_file.name}: {len(transactions)} операций")
                    else:
                        file_stats.append(f"ℹ️ {uploaded_file.name}: транзакций не найдено")
                except Exception as e:
                    failed_files.append(f"{uploaded_file.name} (ошибка: {str(e)})")
                
                progress_bar.progress((i + 1) / len(uploaded_files))
                
            status_text.text("✅ Обработка завершена!")
            
            for stat in file_stats:
                st.info(stat)
                
            if all_transactions:
                df = pd.DataFrame(all_transactions)
                # Сохраняем числовое значение суммы для расчетов до форматирования
                df['Сумма_число'] = df['Сумма'].apply(lambda x: float(str(x).replace(' ', '').replace(',', '.')) if str(x).replace(' ', '').replace(',', '.').replace('-', '').replace('.', '', 1).isdigit() else 0.0)
                df['Сумма'] = df['Сумма_число'].apply(format_amount)
                
                st.markdown("---")
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
                
                st.markdown("### 📋 Результат обработки")
                st.dataframe(df.drop(columns=['Сумма_число']), use_container_width=True, hide_index=True)
                
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

