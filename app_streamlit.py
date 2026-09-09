import streamlit as st
import pandas as pd
import os
import re
import chardet
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Tuple, Optional

# ==================== НАСТРОЙКА СТРАНИЦЫ ====================
st.set_page_config(
    page_title="Аналитик банковских выписок",
    page_icon="🏦",
    layout="wide"
)

# ==================== CSS СТИЛИ ====================
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
    name = re.sub(r'\d{1,2}-\d{1,2}$', '', name)
    name = re.sub(r' 2026$', '', name)
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

# ==================== ПАРСЕР ДЛЯ Regina Alfa-bank_NOMIQA_RUB ====================

def parse_regina_alfa(file_content: bytes, account_name: str) -> List[Dict]:
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

# ==================== ПАРСЕР ДЛЯ Tinkoff RUB ====================

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

# ==================== ПАРСЕР ДЛЯ BSR_Estate_EUR_BluOr_2 ====================

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

# ==================== ПАРСЕР ДЛЯ BSR_Estate_EUR_BluOr_3 ====================

def parse_bsr_bluor_3(file_content: bytes, account_name: str) -> List[Dict]:
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

# ==================== ПАРСЕР ДЛЯ KL59_Rev_NB_EUR_BluOR ====================

def parse_kl59_rev_nb_bluor(file_content: bytes, account_name: str) -> List[Dict]:
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

# ==================== ПАРСЕР ДЛЯ JenHor_Unelma_CZK_CSAS ====================

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

# ==================== ПАРСЕР CSOB (ОБЩИЙ ДЛЯ ВСЕХ CSOB СЧЕТОВ) - ИСПРАВЛЕННЫЙ ====================

def parse_csob_general(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Универсальный парсер для CSOB формата.
    Ищет данные по заголовку или по позициям.
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
    
    if len(lines) < 2:
        return []
    
    # Показываем содержимое файла для отладки
    st.write(f"📄 Всего строк в файле: {len(lines)}")
    st.write(f"📄 Первая строка: {lines[0][:200]}...")
    
    # Проверяем наличие заголовка
    header_idx = -1
    for i, line in enumerate(lines):
        if 'account number' in line.lower() and 'posting date' in line.lower():
            header_idx = i
            break
        if 'account number' in line.lower() and 'payment amount' in line.lower():
            header_idx = i
            break
    
    if header_idx == -1:
        st.write("⚠️ Заголовок не найден, пробуем парсить по позициям")
        # Пробуем парсить без заголовка
        return parse_csob_by_position(file_content, account_name)
    
    st.write(f"✅ Заголовок найден на строке {header_idx}")
    
    # Определяем индексы полей
    header_parts = lines[header_idx].split(';')
    date_idx = -1
    amount_idx = -1
    counterparty_idx = -1
    description_idx = -1
    
    for i, col in enumerate(header_parts):
        col_lower = col.lower().strip()
        if 'posting date' in col_lower:
            date_idx = i
        elif 'payment amount' in col_lower:
            amount_idx = i
        elif 'counterparty' in col_lower and 'account' not in col_lower:
            counterparty_idx = i
        elif 'message to beneficiary' in col_lower:
            description_idx = i
    
    # Если не нашли по точным названиям, используем индексы по умолчанию
    if date_idx == -1:
        date_idx = 4
    if amount_idx == -1:
        amount_idx = 6
    if counterparty_idx == -1:
        counterparty_idx = 13
    if description_idx == -1:
        description_idx = 16
    
    st.write(f"📌 Индексы: дата={date_idx}, сумма={amount_idx}, контрагент={counterparty_idx}, описание={description_idx}")
    
    # Парсим данные
    for line_idx in range(header_idx + 1, len(lines)):
        line = lines[line_idx]
        if not line:
            continue
        
        parts = line.split(';')
        while parts and parts[-1] == '':
            parts.pop()
        
        if len(parts) < 7:
            st.write(f"⚠️ Строка {line_idx} имеет {len(parts)} полей, пропускаем")
            continue
        
        try:
            # ДАТА
            date_str = ''
            if date_idx < len(parts):
                date_str = parts[date_idx].strip()
            
            if not date_str or date_str in ['', 'nan']:
                continue
            
            date = parse_date(date_str)
            if not date:
                st.write(f"⚠️ Не удалось распарсить дату: '{date_str}'")
                continue
            
            # СУММА
            amount = 0.0
            amount_found = False
            
            if amount_idx < len(parts):
                amt_str = parts[amount_idx].strip()
                if amt_str and amt_str not in ['', 'nan']:
                    # Проверяем, что это не номер счета
                    if not re.match(r'^\d+\/\d+$', amt_str):
                        if not re.match(r'^\d{7,}$', amt_str):
                            parsed = parse_amount(amt_str)
                            if parsed != 0.0:
                                amount = parsed
                                amount_found = True
            
            # Если не нашли по индексу, ищем по всем полям
            if not amount_found:
                for part in parts:
                    part_clean = part.strip()
                    if not part_clean or part_clean in ['', 'nan']:
                        continue
                    
                    # Пропускаем номер счета
                    if re.match(r'^\d+\/\d+$', part_clean):
                        continue
                    if re.match(r'^\d{7,}$', part_clean):
                        continue
                    
                    # Проверяем признаки суммы
                    is_amount = False
                    if ',' in part_clean or '.' in part_clean:
                        is_amount = True
                    if part_clean.startswith('-'):
                        is_amount = True
                    if part_clean.startswith('(') and part_clean.endswith(')'):
                        is_amount = True
                    
                    if is_amount:
                        parsed = parse_amount(part_clean)
                        if parsed != 0.0:
                            amount = parsed
                            amount_found = True
                            break
            
            if not amount_found or amount == 0.0:
                continue
            
            # КОНТРАГЕНТ
            counterparty = ''
            if counterparty_idx < len(parts):
                counterparty = parts[counterparty_idx].strip()
                if counterparty in ['', 'nan']:
                    counterparty = ''
            
            if not counterparty:
                for idx in [3, 2, 8, 9]:
                    if idx < len(parts):
                        val = parts[idx].strip()
                        if val and val not in ['', 'nan', 'CZK', 'EUR', 'USD']:
                            if len(val) > 1 and not re.match(r'^[\d.,\-]+$', val):
                                counterparty = val[:200]
                                break
            
            # ОПИСАНИЕ
            description = ''
            if description_idx < len(parts):
                description = parts[description_idx].strip()
                if description in ['', 'nan']:
                    description = ''
            
            if not description:
                for idx in [28, 15, 12, 11, 10, 19, 20]:
                    if idx < len(parts):
                        val = parts[idx].strip()
                        if val and val not in ['', 'nan'] and len(val) > 5:
                            if not re.match(r'^[\d.,\-]+$', val):
                                if not re.match(r'^\d+\.?\d*$', val):
                                    description = val[:500]
                                    break
            
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty,
                'Наименование счета': account_name,
                'Описание': description
            })
            
        except Exception as e:
            st.write(f"⚠️ Ошибка в строке {line_idx}: {str(e)}")
            continue
    
    return transactions

# ==================== ПАРСЕР CSOB ПО ПОЗИЦИЯМ (БЕЗ ЗАГОЛОВКА) ====================

def parse_csob_by_position(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Парсер CSOB без заголовка - по позициям в строке.
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
    
    if len(lines) < 1:
        return []
    
    st.write("📄 Парсинг без заголовка по позициям")
    
    for line_idx, line in enumerate(lines):
        if not line:
            continue
        
        parts = line.split(';')
        while parts and parts[-1] == '':
            parts.pop()
        
        if len(parts) < 7:
            continue
        
        try:
            # ДАТА - ищем в строке
            date = None
            date_str = ''
            for part in parts:
                part_clean = part.strip()
                if re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}$', part_clean):
                    date_str = part_clean
                    break
                elif re.match(r'^\d{4}-\d{2}-\d{2}$', part_clean):
                    date_str = part_clean
                    break
            
            if not date_str:
                # Пробуем взять 5-й элемент (индекс 4)
                if len(parts) > 4:
                    date_str = parts[4].strip()
            
            date = parse_date(date_str)
            if not date:
                continue
            
            # СУММА - ищем в строке
            amount = 0.0
            amount_found = False
            
            # Сначала проверяем индекс 6 (payment amount)
            if len(parts) > 6:
                amt_str = parts[6].strip()
                if amt_str and amt_str not in ['', 'nan']:
                    if not re.match(r'^\d+\/\d+$', amt_str):
                        if not re.match(r'^\d{7,}$', amt_str):
                            parsed = parse_amount(amt_str)
                            if parsed != 0.0:
                                amount = parsed
                                amount_found = True
            
            # Если не нашли, ищем по всем полям
            if not amount_found:
                for part in parts:
                    part_clean = part.strip()
                    if not part_clean or part_clean in ['', 'nan']:
                        continue
                    
                    if re.match(r'^\d+\/\d+$', part_clean):
                        continue
                    if re.match(r'^\d{7,}$', part_clean):
                        continue
                    
                    is_amount = False
                    if ',' in part_clean or '.' in part_clean:
                        is_amount = True
                    if part_clean.startswith('-'):
                        is_amount = True
                    if part_clean.startswith('(') and part_clean.endswith(')'):
                        is_amount = True
                    
                    if is_amount:
                        parsed = parse_amount(part_clean)
                        if parsed != 0.0:
                            amount = parsed
                            amount_found = True
                            break
            
            if not amount_found or amount == 0.0:
                continue
            
            # КОНТРАГЕНТ - индекс 13 или 3
            counterparty = ''
            if len(parts) > 13:
                counterparty = parts[13].strip()
                if counterparty in ['', 'nan']:
                    counterparty = ''
            
            if not counterparty and len(parts) > 3:
                counterparty = parts[3].strip()
                if counterparty in ['', 'nan']:
                    counterparty = ''
            
            if not counterparty:
                for idx in [2, 8, 9]:
                    if idx < len(parts):
                        val = parts[idx].strip()
                        if val and val not in ['', 'nan', 'CZK', 'EUR', 'USD']:
                            if len(val) > 1 and not re.match(r'^[\d.,\-]+$', val):
                                counterparty = val[:200]
                                break
            
            # ОПИСАНИЕ - индекс 16
            description = ''
            if len(parts) > 16:
                description = parts[16].strip()
                if description in ['', 'nan']:
                    description = ''
            
            if not description:
                for idx in [28, 15, 12, 11, 10, 19, 20]:
                    if idx < len(parts):
                        val = parts[idx].strip()
                        if val and val not in ['', 'nan'] and len(val) > 5:
                            if not re.match(r'^[\d.,\-]+$', val):
                                if not re.match(r'^\d+\.?\d*$', val):
                                    description = val[:500]
                                    break
            
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty,
                'Наименование счета': account_name,
                'Описание': description
            })
            
        except Exception as e:
            continue
    
    return transactions

# ==================== ПАРСЕРЫ ДЛЯ CSOB СЧЕТОВ ====================

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

# ==================== ПАРСЕР ДЛЯ Stalkin_ML2_CZK_FIO ====================

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

# ==================== ПАРСЕР ДЛЯ AN14_Estate_EUR_Industra ====================

def parse_industra_an14(file_content: bytes, account_name: str) -> List[Dict]:
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

# ==================== ПАРСЕР ДЛЯ Plavas1_Estate_EUR_Industra ====================

def parse_industra_plavas1(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_industra_an14(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ KL59_Rev_NB_EUR_Industra ====================

def parse_industra_kl59(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_industra_an14(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ Kapital bank_Saida_AZN ====================

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

# ==================== ПАРСЕР ДЛЯ Kapital bank_Saida_AZN (бизнес-счет) ====================

def parse_kapital_saida_business(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_kapital_saida_azn(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ MASHREQ BANK-AED-NOMIQA ====================

def parse_mashreq(file_content: bytes, account_name: str) -> List[Dict]:
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

# ==================== ПАРСЕР ДЛЯ Budapest EUR-MKB ====================

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

# ==================== ПАРСЕР ДЛЯ Budapest HUF-MKB ====================

def parse_mkb_budapest_huf(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_mkb_budapest_eur(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ Saida_N26 ====================

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

# ==================== ПАРСЕР ДЛЯ BUNDA LLC-Pasha Bank - AED-дирхам ====================

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

# ==================== ПАРСЕР ДЛЯ BUNDA LLC-Pasha Bank-AZN ====================

def parse_bunda_pasha_azn(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_bunda_pasha_aed(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ Paysera Baltic Solutions EUR ====================

def parse_paysera_baltic(file_content: bytes, account_name: str) -> List[Dict]:
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

# ==================== ПАРСЕР ДЛЯ Paysera Sveciy Namai Lithuania EUR ====================

def parse_paysera_sveciy(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_baltic(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ Paysera-BS PROPERTY, SIA ====================

def parse_paysera_property(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_baltic(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ Paysera-BS RERUM, SIA ====================

def parse_paysera_rerum(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_baltic(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ RAK BANK Nomiqa клиенты ====================

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

# ==================== ПАРСЕР ДЛЯ AN14_Estate_EUR_Revolut ====================

def parse_revolut_an14(file_content: bytes, account_name: str) -> List[Dict]:
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

# ==================== ПАРСЕР ДЛЯ NB_Rev_EUR_Revolut ====================

def parse_revolut_nb(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_revolut_an14(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ Revolut_Plavas 1 SIA ====================

def parse_revolut_plavas(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_revolut_an14(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ B1_Estate_CZK_UC ====================

def parse_unicredit_b1_estate(file_content: bytes, account_name: str) -> List[Dict]:
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
                        if not re.match(r'^[\d.,\-]+$', part_clean):
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
        except:
            continue
    return transactions

# ==================== ПАРСЕР ДЛЯ Garpiz UniCredit Bank CZK ====================

def parse_garpiz_unicredit(file_content: bytes, account_name: str) -> List[Dict]:
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
                        if not re.match(r'^[\d.,\-]+$', part_clean):
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
        except:
            continue
    return transactions

# ==================== ПАРСЕР ДЛЯ Garpiz_Pernink_CZK_UC ====================

def parse_garpiz_pernink(file_content: bytes, account_name: str) -> List[Dict]:
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
            if not counterparty and len(parts) > 6:
                counterparty = parts[6].strip()
                if counterparty and counterparty != 'nan' and 'Bank' not in counterparty:
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
                        if not re.match(r'^[\d.,\-]+$', part_clean):
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
        except:
            continue
    return transactions

# ==================== ПАРСЕР ДЛЯ Koruna UniCredit- CZK ====================

def parse_unicredit_koruna(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_garpiz_unicredit(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ TwoHills_Molly_Unicredit_CZK ====================

def parse_unicredit_twohills(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_garpiz_unicredit(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ WIO Business Bank ====================

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

# ==================== ПАРСЕР ДЛЯ Saida_Wise ====================

def parse_saida_wise(file_content: bytes, account_name: str) -> List[Dict]:
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

# ==================== УНИВЕРСАЛЬНЫЙ ПАРСЕР ====================

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

def parse_file(file_content: bytes, filename: str) -> List[Dict]:
    account_name = clean_account_name(filename)
    
    # Выводим для отладки
    st.write(f"🔍 Имя счета после очистки: '{account_name}'")
    
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
        'AN14 Estate EUR Revolut': parse_revolut_an14,
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
    
    parser_func = None
    for acc_name, func in account_parsers.items():
        if acc_name == account_name:
            parser_func = func
            st.write(f"✅ Найден точный парсер: '{acc_name}'")
            break
    
    # Если точного совпадения нет, ищем частичное
    if parser_func is None:
        for acc_name, func in account_parsers.items():
            acc_keywords = set(acc_name.lower().split())
            file_keywords = set(account_name.lower().split())
            
            common = acc_keywords.intersection(file_keywords)
            if len(common) >= len(acc_keywords) * 0.6:
                parser_func = func
                st.write(f"✅ Найден частичный парсер: '{acc_name}' (совпало {len(common)} из {len(acc_keywords)} слов)")
                break
    
    if parser_func is None:
        st.write("⚠️ Парсер не найден, используется универсальный")
        parser_func = parse_unknown
    
    return parser_func(file_content, account_name)

# ==================== ОСНОВНОЙ ИНТЕРФЕЙС ====================

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
                        st.write(f"📝 Первая транзакция: {transactions[0]}")
                    else:
                        file_stats.append(f"ℹ️ {uploaded_file.name}: транзакций не найдено")
                        
                except Exception as e:
                    failed_files.append(f"{uploaded_file.name} (ошибка: {str(e)})")
                    st.write(f"❌ Ошибка: {str(e)}")
                
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
                
                st.dataframe(
                    df.drop(columns=['Сумма_число']),
                    use_container_width=True,
                    hide_index=True
                )
                
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
