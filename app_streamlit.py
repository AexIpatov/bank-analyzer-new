import streamlit as st
import pandas as pd
import io
import tempfile
import os
import chardet
import re
from datetime import datetime
from io import BytesIO
from typing import Optional, List, Tuple

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
    """Умный детектор заголовков для финансовых выписок"""
    
    def __init__(self):
        # Расширенный список ключевых слов для заголовков
        self.header_patterns = {
            'date': [
                'date', 'дата', 'datum', 'dátum', 'data',
                'transaction date', 'value date', 'booking date',
                'дата транзакции', 'дата операции'
            ],
            'amount': [
                'amount', 'сумма', 'összeg', 'betrag',
                'debit', 'credit', 'дебет', 'кредит',
                'debit(d)', 'credit(c)', 'сумма списания', 'сумма зачисления'
            ],
            'description': [
                'description', 'описание', 'leírás', 'beschreibung',
                'details', 'детали', 'transaction details',
                'назначение платежа', 'примечание'
            ],
            'balance': [
                'balance', 'остаток', 'egyenleg', 'saldo',
                'closing balance', 'конечный остаток'
            ]
        }
        
        # Паттерны для определения типа файла
        self.file_patterns = {
            'industra': [
                r'industra', r'индустра', r'банк.*индустра',
                r'.*industra.*\.(csv|xlsx|xls)$'
            ],
            'revolut': [
                r'revolut', r'револют', r'.*revolut.*statement',
                r'account-statement.*\.csv$'
            ],
            'budapest': [
                r'budapest', r'будапешт', r'budapest.*bank',
                r'bb.*\.(csv|xlsx|xls)$'
            ],
            'pasha': [
                r'pasha', r'паша', r'kapital', r'капитал',
                r'pasha.*bank', r'kapital.*bank'
            ]
        }
    
    def detect_file_type(self, filename: str) -> str:
        """Определяет тип файла по имени"""
        filename_lower = filename.lower()
        
        for file_type, patterns in self.file_patterns.items():
            for pattern in patterns:
                if re.search(pattern, filename_lower, re.IGNORECASE):
                    return file_type
        
        return "unknown"
    
    def find_header_row(self, df: pd.DataFrame, max_rows_to_check: int = 20) -> Optional[int]:
        """
        Находит строку с заголовками в DataFrame
        
        Args:
            df: DataFrame для поиска
            max_rows_to_check: максимальное количество строк для проверки
        
        Returns:
            Номер строки с заголовками или None если не найдено
        """
        if df.empty:
            return None
        
        rows_to_check = min(max_rows_to_check, len(df))
        
        best_match_score = 0
        best_match_row = None
        
        for row_idx in range(rows_to_check):
            row = df.iloc[row_idx]
            score = self._calculate_header_score(row)
            
            if score > best_match_score:
                best_match_score = score
                best_match_row = row_idx
        
        # Минимальный порог для уверенности
        if best_match_score >= 2:
            return best_match_row
        
        return None
    
    def _calculate_header_score(self, row: pd.Series) -> int:
        """Вычисляет оценку того, является ли строка заголовком"""
        score = 0
        
        for cell in row:
            if pd.isna(cell):
                continue
            
            cell_str = str(cell).lower().strip()
            
            for column_type, keywords in self.header_patterns.items():
                for keyword in keywords:
                    if keyword in cell_str:
                        score += 1
                        break
        
        for cell in row:
            if pd.isna(cell):
                continue
            
            cell_str = str(cell).strip()
            
            if self._looks_like_date(cell_str):
                score -= 1
            
            if self._looks_like_amount(cell_str):
                score -= 1
        
        return max(0, score)
    
    def _looks_like_date(self, value: str) -> bool:
        """Проверяет, похоже ли значение на дату"""
        date_patterns = [
            r'\d{4}[-./]\d{1,2}[-./]\d{1,2}',
            r'\d{1,2}[-./]\d{1,2}[-./]\d{4}',
            r'\d{1,2}[-./]\d{1,2}[-./]\d{2}',
        ]
        
        for pattern in date_patterns:
            if re.match(pattern, value):
                return True
        
        return False
    
    def _looks_like_amount(self, value: str) -> bool:
        """Проверяет, похоже ли значение на денежную сумму"""
        amount_patterns = [
            r'^-?\d+[.,]\d{2}$',
            r'^-?\d+[.,]\d{2}\s*[A-Z]{3}$',
            r'^-?\d+\s*[A-Z]{3}$',
        ]
        
        for pattern in amount_patterns:
            if re.match(pattern, value.replace(' ', '')):
                return True
        
        return False
    
    def get_expected_columns(self, file_type: str) -> List[str]:
        """Возвращает ожидаемые колонки для типа файла"""
        column_templates = {
            'industra': ['Дата транзакции', 'Дебет(D)', 'Кредит(C)', 'Информация о транзакции'],
            'revolut': ['Date started (UTC)', 'Type', 'Description', 'Amount'],
            'budapest': ['Serial number', 'Value date', 'Amount', 'Narrative'],
            'pasha': ['Дата', 'Сумма', 'Валюта', 'Описание'],
            'unknown': ['Date', 'Amount', 'Currency', 'Description']
        }
        
        return column_templates.get(file_type, column_templates['unknown'])
    
    def validate_header_row(self, df: pd.DataFrame, header_row: int) -> bool:
        """
        Проверяет, действительно ли найденная строка является заголовком
        """
        if header_row is None or header_row >= len(df):
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
            except ValueError:
                if self._looks_like_date(cell_str):
                    numeric_count += 1
        
        if numeric_count > len(header) * 0.5:
            return False
        
        return True


# ==================== ЗАГРУЗКА СПРАВОЧНИКОВ ====================
@st.cache_data
def load_reference_books():
    """Загружает справочники из файлов"""
    reference_books = {
        'accounts': {},
        'articles': {},
        'directions': {}
    }
    
    # Справочник банковских счетов
    try:
        df_accounts = pd.read_excel('Справочник банковских счетов_для_агента.xlsx', sheet_name='Для_агента')
        
        # Определяем колонки по названиям
        name_col = None
        direction_col = None
        subdirection_col = None
        currency_col = None
        
        for col in df_accounts.columns:
            col_lower = str(col).lower()
            if 'название' in col_lower:
                name_col = col
            if 'направление' in col_lower:
                direction_col = col
            if 'субнаправление' in col_lower:
                subdirection_col = col
            if 'валюта' in col_lower:
                currency_col = col
        
        if name_col:
            for _, row in df_accounts.iterrows():
                account_name = str(row[name_col]).strip()
                if account_name and account_name != 'nan':
                    reference_books['accounts'][account_name.lower()] = {
                        'direction': row[direction_col] if direction_col and pd.notna(row[direction_col]) else '',
                        'subdirection': row[subdirection_col] if subdirection_col and pd.notna(row[subdirection_col]) else '',
                        'currency': row[currency_col] if currency_col and pd.notna(row[currency_col]) else 'EUR',
                        'business': ''
                    }
    except Exception as e:
        st.warning(f"Не удалось загрузить справочник счетов: {e}")
    
    # Справочник статей
    try:
        df_articles = pd.read_excel('Справочник статей_для_агента.xlsx', sheet_name='Для_агента')
        
        # Определяем колонки
        code_col = None
        parent_col = None
        desc_col = None
        
        for col in df_articles.columns:
            col_lower = str(col).lower()
            if 'субстатья' in col_lower or 'статья' in col_lower:
                code_col = col
            if 'родительская' in col_lower:
                parent_col = col
            if 'описание' in col_lower:
                desc_col = col
        
        if code_col:
            for _, row in df_articles.iterrows():
                code = str(row[code_col]).strip()
                if code and code != 'nan':
                    reference_books['articles'][code.lower()] = {
                        'code': code,
                        'parent': row[parent_col] if parent_col and pd.notna(row[parent_col]) else '',
                        'description': row[desc_col] if desc_col and pd.notna(row[desc_col]) else ''
                    }
    except Exception as e:
        st.warning(f"Не удалось загрузить справочник статей: {e}")
    
    # Справочник направлений
    try:
        df_directions = pd.read_excel('Справочник направлений_для_агента.xlsx', sheet_name='Для_агента')
        
        direction_col = None
        subdirection_col = None
        
        for col in df_directions.columns:
            col_lower = str(col).lower()
            if 'направление' in col_lower:
                direction_col = col
            if 'субнаправление' in col_lower:
                subdirection_col = col
        
        if direction_col:
            for _, row in df_directions.iterrows():
                direction = str(row[direction_col]).strip()
                subdirection = str(row[subdirection_col]).strip() if subdirection_col else ''
                if direction and direction != 'nan':
                    if direction not in reference_books['directions']:
                        reference_books['directions'][direction] = []
                    if subdirection and subdirection != 'nan':
                        reference_books['directions'][direction].append(subdirection.lower())
    except Exception as e:
        st.warning(f"Не удалось загрузить справочник направлений: {e}")
    
    return reference_books

# Загружаем справочники
REF = load_reference_books()

# Создаем экземпляр детектора
HEADER_DETECTOR = HeaderDetector()


# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================
def read_file(file_content, file_name):
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        if file_name.lower().endswith(('.xls', '.xlsx')):
            if file_name.lower().endswith('.xlsx'):
                try:
                    df = pd.read_excel(tmp_path, engine='openpyxl')
                except:
                    df = pd.read_excel(tmp_path)
            else:
                try:
                    df = pd.read_excel(tmp_path, engine='xlrd')
                except:
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
    
    formats = [
        "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y",
        "%Y.%m.%d", "%d-%m-%Y", "%Y/%m/%d"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
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
    if re.match(r'^\d{4}-\d{2}-\d{2}', amount_str):
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

def get_account_info(file_name, df):
    """Определяет счет и по нему направление и субнаправление"""
    file_lower = file_name.lower()
    
    for acc_name, info in REF['accounts'].items():
        if acc_name in file_lower:
            return info['direction'], info['subdirection'], info['currency'], acc_name
    
    return 'UK Estate', '', 'EUR', file_name.replace('.csv', '').replace('.xlsx', '').replace('.xls', '')

def get_article_by_description(description, amount):
    desc_lower = description.lower()
    
    if amount < 0:
        if any(kw in desc_lower for kw in ['комиссия', 'commission', 'fee', 'charge', 'maintenance', 'rko', 'subscription', 'atm withdrawal', 'foreign exchange', 'плата за обслуживание', 'service package', 'számlakivonat díja', 'netbankár monthly fee']):
            return '1.2.17 РКО', 'Расходы', 'Банковские комиссии'
        
        if any(kw in desc_lower for kw in ['service package monthly fee']):
            return '1.2.21.2 Административные офисные расходы', 'Расходы', 'Офисные расходы'
        
        if any(kw in desc_lower for kw in ['зарплат', 'salary', 'darba alga', 'algas izmaksa']):
            return '1.2.15.1 Зарплата', 'Расходы', 'Зарплата'
        
        if any(kw in desc_lower for kw in ['nodokļu nomaksa', 'vid', 'budžets', 'налог']):
            if '1.2.15.2' in desc_lower:
                return '1.2.15.2 Налоги на ФОТ', 'Расходы', 'Налоги на ФОТ'
            if '1.2.16.4' in desc_lower:
                return '1.2.16.3 НДС', 'Расходы', 'НДС'
            return '1.2.16 Налоги', 'Расходы', 'Налоги'
        
        if any(kw in desc_lower for kw in ['latvenergo', 'elektri', 'электричеств', 'electricity']):
            return '1.2.10.5 Электричество', 'Расходы', 'Электричество'
        
        if any(kw in desc_lower for kw in ['rigas udens', 'ūdens', 'вода']):
            return '1.2.10.3 Вода', 'Расходы', 'Вода'
        
        if any(kw in desc_lower for kw in ['gāze', 'газ']):
            return '1.2.10.2 Газ', 'Расходы', 'Газ'
        
        if any(kw in desc_lower for kw in ['atkritumi', 'мусор', 'eco baltia', 'clean r']):
            return '1.2.10.1 Мусор', 'Расходы', 'Вывоз мусора'
        
        if any(kw in desc_lower for kw in ['rigas namu pārvaldnieks', 'latvijas namsaimnieks', 'biedrība']):
            return '1.2.10.6 Коммунальные УК дома', 'Расходы', 'Управляющая компания'
        
        if any(kw in desc_lower for kw in ['tele2', 'bite', 'tet', 'internet', 'связь']):
            return '1.2.9.1 Связь, интернет, TV', 'Расходы', 'Связь и интернет'
        
        if any(kw in desc_lower for kw in ['google one', 'lovable', 'openai', 'chatgpt', 'browsec', 'adobe']):
            return '1.2.9.3 IT сервисы', 'Расходы', 'IT сервисы'
        
        if any(kw in desc_lower for kw in ['facebook', 'facbk', 'tiktok', 'ads', 'marketing', 'реклам']):
            return '1.2.3 Оплата рекламных систем (бюджет)', 'Расходы', 'Маркетинг'
        
        if any(kw in desc_lower for kw in ['flydubai', 'taxi', 'flixbus', 'bolt', 'uber', 'flix']):
            return '1.2.2 Командировочные расходы', 'Расходы', 'Командировки'
        
        if any(kw in desc_lower for kw in ['apmaksa par rēķinu', 'обслуживание', 'ремонт', 'lifti', 'taipans']):
            return '1.2.8.1 Обслуживание объектов', 'Расходы', 'Обслуживание объектов'
        
        if any(kw in desc_lower for kw in ['balta', 'страхование', 'insurance']):
            return '1.2.8.2 Страхование', 'Расходы', 'Страхование'
        
        if any(kw in desc_lower for kw in ['аренда офиса', 'office rent']):
            return '1.2.21.1 Аренда офиса', 'Расходы', 'Аренда офиса'
        
        if any(kw in desc_lower for kw in ['lubova loseva', 'loseva', 'бухгалтер']):
            return '1.2.12 Бухгалтер', 'Расходы', 'Бухгалтерские услуги'
        
        if any(kw in desc_lower for kw in ['pirkuma liguma', 'приобретение недвижимости']):
            return '2.2.7 Расходы по приобретению недвижимости', 'Расходы', 'Покупка недвижимости'
        
        if any(kw in desc_lower for kw in ['notāra', 'tiesu administrācija', 'valsts kase']):
            return '2.2.4 Прочее', 'Расходы', 'Прочие расходы'
        
        if any(kw in desc_lower for kw in ['currency exchange', 'конвертация', 'internal payment']):
            return 'Перевод между счетами', 'Расходы', 'Внутренний перевод'
        
        return '1.2.8.1 Обслуживание объектов', 'Расходы', 'Обслуживание объектов'
    
    else:
        if any(kw in desc_lower for kw in ['airbnb', 'booking.com']):
            return '1.1.1.2 Поступления систем бронирования (Airbnb, Booking и пр.)', 'Доходы', 'Краткосрочная аренда'
        
        if any(kw in desc_lower for kw in ['depozits', 'депозит', 'deposit']):
            return '1.1.1.4 Получение гарантийного депозита', 'Доходы', 'Гарантийный депозит'
        
        if any(kw in desc_lower for kw in ['commission', 'agency commissions', 'incoming swift payment']):
            return '1.1.4.1 Комиссия за продажу недвижимости', 'Доходы', 'Комиссия за продажу'
        
        if any(kw in desc_lower for kw in ['loan', 'займ', 'baltic solutions']):
            return '3.1.3 Получение внутригруппового займа', 'Доходы', 'Внутригрупповой займ'
        
        if any(kw in desc_lower for kw in ['loan return', 'возврат займа']):
            return '3.1.4 Возврат выданного внутригруппового займа', 'Доходы', 'Возврат займа'
        
        if any(kw in desc_lower for kw in ['transfer to own account', 'между своими счетами']):
            return '3.1.1 Ввод средств', 'Доходы', 'Ввод средств'
        
        if any(kw in desc_lower for kw in ['наличные', 'cash', 'rent for january', 'c89-1(3)']):
            return '1.1.1.1 Арендная плата (наличные)', 'Доходы', 'Арендная плата наличные'
        
        if any(kw in desc_lower for kw in ['komunālie', 'utilities', 'компенсац', 'возмещени']):
            return '1.1.2.3 Компенсация по коммунальным расходам', 'Доходы', 'Компенсация коммунальных'
        
        if any(kw in desc_lower for kw in ['кэшбэк', 'cashback', 'u rok do']):
            return '1.1.2.4 Прочие мелкие поступления', 'Доходы', 'Прочие доходы'
        
        if any(kw in desc_lower for kw in ['арендн', 'rent', 'money added', 'ire', 'dzivoklis', 'from', 'credit of sepa']):
            return '1.1.1.3 Арендная плата (счёт)', 'Доходы', 'Арендная плата'
        
        return '1.1.1.3 Арендная плата (счёт)', 'Доходы', 'Арендная плата'

def parse_file(file_content, file_name):
    df = read_file(file_content, file_name)
    if df is None:
        st.error("❌ Не удалось прочитать файл")
        return []
    
    file_lower = file_name.lower()
    
    # Определяем тип файла и получаем информацию о счете
    file_type = HEADER_DETECTOR.detect_file_type(file_name)
    direction, subdirection, default_currency, account_name = get_account_info(file_name, df)
    
    # Находим строку заголовков с помощью умного детектора
    header_row = HEADER_DETECTOR.find_header_row(df)
    
    if header_row is not None and HEADER_DETECTOR.validate_header_row(df, header_row):
        st.write(f"✅ Найдена строка заголовков на индексе {header_row}")
        
        headers = list(df.iloc[header_row].values)
        clean_headers = []
        for h in headers:
            if pd.notna(h) and str(h).strip():
                clean_headers.append(str(h).strip())
            else:
                clean_headers.append(f'col_{len(clean_headers)}')
        
        seen = {}
        unique_headers = []
        for h in clean_headers:
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
        st.write(f"Создан DataFrame с колонками: {list(df.columns)}")
    else:
        st.warning("⚠️ Не удалось найти строку заголовков, будут использованы стандартные имена колонок")
    
    if len(df) == 0:
        st.warning("⚠️ В файле не найдено данных для обработки")
        return []
    
    # Поиск столбцов даты и суммы
    date_col = None
    amount_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in ['date', 'дата', 'datum', 'booking date', 'value date', 'posting date']):
            date_col = col
            break
    
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]
    
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in ['amount', 'сумма', 'debit', 'credit', 'дебет', 'кредит', 'доход', 'расход']):
            amount_col = col
            break
    
    if amount_col is None and len(df.columns) > 1:
        amount_col = df.columns[1]
    
    st.write(f"Столбец даты: {date_col}")
    st.write(f"Столбец суммы: {amount_col}")
    
    # Обработка транзакций
    transactions = []
    
    for idx in range(len(df)):
        try:
            row = df.iloc[idx]
            
            date = ''
            if date_col is not None:
                date_val = row[date_col]
                if pd.notna(date_val):
                    date = parse_date(date_val)
            
            if not date:
                continue
            
            amount = 0
            if amount_col is not None:
                amount_val = row[amount_col]
                if pd.notna(amount_val):
                    amount = parse_amount(amount_val)
            
            if amount == 0:
                continue
            
            if abs(amount) > 1000000:
                continue
            
            description = ''
            for col in df.columns:
                if col not in [date_col, amount_col]:
                    val = row[col]
                    if pd.notna(val) and str(val).strip() and str(val) != 'nan':
                        description += str(val) + ' '
            
            article, direction_type, subdir_type = get_article_by_description(description, amount)
            
            currency = default_currency
            if 'CZK' in file_lower:
                currency = 'CZK'
            elif 'HUF' in file_lower:
                currency = 'HUF'
            elif 'RUB' in file_lower:
                currency = 'RUB'
            elif 'AED' in file_lower:
                currency = 'AED'
            elif 'AZN' in file_lower:
                currency = 'AZN'
            
            transactions.append({
                'date': date,
                'amount': amount,
                'currency': currency,
                'account_name': account_name,
                'description': description[:300],
                'article_name': article,
                'direction': direction if direction else direction_type,
                'subdirection': subdirection if subdirection else subdir_type
            })
            
        except Exception as e:
            st.write(f"⚠️ Ошибка в строке {idx}: {e}")
            continue
    
    st.write(f"=== Найдено транзакций: {len(transactions)} ===")
    return transactions


# ==================== ИНТЕРФЕЙС ПОЛЬЗОВАТЕЛЯ ====================
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
                        доход = df[df['Сумма'] > 0]['Сумма'].sum() if len(df[df['Сумма'] > 0]) > 0 else 0
                        st.metric("📈 Доходы", f"{доход:,.2f}")
                    with col_c:
                        расход = abs(df[df['Сумма'] < 0]['Сумма'].sum()) if len(df[df['Сумма'] < 0]) > 0 else 0
                        st.metric("📉 Расходы", f"{расход:,.2f}")
                    st.dataframe(df, use_container_width=True)
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Транзакции')
                    output.seek(0)
                    st.download_button(
                        "📥 Скачать Excel", 
                        data=output, 
                        file_name=f"анализ_{uploaded_file.name}.xlsx"
                    )
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
                    доход = df[df['Сумма'] > 0]['Сумма'].sum() if len(df[df['Сумма'] > 0]) > 0 else 0
                    st.metric("📈 Доходы", f"{доход:,.2f}")
                with col_c:
                    расход = abs(df[df['Сумма'] < 0]['Сумма'].sum()) if len(df[df['Сумма'] < 0]) > 0 else 0
                    st.metric("📉 Расходы", f"{расход:,.2f}")
                st.dataframe(df, use_container_width=True)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Все транзакции')
                output.seek(0)
                st.download_button(
                    "📥 Скачать сводный Excel", 
                    data=output, 
                    file_name="сводка.xlsx"
                )
