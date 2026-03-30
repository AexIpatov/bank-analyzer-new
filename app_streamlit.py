import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import re
import io
import os
from typing import List, Dict, Tuple, Optional
import chardet

# Настройка страницы
st.set_page_config(
    page_title="Финансовый аналитик выписок",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Кастомный CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.5rem 2rem;
        border-radius: 8px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102,126,234,0.4);
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
    .success-message {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .error-message {
        background: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Конфигурация
class Config:
    DATE_FORMATS = [
        "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d",
        "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d", "%d.%m.%y",
        "%d/%m/%y", "%y-%m-%d", "%Y%m%d"
    ]
    CSV_DELIMITERS = [';', ',', '\t', '|']
    ENCODINGS = ['utf-8', 'utf-8-sig', 'windows-1251', 'cp1251', 'latin-1']
    
    # Карта банков для определения формата
    BANK_PATTERNS = {
        'mkb_budapest': ['mkb', 'budapest', 'mkb bank'],
        'csob': ['csob', 'ceska sporitelna'],
        'unicredit': ['unicredit', 'unicredit bank'],
        'pasha': ['pasha bank', 'pasha'],
        'kapital': ['kapital bank'],
        'revolut': ['revolut'],
        'paysera': ['paysera']
    }

# Функции для работы с файлами
def detect_encoding(file_bytes: bytes) -> str:
    """Определение кодировки файла"""
    try:
        result = chardet.detect(file_bytes[:10000])
        return result['encoding'] if result['encoding'] else 'utf-8'
    except:
        return 'utf-8'

def detect_delimiter(content: str) -> str:
    """Определение разделителя CSV"""
    for delim in Config.CSV_DELIMITERS:
        if content.count(delim) > 5:
            return delim
    return ','

def parse_dates(date_str) -> str:
    """Парсинг даты из различных форматов"""
    if pd.isna(date_str):
        return ''
    
    date_str = str(date_str).strip()
    
    # Очистка
    date_str = re.sub(r'[^\d./\-]', '', date_str.split()[0] if ' ' in date_str else date_str)
    if not date_str:
        return ''
    
    # Пробуем все форматы
    for fmt in Config.DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except:
            continue
    
    # Ручной парсинг для формата DD.MM.YYYY
    if '.' in date_str:
        parts = date_str.split('.')
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            day, month, year = parts
            if len(year) == 2:
                year = f"20{year}"
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    
    return date_str

def parse_amount(amount_str, description="") -> float:
    """Парсинг суммы с определением знака"""
    if pd.isna(amount_str):
        return 0.0
    
    # Преобразование в строку
    amount_str = str(amount_str).strip()
    if amount_str in ['', 'nan', 'NaN', 'None', '-']:
        return 0.0
    
    # Сохраняем оригинал для контекста
    original = amount_str
    
    # Удаляем валюту
    amount_str = re.sub(r'\s*[A-Z]{3}\s*$', '', amount_str)
    amount_str = re.sub(r'^\s*[A-Z]{3}\s*', '', amount_str)
    
    # Замена разделителей
    amount_str = amount_str.replace(' ', '').replace('\xa0', '').replace(',', '.')
    
    # Определяем знак
    is_negative = False
    
    # Проверяем явный минус
    if amount_str.startswith('-'):
        is_negative = True
        amount_str = amount_str[1:]
    
    # Удаляем всё кроме цифр и точки
    amount_str = re.sub(r'[^\d.]', '', amount_str)
    
    if not amount_str:
        return 0.0
    
    try:
        amount = float(amount_str)
        
        # Контекстное определение знака
        if not is_negative and description:
            desc_lower = description.lower()
            expense_keywords = ['fee', 'charge', 'комиссия', 'tax', 'налог', 'payment', 'оплата', 
                              'списание', 'withdrawal', 'purchase', 'покупка']
            if any(kw in desc_lower for kw in expense_keywords):
                is_negative = True
        
        return -abs(amount) if is_negative else abs(amount)
        
    except ValueError:
        # Пробуем найти число в строке
        numbers = re.findall(r'-?\d+\.?\d*', original)
        if numbers:
            try:
                return float(numbers[0])
            except:
                pass
        return 0.0

# Определение статей
def get_article(description: str, amount: float) -> str:
    """Определение статьи расходов/доходов"""
    desc_lower = description.lower()
    
    if amount < 0:  # Расходы
        # Банковские комиссии
        if any(kw in desc_lower for kw in ['комиссия', 'commission', 'fee', 'charge', 'monthly fee']):
            return '1.2.17 РКО'
        
        # Налоги
        if any(kw in desc_lower for kw in ['налог', 'tax', 'nds', 'pvn', 'vat', 'budžets']):
            return '1.2.15.2 Налоги'
        
        # Коммунальные услуги
        if any(kw in desc_lower for kw in ['электричество', 'electricity', 'elektri']):
            return '1.2.10.5 Электричество'
        if any(kw in desc_lower for kw in ['вода', 'water', 'ūdens']):
            return '1.2.10.3 Вода'
        if any(kw in desc_lower for kw in ['газ', 'gas', 'gāze']):
            return '1.2.10.2 Газ'
        if any(kw in desc_lower for kw in ['мусор', 'atkritumi']):
            return '1.2.10.1 Мусор'
        
        # Связь и интернет
        if any(kw in desc_lower for kw in ['интернет', 'internet', 'телефон', 'теле2', 'tele2', 'bite', 'tet']):
            return '1.2.9.1 Связь, интернет'
        
        # IT сервисы
        if any(kw in desc_lower for kw in ['google', 'openai', 'chatgpt', 'adobe', 'slack', 'it сервис']):
            return '1.2.9.3 IT сервисы'
        
        # Транспорт и командировки
        if any(kw in desc_lower for kw in ['такси', 'taxi', 'uber', 'bolt', 'flydubai', 'hotel', 'отель']):
            return '1.2.2 Командировочные расходы'
        
        # Обслуживание
        if any(kw in desc_lower for kw in ['обслуживание', 'ремонт', 'maintenance', 'apmaksa']):
            return '1.2.8.1 Обслуживание объектов'
        
        # Страхование
        if any(kw in desc_lower for kw in ['страхование', 'insurance', 'apdrošināšana']):
            return '1.2.8.2 Страхование'
        
        # Бухгалтерия
        if any(kw in desc_lower for kw in ['бухгалтер', 'accounting']):
            return '1.2.12 Бухгалтер'
        
        return '1.2.8.1 Обслуживание объектов'
    
    else:  # Доходы
        # Аренда
        if any(kw in desc_lower for kw in ['аренд', 'rent', 'airbnb', 'booking']):
            return '1.1.1.3 Арендная плата'
        
        # Комиссии
        if any(kw in desc_lower for kw in ['комиссия', 'commission', 'agency']):
            return '1.1.4.1 Комиссия за продажу'
        
        # Возвраты
        if any(kw in desc_lower for kw in ['возврат', 'refund', 'reversal']):
            return '1.1.2.2 Возвраты от поставщиков'
        
        # Компенсации
        if any(kw in desc_lower for kw in ['компенсац', 'kompensācija']):
            return '1.1.2.3 Компенсация расходов'
        
        # Займы
        if any(kw in desc_lower for kw in ['займ', 'loan']):
            return '3.1.3 Получение займа'
        
        # Кэшбэк
        if any(kw in desc_lower for kw in ['кэшбэк', 'cashback', 'interest']):
            return '1.1.2.4 Прочие поступления'
        
        return '1.1.1.3 Арендная плата'

def get_direction(description: str, file_name: str) -> Tuple[str, str]:
    """Определение направления и объекта"""
    desc_lower = description.lower()
    file_lower = file_name.lower()
    
    # Latvia объекты
    objects = {
        'antonijas': ('Latvia', 'AN14 Антониас 14'),
        'caka': ('Latvia', 'AC89 Чака 89'),
        'matisa': ('Latvia', 'M81 Матиса 81'),
        'brīvības 117': ('Latvia', 'B117 Бривибас 117'),
        'valdemara': ('Latvia', 'V22 Валдемара 22'),
        'gertrudes': ('Latvia', 'G77 Гертрудес 77'),
        'dzirnavu': ('Latvia', 'DS1 Дзирнаву 1'),
        'cesu': ('Latvia', 'C23 Цесу 23'),
    }
    
    for key, (direction, subdirection) in objects.items():
        if key in desc_lower:
            return direction, subdirection
    
    # Europe объекты
    if any(x in file_lower for x in ['budapest', 'mkb']):
        return 'Europe', 'F6 Будапешт'
    if any(x in file_lower for x in ['csob', 'dzibik']):
        return 'Europe', 'DZ1 Дзибик'
    if 'masaryka' in desc_lower:
        return 'Europe', 'TGM45 Масарика'
    
    # East объекты
    if any(x in file_lower for x in ['pasha', 'kapital']):
        if 'nomiqa' in desc_lower:
            return 'Nomiqa', 'BNQ Номика'
        return 'East', 'UKA Азербайджан'
    
    if any(x in file_lower for x in ['mashreq', 'wio']):
        return 'Dubai', 'DNQ Дубай'
    
    return 'Other', 'Прочее'

def split_rental_payment(amount: float, subdirection: str) -> Tuple[float, float]:
    """Разделение арендного платежа на аренду и коммунальные"""
    ratios = {
        'AC89 Чака 89': (0.836, 0.164),
        'AN14 Антониас 14': (0.80, 0.20),
        'M81 Матиса 81': (0.70, 0.30),
        'B117 Бривибас 117': (0.85, 0.15),
        'V22 Валдемара 22': (0.55, 0.45),
        'G77 Гертрудес 77': (0.85, 0.15),
    }
    
    rent_ratio, util_ratio = ratios.get(subdirection, (0.85, 0.15))
    
    rent = round(amount * rent_ratio, 2)
    util = round(amount * util_ratio, 2)
    
    # Корректировка для точной суммы
    diff = amount - (rent + util)
    if abs(diff) > 0.01:
        if rent > util:
            rent += diff
        else:
            util += diff
    
    return rent, util

def parse_bank_file(file_content: bytes, file_name: str) -> List[Dict]:
    """Универсальный парсер файлов банков"""
    transactions = []
    file_lower = file_name.lower()
    
    # Определяем тип файла по расширению
    if file_name.endswith(('.xlsx', '.xls')):
        try:
            df = pd.read_excel(io.BytesIO(file_content), header=None)
        except:
            return []
    else:
        # Определяем кодировку
        encoding = detect_encoding(file_content)
        # Декодируем содержимое
        try:
            content = file_content.decode(encoding)
        except:
            try:
                content = file_content.decode('utf-8', errors='ignore')
            except:
                return []
        
        # Определяем разделитель
        delimiter = detect_delimiter(content)
        
        # Читаем CSV
        try:
            df = pd.read_csv(io.StringIO(content), sep=delimiter, header=None, 
                           encoding='utf-8', engine='python', on_bad_lines='skip')
        except:
            return []
    
    if df.empty:
        return []
    
    # Поиск колонок по ключевым словам
    date_col, amount_col, desc_col = None, None, None
    
    for idx, col in enumerate(df.columns):
        col_values = df[col].astype(str).str.lower()
        
        # Проверяем, содержит ли колонка даты
        if date_col is None:
            sample = col_values.head(10)
            if any(re.search(r'\d{2}[./-]\d{2}[./-]\d{2,4}', str(v)) for v in sample):
                date_col = col
                continue
        
        # Проверяем, содержит ли колонка суммы
        if amount_col is None:
            sample = col_values.head(10)
            if any(re.search(r'\d+[.,]\d+', str(v)) for v in sample):
                amount_col = col
                continue
        
        # Проверяем, содержит ли колонка текст
        if desc_col is None:
            sample = col_values.head(10)
            if any(len(str(v)) > 20 for v in sample):
                desc_col = col
    
    # Если не нашли, используем первые колонки
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]
    if amount_col is None and len(df.columns) > 1:
        amount_col = df.columns[1]
    if desc_col is None and len(df.columns) > 2:
        desc_col = df.columns[2]
    
    # Обработка транзакций
    for idx in range(len(df)):
        try:
            row = df.iloc[idx]
            
            # Пропускаем пустые строки
            if all(pd.isna(cell) or str(cell).strip() == '' for cell in row):
                continue
            
            # Получаем дату
            date_val = row[date_col] if date_col in row.index else None
            if pd.isna(date_val):
                continue
            
            date = parse_dates(date_val)
            if not date:
                continue
            
            # Получаем сумму
            amount_val = row[amount_col] if amount_col in row.index else None
            amount = parse_amount(amount_val) if not pd.isna(amount_val) else 0.0
            
            if amount == 0:
                continue
            
            # Получаем описание
            description = ''
            if desc_col in row.index and not pd.isna(row[desc_col]):
                description = str(row[desc_col])
            
            # Добавляем другие колонки в описание
            for col in df.columns:
                if col not in [date_col, amount_col, desc_col]:
                    val = row[col]
                    if not pd.isna(val) and str(val).strip() and str(val) != 'nan':
                        description += f" {val}"
            
            description = description.strip()
            
            # Определяем валюту
            currency = 'EUR'
            if 'czk' in file_lower:
                currency = 'CZK'
            elif 'huf' in file_lower:
                currency = 'HUF'
            elif 'azn' in file_lower:
                currency = 'AZN'
            elif 'aed' in file_lower:
                currency = 'AED'
            
            # Определяем статью и направление
            article = get_article(description, amount)
            direction, subdirection = get_direction(description, file_name)
            
            # Проверка на арендный платеж (только для доходов)
            if amount > 0 and 'rent' in description.lower() or 'аренд' in description.lower():
                if subdirection in ['AC89 Чака 89', 'AN14 Антониас 14', 'M81 Матиса 81', 
                                  'B117 Бривибас 117', 'V22 Валдемара 22', 'G77 Гертрудес 77']:
                    rent_part, util_part = split_rental_payment(amount, subdirection)
                    
                    # Арендная часть
                    transactions.append({
                        'Дата': date,
                        'Сумма': rent_part,
                        'Валюта': currency,
                        'Описание': f"{description[:200]} (аренда)",
                        'Статья': '1.1.1.3 Арендная плата',
                        'Направление': direction,
                        'Субнаправление': subdirection,
                        'Файл': file_name
                    })
                    
                    # Коммунальная часть
                    if util_part > 0:
                        transactions.append({
                            'Дата': date,
                            'Сумма': util_part,
                            'Валюта': currency,
                            'Описание': f"{description[:200]} (компенсация КУ)",
                            'Статья': '1.1.2.3 Компенсация коммунальных расходов',
                            'Направление': direction,
                            'Субнаправление': subdirection,
                            'Файл': file_name
                        })
                else:
                    # Обычная транзакция
                    transactions.append({
                        'Дата': date,
                        'Сумма': amount,
                        'Валюта': currency,
                        'Описание': description[:500],
                        'Статья': article,
                        'Направление': direction,
                        'Субнаправление': subdirection,
                        'Файл': file_name
                    })
            else:
                # Обычная транзакция
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Валюта': currency,
                    'Описание': description[:500],
                    'Статья': article,
                    'Направление': direction,
                    'Субнаправление': subdirection,
                    'Файл': file_name
                })
                
        except Exception as e:
            continue
    
    return transactions

# Основной интерфейс
def main():
    # Заголовок
    st.markdown("""
    <div class="main-header">
        <h1>📊 Финансовый аналитик выписок</h1>
        <p style="margin:0; opacity:0.9;">Автоматическая обработка банковских выписок</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Боковая панель
    with st.sidebar:
        st.markdown("### 📌 Информация")
        st.info("""
        **Поддерживаемые форматы:**
        - Excel (.xlsx, .xls)
        - CSV
        - TXT
        
        **Поддерживаемые банки:**
        Pasha, CSOB, UniCredit, Industra, 
        Kapital, Revolut, Paysera, MKB
        """)
        
        st.markdown("---")
        st.markdown("### 🎯 Особенности")
        st.markdown("""
        - ✅ Автоматическое определение кодировки
        - ✅ Умное распознавание колонок
        - ✅ Автоматическая категоризация
        - ✅ Разделение арендных платежей
        - ✅ Поддержка нескольких валют
        """)
    
    # Вкладки
    tab1, tab2 = st.tabs(["📄 Один файл", "📚 Несколько файлов"])
    
    with tab1:
        st.markdown("### Загрузите банковскую выписку")
        
        uploaded_file = st.file_uploader(
            "Выберите файл",
            type=['csv', 'xlsx', 'xls', 'txt'],
            key="single_file"
        )
        
        if uploaded_file:
            st.success(f"✅ Загружен файл: {uploaded_file.name}")
            
            col1, col2 = st.columns([1, 4])
            with col1:
                analyze_btn = st.button("🚀 Анализировать", key="analyze_single", use_container_width=True)
            
            if analyze_btn:
                with st.spinner("Анализируем выписку..."):
                    # Парсинг файла
                    file_content = uploaded_file.read()
                    transactions = parse_bank_file(file_content, uploaded_file.name)
                    
                    if transactions:
                        df = pd.DataFrame(transactions)
                        
                        # Статистика
                        st.markdown("---")
                        st.markdown("### 📊 Сводная статистика")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            income = df[df['Сумма'] > 0]['Сумма'].sum()
                            st.metric("💰 Доходы", f"{income:,.2f}")
                        with col2:
                            expense = abs(df[df['Сумма'] < 0]['Сумма'].sum())
                            st.metric("💸 Расходы", f"{expense:,.2f}")
                        with col3:
                            balance = income - expense
                            st.metric("⚖️ Баланс", f"{balance:,.2f}")
                        with col4:
                            st.metric("📝 Операций", len(df))
                        
                        # Таблица с транзакциями
                        st.markdown("### 📋 Детализация операций")
                        
                        # Форматирование для отображения
                        display_df = df.copy()
                        display_df['Сумма'] = display_df['Сумма'].apply(lambda x: f"{x:,.2f}")
                        
                        st.dataframe(
                            display_df,
                            use_container_width=True,
                            height=400
                        )
                        
                        # Экспорт в Excel
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df.to_excel(writer, sheet_name='Транзакции', index=False)
                            
                            # Добавляем сводную таблицу
                            summary = df.groupby('Статья').agg({
                                'Сумма': ['sum', 'count']
                            }).round(2)
                            summary.to_excel(writer, sheet_name='Сводка по статьям')
                            
                            # Сводка по направлениям
                            direction_summary = df.groupby(['Направление', 'Субнаправление']).agg({
                                'Сумма': 'sum'
                            }).round(2)
                            direction_summary.to_excel(writer, sheet_name='Сводка по объектам')
                        
                        output.seek(0)
                        
                        st.download_button(
                            label="📥 Скачать отчет (Excel)",
                            data=output,
                            file_name=f"financial_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                        
                    else:
                        st.error("❌ Не удалось обработать файл. Проверьте формат и попробуйте снова.")
    
    with tab2:
        st.markdown("### Загрузите несколько выписок")
        
        uploaded_files = st.file_uploader(
            "Выберите файлы",
            type=['csv', 'xlsx', 'xls', 'txt'],
            accept_multiple_files=True,
            key="multiple_files"
        )
        
        if uploaded_files:
            st.success(f"✅ Загружено файлов: {len(uploaded_files)}")
            
            if st.button("🚀 Анализировать все файлы", key="analyze_multiple", use_container_width=True):
                all_transactions = []
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for idx, file in enumerate(uploaded_files):
                    status_text.text(f"Обработка: {file.name}")
                    
                    file_content = file.read()
                    transactions = parse_bank_file(file_content, file.name)
                    all_transactions.extend(transactions)
                    
                    progress_bar.progress((idx + 1) / len(uploaded_files))
                
                status_text.empty()
                
                if all_transactions:
                    df = pd.DataFrame(all_transactions)
                    
                    # Статистика
                    st.markdown("---")
                    st.markdown("### 📊 Общая статистика")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        total_income = df[df['Сумма'] > 0]['Сумма'].sum()
                        st.metric("💰 Общий доход", f"{total_income:,.2f}")
                    with col2:
                        total_expense = abs(df[df['Сумма'] < 0]['Сумма'].sum())
                        st.metric("💸 Общий расход", f"{total_expense:,.2f}")
                    with col3:
                        total_balance = total_income - total_expense
                        st.metric("⚖️ Итоговый баланс", f"{total_balance:,.2f}")
                    with col4:
                        st.metric("📝 Всего операций", len(df))
                    
                    # Детализация
                    st.markdown("### 📋 Все операции")
                    
                    display_df = df.copy()
                    display_df['Сумма'] = display_df['Сумма'].apply(lambda x: f"{x:,.2f}")
                    
                    st.dataframe(
                        display_df,
                        use_container_width=True,
                        height=500
                    )
                    
                    # Экспорт
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, sheet_name='Все транзакции', index=False)
                        
                        # Сводка по файлам
                        file_summary = df.groupby('Файл').agg({
                            'Сумма': ['sum', 'count']
                        }).round(2)
                        file_summary.to_excel(writer, sheet_name='Сводка по файлам')
                        
                        # Сводка по статьям
                        article_summary = df.groupby('Статья').agg({
                            'Сумма': ['sum', 'count']
                        }).round(2)
                        article_summary.to_excel(writer, sheet_name='Сводка по статьям')
                    
                    output.seek(0)
                    
                    st.download_button(
                        label="📥 Скачать полный отчет (Excel)",
                        data=output,
                        file_name=f"full_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                    
                else:
                    st.error("❌ Не удалось обработать ни одного файла.")

if __name__ == "__main__":
    main()
