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

# ==================== ПАРСЕР UNICREDIT (ДЛЯ ВСЕХ СЧЕТОВ UNICREDIT) ====================

def parse_unicredit_csv(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Универсальный парсер для всех CSV файлов UniCredit.
    Обрабатывает файлы с разделителем ; и структурой как у Garpiz.
    """
    transactions = []
    
    # Декодируем содержимое
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1250')
        except:
            content = file_content.decode('latin-1')
    
    lines = content.split('\n')
    
    # Пропускаем пустые строки
    lines = [line.strip() for line in lines if line.strip()]
    
    if len(lines) < 3:
        return []
    
    # Находим строку с заголовком
    header_line = -1
    for i, line in enumerate(lines):
        if 'From Account' in line and 'Amount' in line and 'Currency' in line:
            header_line = i
            break
    
    if header_line == -1:
        # Если заголовок не найден, пробуем парсить напрямую
        return parse_unicredit_direct(lines, account_name)
    
    # Парсим строки после заголовка
    for i in range(header_line + 1, len(lines)):
        line = lines[i]
        if not line:
            continue
        
        # Разбиваем по разделителю ;
        parts = line.split(';')
        
        # Удаляем пустые части в конце
        while parts and parts[-1] == '':
            parts.pop()
        
        if len(parts) < 4:
            continue
        
        try:
            # Номер счета (первая колонка)
            account_num = parts[0].strip()
            if not account_num or not re.match(r'^\d+$', account_num):
                continue
            
            # Сумма (вторая колонка)
            amount_str = parts[1].strip() if len(parts) > 1 else ''
            if not amount_str:
                continue
            
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            
            # Дата (четвертая колонка, индекс 3)
            date_str = parts[3].strip() if len(parts) > 3 else ''
            if not date_str:
                continue
            
            date = parse_date(date_str)
            if not date:
                continue
            
            # Ищем контрагента (колонка Name, индекс 9)
            counterparty = ''
            if len(parts) > 9:
                counterparty = parts[9].strip()
                if counterparty and counterparty != 'nan':
                    counterparty = counterparty[:200]
            
            # Если контрагент не найден, пробуем колонку Account (индекс 8)
            if not counterparty and len(parts) > 8:
                counterparty = parts[8].strip()
                if counterparty and counterparty != 'nan':
                    counterparty = counterparty[:200]
            
            # Если все еще нет, пробуем Bank Name (индекс 6)
            if not counterparty and len(parts) > 6:
                counterparty = parts[6].strip()
                if counterparty and counterparty != 'nan' and 'Bank' not in counterparty:
                    counterparty = counterparty[:200]
            
            # Ищем описание (колонка Transaction Details, индекс 13)
            description = ''
            if len(parts) > 13:
                description = parts[13].strip()
                if description and description != 'nan':
                    description = description
            
            # Если нет описания, собираем из других колонок
            if not description:
                desc_parts = []
                # Пропускаем служебные колонки
                exclude_indices = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
                for idx, part in enumerate(parts):
                    if idx in exclude_indices:
                        continue
                    part = part.strip()
                    if part and part != 'nan' and len(part) > 1:
                        # Пропускаем числа
                        if not re.match(r'^[\d\.,\-]+$', part):
                            desc_parts.append(part)
                if desc_parts:
                    description = ' | '.join(desc_parts)
            
            # Если все еще нет описания, используем Bank (индекс 5)
            if not description and len(parts) > 5:
                bank = parts[5].strip()
                if bank and bank != 'nan':
                    description = bank
                
                # Добавляем Bank Name если есть
                if len(parts) > 6:
                    bank_name = parts[6].strip()
                    if bank_name and bank_name != 'nan' and bank_name != bank:
                        if description:
                            description += f" | {bank_name}"
                        else:
                            description = bank_name
            
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

def parse_unicredit_direct(lines: List[str], account_name: str) -> List[Dict]:
    """
    Прямой парсер для CSV UniCredit, когда заголовок не найден.
    """
    transactions = []
    
    for line in lines:
        if not line:
            continue
        
        parts = line.split(';')
        
        # Удаляем пустые части в конце
        while parts and parts[-1] == '':
            parts.pop()
        
        if len(parts) < 4:
            continue
        
        try:
            # Проверяем, что первая колонка - номер счета
            first_val = parts[0].strip()
            if not first_val or not re.match(r'^\d+$', first_val):
                continue
            
            # Ищем дату в строке
            date = None
            for part in parts:
                if re.match(r'^\d{4}-\d{2}-\d{2}', part.strip()):
                    date = parse_date(part.strip())
                    break
            
            if not date:
                continue
            
            # Ищем сумму
            amount = 0.0
            for part in parts:
                part_clean = part.strip()
                if re.match(r'^[\-]?\d+[\.,]\d+$', part_clean) or re.match(r'^[\-]?\d+$', part_clean):
                    parsed = parse_amount(part_clean)
                    if parsed != 0.0:
                        amount = parsed
                        break
            
            if amount == 0.0:
                continue
            
            # Ищем контрагента
            counterparty = ''
            for part in parts:
                part_clean = part.strip()
                if part_clean and len(part_clean) > 3 and not re.match(r'^[\d\.,\-]+$', part_clean):
                    if not re.match(r'^\d{4}-\d{2}-\d{2}', part_clean):
                        counterparty = part_clean[:200]
                        break
            
            # Собираем описание
            description = ''
            desc_parts = []
            for part in parts:
                part_clean = part.strip()
                if part_clean and len(part_clean) > 2:
                    # Пропускаем даты, суммы, номера счетов и валюты
                    if not re.match(r'^\d{4}-\d{2}-\d{2}', part_clean) and \
                       not re.match(r'^[\d\.,\-]+$', part_clean) and \
                       part_clean not in ['CZK', 'EUR', 'USD']:
                        desc_parts.append(part_clean)
            
            if desc_parts:
                # Выбираем наиболее информативное описание
                for part in desc_parts:
                    if len(part) > 5 and 'transaction' not in part.lower():
                        description = part
                        break
                if not description:
                    description = ' | '.join(desc_parts[:3])
            
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

# ==================== ПАРСЕР CSOB (ДЛЯ ВСЕХ СЧЕТОВ CSOB) ====================

def parse_csob(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """
    Универсальный парсер для всех счетов CSOB.
    """
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

# ==================== ПАРСЕР INDUSTRA ====================

def parse_industra(df: pd.DataFrame, account_name: str) -> List[Dict]:
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

# ==================== ПАРСЕР MKB ====================

def parse_mkb(df: pd.DataFrame, account_name: str) -> List[Dict]:
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

# ==================== УНИВЕРСАЛЬНЫЙ ПАРСЕР ====================

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

# ==================== ОСНОВНОЙ ПАРСЕР ====================

def parse_file(file_content: bytes, filename: str) -> List[Dict]:
    account_name = clean_account_name(filename)
    
    # Определяем тип файла по имени
    is_unicredit = False
    is_csob = False
    is_fio = False
    is_industra = False
    is_mkb = False
    is_revolut = False
    is_paysera = False
    
    # UniCredit счета
    unicredit_accounts = [
        'Garpiz UniCredit', 'Garpiz UniCredit Bank',
        'Koruna UniCredit', 'TwoHills_Molly_Unicredit',
        'B1_Estate_CZK_UC', 'Garpiz_Pernink_CZK_UC'
    ]
    
    for acc in unicredit_accounts:
        if acc in account_name:
            is_unicredit = True
            break
    
    # CSOB счета
    if 'CSOB' in account_name or 'DŽIBIK' in account_name or 'DZIBIK' in account_name:
        is_csob = True
    
    # FIO счета
    if 'FIO' in account_name:
        is_fio = True
    
    # Industra счета
    if 'Industra' in account_name:
        is_industra = True
    
    # MKB счета
    if 'MKB' in account_name and 'Budapest' in account_name:
        is_mkb = True
    
    # Revolut счета
    if 'Revolut' in account_name:
        is_revolut = True
    
    # Paysera счета
    if 'Paysera' in account_name:
        is_paysera = True
    
    ext = os.path.splitext(filename)[1].lower()
    
    # Для UniCredit CSV используем специальный парсер
    if is_unicredit and ext == '.csv':
        return parse_unicredit_csv(file_content, account_name)
    
    # Для остальных файлов используем стандартный парсинг
    if ext == '.csv':
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            encoding = detect_file_encoding(tmp_path)
            with open(tmp_path, 'r', encoding=encoding, errors='ignore') as f:
                first_line = f.readline()
            delimiter = ';' if ';' in first_line else ','
            
            df = pd.read_csv(
                tmp_path,
                sep=delimiter,
                encoding=encoding,
                header=None,
                dtype=str,
                on_bad_lines='skip'
            )
            
            if is_csob:
                return parse_csob(df, account_name)
            elif is_fio:
                return parse_fio(df, account_name)
            elif is_industra:
                return parse_industra(df, account_name)
            elif is_mkb:
                return parse_mkb(df, account_name)
            elif is_revolut:
                return parse_revolut(df, account_name)
            elif is_paysera:
                return parse_paysera(df, account_name)
            else:
                return parse_unknown(df, account_name)
                
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
                
                if is_csob:
                    transactions = parse_csob(df, account_name)
                elif is_fio:
                    transactions = parse_fio(df, account_name)
                elif is_industra:
                    transactions = parse_industra(df, account_name)
                elif is_mkb:
                    transactions = parse_mkb(df, account_name)
                elif is_revolut:
                    transactions = parse_revolut(df, account_name)
                elif is_paysera:
                    transactions = parse_paysera(df, account_name)
                else:
                    transactions = parse_unknown(df, account_name)
                
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
