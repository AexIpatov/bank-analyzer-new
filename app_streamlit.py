import streamlit as st
import pandas as pd
import io
import tempfile
import os
import chardet
import re
from datetime import datetime
from io import BytesIO
from typing import Optional, List, Tuple, Dict, Any
import warnings

# Отключаем предупреждения
warnings.filterwarnings('ignore')

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
            
            # Проверяем соответствие паттернам
            for column_type, keywords in self.header_patterns.items():
                for keyword in keywords:
                    if keyword in cell_str:
                        score += 1
                        break  # Не учитываем повторные совпадения в одной ячейке
        
        # Штрафуем строки, которые выглядят как данные
        for cell in row:
            if pd.isna(cell):
                continue
            
            cell_str = str(cell).strip()
            
            # Проверяем, является ли ячейка датой
            if self._looks_like_date(cell_str):
                score -= 1
            
            # Проверяем, является ли ячейка числом (суммой)
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
        # Убираем все пробелы для проверки
        clean_value = value.replace(' ', '')
        
        amount_patterns = [
            r'^-?\d+[.,]\d{2}$',
            r'^-?\d+[.,]\d{2}[A-Z]{3}$',
            r'^-?\d+[A-Z]{3}$',
        ]
        
        for pattern in amount_patterns:
            if re.match(pattern, clean_value):
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
                # Пробуем преобразовать в число
                float(cell_str.replace(',', '.'))
                numeric_count += 1
            except ValueError:
                # Проверяем, является ли значение датой
                if self._looks_like_date(cell_str):
                    numeric_count += 1
        
        # Если больше половины ячеек выглядят как данные, это не заголовок
        if numeric_count > len(header) * 0.5:
            return False
        
        return True

# ==================== СПРАВОЧНИКИ ====================

REF = {
    'accounts': {
        'Industra': {
            'name': 'Industra Bank',
            'currency': 'HUF',
            'country': 'Hungary',
            'account_number': 'HU12345678901234567890123456'
        },
        'Revolut': {
            'name': 'Revolut',
            'currency': 'EUR',
            'country': 'UK',
            'account_number': 'GB29REVO00996912345678'
        },
        'Budapest': {
            'name': 'Budapest Bank',
            'currency': 'HUF',
            'country': 'Hungary',
            'account_number': 'HU98765432109876543210987654'
        },
        'Pasha': {
            'name': 'Pasha Bank',
            'currency': 'AZN',
            'country': 'Azerbaijan',
            'account_number': 'AZ21PAHA00000000001234567890'
        }
    },
    'articles': {
        '1.2.8.1 Обслуживание объектов': [
            'аренда', 'rent', 'квартплата', 'коммунальные', 'utility',
            'электричество', 'electricity', 'газ', 'gas', 'вода', 'water',
            'интернет', 'internet', 'телефон', 'phone', 'уборка', 'cleaning',
            'ремонт', 'repair', 'обслуживание', 'maintenance'
        ],
        '1.2.8.2 Транспорт': [
            'транспорт', 'transport', 'такси', 'taxi', 'бензин', 'fuel',
            'парковка', 'parking', 'автобус', 'bus', 'метро', 'metro',
            'поезд', 'train', 'авиабилет', 'flight', 'каршеринг', 'carsharing'
        ],
        '1.2.8.3 Питание': [
            'еда', 'food', 'ресторан', 'restaurant', 'кафе', 'cafe',
            'супермаркет', 'supermarket', 'продукты', 'groceries',
            'доставка', 'delivery', 'кофе', 'coffee', 'обед', 'lunch'
        ],
        '1.2.8.4 Здоровье': [
            'аптека', 'pharmacy', 'врач', 'doctor', 'больница', 'hospital',
            'лекарства', 'medicine', 'стоматолог', 'dentist', 'спортзал', 'gym',
            'йога', 'yoga', 'фитнес', 'fitness', 'страховка', 'insurance'
        ],
        '1.2.8.5 Образование': [
            'курсы', 'courses', 'обучение', 'education', 'книги', 'books',
            'конференция', 'conference', 'семинар', 'seminar', 'вебинар', 'webinar',
            'подписка', 'subscription', 'литература', 'literature'
        ],
        '1.2.8.6 Развлечения': [
            'кино', 'cinema', 'театр', 'theater', 'концерт', 'concert',
            'музей', 'museum', 'игры', 'games', 'хобби', 'hobby',
            'отдых', 'vacation', 'путешествие', 'travel', 'отель', 'hotel'
        ],
        '1.2.8.7 Одежда и аксессуары': [
            'одежда', 'clothes', 'обувь', 'shoes', 'аксессуары', 'accessories',
            'магазин', 'shop', 'бренд', 'brand', 'мода', 'fashion'
        ],
        '1.2.8.8 Техника и электроника': [
            'техника', 'electronics', 'телефон', 'phone', 'ноутбук', 'laptop',
            'компьютер', 'computer', 'гаджет', 'gadget', 'аксессуар', 'accessory'
        ],
        '1.2.8.9 Прочие расходы': [
            'прочие', 'other', 'разное', 'miscellaneous', 'неизвестно', 'unknown',
            'комиссия', 'fee', 'штраф', 'fine', 'подарок', 'gift', 'благотворительность', 'charity'
        ]
    }
}

# ==================== УТИЛИТЫ ====================

def detect_encoding(file_content: bytes) -> str:
    """
    Определяет кодировку файла
    """
    try:
        # Используем chardet для определения кодировки
        result = chardet.detect(file_content)
        encoding = result['encoding']
        
        # Проверяем надежность определения
        if result['confidence'] < 0.7:
            # Пробуем распространенные кодировки
            for enc in ['utf-8', 'windows-1251', 'cp1251', 'iso-8859-1', 'latin-1']:
                try:
                    file_content.decode(enc)
                    return enc
                except UnicodeDecodeError:
                    continue
        
        if encoding is None:
            return 'utf-8'
        
        return encoding
    except Exception:
        return 'utf-8'

def parse_amount(amount_str: str) -> float:
    """
    Парсит строку с суммой в число
    """
    if pd.isna(amount_str):
        return 0.0
    
    amount_str = str(amount_str).strip()
    
    if not amount_str:
        return 0.0
    
    # Убираем валюту и лишние символы
    amount_str = re.sub(r'[A-Z]{3}$', '', amount_str)  # Убираем валюту в конце
    amount_str = re.sub(r'[^\d.,-]', '', amount_str)   # Оставляем только цифры, точки, запятые и минус
    
    # Обработка отрицательных чисел
    is_negative = False
    if amount_str.startswith('-'):
        is_negative = True
        amount_str = amount_str[1:]
    elif amount_str.startswith('+'):
        amount_str = amount_str[1:]
    
    # Заменяем запятую на точку, если нужно
    if ',' in amount_str and '.' in amount_str:
        # Если есть и запятая, и точка, запятая - разделитель тысяч
        amount_str = amount_str.replace(',', '')
    elif ',' in amount_str:
        # Если только запятая - это разделитель десятичных
        amount_str = amount_str.replace(',', '.')
    
    try:
        amount = float(amount_str)
        if is_negative:
            amount = -amount
        return amount
    except ValueError:
        return 0.0

def get_article_by_description(description: str) -> str:
    """
    Определяет статью расходов по описанию
    """
    if pd.isna(description):
        return '1.2.8.9 Прочие расходы'
    
    desc_lower = str(description).lower()
    
    # Ищем совпадения в справочнике
    best_match = None
    best_score = 0
    
    for article, keywords in REF['articles'].items():
        score = 0
        for keyword in keywords:
            if keyword in desc_lower:
                score += 1
        
        if score > best_score:
            best_score = score
            best_match = article
    
    # Если найдено хорошее совпадение, возвращаем его
    if best_match and best_score >= 1:
        return best_match
    
    # Проверяем специальные случаи
    if any(word in desc_lower for word in ['зарплата', 'salary', 'income', 'доход']):
        return '1.2.1.1 Заработная плата'
    
    if any(word in desc_lower for word in ['перевод', 'transfer', 'перевод средств']):
        return '1.2.8.10 Переводы'
    
    return '1.2.8.9 Прочие расходы'

def get_account_info(filename: str) -> Dict[str, Any]:
    """
    Определяет информацию о счете по имени файла
    """
    filename_lower = filename.lower()
    
    for acc_name, info in REF['accounts'].items():
        if acc_name.lower() in filename_lower:
            return {
                'account_name': info['name'],
                'currency': info['currency'],
                'country': info['country'],
                'account_number': info['account_number']
            }
    
    # Если счет не найден, возвращаем значения по умолчанию
    return {
        'account_name': 'Unknown Bank',
        'currency': 'EUR',
        'country': 'Unknown',
        'account_number': 'N/A'
    }

# ==================== ОСНОВНЫЕ ФУНКЦИИ ПАРСИНГА ====================

def read_csv_file(file_content: bytes, filename: str) -> pd.DataFrame:
    """
    Читает CSV файл с автоматическим определением параметров
    """
    # Определяем кодировку
    encoding = detect_encoding(file_content)
    
    # Пробуем разные разделители
    separators = [';', ',', '\t', '|']
    
    for sep in separators:
        try:
            # Читаем файл с текущим разделителем
            df = pd.read_csv(
                BytesIO(file_content),
                sep=sep,
                encoding=encoding,
                dtype=str,
                on_bad_lines='skip'
            )
            
            # Проверяем, что DataFrame не пустой и имеет разумное количество колонок
            if not df.empty and len(df.columns) > 1:
                return df
        except Exception:
            continue
    
    # Если ни один разделитель не подошел, пробуем без указания разделителя
    try:
        df = pd.read_csv(
            BytesIO(file_content),
            encoding=encoding,
            dtype=str,
            on_bad_lines='skip'
        )
        return df
    except Exception as e:
        st.error(f"Ошибка при чтении CSV файла: {str(e)}")
        return pd.DataFrame()

def read_excel_file(file_content: bytes, filename: str) -> pd.DataFrame:
    """
    Читает Excel файл
    """
    try:
        # Пробуем разные движки
        try:
            df = pd.read_excel(BytesIO(file_content), dtype=str, engine='openpyxl')
        except Exception:
            try:
                df = pd.read_excel(BytesIO(file_content), dtype=str, engine='xlrd')
            except Exception:
                df = pd.read_excel(BytesIO(file_content), dtype=str)
        
        return df
    except Exception as e:
        st.error(f"Ошибка при чтении Excel файла: {str(e)}")
        return pd.DataFrame()

def read_file(file_content: bytes, filename: str) -> pd.DataFrame:
    """
    Читает файл в зависимости от расширения
    """
    filename_lower = filename.lower()
    
    if filename_lower.endswith(('.csv', '.txt')):
        return read_csv_file(file_content, filename)
    elif filename_lower.endswith(('.xlsx', '.xls')):
        return read_excel_file(file_content, filename)
    else:
        st.error(f"Неподдерживаемый формат файла: {filename}")
        return pd.DataFrame()

def parse_file(file_content: bytes, filename: str) -> pd.DataFrame:
    """
    Основная функция парсинга файла
    """
    # Читаем файл
    df = read_file(file_content, filename)
    
    if df.empty:
        return pd.DataFrame()
    
    # Инициализируем детектор заголовков
    detector = HeaderDetector()
    
    # Определяем тип файла
    file_type = detector.detect_file_type(filename)
    
    # Ищем строку с заголовками
    header_row = detector.find_header_row(df)
    
    if header_row is not None and detector.validate_header_row(df, header_row):
        # Используем найденную строку как заголовок
        df.columns = df.iloc[header_row]
        df = df.iloc[header_row + 1:].reset_index(drop=True)
    else:
        # Пробуем стандартные имена колонок
        expected_columns = detector.get_expected_columns(file_type)
        if len(df.columns) >= len(expected_columns):
            df.columns = expected_columns + list(df.columns[len(expected_columns):])
    
    # Очищаем данные
    df = df.dropna(how='all')  # Удаляем полностью пустые строки
    df = df.reset_index(drop=True)
    
    # Определяем колонки
    date_col = None
    amount_col = None
    desc_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        
        if date_col is None and any(keyword in col_lower for keyword in detector.header_patterns['date']):
            date_col = col
        elif amount_col is None and any(keyword in col_lower for keyword in detector.header_patterns['amount']):
            amount_col = col
        elif desc_col is None and any(keyword in col_lower for keyword in detector.header_patterns['description']):
            desc_col = col
    
    # Если не нашли колонки, используем первые подходящие
    if date_col is None:
        for col in df.columns:
            if df[col].apply(lambda x: detector._looks_like_date(str(x))).any():
                date_col = col
                break
    
    if amount_col is None:
        for col in df.columns:
            if df[col].apply(lambda x: detector._looks_like_amount(str(x))).any():
                amount_col = col
                break
    
    if desc_col is None:
        # Используем первую текстовую колонку
        for col in df.columns:
            if col not in [date_col, amount_col] and df[col].dtype == 'object':
                desc_col = col
                break
    
    # Если все еще не нашли, используем первые колонки
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]
    
    if amount_col is None and len(df.columns) > 1:
        amount_col = df.columns[1]
    
    if desc_col is None and len(df.columns) > 2:
        desc_col = df.columns[2]
    
    # Создаем результирующий DataFrame
    result_data = []
    
    for idx, row in df.iterrows():
        try:
            # Получаем значения
            date_val = row[date_col] if date_col in row else None
            amount_val = row[amount_col] if amount_col in row else None
            desc_val = row[desc_col] if desc_col in row else None
            
            # Парсим сумму
            amount = parse_amount(amount_val)
            
            # Пропускаем нулевые суммы (если это не информационная строка)
            if amount == 0 and desc_val and not any(word in str(desc_val).lower() for word in ['balance', 'остаток', 'saldo']):
                continue
            
            # Определяем тип операции
            operation_type = 'Расход' if amount < 0 else 'Доход'
            
            # Определяем статью
            article = get_article_by_description(desc_val)
            
            # Получаем информацию о счете
            account_info = get_account_info(filename)
            
            # Добавляем запись
            result_data.append({
                'Дата': date_val,
                'Сумма': abs(amount),
                'Валюта': account_info['currency'],
                'Описание': desc_val,
                'Тип операции': operation_type,
                'Статья': article,
                'Счет': account_info['account_name'],
                'Номер счета': account_info['account_number'],
                'Страна': account_info['country'],
                'Файл': filename
            })
        except Exception as e:
            # Пропускаем проблемные строки
            continue
    
    result_df = pd.DataFrame(result_data)
    
    # Конвертируем даты
    if not result_df.empty and 'Дата' in result_df.columns:
        result_df['Дата'] = pd.to_datetime(result_df['Дата'], errors='coerce')
    
    return result_df

# ==================== ИНТЕРФЕЙС ====================

def main():
    """
    Основная функция интерфейса
    """
    # Загрузка файлов
    uploaded_files = st.file_uploader(
        "📁 Загрузите файлы выписок",
        type=['csv', 'xlsx', 'xls'],
        accept_multiple_files=True
    )
    
    if not uploaded_files:
        st.info("👆 Загрузите файлы выписок для анализа")
        return
    
    # Обработка файлов
    all_data = []
    processed_files = []
    failed_files = []
    
    with st.spinner("🔍 Анализирую файлы..."):
        for uploaded_file in uploaded_files:
            try:
                # Читаем содержимое файла
                file_content = uploaded_file.getvalue()
                
                # Парсим файл
                df = parse_file(file_content, uploaded_file.name)
                
                if not df.empty:
                    all_data.append(df)
                    processed_files.append(uploaded_file.name)
                else:
                    failed_files.append(uploaded_file.name)
                    
            except Exception as e:
                failed_files.append(f"{uploaded_file.name} - ошибка: {str(e)}")
    
    # Отображаем результаты
    if all_data:
        # Объединяем все данные
        combined_df = pd.concat(all_data, ignore_index=True)
        
        # Отображаем статистику
        st.success(f"✅ Обработано файлов: {len(processed_files)}")
        
        if failed_files:
            st.warning(f"⚠️ Не удалось обработать: {len(failed_files)} файлов")
            for failed in failed_files:
                st.write(f"  - {failed}")
        
        # Показываем данные
        st.markdown("### 📋 Обработанные данные")
        
        # Фильтры
        col1, col2, col3 = st.columns(3)
        
        with col1:
            account_filter = st.multiselect(
                "Фильтр по счету",
                options=combined_df['Счет'].unique(),
                default=combined_df['Счет'].unique()
            )
        
        with col2:
            type_filter = st.multiselect(
                "Фильтр по типу операции",
                options=combined_df['Тип операции'].unique(),
                default=combined_df['Тип операции'].unique()
            )
        
        with col3:
            article_filter = st.multiselect(
                "Фильтр по статье",
                options=combined_df['Статья'].unique(),
                default=combined_df['Статья'].unique()
            )
        
        # Применяем фильтры
        filtered_df = combined_df[
            (combined_df['Счет'].isin(account_filter)) &
            (combined_df['Тип операции'].isin(type_filter)) &
            (combined_df['Статья'].isin(article_filter))
        ]
        
        # Показываем таблицу
        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Статистика
        st.markdown("### 📊 Статистика")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_income = filtered_df[filtered_df['Тип операции'] == 'Доход']['Сумма'].sum()
            st.metric("💰 Общий доход", f"{total_income:,.2f}")
        
        with col2:
            total_expense = filtered_df[filtered_df['Тип операции'] == 'Расход']['Сумма'].sum()
            st.metric("💸 Общий расход", f"{total_expense:,.2f}")
        
        with col3:
            balance = total_income - total_expense
            st.metric("⚖️ Баланс", f"{balance:,.2f}")
        
        with col4:
            transactions_count = len(filtered_df)
            st.metric("📈 Количество операций", transactions_count)
        
        # Детальная статистика по статьям
        st.markdown("### 📋 Распределение по статьям")
        
        if not filtered_df.empty:
            expense_by_article = filtered_df[filtered_df['Тип операции'] == 'Расход'].groupby('Статья')['Сумма'].sum().sort_values(ascending=False)
            income_by_article = filtered_df[filtered_df['Тип операции'] == 'Доход'].groupby('Статья')['Сумма'].sum().sort_values(ascending=False)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 💸 Расходы по статьям")
                if not expense_by_article.empty:
                    st.dataframe(
                        expense_by_article.reset_index().rename(columns={'Сумма': 'Сумма расходов'}),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("Нет данных о расходах")
            
            with col2:
                st.markdown("#### 💰 Доходы по статьям")
                if not income_by_article.empty:
                    st.dataframe(
                        income_by_article.reset_index().rename(columns={'Сумма': 'Сумма доходов'}),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("Нет
