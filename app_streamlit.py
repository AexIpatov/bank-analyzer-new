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
    .debug-info {
        background: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        font-family: monospace;
        font-size: 12px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

def clean_numeric_string(value) -> str:
    """Очистка строки для преобразования в число"""
    if pd.isna(value):
        return ''
    
    str_val = str(value).strip()
    
    # Если это уже число
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    
    # Удаляем валюту
    str_val = re.sub(r'\s*[A-Z]{3}\s*$', '', str_val)
    str_val = re.sub(r'^\s*[A-Z]{3}\s*', '', str_val)
    
    # Удаляем пробелы
    str_val = str_val.replace(' ', '').replace('\xa0', '').replace('\u202f', '')
    
    # Заменяем запятую на точку для десятичных
    if ',' in str_val:
        # Проверяем, является ли запятая десятичным разделителем
        parts = str_val.split(',')
        if len(parts) == 2 and len(parts[1]) <= 2:
            str_val = str_val.replace(',', '.')
    
    # Удаляем все кроме цифр, минуса и точки
    str_val = re.sub(r'[^\d.-]', '', str_val)
    
    return str_val

def parse_amount_safe(amount_val) -> float:
    """Безопасный парсинг суммы"""
    if pd.isna(amount_val):
        return 0.0
    
    # Если это уже число
    if isinstance(amount_val, (int, float)):
        # Проверяем, не является ли это ID или другим большим числом
        if abs(amount_val) > 1e12:  # Слишком большая сумма (больше триллиона)
            return 0.0
        return float(amount_val)
    
    str_val = clean_numeric_string(amount_val)
    
    if not str_val or str_val == '-':
        return 0.0
    
    try:
        amount = float(str_val)
        # Проверяем на реалистичность суммы
        if abs(amount) > 1e9:  # Больше миллиарда - вероятно, не сумма
            return 0.0
        return amount
    except:
        return 0.0

def parse_dates_safe(date_val) -> str:
    """Безопасный парсинг даты"""
    if pd.isna(date_val):
        return ''
    
    if isinstance(date_val, (datetime, pd.Timestamp)):
        return date_val.strftime("%Y-%m-%d")
    
    date_str = str(date_val).strip()
    
    # Очистка
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    
    # Проверяем, похоже ли на дату
    if not re.search(r'\d{4}-\d{2}-\d{2}|\d{2}[./-]\d{2}[./-]\d{2,4}', date_str):
        return ''
    
    formats = [
        "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d",
        "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d", "%d.%m.%y"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except:
            continue
    
    # Ручной парсинг
    if '.' in date_str:
        parts = date_str.split('.')
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            day, month, year = parts
            if len(year) == 2:
                year = f"20{year}"
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    
    return ''

def is_valid_transaction(row, date_col, amount_col) -> bool:
    """Проверка, является ли строка валидной транзакцией"""
    # Проверяем дату
    if date_col is None or date_col not in row.index:
        return False
    
    date_val = row[date_col]
    if pd.isna(date_val):
        return False
    
    date_str = parse_dates_safe(date_val)
    if not date_str:
        return False
    
    # Проверяем сумму
    if amount_col is None or amount_col not in row.index:
        return False
    
    amount_val = row[amount_col]
    amount = parse_amount_safe(amount_val)
    
    if amount == 0:
        return False
    
    return True

def parse_mkb_budapest(file_content: bytes, file_name: str) -> List[Dict]:
    """Специальный парсер для MKB Budapest выписок"""
    transactions = []
    
    try:
        # Читаем Excel файл
        df = pd.read_excel(io.BytesIO(file_content), header=None)
        
        if df.empty:
            return []
        
        # Ищем строку с данными (ищем числовые значения)
        data_start_row = -1
        for idx in range(min(30, len(df))):
            row = df.iloc[idx]
            # Ищем строку с Serial number
            first_cell = str(row[0]).lower() if len(row) > 0 else ''
            if 'serial number' in first_cell:
                data_start_row = idx + 1
                break
        
        if data_start_row == -1:
            # Ищем по наличию дат
            for idx in range(min(30, len(df))):
                row = df.iloc[idx]
                if len(row) > 1:
                    cell = row[1]
                    if not pd.isna(cell):
                        date_str = parse_dates_safe(cell)
                        if date_str:
                            data_start_row = idx
                            break
        
        if data_start_row == -1:
            return []
        
        # Определяем колонки
        # В MKB файле:
        # Колонка 1 - Serial number (дата)
        # Колонка 9 - Amount
        # Колонка 11 - Transaction type
        # Колонка 12 - Narrative
        
        for idx in range(data_start_row, len(df)):
            try:
                row = df.iloc[idx]
                
                # Пропускаем пустые строки
                if all(pd.isna(cell) or str(cell).strip() == '' for cell in row):
                    continue
                
                # Получаем дату (колонка 1 - Value date)
                if len(row) <= 1:
                    continue
                
                date_val = row[1]
                date = parse_dates_safe(date_val)
                if not date:
                    continue
                
                # Получаем сумму (колонка 9)
                if len(row) <= 9:
                    continue
                
                amount_val = row[9]
                amount = parse_amount_safe(amount_val)
                
                if amount == 0:
                    continue
                
                # Получаем описание
                description = ''
                if len(row) > 11 and not pd.isna(row[11]):
                    description = str(row[11])
                if len(row) > 12 and not pd.isna(row[12]):
                    if description:
                        description += ' - '
                    description += str(row[12])
                
                if not description:
                    continue
                
                # Определяем валюту
                currency = 'HUF' if 'huf' in file_name.lower() else 'EUR'
                
                # Определяем статью
                if any(kw in description.lower() for kw in ['service package', 'számlakivonat', 'díja']):
                    article = '1.2.17 РКО'
                elif amount < 0:
                    article = '1.2.8.1 Обслуживание объектов'
                else:
                    article = '1.1.1.3 Арендная плата'
                
                direction, subdirection = 'Europe', 'F6 Будапешт'
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Валюта': currency,
                    'Описание': description[:300],
                    'Статья': article,
                    'Направление': direction,
                    'Субнаправление': subdirection,
                    'Файл': file_name
                })
                
            except Exception as e:
                continue
        
        return transactions
        
    except Exception as e:
        st.error(f"Ошибка при парсинге MKB файла: {str(e)}")
        return []

def parse_csv_safe(file_content: bytes, file_name: str) -> pd.DataFrame:
    """Безопасный парсинг CSV"""
    try:
        # Определяем кодировку
        detected = chardet.detect(file_content[:10000])
        encoding = detected['encoding'] if detected['encoding'] else 'utf-8'
        
        # Декодируем
        try:
            content = file_content.decode(encoding)
        except:
            content = file_content.decode('utf-8', errors='ignore')
        
        # Разделяем на строки
        lines = content.split('\n')
        
        # Фильтруем пустые строки и строки с метаданными
        clean_lines = []
        skip_keywords = ['IBAN:', 'Müddət:', 'Account', 'Customer', 'Commission', 'BEZNY']
        
        for line in lines:
            if not line.strip():
                continue
            
            line_upper = line.upper()
            if any(kw in line_upper for kw in skip_keywords):
                continue
            
            clean_lines.append(line)
        
        if not clean_lines:
            return pd.DataFrame()
        
        # Пробуем разные разделители
        for delimiter in [';', ',', '\t']:
            try:
                # Пробуем с заголовками
                df = pd.read_csv(
                    io.StringIO('\n'.join(clean_lines)), 
                    sep=delimiter,
                    encoding='utf-8',
                    engine='python',
                    on_bad_lines='skip'
                )
                
                # Проверяем, есть ли разумные данные
                if len(df) > 0 and len(df.columns) > 1:
                    # Проверяем, не все ли значения - огромные числа
                    for col in df.columns[:min(3, len(df.columns))]:
                        sample = df[col].head(5).astype(str)
                        if any(re.search(r'\d{4}-\d{2}-\d{2}', str(v)) for v in sample):
                            return df
                    
                    # Если есть колонка с датами
                    for col in df.columns:
                        sample = df[col].head(5).astype(str)
                        if any(re.search(r'\d{4}-\d{2}-\d{2}', str(v)) for v in sample):
                            return df
            except:
                continue
        
        return pd.DataFrame()
        
    except Exception as e:
        return pd.DataFrame()

def parse_bank_file(file_content: bytes, file_name: str) -> List[Dict]:
    """Универсальный парсер файлов банков"""
    file_lower = file_name.lower()
    
    # Специальная обработка для MKB Budapest
    if 'budapest' in file_lower or 'mkb' in file_lower:
        return parse_mkb_budapest(file_content, file_name)
    
    transactions = []
    
    try:
        # Определяем тип файла
        if file_name.endswith(('.xlsx', '.xls')):
            # Excel файл
            try:
                df = pd.read_excel(io.BytesIO(file_content), header=0)
                if df.empty or len(df.columns) < 2:
                    df = pd.read_excel(io.BytesIO(file_content), header=None)
            except:
                df = pd.read_excel(io.BytesIO(file_content), header=None)
        else:
            # CSV/TXT файл
            df = parse_csv_safe(file_content, file_name)
        
        if df.empty:
            return []
        
        # Поиск колонок с данными
        date_col = None
        amount_col = None
        desc_col = None
        
        # Ищем колонку с датами
        for col in df.columns:
            sample = df[col].dropna().head(10)
            if len(sample) > 0:
                sample_str = sample.astype(str)
                if any(re.search(r'\d{4}-\d{2}-\d{2}', str(v)) for v in sample_str):
                    date_col = col
                    break
        
        # Ищем колонку с суммами
        for col in df.columns:
            if col == date_col:
                continue
            sample = df[col].dropna().head(10)
            if len(sample) > 0:
                # Проверяем, есть ли числа
                numeric_count = 0
                for val in sample:
                    num = parse_amount_safe(val)
                    if num != 0 and abs(num) < 1e6:  # Реалистичная сумма
                        numeric_count += 1
                if numeric_count >= 3:  # Хотя бы 3 числа в колонке
                    amount_col = col
                    break
        
        # Ищем колонку с описанием (самая длинная)
        if desc_col is None:
            max_len = 0
            for col in df.columns:
                if col not in [date_col, amount_col]:
                    try:
                        avg_len = df[col].astype(str).str.len().mean()
                        if avg_len > max_len and avg_len > 20:
                            max_len = avg_len
                            desc_col = col
                    except:
                        pass
        
        # Если не нашли колонки, используем первые
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
                
                # Проверяем валидность строки
                if not is_valid_transaction(row, date_col, amount_col):
                    continue
                
                # Получаем дату
                date_val = row[date_col]
                date = parse_dates_safe(date_val)
                if not date:
                    continue
                
                # Получаем сумму
                amount_val = row[amount_col]
                amount = parse_amount_safe(amount_val)
                
                if amount == 0:
                    continue
                
                # Получаем описание
                description = ''
                if desc_col and desc_col in df.columns and not pd.isna(row[desc_col]):
                    description = str(row[desc_col])
                
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
                
                # Определяем статью
                desc_lower = description.lower()
                
                if amount < 0:
                    if any(kw in desc_lower for kw in ['fee', 'charge', 'комиссия', 'díja']):
                        article = '1.2.17 РКО'
                    elif any(kw in desc_lower for kw in ['tax', 'налог', 'vid', 'budžets']):
                        article = '1.2.15.2 Налоги'
                    elif any(kw in desc_lower for kw in ['газ', 'gas', 'gāze']):
                        article = '1.2.10.2 Газ'
                    elif any(kw in desc_lower for kw in ['электричество', 'electricity']):
                        article = '1.2.10.5 Электричество'
                    else:
                        article = '1.2.8.1 Обслуживание объектов'
                else:
                    article = '1.1.1.3 Арендная плата'
                
                # Определяем направление
                direction, subdirection = 'Other', 'Прочее'
                
                if 'antonijas' in file_lower:
                    direction, subdirection = 'Latvia', 'AN14 Антониас 14'
                elif 'caka' in file_lower:
                    direction, subdirection = 'Latvia', 'AC89 Чака 89'
                elif 'pasha' in file_lower:
                    direction, subdirection = 'East', 'Pasha Bank'
                elif 'kapital' in file_lower:
                    direction, subdirection = 'East', 'Kapital Bank'
                elif 'mashreq' in file_lower:
                    direction, subdirection = 'Dubai', 'Mashreq Bank'
                elif 'wise' in file_lower:
                    direction, subdirection = 'Europe', 'Wise'
                elif 'paysera' in file_lower:
                    direction, subdirection = 'Other', 'Paysera'
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Валюта': currency,
                    'Описание': description[:300],
                    'Статья': article,
                    'Направление': direction,
                    'Субнаправление': subdirection,
                    'Файл': file_name
                })
                
            except Exception as e:
                continue
                
    except Exception as e:
        st.error(f"Ошибка при парсинге {file_name}: {str(e)}")
        return []
    
    return transactions

# Основной интерфейс
def main():
    st.markdown("""
    <div class="main-header">
        <h1>📊 Финансовый аналитик выписок</h1>
        <p>Автоматическая обработка банковских выписок v7.0</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("### 📌 Информация")
        st.info("""
        **Поддерживаемые форматы:**
        - Excel (.xlsx, .xls)
        - CSV, TXT
        
        **Поддерживаемые банки:**
        - MKB Budapest
        - Revolut, Paysera
        - Pasha Bank, Kapital Bank
        - Mashreq Bank, Wise
        - CSOB, UniCredit
        """)
        
        st.markdown("---")
        st.markdown("### 🎯 Особенности")
        st.markdown("""
        - ✅ Автоматическое определение колонок
        - ✅ Фильтрация служебных строк
        - ✅ Проверка реалистичности сумм
        - ✅ Поддержка нескольких валют
        - ✅ Автоматическая категоризация
        """)
    
    tab1, tab2 = st.tabs(["📄 Один файл", "📚 Несколько файлов"])
    
    with tab1:
        st.markdown("### Загрузите банковскую выписку")
        
        uploaded_file = st.file_uploader(
            "Выберите файл",
            type=['csv', 'xlsx', 'xls', 'txt'],
            key="single_file"
        )
        
        if uploaded_file:
            st.success(f"✅ Загружен: {uploaded_file.name}")
            
            if st.button("🚀 Анализировать", key="analyze_single"):
                with st.spinner("Анализируем..."):
                    file_content = uploaded_file.read()
                    transactions = parse_bank_file(file_content, uploaded_file.name)
                    
                    if transactions:
                        df = pd.DataFrame(transactions)
                        
                        st.markdown("---")
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
                        
                        st.markdown("### 📋 Транзакции")
                        st.dataframe(df, use_container_width=True, height=400)
                        
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df.to_excel(writer, sheet_name='Транзакции', index=False)
                            
                            summary = df.groupby('Статья').agg({
                                'Сумма': ['sum', 'count']
                            }).round(2)
                            summary.to_excel(writer, sheet_name='Сводка по статьям')
                        
                        output.seek(0)
                        st.download_button(
                            label="📥 Скачать Excel",
                            data=output,
                            file_name=f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            use_container_width=True
                        )
                    else:
                        st.error("❌ Не удалось обработать файл")
    
    with tab2:
        st.markdown("### Загрузите несколько выписок")
        
        uploaded_files = st.file_uploader(
            "Выберите файлы",
            type=['csv', 'xlsx', 'xls', 'txt'],
            accept_multiple_files=True,
            key="multiple_files"
        )
        
        if uploaded_files:
            st.success(f"✅ Загружено: {len(uploaded_files)} файлов")
            
            if st.button("🚀 Анализировать все", key="analyze_multiple"):
                all_transactions = []
                progress_bar = st.progress(0)
                status = st.empty()
                
                for idx, file in enumerate(uploaded_files):
                    status.text(f"Обработка: {file.name}")
                    content = file.read()
                    transactions = parse_bank_file(content, file.name)
                    all_transactions.extend(transactions)
                    progress_bar.progress((idx + 1) / len(uploaded_files))
                
                status.empty()
                
                if all_transactions:
                    df = pd.DataFrame(all_transactions)
                    
                    st.markdown("---")
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
                    
                    st.markdown("### 📋 Все транзакции")
                    st.dataframe(df, use_container_width=True, height=500)
                    
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, sheet_name='Все транзакции', index=False)
                        
                        file_summary = df.groupby('Файл').agg({
                            'Сумма': ['sum', 'count']
                        }).round(2)
                        file_summary.to_excel(writer, sheet_name='Сводка по файлам')
                        
                        article_summary = df.groupby('Статья').agg({
                            'Сумма': ['sum', 'count']
                        }).round(2)
                        article_summary.to_excel(writer, sheet_name='Сводка по статьям')
                    
                    output.seek(0)
                    st.download_button(
                        label="📥 Скачать Excel",
                        data=output,
                        file_name=f"full_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        use_container_width=True
                    )
                else:
                    st.error("❌ Не удалось обработать файлы")

if __name__ == "__main__":
    main()
