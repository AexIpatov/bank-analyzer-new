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
        return []
    
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
            # Номер счета (первая колонка) - должен содержать только цифры
            account_num = parts[0].strip()
            if not account_num or not re.match(r'^\d+$', account_num):
                continue
            
            # Сумма (вторая колонка)
            amount_str = parts[1].strip() if len(parts) > 1 else ''
            if not amount_str:
                continue
            
            # Проверяем, что это не строка с балансом
            # В строке с балансом нет даты в 4-й колонке
            date_str = parts[3].strip() if len(parts) > 3 else ''
            if not date_str or not re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
                continue
            
            # Парсим сумму
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            
            # Парсим дату
            date = parse_date(date_str)
            if not date:
                continue
            
            # Ищем контрагента
            counterparty = ''
            # Пробуем колонку Name (индекс 9)
            if len(parts) > 9:
                val = parts[9].strip()
                if val and val != 'nan' and len(val) > 1:
                    counterparty = val[:200]
            
            # Если нет, пробуем колонку Account (индекс 8)
            if not counterparty and len(parts) > 8:
                val = parts[8].strip()
                if val and val != 'nan' and len(val) > 1:
                    counterparty = val[:200]
            
            # Если все еще нет, пробуем Bank Name (индекс 6)
            if not counterparty and len(parts) > 6:
                val = parts[6].strip()
                if val and val != 'nan' and len(val) > 1 and 'Bank' not in val:
                    counterparty = val[:200]
            
            # Ищем описание
            description = ''
            # Пробуем колонку Transaction Details (индекс 13)
            if len(parts) > 13:
                val = parts[13].strip()
                if val and val != 'nan' and len(val) > 1:
                    description = val
            
            # Если нет описания, собираем из других колонок
            if not description:
                desc_parts = []
                # Проверяем все колонки, кроме служебных
                for idx, part in enumerate(parts):
                    part = part.strip()
                    if not part or part == 'nan' or len(part) <= 1:
                        continue
                    # Пропускаем служебные колонки
                    if idx in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]:
                        continue
                    # Пропускаем числа
                    if re.match(r'^[\d\.,\-]+$', part):
                        continue
                    desc_parts.append(part)
                
                if desc_parts:
                    description = ' | '.join(desc_parts[:3])
            
            # Если все еще нет описания, используем Bank (индекс 5)
            if not description and len(parts) > 5:
                val = parts[5].strip()
                if val and val != 'nan':
                    description = val
            
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

# ==================== ПАРСЕР CSOB (ДЛЯ DŽIBIK Main CSOB CZK) ====================

def parse_csob_dzibik(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """
    Специальный парсер для DŽIBIK Main CSOB CZK.
    """
    transactions = []
    
    # Находим строку с заголовками
    header_row = -1
    for idx in range(min(50, len(df))):
        row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        if 'account number' in row_text and 'account currency' in row_text:
            header_row = idx
            break
    
    if header_row == -1:
        return []
    
    # Определяем индексы колонок
    date_idx = 4  # posting date
    amount_idx = 6  # payment amount
    counterparty_idx = 13  # counterparty
    desc_idx = 15  # message to beneficiary
    
    # Проходим по строкам
    for idx in range(header_row + 1, len(df)):
        try:
            row = df.iloc[idx]
            
            # Пропускаем пустые строки
            if all(pd.isna(x) or str(x).strip() == '' for x in row):
                continue
            
            # Проверяем наличие номера счета
            account_num = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
            if not account_num or account_num.lower() in ['account number', 'nan', '']:
                continue
            
            # Получаем дату
            if date_idx >= len(row):
                continue
            date_val = row.iloc[date_idx]
            if pd.isna(date_val):
                continue
            date = parse_date(str(date_val))
            if not date:
                continue
            
            # Получаем сумму
            if amount_idx >= len(row):
                continue
            amount_val = row.iloc[amount_idx]
            if pd.isna(amount_val):
                continue
            
            amount = parse_amount(str(amount_val))
            
            # Проверяем, что это не номер счета
            account_num_clean = account_num.replace('/', '').replace(' ', '')
            amount_str_clean = str(abs(amount)).replace('.', '').replace(',', '')
            if amount_str_clean == account_num_clean:
                continue
            
            if amount == 0.0:
                continue
            
            # Получаем контрагента
            counterparty = ''
            if counterparty_idx < len(row):
                val = row.iloc[counterparty_idx]
                if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                    counterparty = str(val).strip()[:200]
            
            # Получаем описание
            description = ''
            if desc_idx < len(row):
                val = row.iloc[desc_idx]
                if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                    description = str(val).strip()
            
            # Если нет описания, используем тип транзакции
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

# ==================== ПАРСЕР CSOB (ДЛЯ JENISOV - HORSKA_CSOB) ====================

def parse_csob_jenisov(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """
    Парсер для JENISOV - HORSKA_CSOB CZK и EUR.
    Аналогичен парсеру для DŽIBIK.
    """
    return parse_csob_dzibik(df, account_name)

# ==================== ПАРСЕР CSOB (ДЛЯ RR_Strojka) ====================

def parse_csob_rr_strojka(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """
    Парсер для RR_Strojka_CZK_CSOB и RR_Strojka_EUR_CSOB.
    Аналогичен парсеру для DŽIBIK.
    """
    return parse_csob_dzibik(df, account_name)

# ==================== ПАРСЕР CSOB (ДЛЯ Koruna_Strojka) ====================

def parse_csob_koruna_strojka(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """
    Парсер для Koruna_Strojka_CZK_CSOB и Koruna_Strojka_EUR_CSOB.
    Аналогичен парсеру для DŽIBIK.
    """
    return parse_csob_dzibik(df, account_name)

# ==================== ПАРСЕР FIO (ДЛЯ Stalkin_ML2_CZK_FIO) ====================

def parse_fio_stalkin(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """
    Парсер для Stalkin_ML2_CZK_FIO.
    """
    transactions = []
    
    # Находим строку с заголовками
    header_row = -1
    for idx in range(min(10, len(df))):
        row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
        if 'date' in row_text and 'volume' in row_text and 'currency' in row_text:
            header_row = idx
            break
    
    if header_row == -1:
        return []
    
    # Определяем индексы колонок
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
    
    # Проходим по строкам
    for idx in range(header_row + 1, len(df)):
        try:
            row = df.iloc[idx]
            
            if all(pd.isna(x) or str(x).strip() == '' for x in row):
                continue
            
            # Получаем дату
            if date_idx >= len(row):
                continue
            date_val = row.iloc[date_idx]
            if pd.isna(date_val):
                continue
            date = parse_date(str(date_val))
            if not date:
                continue
            
            # Получаем сумму
            if amount_idx >= len(row):
                continue
            amount_val = row.iloc[amount_idx]
            if pd.isna(amount_val):
                continue
            
            amount = parse_amount(str(amount_val))
            if amount == 0.0:
                continue
            
            # Получаем описание
            description = ''
            if desc_idx is not None and desc_idx < len(row):
                val = row.iloc[desc_idx]
                if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                    description = str(val).strip()
            
            # Получаем контрагента
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

# ==================== ПАРСЕР INDUSTRA (ДЛЯ AN14_Estate_EUR_Industra) ====================

def parse_industra(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """
    Парсер для счетов Industra Bank.
    """
    transactions = []
    
    # Ищем строку с данными по формату
    for idx in range(len(df)):
        try:
            row = df.iloc[idx]
            if len(row) < 3:
                continue
            
            # Проверяем наличие даты в формате DD.MM.YYYY
            date_val = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
            if not re.match(r'^\d{2}\.\d{2}\.\d{4}$', date_val):
                continue
            
            date = parse_date(date_val)
            if not date:
                continue
            
            # Получаем сумму
            amount_val = str(row.iloc[2]) if len(row) > 2 and pd.notna(row.iloc[2]) else ''
            if not amount_val:
                continue
            
            amount = parse_amount(amount_val)
            if amount == 0.0:
                continue
            
            # Получаем описание
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

# ==================== ПАРСЕР MKB (ДЛЯ Budapest EUR-MKB и Budapest HUF-MKB) ====================

def parse_mkb_budapest(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """
    Парсер для Budapest EUR-MKB и Budapest HUF-MKB.
    """
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

# ==================== ПАРСЕР REVOLUT (ДЛЯ AN14_Estate_EUR_Revolut) ====================

def parse_revolut_estate(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """
    Парсер для Revolut счетов.
    """
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

# ==================== ПАРСЕР PAYSERA (ДЛЯ Paysera счетов) ====================

def parse_paysera_generic(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """
    Парсер для Paysera счетов.
    """
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
    """
    Универсальный парсер для неизвестных счетов.
    """
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
    """
    Определяет тип файла и вызывает соответствующий парсер.
    """
    account_name = clean_account_name(filename)
    
    # Определяем тип счета по имени файла
    account_type = 'unknown'
    
    # CSOB счета
    if 'DŽIBIK' in account_name or 'DZIBIK' in account_name:
        account_type = 'csob_dzibik'
    elif 'JENISOV' in account_name and 'CSOB' in account_name:
        account_type = 'csob_jenisov'
    elif 'RR_Strojka' in account_name and 'CSOB' in account_name:
        account_type = 'csob_rr_strojka'
    elif 'Koruna_Strojka' in account_name and 'CSOB' in account_name:
        account_type = 'csob_koruna_strojka'
    
    # UniCredit счета
    elif 'Garpiz UniCredit' in account_name or 'Garpiz UniCredit Bank' in account_name:
        account_type = 'unicredit_garpiz'
    elif 'Koruna UniCredit' in account_name:
        account_type = 'unicredit_garpiz'
    elif 'TwoHills_Molly_Unicredit' in account_name:
        account_type = 'unicredit_garpiz'
    elif 'B1_Estate_CZK_UC' in account_name:
        account_type = 'unicredit_garpiz'
    elif 'Garpiz_Pernink_CZK_UC' in account_name:
        account_type = 'unicredit_garpiz'
    
    # FIO счета
    elif 'Stalkin_ML2_CZK_FIO' in account_name:
        account_type = 'fio_stalkin'
    
    # Industra счета
    elif 'Industra' in account_name:
        account_type = 'industra'
    
    # MKB счета
    elif 'Budapest' in account_name and 'MKB' in account_name:
        account_type = 'mkb_budapest'
    
    # Revolut счета
    elif 'Revolut' in account_name:
        account_type = 'revolut'
    
    # Paysera счета
    elif 'Paysera' in account_name:
        account_type = 'paysera'
    
    ext = os.path.splitext(filename)[1].lower()
    
    # Для UniCredit CSV используем специальный парсер
    if account_type == 'unicredit_garpiz' and ext == '.csv':
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
            
            if account_type == 'csob_dzibik':
                return parse_csob_dzibik(df, account_name)
            elif account_type == 'csob_jenisov':
                return parse_csob_jenisov(df, account_name)
            elif account_type == 'csob_rr_strojka':
                return parse_csob_rr_strojka(df, account_name)
            elif account_type == 'csob_koruna_strojka':
                return parse_csob_koruna_strojka(df, account_name)
            elif account_type == 'fio_stalkin':
                return parse_fio_stalkin(df, account_name)
            elif account_type == 'industra':
                return parse_industra(df, account_name)
            elif account_type == 'mkb_budapest':
                return parse_mkb_budapest(df, account_name)
            elif account_type == 'revolut':
                return parse_revolut_estate(df, account_name)
            elif account_type == 'paysera':
                return parse_paysera_generic(df, account_name)
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
                
                if account_type == 'csob_dzibik':
                    transactions = parse_csob_dzibik(df, account_name)
                elif account_type == 'csob_jenisov':
                    transactions = parse_csob_jenisov(df, account_name)
                elif account_type == 'csob_rr_strojka':
                    transactions = parse_csob_rr_strojka(df, account_name)
                elif account_type == 'csob_koruna_strojka':
                    transactions = parse_csob_koruna_strojka(df, account_name)
                elif account_type == 'fio_stalkin':
                    transactions = parse_fio_stalkin(df, account_name)
                elif account_type == 'industra':
                    transactions = parse_industra(df, account_name)
                elif account_type == 'mkb_budapest':
                    transactions = parse_mkb_budapest(df, account_name)
                elif account_type == 'revolut':
                    transactions = parse_revolut_estate(df, account_name)
                elif account_type == 'paysera':
                    transactions = parse_paysera_generic(df, account_name)
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
