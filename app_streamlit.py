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
    name = re.sub(r'[_\-]', ' ', name).strip()
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
    elif amount_str.startswith('(') and amount_str.endswith(')'):
        is_negative = True
        amount_str = amount_str[1:-1]
    
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
    formatted = f"{abs(amount):.2f}".replace('.', ',')
    if ',' in formatted:
        integer_part, decimal_part = formatted.split(',')
        integer_part = re.sub(r'(?<=\d)(?=(\d{3})+(?!\d))', ' ', integer_part)
        return f"{integer_part},{decimal_part}"
    return formatted


# ==================== ПАРСЕР ДЛЯ Garpiz_Pernink_CZK_UC (ПОЛНОСТЬЮ ПЕРЕРАБОТАННЫЙ) ====================

def parse_garpiz_pernink_pandas(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Специальный парсер для Garpiz_Pernink_CZK_UC.
    Читает CSV с правильным разделителем и обрабатывает все строки.
    """
    transactions = []
    
    # Сохраняем содержимое во временный файл
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        # Определяем кодировку и разделитель
        encoding = detect_file_encoding(tmp_path)
        delimiter = detect_csv_delimiter(tmp_path)
        
        # Читаем весь файл как строки для ручного разбора
        with open(tmp_path, 'r', encoding=encoding, errors='ignore') as f:
            lines = f.readlines()
        
        # Удаляем пустые строки и пробелы
        lines = [line.strip() for line in lines if line.strip()]
        
        if len(lines) < 3:
            return []
        
        # Находим строку с заголовком (содержит "From Account")
        header_idx = -1
        for i, line in enumerate(lines):
            if 'From Account' in line and 'Amount' in line and 'Currency' in line:
                header_idx = i
                break
        
        if header_idx == -1:
            return []
        
        # Разбираем заголовок, чтобы определить индексы колонок
        header_parts = lines[header_idx].split(delimiter)
        # Удаляем пустые части в конце
        while header_parts and header_parts[-1] == '':
            header_parts.pop()
        
        # Определяем индексы нужных колонок
        col_indices = {}
        for i, part in enumerate(header_parts):
            part_clean = part.strip().lower()
            if 'from account' in part_clean:
                col_indices['from_account'] = i
            elif 'amount' in part_clean and 'currency' not in part_clean:
                col_indices['amount'] = i
            elif 'currency' in part_clean:
                col_indices['currency'] = i
            elif 'booking date' in part_clean:
                col_indices['booking_date'] = i
            elif 'value date' in part_clean:
                col_indices['value_date'] = i
            elif 'name' in part_clean and 'bank' not in part_clean:
                col_indices['name'] = i
            elif 'transaction details' in part_clean:
                col_indices['transaction_details'] = i
        
        # Проверяем наличие обязательных колонок
        if 'from_account' not in col_indices or 'amount' not in col_indices or 'booking_date' not in col_indices:
            return []
        
        # Обрабатываем строки после заголовка
        for line_idx in range(header_idx + 1, len(lines)):
            line = lines[line_idx]
            if not line:
                continue
            
            # Разбиваем строку
            parts = line.split(delimiter)
            # Удаляем пустые части в конце
            while parts and parts[-1] == '':
                parts.pop()
            
            if len(parts) < 4:
                continue
            
            try:
                # Получаем номер счета (первая колонка)
                acc_idx = col_indices['from_account']
                if acc_idx >= len(parts):
                    continue
                account_num = parts[acc_idx].strip()
                if not account_num or not re.match(r'^\d+$', account_num):
                    continue
                
                # Получаем дату
                date_idx = col_indices['booking_date']
                if date_idx >= len(parts):
                    continue
                date_str = parts[date_idx].strip()
                if not date_str or not re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
                    continue
                date = parse_date(date_str)
                if not date:
                    continue
                
                # Получаем сумму
                amt_idx = col_indices['amount']
                if amt_idx >= len(parts):
                    continue
                amt_str = parts[amt_idx].strip()
                if not amt_str:
                    continue
                amount = parse_amount(amt_str)
                if amount == 0.0:
                    continue
                
                # Получаем контрагента
                counterparty = ''
                if 'name' in col_indices and col_indices['name'] < len(parts):
                    val = parts[col_indices['name']].strip()
                    if val and val != 'nan' and len(val) > 1:
                        counterparty = val[:200]
                
                # Получаем описание
                description = ''
                if 'transaction_details' in col_indices and col_indices['transaction_details'] < len(parts):
                    val = parts[col_indices['transaction_details']].strip()
                    if val and val != 'nan' and len(val) > 1:
                        description = val
                
                # Если нет описания, собираем из других колонок
                if not description:
                    desc_parts = []
                    exclude_indices = list(col_indices.values())
                    for i, part in enumerate(parts):
                        if i in exclude_indices:
                            continue
                        part_clean = part.strip()
                        if part_clean and part_clean != 'nan' and len(part_clean) > 1:
                            if not re.match(r'^[\d\.,\-]+$', part_clean):
                                desc_parts.append(part_clean)
                    if desc_parts:
                        description = ' | '.join(desc_parts[:5])
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': counterparty,
                    'Наименование счета': account_name,
                    'Описание': description[:500]
                })
                
            except Exception as e:
                continue
        
        return transactions
        
    except Exception as e:
        st.error(f"Ошибка при парсинге Garpiz_Pernink: {str(e)}")
        return []
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


# ==================== ПАРСЕРЫ ДЛЯ ОСТАЛЬНЫХ СЧЕТОВ ====================

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
    date_idx = 4
    amount_idx = 6
    counterparty_idx = 13
    desc_idx = 15
    for idx in range(header_row + 1, len(df)):
        try:
            row = df.iloc[idx]
            if all(pd.isna(x) or str(x).strip() == '' for x in row):
                continue
            account_num = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
            if not account_num or account_num.lower() in ['account number', 'nan', '']:
                continue
            if date_idx >= len(row):
                continue
            date_val = row.iloc[date_idx]
            if pd.isna(date_val):
                continue
            date = parse_date(str(date_val))
            if not date:
                continue
            if amount_idx >= len(row):
                continue
            amount_val = row.iloc[amount_idx]
            if pd.isna(amount_val):
                continue
            amount = parse_amount(str(amount_val))
            account_num_clean = account_num.replace('/', '').replace(' ', '')
            amount_str_clean = str(abs(amount)).replace('.', '').replace(',', '')
            if amount_str_clean == account_num_clean:
                continue
            if amount == 0.0:
                continue
            counterparty = ''
            if counterparty_idx < len(row):
                val = row.iloc[counterparty_idx]
                if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                    counterparty = str(val).strip()[:200]
            description = ''
            if desc_idx < len(row):
                val = row.iloc[desc_idx]
                if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                    description = str(val).strip()
            if not description and len(row) > 12:
                val = row.iloc[12]
                if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                    description = str(val).strip()
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty,
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception as e:
            continue
    return transactions

def parse_jenisov_csob_czk(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_dzibik_csob(df, account_name)

def parse_jenisov_csob_eur(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_dzibik_csob(df, account_name)

def parse_rr_strojka_csob_czk(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_dzibik_csob(df, account_name)

def parse_rr_strojka_csob_eur(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_dzibik_csob(df, account_name)

def parse_koruna_strojka_csob_czk(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_dzibik_csob(df, account_name)

def parse_koruna_strojka_csob_eur(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_dzibik_csob(df, account_name)

def parse_stalkin_fio(df: pd.DataFrame, account_name: str) -> List[Dict]:
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
    date_idx = None
    amount_idx = None
    desc_idx = None
    counterparty_idx = None
    for i, col in enumerate(headers):
        if not col:
            continue
        col_lower = col.lower().strip()
        if col_lower == 'date':
            date_idx = i
        elif col_lower == 'volume':
            amount_idx = i
        elif col_lower == 'message for beneficiary' or col_lower == 'note':
            if desc_idx is None:
                desc_idx = i
        elif col_lower == 'note':
            counterparty_idx = i
    if date_idx is None or amount_idx is None:
        return []
    for idx in range(header_row + 1, len(df)):
        try:
            row = df.iloc[idx]
            if all(pd.isna(x) or str(x).strip() == '' for x in row):
                continue
            if date_idx >= len(row):
                continue
            date_val = row.iloc[date_idx]
            if pd.isna(date_val):
                continue
            date = parse_date(str(date_val))
            if not date:
                continue
            if amount_idx >= len(row):
                continue
            amount_val = row.iloc[amount_idx]
            if pd.isna(amount_val):
                continue
            amount = parse_amount(str(amount_val))
            if amount == 0.0:
                continue
            description = ''
            if desc_idx is not None and desc_idx < len(row):
                val = row.iloc[desc_idx]
                if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                    description = str(val).strip()
            counterparty = ''
            if counterparty_idx is not None and counterparty_idx < len(row):
                val = row.iloc[counterparty_idx]
                if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                    counterparty = str(val).strip()[:200]
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty,
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception as e:
            continue
    return transactions

def parse_an14_industra(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    for idx in range(len(df)):
        try:
            row = df.iloc[idx]
            if len(row) < 3:
                continue
            date_val = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
            if not re.match(r'^\d{2}\.\d{2}\.\d{4}$', date_val):
                continue
            date = parse_date(date_val)
            if not date:
                continue
            amount_val = str(row.iloc[2]) if len(row) > 2 and pd.notna(row.iloc[2]) else ''
            if not amount_val:
                continue
            amount = parse_amount(amount_val)
            if amount == 0.0:
                continue
            description = ''
            if len(row) > 1:
                val = row.iloc[1]
                if pd.notna(val) and str(val).strip():
                    description = str(val).strip()
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

def parse_plavas1_industra(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_an14_industra(df, account_name)

def parse_kl59_industra(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_an14_industra(df, account_name)

def parse_budapest_eur_mkb(df: pd.DataFrame, account_name: str) -> List[Dict]:
    transactions = []
    start_row = -1
    for idx in range(min(20, len(df))):
        val0 = str(df.iloc[idx, 0]) if pd.notna(df.iloc[idx, 0]) else ''
        if val0 and re.match(r'^\d+\.?$', val0.strip()):
            start_row = idx
            break
    if start_row == -1:
        return []
    for idx in range(start_row, len(df)):
        try:
            row = df.iloc[idx]
            if len(row) < 10:
                continue
            sorszam = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
            if not sorszam or not re.match(r'^\d+\.?$', sorszam.strip()):
                continue
            date_val = row.iloc[1] if pd.notna(row.iloc[1]) else ''
            if not date_val:
                continue
            date = parse_date(str(date_val))
            if not date:
                continue
            amount_val = row.iloc[9] if len(row) > 9 and pd.notna(row.iloc[9]) else ''
            if not amount_val:
                continue
            amount = parse_amount(amount_val)
            if amount == 0.0:
                continue
            trans_type = str(row.iloc[2]) if len(row) > 2 and pd.notna(row.iloc[2]) else ''
            counterparty = str(row.iloc[4]) if len(row) > 4 and pd.notna(row.iloc[4]) else ''
            if counterparty and counterparty != 'N/A' and counterparty != 'nan':
                counterparty = counterparty[:200]
            else:
                counterparty = ''
            description = str(row.iloc[11]) if len(row) > 11 and pd.notna(row.iloc[11]) else ''
            if not description and trans_type:
                description = trans_type
            full_description = f"{trans_type} | {counterparty} | {description}" if counterparty else f"{trans_type} | {description}"
            full_description = full_description[:500]
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty,
                'Наименование счета': account_name,
                'Описание': full_description
            })
        except Exception as e:
            continue
    return transactions

def parse_budapest_huf_mkb(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_budapest_eur_mkb(df, account_name)

def parse_paysera_generic(df: pd.DataFrame, account_name: str) -> List[Dict]:
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
    date_idx = None
    amount_idx = None
    desc_idx = None
    counterparty_idx = None
    credit_debit_idx = None
    for i, col in enumerate(headers):
        if not col:
            continue
        col_lower = col.lower().strip()
        if 'дата и время' in col_lower or 'дата' in col_lower:
            date_idx = i
        elif 'сумма и валюта' in col_lower or 'сумма' in col_lower:
            amount_idx = i
        elif 'назначение платежа' in col_lower or 'описание' in col_lower:
            desc_idx = i
        elif 'получатель' in col_lower or 'плательщик' in col_lower:
            counterparty_idx = i
        elif 'кредит' in col_lower or 'дебет' in col_lower:
            credit_debit_idx = i
    if date_idx is None or amount_idx is None:
        return []
    for idx in range(header_row + 1, len(df)):
        try:
            row = df.iloc[idx]
            if all(pd.isna(x) or str(x).strip() == '' for x in row):
                continue
            if date_idx >= len(row):
                continue
            date_val = row.iloc[date_idx]
            if pd.isna(date_val):
                continue
            date = parse_date(str(date_val))
            if not date:
                continue
            if amount_idx >= len(row):
                continue
            amount_val = row.iloc[amount_idx]
            if pd.isna(amount_val):
                continue
            amount = parse_amount(str(amount_val))
            if credit_debit_idx is not None and credit_debit_idx < len(row):
                cd_val = str(row.iloc[credit_debit_idx]).strip().lower()
                if cd_val == 'д' or cd_val == 'debit':
                    amount = -abs(amount)
                elif cd_val == 'к' or cd_val == 'credit':
                    amount = abs(amount)
            if amount == 0.0:
                continue
            description = ''
            if desc_idx is not None and desc_idx < len(row):
                val = row.iloc[desc_idx]
                if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                    description = str(val).strip()
            counterparty = ''
            if counterparty_idx is not None and counterparty_idx < len(row):
                val = row.iloc[counterparty_idx]
                if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                    counterparty = str(val).strip()[:200]
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty,
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception as e:
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
    if header_row == -1:
        return []
    headers = []
    for val in df.iloc[header_row].values:
        if pd.isna(val):
            headers.append('')
        else:
            headers.append(str(val).strip())
    date_idx = None
    amount_idx = None
    desc_idx = None
    counterparty_idx = None
    for i, col in enumerate(headers):
        if not col:
            continue
        col_lower = col.lower().strip()
        if 'date started' in col_lower:
            date_idx = i
        elif 'amount' in col_lower:
            amount_idx = i
        elif 'description' in col_lower:
            desc_idx = i
        elif 'beneficiary name' in col_lower or 'sender name' in col_lower:
            counterparty_idx = i
    if date_idx is None or amount_idx is None:
        return []
    for idx in range(header_row + 1, len(df)):
        try:
            row = df.iloc[idx]
            if all(pd.isna(x) or str(x).strip() == '' for x in row):
                continue
            if date_idx >= len(row):
                continue
            date_val = row.iloc[date_idx]
            if pd.isna(date_val):
                continue
            date = parse_date(str(date_val))
            if not date:
                continue
            if amount_idx >= len(row):
                continue
            amount_val = row.iloc[amount_idx]
            if pd.isna(amount_val):
                continue
            amount = parse_amount(str(amount_val))
            if amount == 0.0:
                continue
            description = ''
            if desc_idx is not None and desc_idx < len(row):
                val = row.iloc[desc_idx]
                if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                    description = str(val).strip()
            counterparty = ''
            if counterparty_idx is not None and counterparty_idx < len(row):
                val = row.iloc[counterparty_idx]
                if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                    counterparty = str(val).strip()[:200]
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty,
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception as e:
            continue
    return transactions

def parse_unicredit_generic(df: pd.DataFrame, account_name: str) -> List[Dict]:
    header_row = -1
    for idx in range(min(50, len(df))):
        row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        if 'from account' in row_text and 'amount' in row_text and 'currency' in row_text:
            header_row = idx
            break
    if header_row == -1:
        return parse_unknown(df, account_name)
    headers = []
    for val in df.iloc[header_row].values:
        if pd.isna(val):
            headers.append('')
        else:
            headers.append(str(val).strip())
    col_indices = {}
    for i, h in enumerate(headers):
        h_lower = h.lower()
        if 'from account' in h_lower:
            col_indices['from_account'] = i
        elif 'amount' in h_lower and 'currency' not in h_lower:
            col_indices['amount'] = i
        elif 'booking date' in h_lower:
            col_indices['booking_date'] = i
        elif 'name' in h_lower and 'bank' not in h_lower:
            col_indices['name'] = i
        elif 'transaction details' in h_lower:
            col_indices['transaction_details'] = i
    if 'from_account' not in col_indices or 'amount' not in col_indices or 'booking_date' not in col_indices:
        return parse_unknown(df, account_name)
    transactions = []
    for idx in range(header_row + 1, len(df)):
        try:
            row = df.iloc[idx]
            if all(pd.isna(x) or str(x).strip() == '' for x in row):
                continue
            acc_idx = col_indices['from_account']
            if acc_idx >= len(row):
                continue
            account_num = str(row.iloc[acc_idx]).strip() if pd.notna(row.iloc[acc_idx]) else ''
            if not account_num or not re.match(r'^\d+$', account_num):
                continue
            date_idx = col_indices['booking_date']
            if date_idx >= len(row):
                continue
            date_val = row.iloc[date_idx]
            if pd.isna(date_val):
                continue
            date_str = str(date_val).strip()
            if not re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
                continue
            date = parse_date(date_str)
            if not date:
                continue
            amt_idx = col_indices['amount']
            if amt_idx >= len(row):
                continue
            amt_val = row.iloc[amt_idx]
            if pd.isna(amt_val):
                continue
            amount = parse_amount(str(amt_val).strip())
            if amount == 0.0:
                continue
            counterparty = ''
            if 'name' in col_indices and col_indices['name'] < len(row):
                val = row.iloc[col_indices['name']]
                if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                    counterparty = str(val).strip()[:200]
            description = ''
            if 'transaction_details' in col_indices and col_indices['transaction_details'] < len(row):
                val = row.iloc[col_indices['transaction_details']]
                if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                    description = str(val).strip()
            if not description:
                desc_parts = []
                exclude_indices = list(col_indices.values())
                for i, val in enumerate(row):
                    if i in exclude_indices:
                        continue
                    if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                        part = str(val).strip()
                        if len(part) > 1 and not re.match(r'^[\d\.,\-]+$', part):
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
        except Exception as e:
            continue
    return transactions

def parse_unknown(df: pd.DataFrame, account_name: str) -> List[Dict]:
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

def parse_regina_alfa(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unknown(df, account_name)

def parse_tinkoff(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unknown(df, account_name)

def parse_bsr_bluor_2(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unknown(df, account_name)

def parse_bsr_bluor_3(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unknown(df, account_name)

def parse_kl59_rev_nb_bluor(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unknown(df, account_name)

def parse_jenhor_unelma(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unknown(df, account_name)

def parse_kapital_saida_azn(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unknown(df, account_name)

def parse_kapital_saida_business(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unknown(df, account_name)

def parse_mashreq(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unknown(df, account_name)

def parse_saida_n26(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unknown(df, account_name)

def parse_bunda_pasha_aed(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unknown(df, account_name)

def parse_bunda_pasha_azn(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unknown(df, account_name)

def parse_paysera_baltic(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_paysera_generic(df, account_name)

def parse_paysera_sveciy(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_paysera_generic(df, account_name)

def parse_paysera_property(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_paysera_generic(df, account_name)

def parse_paysera_rerum(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_paysera_generic(df, account_name)

def parse_rak_bank(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unknown(df, account_name)

def parse_an14_revolut(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_revolut_generic(df, account_name)

def parse_nb_revolut(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_revolut_generic(df, account_name)

def parse_revolut_plavas(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_revolut_generic(df, account_name)

def parse_b1_estate_uc(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unicredit_generic(df, account_name)

def parse_garpiz_unicredit(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unicredit_generic(df, account_name)

def parse_koruna_unicredit(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unicredit_generic(df, account_name)

def parse_twohills_unicredit(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unicredit_generic(df, account_name)

def parse_wio_business(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unknown(df, account_name)

def parse_saida_wise(df: pd.DataFrame, account_name: str) -> List[Dict]:
    return parse_unknown(df, account_name)


# ==================== ОСНОВНОЙ ПАРСЕР ====================

def parse_file(file_content: bytes, filename: str) -> List[Dict]:
    account_name = clean_account_name(filename)
    
    # Специальные парсеры для конкретных форматов
    if 'Garpiz_Pernink_CZK_UC' in account_name:
        return parse_garpiz_pernink_pandas(file_content, account_name)
    
    # Для остальных используем парсеры на основе DataFrame
    # Определяем тип счета по имени файла
    account_type = 'unknown'
    
    account_map = {
        'Regina Alfa-bank_NOMIQA_RUB': parse_regina_alfa,
        'Tinkoff RUB': parse_tinkoff,
        'BSR_Estate_EUR_BluOr_2': parse_bsr_bluor_2,
        'BSR_Estate_EUR_BluOr_3': parse_bsr_bluor_3,
        'KL59_Rev_NB_EUR_BluOR': parse_kl59_rev_nb_bluor,
        'JenHor_Unelma_CZK_CSAS': parse_jenhor_unelma,
        'DŽIBIK Main CSOB CZK': parse_dzibik_csob,
        'JENISOV - HORSKA_CSOB_ CZK': parse_jenisov_csob_czk,
        'JENISOV - HORSKA S.R EUR': parse_jenisov_csob_eur,
        'RR_Strojka_CZK_CSOB': parse_rr_strojka_csob_czk,
        'RR_Strojka_EUR_CSOB': parse_rr_strojka_csob_eur,
        'Koruna_Strojka_CZK_CSOB': parse_koruna_strojka_csob_czk,
        'Koruna_Strojka_EUR_CSOB': parse_koruna_strojka_csob_eur,
        'Stalkin_ML2_CZK_FIO': parse_stalkin_fio,
        'AN14_Estate_EUR_Industra': parse_an14_industra,
        'Plavas1_Estate_EUR_Industra': parse_plavas1_industra,
        'KL59_Rev_NB_EUR_Industra': parse_kl59_industra,
        'Kapital bank_Saida_AZN': parse_kapital_saida_azn,
        'Kapital bank_Saida_AZN (бизнес-счет)': parse_kapital_saida_business,
        'MASHREQ BANK-AED-NOMIQA': parse_mashreq,
        'Budapest EUR-MKB': parse_budapest_eur_mkb,
        'Budapest HUF-MKB': parse_budapest_huf_mkb,
        'Saida_N26': parse_saida_n26,
        'BUNDA LLC-Pasha Bank - AED-дирхам': parse_bunda_pasha_aed,
        'BUNDA LLC-Pasha Bank-AZN': parse_bunda_pasha_azn,
        'Paysera Baltic Solutions EUR': parse_paysera_baltic,
        'Paysera Sveciy Namai Lithuania EUR': parse_paysera_sveciy,
        'Paysera-BS PROPERTY, SIA': parse_paysera_property,
        'Paysera-BS RERUM, SIA': parse_paysera_rerum,
        'RAK BANK Nomiqa клиенты': parse_rak_bank,
        'AN14_Estate_EUR_Revolut': parse_an14_revolut,
        'NB_Rev_EUR_Revolut': parse_nb_revolut,
        'Revolut_Plavas 1 SIA': parse_revolut_plavas,
        'B1_Estate_CZK_UC': parse_b1_estate_uc,
        'Garpiz UniCredit Bank CZK': parse_garpiz_unicredit,
        'Koruna UniCredit- CZK': parse_koruna_unicredit,
        'TwoHills_Molly_Unicredit_CZK': parse_twohills_unicredit,
        'WIO Business Bank': parse_wio_business,
        'Saida_Wise': parse_saida_wise,
    }
    
    parser_func = None
    for acc_name, func in account_map.items():
        if acc_name in account_name:
            parser_func = func
            break
    
    if parser_func is None:
        parser_func = parse_unknown
    
    ext = os.path.splitext(filename)[1].lower()
    
    if ext == '.csv':
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
            result = parser_func(df, account_name)
            return result
        except Exception as e:
            st.error(f"Ошибка при парсинге CSV {filename}: {str(e)}")
            return []
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
    elif ext in ['.xlsx', '.xls']:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        try:
            xl = pd.ExcelFile(tmp_path)
            all_transactions = []
            for sheet_name in xl.sheet_names:
                df = pd.read_excel(tmp_path, sheet_name=sheet_name, header=None, dtype=str)
                if df.empty:
                    continue
                transactions = parser_func(df, account_name)
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
                
                df['Сумма_число'] = df['Сумма']
                df['Сумма'] = df['Сумма'].apply(format_amount)
                
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
