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
    st.markdown("**Версия 3.0** — исправлены знаки сумм, разбивка аренды и маппинг статей")

# ==================== КЛАСС УМНОГО ДЕТЕКТОРА ЗАГОЛОВКОВ ====================
class HeaderDetector:
    def __init__(self):
        self.header_patterns = {
            'date': [
                'date', 'дата', 'datum', 'dátum', 'transaction date', 'value date', 'booking date',
                'дата транзакции', 'дата операции', 'posting date', 'Date started (UTC)', 'Дата'
            ],
            'amount': [
                'amount', 'сумма', 'összeg', 'betrag', 'дебет', 'кредит', 'debit(d)', 'credit(c)',
                'сумма списания', 'сумма зачисления', 'доход', 'расход', 'orig amount', 'payment amount',
                'Total amount', 'Payment currency'
            ],
            'debit': ['debit', 'дебет', 'расход', 'withdrawal', 'списание', 'debet'],
            'credit': ['credit', 'кредит', 'доход', 'deposit', 'зачисление'],
            'description': [
                'description', 'описание', 'leírás', 'beschreibung', 'details', 'детали',
                'transaction details', 'назначение платежа', 'примечание', 'narrative', 'information',
                'Transaction Details', 'Purpose of payment', 'particulars', 'beneficiary'
            ],
            'balance': ['balance', 'остаток', 'egyenleg', 'saldo', 'closing balance', 'конечный остаток']
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
            'mashreq': [r'mashreq']
        }

    def detect_file_type(self, filename: str) -> str:
        filename_lower = filename.lower()
        for file_type, patterns in self.file_patterns.items():
            for pattern in patterns:
                if re.search(pattern, filename_lower, re.IGNORECASE):
                    return file_type
        return "unknown"

    def find_header_row(self, df: pd.DataFrame, max_rows_to_check: int = 30) -> int:
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
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]

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
    """Исправленное определение знака суммы с учетом формата Industra"""
    if pd.isna(amount_str):
        return 0
    amount_str = str(amount_str).strip()
    if amount_str == '' or amount_str == 'nan':
        return 0

    # Сохраняем оригинальную строку для анализа формата
    original_str = amount_str
    
    # Обработка странного формата Industra типа "-+50.00" - это минус 50
    if amount_str.startswith('-+'):
        amount_str = '-' + amount_str[2:]
    
    # Также обрабатываем формат "+-50.00" как минус 50
    if amount_str.startswith('+-'):
        amount_str = '-' + amount_str[2:]

    # Если это колонка дебета (расхода) — сумма всегда отрицательная
    if is_debit_col:
        amount_str = re.sub(r'[^0-9\.,\-]', '', amount_str)
        amount_str = amount_str.replace(',', '.')
        try:
            val = float(amount_str)
            return -abs(val)
        except:
            return 0

    # Если это колонка кредита (дохода) — сумма всегда положительная
    if is_credit_col:
        amount_str = re.sub(r'[^0-9\.,]', '', amount_str)
        amount_str = amount_str.replace(',', '.')
        try:
            val = float(amount_str)
            return abs(val)
        except:
            return 0

    # Общая колонка суммы — определяем знак
    # Убираем валюту и пробелы
    amount_str = re.sub(r'[A-Z]{3}$', '', amount_str.strip())
    amount_str = amount_str.replace(',', '.').replace(' ', '')
    
    # Определяем знак по наличию минуса
    has_minus = amount_str.startswith('-')
    
    # Для Industra: если в описании есть commission/fee и нет минуса, но есть плюс - это расход
    desc_lower = description.lower()
    if ('industra' in desc_lower or 'индустра' in desc_lower) and ('commission' in desc_lower or 'fee' in desc_lower or 'комиссия' in desc_lower):
        if not has_minus and '+' in original_str:
            has_minus = True
    
    # Убираем все нецифровые символы кроме точки и минуса
    amount_str = re.sub(r'[^0-9\.\-]', '', amount_str)
    if amount_str == '' or amount_str == '-':
        return 0

    try:
        val = float(amount_str)
        if has_minus:
            return -abs(val)
        else:
            return abs(val)
    except:
        return 0

def should_split_rental_payment(description, amount, file_name):
    """Определяет, нужно ли разбивать платёж на аренду и компенсацию КУ"""
    desc_lower = description.lower()
    file_lower = file_name.lower()

    # Только положительные суммы (доходы от аренды)
    if amount <= 0:
        return False

    # Для всех банков, где могут быть арендные платежи
    if not any(x in file_lower for x in ['paysera', 'revolut', 'industra', 'tinkoff']):
        return False

    # Исключаем явно не арендные платежи
    exclude_keywords = [
        'booking.com', 'airbnb', 'loan', 'deposit', 'депозит', 
        'commission', 'комиссия', 'fee', 'charge', 'tax', 'налог',
        'salary', 'зарплата', 'refund', 'возврат', 'interest', 'проценты'
    ]
    for kw in exclude_keywords:
        if kw in desc_lower:
            return False

    # Ключевые слова для арендных платежей
    rent_keywords = [
        'rent', 'аренд', 'caka', 'antonijas', 'matisa', 'valdemara', 
        'for rent', 'utilities', 'dzivoklis', 'apartment', 'flat',
        'money added', 'topup', 'from', 'received', 'incoming',
        'brīvības', 'gertrudes', 'mucenieku', 'dzirnavu', 'cesu',
        'skunu', 'deglava', 'hospitalu', 'bruninieku'
    ]
    
    # Проверяем наличие ключевых слов
    has_rent_keyword = any(kw in desc_lower for kw in rent_keywords)
    
    # Также проверяем наличие кодов объектов
    object_codes = ['ac89', 'an14', 'm81', 'b117', 'v22', 'g77', 'mu3', 
                   'ds1', 'c23', 'sk3', 'd4', 'h5', 'brn', 'ac87']
    has_object_code = any(code in desc_lower for code in object_codes)
    
    return has_rent_keyword or has_object_code

def calculate_split(amount, file_name, description):
    """Рассчитывает разбивку на аренду и компенсацию КУ на основе правил из эталона"""
    desc_lower = description.lower()
    
    # Правила из эталонного файла Январь_2026.xlsx
    # Для AC89 Чака 89: типичное соотношение 85% аренда, 15% КУ
    if 'caka' in desc_lower or 'ac89' in desc_lower or 'čaka' in desc_lower:
        # Пример из эталона: 334.75 EUR = 280 EUR (аренда) + 54.75 EUR (КУ)
        # Это примерно 83.6% аренда, 16.4% КУ
        return round(amount * 0.836, 2), round(amount * 0.164, 2)
    
    # Для AN14 Антониас 14
    if 'antonijas' in desc_lower or 'an14' in desc_lower:
        # Пример: 400 EUR = 320 EUR (аренда) + 80 EUR (КУ) = 80%/20%
        return round(amount * 0.8, 2), round(amount * 0.2, 2)
    
    # Для M81 Matisa
    if 'matisa' in desc_lower or 'm81' in desc_lower:
        # Пример: 300 EUR = 210 EUR (аренда) + 90 EUR (КУ) = 70%/30%
        return round(amount * 0.7, 2), round(amount * 0.3, 2)
    
    # Для B117 Бривибас 117
    if 'brīvības 117' in desc_lower or 'b117' in desc_lower:
        return round(amount * 0.85, 2), round(amount * 0.15, 2)
    
    # Для V22 Валдемара
    if 'valdemara' in desc_lower or 'v22' in desc_lower:
        return round(amount * 0.8, 2), round(amount * 0.2, 2)
    
    # По умолчанию: 85% аренда, 15% КУ (наиболее частое соотношение)
    return round(amount * 0.85, 2), round(amount * 0.15, 2)

def get_direction_and_subdirection(file_name, description):
    """Определяет направление и субнаправление (исправлено для Pasha Bank и других)"""
    file_lower = file_name.lower()
    desc_lower = description.lower()

    # ==================== LATVIA ====================
    if 'antonijas' in desc_lower or 'an14' in desc_lower:
        return 'Latvia', 'AN14 Антониас 14 (дом + парковка)'
    if 'caka' in desc_lower or 'ac89' in desc_lower or 'čaka' in desc_lower:
        return 'Latvia', 'AC89 Чака 89 (дом + парковка)'
    if 'matisa' in desc_lower or 'm81' in desc_lower:
        return 'Latvia', 'M81 - Matisa 81'
    if 'brīvības 117' in desc_lower or 'b117' in desc_lower:
        return 'Latvia', 'B117 Бривибас, 117'
    if 'brīvības 78' in desc_lower or 'b78' in desc_lower:
        return 'Latvia', 'B78 Бривибас, 78'
    if 'gertrudes' in desc_lower or 'g77' in desc_lower:
        return 'Latvia', 'G77 Гертрудес, 77'
    if 'valdemara' in desc_lower or 'v22' in desc_lower:
        return 'Latvia', 'V22 К. Валдемара 22'
    if 'mucenieku' in desc_lower or 'mu3' in desc_lower:
        return 'Latvia', 'MU3 - Mucenieku 3 - 4'
    if 'dzirnavu' in desc_lower or 'ds1' in desc_lower:
        return 'Latvia', 'DS1 Дзирнаву, 1'
    if 'cesu' in desc_lower or 'c23' in desc_lower:
        return 'Latvia', 'C23 Цесу, 23'
    if 'skunu' in desc_lower or 'sk3' in desc_lower:
        return 'Latvia', 'SK3-Skunju 3'
    if 'deglava' in desc_lower or 'd4' in desc_lower:
        return 'Latvia', 'D4 Парковка-Deglava4'
    if 'hospitalu' in desc_lower or 'h5' in desc_lower:
        return 'Latvia', 'H5 Хоспиталю'
    if 'bruninieku' in desc_lower or 'brn' in desc_lower:
        return 'Latvia', 'BRN_Brunieku'
    if 'ac87' in desc_lower or 'caka 87' in desc_lower:
        return 'Latvia', 'AC87 Гараж Чака'

    # ==================== EUROPE ====================
    if 'budapest' in file_lower or 'yulia galvin' in desc_lower or 'f6' in desc_lower:
        return 'Europe', 'F6 Помещение в доме Будапешт'
    if 'dzibik' in file_lower or 'bilych nadiia' in desc_lower or 'dz1' in desc_lower:
        return 'Europe', 'DZ1_Dzibik1'
    if 'bastet' in desc_lower or 'j91' in desc_lower:
        return 'Europe', 'J91 Ялтская - Помещение маленькое'
    if 'masaryka' in desc_lower or 'tgm45' in desc_lower or 'bagel lounge' in desc_lower:
        return 'Europe', 'TGM45 Масарика - Bagel Lounge'
    if 'otovice' in desc_lower or 'komplekt' in desc_lower or 'ot1' in desc_lower:
        return 'Europe', 'OT1_Otovice Участок Свалка'
    if 'twohills' in file_lower or 'molly' in desc_lower or 'mol' in desc_lower:
        return 'Europe', 'MOL - Офис Molly'
    if 'sveciy' in file_lower or 'vilnus' in desc_lower or 'lt' in desc_lower:
        return 'Europe', 'LT_Vilnus'
    if 'garpiz' in file_lower or 'tgm20' in desc_lower:
        return 'Europe', 'TGM20-Masaryka20'

    # ==================== EAST ====================
    if 'pasha' in file_lower or 'kapital' in file_lower or 'bunda' in file_lower:
        # Разделяем Pasha Bank: Nomiqa и East-Восток
        if 'nomiqa' in desc_lower or 'bnq' in desc_lower or 'dnq' in desc_lower:
            return 'Nomiqa', 'BNQ_BAKU-Nomiqa'
        elif 'icheri' in desc_lower or 'bis' in desc_lower or 'baku' in desc_lower:
            return 'East-Восток', 'BIS - Baku, Icheri Sheher 1,2'
        else:
            # По умолчанию для Pasha Bank - East-Восток (аренда в Баку)
            return 'East-Восток', 'UKA - UK_AZ-Аренда'

    # ==================== NOMIQA ====================
    if 'mashreq' in file_lower or 'nomiqa' in file_lower:
        if 'dubai' in desc_lower or 'uae' in desc_lower or 'dnq' in desc_lower:
            return 'Nomiqa', 'DNQ_Dubai-Nomiqa'
        return 'Nomiqa', 'BNQ_BAKU-Nomiqa'

    # ==================== UNELMA ====================
    if 'unelma' in file_lower:
        return 'Unelma', 'UK_Unelma'

    # ==================== ПО УМОЛЧАНИЮ ====================
    return 'UK Estate', ''

def get_article(description, amount, file_name):
    """Определение статьи на основе описания и суммы (расширенный маппинг)"""
    desc_lower = description.lower()
    file_lower = file_name.lower()

    # ========== РАСХОДЫ (отрицательные суммы) ==========
    if amount < 0:
        # 1.2.17 РКО — банковские комиссии (приоритет самый высокий)
        if any(kw in desc_lower for kw in [
            'комиссия', 'commission', 'fee', 'charge', 'maintenance', 'rko', 'subscription',
            'atm withdrawal', 'плата за обслуживание', 'service package', 'számlakivonat díja',
            'netbankár monthly fee', 'conversion fee', 'charge for', 'bank charge',
            'pasha bank charge', 'fee for', 'monthly fee', 'account maintenance', 'card fee',
            'banking fee', 'transaction fee', 'service charge', 'tariff', 'тариф'
        ]):
            return '1.2.17 РКО', 'Расходы', 'Банковские комиссии'

        # 1.2.15.1 Зарплата
        if any(kw in desc_lower for kw in [
            'зарплат', 'salary', 'darba alga', 'algas izmaksa', 'darba algas izmaksa',
            'wage', 'payroll', 'alga', 'зарплата', 'зарплату'
        ]):
            return '1.2.15.1 Зарплата', 'Расходы', 'Зарплата'

        # 1.2.15.2 Налоги на ФОТ
        if any(kw in desc_lower for kw in [
            'nodokļu nomaksa', 'vid', 'budžets', 'налог', 'valsts budžets',
            'nodokļu', 'darba devēja', 'nodoku nomaksa', 'state revenue service',
            'social tax', 'социальный налог', 'подоходный налог', 'income tax'
        ]):
            return '1.2.15.2 Налоги на ФОТ', 'Расходы', 'Налоги на ФОТ'

        # 1.2.16.3 НДС
        if any(kw in desc_lower for kw in [
            'value added tax', 'vat', 'ндс', 'pvn', 'output tax', 'pvn nodoklis',
            'pvns', 'н.д.с.', 'добавленная стоимость'
        ]):
            return '1.2.16.3 НДС', 'Расходы', 'НДС'

        # 1.2.16.1 Налог на недвижимость
        if any(kw in desc_lower for kw in [
            'nekustamā īpašuma nodoklis', 'налог на недвижимость', 'pašvaldība',
            'property tax', 'real estate tax', 'имущественный налог'
        ]):
            return '1.2.16.1 Налог на недвижимость', 'Расходы', 'Налог на недвижимость'

        # 1.2.10.5 Электричество
        if any(kw in desc_lower for kw in [
            'latvenergo', 'elektri', 'электричеств', 'electricity', 'power',
            'elektrība', 'электроэнергия', 'light', 'освещение'
        ]):
            return '1.2.10.5 Электричество', 'Расходы', 'Электричество'

        # 1.2.10.3 Вода
        if any(kw in desc_lower for kw in [
            'rigas udens', 'ūdens', 'вода', 'water', 'woda', 'víz',
            'водоснабжение', 'водопровод'
        ]):
            return '1.2.10.3 Вода', 'Расходы', 'Вода'

        # 1.2.10.2 Газ
        if any(kw in desc_lower for kw in [
            'gāze', 'газ', 'gas', 'heating', 'отопление', 'тепло',
            'gáz', 'газовое', 'газоснабжение'
        ]):
            return '1.2.10.2 Газ', 'Расходы', 'Газ'

        # 1.2.10.1 Мусор
        if any(kw in desc_lower for kw in [
            'atkritumi', 'мусор', 'eco baltia', 'clean r', 'waste', 'garbage',
            'вывоз мусора', 'утилизация', 'trash', 'rubbish'
        ]):
            return '1.2.10.1 Мусор', 'Расходы', 'Вывоз мусора'

        # 1.2.10.6 Коммунальные УК дома
        if any(kw in desc_lower for kw in [
            'rigas namu pārvaldnieks', 'latvijas namsaimnieks', 'biedrība',
            'dzīvokļu īpašnieku', 'apartment owners', 'management fee',
            'управляющая компания', 'ук', 'house management', 'condominium'
        ]):
            return '1.2.10.6 Коммунальные УК дома', 'Расходы', 'Управляющая компания'

        # 1.2.9.1 Связь, интернет, TV
        if any(kw in desc_lower for kw in [
            'tele2', 'bite', 'tet', 'internet', 'связь', 'telenet', 'wifi', 'broadband',
            'телефон', 'phone', 'мобильная связь', 'mobile', 'телевидение', 'tv',
            'телеком', 'telecom', 'связь и интернет'
        ]):
            return '1.2.9.1 Связь, интернет, TV', 'Расходы', 'Связь и интернет'

        # 1.2.9.3 IT сервисы
        if any(kw in desc_lower for kw in [
            'google one', 'lovable', 'openai', 'chatgpt', 'browsec', 'adobe',
            'albato', 'slack', 'it сервисы', 'software', 'subscription',
            'microsoft', 'office 365', 'cloud', 'хостинг', 'hosting', 'domain',
            'домен', 'сервер', 'server', 'vps', 'vpn', 'антивирус', 'antivirus'
        ]):
            return '1.2.9.3 IT сервисы', 'Расходы', 'IT сервисы'

        # 1.2.3 Оплата рекламных систем
        if any(kw in desc_lower for kw in [
            'facebook', 'facbk', 'tiktok', 'ads', 'marketing', 'реклам', 'advertising',
            'instagram', 'google ads', 'fb ads', 'яндекс директ', 'yandex direct',
            'контекстная реклама', 'contextual advertising', 'promotion', 'продвижение'
        ]):
            return '1.2.3 Оплата рекламных систем (бюджет)', 'Расходы', 'Маркетинг'

        # 1.2.2 Командировочные расходы
        if any(kw in desc_lower for kw in [
            'flydubai', 'taxi', 'flixbus', 'bolt', 'uber', 'flix', 'careem',
            'travel', 'transport', 'hotel', 'accommodation', 'авиабилеты',
            'билеты', 'tickets', 'проживание', 'питание', 'meal', 'food',
            'командировка', 'business trip', 'транспортные расходы'
        ]):
            return '1.2.2 Командировочные расходы', 'Расходы', 'Командировки'

        # 1.2.8.1 Обслуживание объектов
        if any(kw in desc_lower for kw in [
            'apmaksa par rēķinu', 'обслуживание', 'ремонт', 'lifti', 'taipans',
            'sidorans', 'komval', 'rīgas lifti', 'maintenance', 'repair',
            'уборка', 'cleaning', 'клининг', 'сантехник', 'электрик',
            'plumber', 'electrician', 'техническое обслуживание'
        ]):
            return '1.2.8.1 Обслуживание объектов (бытовые вопросы, без ремонта)', 'Расходы', 'Обслуживание объектов'

        # 1.2.8.2 Страхование
        if any(kw in desc_lower for kw in [
            'balta', 'страхование', 'insurance', 'insure', 'страховка',
            'страховой взнос', 'insurance premium'
        ]):
            return '1.2.8.2 Страхование', 'Расходы', 'Страхование'

        # 1.2.12 Бухгалтер
        if any(kw in desc_lower for kw in [
            'lubova loseva', 'loseva', 'бухгалтер', 'accounting', 'bookkeeping',
            'бухгалтерские услуги', 'бухгалтерия', 'accountant', 'audit', 'аудит'
        ]):
            return '1.2.12 Бухгалтер', 'Расходы', 'Бухгалтерские услуги'

        # 2.2.7 Расходы по приобретению недвижимости
        if any(kw in desc_lower for kw in [
            'pirkuma liguma', 'приобретение недвижимости', 'аванс покупной стоимости',
            'property purchase', 'real estate purchase', 'покупка недвижимости',
            'advance payment', 'авансовый платеж'
        ]):
            return '2.2.7 Расходы по приобретению недвижимости', 'Расходы', 'Покупка недвижимости'

        # 1.2.27 Расходы в ожидании возмещения ЗП по другим бизнесам
        if any(kw in desc_lower for kw in [
            'jl/nf', 'jl/zp', 'расходы в ожидании', 'other business',
            'временные расходы', 'temporary expenses'
        ]):
            return '1.2.27 Расходы в ожидании возмещения ЗП по другим бизнесам', 'Расходы', 'Прочие расходы'

        # Перевод между счетами
        if any(kw in desc_lower for kw in [
            'currency exchange', 'конвертация', 'internal payment',
            'transfer to own account', 'между своими счетами', 'own transfer',
            'внутренний перевод', 'межбанковский перевод', 'bank transfer'
        ]):
            return 'Перевод между счетами', 'Расходы', 'Внутренний перевод'

        # 1.2.37 Возврат гарантийных депозитов
        if any(kw in desc_lower for kw in [
            'deposit return', 'возврат депозита', 'depozīta atgrie
