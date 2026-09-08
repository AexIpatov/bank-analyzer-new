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
    
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    
    if '.' in date_str and len(date_str.split('.')) == 3:
        parts = date_str.split('.')
        try:
            day, month, year = parts
            if len(year) == 2:
                year = f"20{year}"
            return f"{day.zfill(2)}-{month.zfill(2)}-{year}"
        except:
            pass
    
    if '/' in date_str and len(date_str.split('/')) == 3:
        parts = date_str.split('/')
        try:
            if len(parts[0]) == 2 and len(parts[1]) == 2:
                day, month, year = parts
                if len(year) == 2:
                    year = f"20{year}"
                return f"{day.zfill(2)}-{month.zfill(2)}-{year}"
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
    
    is_negative = False
    if amount_str.startswith('-'):
        is_negative = True
        amount_str = amount_str[1:]
    elif amount_str.startswith('(') and amount_str.endswith(')'):
        is_negative = True
        amount_str = amount_str[1:-1]
    
    amount_str = re.sub(r'\s*[A-Z]{3}\s*$', '', amount_str)
    amount_str = re.sub(r'^\s*[A-Z]{3}\s*', '', amount_str)
    amount_str = amount_str.replace(' ', '').replace('\xa0', '')
    amount_str = amount_str.replace(',', '.')
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

# ==================== ПАРСЕР CSOB (Чехия) ====================
def parse_csob_industra(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """Парсинг выписок CSOB / Industra с колонками Дебет(D) и Кредит(C)"""
    transactions = []
    
    # Ищем колонки
    date_col = None
    debit_col = None
    credit_col = None
    desc_col = None
    counterparty_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        if 'дата' in col_lower or 'date' in col_lower or 'datum' in col_lower:
            date_col = col
        elif 'дебет' in col_lower or 'debit' in col_lower:
            debit_col = col
        elif 'кредит' in col_lower or 'credit' in col_lower:
            credit_col = col
        elif 'информация' in col_lower or 'description' in col_lower or 'transaction' in col_lower:
            desc_col = col
        elif 'получатель' in col_lower or 'плательщик' in col_lower or 'counterparty' in col_lower:
            counterparty_col = col
    
    # Если не нашли, ищем по позициям (для Industra)
    if date_col is None:
        for col in df.columns:
            if 'дата' in str(col).lower():
                date_col = col
                break
    if debit_col is None and credit_col is None:
        # Ищем колонки с числами
        for col in df.columns:
            sample = df[col].dropna()
            if len(sample) > 0:
                sample_str = str(sample.iloc[0])
                if '-' in sample_str or any(c.isdigit() for c in sample_str):
                    if debit_col is None:
                        debit_col = col
                    elif credit_col is None:
                        credit_col = col
    
    # Если не нашли дебет/кредит, ищем по индексам (последние колонки)
    if debit_col is None and credit_col is None:
        cols = list(df.columns)
        if len(cols) >= 2:
            credit_col = cols[-1]
            debit_col = cols[-2]
    
    if date_col is None or (debit_col is None and credit_col is None):
        return []
    
    for idx, row in df.iterrows():
        try:
            # Дата
            date = ''
            if date_col in row and pd.notna(row[date_col]):
                date = parse_date(str(row[date_col]))
            
            if not date:
                continue
            
            # Сумма
            amount = 0.0
            
            # Проверяем дебет (отрицательная)
            if debit_col in row and pd.notna(row[debit_col]):
                val = str(row[debit_col]).strip()
                if val and val != '0' and val != '0.0':
                    amount = -abs(parse_amount(val))
            
            # Если в дебете 0, проверяем кредит
            if amount == 0.0 and credit_col in row and pd.notna(row[credit_col]):
                val = str(row[credit_col]).strip()
                if val and val != '0' and val != '0.0':
                    amount = abs(parse_amount(val))
            
            if amount == 0.0:
                continue
            
            # Описание
            description = ''
            if desc_col in row and pd.notna(row[desc_col]):
                description = str(row[desc_col])
            
            # Контрагент
            counterparty = ''
            if counterparty_col in row and pd.notna(row[counterparty_col]):
                counterparty = str(row[counterparty_col])
            
            if not description:
                for col in df.columns:
                    if col not in [date_col, debit_col, credit_col, counterparty_col]:
                        val = row[col]
                        if pd.notna(val) and str(val).strip():
                            description += str(val) + ' '
            
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

# ==================== ПАРСЕР КОММЕРЧЕСКИХ ВЫПИСОК ====================
def parse_generic_excel(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """Универсальный парсер для коммерческих выписок"""
    transactions = []
    
    # Ищем колонки по ключевым словам
    date_col = None
    amount_col = None
    desc_col = None
    counterparty_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        
        if any(kw in col_lower for kw in ['date', 'дата', 'datum', 'posting', 'booking']):
            if date_col is None:
                date_col = col
        elif any(kw in col_lower for kw in ['amount', 'сумма', 'volume', 'payment amount', 'total']):
            if amount_col is None:
                amount_col = col
        elif any(kw in col_lower for kw in ['description', 'описание', 'details', 'message', 'note']):
            if desc_col is None:
                desc_col = col
        elif any(kw in col_lower for kw in ['counterparty', 'контрагент', 'payee', 'payer', 'beneficiary']):
            if counterparty_col is None:
                counterparty_col = col
    
    # Если не нашли, пробуем найти по позициям
    if date_col is None and len(df.columns) > 0:
        for col in df.columns:
            sample = df[col].dropna()
            if len(sample) > 0:
                sample_str = str(sample.iloc[0])
                if re.search(r'\d{2}[./]\d{2}[./]\d{4}', sample_str):
                    date_col = col
                    break
    
    if amount_col is None:
        for col in df.columns:
            sample = df[col].dropna()
            if len(sample) > 2:
                # Проверяем, есть ли числа с минусом
                neg_count = sum(1 for x in sample if str(x).strip().startswith('-'))
                if neg_count > 0:
                    amount_col = col
                    break
    
    if date_col is None or amount_col is None:
        # Если не нашли, используем первые колонки
        if len(df.columns) >= 2:
            date_col = df.columns[0]
            amount_col = df.columns[1]
        else:
            return []
    
    for idx, row in df.iterrows():
        try:
            date = ''
            if date_col in row and pd.notna(row[date_col]):
                date = parse_date(str(row[date_col]))
            
            if not date:
                continue
            
            amount = 0.0
            if amount_col in row and pd.notna(row[amount_col]):
                amount = parse_amount(row[amount_col])
            
            if amount == 0.0:
                continue
            
            description = ''
            if desc_col in row and pd.notna(row[desc_col]):
                description = str(row[desc_col])
            
            counterparty = ''
            if counterparty_col in row and pd.notna(row[counterparty_col]):
                counterparty = str(row[counterparty_col])
            
            if not description:
                for col in df.columns:
                    if col not in [date_col, amount_col, counterparty_col]:
                        val = row[col]
                        if pd.notna(val) and str(val).strip():
                            description += str(val) + ' '
            
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
            if df.empty:
                continue
            
            # Определяем тип файла по названию листа и содержимому
            sheet_lower = str(sheet_name).lower()
            
            # Проверяем на CSOB/Industra
            is_csob = False
            for idx in range(min(10, len(df))):
                row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
                if 'дебет' in row_text or 'кредит' in row_text or 'debit' in row_text or 'credit' in row_text:
                    if 'дата' in row_text or 'date' in row_text:
                        is_csob = True
                        break
            
            if is_csob:
                # Ищем строку с заголовками
                header_row = -1
                for idx in range(min(20, len(df))):
                    row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
                    if any(kw in row_text for kw in ['дата', 'дебет', 'кредит', 'date', 'debit', 'credit']):
                        header_row = idx
                        break
                
                if header_row >= 0:
                    headers = [str(h).strip() if pd.notna(h) else f'col_{i}' for i, h in enumerate(df.iloc[header_row].values)]
                    data_rows = []
                    for idx in range(header_row + 1, len(df)):
                        row = list(df.iloc[idx].values)
                        if len(row) < len(headers):
                            row.extend([''] * (len(headers) - len(row)))
                        data_rows.append(row[:len(headers)])
                    
                    df_clean = pd.DataFrame(data_rows, columns=headers)
                    transactions = parse_csob_industra(df_clean, account_name)
                    all_transactions.extend(transactions)
                else:
                    # Если заголовки не найдены, пробуем универсальный парсер
                    transactions = parse_generic_excel(df, account_name)
                    all_transactions.extend(transactions)
            else:
                # Универсальный парсер
                transactions = parse_generic_excel(df, account_name)
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
        
        df = pd.read_csv(
            tmp_path,
            sep=delimiter,
            encoding=encoding,
            header=None,
            dtype=str,
            on_bad_lines='skip'
        )
        
        # Пробуем найти заголовки
        header_row = -1
        for idx in range(min(30, len(df))):
            row_text = ' '.join(str(v).lower() for v in df.iloc[idx].values if pd.notna(v))
            if any(kw in row_text for kw in ['date', 'дата', 'amount', 'сумма', 'volume']):
                if any(kw in row_text for kw in ['description', 'описание', 'message']):
                    header_row = idx
                    break
        
        if header_row >= 0:
            headers = [str(h).strip() if pd.notna(h) else f'col_{i}' for i, h in enumerate(df.iloc[header_row].values)]
            data_rows = []
            for idx in range(header_row + 1, len(df)):
                row = list(df.iloc[idx].values)
                if len(row) < len(headers):
                    row.extend([''] * (len(headers) - len(row)))
                data_rows.append(row[:len(headers)])
            
            df = pd.DataFrame(data_rows, columns=headers)
        
        return parse_generic_excel(df, account_name)
                
    except Exception as e:
        st.error(f"Ошибка при парсинге CSV {filename}: {str(e)}")
        return []
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass

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
                df = pd.DataFrame(all_transactions)
                df['Сумма'] = df['Сумма'].apply(format_amount)
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
