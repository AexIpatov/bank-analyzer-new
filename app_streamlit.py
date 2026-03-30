import streamlit as st
import pandas as pd
import io
import tempfile
import os
import chardet
import re
from datetime import datetime
from io import BytesIO
import numpy as np
from typing import List, Dict, Tuple, Optional

st.set_page_config(page_title="Финансовый аналитик выписок", page_icon="📈", layout="wide")

st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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

st.markdown('<div class="main-header"><h1>📊 Финансовый аналитик выписок v6.2</h1><p>Полная поддержка всех форматов</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🧠 О программе")
    st.markdown("**Поддерживаемые форматы:** Excel (.xlsx, .xls), CSV, TXT")
    st.markdown("**Поддерживаемые банки:** Pasha, CSOB, UniCredit, Industra, Kapital, Mashreq, WIO, Revolut, Paysera, MKB Budapest")
    st.markdown("---")
    st.markdown("**Версия 6.2** — исправлены отступы")

class Config:
    DATE_FORMATS = [
        "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d",
        "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d", "%d.%m.%y",
        "%d/%m/%y", "%y-%m-%d", "%d-%b-%y", "%d-%b-%Y",
        "%b %d, %Y", "%d %b %Y", "%Y%m%d"
    ]
    CSV_DELIMITERS = [';', ',', '\t', '|', ':', '~']
    ENCODINGS = ['utf-8', 'utf-8-sig', 'windows-1251', 'cp1251', 'latin-1']
    CURRENCIES = {'EUR': 'EUR', 'CZK': 'CZK', 'HUF': 'HUF', 'AZN': 'AZN', 'AED': 'AED', 'RUB': 'RUB'}


def detect_encoding(file_path: str) -> str:
    with open(file_path, 'rb') as f:
        raw = f.read(10000)
    result = chardet.detect(raw)
    return result['encoding'] if result['encoding'] else 'utf-8'


def detect_delimiter(file_path: str, encoding: str) -> str:
    with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
        sample = f.read(5000)
    for delim in Config.CSV_DELIMITERS:
        if sample.count(delim) > 5:
            return delim
    return ','


def read_file(file_content: bytes, file_name: str) -> pd.DataFrame:
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        file_ext = os.path.splitext(file_name)[1].lower()
        
        if file_ext in ['.xlsx', '.xls']:
            try:
                df = pd.read_excel(tmp_path, header=None, engine='openpyxl')
                return df
            except:
                try:
                    df = pd.read_excel(tmp_path, header=None)
                    return df
                except:
                    return pd.DataFrame()
        else:
            encoding = detect_encoding(tmp_path)
            delimiter = detect_delimiter(tmp_path, encoding)
            try:
                df = pd.read_csv(tmp_path, sep=delimiter, encoding=encoding, header=None,
                                engine='python', on_bad_lines='skip')
                return df
            except:
                return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


def parse_mkb_budapest(file_content: bytes, file_name: str) -> pd.DataFrame:
    """Специальный парсер для выписок MKB Budapest"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xls') as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        # Читаем Excel
        try:
            df_raw = pd.read_excel(tmp_path, header=None, engine='openpyxl')
        except:
            df_raw = pd.read_excel(tmp_path, header=None)
        
        if df_raw.empty:
            return pd.DataFrame()
        
        # Ищем строку с "Serial number" (обычно строка 4, индекс 3)
        header_row = -1
        for idx in range(min(20, len(df_raw))):
            row_text = ' '.join([str(cell).lower() for cell in df_raw.iloc[idx] if pd.notna(cell)])
            if 'serial number' in row_text and 'value date' in row_text:
                header_row = idx
                break
        
        if header_row == -1:
            return pd.DataFrame()
        
        # Получаем заголовки
        headers = []
        for cell in df_raw.iloc[header_row]:
            if pd.isna(cell):
                headers.append('')
            else:
                headers.append(str(cell).strip())
        
        # Собираем данные со строк после заголовка
        data = []
        for idx in range(header_row + 1, len(df_raw)):
            row = df_raw.iloc[idx]
            # Пропускаем пустые строки
            if all(pd.isna(cell) or str(cell).strip() == '' for cell in row):
                continue
            # Пропускаем строки с итогами
            first_cell = str(row.iloc[0]).lower() if len(row) > 0 else ''
            if first_cell in ['start balance', 'final balance', 'debit turnover', 'credit turnover']:
                continue
            data.append(list(row))
        
        if not data:
            return pd.DataFrame()
        
        # Выравниваем колонки
        max_cols = len(headers)
        for row in data:
            while len(row) < max_cols:
                row.append('')
        
        df = pd.DataFrame(data, columns=headers[:len(data[0])])
        
        # Оставляем только нужные колонки
        keep_cols = []
        for col in df.columns:
            col_lower = str(col).lower()
            if any(kw in col_lower for kw in ['serial number', 'value date', 'amount', 'narrative', 'beneficiary', 'transaction type', 'currency']):
                keep_cols.append(col)
        
        if keep_cols:
            df = df[keep_cols]
        
        return df
        
    except Exception as e:
        return pd.DataFrame()
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


def parse_date(date_str) -> str:
    if pd.isna(date_str):
        return ''
    date_str = str(date_str).strip()
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    
    date_str = re.sub(r'[^\d./\-]', '', date_str)
    
    for fmt in Config.DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except:
            continue
    
    if '.' in date_str:
        parts = date_str.split('.')
        if len(parts) == 3:
            day, month, year = parts
            if len(year) == 2:
                year = f"20{year}"
            try:
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            except:
                pass
    
    return date_str


def parse_amount(amount_str, description="") -> float:
    if pd.isna(amount_str):
        return 0.0
    
    amount_str = str(amount_str).strip()
    if amount_str in ['', 'nan', '-', 'None', 'null', 'NaN']:
        return 0.0
    
    original = amount_str
    
    if amount_str.startswith('-+'):
        amount_str = '-' + amount_str[2:]
    if amount_str.startswith('+-'):
        amount_str = '-' + amount_str[2:]
    
    amount_str = re.sub(r'\s*[A-Z]{3}\s*$', '', amount_str)
    amount_str = re.sub(r'^\s*[A-Z]{3}\s*', '', amount_str)
    amount_str = amount_str.replace(' ', '').replace('\xa0', '')
    amount_str = amount_str.replace(',', '.')
    
    is_negative = amount_str.startswith('-')
    amount_str = amount_str.lstrip('-')
    amount_str = re.sub(r'[^\d.]', '', amount_str)
    
    if not amount_str:
        return 0.0
    
    # Контекстное определение знака
    if not is_negative and description:
        desc_lower = description.lower()
        expense_words = ['fee', 'charge', 'комиссия', 'tax', 'налог', 'to ', 'payment', 'оплата', 'списание']
        if any(w in desc_lower for w in expense_words):
            is_negative = True
    
    try:
        val = float(amount_str)
        return -abs(val) if is_negative else abs(val)
    except:
        numbers = re.findall(r'-?\d+[.,]\d+', original)
        if numbers:
            try:
                val = float(numbers[0].replace(',', '.'))
                return -abs(val) if is_negative else abs(val)
            except:
                pass
        return 0.0


def get_article(description: str, amount: float) -> str:
    desc_lower = description.lower()
    
    if amount < 0:
        # Расходы
        if any(kw in desc_lower for kw in ['комиссия', 'commission', 'fee', 'charge', 'maintenance', 'monthly fee', 'számlakivonat', 'netbankár', 'conversion fee', 'bank charge', 'popl.', 'vedeni', 'balicek']):
            return '1.2.17 РКО'
        if any(kw in desc_lower for kw in ['зарплат', 'salary', 'darba alga', 'algas izmaksa']):
            return '1.2.15.1 Зарплата'
        if any(kw in desc_lower for kw in ['nodokļu nomaksa', 'vid', 'budžets', 'налог', 'valsts budžets', 'tax']):
            return '1.2.15.2 Налоги на ФОТ'
        if any(kw in desc_lower for kw in ['value added tax', 'vat', 'ндс', 'pvn']):
            return '1.2.16.3 НДС'
        if any(kw in desc_lower for kw in ['latvenergo', 'elektri', 'электричеств', 'electricity']):
            return '1.2.10.5 Электричество'
        if any(kw in desc_lower for kw in ['rigas udens', 'ūdens', 'вода', 'water']):
            return '1.2.10.3 Вода'
        if any(kw in desc_lower for kw in ['gāze', 'газ', 'gas', 'heating']):
            return '1.2.10.2 Газ'
        if any(kw in desc_lower for kw in ['atkritumi', 'мусор', 'eco baltia', 'clean r']):
            return '1.2.10.1 Мусор'
        if any(kw in desc_lower for kw in ['rigas namu pārvaldnieks', 'latvijas namsaimnieks', 'biedrība', 'управляющая компания']):
            return '1.2.10.6 Коммунальные УК дома'
        if any(kw in desc_lower for kw in ['tele2', 'bite', 'tet', 'internet', 'связь', 'telenet']):
            return '1.2.9.1 Связь, интернет, TV'
        if any(kw in desc_lower for kw in ['google one', 'lovable', 'openai', 'chatgpt', 'browsec', 'adobe', 'slack', 'it сервисы']):
            return '1.2.9.3 IT сервисы'
        if any(kw in desc_lower for kw in ['facebook', 'facbk', 'tiktok', 'ads', 'marketing', 'реклам']):
            return '1.2.3 Оплата рекламных систем (бюджет)'
        if any(kw in desc_lower for kw in ['flydubai', 'taxi', 'flixbus', 'bolt', 'uber', 'careem', 'travel', 'hotel']):
            return '1.2.2 Командировочные расходы'
        if any(kw in desc_lower for kw in ['apmaksa par rēķinu', 'обслуживание', 'ремонт', 'lifti', 'maintenance']):
            return '1.2.8.1 Обслуживание объектов'
        if any(kw in desc_lower for kw in ['balta', 'страхование', 'insurance']):
            return '1.2.8.2 Страхование'
        if any(kw in desc_lower for kw in ['бухгалтер', 'accounting', 'loseva']):
            return '1.2.12 Бухгалтер'
        if any(kw in desc_lower for kw in ['pirkuma liguma', 'приобретение недвижимости', 'property purchase']):
            return '2.2.7 Расходы по приобретению недвижимости'
        if any(kw in desc_lower for kw in ['currency exchange', 'конвертация', 'internal payment', 'transfer to own account', 'ipp transfer', 'inter company transfer']):
            return 'Перевод между счетами'
        return '1.2.8.1 Обслуживание объектов'
    else:
        # Доходы
        if any(kw in desc_lower for kw in ['airbnb', 'booking.com']):
            return '1.1.1.2 Поступления систем бронирования (Airbnb, Booking и пр.)'
        if any(kw in desc_lower for kw in ['depozits', 'депозит', 'deposit', 'guarantee']):
            return '1.1.1.4 Получение гарантийного депозита'
        if any(kw in desc_lower for kw in ['commission', 'agency commissions', 'incoming swift payment', 'marketing and advertisement', 'inward remittance']):
            return '1.1.4.1 Комиссия за продажу недвижимости'
        if any(kw in desc_lower for kw in ['loan', 'займ', 'baltic solutions', 'loan payment']):
            return '3.1.3 Получение внутригруппового займа'
        if any(kw in desc_lower for kw in ['loan return', 'возврат займа', 'partial repayment']):
            return '3.1.4 Возврат выданного внутригруппового займа'
        if any(kw in desc_lower for kw in ['transfer to own account', 'между своими счетами']):
            return '3.1.1 Ввод средств'
        if any(kw in desc_lower for kw in ['komunālie', 'utilities', 'компенсац', 'возмещени']):
            return '1.1.2.3 Компенсация по коммунальным расходам'
        if any(kw in desc_lower for kw in ['кэшбэк', 'cashback', 'interest']):
            return '1.1.2.4 Прочие мелкие поступления'
        if any(kw in desc_lower for kw in ['refund', 'возврат', 'reversal']):
            return '1.1.2.2 Возвраты от поставщиков'
        if any(kw in desc_lower for kw in ['арендн', 'rent', 'money added', 'topup', 'received', 'incoming payment']):
            return '1.1.1.3 Арендная плата (счёт)'
        return '1.1.1.3 Арендная плата (счёт)'


def get_direction(description: str, file_name: str) -> Tuple[str, str]:
    desc_lower = description.lower()
    file_lower = file_name.lower()
    
    # Latvia
    if any(x in desc_lower for x in ['antonijas', 'an14']):
        return 'Latvia', 'AN14 Антониас 14 (дом + парковка)'
    if any(x in desc_lower for x in ['caka', 'ac89', 'čaka']):
        return 'Latvia', 'AC89 Чака 89 (дом + парковка)'
    if any(x in desc_lower for x in ['matisa', 'm81']):
        return 'Latvia', 'M81 - Matisa 81'
    if any(x in desc_lower for x in ['brīvības 117', 'b117']):
        return 'Latvia', 'B117 Бривибас, 117'
    if any(x in desc_lower for x in ['valdemara', 'v22']):
        return 'Latvia', 'V22 К. Валдемара 22'
    if any(x in desc_lower for x in ['gertrudes', 'g77']):
        return 'Latvia', 'G77 Гертрудес, 77'
    if any(x in desc_lower for x in ['mucenieku', 'mu3']):
        return 'Latvia', 'MU3 - Mucenieku 3 - 4'
    if any(x in desc_lower for x in ['dzirnavu', 'ds1']):
        return 'Latvia', 'DS1 Дзирнаву, 1'
    if any(x in desc_lower for x in ['cesu', 'c23']):
        return 'Latvia', 'C23 Цесу, 23'
    if any(x in desc_lower for x in ['skunu', 'sk3']):
        return 'Latvia', 'SK3-Skunju 3'
    if any(x in desc_lower for x in ['deglava', 'd4']):
        return 'Latvia', 'D4 Парковка-Deglava4'
    if any(x in desc_lower for x in ['hospitalu', 'h5']):
        return 'Latvia', 'H5 Хоспиталю'
    if any(x in desc_lower for x in ['bruninieku', 'brn']):
        return 'Latvia', 'BRN_Brunieku'
    
    # Europe
    if any(x in file_lower for x in ['budapest', 'mkb']) or 'yulia galvin' in desc_lower:
        return 'Europe', 'F6 Помещение в доме Будапешт'
    if any(x in file_lower for x in ['dzibik', 'csob']) or 'bilych nadiia' in desc_lower:
        return 'Europe', 'DZ1_Dzibik1'
    if 'bastet' in desc_lower:
        return 'Europe', 'J91 Ялтская - Помещение маленькое'
    if any(x in desc_lower for x in ['masaryka', 'tgm45', 'bagel lounge']):
        return 'Europe', 'TGM45 Масарика - Bagel Lounge'
    if any(x in desc_lower for x in ['otovice', 'komplekt']):
        return 'Europe', 'OT1_Otovice Участок Свалка'
    if any(x in file_lower for x in ['twohills', 'molly']):
        return 'Europe', 'MOL - Офис Molly'
    if any(x in file_lower for x in ['sveciy', 'vilnus']):
        return 'Europe', 'LT_Vilnus'
    if any(x in file_lower for x in ['garpiz']):
        return 'Europe', 'TGM20-Masaryka20'
    
    # East
    if any(x in file_lower for x in ['pasha', 'kapital', 'bunda']):
        if any(x in desc_lower for x in ['nomiqa', 'bnq', 'dnq']):
            return 'Nomiqa', 'BNQ_BAKU-Nomiqa'
        if any(x in desc_lower for x in ['icheri', 'bis', 'baku']):
            return 'East-Восток', 'BIS - Baku, Icheri Sheher 1,2'
        return 'East-Восток', 'UKA - UK_AZ-Аренда'
    
    if any(x in file_lower for x in ['mashreq', 'wio']):
        if 'dubai' in desc_lower:
            return 'Nomiqa', 'DNQ_Dubai-Nomiqa'
        return 'Nomiqa', 'BNQ_BAKU-Nomiqa'
    
    return 'UK Estate', ''


def should_split_rental(description: str, amount: float, subdirection: str) -> bool:
    if amount <= 0:
        return False
    
    desc_lower = description.lower()
    
    exclude = ['booking.com', 'airbnb', 'loan', 'deposit', 'commission', 'fee', 'tax', 'salary', 'refund']
    if any(kw in desc_lower for kw in exclude):
        return False
    
    rent_keywords = ['rent', 'аренд', 'caka', 'antonijas', 'matisa', 'valdemara', 'money added', 'topup']
    if not any(kw in desc_lower for kw in rent_keywords):
        return False
    
    valid_sub = ['AC89 Чака 89', 'AN14 Антониас 14', 'M81 - Matisa 81', 'B117 Бривибас, 117', 'V22 К. Валдемара 22', 'G77 Гертрудес, 77']
    return any(sd in subdirection for sd in valid_sub)


def calculate_split(amount: float, subdirection: str) -> Tuple[float, float]:
    ratios = {
        'AC89 Чака 89': (0.836, 0.164),
        'AN14 Антониас 14': (0.80, 0.20),
        'M81 - Matisa 81': (0.70, 0.30),
        'B117 Бривибас, 117': (0.85, 0.15),
        'V22 К. Валдемара 22': (0.55, 0.45),
        'G77 Гертрудес, 77': (0.85, 0.15),
    }
    
    ratio = ratios.get(subdirection, (0.85, 0.15))
    rent = round(amount * ratio[0], 2)
    util = round(amount * ratio[1], 2)
    
    total = rent + util
    if abs(total - amount) > 0.01:
        if rent > util:
            rent = round(rent + (amount - total), 2)
        else:
            util = round(util + (amount - total), 2)
    
    return rent, util


def parse_file(file_content: bytes, file_name: str) -> List[Dict]:
    file_lower = file_name.lower()
    
    # Специальная обработка для MKB Budapest
    if 'budapest' in file_lower or 'mkb' in file_lower:
        df = parse_mkb_budapest(file_content, file_name)
        if df.empty:
            df = read_file(file_content, file_name)
    else:
        df = read_file(file_content, file_name)
    
    if df.empty:
        st.warning(f"⚠️ Не удалось прочитать файл {file_name}")
        return []
    
    # Поиск колонок
    date_col = None
    amount_col = None
    desc_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        if date_col is None and any(kw in col_lower for kw in ['date', 'дата', 'value date', 'booking date']):
            date_col = col
        if amount_col is None and any(kw in col_lower for kw in ['amount', 'сумма', 'total amount', 'payment amount']):
            amount_col = col
        if desc_col is None and any(kw in col_lower for kw in ['description', 'описание', 'narrative', 'purpose', 'details', 'beneficiary']):
            desc_col = col
    
    # Для MKB: колонка Amount часто 9-я
    if 'budapest' in file_lower and amount_col is None:
        if len(df.columns) > 9:
            amount_col = df.columns[9]
    
    # Если не нашли колонку описания, используем колонку с самым длинным текстом
    if desc_col is None:
        max_len = 0
        for col in df.columns:
            try:
                avg_len = df[col].astype(str).str.len().mean()
                if avg_len > max_len:
                    max_len = avg_len
                    desc_col = col
            except:
                pass
    
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]
    
    transactions = []
    
    for idx in range(len(df)):
        try:
            row = df.iloc[idx]
            
            # Пропускаем пустые строки
            if all(pd.isna(cell) or str(cell).strip() == '' for cell in row):
                continue
            
            # Дата
            date = ''
            if date_col in row:
                date_val = row[date_col]
                if pd.notna(date_val):
                    date = parse_date(date_val)
            if not date:
                continue
            
            # Сумма
            amount = 0.0
            if amount_col in row:
                amount_val = row[amount_col]
                if pd.notna(amount_val):
                    amount = parse_amount(amount_val)
            
            if amount == 0:
                continue
            
            # Описание
            description = ''
            if desc_col in row:
                desc_val = row[desc_col]
                if pd.notna(desc_val):
                    description = str(desc_val)
            
            # Добавляем другие колонки
            for col in df.columns:
                if col not in [date_col, amount_col, desc_col]:
                    val = row[col]
                    if pd.notna(val) and str(val).strip() and str(val) != 'nan':
                        description += ' ' + str(val)
            
            description = description.strip()
            
            # Валюта
            currency = 'EUR'
            if 'czk' in file_lower:
                currency = 'CZK'
            elif 'huf' in file_lower:
                currency = 'HUF'
            elif 'azn' in file_lower:
                currency = 'AZN'
            elif 'aed' in file_lower:
                currency = 'AED'
            
            account_name = file_name.replace('.csv', '').replace('.xlsx', '').replace('.xls', '').replace('.txt', '')
            
            # Определяем статью и направление
            article = get_article(description, amount)
            direction, subdirection = get_direction(description, file_name)
            
            # Разбивка арендных платежей
            if should_split_rental(description, amount, subdirection):
                rent_share, util_share = calculate_split(amount, subdirection)
                
                if rent_share > 0:
                    transactions.append({
                        'Дата': date,
                        'Сумма': rent_share,
                        'НДС': 0.0,
                        'Счет': account_name,
                        'Валюта': currency,
                        'Контрагент': '',
                        'Статья': article,
                        'Род. статья': '',
                        'Описание': f"{description[:300]} (аренда)",
                        'Направление': direction,
                        'Субнаправление': subdirection,
                        'Месяц начисления': date[:7] if date else '',
                        'Исходный файл': file_name
                    })
                
                if util_share > 0:
                    transactions.append({
                        'Дата': date,
                        'Сумма': util_share,
                        'НДС': 0.0,
                        'Счет': account_name,
                        'Валюта': currency,
                        'Контрагент': '',
                        'Статья': '1.1.2.3 Компенсация по коммунальным расходам',
                        'Род. статья': '',
                        'Описание': f"{description[:300]} (компенсация КУ)",
                        'Направление': direction,
                        'Субнаправление': subdirection,
                        'Месяц начисления': date[:7] if date else '',
                        'Исходный файл': file_name
                    })
            else:
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'НДС': 0.0,
                    'Счет': account_name,
                    'Валюта': currency,
                    'Контрагент': '',
                    'Статья': article,
                    'Род. статья': '',
                    'Описание': description[:500],
                    'Направление': direction,
                    'Субнаправление': subdirection,
                    'Месяц начисления': date[:7] if date else '',
                    'Исходный файл': file_name
                })
        
        except Exception as e:
            continue
    
    return transactions


def main():
    tab1, tab2 = st.tabs(["📂 Один файл", "📚 Несколько файлов"])
    
    with tab1:
        st.markdown("### Загрузите выписку для анализа")
        uploaded_file = st.file_uploader("Выберите файл", type=['csv', 'xlsx', 'xls', 'txt'], key="single")
        
        if uploaded_file:
            st.success(f"✅ Файл загружен: {uploaded_file.name}")
            
            if st.button("🚀 Запустить анализ", key="single_btn"):
                with st.spinner("Анализируем..."):
                    content = uploaded_file.read()
                    transactions = parse_file(content, uploaded_file.name)
                    
                    if transactions:
                        df = pd.DataFrame(transactions)
                        
                        st.markdown("---")
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("📊 Всего операций", len(transactions))
                        with col2:
                            доход = df[df['Сумма'] > 0]['Сумма'].sum()
                            st.metric("📈 Доходы", f"{доход:,.2f}")
                        with col3:
                            расход = abs(df[df['Сумма'] < 0]['Сумма'].sum())
                            st.metric("📉 Расходы", f"{расход:,.2f}")
                        with col4:
                            баланс = доход - расход
                            st.metric("💰 Баланс", f"{баланс:,.2f}")
                        
                        st.markdown("### 📋 Обработанные транзакции")
                        st.dataframe(df, use_container_width=True)
                        
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df.to_excel(writer, sheet_name='Транзакции', index=False)
                        
                        output.seek(0)
                        st.download_button(
                            label="📥 Скачать Excel",
                            data=output,
                            file_name=f"анализ_{uploaded_file.name.split('.')[0]}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.error("❌ Не удалось обработать файл. Проверьте формат файла.")
    
    with tab2:
        st.markdown("### Загрузите несколько файлов для анализа")
        uploaded_files = st.file_uploader(
            "Выберите файлы", 
            type=['csv', 'xlsx', 'xls', 'txt'], 
            accept_multiple_files=True,
            key="multiple"
        )
        
        if uploaded_files:
            st.success(f"✅ Загружено файлов: {len(uploaded_files)}")
            
            if st.button("🚀 Запустить анализ всех файлов", key="multiple_btn"):
                all_transactions = []
                
                with st.spinner("Анализируем файлы..."):
                    progress_bar = st.progress(0)
                    
                    for i, uploaded_file in enumerate(uploaded_files):
                        try:
                            content = uploaded_file.read()
                            transactions = parse_file(content, uploaded_file.name)
                            all_transactions.extend(transactions)
                            progress_bar.progress((i + 1) / len(uploaded_files))
                            st.info(f"✅ Обработан {uploaded_file.name}: {len(transactions)} операций")
                        except Exception as e:
                            st.error(f"❌ Ошибка при обработке {uploaded_file.name}: {str(e)}")
                    
                    if all_transactions:
                        df = pd.DataFrame(all_transactions)
                        
                        st.markdown("---")
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("📊 Всего операций", len(all_transactions))
                        with col2:
                            доход = df[df['Сумма'] > 0]['Сумма'].sum()
                            st.metric("📈 Доходы", f"{доход:,.2f}")
                        with col3:
                            расход = abs(df[df['Сумма'] < 0]['Сумма'].sum())
                            st.metric("📉 Расходы", f"{расход:,.2f}")
                        with col4:
                            баланс = доход - расход
                            st.metric("💰 Баланс", f"{баланс:,.2f}")
                        
                        st.markdown("### 📋 Все обработанные транзакции")
                        st.dataframe(df, use_container_width=True)
                        
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df.to_excel(writer, sheet_name='Все транзакции', index=False)
                        
                        output.seek(0)
                        st.download_button(
                            label="📥 Скачать Excel",
                            data=output,
                            file_name="анализ_всех_файлов.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.error("❌ Не удалось обработать файлы. Проверьте форматы файлов.")


if __name__ == "__main__":
    main()
