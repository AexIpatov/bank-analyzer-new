import streamlit as st
import pandas as pd
import os
import re
import tempfile
import chardet
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Tuple, Optional

st.set_page_config(page_title="Аналитик банковских выписок", page_icon="🏦", layout="wide")

st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
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

st.markdown('<div class="main-header"><h1>🏦 Аналитик банковских выписок</h1><p>Поддержка CSV, XLSX, XLS форматов</p></div>', unsafe_allow_html=True)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def detect_file_encoding(file_path: str) -> str:
    """Определяет кодировку файла"""
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)
        result = chardet.detect(raw_data)
        return result['encoding'] if result['encoding'] else 'utf-8'
    except:
        return 'utf-8'

def detect_csv_delimiter(file_path: str) -> str:
    """Определяет разделитель в CSV файле"""
    delimiters = [';', ',', '\t', '|']
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            first_line = f.readline()
        
        counts = {}
        for delim in delimiters:
            counts[delim] = first_line.count(delim)
        
        max_delim = max(counts, key=counts.get)
        return max_delim if counts[max_delim] > 0 else ';'
    except:
        return ';'

def clean_account_name(filename: str) -> str:
    """Очищает имя файла для получения наименования счета"""
    name = os.path.splitext(filename)[0]
    name = re.sub(r'\d{4}-\d{2}-\d{2}', '', name)
    name = re.sub(r'[_-]', ' ', name).strip()
    name = re.sub(r'\s+', ' ', name)
    return name if name else 'Неизвестный счет'

def parse_date(date_str: str) -> str:
    """Парсинг даты из разных форматов и возврат в формате ДД-ММ-ГГГГ"""
    if not date_str or pd.isna(date_str):
        return ''
    
    date_str = str(date_str).strip()
    
    # Если дата в формате с временем
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    
    # Если дата в формате с точкой (день.месяц.год)
    if '.' in date_str and len(date_str.split('.')) == 3:
        parts = date_str.split('.')
        try:
            day, month, year = parts
            if len(year) == 2:
                year = f"20{year}"
            return f"{day.zfill(2)}-{month.zfill(2)}-{year}"
        except:
            pass
    
    # Если дата в формате с косой чертой (месяц/день/год или день/месяц/год)
    if '/' in date_str and len(date_str.split('/')) == 3:
        parts = date_str.split('/')
        try:
            # Пробуем как ДД/ММ/ГГГГ
            if len(parts[0]) == 2 and len(parts[1]) == 2:
                day, month, year = parts
                if len(year) == 2:
                    year = f"20{year}"
                return f"{day.zfill(2)}-{month.zfill(2)}-{year}"
            # Пробуем как ММ/ДД/ГГГГ
            elif len(parts[0]) == 2 and len(parts[1]) == 2:
                month, day, year = parts
                if len(year) == 2:
                    year = f"20{year}"
                return f"{day.zfill(2)}-{month.zfill(2)}-{year}"
        except:
            pass
    
    formats = [
        "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d",
        "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d", "%d.%m.%y",
        "%d/%m/%y", "%y-%m-%d", "%d-%b-%y", "%d-%b-%Y",
        "%b %d, %Y", "%d %b %Y", "%Y%m%d"
    ]
    
    for fmt in formats:
        try:
            date_obj = datetime.strptime(date_str, fmt)
            return date_obj.strftime("%d-%m-%Y")
        except:
            continue
    
    return date_str

def parse_amount(amount_str) -> float:
    """Парсинг суммы из строки"""
    if amount_str is None or pd.isna(amount_str):
        return 0.0
    
    amount_str = str(amount_str).strip()
    
    if amount_str in ['', 'nan', '-', 'None', 'null', 'NaN', 'N/A', 'n/a', '0']:
        return 0.0
    
    # Определяем знак
    is_negative = False
    if amount_str.startswith('-'):
        is_negative = True
        amount_str = amount_str[1:]
    elif amount_str.startswith('(') and amount_str.endswith(')'):
        is_negative = True
        amount_str = amount_str[1:-1]
    
    # Удаляем валюту
    amount_str = re.sub(r'\s*[A-Z]{3}\s*$', '', amount_str)
    amount_str = re.sub(r'^\s*[A-Z]{3}\s*', '', amount_str)
    
    # Удаляем пробелы и заменяем запятую на точку
    amount_str = amount_str.replace(' ', '').replace('\xa0', '')
    amount_str = amount_str.replace(',', '.')
    
    # Оставляем только цифры, точки и минус
    amount_str = re.sub(r'[^\d.\-]', '', amount_str)
    
    if not amount_str or amount_str == '.':
        return 0.0
    
    try:
        value = float(amount_str)
        return -abs(value) if is_negative else abs(value)
    except:
        return 0.0

def format_amount(amount: float) -> str:
    """Форматирует сумму с запятой как разделителем"""
    if amount is None or pd.isna(amount):
        return "0,00"
    formatted = f"{amount:.2f}".replace('.', ',')
    if ',' in formatted:
        integer_part, decimal_part = formatted.split(',')
        integer_part = re.sub(r'(?<=\d)(?=(\d{3})+(?!\d))', ' ', integer_part)
        return f"{integer_part},{decimal_part}"
    return formatted

def find_header_row(df: pd.DataFrame) -> int:
    """Находит строку с заголовками в DataFrame"""
    header_keywords = [
        'date', 'дата', 'datum', 'posting', 'value date', 'booking date',
        'amount', 'сумма', 'volume', 'payment amount', 'total',
        'description', 'описание', 'details', 'narrative', 'message',
        'counterparty', 'контрагент', 'payee', 'payer', 'beneficiary',
        'credit', 'дебет', 'debit', 'balance', 'баланс'
    ]
    
    for idx in range(min(30, len(df))):
        row = df.iloc[idx]
        row_text = ' '.join(str(v).lower() for v in row if pd.notna(v))
        
        matches = 0
        for keyword in header_keywords:
            if keyword in row_text:
                matches += 1
        
        if matches >= 2:
            return idx
    
    return -1

def find_amount_column(df: pd.DataFrame) -> Tuple[Optional[str], bool]:
    """Находит колонку с суммой и определяет, нужно ли менять знак"""
    for col in df.columns:
        col_lower = str(col).lower()
        
        # Проверяем названия колонок
        if any(kw in col_lower for kw in ['payment amount', 'amount', 'сумма', 'volume']):
            # Проверяем, не является ли это колонкой с отрицательными числами
            sample = df[col].dropna().head(5)
            neg_count = sum(1 for x in sample if str(x).strip().startswith('-'))
            if neg_count > len(sample) / 2:
                return col, True  # сумма уже с правильным знаком
            return col, False
        
        if any(kw in col_lower for kw in ['debit', 'дебет', 'məxaric']):
            return col, True  # расходы уже отрицательные
        
        if any(kw in col_lower for kw in ['credit', 'кредит', 'mədaxil']):
            return col, False  # доходы положительные
    
    return None, False

# ==================== ПАРСЕР CSV ====================
def parse_csv(file_content: bytes, filename: str) -> List[Dict]:
    """Парсинг CSV файлов"""
    account_name = clean_account_name(filename)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        encoding = detect_file_encoding(tmp_path)
        delimiter = detect_csv_delimiter(tmp_path)
        
        # Пробуем прочитать с разными параметрами
        df = None
        for skip_rows in [0, 1, 2, 3]:
            try:
                df = pd.read_csv(
                    tmp_path,
                    sep=delimiter,
                    encoding=encoding,
                    header=None,
                    dtype=str,
                    skiprows=skip_rows,
                    on_bad_lines='skip'
                )
                if len(df) > 2:
                    break
            except:
                continue
        
        if df is None or len(df) == 0:
            return []
        
        header_row = find_header_row(df)
        
        if header_row >= 0:
            headers = [str(h).strip() if pd.notna(h) else f'col_{i}' for i, h in enumerate(df.iloc[header_row].values)]
            headers = [h if h and h != 'nan' else f'col_{i}' for i, h in enumerate(headers)]
            
            data_rows = []
            for idx in range(header_row + 1, len(df)):
                row = list(df.iloc[idx].values)
                if len(row) < len(headers):
                    row.extend([''] * (len(headers) - len(row)))
                data_rows.append(row[:len(headers)])
            
            df = pd.DataFrame(data_rows, columns=headers)
        
        return parse_generic_df(df, account_name)
                
    except Exception as e:
        st.error(f"Ошибка при парсинге CSV {filename}: {str(e)}")
        return []
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass

# ==================== ПАРСЕР EXCEL ====================
def parse_excel(file_content: bytes, filename: str) -> List[Dict]:
    """Парсинг Excel файлов"""
    account_name = clean_account_name(filename)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        # Читаем все листы
        sheets = pd.read_excel(tmp_path, sheet_name=None, header=None, dtype=str)
        
        all_transactions = []
        for sheet_name, df in sheets.items():
            # Пропускаем пустые листы
            if df.empty:
                continue
            
            # Пропускаем листы с метаданными
            if any(str(v).lower() in ['metadata', 'sheet', 'report'] for v in df.iloc[0].values if pd.notna(v)):
                continue
            
            header_row = find_header_row(df)
            
            if header_row >= 0:
                headers = [str(h).strip() if pd.notna(h) else f'col_{i}' for i, h in enumerate(df.iloc[header_row].values)]
                headers = [h if h and h != 'nan' else f'col_{i}' for i, h in enumerate(headers)]
                
                data_rows = []
                for idx in range(header_row + 1, len(df)):
                    row = list(df.iloc[idx].values)
                    if len(row) < len(headers):
                        row.extend([''] * (len(headers) - len(row)))
                    data_rows.append(row[:len(headers)])
                
                df_clean = pd.DataFrame(data_rows, columns=headers)
                transactions = parse_generic_df(df_clean, account_name)
                all_transactions.extend(transactions)
        
        return all_transactions
                
    except Exception as e:
        st.error(f"Ошибка при парсинге Excel {filename}: {str(e)}")
        return []
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass

# ==================== УНИВЕРСАЛЬНЫЙ ПАРСЕР ====================
def parse_generic_df(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """Универсальный парсер для DataFrame"""
    transactions = []
    
    # Если данных нет
    if df.empty:
        return []
    
    # Определяем колонки
    date_col = None
    amount_col = None
    desc_col = None
    counterparty_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        
        # Дата
        if any(kw in col_lower for kw in ['date', 'дата', 'datum', 'posting', 'booking date', 'value date', 'trans date']):
            if date_col is None:
                date_col = col
                continue
        
        # Сумма (ищем основные колонки)
        if any(kw in col_lower for kw in ['payment amount', 'amount', 'сумма', 'volume', 'total', 'összeg']):
            if amount_col is None:
                amount_col = col
                continue
        
        # Дебет/Кредит
        if any(kw in col_lower for kw in ['debit', 'дебет', 'məxaric']):
            if amount_col is None:
                amount_col = col
                continue
        
        if any(kw in col_lower for kw in ['credit', 'кредит', 'mədaxil']):
            if amount_col is None:
                amount_col = col
                continue
        
        # Описание
        if any(kw in col_lower for kw in ['description', 'описание', 'details', 'narrative', 'message', 'transaction details', 'note']):
            if desc_col is None:
                desc_col = col
                continue
        
        # Контрагент
        if any(kw in col_lower for kw in ['counterparty', 'контрагент', 'payee', 'payer', 'beneficiary', 'name']):
            if counterparty_col is None:
                counterparty_col = col
                continue
    
    # Если колонки не найдены, используем первые подходящие
    if date_col is None:
        for col in df.columns:
            col_lower = str(col).lower()
            if any(kw in col_lower for kw in ['date', 'дата', 'datum']):
                date_col = col
                break
        if date_col is None and len(df.columns) > 0:
            date_col = df.columns[0]
    
    if amount_col is None:
        for col in df.columns:
            col_lower = str(col).lower()
            if any(kw in col_lower for kw in ['amount', 'sum', 'volume']):
                amount_col = col
                break
        if amount_col is None and len(df.columns) > 1:
            amount_col = df.columns[1]
    
    # Если описание не найдено, используем первую свободную колонку
    if desc_col is None:
        for col in df.columns:
            if col not in [date_col, amount_col, counterparty_col]:
                desc_col = col
                break
    
    # Парсим транзакции
    for idx, row in df.iterrows():
        try:
            # Дата
            date = ''
            if date_col in row:
                val = row[date_col]
                if pd.notna(val):
                    date = parse_date(str(val))
            
            if not date:
                continue
            
            # Сумма
            amount = 0.0
            if amount_col in row:
                val = row[amount_col]
                if pd.notna(val):
                    amount = parse_amount(val)
            
            if amount == 0.0:
                # Проверяем, может быть сумма в другой колонке
                for col in df.columns:
                    if col not in [date_col, desc_col, counterparty_col]:
                        val = row[col]
                        if pd.notna(val):
                            parsed = parse_amount(val)
                            if parsed != 0:
                                amount = parsed
                                break
            
            if amount == 0.0:
                continue
            
            # Описание
            description = ''
            if desc_col in row:
                val = row[desc_col]
                if pd.notna(val):
                    description = str(val)
            
            # Контрагент
            counterparty = ''
            if counterparty_col in row:
                val = row[counterparty_col]
                if pd.notna(val):
                    counterparty = str(val)
            
            # Если описание пустое, собираем из других колонок
            if not description or len(description) < 3:
                desc_parts = []
                for col in df.columns:
                    if col not in [date_col, amount_col, counterparty_col]:
                        val = row[col]
                        if pd.notna(val) and str(val).strip():
                            desc_parts.append(str(val))
                if desc_parts:
                    description = ' '.join(desc_parts)
            
            transactions.append({
                'Дата': date,
                'Сумма': amount,
                'Контрагент': counterparty[:200] if counterparty else '',
                'Наименование счета': account_name,
                'Описание': description[:500]
            })
        except Exception as e:
            continue
    
    return transactions

# ==================== ГЛАВНАЯ ФУНКЦИЯ ПАРСИНГА ====================
def parse_file(file_content: bytes, filename: str) -> List[Dict]:
    """Основная функция парсинга файла"""
    ext = os.path.splitext(filename)[1].lower()
    
    if ext == '.csv':
        return parse_csv(file_content, filename)
    elif ext in ['.xlsx', '.xls']:
        return parse_excel(file_content, filename)
    else:
        st.warning(f"Неподдерживаемый формат файла: {filename}. Используйте CSV или Excel.")
        return []

# ==================== ИНТЕРФЕЙС ====================
def main():
    st.markdown("### 📂 Загрузите банковские выписки")
    st.markdown("Поддерживаются форматы: **CSV, XLSX, XLS**")
    
    uploaded_files = st.file_uploader(
        "Выберите файлы",
        type=['csv', 'xlsx', 'xls'],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        st.success(f"✅ Загружено файлов: {len(uploaded_files)}")
        
        if st.button("🚀 Обработать файлы"):
            all_transactions = []
            failed_files = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Обработка: {uploaded_file.name}")
                
                try:
                    content = uploaded_file.read()
                    transactions = parse_file(content, uploaded_file.name)
                    
                    if transactions:
                        all_transactions.extend(transactions)
                        st.info(f"✅ {uploaded_file.name}: {len(transactions)} операций")
                    else:
                        failed_files.append(uploaded_file.name)
                except Exception as e:
                    failed_files.append(f"{uploaded_file.name} (ошибка: {str(e)})")
                
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            status_text.text("✅ Обработка завершена!")
            
            if all_transactions:
                # Создаем DataFrame
                df = pd.DataFrame(all_transactions)
                
                # Форматируем суммы с запятой
                df['Сумма'] = df['Сумма'].apply(format_amount)
                
                # Конвертируем суммы обратно в числа для подсчета
                numeric_amounts = pd.to_numeric(
                    df['Сумма'].str.replace(',', '.').str.replace(' ', ''), 
                    errors='coerce'
                )
                
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("📊 Всего операций", len(all_transactions))
                with col2:
                    доход = numeric_amounts[numeric_amounts > 0].sum()
                    st.metric("📈 Доходы", f"{доход:,.2f}".replace('.', ','))
                with col3:
                    расход = abs(numeric_amounts[numeric_amounts < 0].sum())
                    st.metric("📉 Расходы", f"{расход:,.2f}".replace('.', ','))
                
                st.markdown("### 📋 Результат обработки")
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Транзакции', index=False)
                    
                    # Сводка по счетам
                    df_temp = df.copy()
                    df_temp['Сумма_число'] = numeric_amounts
                    
                    bank_summary = df_temp.groupby('Наименование счета').agg({
                        'Сумма_число': ['count', 'sum']
                    }).round(2)
                    bank_summary.columns = ['Количество операций', 'Сумма']
                    bank_summary['Сумма'] = bank_summary['Сумма'].apply(
                        lambda x: f"{x:,.2f}".replace('.', ',')
                    )
                    bank_summary.to_excel(writer, sheet_name='Сводка по счетам')
                
                output.seek(0)
                st.download_button(
                    label="📥 Скачать Excel",
                    data=output,
                    file_name="анализ_банковских_выписок.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            if failed_files:
                st.warning(f"⚠️ Не удалось обработать: {len(failed_files)} файлов")
                for f in failed_files:
                    st.write(f"- {f}")

if __name__ == "__main__":
    main()
