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

st.markdown('<div class="main-header"><h1>📊 Финансовый аналитик выписок v6.0</h1><p>Полная поддержка всех форматов банковских выписок</p></div>', unsafe_allow_html=True)

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
    st.markdown("**Версия 6.0** — полная поддержка всех статей и разбивки аренды")

# ==================== КОНФИГУРАЦИЯ ====================
class Config:
    DATE_FORMATS = [
        "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d",
        "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d", "%d.%m.%y",
        "%d/%m/%y", "%y-%m-%d", "%d-%b-%y", "%d-%b-%Y",
        "%b %d, %Y", "%d %b %Y", "%Y%m%d"
    ]
    CSV_DELIMITERS = [';', ',', '\t', '|', ':', '~']
    ENCODINGS = ['utf-8', 'utf-8-sig', 'windows-1251', 'cp1251', 'iso-8859-1', 'latin-1', 'cp1252']
    CURRENCIES = {'EUR': 'EUR', 'CZK': 'CZK', 'HUF': 'HUF', 'AZN': 'AZN', 'AED': 'AED', 'RUB': 'RUB', 'USD': 'USD', 'GBP': 'GBP', 'PLN': 'PLN'}


# ==================== КЛАСС ДЛЯ ПАРСИНГА MKB BUDAPEST ====================
class MKBParser:
    """Специализированный парсер для выписок MKB Budapest"""
    
    @staticmethod
    def parse(file_content: bytes, file_name: str) -> Tuple[pd.DataFrame, bool]:
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
                return pd.DataFrame(), False
            
            # Ищем строку с заголовками (Serial number, Value date, Transaction type...)
            header_row = -1
            for idx in range(min(30, len(df_raw))):
                row = df_raw.iloc[idx]
                row_text = ' '.join([str(cell).lower() for cell in row if pd.notna(cell)])
                if 'serial number' in row_text and 'value date' in row_text:
                    header_row = idx
                    break
            
            if header_row == -1:
                return pd.DataFrame(), False
            
            # Извлекаем заголовки
            headers = []
            for cell in df_raw.iloc[header_row].values:
                if pd.isna(cell):
                    headers.append('')
                else:
                    headers.append(str(cell).strip())
            
            # Собираем данные
            data = []
            for idx in range(header_row + 1, len(df_raw)):
                row = df_raw.iloc[idx]
                if all(pd.isna(cell) or str(cell).strip() == '' for cell in row):
                    continue
                first_cell = str(row.iloc[0]).lower() if len(row) > 0 else ''
                if first_cell in ['start balance', 'final balance', 'debit turnover', 'credit turnover']:
                    continue
                data.append(list(row))
            
            if not data:
                return pd.DataFrame(), False
            
            max_cols = len(headers)
            for row in data:
                while len(row) < max_cols:
                    row.append('')
            
            df = pd.DataFrame(data, columns=headers[:len(data[0])])
            return df, True
            
        except Exception as e:
            return pd.DataFrame(), False
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass


# ==================== ФУНКЦИИ ПАРСИНГА ====================
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
            # Определяем кодировку
            with open(tmp_path, 'rb') as f:
                raw = f.read(10000)
            result = chardet.detect(raw)
            encoding = result['encoding'] if result['encoding'] else 'utf-8'
            
            # Определяем разделитель
            with open(tmp_path, 'r', encoding=encoding, errors='ignore') as f:
                sample = f.read(5000)
            
            delimiter = ','
            for delim in Config.CSV_DELIMITERS:
                if sample.count(delim) > 5:
                    delimiter = delim
                    break
            
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


def parse_amount(amount_str, is_debit_col=False, is_credit_col=False, description="") -> float:
    if pd.isna(amount_str):
        return 0.0
    
    amount_str = str(amount_str).strip()
    if amount_str in ['', 'nan', '-', 'None', 'null', 'NaN', 'N/A', 'n/a']:
        return 0.0
    
    original_str = amount_str
    
    if amount_str.startswith('-+'):
        amount_str = '-' + amount_str[2:]
    if amount_str.startswith('+-'):
        amount_str = '-' + amount_str[2:]
    
    if is_debit_col:
        amount_str = re.sub(r'[^0-9\.,\-]', '', amount_str)
        amount_str = amount_str.replace(',', '.')
        try:
            val = float(amount_str)
            return -abs(val)
        except:
            return 0
    
    if is_credit_col:
        amount_str = re.sub(r'[^0-9\.,]', '', amount_str)
        amount_str = amount_str.replace(',', '.')
        try:
            val = float(amount_str)
            return abs(val)
        except:
            return 0
    
    amount_str = re.sub(r'\s*[A-Z]{3}\s*$', '', amount_str)
    amount_str = re.sub(r'^\s*[A-Z]{3}\s*', '', amount_str)
    amount_str = amount_str.replace(' ', '').replace('\xa0', '')
    amount_str = amount_str.replace(',', '.')
    
    has_minus = amount_str.startswith('-')
    amount_str = amount_str.lstrip('-')
    amount_str = re.sub(r'[^\d.]', '', amount_str)
    
    if not amount_str:
        return 0.0
    
    desc_lower = description.lower() if description else ""
    if not has_minus:
        expense_keywords = [
            'fee', 'charge', 'комиссия', 'tax', 'налог', 'to ', 'transfer to',
            'списание', 'снятие', 'оплата', 'payment', 'платеж', 'withdrawal',
            'дебит', 'расход', 'стоимость', 'цена', 'cost', 'price', 'purchase'
        ]
        if any(kw in desc_lower for kw in expense_keywords):
            has_minus = True
    
    try:
        val = float(amount_str)
        return -abs(val) if has_minus else abs(val)
    except:
        numbers = re.findall(r'-?\d+[.,]\d+', original_str)
        if numbers:
            try:
                val = float(numbers[0].replace(',', '.'))
                return -abs(val) if has_minus else abs(val)
            except:
                pass
        return 0.0


# ==================== ОПРЕДЕЛЕНИЕ СТАТЕЙ (ПОЛНАЯ ВЕРСИЯ) ====================
class ArticleClassifier:
    def __init__(self):
        self.parent_articles = {
            '1.1.1': 'Поступления за аренду недвижимости и земельных участков',
            '1.1.2': 'Прочие поступления',
            '1.1.4': 'Поступления за оказание услуг',
            '1.2.1': 'Закупка до 1000 евро',
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
            '1.2.27': 'Расходы в ожидании возмещения ЗП по другим бизнесам',
            '1.2.28': 'Расходы, произведённые за другие компании группы (к возмещению)',
            '1.2.33': 'Непредвиденные расходы',
            '1.2.34': 'Вознаграждение инвестора',
            '1.2.37': 'Возврат гарантийных депозитов',
            '1.2.38': 'НДС в составе комиссий банка',
            '2.2.4': 'Прочее',
            '2.2.7': 'Расходы по приобретению недвижимости',
            '2.2.9': 'Перемещение расход отдельный бизнес',
            '3.1.1': 'Ввод средств',
            '3.1.3': 'Получение внутригруппового займа',
            '3.1.4': 'Возврат выданного внутригруппового займа'
        }
        
        self.expense_articles = {
            '1.2.17 РКО': [
                'комиссия', 'commission', 'fee', 'charge', 'maintenance', 'rko', 'subscription',
                'atm withdrawal', 'плата за обслуживание', 'service package', 'számlakivonat díja',
                'netbankár monthly fee', 'conversion fee', 'charge for', 'bank charge',
                'pasha bank charge', 'monthly fee', 'account maintenance', 'card fee',
                'banking fee', 'transaction fee', 'service charge', 'tariff', 'тариф',
                'revolut business fee', 'grow plan fee', 'expenses app charge',
                'foreign exchange transaction fee', 'fee for',
                'popl.', 'vedeni', 'balicek', 'vypis', 'postou', 'tuz', 'ok', 'odch',
                'prich', 'intc', 'pl', 'st', 'tp', 'bankovní poplatek', 'opłata bankowa'
            ],
            '1.2.15.1 Зарплата': [
                'зарплат', 'salary', 'darba alga', 'algas izmaksa', 'darba algas izmaksa',
                'wage', 'payroll', 'alga', 'зарплата', 'зарплату', 'algas', 'salary amount',
                'darba algas izmaksa par', 'mzda', 'płaca', 'maaş', 'wages'
            ],
            '1.2.15.2 Налоги на ФОТ': [
                'nodokļu nomaksa', 'vid', 'budžets', 'налог', 'valsts budžets',
                'nodokļu', 'darba devēja', 'nodoku nomaksa', 'state revenue service',
                'social tax', 'социальный налог', 'подоходный налог', 'income tax',
                'dsmf', 'государственные сборы', 'taxes', 'налоги', 'daň', 'podatek'
            ],
            '1.2.16.3 НДС': [
                'value added tax', 'vat', 'ндс', 'pvn', 'output tax', 'pvn nodoklis',
                'pvns', 'н.д.с.', 'добавленная стоимость', 'value added tax - output',
                'dph', 'iva', 'kdv', 'moms', 'btw', 'tva'
            ],
            '1.2.16.1 Налог на недвижимость': [
                'nekustamā īpašuma nodoklis', 'налог на недвижимость', 'pašvaldība',
                'property tax', 'real estate tax', 'имущественный налог',
                'rigas valstspilsētas pašvaldība', 'daň z nemovitosti'
            ],
            '1.2.10.5 Электричество': [
                'latvenergo', 'elektri', 'электричеств', 'electricity', 'power',
                'elektrība', 'электроэнергия', 'light', 'освещение', 'электричество',
                'elektřina', 'prąd', 'elektrik'
            ],
            '1.2.10.3 Вода': [
                'rigas udens', 'ūdens', 'вода', 'water', 'woda', 'víz',
                'водоснабжение', 'водопровод', 'rīgas ūdens', 'voda', 'su'
            ],
            '1.2.10.2 Газ': [
                'gāze', 'газ', 'gas', 'heating', 'отопление', 'тепло',
                'gáz', 'газовое', 'газоснабжение', 'plyn', 'gaz'
            ],
            '1.2.10.1 Мусор': [
                'atkritumi', 'мусор', 'eco baltia', 'clean r', 'waste', 'garbage',
                'вывоз мусора', 'утилизация', 'trash', 'rubbish', 'odpad', 'çöp'
            ],
            '1.2.10.6 Коммунальные УК дома': [
                'rigas namu pārvaldnieks', 'latvijas namsaimnieks', 'biedrība',
                'dzīvokļu īpašnieku', 'apartment owners', 'management fee',
                'управляющая компания', 'ук', 'house management', 'condominium',
                'vecruni', 'nia nami', 'mūsu nams', 'správa domu', 'yönetim ücreti'
            ],
            '1.2.9.1 Связь, интернет, TV': [
                'tele2', 'bite', 'tet', 'internet', 'связь', 'telenet', 'wifi', 'broadband',
                'телефон', 'phone', 'мобильная связь', 'mobile', 'телевидение', 'tv',
                'телеком', 'telecom', 'связь и интернет', 'bite latvija', 'telekomunikace'
            ],
            '1.2.9.3 IT сервисы': [
                'google one', 'lovable', 'openai', 'chatgpt', 'browsec', 'adobe',
                'albato', 'slack', 'it сервисы', 'software', 'subscription',
                'microsoft', 'office 365', 'cloud', 'хостинг', 'hosting', 'domain',
                'домен', 'сервер', 'server', 'vps', 'vpn', 'антивирус', 'antivirus',
                'asana', 'zapier', 'google *google', 'digitalocean', 'aws', 'azure',
                'github', 'gitlab', 'bitbucket', 'jira', 'confluence', 'trello'
            ],
            '1.2.3 Оплата рекламных систем (бюджет)': [
                'facebook', 'facbk', 'tiktok', 'ads', 'marketing', 'реклам', 'advertising',
                'instagram', 'google ads', 'fb ads', 'яндекс директ', 'yandex direct',
                'контекстная реклама', 'contextual advertising', 'promotion', 'продвижение',
                'propertyfinder', 'tiktok ads', 'linkedin ads', 'twitter ads', 'ad campaign'
            ],
            '1.2.2 Командировочные расходы': [
                'flydubai', 'taxi', 'flixbus', 'bolt', 'uber', 'flix', 'careem',
                'travel', 'transport', 'hotel', 'accommodation', 'авиабилеты',
                'билеты', 'tickets', 'проживание', 'питание', 'meal', 'food',
                'командировка', 'business trip', 'транспортные расходы', 'dubai taxi',
                'cars taxi', 'enoc', 'emarat', 'hotel', 'отель', 'restaurant', 'ресторан'
            ],
            '1.2.8.1 Обслуживание объектов (бытовые вопросы, без ремонта)': [
                'apmaksa par rēķinu', 'обслуживание', 'ремонт', 'lifti', 'taipans',
                'sidorans', 'komval', 'rīgas lifti', 'maintenance', 'repair',
                'уборка', 'cleaning', 'клининг', 'сантехник', 'электрик',
                'plumber', 'electrician', 'техническое обслуживание', 'atlas materials',
                'údržba', 'bakım', 'cleaning service', 'janitor'
            ],
            '1.2.8.2 Страхование': [
                'balta', 'страхование', 'insurance', 'insure', 'страховка',
                'страховой взнос', 'insurance premium', 'pojištění', 'sigorta'
            ],
            '1.2.12 Бухгалтер': [
                'lubova loseva', 'loseva', 'бухгалтер', 'accounting', 'bookkeeping',
                'бухгалтерские услуги', 'бухгалтерия', 'accountant', 'audit', 'аудит',
                'účetní', 'muhasebeci'
            ],
            '2.2.7 Расходы по приобретению недвижимости': [
                'pirkuma liguma', 'приобретение недвижимости', 'аванс покупной стоимости',
                'property purchase', 'real estate purchase', 'покупка недвижимости',
                'advance payment', 'авансовый платеж', 'rezervacni smlouva',
                'kupní smlouva', 'satın alma'
            ],
            '1.2.27 Расходы в ожидании возмещения ЗП по другим бизнесам': [
                'jl/nf', 'jl/zp', 'расходы в ожидании', 'other business',
                'временные расходы', 'temporary expenses', 'alexander plyatsevoy'
            ],
            '1.2.37 Возврат гарантийных депозитов': [
                'deposit return', 'возврат депозита', 'depozīta atgriešana',
                'гарантийный депозит', 'security deposit refund', 'vrácení zálohy',
                'depozito iade'
            ],
            '1.2.21.1 Аренда офиса': [
                'office rent', 'аренда офиса', 'icare odәnisi', 'rent payment',
                'аренда помещения', 'office space', 'kancelář', 'ofis kirası'
            ],
            '1.2.21.2 Административные офисные расходы': [
                'office', 'офис', 'stationery', 'канцелярия', 'post office', 'ceska posta',
                'почта', 'post', 'канцелярские товары', 'kancelářské potřeby'
            ],
            '1.2.24 Расходы по отдельному бизнесу': [
                'vzr div', 'nav', 'personal income', 'social security', 'social contribution',
                'giro payment', 'transaction fee part', 'nav corporate tax', 'nav tarsasagi ado'
            ],
            '1.2.28 Расходы, произведённые за другие компании группы (к возмещению)': [
                'относится к александру', 'за другие компании', 'revelton',
                'расходы за другие компании', 'other companies', 'pro jiné společnosti'
            ],
            '1.2.33 Непредвиденные расходы': [
                'kompensācija', 'непредвиденные', 'unexpected', 'compensation',
                'neočekávané výdaje', 'beklenmedik giderler'
            ],
            '1.2.34 Вознаграждение инвестора': [
                'вознаграждение инвестора', 'investor reward', 'bs property', 'bs rerum',
                'odměna investora', 'yatırımcı ödülü'
            ],
            '1.2.38 НДС в составе комиссий банка': [
                'value added tax', 'vat', 'ндс', 'tax on commission', 'bank commission vat',
                'dph z bankovních poplatků', 'banka komisyonu kdv'
            ],
            'Перевод между счетами': [
                'currency exchange', 'конвертация', 'internal payment',
                'transfer to own account', 'между своими счетами', 'own transfer',
                'внутренний перевод', 'межбанковский перевод', 'bank transfer',
                'перевод между счетами', 'перевод в кассу', 'перевод на счет',
                'ipp transfer', 'inter company transfer', 'same-day own account transfer',
                'převod mezi účty', 'hesap transferi'
            ]
        }
        
        self.income_articles = {
            '1.1.1.2 Поступления систем бронирования (Airbnb, Booking и пр.)': [
                'airbnb', 'booking.com', 'booking b.v.', 'booking', 'airbnb payments',
                'vrbo', 'homeaway', 'expedia', 'tripadvisor', 'agoda'
            ],
            '1.1.1.4 Получение гарантийного депозита': [
                'depozits', 'депозит', 'deposit', 'guarantee', 'security deposit',
                'гарантийный депозит', 'záloha', 'depozito'
            ],
            '1.1.1.5 Возмещения': [
                'atlıdzība', 'возмещение', 'compensation', 'refund', 'возврат',
                'компенсация', 'náhrada', 'tazminat'
            ],
            '1.1.4.1 Комиссия за продажу недвижимости': [
                'commission', 'agency commissions', 'incoming swift payment',
                'marketing and advertisement', 'consultancy fees', 'real estate commission',
                'agent commission', 'комиссия за продажу', 'inward remittance',
                'fund transfer', 'provision', 'komise', 'komisyon'
            ],
            '3.1.3 Получение внутригруппового займа': [
                'loan', 'займ', 'baltic solutions', 'payment acc loan agreement',
                'loan payment', 'loan repayment', 'получение займа', 'půjčka', 'kredi'
            ],
            '3.1.4 Возврат выданного внутригруппового займа': [
                'loan return', 'возврат займа', 'partial repayment', 'repayment',
                'partial repayment of the loan', 'возврат выданного займа',
                'splátka půjčky', 'kredi geri ödemesi'
            ],
            '3.1.1 Ввод средств': [
                'transfer to own account', 'между своими счетами', 'own transfer', 'ввод средств',
                'fx spot/fwd payment', 'конвертация валюты', 'vklad', 'yatırım'
            ],
            '1.1.2.3 Компенсация по коммунальным расходам': [
                'komunālie', 'utilities', 'компенсац', 'возмещени', 'utility',
                'communal', 'heating cost', 'water cost', 'коммунальные', 'компенсация',
                'возмещение коммунальных', 'kompenzace', 'tazminat'
            ],
            '1.1.2.4 Прочие мелкие поступления': [
                'кэшбэк', 'cashback', 'u rok do', 'interest', 'проценты', 'урок',
                'urok do', 'процент', 'interest payment', 'cash back', 'cash-back',
                'cashback bonus', 'cashback reward'
            ],
            '1.1.2.2 Возвраты от поставщиков': [
                'return on request', 'возврат', 'refund', 'reversal', 'vat reversal',
                'возврат от поставщика', 'supplier refund', 'vrácení od dodavatele'
            ],
            '1.1.1.1 Арендная плата (наличные)': [
                'наличные', 'cash', 'cash payment', 'hotovost', 'nakit'
            ],
            '1.1.1.3 Арендная плата (счёт)': [
                'арендн', 'rent', 'money added', 'ire', 'dzivoklis', 'from',
                'credit of sepa', 'topup', 'received', 'incoming payment',
                'partial repayment', 'payment acc loan agreement', 'sent from',
                'поступление', 'received from', 'rent payment', 'арендная плата',
                'плата за аренду', 'ire par', 'par dzivokli', 'nájemné', 'kira'
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
            return '1.2.8.1 Обслуживание объектов (бытовые вопросы, без ремонта)', '1.2.8 Обслуживание объектов'
        else:
            for article, keywords in self.income_articles.items():
                for keyword in keywords:
                    if keyword in desc_lower:
                        article_code = article.split(' ')[0]
                        parent_code = '.'.join(article_code.split('.')[:2])
                        parent_article = self.parent_articles.get(parent_code, "")
                        return article, parent_article
            return '1.1.1.3 Арендная плата (счёт)', '1.1.1 Поступления за аренду недвижимости и земельных участков'


# ==================== ОПРЕДЕЛЕНИЕ НАПРАВЛЕНИЙ (ПОЛНАЯ ВЕРСИЯ) ====================
class DirectionClassifier:
    def __init__(self):
        self.directions = {
            'Latvia': [
                ('AN14 Антониас 14 (дом + парковка)', ['antonijas', 'an14', 'antonias']),
                ('AC89 Чака 89 (дом + парковка)', ['caka', 'ac89', 'čaka', 'caka iela', 'chaka']),
                ('M81 - Matisa 81', ['matisa', 'm81', 'matīsa']),
                ('B117 Бривибас, 117', ['brīvības 117', 'b117', 'brivibas', 'brīvības']),
                ('B78 Бривибас, 78', ['brīvības 78', 'b78']),
                ('G77 Гертрудес, 77', ['gertrudes', 'g77', 'gertrūdes']),
                ('V22 К. Валдемара 22', ['valdemara', 'v22', 'valdemāra']),
                ('MU3 - Mucenieku 3 - 4', ['mucenieku', 'mu3']),
                ('DS1 Дзирнаву, 1', ['dzirnavu', 'ds1', 'dzirnavu iela']),
                ('C23 Цесу, 23', ['cesu', 'c23', 'cesu iela']),
                ('SK3-Skunju 3', ['skunu', 'sk3', 'skunju', 'skunu iela']),
                ('D4 Парковка-Deglava4', ['deglava', 'd4', 'deglava iela']),
                ('H5 Хоспиталю', ['hospitalu', 'h5', 'hospitalu iela']),
                ('BRN_Brunieku', ['bruninieku', 'brn', 'bruņinieku', 'bruninieku iela']),
                ('AC87 Гараж Чака', ['ac87', 'caka 87']),
                ('UK_Latvia', ['uk_latvia', 'латвия', 'latvia', 'riga', 'рига'])
            ],
            'Europe': [
                ('F6 Помещение в доме Будапешт', ['budapest', 'f6', 'yulia galvin', 'будапешт']),
                ('DZ1_Dzibik1', ['dzibik', 'dz1', 'bilych nadiia']),
                ('J91 Ялтская - Помещение маленькое', ['j91', 'ялтская', 'bastet']),
                ('TGM45 Масарика - Bagel Lounge', ['masaryka', 'tgm45', 'bagel lounge', 'restco', 'masaryk']),
                ('OT1_Otovice Участок Свалка', ['otovice', 'ot1', 'komplekt', 'sedlecky kaolin']),
                ('MOL - Офис Molly', ['twohills', 'molly', 'mol']),
                ('LT_Vilnus', ['sveciy', 'vilnus', 'vilnius', 'вильнюс']),
                ('TGM20-Masaryka20', ['garpiz', 'tgm20', 'masaryka20']),
                ('Pernik', ['pernik']),
                ('UK_EU', ['uk_eu', 'европа', 'europe', 'eu', 'чехия', 'czech', 'чехия'])
            ],
            'East-Восток': [
                ('BIS - Baku, Icheri Sheher 1,2', ['icheri', 'bis', 'baku', 'cordiality', 'баку']),
                ('UKA - UK_AZ-Аренда', ['uka', 'uk_az', 'азербайджан', 'azerbaijan', 'azn'])
            ],
            'Nomiqa': [
                ('BNQ_BAKU-Nomiqa', ['bnq', 'baku-nomiqa', 'bunda']),
                ('DNQ_Dubai-Nomiqa', ['dnq', 'dubai-nomiqa', 'nomiqa real estate', 'mashreq', 'dubai', 'дубай'])
            ],
            'Unelma': [
                ('UK_Unelma', ['unelma'])
            ],
            'Отдельный бизнес': [
                ('', ['jl/nf', 'jl/zp', 'отдельный бизнес', 'в ожидании возмещения',
                     'alexander plyatsevoy', 'временные расходы', 'temporary business'])
            ],
            'UK Estate': [
                ('', ['uk estate', 'общие расходы', 'general expenses', 'head office'])
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
        
        if any(x in file_lower for x in ['pasha', 'kapital', 'bunda', 'azn', 'azerbaijan', 'баку']):
            return 'East-Восток', 'UKA - UK_AZ-Аренда'
        if any(x in file_lower for x in ['mashreq', 'wio', 'aed', 'dubai', 'uae', 'оаэ']):
            return 'Nomiqa', 'DNQ_Dubai-Nomiqa'
        if any(x in file_lower for x in ['csob', 'unicredit', 'czk', 'чехия', 'czech', 'praha', 'prague', 'budapest', 'mkb']):
            return 'Europe', 'UK_EU'
        if any(x in file_lower for x in ['industra', 'revolut', 'paysera', 'латвия', 'latvia', 'riga', 'lv']):
            return 'Latvia', 'UK_Latvia'
        
        return 'UK Estate', ''


# ==================== РАЗБИВКА АРЕНДНЫХ ПЛАТЕЖЕЙ ====================
class RentalSplitter:
    def __init__(self):
        self.split_ratios = {
            'AC89 Чака 89 (дом + парковка)': (0.836, 0.164),
            'AN14 Антониас 14 (дом + парковка)': (0.80, 0.20),
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
            'inward remittance', 'fund transfer', 'conversion', 'exchange'
        ]
        
        for kw in exclude_keywords:
            if kw in desc_lower:
                return False
        
        rent_keywords = [
            'rent', 'аренд', 'caka', 'antonijas', 'matisa', 'valdemara',
            'for rent', 'dzivoklis', 'apartment', 'ire',
            'money added', 'topup', 'from', 'received', 'incoming',
            'brīvības', 'gertrudes', 'mucenieku', 'dzirnavu', 'cesu',
            'skunu', 'deglava', 'hospitalu', 'bruninieku', 'nájemné',
            'kira', 'rental', 'lease', 'лизинг'
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
    file_lower = file_name.lower()
    
    # Специальная обработка для MKB Budapest
    if 'budapest' in file_lower or 'mkb' in file_lower:
        df, is_mkb = MKBParser.parse(file_content, file_name)
        if is_mkb and not df.empty:
            pass
        else:
            df = read_file(file_content, file_name)
    else:
        df = read_file(file_content, file_name)
    
    if df.empty:
        st.warning(f"⚠️ Не удалось прочитать файл {file_name}")
        return []
    
    # Поиск заголовков
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
        
        if date_col is None and any(kw in col_lower for kw in ['date', 'дата', 'value date', 'booking date', 'datum']):
            date_col = col
        if amount_col is None and any(kw in col_lower for kw in ['amount', 'сумма', 'total amount', 'payment amount']):
            amount_col = col
        if debit_col is None and any(kw in col_lower for kw in ['debit', 'дебет', 'расход', 'withdrawal']):
            debit_col = col
        if credit_col is None and any(kw in col_lower for kw in ['credit', 'кредит', 'доход', 'deposit']):
            credit_col = col
        if desc_col is None and any(kw in col_lower for kw in ['description', 'описание', 'narrative', 'purpose', 'details', 'transaction details']):
            desc_col = col
        if payer_col is None and any(kw in col_lower for kw in ['payer', 'плательщик', 'получатель', 'beneficiary', 'recipient']):
            payer_col = col
    
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]
    
    if desc_col is None and len(df.columns) > 1:
        desc_col = df.columns[1]
    
    # Для MKB Budapest
    if 'budapest' in file_lower and amount_col is None and debit_col is None and credit_col is None:
        if len(df.columns) > 9:
            amount_col = df.columns[9]
    
    article_classifier = ArticleClassifier()
    direction_classifier = DirectionClassifier()
    rental_splitter = RentalSplitter()
    
    transactions = []
    
    for idx in range(len(df)):
        try:
            row = df.iloc[idx]
            
            # Пропускаем пустые строки
            if all(pd.isna(cell) or str(cell).strip() == '' for cell in row):
                continue
            
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
            
            if amount_col is not None and amount_col in row:
                amount_val = row[amount_col]
                if pd.notna(amount_val) and str(amount_val).strip():
                    amount = parse_amount(amount_val, description=description)
            
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
            if 'czk' in file_lower:
                currency = 'CZK'
            elif 'huf' in file_lower:
                currency = 'HUF'
            elif 'azn' in file_lower:
                currency = 'AZN'
            elif 'aed' in file_lower:
                currency = 'AED'
            elif 'rub' in file_lower:
                currency = 'RUB'
            
            account_name = file_name.replace('.csv', '').replace('.xlsx', '').replace('.xls', '').replace('.txt', '')
            
            direction, subdirection = direction_classifier.get_direction(file_name, description, payer)
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


# ==================== ДЕТЕКТОР ЗАГОЛОВКОВ ====================
class HeaderDetector:
    def __init__(self):
        self.header_patterns = {
            'date': ['date', 'дата', 'datum', 'dátum', 'transaction date', 'value date', 'booking date'],
            'amount': ['amount', 'сумма', 'összeg', 'betrag', 'дебет', 'кредит', 'debit(d)', 'credit(c)'],
            'debit': ['debit', 'дебет', 'расход', 'withdrawal', 'списание'],
            'credit': ['credit', 'кредит', 'доход', 'deposit', 'зачисление'],
            'description': ['description', 'описание', 'leírás', 'details', 'назначение платежа', 'narrative'],
            'balance': ['balance', 'остаток', 'egyenleg', 'saldo']
        }
    
    def find_header_row(self, df: pd.DataFrame, max_rows: int = 50) -> int:
        if df.empty:
            return -1
        
        rows = min(max_rows, len(df))
        best_score = 0
        best_row = -1
        
        for row_idx in range(rows):
            row = df.iloc[row_idx]
            score = self._calculate_score(row)
            if score > best_score:
                best_score = score
                best_row = row_idx
        
        return best_row if best_score >= 2 else -1
    
    def _calculate_score(self, row: pd.Series) -> int:
        score = 0
        found = set()
        
        for cell in row:
            if pd.isna(cell):
                continue
            cell_str = str(cell).lower().strip()
            
            for category, keywords in self.header_patterns.items():
                for kw in keywords:
                    if kw in cell_str:
                        if category not in found:
                            found.add(category)
                            score += 2
                        else:
                            score += 1
                        break
        
        for cell in row:
            if pd.isna(cell):
                continue
            cell_str = str(cell).strip()
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
        total = len(header)
        
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
        
        return numeric_count <= total * 0.4


# ==================== ИНТЕРФЕЙС ====================
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
