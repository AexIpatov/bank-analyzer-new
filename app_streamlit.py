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

def detect_csv_delimiter_from_bytes(file_content: bytes) -> str:
    """Определяет разделитель в CSV файле"""
    delimiters = [';', ',', '\t', '|']
    try:
        encoding = detect_file_encoding_from_bytes(file_content)
        first_line = file_content.decode(encoding, errors='ignore').split('\n')[0]
        counts = {}
        for delim in delimiters:
            counts[delim] = first_line.count(delim)
        max_delim = max(counts, key=counts.get)
        return max_delim if counts[max_delim] > 0 else ';'
    except:
        return ';'

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
    """Форматирует число для отображения в таблице"""
    if amount is None or pd.isna(amount):
        return "0,00"
    formatted = f"{abs(amount):.2f}".replace('.', ',')
    if ',' in formatted:
        integer_part, decimal_part = formatted.split(',')
        integer_part = re.sub(r'(?<=\d)(?=(\d{3})+(?!\d))', ' ', integer_part)
        return f"{integer_part},{decimal_part}"
    return formatted


# ==================== ПАРСЕРЫ ДЛЯ КАЖДОГО БАНКОВСКОГО СЧЕТА ====================

# ===== 1. Regina Alfa-bank_NOMIQA_RUB =====
def parse_regina_alfa(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Regina Alfa-bank NOMIQA RUB"""
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1251')
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
            description = ' '.join(parts[2:])[:500]
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': '',
                'Наименование счета': account_name,
                'Описание': description
            })
        except:
            continue
    return transactions

# ===== 2. Tinkoff RUB =====
def parse_tinkoff(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Tinkoff RUB"""
    transactions = []
    try:
        content = file_content.decode('utf-8')
    except:
        try:
            content = file_content.decode('cp1251')
        except:
            content = file_content.decode('latin-1')
    
    lines = content.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    
    for line in lines:
        parts = line.split(';')
        if len(parts) < 4:
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
            counterparty = parts[2].strip() if len(parts) > 2 else ''
            description = ' '.join(parts[3:])[:500]
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty[:200],
                'Наименование счета': account_name,
                'Описание': description
            })
        except:
            continue
    return transactions

# ===== 3. BSR_Estate_EUR_BluOr_2 =====
def parse_bsr_bluor_2(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для BSR_Estate_EUR_BluOr_2"""
    return parse_generic_bluor(file_content, account_name)

# ===== 4. BSR_Estate_EUR_BluOr_3 =====
def parse_bsr_bluor_3(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для BSR_Estate_EUR_BluOr_3"""
    return parse_generic_bluor(file_content, account_name)

# ===== 5. KL59_Rev_NB_EUR_BluOR =====
def parse_kl59_rev_nb_bluor(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для KL59_Rev_NB_EUR_BluOR"""
    return parse_generic_bluor(file_content, account_name)

# ===== 6. JenHor_Unelma_CZK_CSAS =====
def parse_jenhor_unelma(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для JenHor_Unelma_CZK_CSAS"""
    return parse_unknown(file_content, account_name)

# ===== 7. DŽIBIK Main CSOB CZK =====
def parse_dzibik_csob(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для DŽIBIK Main CSOB CZK"""
    return parse_csob_generic(file_content, account_name)

# ===== 8. JENISOV - HORSKA_CSOB_ CZK =====
def parse_jenisov_csob_czk(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для JENISOV - HORSKA_CSOB_ CZK"""
    return parse_csob_generic(file_content, account_name)

# ===== 9. JENISOV - HORSKA S.R EUR =====
def parse_jenisov_csob_eur(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для JENISOV - HORSKA S.R EUR"""
    return parse_csob_generic(file_content, account_name)

# ===== 10. RR_Strojka_CZK_CSOB =====
def parse_rr_strojka_csob_czk(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для RR_Strojka_CZK_CSOB"""
    return parse_csob_generic(file_content, account_name)

# ===== 11. RR_Strojka_EUR_CSOB =====
def parse_rr_strojka_csob_eur(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для RR_Strojka_EUR_CSOB"""
    return parse_csob_generic(file_content, account_name)

# ===== 12. Koruna_Strojka_CZK_CSOB =====
def parse_koruna_strojka_csob_czk(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Koruna_Strojka_CZK_CSOB"""
    return parse_csob_generic(file_content, account_name)

# ===== 13. Koruna_Strojka_EUR_CSOB =====
def parse_koruna_strojka_csob_eur(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Koruna_Strojka_EUR_CSOB"""
    return parse_csob_generic(file_content, account_name)

# ===== 14. Stalkin_ML2_CZK_FIO =====
def parse_stalkin_fio(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Stalkin_ML2_CZK_FIO"""
    return parse_fio_generic(file_content, account_name)

# ===== 15. AN14_Estate_EUR_Industra =====
def parse_an14_industra(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для AN14_Estate_EUR_Industra"""
    return parse_industra_generic(file_content, account_name)

# ===== 16. Plavas1_Estate_EUR_Industra =====
def parse_plavas1_industra(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Plavas1_Estate_EUR_Industra"""
    return parse_industra_generic(file_content, account_name)

# ===== 17. KL59_Rev_NB_EUR_Industra =====
def parse_kl59_industra(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для KL59_Rev_NB_EUR_Industra"""
    return parse_industra_generic(file_content, account_name)

# ===== 18. Kapital bank_Saida_AZN =====
def parse_kapital_saida_azn(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Kapital bank_Saida_AZN"""
    return parse_unknown(file_content, account_name)

# ===== 19. Kapital bank_Saida_AZN (бизнес-счет) =====
def parse_kapital_saida_business(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Kapital bank_Saida_AZN (бизнес-счет)"""
    return parse_unknown(file_content, account_name)

# ===== 20. MASHREQ BANK-AED-NOMIQA =====
def parse_mashreq(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для MASHREQ BANK-AED-NOMIQA"""
    return parse_unknown(file_content, account_name)

# ===== 21. Budapest EUR-MKB =====
def parse_budapest_eur_mkb(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Budapest EUR-MKB"""
    return parse_mkb_generic(file_content, account_name)

# ===== 22. Budapest HUF-MKB =====
def parse_budapest_huf_mkb(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Budapest HUF-MKB"""
    return parse_mkb_generic(file_content, account_name)

# ===== 23. Saida_N26 =====
def parse_saida_n26(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Saida_N26"""
    return parse_unknown(file_content, account_name)

# ===== 24. BUNDA LLC-Pasha Bank - AED-дирхам =====
def parse_bunda_pasha_aed(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для BUNDA LLC-Pasha Bank - AED-дирхам"""
    return parse_unknown(file_content, account_name)

# ===== 25. BUNDA LLC-Pasha Bank-AZN =====
def parse_bunda_pasha_azn(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для BUNDA LLC-Pasha Bank-AZN"""
    return parse_unknown(file_content, account_name)

# ===== 26. Paysera Baltic Solutions EUR =====
def parse_paysera_baltic(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Paysera Baltic Solutions EUR"""
    return parse_paysera_generic(file_content, account_name)

# ===== 27. Paysera Sveciy Namai Lithuania EUR =====
def parse_paysera_sveciy(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Paysera Sveciy Namai Lithuania EUR"""
    return parse_paysera_generic(file_content, account_name)

# ===== 28. Paysera-BS PROPERTY, SIA =====
def parse_paysera_property(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Paysera-BS PROPERTY, SIA"""
    return parse_paysera_generic(file_content, account_name)

# ===== 29. Paysera-BS RERUM, SIA =====
def parse_paysera_rerum(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Paysera-BS RERUM, SIA"""
    return parse_paysera_generic(file_content, account_name)

# ===== 30. RAK BANK Nomiqa клиенты =====
def parse_rak_bank(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для RAK BANK Nomiqa клиенты"""
    return parse_unknown(file_content, account_name)

# ===== 31. AN14_Estate_EUR_Revolut =====
def parse_an14_revolut(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для AN14_Estate_EUR_Revolut"""
    return parse_revolut_generic(file_content, account_name)

# ===== 32. NB_Rev_EUR_Revolut =====
def parse_nb_revolut(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для NB_Rev_EUR_Revolut"""
    return parse_revolut_generic(file_content, account_name)

# ===== 33. Revolut_Plavas 1 SIA =====
def parse_revolut_plavas(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Revolut_Plavas 1 SIA"""
    return parse_revolut_generic(file_content, account_name)

# ===== 34. B1_Estate_CZK_UC =====
def parse_b1_estate_uc(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для B1_Estate_CZK_UC"""
    return parse_unicredit_generic(file_content, account_name)

# ===== 35. Garpiz UniCredit Bank CZK =====
def parse_garpiz_unicredit(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Garpiz UniCredit Bank CZK"""
    return parse_unicredit_garpiz(file_content, account_name)

# ===== 36. Garpiz_Pernink_CZK_UC =====
def parse_garpiz_pernink(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Garpiz_Pernink_CZK_UC"""
    return parse_unicredit_pernink(file_content, account_name)

# ===== 37. Koruna UniCredit- CZK =====
def parse_koruna_unicredit(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Koruna UniCredit- CZK"""
    return parse_unicredit_generic(file_content, account_name)

# ===== 38. TwoHills_Molly_Unicredit_CZK =====
def parse_twohills_unicredit(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для TwoHills_Molly_Unicredit_CZK"""
    return parse_unicredit_generic(file_content, account_name)

# ===== 39. WIO Business Bank =====
def parse_wio_business(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для WIO Business Bank"""
    return parse_unknown(file_content, account_name)

# ===== 40. Saida_Wise =====
def parse_saida_wise(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Saida_Wise"""
    return parse_unknown(file_content, account_name)


# ==================== ОБЩИЕ ПАРСЕРЫ ДЛЯ ГРУПП БАНКОВ ====================

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
    """Парсер для BluOr банка (общий)"""
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
            # BluOr формат: Дата;Описание;Сумма
            date_str = parts[0].strip()
            date = parse_date(date_str)
            if not date:
                continue
            description = parts[1].strip() if len(parts) > 1 else ''
            amount_str = parts[2].strip().replace(',', '.') if len(parts) > 2 else ''
            amount = parse_amount(amount_str)
            if amount == 0.0 and len(parts) > 3:
                amount_str = parts[3].strip().replace(',', '.')
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
        if 'date' in line.lower() and 'volume' in line.lower() and 'currency' in line.lower():
            header_idx = i
            break
    
    if header_idx == -1:
        return parse_unknown(file_content, account_name)
    
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

def parse_industra_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Industra банка"""
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

def parse_mkb_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для MKB банка"""
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
        return parse_unknown(file_content, account_name)
    
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

def parse_paysera_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Paysera банка"""
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
        if 'дата и время' in line.lower() and 'сумма и валюта' in line.lower():
            header_idx = i
            break
    
    if header_idx == -1:
        return parse_unknown(file_content, account_name)
    
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

def parse_revolut_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для Revolut банка"""
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
        if 'date started' in line.lower() and 'amount' in line.lower():
            header_idx = i
            break
    
    if header_idx == -1:
        return parse_unknown(file_content, account_name)
    
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

def parse_unicredit_generic(file_content: bytes, account_name: str) -> List[Dict]:
    """Парсер для UniCredit банка (общий)"""
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
        if 'from account' in line.lower() and 'amount' in line.lower() and 'currency' in line.lower():
            header_idx = i
            break
    
    if header_idx == -1:
        return parse_unknown(file_content, account_name)
    
    for line_idx in range(header_idx + 1, len(lines)):
        line = lines[line_idx]
        if not line:
            continue
        parts = line.split(';')
        if len(parts) < 4:
            continue
        try:
            account_num = parts[0].strip()
            if not account_num or not re.match(r'^\d+$', account_num):
                continue
            
            date_str = parts[3].strip() if len(parts) > 3 else ''
            if not date_str or not re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
                continue
            date = parse_date(date_str)
            if not date:
                continue
            
            amount_str = parts[1].strip() if len(parts) > 1 else ''
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            
            counterparty = parts[9].strip() if len(parts) > 9 else ''
            if not counterparty and len(parts) > 8:
                counterparty = parts[8].strip()
            if not counterparty and len(parts) > 6:
                counterparty = parts[6].strip()
            
            description = parts[13].strip() if len(parts) > 13 else ''
            
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

def parse_unicredit_garpiz(file_content: bytes, account_name: str) -> List[Dict]:
    """Специальный парсер для Garpiz UniCredit Bank CZK"""
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
        if 'from account' in line.lower() and 'amount' in line.lower() and 'currency' in line.lower():
            header_idx = i
            break
    
    if header_idx == -1:
        return parse_unknown(file_content, account_name)
    
    for line_idx in range(header_idx + 1, len(lines)):
        line = lines[line_idx]
        if not line:
            continue
        parts = line.split(';')
        if len(parts) < 4:
            continue
        try:
            account_num = parts[0].strip()
            if not account_num or not re.match(r'^\d+$', account_num):
                continue
            
            date_str = parts[3].strip() if len(parts) > 3 else ''
            if not date_str or not re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
                continue
            date = parse_date(date_str)
            if not date:
                continue
            
            amount_str = parts[1].strip() if len(parts) > 1 else ''
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            
            counterparty = parts[9].strip() if len(parts) > 9 else ''
            if not counterparty and len(parts) > 8:
                counterparty = parts[8].strip()
            
            description_parts = []
            if len(parts) > 13:
                val = parts[13].strip()
                if val and val != 'nan':
                    description_parts.append(val)
            
            for i, part in enumerate(parts):
                if i in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]:
                    continue
                part_clean = part.strip()
                if part_clean and part_clean != 'nan' and len(part_clean) > 1:
                    if not re.match(r'^[\d\.,\-]+$', part_clean):
                        description_parts.append(part_clean)
            
            description = ' | '.join(description_parts[:5]) if description_parts else ''
            
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

def parse_unicredit_pernink(file_content: bytes, account_name: str) -> List[Dict]:
    """Специальный парсер для Garpiz_Pernink_CZK_UC"""
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
        if 'from account' in line.lower() and 'amount' in line.lower() and 'currency' in line.lower():
            header_idx = i
            break
    
    if header_idx == -1:
        return parse_unknown(file_content, account_name)
    
    for line_idx in range(header_idx + 1, len(lines)):
        line = lines[line_idx]
        if not line:
            continue
        parts = line.split(';')
        if len(parts) < 4:
            continue
        try:
            account_num = parts[0].strip()
            if not account_num or not re.match(r'^\d+$', account_num):
                continue
            
            date_str = parts[3].strip() if len(parts) > 3 else ''
            if not date_str or not re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
                continue
            date = parse_date(date_str)
            if not date:
                continue
            
            amount_str = parts[1].strip() if len(parts) > 1 else ''
            amount = parse_amount(amount_str)
            if amount == 0.0:
                continue
            
            counterparty = parts[9].strip() if len(parts) > 9 else ''
            if not counterparty and len(parts) > 8:
                counterparty = parts[8].strip()
            
            description_parts = []
            if len(parts) > 13:
                val = parts[13].strip()
                if val and val != 'nan':
                    description_parts.append(val)
            
            for i, part in enumerate(parts):
                if i in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]:
                    continue
                part_clean = part.strip()
                if part_clean and part_clean != 'nan' and len(part_clean) > 1:
                    if not re.match(r'^[\d\.,\-]+$', part_clean):
                        description_parts.append(part_clean)
            
            description = ' | '.join(description_parts[:5]) if description_parts else ''
            
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
    """Основной парсер, определяет тип счета и вызывает соответствующий парсер"""
    account_name = clean_account_name(filename)
    
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
        'Garpiz UniCredit Bank CZK': parse_garpiz_unicredit,
        'Garpiz_Pernink_CZK_UC': parse_garpiz_pernink,
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
