import streamlit as st
import pandas as pd
import os
import re
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

def detect_file_encoding_from_bytes(file_content: bytes) -> str:
    """Определяет кодировку файла по содержимому"""
    try:
        raw_data = file_content[:10000]
        result = chardet.detect(raw_data)
        return result['encoding'] if result['encoding'] else 'utf-8'
    except:
        return 'utf-8'

def clean_account_name(filename: str) -> str:
    """Очищает имя файла для отображения названия счета"""
    name = os.path.splitext(filename)[0]
    name = re.sub(r'\d{4}-\d{2}-\d{2}', '', name)
    name = re.sub(r'LV\d{2}[A-Z]{4}\d{13,}', '', name)
    name = re.sub(r'[_\-]', ' ', name).strip()
    name = re.sub(r'\s+', ' ', name)
    return name if name else 'Неизвестный счет'

def parse_date(date_str: str) -> str:
    """Преобразует дату в формат ДД-ММ-ГГГГ"""
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
    """Преобразует строку с суммой в число с плавающей точкой"""
    if amount_str is None or pd.isna(amount_str):
        return 0.0
    
    amount_str = str(amount_str).strip()
    
    if amount_str in ['', 'nan', '-', 'None', 'null', 'NaN', 'N/A', 'n/a']:
        return 0.0
    
    # Проверяем знак
    is_negative = False
    if amount_str.startswith('-'):
        is_negative = True
        amount_str = amount_str[1:]
    elif amount_str.startswith('(') and amount_str.endswith(')'):
        is_negative = True
        amount_str = amount_str[1:-1]
    
    # Удаляем валюту
    amount_str = re.sub(r'\s*[A-Z]{3}\s*$', '', amount_str)
    amount_str = re.sub(r'^\s*[A-Z]{3}\s*', '', amount_str)
    
    # Удаляем пробелы
    amount_str = amount_str.replace(' ', '').replace('\xa0', '')
    
    # Обрабатываем разделители
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
    
    # Удаляем все нечисловые символы кроме точки и минуса
    amount_str = re.sub(r'[^\d.\-]', '', amount_str)
    
    if not amount_str or amount_str == '.':
        return 0.0
    
    try:
        value = float(amount_str)
        # Возвращаем с правильным знаком
        return -abs(value) if is_negative else abs(value)
    except:
        return 0.0

def format_amount(amount: float) -> str:
    """Форматирует число для отображения в таблице"""
    if amount is None or pd.isna(amount):
        return "0,00"
    formatted = f"{abs(amount):.2f}".replace('.', ',')
    if ',' in formatted:
        integer_part, decimal_part = formatted.split(',')
        integer_part = re.sub(r'(?<=\d)(?=(\d{3})+(?!\d))', ' ', integer_part)
        return f"{integer_part},{decimal_part}"
    return formatted


# ==================== ПАРСЕР ДЛЯ Garpiz_Pernink_CZK_UC (ИСПРАВЛЕННЫЙ) ====================

def parse_garpiz_pernink(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Специальный парсер для Garpiz_Pernink_CZK_UC.
    Правильно определяет суммы - берет их из колонки Amount (индекс 1).
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
    lines = [line.strip() for line in lines if line.strip()]
    
    if len(lines) < 3:
        return []
    
    # Находим строку с заголовком
    header_idx = -1
    for i, line in enumerate(lines):
        if 'From Account' in line and 'Amount' in line and 'Currency' in line:
            header_idx = i
            break
    
    if header_idx == -1:
        return []
    
    # Разбираем заголовок, чтобы определить индексы колонок
    header_parts = lines[header_idx].split(';')
    
    # Удаляем пустые части в конце
    while header_parts and header_parts[-1] == '':
        header_parts.pop()
    
    # Определяем индексы нужных колонок
    from_account_idx = None
    amount_idx = None
    currency_idx = None
    booking_date_idx = None
    value_date_idx = None
    bank_idx = None
    bank_name_idx = None
    account_idx = None
    name_idx = None
    transaction_details_idx = None
    
    for i, part in enumerate(header_parts):
        part_clean = part.strip().lower()
        if 'from account' in part_clean:
            from_account_idx = i
        elif 'amount' in part_clean and 'currency' not in part_clean:
            amount_idx = i
        elif 'currency' in part_clean:
            currency_idx = i
        elif 'booking date' in part_clean:
            booking_date_idx = i
        elif 'value date' in part_clean:
            value_date_idx = i
        elif 'bank' in part_clean and 'name' not in part_clean:
            bank_idx = i
        elif 'bank name' in part_clean:
            bank_name_idx = i
        elif 'account' in part_clean and 'from' not in part_clean:
            account_idx = i
        elif 'name' in part_clean and 'bank' not in part_clean:
            name_idx = i
        elif 'transaction details' in part_clean:
            transaction_details_idx = i
    
    # Проверяем наличие обязательных колонок
    if from_account_idx is None or amount_idx is None or booking_date_idx is None:
        return []
    
    # Обрабатываем строки после заголовка
    for line_idx in range(header_idx + 1, len(lines)):
        line = lines[line_idx]
        if not line:
            continue
        
        # Разбиваем строку
        parts = line.split(';')
        
        # Удаляем пустые части в конце
        while parts and parts[-1] == '':
            parts.pop()
        
        if len(parts) < 4:
            continue
        
        try:
            # Получаем номер счета (первая колонка)
            if from_account_idx >= len(parts):
                continue
            account_num = parts[from_account_idx].strip()
            if not account_num or not re.match(r'^\d+$', account_num):
                continue
            
            # Получаем дату
            if booking_date_idx >= len(parts):
                continue
            date_str = parts[booking_date_idx].strip()
            if not date_str or not re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
                continue
            date = parse_date(date_str)
            if not date:
                continue
            
            # Получаем сумму - ВАЖНО: берем из колонки Amount (индекс 1)
            if amount_idx >= len(parts):
                continue
            amt_str = parts[amount_idx].strip()
            if not amt_str:
                continue
            
            # Парсим сумму - она уже содержит знак минус если есть
            amount = parse_amount(amt_str)
            if amount == 0.0:
                continue
            
            # Получаем контрагента
            counterparty = ''
            if name_idx is not None and name_idx < len(parts):
                val = parts[name_idx].strip()
                if val and val != 'nan' and len(val) > 1:
                    counterparty = val[:200]
            
            # Если контрагент не найден, пробуем колонку Bank Name
            if not counterparty and bank_name_idx is not None and bank_name_idx < len(parts):
                val = parts[bank_name_idx].strip()
                if val and val != 'nan' and len(val) > 1 and 'Bank' not in val:
                    counterparty = val[:200]
            
            # Если все еще нет, пробуем колонку Account
            if not counterparty and account_idx is not None and account_idx < len(parts):
                val = parts[account_idx].strip()
                if val and val != 'nan' and len(val) > 1:
                    counterparty = val[:200]
            
            # Получаем описание
            description = ''
            if transaction_details_idx is not None and transaction_details_idx < len(parts):
                val = parts[transaction_details_idx].strip()
                if val and val != 'nan' and len(val) > 1:
                    description = val
            
            # Если нет описания, собираем из других колонок
            if not description:
                desc_parts = []
                exclude_indices = [from_account_idx, amount_idx, currency_idx, booking_date_idx, 
                                   value_date_idx, bank_idx, bank_name_idx, account_idx, name_idx]
                for i, part in enumerate(parts):
                    if i in exclude_indices:
                        continue
                    part_clean = part.strip()
                    if part_clean and part_clean != 'nan' and len(part_clean) > 1:
                        # Пропускаем числа, похожие на суммы или коды
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


# ==================== ПАРСЕР ДЛЯ Garpiz UniCredit Bank CZK ====================

def parse_garpiz_unicredit(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Парсер для Garpiz UniCredit Bank CZK.
    """
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
    
    # Находим строку с заголовком
    header_idx = -1
    for i, line in enumerate(lines):
        if 'From Account' in line and 'Amount' in line and 'Currency' in line:
            header_idx = i
            break
    
    if header_idx == -1:
        return []
    
    # Разбираем заголовок
    header_parts = lines[header_idx].split(';')
    while header_parts and header_parts[-1] == '':
        header_parts.pop()
    
    # Определяем индексы колонок
    from_account_idx = None
    amount_idx = None
    currency_idx = None
    booking_date_idx = None
    name_idx = None
    transaction_details_idx = None
    account_idx = None
    
    for i, part in enumerate(header_parts):
        part_clean = part.strip().lower()
        if 'from account' in part_clean:
            from_account_idx = i
        elif 'amount' in part_clean and 'currency' not in part_clean:
            amount_idx = i
        elif 'currency' in part_clean:
            currency_idx = i
        elif 'booking date' in part_clean:
            booking_date_idx = i
        elif 'name' in part_clean and 'bank' not in part_clean:
            name_idx = i
        elif 'transaction details' in part_clean:
            transaction_details_idx = i
        elif 'account' in part_clean and 'from' not in part_clean:
            account_idx = i
    
    if from_account_idx is None or amount_idx is None or booking_date_idx is None:
        return []
    
    for line_idx in range(header_idx + 1, len(lines)):
        line = lines[line_idx]
        if not line:
            continue
        
        parts = line.split(';')
        while parts and parts[-1] == '':
            parts.pop()
        
        if len(parts) < 4:
            continue
        
        try:
            account_num = parts[from_account_idx].strip()
            if not account_num or not re.match(r'^\d+$', account_num):
                continue
            
            date_str = parts[booking_date_idx].strip()
            if not date_str or not re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
                continue
            date = parse_date(date_str)
            if not date:
                continue
            
            amt_str = parts[amount_idx].strip()
            if not amt_str:
                continue
            amount = parse_amount(amt_str)
            if amount == 0.0:
                continue
            
            counterparty = ''
            if name_idx is not None and name_idx < len(parts):
                val = parts[name_idx].strip()
                if val and val != 'nan' and len(val) > 1:
                    counterparty = val[:200]
            if not counterparty and account_idx is not None and account_idx < len(parts):
                val = parts[account_idx].strip()
                if val and val != 'nan' and len(val) > 1:
                    counterparty = val[:200]
            
            description = ''
            if transaction_details_idx is not None and transaction_details_idx < len(parts):
                val = parts[transaction_details_idx].strip()
                if val and val != 'nan' and len(val) > 1:
                    description = val
            
            if not description:
                desc_parts = []
                exclude_indices = [from_account_idx, amount_idx, currency_idx, booking_date_idx, name_idx, account_idx]
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


# ==================== ПАРСЕРЫ ДЛЯ ОСТАЛЬНЫХ СЧЕТОВ ====================

def parse_unknown(file_content: bytes, account_name: str) -> List[Dict]:
    """Универсальный парсер для неизвестных форматов"""
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
                if len(part) > 2 and not re.match(r'^[\d\.,\-]+$', part):
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

def parse_generic_bluor(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для BluOr банка"""
    return parse_unknown(file_content, account_name)

def parse_csob_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для CSOB банка"""
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
    
    header_idx = -1
    for i, line in enumerate(lines):
        if 'account number' in line.lower() and 'account currency' in line.lower():
            header_idx = i
            break
    
    if header_idx == -1:
        return parse_unknown(file_content, account_name)
    
    for line_idx in range(header_idx + 1, len(lines)):
        line = lines[line_idx]
        if not line:
            continue
        parts = line.split(';')
        if len(parts) < 7:
            continue
        try:
            account_num = parts[0].strip()
            if not account_num:
                continue
            
            date_str = parts[4].strip() if len(parts) > 4 else ''
            date = parse_date(date_str)
            if not date:
                continue
            
            amount_str = parts[6].strip() if len(parts) > 6 else ''
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            
            counterparty = parts[13].strip() if len(parts) > 13 else ''
            description = parts[15].strip() if len(parts) > 15 else ''
            if not description and len(parts) > 12:
                description = parts[12].strip()
            
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

def parse_fio_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для FIO банка"""
    return parse_unknown(file_content, account_name)

def parse_industra_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Industra банка"""
    return parse_unknown(file_content, account_name)

def parse_mkb_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для MKB банка"""
    return parse_unknown(file_content, account_name)

def parse_paysera_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Paysera банка"""
    return parse_unknown(file_content, account_name)

def parse_revolut_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Revolut банка"""
    return parse_unknown(file_content, account_name)

def parse_unicredit_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для UniCredit банка (общий)"""
    return parse_unknown(file_content, account_name)


# ==================== ФУНКЦИИ-ОБЕРТКИ ДЛЯ КАЖДОГО СЧЕТА ====================

def parse_regina_alfa(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_tinkoff(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_bsr_bluor_2(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_generic_bluor(file_content, account_name)

def parse_bsr_bluor_3(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_generic_bluor(file_content, account_name)

def parse_kl59_rev_nb_bluor(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_generic_bluor(file_content, account_name)

def parse_jenhor_unelma(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_dzibik_csob(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_generic(file_content, account_name)

def parse_jenisov_csob_czk(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_generic(file_content, account_name)

def parse_jenisov_csob_eur(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_generic(file_content, account_name)

def parse_rr_strojka_csob_czk(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_generic(file_content, account_name)

def parse_rr_strojka_csob_eur(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_generic(file_content, account_name)

def parse_koruna_strojka_csob_czk(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_generic(file_content, account_name)

def parse_koruna_strojka_csob_eur(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_generic(file_content, account_name)

def parse_stalkin_fio(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_fio_generic(file_content, account_name)

def parse_an14_industra(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_industra_generic(file_content, account_name)

def parse_plavas1_industra(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_industra_generic(file_content, account_name)

def parse_kl59_industra(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_industra_generic(file_content, account_name)

def parse_kapital_saida_azn(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_kapital_saida_business(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_mashreq(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_budapest_eur_mkb(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_mkb_generic(file_content, account_name)

def parse_budapest_huf_mkb(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_mkb_generic(file_content, account_name)

def parse_saida_n26(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_bunda_pasha_aed(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_bunda_pasha_azn(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_paysera_baltic(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_generic(file_content, account_name)

def parse_paysera_sveciy(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_generic(file_content, account_name)

def parse_paysera_property(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_generic(file_content, account_name)

def parse_paysera_rerum(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_generic(file_content, account_name)

def parse_rak_bank(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_an14_revolut(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_revolut_generic(file_content, account_name)

def parse_nb_revolut(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_revolut_generic(file_content, account_name)

def parse_revolut_plavas(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_revolut_generic(file_content, account_name)

def parse_b1_estate_uc(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unicredit_generic(file_content, account_name)

def parse_koruna_unicredit(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unicredit_generic(file_content, account_name)

def parse_twohills_unicredit(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unicredit_generic(file_content, account_name)

def parse_wio_business(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_saida_wise(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)


# ==================== ОСНОВНОЙ ПАРСЕР ====================

def parse_file(file_content: bytes, filename: str) -> List[Dict]:
    """Основной парсер, определяет тип счета и вызывает соответствующий парсер"""
    account_name = clean_account_name(filename)
    
    # Специальные парсеры для UniCredit
    if 'Garpiz_Pernink_CZK_UC' in account_name:
        return parse_garpiz_pernink(file_content, account_name)
    
    if 'Garpiz UniCredit Bank CZK' in account_name:
        return parse_garpiz_unicredit(file_content, account_name)
    
    # Сопоставление имени счета с функцией-парсером
    account_parsers = {
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
        'Koruna UniCredit- CZK': parse_koruna_unicredit,
        'TwoHills_Molly_Unicredit_CZK': parse_twohills_unicredit,
        'WIO Business Bank': parse_wio_business,
        'Saida_Wise': parse_saida_wise,
    }
    
    # Выбираем парсер
    parser_func = None
    for acc_name, func in account_parsers.items():
        if acc_name in account_name:
            parser_func = func
            break
    
    if parser_func is None:
        parser_func = parse_unknown
    
    return parser_func(file_content, account_name)


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
