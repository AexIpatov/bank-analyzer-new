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
</style>
""", unsafe_allow_html=True)

# Конфигурация
class Config:
    DATE_FORMATS = [
        "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d",
        "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d", "%d.%m.%y",
        "%d/%m/%y", "%y-%m-%d", "%Y%m%d"
    ]

def parse_dates(date_val) -> str:
    """Парсинг даты из различных форматов"""
    if pd.isna(date_val):
        return ''
    
    # Если это datetime объект
    if isinstance(date_val, (datetime, pd.Timestamp)):
        return date_val.strftime("%Y-%m-%d")
    
    date_str = str(date_val).strip()
    
    # Очистка
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    
    # Пробуем все форматы
    for fmt in Config.DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except:
            continue
    
    return date_str

def parse_amount(amount_val, description="") -> float:
    """Парсинг суммы с правильной обработкой"""
    if pd.isna(amount_val):
        return 0.0
    
    # Если это уже число
    if isinstance(amount_val, (int, float)):
        return float(amount_val)
    
    amount_str = str(amount_val).strip()
    if amount_str in ['', 'nan', 'NaN', 'None', '-', 'null']:
        return 0.0
    
    # Сохраняем оригинал
    original = amount_str
    
    # Определяем знак
    is_negative = False
    if amount_str.startswith('-'):
        is_negative = True
        amount_str = amount_str[1:]
    elif amount_str.startswith('+'):
        amount_str = amount_str[1:]
    
    # Удаляем валюту
    amount_str = re.sub(r'\s*[A-Z]{3}\s*$', '', amount_str)
    amount_str = re.sub(r'^\s*[A-Z]{3}\s*', '', amount_str)
    
    # Удаляем пробелы
    amount_str = amount_str.replace(' ', '').replace('\xa0', '').replace('\u202f', '')
    
    # Очищаем от всех символов, кроме цифр, минуса и точки/запятой
    # Заменяем запятую на точку для десятичных
    if ',' in amount_str:
        # Проверяем, является ли запятая десятичным разделителем
        parts = amount_str.split(',')
        if len(parts) == 2 and len(parts[1]) <= 2:
            amount_str = amount_str.replace(',', '.')
    
    # Удаляем все кроме цифр, минуса и точки
    amount_str = re.sub(r'[^\d.-]', '', amount_str)
    
    if not amount_str or amount_str == '-':
        return 0.0
    
    try:
        amount = float(amount_str)
    except ValueError:
        # Пробуем найти число в строке
        numbers = re.findall(r'-?\d+\.?\d*', original)
        if numbers:
            try:
                amount = float(numbers[0])
            except:
                return 0.0
        else:
            return 0.0
    
    # Контекстное определение знака для расходов
    if not is_negative and amount > 0 and description:
        desc_lower = description.lower()
        expense_keywords = [
            'fee', 'charge', 'komis', 'díja', 'комиссия', 'tax', 'налог',
            'payment', 'оплата', 'списание', 'withdrawal', 'service', 
            'monthly', 'számlakivonat', 'díj'
        ]
        if any(kw in desc_lower for kw in expense_keywords):
            is_negative = True
    
    if is_negative and amount > 0:
        amount = -amount
    
    return amount

def get_article(description: str, amount: float) -> str:
    """Определение статьи расходов/доходов"""
    desc_lower = description.lower()
    
    if amount < 0:  # Расходы
        if any(kw in desc_lower for kw in ['fee', 'charge', 'service package', 'számlakivonat díja', 'díja']):
            return '1.2.17 РКО (банковские комиссии)'
        if any(kw in desc_lower for kw in ['налог', 'tax', 'vat']):
            return '1.2.15.2 Налоги'
        if any(kw in desc_lower for kw in ['электричество', 'electricity']):
            return '1.2.10.5 Электричество'
        if any(kw in desc_lower for kw in ['вода', 'water']):
            return '1.2.10.3 Вода'
        if any(kw in desc_lower for kw in ['газ', 'gas']):
            return '1.2.10.2 Газ'
        if any(kw in desc_lower for kw in ['интернет', 'internet', 'телефон']):
            return '1.2.9.1 Связь, интернет'
        return '1.2.8.1 Обслуживание объектов'
    else:  # Доходы
        if any(kw in desc_lower for kw in ['аренд', 'rent']):
            return '1.1.1.3 Арендная плата'
        if any(kw in desc_lower for kw in ['возврат', 'refund']):
            return '1.1.2.2 Возвраты от поставщиков'
        return '1.1.1.3 Арендная плата'

def get_direction(description: str, file_name: str) -> Tuple[str, str]:
    """Определение направления и объекта"""
    file_lower = file_name.lower()
    
    # MKB Budapest
    if 'budapest' in file_lower or 'mkb' in file_lower:
        return 'Europe', 'F6 Будапешт (MKB)'
    
    # Latvia объекты
    desc_lower = description.lower()
    if 'antonijas' in desc_lower:
        return 'Latvia', 'AN14 Антониас 14'
    if 'caka' in desc_lower:
        return 'Latvia', 'AC89 Чака 89'
    if 'matisa' in desc_lower:
        return 'Latvia', 'M81 Матиса 81'
    
    return 'Other', 'Прочее'

def parse_mkb_budapest(file_content: bytes, file_name: str) -> List[Dict]:
    """Специальный парсер для MKB Budapest выписок"""
    transactions = []
    
    try:
        # Читаем Excel файл без заголовков
        df = pd.read_excel(io.BytesIO(file_content), header=None)
        
        if df.empty:
            st.error("Файл пуст")
            return []
        
        # Отладочная информация
        st.info(f"Файл прочитан. Размер: {df.shape[0]} строк x {df.shape[1]} колонок")
        
        # Ищем строку с заголовками (Serial number, Value date и т.д.)
        header_row = -1
        for idx in range(min(30, len(df))):
            row_text = ' '.join([str(cell).lower() for cell in df.iloc[idx] if pd.notna(cell)])
            if 'serial number' in row_text or 'value date' in row_text:
                header_row = idx
                break
        
        if header_row == -1:
            st.error("Не найдена строка с заголовками")
            return []
        
        st.success(f"Найдена строка заголовков: {header_row + 1}")
        
        # Определяем индексы колонок
        headers = []
        for idx, cell in enumerate(df.iloc[header_row]):
            if pd.isna(cell):
                headers.append(f'col_{idx}')
            else:
                headers.append(str(cell).strip())
        
        # Индексы нужных колонок
        date_idx = None
        amount_idx = None
        desc_idx = None
        currency_idx = None
        
        for idx, header in enumerate(headers):
            header_lower = header.lower()
            if 'value date' in header_lower:
                date_idx = idx
            elif 'amount' in header_lower:
                amount_idx = idx
            elif 'narrative' in header_lower or 'transaction type' in header_lower:
                desc_idx = idx
            elif 'currency' in header_lower:
                currency_idx = idx
        
        # Если не нашли по заголовкам, ищем по содержимому
        if amount_idx is None:
            # Ищем колонку с числами
            for idx in range(len(headers)):
                sample = df.iloc[header_row+1:header_row+5, idx].dropna()
                if len(sample) > 0:
                    sample_str = sample.astype(str)
                    if any(re.search(r'-?\d+', str(v)) for v in sample_str):
                        amount_idx = idx
                        break
        
        if date_idx is None:
            date_idx = 1  # Value date обычно во второй колонке
        
        if desc_idx is None:
            desc_idx = 4  # Narrative обычно в 5-й колонке
        
        st.info(f"Колонки: дата={date_idx}, сумма={amount_idx}, описание={desc_idx}")
        
        # Обрабатываем строки
        processed = 0
        for idx in range(header_row + 1, len(df)):
            try:
                row = df.iloc[idx]
                
                # Пропускаем пустые строки
                if all(pd.isna(cell) or str(cell).strip() == '' for cell in row):
                    continue
                
                # Получаем дату
                if date_idx is None or date_idx >= len(row):
                    continue
                    
                date_val = row[date_idx]
                if pd.isna(date_val):
                    continue
                
                date = parse_dates(date_val)
                if not date:
                    continue
                
                # Получаем сумму
                if amount_idx is None or amount_idx >= len(row):
                    continue
                    
                amount_val = row[amount_idx]
                amount = parse_amount(amount_val)
                
                if amount == 0:
                    continue
                
                # Получаем описание
                description = ''
                if desc_idx and desc_idx < len(row) and not pd.isna(row[desc_idx]):
                    description = str(row[desc_idx])
                
                # Добавляем Transaction type если есть
                if len(row) > 11 and not pd.isna(row[11]):  # Transaction type
                    if description:
                        description += ' - '
                    description += str(row[11])
                
                # Получаем валюту
                currency = 'HUF'
                if currency_idx and currency_idx < len(row) and not pd.isna(row[currency_idx]):
                    currency = str(row[currency_idx])
                
                # Определяем статью и направление
                article = get_article(description, amount)
                direction, subdirection = get_direction(description, file_name)
                
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
                processed += 1
                
            except Exception as e:
                continue
        
        st.success(f"Обработано транзакций: {processed}")
        return transactions
        
    except Exception as e:
        st.error(f"Ошибка при парсинге MKB файла: {str(e)}")
        return []

def parse_bank_file(file_content: bytes, file_name: str) -> List[Dict]:
    """Универсальный парсер файлов банков"""
    file_lower = file_name.lower()
    
    # Специальная обработка для MKB Budapest
    if 'budapest' in file_lower or 'mkb' in file_lower:
        st.info("Обнаружен файл MKB Budapest, использую специальный парсер...")
        return parse_mkb_budapest(file_content, file_name)
    
    # Общий парсер для остальных файлов
    transactions = []
    
    try:
        # Определяем тип файла
        if file_name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(io.BytesIO(file_content), header=0)
        else:
            # Для CSV/TXT
            content = file_content.decode('utf-8', errors='ignore')
            df = pd.read_csv(io.StringIO(content), sep=None, engine='python')
        
        if df.empty:
            return []
        
        # Поиск колонок
        date_col, amount_col, desc_col = None, None, None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if any(kw in col_lower for kw in ['date', 'дата', 'value date']):
                date_col = col
            elif any(kw in col_lower for kw in ['amount', 'сумма', 'total']):
                amount_col = col
            elif any(kw in col_lower for kw in ['description', 'описание', 'narrative']):
                desc_col = col
        
        if date_col is None:
            date_col = df.columns[0]
        if amount_col is None and len(df.columns) > 1:
            amount_col = df.columns[1]
        if desc_col is None and len(df.columns) > 2:
            desc_col = df.columns[2]
        
        # Обработка транзакций
        for idx in range(len(df)):
            try:
                row = df.iloc[idx]
                
                # Дата
                date_val = row[date_col] if date_col in df.columns else None
                if pd.isna(date_val):
                    continue
                date = parse_dates(date_val)
                if not date:
                    continue
                
                # Сумма
                amount_val = row[amount_col] if amount_col in df.columns else 0
                amount = parse_amount(amount_val)
                if amount == 0:
                    continue
                
                # Описание
                description = ''
                if desc_col and desc_col in df.columns and not pd.isna(row[desc_col]):
                    description = str(row[desc_col])
                
                # Валюта
                currency = 'EUR'
                if 'czk' in file_lower:
                    currency = 'CZK'
                elif 'huf' in file_lower:
                    currency = 'HUF'
                
                # Статья и направление
                article = get_article(description, amount)
                direction, subdirection = get_direction(description, file_name)
                
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
                
    except Exception as e:
        st.error(f"Ошибка при парсинге файла {file_name}: {str(e)}")
        return []
    
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
        - CSV, TXT
        
        **Поддерживаемые банки:**
        - MKB Budapest (специальный парсер)
        - Pasha Bank
        - CSOB
        - UniCredit
        - Revolut
        - Paysera
        
        **Валюты:**
        EUR, CZK, HUF, AZN, AED
        """)
        
        st.markdown("---")
        st.markdown("### 🎯 Особенности")
        st.markdown("""
        - ✅ Специальный парсер для MKB Budapest
        - ✅ Автоматическое распознавание колонок
        - ✅ Правильная обработка сумм в HUF
        - ✅ Автоматическая категоризация
        - ✅ Экспорт в Excel с аналитикой
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
            st.info(f"Размер файла: {uploaded_file.size} байт")
            
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
