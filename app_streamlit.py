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
import csv

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
.success-box {
    background-color: #d4edda;
    border: 1px solid #c3e6cb;
    border-radius: 10px;
    padding: 1rem;
    margin: 1rem 0;
}
.warning-box {
    background-color: #fff3cd;
    border: 1px solid #ffeaa7;
    border-radius: 10px;
    padding: 1rem;
    margin: 1rem 0;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>📊 Финансовый аналитик выписок v5.2</h1><p>Полная поддержка всех форматов банковских выписок</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🧠 О программе")
    st.markdown("**Поддерживаемые форматы:**")
    st.markdown("- Excel (.xlsx, .xls)")
    st.markdown("- CSV (разные разделители)")
    st.markdown("- Текстовые файлы")
    st.markdown("---")
    st.markdown("**Поддерживаемые банки:**")
    st.markdown("- Pasha Bank (AZN, AED)")
    st.markdown("- CSOB Bank (CZK)")
    st.markdown("- UniCredit Bank (CZK)")
    st.markdown("- Industra Bank (EUR)")
    st.markdown("- Kapital Bank (AZN)")
    st.markdown("- Mashreq Bank (AED)")
    st.markdown("- WIO Bank (AED)")
    st.markdown("- Revolut (EUR)")
    st.markdown("- Paysera (EUR)")
    st.markdown("- MKB Budapest (EUR, HUF)")
    st.markdown("---")
    st.markdown("**Версия 5.2** — исправлена обработка MKB Budapest")

# ==================== КОНФИГУРАЦИЯ ====================
class Config:
    """Конфигурация приложения"""
    DATE_FORMATS = [
        "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d",
        "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d", "%d.%m.%y",
        "%d/%m/%y", "%y-%m-%d", "%d-%b-%y", "%d-%b-%Y",
        "%b %d, %Y", "%d %b %Y", "%Y%m%d"
    ]
    
    CSV_DELIMITERS = [';', ',', '\t', '|', ':', '~']
    
    ENCODINGS = ['utf-8', 'utf-8-sig', 'windows-1251', 'cp1251', 'iso-8859-1', 'latin-1', 'cp1252', 'mac_roman']
    
    CURRENCIES = {
        'EUR': 'EUR', 'CZK': 'CZK', 'HUF': 'HUF', 'AZN': 'AZN',
        'AED': 'AED', 'RUB': 'RUB', 'USD': 'USD', 'GBP': 'GBP', 'PLN': 'PLN'
    }


# ==================== КЛАСС УМНОГО ДЕТЕКТОРА ЗАГОЛОВКОВ ====================
class HeaderDetector:
    def __init__(self):
        self.header_patterns = {
            'date': [
                'date', 'дата', 'datum', 'dátum', 'transaction date', 'value date',
                'booking date', 'дата транзакции', 'дата операции', 'posting date',
                'Date started (UTC)', 'Дата', 'Date completed (UTC)', 'дата валютирования'
            ],
            'amount': [
                'amount', 'сумма', 'összeg', 'betrag', 'дебет', 'кредит', 'debit(d)',
                'credit(c)', 'сумма списания', 'сумма зачисления', 'доход', 'расход',
                'orig amount', 'payment amount', 'Total amount', 'Amount', 'Сумма'
            ],
            'debit': ['debit', 'дебет', 'расход', 'withdrawal', 'списание', 'debet'],
            'credit': ['credit', 'кредит', 'доход', 'deposit', 'зачисление'],
            'description': [
                'description', 'описание', 'leírás', 'beschreibung', 'details',
                'transaction details', 'назначение платежа', 'narrative', 'information',
                'Purpose of payment', 'particulars', 'beneficiary', 'Description'
            ],
            'balance': ['balance', 'остаток', 'egyenleg', 'saldo', 'closing balance'],
            'serial': ['serial number', 'sorszám', 'номер', 'no.']
        }
        
        self.file_patterns = {
            'industra': [r'industra', r'индустра', r'plavas'],
            'revolut': [r'revolut', r'револют'],
            'budapest': [r'budapest', r'будапешт', r'mkb'],
            'pasha': [r'pasha', r'паша', r'bunda'],
            'kapital': [r'kapital', r'капитал', r'saida'],
            'csob': [r'csob', r'čsob', r'dzibik'],
            'unicredit': [r'unicredit', r'uni credit', r'garpiz', r'koruna', r'twohills'],
            'mashreq': [r'mashreq'],
            'wio': [r'wio'],
            'wise': [r'wise'],
            'paysera': [r'paysera']
        }

    def detect_file_type(self, filename: str) -> str:
        filename_lower = filename.lower()
        for file_type, patterns in self.file_patterns.items():
            for pattern in patterns:
                if re.search(pattern, filename_lower, re.IGNORECASE):
                    return file_type
        return "unknown"

    def find_header_row(self, df: pd.DataFrame, max_rows_to_check: int = 50) -> int:
        if df.empty:
            return -1
        
        rows_to_check = min(max_rows_to_check, len(df))
        best_score = 0
        best_row = -1
        
        for row_idx in range(rows_to_check):
            row = df.iloc[row_idx]
            score = self._calculate_header_score(row)
            if score > best_score:
                best_score = score
                best_row = row_idx
        
        if best_score >= 2:
            return best_row
        return -1

    def _calculate_header_score(self, row: pd.Series) -> int:
        score = 0
        header_keywords_found = set()
        
        for cell in row:
            if pd.isna(cell):
                continue
            cell_str = str(cell).lower().strip()
            
            for category, keywords in self.header_patterns.items():
                for kw in keywords:
                    if kw in cell_str:
                        if category not in header_keywords_found:
                            header_keywords_found.add(category)
                            score += 2
                        else:
                            score += 1
                        break
            
            if re.match(r'^-?\d+[.,]\d{2}$', cell_str.replace(' ', '')):
                score -= 2
            if re.match(r'\d{4}[-./]\d{1,2}[-./]\d{1,2}', cell_str):
                score -= 2
        
        return max(0, score)

    def validate_header_row(self, df: pd.DataFrame, header_row: int) -> bool:
        if header_row < 0 or header_row >= len(df):
            return False
        
        header = df.iloc[header_row]
        numeric_count = 0
        total_cells = len(header)
        
        for cell in header:
            if pd.isna(cell):
                continue
            cell_str = str(cell).strip()
            try:
                float(cell_str.replace(',', '.'))
                numeric_count += 1
            except:
                if re.match(r'\d{4}[-./]\d{1,2}[-./]\d{1,2}', cell_str):
                    numeric_count += 1
        
        return numeric_count <= total_cells * 0.4


# ==================== ФУНКЦИИ ПАРСИНГА ====================
def detect_csv_delimiter(file_path: str, sample_size: int = 2048) -> str:
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        sample = f.read(sample_size)
    
    delimiter_counts = {}
    for delimiter in Config.CSV_DELIMITERS:
        count = sample.count(delimiter)
        if count > 0:
            delimiter_counts[delimiter] = count
    
    if not delimiter_counts:
        if '"' in sample and ',' in sample:
            return ','
        return ','
    
    return max(delimiter_counts.items(), key=lambda x: x[1])[0]

def detect_file_encoding(file_path: str, sample_size: int = 4096) -> str:
    with open(file_path, 'rb') as f:
        raw_data = f.read(sample_size)
    
    result = chardet.detect(raw_data)
    encoding = result['encoding'] if result['encoding'] else 'utf-8'
    
    if encoding.lower() in ['windows-1251', 'cp1251']:
        return 'windows-1251'
    elif encoding.lower() == 'iso-8859-1':
        return 'latin-1'
    elif encoding.lower() == 'ascii':
        return 'utf-8'
    
    return encoding

def read_file(file_content: bytes, file_name: str) -> pd.DataFrame:
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        file_ext = os.path.splitext(file_name)[1].lower()
        
        if file_ext in ['.xlsx', '.xls']:
            try:
                excel_file = pd.ExcelFile(tmp_path, engine='openpyxl')
                sheet_names = excel_file.sheet_names
                
                for sheet in sheet_names:
                    sheet_lower = sheet.lower()
                    if any(kw in sheet_lower for kw in ['транзакции', 'transactions', 'операции', 'operations', 'statement', 'выписка', 'f122']):
                        df = pd.read_excel(tmp_path, sheet_name=sheet, header=None, engine='openpyxl')
                        break
                else:
                    df = pd.read_excel(tmp_path, header=None, engine='openpyxl')
                
                return df
            except:
                try:
                    df = pd.read_excel(tmp_path, header=None)
                except:
                    encoding = detect_file_encoding(tmp_path)
                    delimiter = detect_csv_delimiter(tmp_path)
                    df = pd.read_csv(tmp_path, sep=delimiter, encoding=encoding, header=None,
                                    engine='python', on_bad_lines='skip')
                return df
        else:
            encoding = detect_file_encoding(tmp_path)
            delimiter = detect_csv_delimiter(tmp_path)
            
            try:
                df = pd.read_csv(tmp_path, sep=delimiter, encoding=encoding, header=None,
                                engine='python', on_bad_lines='skip', quotechar='"')
            except:
                for delim in Config.CSV_DELIMITERS:
                    if delim != delimiter:
                        try:
                            df = pd.read_csv(tmp_path, sep=delim, encoding=encoding, header=None,
                                            engine='python', on_bad_lines='skip', quotechar='"')
                            break
                        except:
                            continue
                else:
                    with open(tmp_path, 'r', encoding=encoding, errors='ignore') as f:
                        lines = f.readlines()
                    
                    data = []
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        parts_found = False
                        for delim in Config.CSV_DELIMITERS:
                            if delim in line:
                                parts = [part.strip('"\' ') for part in line.split(delim)]
                                data.append(parts)
                                parts_found = True
                                break
                        if not parts_found:
                            data.append([line])
                    
                    if data:
                        max_cols = max(len(row) for row in data)
                        for row in data:
                            while len(row) < max_cols:
                                row.append('')
                        df = pd.DataFrame(data)
                    else:
                        df = pd.DataFrame()
            
            return df
    
    except Exception as e:
        st.error(f"Ошибка при чтении файла {file_name}: {str(e)}")
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
    
    date_str = re.sub(r'[^\d./\- :]', '', date_str)
    
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
    
    if re.match(r'^\d{8}$', date_str):
        try:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        except:
            pass
    
    return date_str

def parse_amount(amount_str, is_debit_col=False, is_credit_col=False, description="") -> float:
    if pd.isna(amount_str):
        return 0.0
    
    amount_str = str(amount_str).strip()
    
    if amount_str in ['', 'nan', '-', 'None', 'null', 'NaN', 'N/A', 'n/a']:
        return 0.0
    
    original_str = amount_str
    
    if amount_str.startswith('-+'):
        amount_str = '-' + amount_str[2:]
    elif amount_str.startswith('+-'):
        amount_str = '-' + amount_str[2:]
    
    amount_str = re.sub(r'\s*[A-Z]{3}\s*$', '', amount_str)
    amount_str = re.sub(r'^\s*[A-Z]{3}\s*', '', amount_str)
    amount_str = amount_str.replace(' ', '').replace('\xa0', '')
    amount_str = amount_str.replace(',', '.')
    amount_str = re.sub(r'[^\d.\-]', '', amount_str)
    
    if not amount_str or amount_str == '-':
        return 0.0
    
    is_negative = amount_str.startswith('-')
    amount_str = amount_str.lstrip('-')
    
    if is_debit_col:
        is_negative = True
    elif is_credit_col:
        is_negative = False
    
    desc_lower = description.lower() if description else ""
    if not is_negative:
        expense_keywords = [
            'fee', 'charge', 'комиссия', 'tax', 'налог', 'to ', 'transfer to',
            'списание', 'снятие', 'оплата', 'payment', 'платеж', 'withdrawal',
            'дебит', 'расход', 'стоимость', 'цена', 'cost', 'price', 'purchase'
        ]
        income_keywords = [
            'from', 'received', 'incoming', 'deposit', 'зачисление', 'пополнение',
            'возврат', 'refund', 'компенсация', 'income', 'доход', 'поступление'
        ]
        
        has_expense = any(keyword in desc_lower for keyword in expense_keywords)
        has_income = any(keyword in desc_lower for keyword in income_keywords)
        
        if has_expense and not has_income:
            is_negative = True
        elif has_income and not has_expense:
            is_negative = False
    
    try:
        value = float(amount_str)
        return -abs(value) if is_negative else abs(value)
    except:
        numbers = re.findall(r'-?\d+[.,]\d+', original_str)
        if numbers:
            try:
                value = float(numbers[0].replace(',', '.'))
                return -abs(value) if is_negative else abs(value)
            except:
                pass
        
        numbers = re.findall(r'-?\d+', original_str)
        if numbers:
            try:
                value = float(numbers[0])
                return -abs(value) if is_negative else abs(value)
            except:
                pass
        
        return 0.0


# ==================== ОПРЕДЕЛЕНИЕ СТАТЕЙ ====================
class ArticleClassifier:
    def __init__(self):
        self.parent_articles = {
            '1.1.1': 'Поступления за аренду недвижимости и земельных участков',
            '1.1.2': 'Прочие поступления',
            '1.1.4': 'Поступления за оказание услуг',
            '1.2.2': 'Командировочные расходы',
            '1.2.3': 'Оплата рекламных систем (бюджет)',
            '1.2.8': 'Обслуживание объектов',
            '1.2.9': 'Услуги ИТ и связи',
            '1.2.10': 'Коммунальные платежи',
            '1.2.15': 'Зарплата и налоги на ФОТ',
            '1.2.16': 'Налоги',
            '1.2.17': 'РКО',
            '1.2.21': 'Офисные расходы',
            '1.2.24': 'Расходы по отдельному бизнесу',
            '1.2.27': 'Расходы в ожидании возмещения ЗП',
            '1.2.28': 'Расходы за другие компании группы',
            '1.2.34': 'Вознаграждение инвестора',
            '1.2.37': 'Возврат гарантийных депозитов',
            '2.2.7': 'Расходы по приобретению недвижимости',
            '3.1.1': 'Ввод средств',
            '3.1.3': 'Получение внутригруппового займа',
            '3.1.4': 'Возврат выданного займа'
        }
        
        self.expense_articles = {
            '1.2.17 РКО': [
                'комиссия', 'commission', 'fee', 'charge', 'maintenance', 'rko',
                'плата за обслуживание', 'service package', 'számlakivonat díja',
                'netbankár monthly fee', 'conversion fee', 'bank charge',
                'monthly fee', 'account maintenance', 'card fee', 'transaction fee'
            ],
            '1.2.15.1 Зарплата': [
                'зарплат', 'salary', 'darba alga', 'algas izmaksa', 'wage', 'payroll'
            ],
            '1.2.15.2 Налоги на ФОТ': [
                'nodokļu nomaksa', 'vid', 'budžets', 'налог', 'valsts budžets',
                'social tax', 'подоходный налог', 'income tax', 'dsmf'
            ],
            '1.2.16.3 НДС': [
                'value added tax', 'vat', 'ндс', 'pvn', 'output tax', 'dph', 'iva'
            ],
            '1.2.16.1 Налог на недвижимость': [
                'nekustamā īpašuma nodoklis', 'налог на недвижимость', 'property tax'
            ],
            '1.2.10.5 Электричество': [
                'latvenergo', 'elektri', 'электричеств', 'electricity', 'power'
            ],
            '1.2.10.3 Вода': [
                'rigas udens', 'ūdens', 'вода', 'water'
            ],
            '1.2.10.2 Газ': [
                'gāze', 'газ', 'gas', 'heating'
            ],
            '1.2.10.1 Мусор': [
                'atkritumi', 'мусор', 'eco baltia', 'clean r', 'waste'
            ],
            '1.2.10.6 Коммунальные УК дома': [
                'rigas namu pārvaldnieks', 'latvijas namsaimnieks', 'biedrība',
                'управляющая компания', 'management fee'
            ],
            '1.2.9.1 Связь, интернет, TV': [
                'tele2', 'bite', 'tet', 'internet', 'связь', 'telenet', 'wifi'
            ],
            '1.2.9.3 IT сервисы': [
                'google one', 'lovable', 'openai', 'chatgpt', 'browsec', 'adobe',
                'albato', 'slack', 'it сервисы', 'software', 'subscription'
            ],
            '1.2.3 Оплата рекламных систем': [
                'facebook', 'facbk', 'tiktok', 'ads', 'marketing', 'реклам',
                'instagram', 'google ads', 'fb ads', 'propertyfinder'
            ],
            '1.2.2 Командировочные расходы': [
                'flydubai', 'taxi', 'flixbus', 'bolt', 'uber', 'careem',
                'travel', 'transport', 'hotel', 'авиабилеты', 'tickets',
                'командировка', 'dubai taxi', 'enoc', 'emarat'
            ],
            '1.2.8.1 Обслуживание объектов': [
                'apmaksa par rēķinu', 'обслуживание', 'ремонт', 'lifti', 'taipans',
                'sidorans', 'komval', 'rīgas lifti', 'maintenance'
            ],
            '1.2.8.2 Страхование': [
                'balta', 'страхование', 'insurance', 'insure'
            ],
            '1.2.12 Бухгалтер': [
                'lubova loseva', 'loseva', 'бухгалтер', 'accounting'
            ],
            '2.2.7 Расходы по приобретению недвижимости': [
                'pirkuma liguma', 'приобретение недвижимости', 'property purchase',
                'аванс покупной стоимости', 'rezervacni smlouva'
            ],
            '1.2.27 Расходы в ожидании возмещения': [
                'jl/nf', 'jl/zp', 'расходы в ожидании', 'other business'
            ],
            '1.2.37 Возврат гарантийных депозитов': [
                'deposit return', 'возврат депозита', 'depozīta atgriešana'
            ],
            '1.2.24 Расходы по отдельному бизнесу': [
                'vzr div', 'nav', 'personal income', 'social security',
                'giro payment', 'transaction fee part'
            ],
            '1.2.28 Расходы за другие компании': [
                'относится к александру', 'за другие компании', 'revelton'
            ],
            '1.2.34 Вознаграждение инвестора': [
                'вознаграждение инвестора', 'investor reward', 'bs property', 'bs rerum'
            ],
            'Перевод между счетами': [
                'currency exchange', 'конвертация', 'internal payment',
                'transfer to own account', 'между своими счетами',
                'ipp transfer', 'inter company transfer', 'same-day own account transfer'
            ]
        }
        
        self.income_articles = {
            '1.1.1.2 Поступления систем бронирования': [
                'airbnb', 'booking.com', 'booking b.v.'
            ],
            '1.1.1.4 Получение гарантийного депозита': [
                'depozits', 'депозит', 'deposit', 'guarantee', 'security deposit'
            ],
            '1.1.4.1 Комиссия за продажу недвижимости': [
                'commission', 'agency commissions', 'incoming swift payment',
                'marketing and advertisement', 'consultancy fees', 'real estate commission',
                'inward remittance', 'fund transfer'
            ],
            '3.1.3 Получение внутригруппового займа': [
                'loan', 'займ', 'baltic solutions', 'payment acc loan agreement'
            ],
            '3.1.4 Возврат выданного займа': [
                'loan return', 'возврат займа', 'partial repayment', 'repayment'
            ],
            '3.1.1 Ввод средств': [
                'transfer to own account', 'между своими счетами', 'own transfer',
                'fx spot/fwd payment', 'конвертация валюты'
            ],
            '1.1.2.3 Компенсация по коммунальным расходам': [
                'komunālie', 'utilities', 'компенсац', 'возмещени', 'communal'
            ],
            '1.1.2.4 Прочие мелкие поступления': [
                'кэшбэк', 'cashback', 'u rok do', 'interest', 'проценты'
            ],
            '1.1.2.2 Возвраты от поставщиков': [
                'return on request', 'возврат', 'refund', 'reversal', 'vat reversal'
            ],
            '1.1.1.1 Арендная плата (наличные)': [
                'наличные', 'cash', 'cash payment'
            ],
            '1.1.1.3 Арендная плата (счёт)': [
                'арендн', 'rent', 'money added', 'ire', 'dzivoklis', 'from',
                'credit of sepa', 'topup', 'received', 'incoming payment',
                'sent from', 'поступление', 'rent payment', 'nájemné', 'kira'
            ]
        }
    
    def get_article(self, description: str, amount: float, file_name: str) -> Tuple[str, str]:
        desc_lower = description.lower()
        
        if amount < 0:
            for article, keywords in self.expense_articles.items():
                for keyword in keywords:
                    if keyword in desc_lower:
                        article_code = article.split(' ')[0]
                        parent_code = '.'.join(article_code.split('.')[:2])
                        parent_article = self.parent_articles.get(parent_code, "")
                        return article, parent_article
            return '1.2.8.1 Обслуживание объектов', '1.2.8 Обслуживание объектов'
        else:
            for article, keywords in self.income_articles.items():
                for keyword in keywords:
                    if keyword in desc_lower:
                        article_code = article.split(' ')[0]
                        parent_code = '.'.join(article_code.split('.')[:2])
                        parent_article = self.parent_articles.get(parent_code, "")
                        return article, parent_article
            return '1.1.1.3 Арендная плата (счёт)', '1.1.1 Поступления за аренду'


# ==================== ОПРЕДЕЛЕНИЕ НАПРАВЛЕНИЙ ====================
class DirectionClassifier:
    def __init__(self):
        self.directions = {
            'Latvia': [
                ('AN14 Антониас 14', ['antonijas', 'an14']),
                ('AC89 Чака 89', ['caka', 'ac89', 'čaka']),
                ('M81 - Matisa 81', ['matisa', 'm81']),
                ('B117 Бривибас, 117', ['brīvības 117', 'b117']),
                ('B78 Бривибас, 78', ['brīvības 78', 'b78']),
                ('G77 Гертрудес, 77', ['gertrudes', 'g77']),
                ('V22 К. Валдемара 22', ['valdemara', 'v22']),
                ('MU3 - Mucenieku 3 - 4', ['mucenieku', 'mu3']),
                ('DS1 Дзирнаву, 1', ['dzirnavu', 'ds1']),
                ('C23 Цесу, 23', ['cesu', 'c23']),
                ('SK3-Skunju 3', ['skunu', 'sk3']),
                ('D4 Парковка-Deglava4', ['deglava', 'd4']),
                ('H5 Хоспиталю', ['hospitalu', 'h5']),
                ('BRN_Brunieku', ['bruninieku', 'brn']),
                ('AC87 Гараж Чака', ['ac87', 'caka 87'])
            ],
            'Europe': [
                ('F6 Помещение в доме Будапешт', ['budapest', 'f6', 'yulia galvin']),
                ('DZ1_Dzibik1', ['dzibik', 'dz1', 'bilych nadiia']),
                ('J91 Ялтская', ['j91', 'ялтская', 'bastet']),
                ('TGM45 Масарика', ['masaryka', 'tgm45', 'bagel lounge']),
                ('OT1_Otovice', ['otovice', 'ot1', 'komplekt']),
                ('MOL - Офис Molly', ['twohills', 'molly', 'mol']),
                ('LT_Vilnus', ['sveciy', 'vilnus']),
                ('TGM20-Masaryka20', ['garpiz', 'tgm20']),
                ('Pernik', ['pernik'])
            ],
            'East-Восток': [
                ('BIS - Baku', ['icheri', 'bis', 'baku', 'cordiality']),
                ('UKA - UK_AZ-Аренда', ['uka', 'uk_az', 'азербайджан'])
            ],
            'Nomiqa': [
                ('BNQ_BAKU-Nomiqa', ['bnq', 'baku-nomiqa']),
                ('DNQ_Dubai-Nomiqa', ['dnq', 'dubai-nomiqa', 'nomiqa real estate', 'mashreq'])
            ],
            'Unelma': [
                ('UK_Unelma', ['unelma'])
            ],
            'Отдельный бизнес': [
                ('', ['jl/nf', 'jl/zp', 'отдельный бизнес', 'в ожидании возмещения'])
            ]
        }
    
    def get_direction(self, file_name: str, description: str, payer: str = "") -> Tuple[str, str]:
        file_lower = file_name.lower()
        desc_lower = description.lower()
        payer_lower = payer.lower() if payer else ""
        
        combined_text = f"{desc_lower} {payer_lower} {file_lower}"
        
        for direction, subdirections in self.directions.items():
            for subdirection, keywords in subdirections:
                for keyword in keywords:
                    if keyword in combined_text:
                        return direction, subdirection
        
        if any(x in file_lower for x in ['pasha', 'kapital', 'bunda', 'azn', 'azerbaijan']):
            return 'East-Восток', 'UKA - UK_AZ-Аренда'
        if any(x in file_lower for x in ['mashreq', 'wio', 'aed', 'dubai', 'uae']):
            return 'Nomiqa', 'DNQ_Dubai-Nomiqa'
        if any(x in file_lower for x in ['csob', 'unicredit', 'czk', 'czech', 'praha', 'budapest', 'mkb']):
            return 'Europe', 'UK_EU'
        if any(x in file_lower for x in ['industra', 'revolut', 'paysera', 'latvia', 'riga']):
            return 'Latvia', 'UK_Latvia'
        
        return 'UK Estate', ''


# ==================== РАЗБИВКА АРЕНДНЫХ ПЛАТЕЖЕЙ ====================
class RentalSplitter:
    def __init__(self):
        self.split_ratios = {
            'AC89 Чака 89': (0.836, 0.164),
            'AN14 Антониас 14': (0.80, 0.20),
            'M81 - Matisa 81': (0.70, 0.30),
            'B117 Бривибас, 117': (0.85, 0.15),
            'V22 К. Валдемара 22': (0.55, 0.45),
            'G77 Гертрудес, 77': (0.85, 0.15),
            'default': (0.85, 0.15)
        }
    
    def should_split(self, description: str, amount: float, file_name: str, subdirection: str) -> bool:
        if amount <= 0:
            return False
        
        desc_lower = description.lower()
        
        exclude_keywords = [
            'booking.com', 'airbnb', 'loan', 'deposit', 'депозит',
            'commission', 'комиссия', 'fee', 'charge', 'tax', 'налог',
            'salary', 'зарплата', 'refund', 'возврат', 'interest',
            'valsts budžets', 'latvenergo', 'rigas udens', 'bite', 'tele2',
            'inward remittance', 'fund transfer', 'conversion'
        ]
        
        for kw in exclude_keywords:
            if kw in desc_lower:
                return False
        
        rent_keywords = [
            'rent', 'аренд', 'caka', 'antonijas', 'matisa', 'valdemara',
            'for rent', 'dzivoklis', 'apartment', 'ire',
            'money added', 'topup', 'from', 'received'
        ]
        
        has_rent_keyword = any(kw in desc_lower for kw in rent_keywords)
        valid_subdirections = list(self.split_ratios.keys())
        has_valid_subdirection = any(sd in subdirection for sd in valid_subdirections)
        
        return has_rent_keyword and has_valid_subdirection
    
    def calculate_split(self, amount: float, subdirection: str) -> Tuple[float, float]:
        ratio = self.split_ratios.get(subdirection, self.split_ratios['default'])
        rent_share = round(amount * ratio[0], 2)
        utility_share = round(amount * ratio[1], 2)
        
        total = rent_share + utility_share
        if abs(total - amount) > 0.01:
            if rent_share > utility_share:
                rent_share = round(rent_share + (amount - total), 2)
            else:
                utility_share = round(utility_share + (amount - total), 2)
        
        return rent_share, utility_share


# ==================== ОСНОВНАЯ ФУНКЦИЯ ПАРСИНГА ====================
def parse_file(file_content: bytes, file_name: str) -> List[Dict]:
    df = read_file(file_content, file_name)
    
    if df is None or df.empty:
        st.warning(f"⚠️ Не удалось прочитать файл {file_name}")
        return []
    
    file_lower = file_name.lower()
    
    # ========== СПЕЦИАЛЬНАЯ ОБРАБОТКА ДЛЯ MKB BUDAPEST ==========
    if 'budapest' in file_lower or 'mkb' in file_lower:
        # Ищем строку с заголовками (Serial number, Value date, etc.)
        header_row = None
        for idx, row in df.iterrows():
            row_str = ' '.join([str(cell).lower() for cell in row if pd.notna(cell)])
            if 'serial number' in row_str and 'value date' in row_str:
                header_row = idx
                break
        
        if header_row is not None:
            # Извлекаем заголовки
            headers = []
            for i, cell in enumerate(df.iloc[header_row].values):
                if pd.isna(cell):
                    headers.append(f'col_{i}')
                else:
                    headers.append(str(cell).strip())
            
            # Создаем DataFrame с данными
            data_rows = []
            for idx in range(header_row + 1, len(df)):
                row = list(df.iloc[idx].values)
                # Пропускаем пустые строки
                if all(str(cell).strip() == '' for cell in row):
                    continue
                if len(row) < len(headers):
                    row.extend([''] * (len(headers) - len(row)))
                elif len(row) > len(headers):
                    row = row[:len(headers)]
                data_rows.append(row)
            
            df = pd.DataFrame(data_rows, columns=headers)
    
    # ========== СТАНДАРТНОЕ ОПРЕДЕЛЕНИЕ ЗАГОЛОВКОВ ==========
    detector = HeaderDetector()
    header_row = detector.find_header_row(df)
    
    if header_row >= 0 and detector.validate_header_row(df, header_row):
        headers = []
        for i, h in enumerate(df.iloc[header_row].values):
            if pd.isna(h):
                headers.append(f'col_{i}')
            else:
                headers.append(str(h).strip())
        
        data_rows = []
        for idx in range(header_row + 1, len(df)):
            row = list(df.iloc[idx].values)
            if len(row) < len(headers):
                row.extend([''] * (len(headers) - len(row)))
            elif len(row) > len(headers):
                row = row[:len(headers)]
            data_rows.append(row)
        
        df = pd.DataFrame(data_rows, columns=headers)
    
    if df.empty:
        st.warning(f"⚠️ В файле {file_name} не найдено данных для обработки")
        return []
    
    # Определение колонок
    date_col = None
    amount_col = None
    debit_col = None
    credit_col = None
    desc_col = None
    payer_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        
        if date_col is None and any(kw in col_lower for kw in detector.header_patterns['date']):
            date_col = col
        if amount_col is None and any(kw in col_lower for kw in detector.header_patterns['amount']):
            amount_col = col
        if debit_col is None and any(kw in col_lower for kw in detector.header_patterns['debit']):
            debit_col = col
        if credit_col is None and any(kw in col_lower for kw in detector.header_patterns['credit']):
            credit_col = col
        if desc_col is None and any(kw in col_lower for kw in detector.header_patterns['description']):
            desc_col = col
        if payer_col is None and any(kw in col_lower for kw in ['payer', 'плательщик', 'получатель', 'beneficiary']):
            payer_col = col
    
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]
    
    if desc_col is None and len(df.columns) > 1:
        desc_col = df.columns[1]
    
    # Для MKB Budapest: колонка Amount обычно 9-я (индекс 9)
    if 'budapest' in file_lower and amount_col is None and debit_col is None and credit_col is None:
        if len(df.columns) > 9:
            amount_col = df.columns[9]
    
    # Инициализация классификаторов
    article_classifier = ArticleClassifier()
    direction_classifier = DirectionClassifier()
    rental_splitter = RentalSplitter()
    
    transactions = []
    
    for idx in range(len(df)):
        try:
            row = df.iloc[idx]
            
            # Описание
            description = ''
            if desc_col is not None and desc_col in row:
                desc_val = row[desc_col]
                if pd.notna(desc_val):
                    description = str(desc_val)
            
            # Плательщик
            payer = ''
            if payer_col is not None and payer_col in row:
                payer_val = row[payer_col]
                if pd.notna(payer_val) and str(payer_val).strip():
                    payer = str(payer_val)
                    description = f"{description} {payer}"
            
            # Добавляем другие колонки
            for col in df.columns:
                if col not in [date_col, amount_col, debit_col, credit_col, desc_col, payer_col]:
                    val = row[col]
                    if pd.notna(val) and str(val).strip() and str(val) != 'nan':
                        try:
                            float(str(val).replace(',', '.'))
                            continue
                        except:
                            description += ' ' + str(val)
            
            description = description.strip()
            
            # Дата
            date = ''
            if date_col is not None and date_col in row:
                date_val = row[date_col]
                if pd.notna(date_val):
                    date = parse_date(date_val)
            
            if not date:
                continue
            
            # Сумма
            amount = 0.0
            
            # Пробуем amount_col
            if amount_col is not None and amount_col in row:
                amount_val = row[amount_col]
                if pd.notna(amount_val) and str(amount_val).strip():
                    amount = parse_amount(amount_val, description=description)
            
            # Пробуем debit/credit
            if amount == 0 and debit_col is not None and debit_col in row:
                debit_val = row[debit_col]
                if pd.notna(debit_val) and str(debit_val).strip():
                    amount = parse_amount(debit_val, is_debit_col=True, description=description)
            
            if amount == 0 and credit_col is not None and credit_col in row:
                credit_val = row[credit_col]
                if pd.notna(credit_val) and str(credit_val).strip():
                    amount = parse_amount(credit_val, is_credit_col=True, description=description)
            
            if amount == 0:
                continue
            
            # Валюта
            currency = 'EUR'
            if 'czk' in file_lower or 'czech' in file_lower:
                currency = 'CZK'
            elif 'huf' in file_lower or 'hungary' in file_lower:
                currency = 'HUF'
            elif 'azn' in file_lower:
                currency = 'AZN'
            elif 'aed' in file_lower or 'uae' in file_lower:
                currency = 'AED'
            elif 'rub' in file_lower:
                currency = 'RUB'
            
            account_name = file_name.replace('.csv', '').replace('.xlsx', '').replace('.xls', '').replace('.txt', '')
            
            # Определение направления
            direction, subdirection = direction_classifier.get_direction(file_name, description, payer)
            
            # Определение статьи
            article, parent_article = article_classifier.get_article(description, amount, file_name)
            
            # Разбивка арендных платежей
            if rental_splitter.should_split(description, amount, file_name, subdirection):
                rent_share, utility_share = rental_splitter.calculate_split(amount, subdirection)
                
                if rent_share > 0:
                    transactions.append({
                        'Дата': date,
                        'Сумма': rent_share,
                        'НДС': 0.0,
                        'Счет': account_name,
                        'Валюта': currency,
                        'Контрагент': payer,
                        'Статья': article,
                        'Род. статья': parent_article,
                        'Описание': f"{description[:300]} (аренда)",
                        'Направление': direction,
                        'Субнаправление': subdirection,
                        'Месяц начисления': date[:7] if date else '',
                        'Исходный файл': file_name
                    })
                
                if utility_share > 0:
                    transactions.append({
                        'Дата': date,
                        'Сумма': utility_share,
                        'НДС': 0.0,
                        'Счет': account_name,
                        'Валюта': currency,
                        'Контрагент': payer,
                        'Статья': '1.1.2.3 Компенсация по коммунальным расходам',
                        'Род. статья': '1.1.2 Прочие поступления',
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
                    'Контрагент': payer,
                    'Статья': article,
                    'Род. статья': parent_article,
                    'Описание': description[:500],
                    'Направление': direction,
                    'Субнаправление': subdirection,
                    'Месяц начисления': date[:7] if date else '',
                    'Исходный файл': file_name
                })
        
        except Exception as e:
            continue
    
    return transactions


# ==================== ИНТЕРФЕЙС ====================
def main():
    tab1, tab2, tab3 = st.tabs(["📂 Один файл", "📚 Несколько файлов", "⚙️ Настройки"])
    
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
    
    with tab3:
        st.markdown("### Настройки анализа")
        st.markdown("#### Форматы дат")
        for fmt in Config.DATE_FORMATS[:8]:
            st.write(f"- `{fmt}`")
        st.markdown("#### Разделители CSV")
        for delim in Config.CSV_DELIMITERS:
            st.write(f"- `{delim}`" if delim != '\t' else "- `\\t` (табуляция)")
        st.markdown("#### Валюты")
        for code, name in Config.CURRENCIES.items():
            st.write(f"- `{code}`")


if __name__ == "__main__":
    main()
