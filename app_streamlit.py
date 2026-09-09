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
    name = re.sub(r'\d{2}\.\d{2}\.\d{4}$', '', name)
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
    sign = "-" if amount < 0 else ""
    amount_abs = abs(amount)
    formatted = f"{amount_abs:.2f}".replace('.', ',')
    if ',' in formatted:
        integer_part, decimal_part = formatted.split(',')
        integer_part = re.sub(r'(?<=\d)(?=(\d{3})+(?!\d))', ' ', integer_part)
        return f"{sign}{integer_part},{decimal_part}"
    return f"{sign}{formatted}"

# ==================== ПАРСЕР ДЛЯ Regina Alfa-bank_NOMIQA_RUB ====================

def parse_regina_alfa(file_content: bytes, account_name: str) -> List[Dict]:
    """
    Парсер для Альфа-Банк (Россия) формата.
    XLSX с заголовками: Дата проводки, Код операции, Описание, Сумма в валюте счета
    """
    transactions = []
    
    try:
        df = pd.read_excel(BytesIO(file_content), sheet_name='Table 1', header=None)
    except Exception as e:
        try:
            df = pd.read_excel(BytesIO(file_content), header=None)
        except Exception as e2:
            return []
    
    if df.empty:
        return []
    
    # Ищем строку "Операции по счету"
    data_start_idx = -1
    for idx, row in df.iterrows():
        if idx < 50:
            row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Операции по счету' in row_str:
                data_start_idx = idx + 1
                break
    
    if data_start_idx == -1:
        return []
    
    # Собираем все строки данных, включая многострочные описания
    all_data_rows = []
    current_row = None
    
    for idx in range(data_start_idx, len(df)):
        row = df.iloc[idx]
        row_values = [x for x in row.values if pd.notna(x)]
        
        if not row_values:
            continue
        
        # Проверяем, является ли строка продолжением описания
        row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
        
        # Проверяем, что это не подпись и не итоговая строка
        if 'подпись' in row_str.lower() or 'Уполномоченное лицо' in row_str:
            break
        
        # Проверяем, содержит ли строка дату (начало новой записи)
        has_date = False
        for val in row.values:
            if pd.notna(val):
                val_str = str(val).strip()
                if re.match(r'^\d{4}-\d{2}-\d{2}', val_str) or re.match(r'^\d{2}\.\d{2}\.\d{4}', val_str):
                    has_date = True
                    break
        
        if has_date and current_row is not None:
            all_data_rows.append(current_row)
            current_row = row.values.tolist()
        elif current_row is None:
            current_row = row.values.tolist()
        else:
            # Это продолжение описания - объединяем
            for i, val in enumerate(row.values):
                if pd.notna(val) and val != '':
                    if i < len(current_row):
                        if pd.isna(current_row[i]) or current_row[i] == '':
                            current_row[i] = val
                        else:
                            current_row[i] = str(current_row[i]) + ' ' + str(val)
                    else:
                        current_row.append(val)
    
    if current_row is not None:
        all_data_rows.append(current_row)
    
    if not all_data_rows:
        return []
    
    # Определяем индексы колонок
    date_idx = 0
    code_idx = 1
    desc_idx = 2
    amount_idx = 10
    
    # Парсим данные
    for row_data in all_data_rows:
        try:
            # ДАТА
            date_str = ''
            if date_idx < len(row_data):
                val = row_data[date_idx]
                if pd.notna(val):
                    date_str = str(val).strip()
                    if date_str == 'nan':
                        date_str = ''
            
            if not date_str:
                continue
            
            # Извлекаем дату из строки (может быть "2026-08-04 00:00:00" или "26.08.2026")
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_str)
            if date_match:
                date_str = date_match.group(1)
            else:
                date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_str)
                if date_match:
                    date_str = date_match.group(1)
            
            date = parse_date(date_str)
            if not date:
                continue
            
            # СУММА
            amount = 0.0
            amount_found = False
            
            # Ищем сумму в последних колонках
            for col_idx in range(len(row_data) - 1, max(0, len(row_data) - 4), -1):
                val = row_data[col_idx]
                if pd.notna(val) and val != '':
                    val_str = str(val).strip()
                    if val_str and val_str != 'nan':
                        # Очищаем от пробелов и валюты
                        val_str = re.sub(r'\s*RUR\s*$', '', val_str)
                        parsed = parse_amount(val_str)
                        if parsed != 0.0:
                            amount = parsed
                            amount_found = True
                            break
            
            if not amount_found:
                continue
            
            # ОПИСАНИЕ
            description = ''
            if desc_idx < len(row_data):
                val = row_data[desc_idx]
                if pd.notna(val):
                    description = str(val).strip()
                    if description == 'nan':
                        description = ''
            
            # КОНТРАГЕНТ
            counterparty = ''
            if description:
                # Ищем контрагента в описании
                # Перевод через СБП
                match = re.search(r'от\s+([+\d\s]+)', description)
                if match:
                    counterparty = match.group(1).strip()
                else:
                    match = re.search(r'на\s+([+\d\s]+)', description)
                    if match:
                        counterparty = match.group(1).strip()
                    else:
                        # Ищем получателя платежа
                        match = re.search(r'Пляцевая\s+Регина', description)
                        if match:
                            counterparty = 'Пляцевая Регина Николаевна'
                        else:
                            # Операция по карте
                            match = re.search(r'место совершения операции:\s*([^\\]+)', description)
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
            
        except Exception as e:
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
    return parse_bsr_bluor_2(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ KL59_Rev_NB_EUR_BluOR (BluOr Bank) ====================

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
            
        except Exception as e:
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

# ==================== ПАРСЕР CSOB (ОБЩИЙ ДЛЯ ВСЕХ CSOB СЧЕТОВ) ====================

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

# ==================== ПАРСЕР ДЛЯ AN14_Estate_EUR_Industra (Industra Bank) ====================

def parse_industra_an14(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    
    try:
        df = pd.read_excel(BytesIO(file_content), header=None)
    except Exception as e:
        return []
    
    if df.empty:
        return []
    
    header_row_idx = -1
    for idx, row in df.iterrows():
        if idx < 30:
            row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Дата транзакции' in row_str and 'Дебет' in row_str and 'Кредит' in row_str:
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
            
        except Exception as e:
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
        df = pd.read_excel(BytesIO(file_content), sheet_name='Account transactions Statement', header=None)
    except Exception as e:
        try:
            df = pd.read_excel(BytesIO(file_content), header=None)
        except Exception as e2:
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
            
        except Exception as e:
            continue
    
    return transactions

# ==================== ПАРСЕР ДЛЯ AN14_Estate_EUR_Revolut (Revolut) ====================

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
    
    for i, col in enumerate(header_parts):
        col_clean = col.strip().strip('"')
        if 'Date started' in col_clean:
            date_idx = i
        elif 'Amount' in col_clean and 'Total' not in col_clean:
            amount_idx = i
        elif 'Description' in col_clean:
            desc_idx = i
        elif 'Payer' in col_clean:
            counterparty_idx = i
        elif 'State' in col_clean:
            state_idx = i
    
    if date_idx == -1:
        date_idx = 0
    if amount_idx == -1:
        amount_idx = 14
    if desc_idx == -1:
        desc_idx = 5
    
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
            
            counterparty = ''
            if counterparty_idx != -1 and counterparty_idx < len(parts):
                counterparty = parts[counterparty_idx].strip()
                if counterparty == '' or counterparty == 'nan':
                    counterparty = ''
            
            if not counterparty:
                description = parts[desc_idx].strip() if desc_idx < len(parts) else ''
                match = re.search(r'To\s+([^,]+)', description)
                if match:
                    counterparty = match.group(1).strip()
                else:
                    counterparty = description[:200]
            
            description = parts[desc_idx].strip() if desc_idx < len(parts) else ''
            
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty[:200],
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
            
        except Exception as e:
            continue
    
    return transactions

# ==================== ПАРСЕР ДЛЯ NB_Rev_EUR_Revolut ====================

def parse_revolut_nb(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_revolut_an14(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ Revolut_Plavas 1 SIA ====================

def parse_revolut_plavas(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_revolut_an14(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ Paysera (ОБЩИЙ) ====================

def parse_paysera_general(file_content: bytes, account_name: str) -> List[Dict]:
    transactions = []
    
    try:
        df = pd.read_excel(BytesIO(file_content), sheet_name='Worksheet', header=None)
    except Exception as e:
        try:
            df = pd.read_excel(BytesIO(file_content), header=None)
        except Exception as e2:
            return []
    
    if df.empty:
        return []
    
    header_row_idx = -1
    for idx, row in df.iterrows():
        if idx < 20:
            row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
            if 'Тип' in row_str and 'Дата и время' in row_str and 'Сумма и валюта' in row_str:
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
        elif 'Тип' in val_str:
            col_indices['trans_type'] = idx
    
    if 'date' not in col_indices:
        col_indices['date'] = 3
    if 'amount' not in col_indices:
        col_indices['amount'] = 7
    if 'counterparty' not in col_indices:
        col_indices['counterparty'] = 4
    
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
            
        except Exception as e:
            continue
    
    return transactions

# ==================== ПАРСЕР ДЛЯ Paysera Baltic Solutions EUR ====================

def parse_paysera_baltic(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_general(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ Paysera Sveciy Namai Lithuania EUR ====================

def parse_paysera_sveciy(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_general(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ Paysera-BS PROPERTY, SIA ====================

def parse_paysera_property(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_general(file_content, account_name)

# ==================== ПАРСЕР ДЛЯ Paysera-BS RERUM, SIA ====================

def parse_paysera_rerum(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_paysera_general(file_content, account_name)

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
    counterparty_idx = -1
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
            
        except Exception as e:
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
    transactions = []
    
    try:
        df = pd.read_excel(BytesIO(file_content), sheet_name='Statement', header=None)
    except Exception as e:
        try:
            df = pd.read_excel(BytesIO(file_content), header=None)
        except Exception as e2:
            return []
    
    if df.empty:
        return []
    
    header_row_idx = -1
    for idx, row in df.iterrows():
        if idx < 20:
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
            
        except Exception as e:
            continue
    
    return transactions

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

# ==================== ПАРСЕР ДЛЯ Koruna UniCredit- CZK (UniCredit Bank) ====================

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
            
        except Exception as e:
            continue
    
    return transactions

# ==================== ПАРСЕРЫ ДЛЯ UNICREDIT СЧЕТОВ ====================

def parse_unicredit_b1_estate(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unicredit_koruna(file_content, account_name)

def parse_garpiz_unicredit(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unicredit_koruna(file_content, account_name)

def parse_garpiz_pernink(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unicredit_koruna(file_content, account_name)

def parse_unicredit_twohills(file_content: bytes, account_name: str) -> List[Dict]:
    return parse_unicredit_koruna(file_content, account_name)

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
            break
    
    if parser_func is None:
        for acc_name, func in account_parsers.items():
            acc_keywords = set(acc_name.lower().split())
            file_keywords = set(account_name.lower().split())
            
            common = acc_keywords.intersection(file_keywords)
            if len(common) >= len(acc_keywords) * 0.6:
                parser_func = func
                break
    
    if parser_func is None:
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
