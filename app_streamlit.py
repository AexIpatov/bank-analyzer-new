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

def parse_dates(date_val) -> str:
    """Парсинг даты из различных форматов"""
    if pd.isna(date_val):
        return ''
    
    if isinstance(date_val, (datetime, pd.Timestamp)):
        return date_val.strftime("%Y-%m-%d")
    
    date_str = str(date_val).strip()
    
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    
    # Пробуем разные форматы
    formats = [
        "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d",
        "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d", "%d.%m.%y"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except:
            continue
    
    return date_str

def parse_amount(amount_val) -> float:
    """Парсинг суммы"""
    if pd.isna(amount_val):
        return 0.0
    
    if isinstance(amount_val, (int, float)):
        return float(amount_val)
    
    amount_str = str(amount_val).strip()
    if amount_str in ['', 'nan', 'NaN', 'None', '-']:
        return 0.0
    
    # Сохраняем знак
    is_negative = amount_str.startswith('-')
    if is_negative:
        amount_str = amount_str[1:]
    
    # Удаляем валюту и пробелы
    amount_str = re.sub(r'\s*[A-Z]{3}\s*$', '', amount_str)
    amount_str = amount_str.replace(' ', '').replace('\xa0', '').replace('\u202f', '')
    
    # Заменяем запятую на точку (европейский формат)
    if ',' in amount_str:
        amount_str = amount_str.replace(',', '.')
    
    # Очищаем от всего кроме цифр, минуса и точки
    amount_str = re.sub(r'[^\d.-]', '', amount_str)
    
    if not amount_str:
        return 0.0
    
    try:
        amount = float(amount_str)
        return -amount if is_negative else amount
    except:
        return 0.0

def get_article(description: str, amount: float) -> str:
    """Определение статьи"""
    desc_lower = description.lower()
    
    if amount < 0:
        if any(kw in desc_lower for kw in ['fee', 'charge', 'service', 'díja', 'komis']):
            return '1.2.17 РКО'
        if any(kw in desc_lower for kw in ['tax', 'налог', 'vid', 'budžets']):
            return '1.2.15.2 Налоги'
        if any(kw in desc_lower for kw in ['газ', 'gas', 'gāze']):
            return '1.2.10.2 Газ'
        if any(kw in desc_lower for kw in ['электричество', 'electricity', 'elektri']):
            return '1.2.10.5 Электричество'
        if any(kw in desc_lower for kw in ['вода', 'water', 'ūdens']):
            return '1.2.10.3 Вода'
        return '1.2.8.1 Обслуживание объектов'
    else:
        if any(kw in desc_lower for kw in ['rent', 'аренд', 'money added', 'from']):
            return '1.1.1.3 Арендная плата'
        return '1.1.1.3 Арендная плата'

def get_direction(description: str, file_name: str) -> Tuple[str, str]:
    """Определение направления"""
    file_lower = file_name.lower()
    
    if 'budapest' in file_lower or 'mkb' in file_lower:
        return 'Europe', 'F6 Будапешт'
    if 'antonijas' in file_lower:
        return 'Latvia', 'AN14 Антониас 14'
    if 'caka' in file_lower:
        return 'Latvia', 'AC89 Чака 89'
    if 'pasha' in file_lower:
        return 'East', 'Pasha Bank'
    if 'kapital' in file_lower:
        return 'East', 'Kapital Bank'
    if 'mashreq' in file_lower:
        return 'Dubai', 'Mashreq Bank'
    if 'wise' in file_lower:
        return 'Europe', 'Wise'
    
    return 'Other', 'Прочее'

def parse_mkb_budapest(file_content: bytes, file_name: str) -> List[Dict]:
    """Специальный парсер для MKB Budapest выписок"""
    transactions = []
    
    try:
        # Читаем Excel файл без заголовков
        df = pd.read_excel(io.BytesIO(file_content), header=None)
        
        if df.empty:
            return []
        
        # Ищем строку с данными (не заголовки)
        # В MKB файле данные начинаются после строки с "Serial number"
        data_start_row = -1
        for idx in range(min(20, len(df))):
            row = df.iloc[idx]
            # Ищем строку с Serial number
            first_cell = str(row[0]).lower() if len(row) > 0 else ''
            if 'serial number' in first_cell:
                data_start_row = idx + 1
                break
        
        if data_start_row == -1:
            # Если не нашли, пробуем искать по первому числовому значению
            for idx in range(min(20, len(df))):
                row = df.iloc[idx]
                if len(row) > 0 and not pd.isna(row[0]):
                    try:
                        # Пробуем преобразовать в число
                        float(str(row[0]).strip())
                        data_start_row = idx
                        break
                    except:
                        continue
        
        if data_start_row == -1:
            return []
        
        # Определяем индексы колонок по первой строке данных
        sample_row = df.iloc[data_start_row]
        
        date_idx = None
        amount_idx = None
        desc_idx = None
        
        # В MKB файле:
        # Колонка 1 - Serial number (дата в формате YYYY-MM-DD)
        # Колонка 2 - Value date
        # Колонка 11 - Transaction type (описание)
        # Колонка 9 - Amount (сумма)
        
        date_idx = 1  # Value date
        amount_idx = 9  # Amount
        desc_idx = 11  # Transaction type
        
        # Проверяем, что индексы существуют
        if amount_idx >= len(sample_row):
            # Пробуем найти Amount по содержимому
            for idx in range(len(sample_row)):
                val = sample_row[idx]
                if not pd.isna(val):
                    val_str = str(val)
                    if re.search(r'-?\d+', val_str) and 'HUF' in val_str:
                        amount_idx = idx
                        break
        
        # Обрабатываем строки
        for idx in range(data_start_row, len(df)):
            try:
                row = df.iloc[idx]
                
                # Пропускаем пустые строки
                if all(pd.isna(cell) or str(cell).strip() == '' for cell in row):
                    continue
                
                # Получаем дату
                if date_idx is None or date_idx >= len(row):
                    continue
                    
                date_val = row[date_idx]
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
                
                # Добавляем Narrative если есть
                if len(row) > 12 and not pd.isna(row[12]):
                    description += ' - ' + str(row[12])
                
                # Определяем статью и направление
                article = get_article(description, amount)
                direction, subdirection = get_direction(description, file_name)
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Валюта': 'HUF',
                    'Описание': description[:500],
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
    """Безопасный парсинг CSV с автоматическим определением разделителя"""
    try:
        # Определяем кодировку
        detected = chardet.detect(file_content[:10000])
        encoding = detected['encoding'] if detected['encoding'] else 'utf-8'
        
        # Декодируем
        try:
            content = file_content.decode(encoding)
        except:
            content = file_content.decode('utf-8', errors='ignore')
        
        # Пробуем разные разделители
        for delimiter in [';', ',', '\t', '|']:
            try:
                # Пробуем прочитать с этим разделителем
                df = pd.read_csv(
                    io.StringIO(content), 
                    sep=delimiter,
                    encoding='utf-8',
                    engine='python',
                    on_bad_lines='skip',
                    header=0
                )
                
                # Проверяем, что получили разумное количество колонок
                if len(df.columns) > 1 and len(df) > 0:
                    return df
            except:
                continue
        
        # Если ничего не помогло, читаем без заголовков
        for delimiter in [';', ',', '\t', '|']:
            try:
                df = pd.read_csv(
                    io.StringIO(content), 
                    sep=delimiter,
                    encoding='utf-8',
                    engine='python',
                    on_bad_lines='skip',
                    header=None
                )
                if len(df.columns) > 1 and len(df) > 0:
                    return df
            except:
                continue
        
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Ошибка при парсинге CSV {file_name}: {str(e)}")
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
            df = pd.read_excel(io.BytesIO(file_content), header=0)
            if df.empty:
                df = pd.read_excel(io.BytesIO(file_content), header=None)
        else:
            # CSV/TXT файл
            df = parse_csv_safe(file_content, file_name)
        
        if df.empty:
            return []
        
        # Поиск колонок
        date_col = None
        amount_col = None
        desc_col = None
        
        for col in df.columns:
            col_str = str(col).lower()
            
            if 'date' in col_str or 'дата' in col_str or 'value date' in col_str:
                date_col = col
            elif 'amount' in col_str or 'сумма' in col_str or 'total' in col_str:
                amount_col = col
            elif 'description' in col_str or 'описание' in col_str or 'narrative' in col_str or 'purpose' in col_str:
                desc_col = col
        
        # Если не нашли по имени, ищем по содержимому
        if date_col is None:
            for col in df.columns:
                sample = df[col].dropna().head(5)
                if len(sample) > 0:
                    sample_str = sample.astype(str)
                    if any(re.search(r'\d{4}-\d{2}-\d{2}', str(v)) for v in sample_str):
                        date_col = col
                        break
        
        if amount_col is None:
            for col in df.columns:
                sample = df[col].dropna().head(5)
                if len(sample) > 0:
                    sample_str = sample.astype(str)
                    if any(re.search(r'-?\d+[.,]?\d*', str(v)) for v in sample_str):
                        amount_col = col
                        break
        
        if desc_col is None and len(df.columns) > 2:
            # Используем колонку с самым длинным текстом
            max_len = 0
            for col in df.columns:
                if col not in [date_col, amount_col]:
                    try:
                        avg_len = df[col].astype(str).str.len().mean()
                        if avg_len > max_len:
                            max_len = avg_len
                            desc_col = col
                    except:
                        pass
        
        # Если все еще не нашли, используем первые колонки
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
                
                # Пропускаем строки с метаданными
                first_cell = str(row.iloc[0]).lower() if len(row) > 0 else ''
                if first_cell in ['iban:', 'müddət:', 'account', 'customer', 'commission']:
                    continue
                
                # Получаем дату
                if date_col not in df.columns:
                    continue
                    
                date_val = row[date_col]
                if pd.isna(date_val):
                    continue
                
                date = parse_dates(date_val)
                if not date:
                    continue
                
                # Получаем сумму
                if amount_col not in df.columns:
                    continue
                    
                amount_val = row[amount_col]
                amount = parse_amount(amount_val)
                
                if amount == 0:
                    continue
                
                # Получаем описание
                description = ''
                if desc_col and desc_col in df.columns and not pd.isna(row[desc_col]):
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
    st.markdown("""
    <div class="main-header">
        <h1>📊 Финансовый аналитик выписок</h1>
        <p style="margin:0; opacity:0.9;">Автоматическая обработка банковских выписок</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("### 📌 Информация")
        st.info("""
        **Поддерживаемые форматы:**
        - Excel (.xlsx, .xls)
        - CSV, TXT
        
        **Поддерживаемые банки:**
        - MKB Budapest (специальный парсер)
        - Revolut, Paysera
        - Pasha Bank, Kapital Bank
        - Mashreq Bank, Wise
        - CSOB, UniCredit, Industra
        """)
        
        st.markdown("---")
        st.markdown("### 🔧 Особенности")
        st.markdown("""
        - ✅ Автоматическое определение кодировки
        - ✅ Умный поиск колонок
        - ✅ Поддержка нескольких валют
        - ✅ Автоматическая категоризация
        - ✅ Обработка ошибок CSV
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
            st.success(f"✅ Загружен файл: {uploaded_file.name}")
            
            if st.button("🚀 Анализировать", key="analyze_single", use_container_width=True):
                with st.spinner("Анализируем выписку..."):
                    file_content = uploaded_file.read()
                    transactions = parse_bank_file(file_content, uploaded_file.name)
                    
                    if transactions:
                        df = pd.DataFrame(transactions)
                        
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
                        
                        st.markdown("### 📋 Детализация операций")
                        
                        display_df = df.copy()
                        display_df['Сумма'] = display_df['Сумма'].apply(lambda x: f"{x:,.2f}")
                        
                        st.dataframe(display_df, use_container_width=True, height=400)
                        
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df.to_excel(writer, sheet_name='Транзакции', index=False)
                            
                            summary = df.groupby('Статья').agg({
                                'Сумма': ['sum', 'count']
                            }).round(2)
                            summary.to_excel(writer, sheet_name='Сводка по статьям')
                            
                            direction_summary = df.groupby(['Направление', 'Субнаправление']).agg({
                                'Сумма': 'sum'
                            }).round(2)
                            direction_summary.to_excel(writer, sheet_name='Сводка по объектам')
                        
                        output.seek(0)
                        
                        st.download_button(
                            label="📥 Скачать отчет (Excel)",
                            data=output,
                            file_name=f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                        
                    else:
                        st.error("❌ Не удалось обработать файл. Проверьте формат.")
    
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
                    
                    st.markdown("### 📋 Все операции")
                    
                    display_df = df.copy()
                    display_df['Сумма'] = display_df['Сумма'].apply(lambda x: f"{x:,.2f}")
                    
                    st.dataframe(display_df, use_container_width=True, height=500)
                    
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
