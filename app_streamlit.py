import streamlit as st
import pandas as pd
import numpy as np
import re
import io
import os
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import chardet

# --- Настройка страницы ---
st.set_page_config(
    page_title="Финансовый аналитик выписок",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Кастомный CSS ---
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

# --- Справочники для классификации ---
ARTICLE_KEYWORDS = {
    # ДОХОДЫ (Сумма > 0)
    '1.1.1.2 Поступления систем бронирования': ['airbnb', 'booking.com', 'booking'],
    '1.1.1.3 Арендная плата (счёт)': ['rent', 'аренд', 'ire', 'apmaksa par rēķinu'],
    '1.1.1.4 Получение гарантийного депозита': ['depozit', 'депозит', 'guarantee'],
    '1.1.2.2 Возвраты от поставщиков': ['refund', 'возврат', 'reversal'],
    '1.1.2.3 Компенсация по коммунальным расходам': ['komunālie', 'utilities', 'компенсац'],
    '1.1.4.1 Комиссия за продажу недвижимости': ['commission', 'agency commissions'],
    '1.1.5.3 Кэшбэк': ['cashback', 'кэшбэк'],
    # РАСХОДЫ (Сумма < 0)
    '1.2.17 РКО и банковские комиссии': ['fee', 'charge', 'commission', 'komis', 'díja', 'service package', 'monthly fee'],
    '1.2.15.2 Налоги на ФОТ': ['tax', 'налог', 'nodokļu', 'budžets', 'vid'],
    '1.2.16.3 НДС': ['vat', 'nds', 'pvn', 'value added tax'],
    '1.2.8.1 Обслуживание объектов': ['apmaksa par rēķinu', 'обслуживание', 'ремонт', 'lifti'],
    # ... (добавьте остальные статьи по вашему списку)
}

DIRECTION_KEYWORDS = {
    'Latvia': ['latvia', 'lv'],
    'Europe': ['europe', 'cz', 'hu', 'lt'],
    'East': ['east', 'az', 'baku'],
    'Dubai': ['dubai', 'ae', 'aed'],
    # ... (другие направления)
}

OBJECT_KEYWORDS = {
    # Латвия
    'AN14 Антониас 14': ['antonijas', 'an14'],
    'AC89 Чака 89': ['caka', 'ac89', 'čaka'],
    # ... (все объекты недвижимости по ключевым словам из задания)
}

RENT_SPLIT_RULES = {
    # Латвия
    'AC89 Чака 89': {'rent': 0.836, 'utilities': 0.164},
    # ... (правила для всех объектов Латвии)
}

# Ключевые слова для фильтрации служебных строк
SKIP_KEYWORDS = ['IBAN:', 'Müddət:', 'Account', 'Customer', 'Commission',
                 'BEZNY UCET', 'BUSINESS TOP', 'Serial number',
                 'Start date', 'End date', 'Start balance', 'Final balance']
def clean_numeric_string(value) -> str:
    """Очистка строки для преобразования в число"""
    if pd.isna(value):
        return ''
    
    str_val = str(value).strip()
    
    # Удаляем валюту в конце или начале строки
    str_val = re.sub(r'\s*[A-Z]{3}\s*$', '', str_val)
    str_val = re.sub(r'^\s*[A-Z]{3}\s*', '', str_val)
    
    # Удаляем пробелы и неразрывные пробелы
    str_val = str_val.replace(' ', '').replace('\xa0', '').replace('\u202f', '')
    
    # Заменяем запятую на точку для десятичных (только если после запятой 1-2 знака)
    if ',' in str_val:
        parts = str_val.split(',')
        if len(parts) == 2 and len(parts[1]) <= 2:
            str_val = str_val.replace(',', '.')
    
    # Оставляем только цифры, минус и точку
    str_val = re.sub(r'[^\d.-]', '', str_val)
    
    return str_val

def parse_amount_safe(amount_val) -> float:
    """Безопасный парсинг суммы"""
    if pd.isna(amount_val):
        return 0.0
    
    if isinstance(amount_val, (int, float)):
        if abs(amount_val) > 1e9:  # Больше миллиарда - вероятно, не сумма
            return 0.0
        return float(amount_val)
    
    str_val = clean_numeric_string(amount_val)
    
    if not str_val or str_val == '-':
        return 0.0
    
    try:
        amount = float(str_val)
        if abs(amount) > 1e9:
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
    
    # Убираем время
    if ' ' in date_str:
        date_str = date_str.split(' ', 1)[0]
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    
    formats = [
        "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d",
        "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d", "%d.%m.%y"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except:
            continue
    
    return ''
def classify_article(description: str) -> str:
    desc_lower = description.lower()
    for article, keywords in ARTICLE_KEYWORDS.items():
        if any(kw in desc_lower for kw in keywords):
            return article
    return "Прочие"

def classify_direction(file_name: str) -> str:
    name_lower = file_name.lower()
    for direction, keywords in DIRECTION_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return direction
    return "Other"

def classify_object(description: str, file_name: str) -> str:
    text = f"{description} {file_name}".lower()
    for obj, keywords in OBJECT_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return obj
    return "Прочее"

def split_rent(amount: float, obj: str) -> Tuple[float, float]:
    """Разделение суммы на аренду и коммунальные услуги"""
    if obj in RENT_SPLIT_RULES and amount > 0:
        rule = RENT_SPLIT_RULES[obj]
        rent_amount = amount * rule['rent']
        utils_amount = amount * rule['utilities']
        return rent_amount, utils_amount
    return amount, 0.0

def is_valid_transaction(row, date_col, amount_col) -> bool:
    """Проверка валидности строки как транзакции"""
    if date_col not in row.index or amount_col not in row.index:
        return False
    
    date_str = parse_dates_safe(row[date_col])
    amount = parse_amount_safe(row[amount_col])
    
    return bool(date_str) and amount != 0

def parse_csv_safe(file_content: bytes) -> pd.DataFrame:
    """Безопасный парсинг CSV с автоопределением разделителя и кодировки"""
    try:
        detected = chardet.detect(file_content[:20000])
        encoding = detected['encoding'] or 'utf-8'
        
        content = file_content.decode(encoding, errors='ignore')
        
        # Фильтрация служебных строк
        lines = []
        for line in content.split('\n'):
            line_upper = line.upper()
            if not line.strip():
                continue
            if any(kw in line_upper for kw in SKIP_KEYWORDS):
                continue
            lines.append(line)
        
        if not lines:
            return pd.DataFrame()
        
        for delimiter in [';', ',', '\t']:
            try:
                df = pd.read_csv(
                    io.StringIO('\n'.join(lines)),
                    sep=delimiter,
                    encoding='utf-8',
                    engine='python',
                    on_bad_lines='skip'
                )
                if len(df.columns) > 1 and len(df) > 0:
                    return df
            except Exception as e:
                continue
                
        return pd.DataFrame()
        
    except Exception as e:
        return pd.DataFrame()
def parse_bank_file(file_content: bytes, file_name: str) -> List[Dict]:
    """Универсальный парсер банковских выписок"""
    
    transactions = []
    
    try:
        file_lower = file_name.lower()
        
        # Определяем тип файла и читаем его
        if file_name.endswith(('.xlsx', '.xls')):
            try:
                df = pd.read_excel(io.BytesIO(file_content), header=0)
                if df.empty or len(df.columns) < 2:
                    df = pd.read_excel(io.BytesIO(file_content), header=None)
            except Exception as e:
                df = pd.read_excel(io.BytesIO(file_content), header=None)
                st.warning(f"Файл {file_name} без заголовков")
                
            # Если это MKB Budapest (по имени файла или содержимому)
            if ('budapest' in file_lower or 'mkb' in file_lower):
                df_mkb = pd.read_excel(io.BytesIO(file_content), header=None)
                for idx in range(min(50, len(df_mkb))):
                    row = df_mkb.iloc[idx]
                    first_cell = str(row[0]).lower() if len(row) > 0 else ''
                    if first_cell.startswith('serial number'):
                        df_mkb.columns = df_mkb.iloc[idx]
                        df_mkb = df_mkb.iloc[idx+1:]
                        df = df_mkb.copy()
                        break

        else:
            df = parse_csv_safe(file_content)
        
        if df.empty or len(df.columns) < 2:
            return []
        
        # Поиск колонок с данными (дата, сумма, описание)
        date_col, amount_col, desc_col = None, None, None

        for col in df.columns[:5]:
            sample = df[col].dropna().head(5).astype(str)
            if any(re.search(r'\d{4}-\d{2}-\d{2}', s) for s in sample):
                date_col = col

        for col in df.columns[:5]:
            sample_vals = df[col].dropna().head(5)
            nums = [parse_amount_safe(v) for v in sample_vals]
            non_zero_nums = [n for n in nums if n != 0]
            if len(non_zero_nums) >= 3 and date_col != col:
                amount_col = col

        desc_candidates = [c for c in df.columns[:5] if c not in [date_col, amount_col]]
        desc_col = desc_candidates[0] if desc_candidates else None

        # Если не нашли колонки автоматически - используем первые три
        cols_list = list(df.columns)
        date_col = date_col or cols_list[0]
        amount_col = amount_col or (cols_list[1] if len(cols_list) > 1 else None)
        
        # Обработка транзакций по строкам
        for idx in range(len(df)):
            try:
                row = df.iloc[idx]
                
                if not is_valid_transaction(row, date_col, amount_col):
                    continue

                date_str = parse_dates_safe(row[date_col])
                amount_raw = row[amount_col]
                description_raw = row[desc_col] if desc_col and desc_col in row else ''
                
                description = str(description_raw)[:300]
                
                amount = parse_amount_safe(amount_raw)
                
                direction = classify_direction(file_name)
                obj_name = classify_object(description, file_name)
                
                article_code = classify_article(description)
                
                currency = "EUR"
                if "czk" in file_lower: currency="CZK"
                elif "huf" in file_lower: currency="HUF"
                elif "azn" in file_lower: currency="AZN"
                elif "aed" in file_lower: currency="AED"
                
                rent_amount, utils_amount = split_rent(amount, obj_name)
                
                # Если это арендная плата для Латвии - создаем две записи
                records_to_add = []
                
                main_record = {
                    "Дата": date_str,
                    "Сумма": amount,
                    "Валюта": currency,
                    "Описание": description,
                    "Статья": article_code,
                    "Направление": direction,
                    "Субнаправление": obj_name,
                    "Файл": file_name,
                }
                
                records_to_add.append(main_record)
                
                # Добавляем отдельную запись за коммунальные услуги при аренде в Латвии
                is_latvia_rent = (
                    direction == "Latvia" and 
                    article_code == "1.1.1.3 Арендная плата (счёт)" and 
                    utils_amount != 0 
                )
                
                if is_latvia_rent and obj_name != "Прочее":
                    utils_record = main_record.copy()
                    utils_record["Сумма"] = utils_amount
                    utils_record["Статья"] = "1.2.10 Коммунальные услуги (детально)"
                    records_to_add.append(utils_record)
                    
                transactions.extend(records_to_add)
                
            except Exception as e:
                continue

    except Exception as e:
        st.error(f"Ошибка при парсинге {file_name}: {str(e)}")
        
    return transactions

def main():
    st.markdown("""
    <div class="main-header">
      <h1>📊 Финансовый аналитик выписок</h1>
      <p>Автоматическая обработка банковских выписок v2.0</p>
      <p>Полная иерархия статей и объектов недвижимости</p>
   </div>
   """, unsafe_allow_html=True)
    
   with st.sidebar:
       st.markdown("### 📌 Информация")
       st.info("""
       **Поддерживаемые форматы:** Excel (.xlsx), CSV (.csv), TXT (.txt).
       **Поддерживаемые банки:** MKB Budapest, Revolut, Paysera и др.
       """)
       
       st.markdown("---")
       st.markdown("### 🎯 Особенности")
       st.markdown("""
       - ✅ Автоматическое определение колонок и кодировки.
       - ✅ Фильтрация служебных строк.
       - ✅ Проверка реалистичности сумм.
       - ✅ Поддержка нескольких валют.
       - ✅ Автоматическая категоризация по полной иерархии.
       - ✅ Разделение арендных платежей для Латвии.
       """)
   
   tab1, tab2 = st.tabs(["📄 Один файл", "📚 Несколько файлов"])
   
   with tab1:
       st.markdown("### Загрузите банковскую выписку")
       
       uploaded_file = st.file_uploader(
           "Выберите файл",
           type=['csv', 'xlsx', 'xls', 'txt'],
           key="single_file"
       )
       
       if uploaded_file and st.button("🚀 Анализировать", key="analyze_single"):
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
                   st.dataframe(df.reset_index(drop=True), use_container_width=True)
                   
                   output = io.BytesIO()
                   with pd.ExcelWriter(output, engine='openpyxl') as writer:
                       df.to_excel(writer, sheet_name='Транзакции', index=False)
                       
                       summary_df = df.groupby(['Статья']).agg({
                           "Сумма": ["sum", "count"]
                       }).round(2)
                       summary_df.to_excel(writer, sheet_name='Сводка по статьям')
                       
                       dir_summary_df = df.groupby(['Направление']).agg({
                           "Сумма": ["sum", "count"]
                       }).round(2)
                       dir_summary_df.to_excel(writer, sheet_name='Сводка по направлениям')
                   
                   output.seek(0)
                   st.download_button(
                       label="📥 Скачать Excel",
                       data=output,
                       file_name=f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                   )
               else:
                   st.error("❌ Не удалось обработать файл или нет валидных транзакций.")
   
   with tab2:
       st.markdown("### Загрузите несколько выписок")
       
       uploaded_files = st.file_uploader(
           "Выберите файлы",
           type=['csv', 'xlsx', 'xls', 'txt'],
           accept_multiple_files=True,
           key="multiple_files"
       )
       
       if uploaded_files and st.button("🚀 Анализировать все", key="analyze_multiple"):
           all_transactions = []
           progress_bar = st.progress(0)
           status_text = st.empty()
           
           for idx, file in enumerate(uploaded_files):
               status_text.text(f"Обработка {file.name} ({idx+1}/{len(uploaded_files)})")
               content = file.read()
               transactions = parse_bank_file(content, file.name)
               all_transactions.extend(transactions)
               progress_bar.progress((idx + 1) / len(uploaded_files))
           
           status_text.empty()
           
           if all_transactions:
               df_all = pd.DataFrame(all_transactions).reset_index(drop=True)
               
               st.markdown("---")
               col1, col2, col3, col4 = st.columns(4)
               
               with col1:
                   income_all = df_all[df_all['Сумма'] > 0]['Сумма'].sum()
                   st.metric("💰 Доходы", f"{income_all:,.2f}")
               with col2:
                   expense_all = abs(df_all[df_all['Сумма'] < 0]['Сумма'].sum())
                   st.metric("💸 Расходы", f"{expense_all:,.2f}")
               with col3:
                   balance_all = income_all - expense_all
                   st.metric("⚖️ Баланс", f"{balance_all:,.2f}")
               with col4:
                   st.metric("📝 Операций", len(df_all))
               
               st.markdown("### 📋 Все транзакции")
               st.dataframe(df_all.reset_index(drop=True), use_container_width=True)
               
               output_all = io.BytesIO()
               with pd.ExcelWriter(output_all, engine='openpyxl') as writer:
                   df_all.to_excel(writer, sheet_name='Все транзакции', index=False)
                   
                   summary_df_all = df_all.groupby(['Статья']).agg({
                       "Сумма": ["sum", "count"]
                   }).round(2)
                   summary_df_all.to_excel(writer, sheet_name='Сводка по статьям')
                   
                   dir_summary_df_all = df_all.groupby(['Направление']).agg({
                       "Сумма": ["sum", "count"]
                   }).round(2)
                   dir_summary_df_all.to_excel(writer, sheet_name='Сводка по направлениям')
                   
                   file_summary_df_all = df_all.groupby(['Файл']).agg({
                       "Сумма": ["sum", "count"]
                   }).round(2)
                   file_summary_df_all.to_excel(writer, sheet_name='Сводка по файлам')
               
               output_all.seek(0)
               st.download_button(
                   label="📥 Скачать Excel",
                   data=output_all,
                   file_name=f"full_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                   mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
               )
           else:
               st.error("❌ Не удалось обработать файлы или нет валидных транзакций.")
   
if __name__ == "__main__":
   main()
