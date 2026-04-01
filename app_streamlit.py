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

st.set_page_config(page_title="Аналитик выписок", page_icon="📈", layout="wide")

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

st.markdown('<div class="main-header"><h1>📊 Финансовый аналитик выписок v6.0</h1><p>Полная поддержка Paysera и других банков</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🧠 О программе")
    st.markdown("**Поддерживаемые форматы:** Excel (.xlsx, .xls), CSV")
    st.markdown("**Счет берется из имени файла**")
    st.markdown("---")
    st.markdown("**Версия 6.0** — исправлен парсинг Paysera")


# ==================== ФУНКЦИИ ПАРСИНГА ====================
def read_csv_paysera(file_content, file_name):
    """Специальный парсер для файлов Paysera"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        # Определяем кодировку
        with open(tmp_path, 'rb') as f:
            raw = f.read(10000)
        result = chardet.detect(raw)
        encoding = result['encoding'] if result['encoding'] else 'utf-8'
        
        # Читаем все строки
        with open(tmp_path, 'r', encoding=encoding) as f:
            lines = f.readlines()
        
        # Ищем строку с заголовками (Тип, Номер выписки, Номер перевода, Дата и время...)
        header_row_idx = -1
        for i, line in enumerate(lines):
            if 'Тип' in line and 'Дата и время' in line:
                header_row_idx = i
                break
        
        if header_row_idx == -1:
            return pd.DataFrame()
        
        # Парсим заголовки
        header_line = lines[header_row_idx].strip()
        # Убираем лишние кавычки в начале и конце
        if header_line.startswith('"') and header_line.endswith('"'):
            header_line = header_line[1:-1]
        
        # Разделяем по запятой, но учитываем кавычки
        headers = []
        current = ''
        in_quotes = False
        for char in header_line:
            if char == '"':
                in_quotes = not in_quotes
            elif char == ',' and not in_quotes:
                headers.append(current.strip('"').strip())
                current = ''
            else:
                current += char
        if current:
            headers.append(current.strip('"').strip())
        
        # Собираем данные
        data_rows = []
        for i in range(header_row_idx + 1, len(lines)):
            line = lines[i].strip()
            if not line:
                continue
            
            # Убираем кавычки в начале и конце строки
            if line.startswith('"') and line.endswith('"'):
                line = line[1:-1]
            
            # Парсим строку с учетом кавычек
            row = []
            current = ''
            in_quotes = False
            for char in line:
                if char == '"':
                    in_quotes = not in_quotes
                elif char == ',' and not in_quotes:
                    row.append(current.strip('"').strip())
                    current = ''
                else:
                    current += char
            if current:
                row.append(current.strip('"').strip())
            
            # Пропускаем строки с итогами
            if row and len(row) > 0 and row[0] in ['Start balance', 'Final balance', 'Debit turnover', 'Credit turnover', 'Balance']:
                continue
            
            data_rows.append(row)
        
        if not data_rows:
            return pd.DataFrame()
        
        # Выравниваем колонки
        max_cols = len(headers)
        for row in data_rows:
            while len(row) < max_cols:
                row.append('')
        
        df = pd.DataFrame(data_rows, columns=headers[:len(data_rows[0])])
        return df
        
    except Exception as e:
        st.error(f"Ошибка при чтении Paysera файла: {str(e)}")
        return pd.DataFrame()
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


def read_general_csv(file_content, file_name):
    """Общий парсер для CSV файлов"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        # Определяем кодировку
        with open(tmp_path, 'rb') as f:
            raw = f.read(10000)
        result = chardet.detect(raw)
        encoding = result['encoding'] if result['encoding'] else 'utf-8'
        
        # Пробуем разные разделители
        for sep in [';', ',', '\t', '|']:
            try:
                df = pd.read_csv(tmp_path, sep=sep, encoding=encoding, header=None, 
                                on_bad_lines='skip', engine='python')
                if len(df.columns) > 1 and len(df) > 0:
                    return df
            except:
                continue
        
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


def read_excel_file(file_content, file_name):
    """Парсер для Excel файлов"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        df = pd.read_excel(tmp_path, header=None, engine='openpyxl')
        return df
    except:
        try:
            df = pd.read_excel(tmp_path, header=None)
            return df
        except:
            return pd.DataFrame()
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


def read_file(file_content, file_name):
    """Универсальный парсер файлов"""
    file_lower = file_name.lower()
    
    # Для Paysera используем специальный парсер
    if 'paysera' in file_lower and file_name.endswith('.csv'):
        return read_csv_paysera(file_content, file_name)
    
    # Для CSV
    if file_name.endswith('.csv'):
        return read_general_csv(file_content, file_name)
    
    # Для Excel
    if file_name.endswith(('.xlsx', '.xls')):
        return read_excel_file(file_content, file_name)
    
    return pd.DataFrame()


def parse_date(date_str):
    if pd.isna(date_str):
        return ''
    date_str = str(date_str).strip()
    
    # Обработка формата Paysera: "2026-03-16 08:18:22 +0100"
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]
    if 'T' in date_str:
        date_str = date_str.split('T')[0]

    formats = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d", "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except:
            continue

    if '.' in date_str:
        parts = date_str.split('.')
        if len(parts) == 3 and len(parts[2]) == 4:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
        if len(parts) == 3 and len(parts[2]) == 2:
            year = 2000 + int(parts[2])
            return f"{year}-{parts[1]}-{parts[0]}"
    if '-' in date_str and len(date_str) >= 10:
        return date_str[:10]
    return date_str


def parse_amount(amount_str, description=""):
    """Парсинг суммы из разных форматов"""
    if pd.isna(amount_str):
        return 0
    amount_str = str(amount_str).strip()
    if amount_str in ['', 'nan', '-', 'None', 'null', 'NaN']:
        return 0
    
    original = amount_str
    
    # Удаляем валюту
    amount_str = re.sub(r',[A-Z]{3}$', '', amount_str)
    amount_str = re.sub(r'[A-Z]{3}$', '', amount_str)
    
    # Удаляем пробелы и заменяем запятую
    amount_str = amount_str.replace(' ', '').replace('\xa0', '')
    amount_str = amount_str.replace(',', '.')
    
    # Определяем знак
    is_negative = amount_str.startswith('-')
    amount_str = amount_str.lstrip('-')
    
    # Убираем всё кроме цифр и точки
    amount_str = re.sub(r'[^\d.]', '', amount_str)
    if not amount_str:
        return 0
    
    # Контекстное определение знака
    desc_lower = description.lower()
    if not is_negative:
        expense_keywords = [
            'fee', 'charge', 'комиссия', 'tax', 'налог', 'apmaksa', 
            'nodokļu', 'spisanie', 'списание', 'payment', 'оплата'
        ]
        if any(kw in desc_lower for kw in expense_keywords):
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
        return 0


# ==================== ОПРЕДЕЛЕНИЕ СТАТЬИ ====================
def get_article(description, amount):
    desc_lower = description.lower()
    
    if amount < 0:
        # Расходы
        if any(kw in desc_lower for kw in ['комиссия', 'commission', 'fee', 'charge', 'maintenance', 'service package']):
            return '1.2.17 РКО'
        if any(kw in desc_lower for kw in ['зарплат', 'salary', 'darba alga', 'algas izmaksa']):
            return '1.2.15.1 Зарплата'
        if any(kw in desc_lower for kw in ['nodokļu nomaksa', 'vid', 'budžets', 'налог', 'tax']):
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
        if any(kw in desc_lower for kw in ['rigas namu pārvaldnieks', 'latvijas namsaimnieks', 'biedrība']):
            return '1.2.10.6 Коммунальные УК дома'
        if any(kw in desc_lower for kw in ['tele2', 'bite', 'tet', 'internet', 'связь']):
            return '1.2.9.1 Связь, интернет, TV'
        if any(kw in desc_lower for kw in ['google one', 'lovable', 'openai', 'chatgpt', 'it сервисы']):
            return '1.2.9.3 IT сервисы'
        if any(kw in desc_lower for kw in ['facebook', 'facbk', 'tiktok', 'ads', 'marketing', 'реклам']):
            return '1.2.3 Оплата рекламных систем (бюджет)'
        if any(kw in desc_lower for kw in ['flydubai', 'taxi', 'flixbus', 'bolt', 'uber', 'travel']):
            return '1.2.2 Командировочные расходы'
        if any(kw in desc_lower for kw in ['apmaksa par rēķinu', 'обслуживание', 'ремонт', 'lifti']):
            return '1.2.8.1 Обслуживание объектов'
        if any(kw in desc_lower for kw in ['balta', 'страхование', 'insurance']):
            return '1.2.8.2 Страхование'
        if any(kw in desc_lower for kw in ['бухгалтер', 'accounting', 'loseva']):
            return '1.2.12 Бухгалтер'
        if any(kw in desc_lower for kw in ['pirkuma liguma', 'приобретение недвижимости']):
            return '2.2.7 Расходы по приобретению недвижимости'
        if any(kw in desc_lower for kw in ['currency exchange', 'конвертация', 'internal payment']):
            return 'Перевод между счетами'
        return '1.2.8.1 Обслуживание объектов'
    else:
        # Доходы
        if any(kw in desc_lower for kw in ['airbnb', 'booking.com']):
            return '1.1.1.2 Поступления систем бронирования (Airbnb, Booking и пр.)'
        if any(kw in desc_lower for kw in ['depozits', 'депозит', 'deposit', 'guarantee']):
            return '1.1.1.4 Получение гарантийного депозита'
        if any(kw in desc_lower for kw in ['commission', 'agency commissions', 'incoming swift payment']):
            return '1.1.4.1 Комиссия за продажу недвижимости'
        if any(kw in desc_lower for kw in ['loan', 'займ', 'baltic solutions', 'loan payment']):
            return '3.1.3 Получение внутригруппового займа'
        if any(kw in desc_lower for kw in ['loan return', 'возврат займа', 'partial repayment']):
            return '3.1.4 Возврат выданного внутригруппового займа'
        if any(kw in desc_lower for kw in ['komunālie', 'utilities', 'компенсац', 'возмещени']):
            return '1.1.2.3 Компенсация по коммунальным расходам'
        if any(kw in desc_lower for kw in ['кэшбэк', 'cashback', 'interest']):
            return '1.1.2.4 Прочие мелкие поступления'
        if any(kw in desc_lower for kw in ['refund', 'возврат', 'reversal']):
            return '1.1.2.2 Возвраты от поставщиков'
        if any(kw in desc_lower for kw in ['арендн', 'rent', 'money added', 'topup', 'received']):
            return '1.1.1.3 Арендная плата (счёт)'
        return '1.1.1.3 Арендная плата (счёт)'


# ==================== ОПРЕДЕЛЕНИЕ НАПРАВЛЕНИЙ ====================
def get_direction(description, file_name):
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
    if any(x in file_lower for x in ['budapest']) or 'yulia galvin' in desc_lower:
        return 'Europe', 'F6 Помещение в доме Будапешт'
    if any(x in file_lower for x in ['dzibik']) or 'bilych nadiia' in desc_lower:
        return 'Europe', 'DZ1_Dzibik1'
    if 'bastet' in desc_lower:
        return 'Europe', 'J91 Ялтская - Помещение маленькое'
    if any(x in desc_lower for x in ['masaryka', 'tgm45']):
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
        return 'East-Восток', 'UKA - UK_AZ-Аренда'
    
    if any(x in file_lower for x in ['mashreq', 'wio']):
        return 'Nomiqa', 'BNQ_BAKU-Nomiqa'
    
    return 'UK Estate', ''


# ==================== РАЗБИВКА АРЕНДНЫХ ПЛАТЕЖЕЙ ====================
def should_split_rental(description, amount):
    if amount <= 0:
        return False
    
    desc_lower = description.lower()
    
    exclude = ['booking.com', 'airbnb', 'loan', 'deposit', 'commission', 'fee', 'tax', 'salary', 'refund', 'valsts', 'latvenergo', 'rigas udens']
    if any(kw in desc_lower for kw in exclude):
        return False
    
    rent_keywords = ['rent', 'аренд', 'caka', 'antonijas', 'matisa', 'valdemara', 'money added', 'topup', 'from']
    if not any(kw in desc_lower for kw in rent_keywords):
        return False
    
    return True


def calculate_split(amount, description):
    desc_lower = description.lower()
    
    if any(x in desc_lower for x in ['caka', 'ac89', 'čaka']):
        return round(amount * 0.836, 2), round(amount * 0.164, 2)
    if any(x in desc_lower for x in ['antonijas', 'an14']):
        return round(amount * 0.8, 2), round(amount * 0.2, 2)
    if any(x in desc_lower for x in ['matisa', 'm81']):
        return round(amount * 0.7, 2), round(amount * 0.3, 2)
    if any(x in desc_lower for x in ['valdemara', 'v22']):
        return round(amount * 0.55, 2), round(amount * 0.45, 2)
    
    return round(amount * 0.85, 2), round(amount * 0.15, 2)


# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
def parse_file(file_content, file_name):
    df = read_file(file_content, file_name)
    
    if df is None or df.empty:
        st.warning(f"⚠️ Не удалось прочитать файл {file_name}")
        return []
    
    # Поиск колонок
    date_col = None
    amount_col = None
    desc_col = None
    debit_col = None
    credit_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        if date_col is None and any(kw in col_lower for kw in ['date', 'дата', 'дата и время', 'value date']):
            date_col = col
        if amount_col is None and any(kw in col_lower for kw in ['amount', 'сумма', 'сумма и валюта']):
            amount_col = col
        if desc_col is None and any(kw in col_lower for kw in ['description', 'описание', 'назначение платежа', 'purpose']):
            desc_col = col
        if debit_col is None and any(kw in col_lower for kw in ['debit', 'дебет', 'д', 'расход']):
            debit_col = col
        if credit_col is None and any(kw in col_lower for kw in ['credit', 'кредит', 'к', 'доход']):
            credit_col = col
    
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
            amount = 0
            
            # Пробуем amount_col
            if amount_col in row:
                amount_val = row[amount_col]
                if pd.notna(amount_val):
                    amount = parse_amount(amount_val)
            
            # Пробуем debit/credit
            if amount == 0 and debit_col in row and credit_col in row:
                debit_val = row[debit_col] if debit_col in row else None
                credit_val = row[credit_col] if credit_col in row else None
                
                if pd.notna(debit_val) and str(debit_val).strip():
                    amount = parse_amount(debit_val)
                    if amount != 0:
                        amount = -abs(amount)
                elif pd.notna(credit_val) and str(credit_val).strip():
                    amount = parse_amount(credit_val)
                    if amount != 0:
                        amount = abs(amount)
            
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
                if col not in [date_col, amount_col, desc_col, debit_col, credit_col]:
                    val = row[col]
                    if pd.notna(val) and str(val).strip() and str(val) != 'nan':
                        description += ' ' + str(val)
            
            description = description.strip()
            
            # Валюта
            currency = 'EUR'
            if 'czk' in file_name.lower():
                currency = 'CZK'
            elif 'huf' in file_name.lower():
                currency = 'HUF'
            elif 'azn' in file_name.lower():
                currency = 'AZN'
            elif 'aed' in file_name.lower():
                currency = 'AED'
            
            account_name = file_name.replace('.csv', '').replace('.xlsx', '').replace('.xls', '')
            
            # Определяем статью и направление
            article = get_article(description, amount)
            direction, subdirection = get_direction(description, file_name)
            
            # Разбивка арендных платежей
            if should_split_rental(description, amount):
                rent_share, util_share = calculate_split(amount, description)
                
                if rent_share > 0:
                    transactions.append({
                        'Дата': date,
                        'Сумма': rent_share,
                        'Валюта': currency,
                        'Счет': account_name,
                        'Статья': article,
                        'Направление': direction,
                        'Субнаправление': subdirection,
                        'Описание': f"{description[:300]} (аренда)",
                        'Исходный файл': file_name
                    })
                
                if util_share > 0:
                    transactions.append({
                        'Дата': date,
                        'Сумма': util_share,
                        'Валюта': currency,
                        'Счет': account_name,
                        'Статья': '1.1.2.3 Компенсация по коммунальным расходам',
                        'Направление': direction,
                        'Субнаправление': subdirection,
                        'Описание': f"{description[:300]} (компенсация КУ)",
                        'Исходный файл': file_name
                    })
            else:
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Валюта': currency,
                    'Счет': account_name,
                    'Статья': article,
                    'Направление': direction,
                    'Субнаправление': subdirection,
                    'Описание': description[:500],
                    'Исходный файл': file_name
                })
                
        except Exception as e:
            continue
    
    return transactions


# ==================== ИНТЕРФЕЙС ====================
def main():
    tab1, tab2 = st.tabs(["📂 Один файл", "📚 Несколько файлов"])
    
    with tab1:
        st.markdown("### Загрузите выписку для анализа")
        uploaded_file = st.file_uploader("Выберите файл", type=['csv', 'xlsx', 'xls'], key="single")
        
        if uploaded_file:
            st.success(f"✅ Файл загружен: {uploaded_file.name}")
            
            if st.button("🚀 Запустить анализ", key="single_btn"):
                with st.spinner("Анализируем..."):
                    content = uploaded_file.read()
                    transactions = parse_file(content, uploaded_file.name)
                    
                    if transactions:
                        df = pd.DataFrame(transactions)
                        
                        st.markdown("---")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("📊 Всего операций", len(transactions))
                        with col2:
                            доход = df[df['Сумма'] > 0]['Сумма'].sum()
                            st.metric("📈 Доходы", f"{доход:,.2f}")
                        with col3:
                            расход = abs(df[df['Сумма'] < 0]['Сумма'].sum())
                            st.metric("📉 Расходы", f"{расход:,.2f}")
                        
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
            type=['csv', 'xlsx', 'xls'], 
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
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("📊 Всего операций", len(all_transactions))
                        with col2:
                            доход = df[df['Сумма'] > 0]['Сумма'].sum()
                            st.metric("📈 Доходы", f"{доход:,.2f}")
                        with col3:
                            расход = abs(df[df['Сумма'] < 0]['Сумма'].sum())
                            st.metric("📉 Расходы", f"{расход:,.2f}")
                        
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
