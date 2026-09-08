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

# ==================== СПРАВОЧНИК БАНКОВ ====================
BANK_REFERENCE = {
    'csob': {'name': 'ČSOB', 'country': 'Czech Republic', 'currency': 'CZK'},
    'čsob': {'name': 'ČSOB', 'country': 'Czech Republic', 'currency': 'CZK'},
    'unicredit': {'name': 'UniCredit Bank', 'country': 'Czech Republic', 'currency': 'CZK'},
    'uni credit': {'name': 'UniCredit Bank', 'country': 'Czech Republic', 'currency': 'CZK'},
    'industra': {'name': 'Industra Bank', 'country': 'Latvia', 'currency': 'EUR'},
    'revolut': {'name': 'Revolut', 'country': 'UK', 'currency': 'EUR'},
    'paysera': {'name': 'Paysera', 'country': 'Lithuania', 'currency': 'EUR'},
    'budapest': {'name': 'MKB Bank', 'country': 'Hungary', 'currency': 'HUF'},
    'mkb': {'name': 'MKB Bank', 'country': 'Hungary', 'currency': 'HUF'},
    'pasha': {'name': 'Pasha Bank', 'country': 'Azerbaijan', 'currency': 'AZN'},
    'kapital': {'name': 'Kapital Bank', 'country': 'Azerbaijan', 'currency': 'AZN'},
    'bunda': {'name': 'Pasha Bank', 'country': 'Azerbaijan', 'currency': 'AED'},
    'mashreq': {'name': 'Mashreq Bank', 'country': 'UAE', 'currency': 'AED'},
    'wio': {'name': 'WIO Bank', 'country': 'UAE', 'currency': 'AED'},
    'tinkoff': {'name': 'Тинькофф', 'country': 'Russia', 'currency': 'RUB'},
}

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def detect_file_type(filename: str) -> str:
    """Определяет тип банка по имени файла"""
    filename_lower = filename.lower()
    
    bank_patterns = {
        'csob': ['csob', 'čsob', 'dzibik', 'koruna', 'strojka', 'ostrava'],
        'unicredit': ['unicredit', 'uni credit', 'garpiz'],
        'industra': ['industra', 'plavas'],
        'revolut': ['revolut'],
        'paysera': ['paysera', 'bs property', 'bs rerum'],
        'budapest': ['budapest', 'mkb'],
        'pasha': ['pasha', 'bunda'],
        'kapital': ['kapital', 'saida'],
        'mashreq': ['mashreq'],
        'tinkoff': ['tinkoff'],
    }
    
    for bank_type, patterns in bank_patterns.items():
        for pattern in patterns:
            if pattern in filename_lower:
                return bank_type
    
    return 'unknown'

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

def get_bank_name(filename: str) -> str:
    """Получает наименование банка из справочника"""
    file_lower = filename.lower()
    
    for key, info in BANK_REFERENCE.items():
        if key in file_lower:
            return info['name']
    
    return 'Неизвестный банк'

def parse_date(date_str: str) -> str:
    """Парсинг даты из разных форматов"""
    if not date_str or pd.isna(date_str):
        return ''
    
    date_str = str(date_str).strip()
    
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    
    formats = [
        "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d",
        "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d", "%d.%m.%y",
        "%d/%m/%y", "%y-%m-%d", "%d-%b-%y", "%d-%b-%Y",
        "%b %d, %Y", "%d %b %Y", "%Y%m%d"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except:
            continue
    
    if '.' in date_str:
        parts = date_str.split('.')
        if len(parts) == 3:
            day, month, year = parts
            if len(year) == 2:
                year = f"20{year}"
            try:
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            except:
                pass
    
    return date_str

def parse_amount(amount_str: str) -> float:
    """Парсинг суммы из строки"""
    if not amount_str or pd.isna(amount_str):
        return 0.0
    
    amount_str = str(amount_str).strip()
    
    if amount_str in ['', 'nan', '-', 'None', 'null', 'NaN', 'N/A', 'n/a']:
        return 0.0
    
    is_negative = False
    if amount_str.startswith('-'):
        is_negative = True
        amount_str = amount_str[1:]
    elif amount_str.startswith('-+'):
        is_negative = True
        amount_str = amount_str[2:]
    
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

def find_header_row(df: pd.DataFrame) -> int:
    """Находит строку с заголовками в DataFrame"""
    header_keywords = [
        'date', 'дата', 'datum', 'posting date', 'value date',
        'amount', 'сумма', 'payment amount',
        'description', 'описание', 'transaction details',
        'counterparty', 'контрагент', 'payee',
        'account number', 'balance'
    ]
    
    for idx in range(min(20, len(df))):
        row = df.iloc[idx]
        row_text = ' '.join(str(v).lower() for v in row if pd.notna(v))
        
        matches = 0
        for keyword in header_keywords:
            if keyword in row_text:
                matches += 1
        
        if matches >= 3:
            return idx
    
    return -1

# ==================== ПАРСЕР CSV ====================
def parse_csv(file_content: bytes, filename: str) -> List[Dict]:
    """Парсинг CSV файлов"""
    account_name = clean_account_name(filename)
    bank_name = get_bank_name(filename)
    
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
        
        header_row = find_header_row(df)
        
        if header_row >= 0:
            headers = [str(h).strip() for h in df.iloc[header_row].values]
            headers = [f'col_{i}' if pd.isna(h) or h == '' else h for i, h in enumerate(headers)]
            
            data_rows = []
            for idx in range(header_row + 1, len(df)):
                row = list(df.iloc[idx].values)
                if len(row) < len(headers):
                    row.extend([''] * (len(headers) - len(row)))
                data_rows.append(row[:len(headers)])
            
            df = pd.DataFrame(data_rows, columns=headers)
        
        return parse_generic_df(df, account_name, bank_name)
                
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
    bank_name = get_bank_name(filename)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        df = pd.read_excel(tmp_path, header=None, dtype=str)
        
        header_row = find_header_row(df)
        
        if header_row >= 0:
            headers = [str(h).strip() for h in df.iloc[header_row].values]
            headers = [f'col_{i}' if pd.isna(h) or h == '' else h for i, h in enumerate(headers)]
            
            data_rows = []
            for idx in range(header_row + 1, len(df)):
                row = list(df.iloc[idx].values)
                if len(row) < len(headers):
                    row.extend([''] * (len(headers) - len(row)))
                data_rows.append(row[:len(headers)])
            
            df = pd.DataFrame(data_rows, columns=headers)
        
        return parse_generic_df(df, account_name, bank_name)
                
    except Exception as e:
        st.error(f"Ошибка при парсинге Excel {filename}: {str(e)}")
        return []
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass

# ==================== УНИВЕРСАЛЬНЫЙ ПАРСЕР ====================
def parse_generic_df(df: pd.DataFrame, account_name: str, bank_name: str) -> List[Dict]:
    """Универсальный парсер для DataFrame"""
    transactions = []
    
    date_col = None
    amount_col = None
    desc_col = None
    counterparty_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in ['date', 'дата', 'datum', 'posting', 'value date']):
            if date_col is None:
                date_col = col
        elif any(kw in col_lower for kw in ['amount', 'сумма', 'payment amount']):
            if amount_col is None:
                amount_col = col
        elif any(kw in col_lower for kw in ['description', 'описание', 'details', 'narrative']):
            if desc_col is None:
                desc_col = col
        elif any(kw in col_lower for kw in ['counterparty', 'контрагент', 'payer', 'payee', 'name']):
            if counterparty_col is None:
                counterparty_col = col
        elif any(kw in col_lower for kw in ['debit', 'дебет', 'credit', 'кредит']):
            if amount_col is None:
                amount_col = col
    
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]
    if amount_col is None and len(df.columns) > 1:
        amount_col = df.columns[1]
    
    for idx, row in df.iterrows():
        try:
            date = ''
            if date_col in row:
                date = parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
            
            if not date:
                continue
            
            amount = 0
            if amount_col in row:
                amount = parse_amount(str(row[amount_col])) if pd.notna(row[amount_col]) else 0
            
            if amount == 0:
                continue
            
            description = ''
            if desc_col in row:
                description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
            
            counterparty = ''
            if counterparty_col in row:
                counterparty = str(row[counterparty_col]) if pd.notna(row[counterparty_col]) else ''
            
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
                'Наименование банка': bank_name,
                'Направление': 'Расход' if amount < 0 else 'Доход',
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
                df = pd.DataFrame(all_transactions)
                
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("📊 Всего операций", len(all_transactions))
                with col2:
                    доход = df[df['Сумма'] > 0]['Сумма'].sum()
                    st.metric("📈 Доходы", f"{доход:,.2f}")
                with col3:
                    расход = abs(df[df['Сумма'] < 0]['Сумма'].sum())
                    st.metric("📉 Расходы", f"{расход:,.2f}")
                
                st.markdown("### 📋 Результат обработки")
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Транзакции', index=False)
                    
                    # Сводка по счетам
                    bank_summary = df.groupby('Наименование счета').agg({
                        'Сумма': ['count', 'sum']
                    }).round(2)
                    bank_summary.columns = ['Количество операций', 'Сумма']
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
