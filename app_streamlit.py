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

st.markdown('<div class="main-header"><h1>📊 Финансовый аналитик выписок</h1><p>Загрузите выписки — получите структурированные данные</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🧠 О программе")
    st.markdown("**Поддерживаемые форматы:** Excel (.xlsx, .xls), CSV")
    st.markdown("**Счет берется из имени файла**")
    st.markdown("---")
    st.markdown("**Версия 5.0** — исправлен парсинг Paysera")


# ==================== КЛАСС УМНОГО ДЕТЕКТОРА ЗАГОЛОВКОВ ====================
class HeaderDetector:
    def __init__(self):
        self.header_patterns = {
            'date': [
                'date', 'дата', 'datum', 'dátum', 'transaction date', 'value date', 'booking date',
                'дата транзакции', 'дата операции', 'posting date', 'Date started (UTC)', 'Дата',
                'Date completed (UTC)', 'Дата транзакции', 'Дата и время'
            ],
            'amount': [
                'amount', 'сумма', 'összeg', 'betrag', 'дебет', 'кредит', 'debit(d)', 'credit(c)',
                'сумма списания', 'сумма зачисления', 'доход', 'расход', 'orig amount', 'payment amount',
                'Total amount', 'Payment currency', 'Amount', 'Сумма', 'Сумма и валюта'
            ],
            'debit': ['debit', 'дебет', 'расход', 'withdrawal', 'списание', 'debet', 'Расход', 'Д'],
            'credit': ['credit', 'кредит', 'доход', 'deposit', 'зачисление', 'Доход', 'К'],
            'description': [
                'description', 'описание', 'leírás', 'beschreibung', 'details', 'детали',
                'transaction details', 'назначение платежа', 'примечание', 'narrative', 'information',
                'Transaction Details', 'Purpose of payment', 'particulars', 'beneficiary', 'Description',
                'Назначение платежа', 'Информация о транзакции', 'Транзакция', 'Описание'
            ],
            'balance': ['balance', 'остаток', 'egyenleg', 'saldo', 'closing balance', 'конечный остаток', 'Баланс']
        }

        self.file_patterns = {
            'industra': [r'industra', r'индустра'],
            'revolut': [r'revolut', r'револют'],
            'budapest': [r'budapest', r'будапешт'],
            'pasha': [r'pasha', r'паша', r'kapital', r'капитал', r'bunda'],
            'paysera': [r'paysera'],
            'tinkoff': [r'tinkoff'],
            'dzibik': [r'dzibik'],
            'koruna': [r'koruna'],
            'garpiz': [r'garpiz'],
            'twohills': [r'twohills'],
            'mashreq': [r'mashreq'],
            'wio': [r'wio'],
            'wise': [r'wise']
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
        for cell in row:
            if pd.isna(cell):
                continue
            cell_str = str(cell).lower().strip()
            for keywords in self.header_patterns.values():
                for kw in keywords:
                    if kw in cell_str:
                        score += 1
                        break

        for cell in row:
            if pd.isna(cell):
                continue
            cell_str = str(cell).strip()
            if re.match(r'\d{4}[-./]\d{1,2}[-./]\d{1,2}', cell_str):
                score -= 1
            if re.match(r'^-?\d+[.,]\d{2}$', cell_str.replace(' ', '')):
                score -= 1

        return max(0, score)

    def validate_header_row(self, df: pd.DataFrame, header_row: int) -> bool:
        if header_row < 0 or header_row >= len(df):
            return False

        header = df.iloc[header_row]
        numeric_count = 0
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

        return numeric_count <= len(header) * 0.3


# ==================== ФУНКЦИИ ПАРСИНГА ====================
def read_file(file_content, file_name):
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name

    try:
        if file_name.lower().endswith(('.xls', '.xlsx')):
            try:
                df = pd.read_excel(tmp_path, engine='openpyxl', header=None)
            except:
                df = pd.read_excel(tmp_path, header=None)
        else:
            with open(tmp_path, 'rb') as f:
                raw = f.read()
            result = chardet.detect(raw[:10000])
            encoding = result['encoding'] if result['encoding'] else 'utf-8'

            with open(tmp_path, 'r', encoding=encoding) as f:
                lines = f.readlines()

            data = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if ';' in line:
                    parts = line.split(';')
                elif ',' in line:
                    parts = line.split(',')
                else:
                    parts = [line]
                data.append(parts)

            max_cols = max(len(row) for row in data) if data else 0
            for row in data:
                while len(row) < max_cols:
                    row.append('')

            df = pd.DataFrame(data)
    except Exception as e:
        os.unlink(tmp_path)
        raise e
    os.unlink(tmp_path)
    return df

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

def parse_amount(amount_str, is_debit_col=False, is_credit_col=False, description=""):
    """Исправленное определение знака суммы с поддержкой формата Paysera"""
    if pd.isna(amount_str):
        return 0
    amount_str = str(amount_str).strip()
    if amount_str == '' or amount_str == 'nan' or amount_str == '-':
        return 0

    original_str = amount_str
    
    # Обработка формата Paysera: "-320.00,EUR" или "320.00,EUR"
    if ',' in amount_str and not '.' in amount_str:
        amount_str = amount_str.replace(',', '.')
    
    # Удаляем валюту из строки
    amount_str = re.sub(r',[A-Z]{3}$', '', amount_str)
    amount_str = re.sub(r'[A-Z]{3}$', '', amount_str)
    
    # Обработка формата "-+50.00" (Industra)
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

    amount_str = amount_str.replace(' ', '')
    
    # Определяем знак
    has_minus = amount_str.startswith('-')
    amount_str = amount_str.lstrip('-')
    
    # Убираем всё кроме цифр и точки
    amount_str = re.sub(r'[^\d.]', '', amount_str)
    if amount_str == '':
        return 0
    
    desc_lower = description.lower()
    
    # Контекстное определение знака
    if not has_minus:
        expense_keywords = ['fee', 'charge', 'комиссия', 'tax', 'налог', 'to ', 'transfer to', 'apmaksa', 'nodokļu']
        if any(kw in desc_lower for kw in expense_keywords):
            has_minus = True
    else:
        # Если есть минус в строке, но это доход (редко)
        income_keywords = ['from', 'received', 'incoming', 'credit', 'зачисление']
        if any(kw in desc_lower for kw in income_keywords):
            has_minus = False

    try:
        val = float(amount_str)
        return -abs(val) if has_minus else abs(val)
    except:
        return 0


# ==================== ОПРЕДЕЛЕНИЕ СУБНАПРАВЛЕНИЯ ====================
def get_direction_and_subdirection(file_name, description, payer=""):
    file_lower = file_name.lower()
    desc_lower = description.lower()
    payer_lower = payer.lower()

    # LATVIA
    if any(x in desc_lower for x in ['antonijas', 'an14']):
        return 'Latvia', 'AN14 Антониас 14 (дом + парковка)'
    if any(x in desc_lower for x in ['caka', 'ac89', 'čaka']):
        return 'Latvia', 'AC89 Чака 89 (дом + парковка)'
    if any(x in desc_lower for x in ['matisa', 'm81']):
        return 'Latvia', 'M81 - Matisa 81'
    if any(x in desc_lower for x in ['brīvības 117', 'b117']):
        return 'Latvia', 'B117 Бривибас, 117'
    if any(x in desc_lower for x in ['brīvības 78', 'b78']):
        return 'Latvia', 'B78 Бривибас, 78'
    if any(x in desc_lower for x in ['gertrudes', 'g77']):
        return 'Latvia', 'G77 Гертрудес, 77'
    if any(x in desc_lower for x in ['valdemara', 'v22']):
        return 'Latvia', 'V22 К. Валдемара 22'
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
    if any(x in desc_lower for x in ['ac87', 'caka 87']):
        return 'Latvia', 'AC87 Гараж Чака'

    # EUROPE
    if any(x in file_lower for x in ['budapest', 'f6']) or 'yulia galvin' in desc_lower:
        return 'Europe', 'F6 Помещение в доме Будапешт'
    if any(x in file_lower for x in ['dzibik', 'dz1']) or 'bilych nadiia' in desc_lower:
        return 'Europe', 'DZ1_Dzibik1'
    if 'bastet' in desc_lower or 'j91' in desc_lower:
        return 'Europe', 'J91 Ялтская - Помещение маленькое'
    if any(x in desc_lower for x in ['masaryka', 'tgm45', 'bagel lounge']):
        return 'Europe', 'TGM45 Масарика - Bagel Lounge'
    if any(x in desc_lower for x in ['otovice', 'komplekt', 'ot1']):
        return 'Europe', 'OT1_Otovice Участок Свалка'
    if any(x in file_lower for x in ['twohills', 'molly']) or 'mol' in desc_lower:
        return 'Europe', 'MOL - Офис Molly'
    if any(x in file_lower for x in ['sveciy', 'vilnus']):
        return 'Europe', 'LT_Vilnus'
    if 'garpiz' in file_lower or 'tgm20' in desc_lower:
        return 'Europe', 'TGM20-Masaryka20'

    # EAST
    if any(x in file_lower for x in ['pasha', 'kapital', 'bunda']):
        if any(x in desc_lower for x in ['nomiqa', 'bnq', 'dnq']):
            return 'Nomiqa', 'BNQ_BAKU-Nomiqa'
        if any(x in desc_lower for x in ['icheri', 'bis', 'baku']):
            return 'East-Восток', 'BIS - Baku, Icheri Sheher 1,2'
        return 'East-Восток', 'UKA - UK_AZ-Аренда'

    # NOMIQA
    if 'mashreq' in file_lower or 'wio' in file_lower or 'nomiqa' in desc_lower:
        if any(x in desc_lower for x in ['dubai', 'uae', 'dnq']):
            return 'Nomiqa', 'DNQ_Dubai-Nomiqa'
        return 'Nomiqa', 'BNQ_BAKU-Nomiqa'

    # UNELMA
    if 'unelma' in file_lower:
        return 'Unelma', 'UK_Unelma'

    # ОТДЕЛЬНЫЙ БИЗНЕС
    if any(x in desc_lower for x in ['jl/nf', 'jl/zp', 'отдельный бизнес', 'в ожидании возмещения']):
        return 'Отдельный бизнес', ''

    return 'UK Estate', ''


# ==================== ОПРЕДЕЛЕНИЕ СТАТЬИ ====================
def get_article(description, amount, file_name):
    desc_lower = description.lower()
    file_lower = file_name.lower()

    # ========== РАСХОДЫ ==========
    if amount < 0:
        # 1.2.17 РКО
        if any(kw in desc_lower for kw in [
            'комиссия', 'commission', 'fee', 'charge', 'maintenance', 'rko', 'subscription',
            'atm withdrawal', 'плата за обслуживание', 'service package', 'számlakivonat díja',
            'netbankár monthly fee', 'conversion fee', 'charge for', 'bank charge',
            'pasha bank charge', 'monthly fee', 'account maintenance', 'card fee',
            'banking fee', 'transaction fee', 'service charge', 'tariff', 'тариф'
        ]):
            return '1.2.17 РКО'

        # 1.2.15.1 Зарплата
        if any(kw in desc_lower for kw in [
            'зарплат', 'salary', 'darba alga', 'algas izmaksa', 'darba algas izmaksa',
            'wage', 'payroll', 'alga', 'зарплата', 'зарплату', 'algas', 'salary amount'
        ]):
            return '1.2.15.1 Зарплата'

        # 1.2.15.2 Налоги на ФОТ
        if any(kw in desc_lower for kw in [
            'nodokļu nomaksa', 'vid', 'budžets', 'налог', 'valsts budžets',
            'nodokļu', 'darba devēja', 'nodoku nomaksa', 'state revenue service',
            'social tax', 'социальный налог', 'подоходный налог', 'income tax'
        ]):
            return '1.2.15.2 Налоги на ФОТ'

        # 1.2.16.3 НДС
        if any(kw in desc_lower for kw in [
            'value added tax', 'vat', 'ндс', 'pvn', 'output tax', 'pvn nodoklis',
            'pvns', 'н.д.с.', 'добавленная стоимость'
        ]):
            return '1.2.16.3 НДС'

        # 1.2.16.1 Налог на недвижимость
        if any(kw in desc_lower for kw in [
            'nekustamā īpašuma nodoklis', 'налог на недвижимость', 'pašvaldība',
            'property tax', 'real estate tax', 'имущественный налог'
        ]):
            return '1.2.16.1 Налог на недвижимость'

        # 1.2.10.5 Электричество
        if any(kw in desc_lower for kw in [
            'latvenergo', 'elektri', 'электричеств', 'electricity', 'power',
            'elektrība', 'электроэнергия', 'light', 'освещение'
        ]):
            return '1.2.10.5 Электричество'

        # 1.2.10.3 Вода
        if any(kw in desc_lower for kw in [
            'rigas udens', 'ūdens', 'вода', 'water', 'woda', 'víz',
            'водоснабжение', 'водопровод'
        ]):
            return '1.2.10.3 Вода'

        # 1.2.10.2 Газ
        if any(kw in desc_lower for kw in [
            'gāze', 'газ', 'gas', 'heating', 'отопление', 'тепло',
            'gáz', 'газовое', 'газоснабжение'
        ]):
            return '1.2.10.2 Газ'

        # 1.2.10.1 Мусор
        if any(kw in desc_lower for kw in [
            'atkritumi', 'мусор', 'eco baltia', 'clean r', 'waste', 'garbage',
            'вывоз мусора', 'утилизация', 'trash', 'rubbish'
        ]):
            return '1.2.10.1 Мусор'

        # 1.2.10.6 Коммунальные УК дома
        if any(kw in desc_lower for kw in [
            'rigas namu pārvaldnieks', 'latvijas namsaimnieks', 'biedrība',
            'dzīvokļu īpašnieku', 'apartment owners', 'management fee',
            'управляющая компания', 'ук', 'house management', 'condominium'
        ]):
            return '1.2.10.6 Коммунальные УК дома'

        # 1.2.9.1 Связь, интернет, TV
        if any(kw in desc_lower for kw in [
            'tele2', 'bite', 'tet', 'internet', 'связь', 'telenet', 'wifi', 'broadband',
            'телефон', 'phone', 'мобильная связь', 'mobile', 'телевидение', 'tv'
        ]):
            return '1.2.9.1 Связь, интернет, TV'

        # 1.2.9.3 IT сервисы
        if any(kw in desc_lower for kw in [
            'google one', 'lovable', 'openai', 'chatgpt', 'browsec', 'adobe',
            'albato', 'slack', 'it сервисы', 'software', 'subscription'
        ]):
            return '1.2.9.3 IT сервисы'

        # 1.2.3 Оплата рекламных систем
        if any(kw in desc_lower for kw in [
            'facebook', 'facbk', 'tiktok', 'ads', 'marketing', 'реклам', 'advertising'
        ]):
            return '1.2.3 Оплата рекламных систем (бюджет)'

        # 1.2.2 Командировочные расходы
        if any(kw in desc_lower for kw in [
            'flydubai', 'taxi', 'flixbus', 'bolt', 'uber', 'flix', 'careem',
            'travel', 'transport', 'hotel', 'accommodation', 'авиабилеты'
        ]):
            return '1.2.2 Командировочные расходы'

        # 1.2.8.1 Обслуживание объектов
        if any(kw in desc_lower for kw in [
            'apmaksa par rēķinu', 'обслуживание', 'ремонт', 'lifti', 'taipans',
            'sidorans', 'komval', 'rīgas lifti', 'maintenance', 'repair'
        ]):
            return '1.2.8.1 Обслуживание объектов (бытовые вопросы, без ремонта)'

        # 1.2.8.2 Страхование
        if any(kw in desc_lower for kw in [
            'balta', 'страхование', 'insurance', 'insure', 'страховка'
        ]):
            return '1.2.8.2 Страхование'

        # 1.2.12 Бухгалтер
        if any(kw in desc_lower for kw in [
            'lubova loseva', 'loseva', 'бухгалтер', 'accounting', 'bookkeeping'
        ]):
            return '1.2.12 Бухгалтер'

        # 2.2.7 Расходы по приобретению недвижимости
        if any(kw in desc_lower for kw in [
            'pirkuma liguma', 'приобретение недвижимости', 'аванс покупной стоимости',
            'property purchase', 'real estate purchase', 'покупка недвижимости'
        ]):
            return '2.2.7 Расходы по приобретению недвижимости'

        # 1.2.27 Расходы в ожидании возмещения
        if any(kw in desc_lower for kw in [
            'jl/nf', 'jl/zp', 'расходы в ожидании', 'other business'
        ]):
            return '1.2.27 Расходы в ожидании возмещения ЗП по другим бизнесам'

        # 1.2.37 Возврат гарантийных депозитов
        if any(kw in desc_lower for kw in [
            'deposit return', 'возврат депозита', 'depozīta atgriešana'
        ]):
            return '1.2.37 Возврат гарантийных депозитов'

        # Перевод между счетами
        if any(kw in desc_lower for kw in [
            'currency exchange', 'конвертация', 'internal payment',
            'transfer to own account', 'между своими счетами', 'own transfer'
        ]):
            return 'Перевод между счетами'

        return '1.2.8.1 Обслуживание объектов (бытовые вопросы, без ремонта)'

    # ========== ДОХОДЫ ==========
    else:
        # 1.1.1.2 Поступления систем бронирования
        if any(kw in desc_lower for kw in ['airbnb', 'booking.com', 'booking b.v.']):
            return '1.1.1.2 Поступления систем бронирования (Airbnb, Booking и пр.)'

        # 1.1.1.4 Получение гарантийного депозита
        if any(kw in desc_lower for kw in ['depozits', 'депозит', 'deposit', 'guarantee']):
            return '1.1.1.4 Получение гарантийного депозита'

        # 1.1.1.5 Возмещения
        if any(kw in desc_lower for kw in ['atlıdzība', 'возмещение', 'compensation']):
            return '1.1.1.5 Возмещения'

        # 1.1.4.1 Комиссия за продажу недвижимости
        if any(kw in desc_lower for kw in [
            'commission', 'agency commissions', 'incoming swift payment',
            'marketing and advertisement', 'consultancy fees', 'real estate commission'
        ]):
            return '1.1.4.1 Комиссия за продажу недвижимости'

        # 3.1.3 Получение внутригруппового займа
        if any(kw in desc_lower for kw in [
            'loan', 'займ', 'baltic solutions', 'payment acc loan agreement',
            'loan payment', 'loan repayment'
        ]):
            return '3.1.3 Получение внутригруппового займа'

        # 3.1.4 Возврат выданного внутригруппового займа
        if any(kw in desc_lower for kw in [
            'loan return', 'возврат займа', 'partial repayment', 'repayment'
        ]):
            return '3.1.4 Возврат выданного внутригруппового займа'

        # 3.1.1 Ввод средств
        if any(kw in desc_lower for kw in [
            'transfer to own account', 'между своими счетами', 'own transfer', 'ввод средств'
        ]):
            return '3.1.1 Ввод средств'

        # 1.1.2.3 Компенсация по коммунальным расходам
        if any(kw in desc_lower for kw in [
            'komunālie', 'utilities', 'компенсац', 'возмещени', 'utility',
            'communal', 'heating cost', 'water cost'
        ]):
            return '1.1.2.3 Компенсация по коммунальным расходам'

        # 1.1.2.4 Прочие мелкие поступления
        if any(kw in desc_lower for kw in [
            'кэшбэк', 'cashback', 'u rok do', 'interest', 'проценты'
        ]):
            return '1.1.2.4 Прочие мелкие поступления'

        # 1.1.2.2 Возвраты от поставщиков
        if any(kw in desc_lower for kw in [
            'return on request', 'возврат', 'refund', 'reversal', 'vat reversal'
        ]):
            return '1.1.2.2 Возвраты от поставщиков'

        # 1.1.1.1 Арендная плата (наличные)
        if any(kw in desc_lower for kw in ['наличные', 'cash']):
            return '1.1.1.1 Арендная плата (наличные)'

        # 1.1.1.3 Арендная плата (счёт)
        if any(kw in desc_lower for kw in [
            'арендн', 'rent', 'money added', 'ire', 'dzivoklis', 'from',
            'credit of sepa', 'topup', 'received', 'incoming payment'
        ]):
            return '1.1.1.3 Арендная плата (счёт)'

        return '1.1.1.3 Арендная плата (счёт)'


# ==================== РАЗБИВКА АРЕНДНЫХ ПЛАТЕЖЕЙ ====================
def should_split_rental_payment(description, amount, file_name):
    """Определяет, нужно ли разбивать платёж на аренду и компенсацию КУ"""
    if amount <= 0:
        return False
    
    desc_lower = description.lower()
    file_lower = file_name.lower()

    # Только для Paysera, Revolut, Industra (арендные платежи от физических лиц)
    if not any(x in file_lower for x in ['paysera', 'revolut', 'industra']):
        return False

    # Исключаем явно не арендные платежи
    exclude_keywords = [
        'booking.com', 'airbnb', 'loan', 'deposit', 'депозит', 
        'commission', 'комиссия', 'fee', 'charge', 'tax', 'налог',
        'salary', 'зарплата', 'refund', 'возврат', 'interest', 'проценты',
        'valsts budžets', 'budžets', 'vid', 'rigas valstpilsētas pašvaldība',
        'latvenergo', 'rigas udens', 'eco baltia', 'bite', 'tele2', 'tet',
        'rīgas lifti', 'taipans', 'sidorans', 'komval', 'apmaksa par',
        'inward remittance', 'fund transfer', 'swift payment'
    ]
    for kw in exclude_keywords:
        if kw in desc_lower:
            return False

    # Ключевые слова для арендных платежей от физических лиц
    rent_keywords = [
        'rent', 'аренд', 'caka', 'antonijas', 'matisa', 'valdemara', 
        'for rent', 'dzivoklis', 'apartment', 'flat', 'ire',
        'money added', 'topup', 'from', 'received', 'incoming',
        'brīvības', 'gertrudes', 'mucenieku', 'dzirnavu', 'cesu',
        'skunu', 'deglava', 'hospitalu', 'bruninieku'
    ]
    
    has_rent_keyword = any(kw in desc_lower for kw in rent_keywords)
    
    # Также проверяем наличие кодов объектов
    object_codes = ['ac89', 'an14', 'm81', 'b117', 'v22', 'g77', 'mu3', 
                   'ds1', 'c23', 'sk3', 'd4', 'h5', 'brn', 'ac87']
    has_object_code = any(code in desc_lower for code in object_codes)
    
    return has_rent_keyword or has_object_code

def calculate_split(amount, file_name, description):
    """Рассчитывает разбивку на аренду и компенсацию КУ"""
    desc_lower = description.lower()
    
    # Правила из Финтабло
    if any(x in desc_lower for x in ['caka', 'ac89', 'čaka']):
        return round(amount * 0.836, 2), round(amount * 0.164, 2)
    
    if any(x in desc_lower for x in ['antonijas', 'an14']):
        return round(amount * 0.8, 2), round(amount * 0.2, 2)
    
    if any(x in desc_lower for x in ['matisa', 'm81']):
        return round(amount * 0.7, 2), round(amount * 0.3, 2)
    
    if any(x in desc_lower for x in ['brīvības 117', 'b117']):
        return round(amount * 0.85, 2), round(amount * 0.15, 2)
    
    if any(x in desc_lower for x in ['valdemara', 'v22']):
        return round(amount * 0.55, 2), round(amount * 0.45, 2)
    
    if any(x in desc_lower for x in ['gertrudes', 'g77']):
        return round(amount * 0.85, 2), round(amount * 0.15, 2)
    
    return round(amount * 0.85, 2), round(amount * 0.15, 2)


# ==================== ОСНОВНАЯ ФУНКЦИЯ ПАРСИНГА ====================
def parse_file(file_content, file_name):
    df = read_file(file_content, file_name)
    if df is None or df.empty:
        st.error("❌ Не удалось прочитать файл")
        return []
    
    file_lower = file_name.lower()
    detector = HeaderDetector()
    
    # Специальная обработка для файлов Paysera (многострочные заголовки)
    if 'paysera' in file_lower:
        # Ищем строку с заголовками
        header_row = -1
        for idx in range(min(30, len(df))):
            row_text = ' '.join([str(cell).lower() for cell in df.iloc[idx] if pd.notna(cell)])
            if 'тип' in row_text and 'дата и время' in row_text:
                header_row = idx
                break
        
        if header_row >= 0:
            # Извлекаем заголовки
            headers = []
            for cell in df.iloc[header_row]:
                if pd.isna(cell):
                    headers.append('')
                else:
                    headers.append(str(cell).strip())
            
            # Собираем данные
            data_rows = []
            for idx in range(header_row + 1, len(df)):
                row = list(df.iloc[idx].values)
                if all(pd.isna(cell) or str(cell).strip() == '' for cell in row):
                    continue
                if len(row) < len(headers):
                    row.extend([''] * (len(headers) - len(row)))
                data_rows.append(row[:len(headers)])
            
            if data_rows:
                df = pd.DataFrame(data_rows, columns=headers)
    
    # Если не нашли заголовки Paysera, пробуем стандартный детектор
    if df.empty or ('paysera' not in file_lower):
        header_row = detector.find_header_row(df)
        if header_row >= 0 and detector.validate_header_row(df, header_row):
            headers = [str(h).strip() if pd.notna(h) else f'col_{i}' for i, h in enumerate(df.iloc[header_row].values)]
            seen = {}
            unique_headers = []
            for h in headers:
                if h in seen:
                    seen[h] += 1
                    unique_headers.append(f"{h}_{seen[h]}")
                else:
                    seen[h] = 0
                    unique_headers.append(h)
            
            data_rows = []
            for idx in range(header_row + 1, len(df)):
                row = list(df.iloc[idx].values)
                if len(row) < len(unique_headers):
                    row.extend([''] * (len(unique_headers) - len(row)))
                data_rows.append(row[:len(unique_headers)])
            
            df = pd.DataFrame(data_rows, columns=unique_headers)
    
    if df.empty:
        st.warning("⚠️ В файле не найдено данных для обработки")
        return []
    
    # Определение колонок
    date_col = None
    amount_col = None
    debit_col = None
    credit_col = None
    desc_col = None
    type_col = None
    payer_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        if date_col is None and any(kw in col_lower for kw in ['date', 'дата', 'datum', 'booking', 'posting', 'value', 'started', 'value date', 'дата и время']):
            date_col = col
        if amount_col is None and any(kw in col_lower for kw in ['amount', 'сумма', 'total amount', 'сумма и валюта']):
            amount_col = col
        if debit_col is None and any(kw in col_lower for kw in ['debit', 'дебет', 'расход', 'withdrawal', 'debet', 'д']):
            debit_col = col
        if credit_col is None and any(kw in col_lower for kw in ['credit', 'кредит', 'доход', 'deposit', 'к']):
            credit_col = col
        if desc_col is None and any(kw in col_lower for kw in ['description', 'описание', 'details', 'назначение', 'narrative', 'information', 'info', 'назначение платежа']):
            desc_col = col
        if type_col is None and any(kw in col_lower for kw in ['type', 'тип', 'transaction type']):
            type_col = col
        if payer_col is None and any(kw in col_lower for kw in ['payer', 'плательщик', 'получатель', 'beneficiary', 'recipient']):
            payer_col = col
    
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]
    
    transactions = []
    
    for idx in range(len(df)):
        try:
            row = df.iloc[idx]
            
            # Пропускаем пустые строки
            if all(pd.isna(cell) or str(cell).strip() == '' for cell in row):
                continue
            
            # Описание
            description = ''
            if desc_col in row:
                desc_val = row[desc_col]
                if pd.notna(desc_val):
                    description = str(desc_val)
            
            # Тип операции
            if type_col in row:
                type_val = row[type_col]
                if pd.notna(type_val) and str(type_val).strip():
                    description = f"{str(type_val)} {description}"
            
            # Плательщик/получатель
            payer = ''
            if payer_col in row:
                payer_val = row[payer_col]
                if pd.notna(payer_val) and str(payer_val).strip():
                    payer = str(payer_val)
                    description = f"{description} {payer}"
            
            # Добавляем другие колонки
            for col in df.columns:
                if col not in [date_col, amount_col, debit_col, credit_col, desc_col, type_col, payer_col]:
                    val = row[col]
                    if pd.notna(val) and str(val).strip() and str(val) != 'nan':
                        description += ' ' + str(val)
            
            description = description.strip()
            
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
                if pd.notna(amount_val) and str(amount_val).strip():
                    amount = parse_amount(amount_val, description=description)
            
            # Пробуем debit/credit
            if amount == 0 and debit_col in row and credit_col in row:
                debit_val = row[debit_col] if debit_col in row else None
                credit_val = row[credit_col] if credit_col in row else None
                
                if pd.notna(debit_val) and str(debit_val).strip():
                    amount = parse_amount(debit_val, is_debit_col=True, description=description)
                elif pd.notna(credit_val) and str(credit_val).strip():
                    amount = parse_amount(credit_val, is_credit_col=True, description=description)
            
            if amount == 0:
                continue
            
            # Валюта
            currency = 'EUR'
            if any(x in file_lower for x in ['czk', 'czech']) or 'CZK' in description:
                currency = 'CZK'
            elif 'HUF' in file_lower:
                currency = 'HUF'
            elif 'RUB' in file_lower:
                currency = 'RUB'
            elif any(x in file_lower for x in ['aed', 'dirham']):
                currency = 'AED'
            elif any(x in file_lower for x in ['azn', 'manat']):
                currency = 'AZN'
            
            account_name = file_name.replace('.csv', '').replace('.xlsx', '').replace('.xls', '')
            
            # Разбивка арендных платежей
            if should_split_rental_payment(description, amount, file_name):
                rent_share, utility_share = calculate_split(amount, file_name, description)
                
                if rent_share > 0:
                    article = get_article(description, rent_share, file_name)
                    direction, subdirection = get_direction_and_subdirection(file_name, description, payer)
                    transactions.append({
                        'date': date,
                        'amount': rent_share,
                        'currency': currency,
                        'account_name': account_name,
                        'description': f"{description[:400]} (аренда)",
                        'article_name': article,
                        'direction': direction,
                        'subdirection': subdirection
                    })
                
                if utility_share > 0:
                    direction, subdirection = get_direction_and_subdirection(file_name, description, payer)
                    transactions.append({
                        'date': date,
                        'amount': utility_share,
                        'currency': currency,
                        'account_name': account_name,
                        'description': f"{description[:400]} (компенсация КУ)",
                        'article_name': '1.1.2.3 Компенсация по коммунальным расходам',
                        'direction': direction,
                        'subdirection': subdirection
                    })
            else:
                article = get_article(description, amount, file_name)
                direction, subdirection = get_direction_and_subdirection(file_name, description, payer)
                
                transactions.append({
                    'date': date,
                    'amount': amount,
                    'currency': currency,
                    'account_name': account_name,
                    'description': description[:500],
                    'article_name': article,
                    'direction': direction,
                    'subdirection': subdirection
                })
                
        except Exception as e:
            continue
    
    return transactions


# ==================== ИНТЕРФЕЙС ====================
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
                    df = pd.DataFrame([{
                        'Дата': t['date'],
                        'Сумма': t['amount'],
                        'Валюта': t['currency'],
                        'Счет': t['account_name'],
                        'Статья': t['article_name'],
                        'Направление': t['direction'],
                        'Субнаправление': t['subdirection'],
                        'Описание': t['description'][:100]
                    } for t in transactions])
                    st.markdown("---")
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("📊 Всего операций", len(transactions))
                    with col_b:
                        доход = df[df['Сумма'] > 0]['Сумма'].sum()
                        st.metric("📈 Доходы", f"{доход:,.2f}")
                    with col_c:
                        расход = abs(df[df['Сумма'] < 0]['Сумма'].sum())
                        st.metric("📉 Расходы", f"{расход:,.2f}")
                    st.dataframe(df, use_container_width=True)
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Транзакции')
                    output.seek(0)
                    st.download_button("📥 Скачать Excel", data=output, file_name=f"анализ_{uploaded_file.name}.xlsx")
                else:
                    st.warning("⚠️ Не найдено транзакций")

with tab2:
    st.markdown("### Загрузите несколько файлов")
    uploaded_files = st.file_uploader("Выберите файлы", type=['csv', 'xlsx', 'xls'], accept_multiple_files=True, key="multiple")
    if uploaded_files:
        st.info(f"📄 Выбрано файлов: {len(uploaded_files)}")
        if st.button("🚀 Запустить анализ всех", key="multi_btn"):
            all_transactions = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            for i, f in enumerate(uploaded_files):
                status_text.text(f"🔄 Обработка: {f.name}")
                content = f.read()
                trans = parse_file(content, f.name)
                for t in trans:
                    t['source_file'] = f.name
                    all_transactions.append(t)
                progress_bar.progress((i + 1) / len(uploaded_files))
            status_text.text("✅ Обработка завершена!")
            if all_transactions:
                df = pd.DataFrame([{
                    'Дата': t['date'],
                    'Сумма': t['amount'],
                    'Валюта': t['currency'],
                    'Счет': t['account_name'],
                    'Исходный файл': t.get('source_file', ''),
                    'Статья': t['article_name'],
                    'Направление': t['direction'],
                    'Субнаправление': t['subdirection'],
                    'Описание': t['description'][:100]
                } for t in all_transactions])
                st.markdown("---")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("📊 Всего операций", len(all_transactions))
                with col_b:
                    доход = df[df['Сумма'] > 0]['Сумма'].sum()
                    st.metric("📈 Доходы", f"{доход:,.2f}")
                with col_c:
                    расход = abs(df[df['Сумма'] < 0]['Сумма'].sum())
                    st.metric("📉 Расходы", f"{расход:,.2f}")
                st.dataframe(df, use_container_width=True)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Все транзакции')
                output.seek(0)
                st.download_button("📥 Скачать сводный Excel", data=output, file_name="сводка.xlsx")
