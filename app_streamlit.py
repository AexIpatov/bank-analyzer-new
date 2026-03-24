import streamlit as st
import pandas as pd
import io
import tempfile
import os
import chardet
import re
from datetime import datetime
from io import BytesIO

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

# ==================== КЛАСС УМНОГО ДЕТЕКТОРА ЗАГОЛОВКОВ ====================
class HeaderDetector:
    def __init__(self):
        self.header_patterns = {
            'date': ['date', 'дата', 'datum', 'dátum', 'transaction date', 'value date', 'booking date', 'дата транзакции', 'дата операции', 'posting date'],
            'amount': ['amount', 'сумма', 'összeg', 'betrag', 'debit', 'credit', 'дебет', 'кредит', 'debit(d)', 'credit(c)', 'сумма списания', 'сумма зачисления', 'доход', 'расход'],
            'description': ['description', 'описание', 'leírás', 'beschreibung', 'details', 'детали', 'transaction details', 'назначение платежа', 'примечание', 'narrative'],
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
                df = pd.read_excel(tmp_path, engine='openpyxl')
            except:
                df = pd.read_excel(tmp_path)
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
    
    formats = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d", "%d-%m-%Y"]
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

def parse_amount(amount_str):
    if pd.isna(amount_str):
        return 0
    amount_str = str(amount_str).strip()
    if amount_str == '' or amount_str == 'nan':
        return 0
    
    if re.match(r'^\d{1,2}\.\d{1,2}\.\d{2,4}$', amount_str):
        return 0
    
    if amount_str.startswith('-+'):
        amount_str = '-' + amount_str[2:]
    
    amount_str = amount_str.replace(',', '.').replace(' ', '')
    has_minus = amount_str.startswith('-')
    amount_str = re.sub(r'[^0-9\.\-]', '', amount_str)
    if amount_str == '' or amount_str == '-':
        return 0
    try:
        val = float(amount_str)
        if has_minus and val > 0:
            val = -val
        return val
    except:
        return 0

def get_direction_and_subdirection(file_name, description):
    """Определяет направление и субнаправление"""
    file_lower = file_name.lower()
    desc_lower = description.lower()
    
    # ==================== LATVIA ====================
    if 'antonijas' in file_lower or 'an14' in desc_lower or 'antonijas' in desc_lower:
        return 'Latvia', 'AN14 Антониас 14 (дом + парковка)'
    if 'caka' in desc_lower or 'ac89' in desc_lower or 'čaka' in desc_lower:
        return 'Latvia', 'AC89 Чака 89 (дом + парковка)'
    if 'plavas' in file_lower or 'matisa' in desc_lower or 'm81' in desc_lower:
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
    if 'budapest' in file_lower or 'yulia galvin' in desc_lower:
        return 'Europe', 'F6 Помещение в доме Будапешт'
    if 'dzibik' in file_lower or 'bilych nadiia' in desc_lower:
        return 'Europe', 'DZ1_Dzibik1'
    if 'bastet' in desc_lower or 'j91' in desc_lower:
        return 'Europe', 'J91 Ялтская - Помещение маленькое'
    if 'masaryka' in desc_lower or 'tgm45' in desc_lower or 'bagel lounge' in desc_lower:
        return 'Europe', 'TGM45 Масарика - Bagel Lounge'
    if 'otovice' in desc_lower or 'komplekt' in desc_lower:
        return 'Europe', 'OT1_Otovice Участок Свалка'
    if 'twohills' in file_lower or 'molly' in desc_lower:
        return 'Europe', 'MOL - Офис Molly'
    if 'sveciy' in file_lower or 'vilnus' in desc_lower:
        return 'Europe', 'LT_Vilnus'
    if 'garpiz' in file_lower or 'tgm20' in desc_lower:
        return 'Europe', 'TGM20-Masaryka20'
    
    # ==================== EAST ====================
    if 'pasha' in file_lower or 'kapital' in file_lower or 'bunda' in file_lower:
        if 'icheri' in desc_lower or 'bis' in desc_lower:
            return 'East-Восток', 'BIS - Baku, Icheri Sheher 1,2'
        return 'East-Восток', 'UKA - UK_AZ-Аренда'
    
    # ==================== NOMIQA ====================
    if 'mashreq' in file_lower or 'nomiqa' in file_lower:
        if 'dubai' in desc_lower or 'uae' in desc_lower:
            return 'Nomiqa', 'DNQ_Dubai-Nomiqa'
        return 'Nomiqa', 'BNQ_BAKU-Nomiqa'
    
    # ==================== UNELMA ====================
    if 'unelma' in file_lower:
        return 'Unelma', 'UK_Unelma'
    
    # ==================== ПО УМОЛЧАНИЮ ====================
    return 'UK Estate', ''

def get_article(description, amount):
    """Определение статьи на основе описания и суммы"""
    desc_lower = description.lower()
    
    if amount < 0:  # Расходы
        # 1.2.17 РКО — банковские комиссии
        if any(kw in desc_lower for kw in ['комиссия', 'commission', 'fee', 'charge', 'maintenance', 'rko', 'subscription', 'atm withdrawal', 'плата за обслуживание', 'service package', 'számlakivonat díja', 'netbankár monthly fee', 'conversion fee']):
            return '1.2.17 РКО', 'Расходы', 'Банковские комиссии'
        
        # 1.2.15.1 Зарплата
        if any(kw in desc_lower for kw in ['зарплат', 'salary', 'darba alga', 'algas izmaksa', 'darba algas izmaksa']):
            return '1.2.15.1 Зарплата', 'Расходы', 'Зарплата'
        
        # 1.2.15.2 Налоги на ФОТ
        if any(kw in desc_lower for kw in ['nodokļu nomaksa', 'vid', 'budžets', 'налог', 'valsts budžets', 'nodokļu', 'darba devēja']):
            return '1.2.15.2 Налоги на ФОТ', 'Расходы', 'Налоги на ФОТ'
        
        # 1.2.16.3 НДС
        if any(kw in desc_lower for kw in ['value added tax', 'vat', 'ндс', 'pvn']):
            return '1.2.16.3 НДС', 'Расходы', 'НДС'
        
        # 1.2.16.1 Налог на недвижимость
        if any(kw in desc_lower for kw in ['nekustamā īpašuma nodoklis', 'налог на недвижимость', 'pašvaldība']):
            return '1.2.16.1 Налог на недвижимость', 'Расходы', 'Налог на недвижимость'
        
        # 1.2.10.5 Электричество
        if any(kw in desc_lower for kw in ['latvenergo', 'elektri', 'электричеств', 'electricity']):
            return '1.2.10.5 Электричество', 'Расходы', 'Электричество'
        
        # 1.2.10.3 Вода
        if any(kw in desc_lower for kw in ['rigas udens', 'ūdens', 'вода']):
            return '1.2.10.3 Вода', 'Расходы', 'Вода'
        
        # 1.2.10.2 Газ
        if any(kw in desc_lower for kw in ['gāze', 'газ']):
            return '1.2.10.2 Газ', 'Расходы', 'Газ'
        
        # 1.2.10.1 Мусор
        if any(kw in desc_lower for kw in ['atkritumi', 'мусор', 'eco baltia', 'clean r']):
            return '1.2.10.1 Мусор', 'Расходы', 'Вывоз мусора'
        
        # 1.2.10.6 Коммунальные УК дома
        if any(kw in desc_lower for kw in ['rigas namu pārvaldnieks', 'latvijas namsaimnieks', 'biedrība', 'dzīvokļu īpašnieku']):
            return '1.2.10.6 Коммунальные УК дома', 'Расходы', 'Управляющая компания'
        
        # 1.2.9.1 Связь, интернет, TV
        if any(kw in desc_lower for kw in ['tele2', 'bite', 'tet', 'internet', 'связь', 'telenet']):
            return '1.2.9.1 Связь, интернет, TV', 'Расходы', 'Связь и интернет'
        
        # 1.2.9.3 IT сервисы
        if any(kw in desc_lower for kw in ['google one', 'lovable', 'openai', 'chatgpt', 'browsec', 'adobe', 'albato', 'slack']):
            return '1.2.9.3 IT сервисы', 'Расходы', 'IT сервисы'
        
        # 1.2.3 Оплата рекламных систем
        if any(kw in desc_lower for kw in ['facebook', 'facbk', 'tiktok', 'ads', 'marketing', 'реклам']):
            return '1.2.3 Оплата рекламных систем (бюджет)', 'Расходы', 'Маркетинг'
        
        # 1.2.2 Командировочные расходы
        if any(kw in desc_lower for kw in ['flydubai', 'taxi', 'flixbus', 'bolt', 'uber', 'flix', 'careem']):
            return '1.2.2 Командировочные расходы', 'Расходы', 'Командировки'
        
        # 1.2.8.1 Обслуживание объектов
        if any(kw in desc_lower for kw in ['apmaksa par rēķinu', 'обслуживание', 'ремонт', 'lifti', 'taipans', 'sidorans', 'komval', 'rīgas lifti']):
            return '1.2.8.1 Обслуживание объектов', 'Расходы', 'Обслуживание объектов'
        
        # 1.2.8.2 Страхование
        if any(kw in desc_lower for kw in ['balta', 'страхование', 'insurance']):
            return '1.2.8.2 Страхование', 'Расходы', 'Страхование'
        
        # 1.2.12 Бухгалтер
        if any(kw in desc_lower for kw in ['lubova loseva', 'loseva', 'бухгалтер']):
            return '1.2.12 Бухгалтер', 'Расходы', 'Бухгалтерские услуги'
        
        # 2.2.7 Расходы по приобретению недвижимости
        if any(kw in desc_lower for kw in ['pirkuma liguma', 'приобретение недвижимости', 'аванс покупной стоимости']):
            return '2.2.7 Расходы по приобретению недвижимости', 'Расходы', 'Покупка недвижимости'
        
        # Перевод между счетами
        if any(kw in desc_lower for kw in ['currency exchange', 'конвертация', 'internal payment', 'transfer to own account', 'между своими счетами']):
            return 'Перевод между счетами', 'Расходы', 'Внутренний перевод'
        
        # По умолчанию
        return '1.2.8.1 Обслуживание объектов', 'Расходы', 'Обслуживание объектов'
    
    else:  # Доходы
        # 1.1.1.2 Поступления систем бронирования
        if any(kw in desc_lower for kw in ['airbnb', 'booking.com', 'booking b.v.']):
            return '1.1.1.2 Поступления систем бронирования (Airbnb, Booking и пр.)', 'Доходы', 'Краткосрочная аренда'
        
        # 1.1.1.4 Получение гарантийного депозита
        if any(kw in desc_lower for kw in ['depozits', 'депозит', 'deposit']):
            return '1.1.1.4 Получение гарантийного депозита', 'Доходы', 'Гарантийный депозит'
        
        # 1.1.4.1 Комиссия за продажу недвижимости
        if any(kw in desc_lower for kw in ['commission', 'agency commissions', 'incoming swift payment', 'marketing and advertisement']):
            return '1.1.4.1 Комиссия за продажу недвижимости', 'Доходы', 'Комиссия за продажу'
        
        # 3.1.3 Получение внутригруппового займа
        if any(kw in desc_lower for kw in ['loan', 'займ', 'baltic solutions', 'payment acc loan agreement']):
            return '3.1.3 Получение внутригруппового займа', 'Доходы', 'Внутригрупповой займ'
        
        # 3.1.4 Возврат выданного внутригруппового займа
        if any(kw in desc_lower for kw in ['loan return', 'возврат займа', 'partial repayment']):
            return '3.1.4 Возврат выданного внутригруппового займа', 'Доходы', 'Возврат займа'
        
        # 3.1.1 Ввод средств
        if any(kw in desc_lower for kw in ['transfer to own account', 'между своими счетами']):
            return '3.1.1 Ввод средств', 'Доходы', 'Ввод средств'
        
        # 1.1.1.1 Арендная плата (наличные)
        if any(kw in desc_lower for kw in ['наличные', 'cash']):
            return '1.1.1.1 Арендная плата (наличные)', 'Доходы', 'Арендная плата наличные'
        
        # 1.1.2.3 Компенсация по коммунальным расходам
        if any(kw in desc_lower for kw in ['komunālie', 'utilities', 'компенсац', 'возмещени']):
            return '1.1.2.3 Компенсация по коммунальным расходам', 'Доходы', 'Компенсация коммунальных'
        
        # 1.1.2.4 Прочие мелкие поступления
        if any(kw in desc_lower for kw in ['кэшбэк', 'cashback', 'u rok do']):
            return '1.1.2.4 Прочие мелкие поступления', 'Доходы', 'Прочие доходы'
        
        # 1.1.2.2 Возвраты от поставщиков
        if any(kw in desc_lower for kw in ['return on request', 'возврат', 'refund']):
            return '1.1.2.2 Возвраты от поставщиков', 'Доходы', 'Возвраты от поставщиков'
        
        # 1.1.1.3 Арендная плата (счёт)
        if any(kw in desc_lower for kw in ['арендн', 'rent', 'money added', 'ire', 'dzivoklis', 'from', 'credit of sepa', 'topup']):
            return '1.1.1.3 Арендная плата (счёт)', 'Доходы', 'Арендная плата'
        
        # По умолчанию
        return '1.1.1.3 Арендная плата (счёт)', 'Доходы', 'Арендная плата'


def parse_file(file_content, file_name):
    df = read_file(file_content, file_name)
    if df is None or df.empty:
        st.error("❌ Не удалось прочитать файл")
        return []
    
    file_lower = file_name.lower()
    detector = HeaderDetector()
    file_type = detector.detect_file_type(file_name)
    
    # Поиск заголовков
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
    
    # Поиск колонок
    date_col = None
    amount_col = None
    desc_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in ['date', 'дата', 'datum', 'booking', 'posting', 'value']):
            if date_col is None:
                date_col = col
        if any(kw in col_lower for kw in ['amount', 'сумма', 'debit', 'credit', 'дебет', 'кредит', 'доход', 'расход']):
            if amount_col is None:
                amount_col = col
        if any(kw in col_lower for kw in ['description', 'описание', 'details', 'назначение', 'narrative', 'information']):
            if desc_col is None:
                desc_col = col
    
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]
    if amount_col is None and len(df.columns) > 1:
        amount_col = df.columns[1]
    if desc_col is None and len(df.columns) > 2:
        desc_col = df.columns[2]
    
    transactions = []
    
    for idx in range(len(df)):
        try:
            row = df.iloc[idx]
            
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
            
            for col in df.columns:
                if col not in [date_col, amount_col, desc_col]:
                    val = row[col]
                    if pd.notna(val) and str(val).strip() and str(val) != 'nan':
                        description += ' ' + str(val)
            
            # Определяем статью, направление и субнаправление
            article, direction_type, subdir_type = get_article(description, amount)
            direction, subdirection = get_direction_and_subdirection(file_name, description)
            
            # Определяем валюту
            currency = 'EUR'
            if 'CZK' in file_lower or 'czk' in str(df.columns).lower():
                currency = 'CZK'
            elif 'HUF' in file_lower:
                currency = 'HUF'
            elif 'RUB' in file_lower:
                currency = 'RUB'
            elif 'AED' in file_lower:
                currency = 'AED'
            elif 'AZN' in file_lower:
                currency = 'AZN'
            
            account_name = file_name.replace('.csv', '').replace('.xlsx', '').replace('.xls', '')
            
            transactions.append({
                'date': date,
                'amount': amount,
                'currency': currency,
                'account_name': account_name,
                'description': description[:500],
                'article_name': article,
                'direction': direction if direction else direction_type,
                'subdirection': subdirection if subdirection else subdir_type
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
