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
    try:
        raw_data = file_content[:10000]
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
    """
    Преобразует строку с суммой в число с плавающей точкой.
    Работает с форматами: -350,00 или 350,00 или -350.00
    """
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
    Игнорирует номер счета как сумму.
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
    
    header_idx = -1
    for i, line in enumerate(lines):
        if 'From Account' in line and 'Amount' in line and 'Currency' in line:
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
        
        if len(parts) < 4:
            continue
        
        try:
            # Номер счета - первая колонка (используем только для проверки)
            account_num = parts[0].strip()
            if not account_num or not re.match(r'^\d+$', account_num):
                continue
            
            # Сумма - ВТОРАЯ колонка (индекс 1)
            amt_str = parts[1].strip() if len(parts) > 1 else ''
            if not amt_str:
                continue
            
            # Проверяем, что это действительно сумма (содержит запятую или точку)
            # и НЕ является номером счета (длинное число без запятой)
            if re.match(r'^\d{10,}$', amt_str):
                # Это номер счета, пропускаем
                continue
            
            # Парсим сумму с сохранением знака
            amount = parse_amount(amt_str)
            if amount == 0.0:
                continue
            
            # Дата - четвертая колонка (индекс 3)
            date_str = parts[3].strip() if len(parts) > 3 else ''
            if not date_str or not re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
                continue
            date = parse_date(date_str)
            if not date:
                continue
            
            # Контрагент - колонка Name (индекс 9)
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
            
            # Описание - колонка Transaction Details (индекс 13)
            description = ''
            if len(parts) > 13:
                description = parts[13].strip()
                if description and description != 'nan':
                    description = description
            
            # Если нет описания, собираем из других колонок
            if not description:
                desc_parts = []
                exclude_indices = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
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
    
    header_idx = -1
    for i, line in enumerate(lines):
        if 'From Account' in line and 'Amount' in line and 'Currency' in line:
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
        
        if len(parts) < 4:
            continue
        
        try:
            account_num = parts[0].strip()
            if not account_num or not re.match(r'^\d+$', account_num):
                continue
            
            amt_str = parts[1].strip() if len(parts) > 1 else ''
            if not amt_str:
                continue
            
            # Проверяем, что это действительно сумма
            if re.match(r'^\d{10,}$', amt_str):
                continue
            
            amount = parse_amount(amt_str)
            if amount == 0.0:
                continue
            
            date_str = parts[3].strip() if len(parts) > 3 else ''
            if not date_str or not re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
                continue
            date = parse_date(date_str)
            if not date:
                continue
            
            counterparty = ''
            if len(parts) > 9:
                counterparty = parts[9].strip()
                if counterparty and counterparty != 'nan':
                    counterparty = counterparty[:200]
            if not counterparty and len(parts) > 8:
                counterparty = parts[8].strip()
                if counterparty and counterparty != 'nan':
                    counterparty = counterparty[:200]
            
            description = ''
            if len(parts) > 13:
                description = parts[13].strip()
                if description and description != 'nan':
                    description = description
            
            if not description:
                desc_parts = []
                exclude_indices = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
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


# ==================== ПАРСЕР CSOB (ДЛЯ DŽIBIK Main CSOB CZK) ====================

def parse_csob_dzibik(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Специальный парсер для DŽIBIK Main CSOB CZK.
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
    
    header_idx = -1
    for i, line in enumerate(lines):
        if 'account number' in line.lower() and 'account currency' in line.lower():
            header_idx = i
            break
    
    if header_idx == -1:
        return []
    
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


# ==================== ПАРСЕР CSOB (ДЛЯ JENISOV - HORSKA_CSOB_ CZK) ====================

def parse_csob_jenisov_czk(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_dzibik(file_content, account_name)


# ==================== ПАРСЕР CSOB (ДЛЯ JENISOV - HORSKA S.R EUR) ====================

def parse_csob_jenisov_eur(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_dzibik(file_content, account_name)


# ==================== ПАРСЕР CSOB (ДЛЯ RR_Strojka_CZK_CSOB) ====================

def parse_csob_rr_strojka_czk(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_dzibik(file_content, account_name)


# ==================== ПАРСЕР CSOB (ДЛЯ RR_Strojka_EUR_CSOB) ====================

def parse_csob_rr_strojka_eur(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_dzibik(file_content, account_name)


# ==================== ПАРСЕР CSOB (ДЛЯ Koruna_Strojka_CZK_CSOB) ====================

def parse_csob_koruna_strojka_czk(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_dzibik(file_content, account_name)


# ==================== ПАРСЕР CSOB (ДЛЯ Koruna_Strojka_EUR_CSOB) ====================

def parse_csob_koruna_strojka_eur(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_csob_dzibik(file_content, account_name)


# ==================== ПАРСЕР FIO (ДЛЯ Stalkin_ML2_CZK_FIO) ====================

def parse_fio_stalkin(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Парсер для Stalkin_ML2_CZK_FIO.
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


# ==================== ПАРСЕР INDUSTRA (ДЛЯ AN14_Estate_EUR_Industra) ====================

def parse_industra_an14(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Парсер для AN14_Estate_EUR_Industra.
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
    
    for line in lines:
        parts = line.split(';')
        if len(parts) < 3:
            continue
        
        try:
            date_str = parts[0].strip()
            if not re.match(r'^\d{2}\.\d{2}\.\d{4}$', date_str):
                continue
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


# ==================== ПАРСЕР INDUSTRA (ДЛЯ Plavas1_Estate_EUR_Industra) ====================

def parse_industra_plavas1(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_industra_an14(file_content, account_name)


# ==================== ПАРСЕР INDUSTRA (ДЛЯ KL59_Rev_NB_EUR_Industra) ====================

def parse_industra_kl59(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_industra_an14(file_content, account_name)


# ==================== ПАРСЕР MKB (ДЛЯ Budapest EUR-MKB) ====================

def parse_mkb_budapest_eur(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Парсер для Budapest EUR-MKB.
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


# ==================== ПАРСЕР MKB (ДЛЯ Budapest HUF-MKB) ====================

def parse_mkb_budapest_huf(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_mkb_budapest_eur(file_content, account_name)


# ==================== ПАРСЕР PAYSERA (ДЛЯ Paysera Baltic Solutions EUR) ====================

def parse_paysera_baltic(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Парсер для Paysera Baltic Solutions EUR.
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
    
    header_idx = -1
    for i, line in enumerate(lines):
        if 'дата и время' in line.lower() and 'сумма и валюта' in line.lower():
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
            
            description = parts[2].strip() if len(parts) > 2 else ''
            counterparty = parts[3].strip() if len(parts) > 3 else ''
            
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


# ==================== ПАРСЕР PAYSERA (ДЛЯ Paysera Sveciy Namai Lithuania EUR) ====================

def parse_paysera_sveciy(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_baltic(file_content, account_name)


# ==================== ПАРСЕР PAYSERA (ДЛЯ Paysera-BS PROPERTY, SIA) ====================

def parse_paysera_property(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_baltic(file_content, account_name)


# ==================== ПАРСЕР PAYSERA (ДЛЯ Paysera-BS RERUM, SIA) ====================

def parse_paysera_rerum(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_baltic(file_content, account_name)


# ==================== ПАРСЕР REVOLUT (ДЛЯ AN14_Estate_EUR_Revolut) ====================

def parse_revolut_an14(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Парсер для AN14_Estate_EUR_Revolut.
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
    
    header_idx = -1
    for i, line in enumerate(lines):
        if 'date started' in line.lower() and 'amount' in line.lower():
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
            
            description = parts[2].strip() if len(parts) > 2 else ''
            counterparty = parts[3].strip() if len(parts) > 3 else ''
            
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


# ==================== ПАРСЕР REVOLUT (ДЛЯ NB_Rev_EUR_Revolut) ====================

def parse_revolut_nb(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_revolut_an14(file_content, account_name)


# ==================== ПАРСЕР REVOLUT (ДЛЯ Revolut_Plavas 1 SIA) ====================

def parse_revolut_plavas(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_revolut_an14(file_content, account_name)


# ==================== ПАРСЕР UNICREDIT (ДЛЯ B1_Estate_CZK_UC) ====================

def parse_unicredit_b1_estate(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Парсер для B1_Estate_CZK_UC.
    """
    return parse_garpiz_unicredit(file_content, account_name)


# ==================== ПАРСЕР UNICREDIT (ДЛЯ Koruna UniCredit- CZK) ====================

def parse_unicredit_koruna(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_garpiz_unicredit(file_content, account_name)


# ==================== ПАРСЕР UNICREDIT (ДЛЯ TwoHills_Molly_Unicredit_CZK) ====================

def parse_unicredit_twohills(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_garpiz_unicredit(file_content, account_name)


# ==================== УНИВЕРСАЛЬНЫЙ ПАРСЕР ====================

def parse_unknown(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Универсальный парсер для неизвестных форматов.
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


# ==================== ПАРСЕРЫ ДЛЯ ОСТАЛЬНЫХ СЧЕТОВ (ОБЕРТКИ) ====================

def parse_regina_alfa(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_tinkoff(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_bsr_bluor_2(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_bsr_bluor_3(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_kl59_rev_nb_bluor(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_jenhor_unelma(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_kapital_saida_azn(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_kapital_saida_business(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_mashreq(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_saida_n26(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_bunda_pasha_aed(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_bunda_pasha_azn(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_rak_bank(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_wio_business(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)

def parse_saida_wise(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unknown(file_content, account_name)


# ==================== ОСНОВНОЙ ПАРСЕР ====================

def parse_file(file_content: bytes, filename: str) -> List[Dict]:
    """
    Основной парсер, определяет тип счета и вызывает соответствующий парсер.
    """
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
        'DŽIBIK Main CSOB CZK': parse_csob_dzibik,
        'JENISOV - HORSKA_CSOB_ CZK': parse_csob_jenisov_czk,
        'JENISOV - HORSKA S.R EUR': parse_csob_jenisov_eur,
        'RR_Strojka_CZK_CSOB': parse_csob_rr_strojka_czk,
        'RR_Strojka_EUR_CSOB': parse_csob_rr_strojka_eur,
        'Koruna_Strojka_CZK_CSOB': parse_csob_koruna_strojka_czk,
        'Koruna_Strojka_EUR_CSOB': parse_csob_koruna_strojka_eur,
        'Stalkin_ML2_CZK_FIO': parse_fio_stalkin,
        'AN14_Estate_EUR_Industra': parse_industra_an14,
        'Plavas1_Estate_EUR_Industra': parse_industra_plavas1,
        'KL59_Rev_NB_EUR_Industra': parse_industra_kl59,
        'Kapital bank_Saida_AZN': parse_kapital_saida_azn,
        'Kapital bank_Saida_AZN (бизнес-счет)': parse_kapital_saida_business,
        'MASHREQ BANK-AED-NOMIQA': parse_mashreq,
        'Budapest EUR-MKB': parse_mkb_budapest_eur,
        'Budapest HUF-MKB': parse_mkb_budapest_huf,
        'Saida_N26': parse_saida_n26,
        'BUNDA LLC-Pasha Bank - AED-дирхам': parse_bunda_pasha_aed,
        'BUNDA LLC-Pasha Bank-AZN': parse_bunda_pasha_azn,
        'Paysera Baltic Solutions EUR': parse_paysera_baltic,
        'Paysera Sveciy Namai Lithuania EUR': parse_paysera_sveciy,
        'Paysera-BS PROPERTY, SIA': parse_paysera_property,
        'Paysera-BS RERUM, SIA': parse_paysera_rerum,
        'RAK BANK Nomiqa клиенты': parse_rak_bank,
        'AN14_Estate_EUR_Revolut': parse_revolut_an14,
        'NB_Rev_EUR_Revolut': parse_revolut_nb,
        'Revolut_Plavas 1 SIA': parse_revolut_plavas,
        'B1_Estate_CZK_UC': parse_unicredit_b1_estate,
        'Koruna UniCredit- CZK': parse_unicredit_koruna,
        'TwoHills_Molly_Unicredit_CZK': parse_unicredit_twohills,
        'WIO Business Bank': parse_wio_business,
        'Saida_Wise': parse_saida_wise,
    }
    
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
