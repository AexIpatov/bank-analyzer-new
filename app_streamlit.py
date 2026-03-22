import streamlit as st
import pandas as pd
import io
import tempfile
import os
import chardet
import re
from datetime import datetime

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
            
            # Специальная обработка для UniCredit файлов (Garpiz, Koruna)
            name_lower = file_name.lower()
            if 'garpiz' in name_lower or 'koruna' in name_lower or 'twohills' in name_lower:
                # Для UniCredit файлов используем разделитель ';' и пропускаем первые строки
                try:
                    df = pd.read_csv(tmp_path, sep=';', encoding=encoding, on_bad_lines='skip', skiprows=1)
                    if len(df.columns) <= 1:
                        df = pd.read_csv(tmp_path, sep=';', encoding='latin1', on_bad_lines='skip', skiprows=1)
                except:
                    df = pd.read_csv(tmp_path, sep=';', encoding='latin1', on_bad_lines='skip', skiprows=1)
            else:
                for sep in [';', ',']:
                    try:
                        df = pd.read_csv(tmp_path, sep=sep, encoding=encoding, on_bad_lines='skip')
                        if len(df.columns) > 1:
                            break
                    except:
                        continue
                if len(df.columns) <= 1:
                    df = pd.read_csv(tmp_path, sep=';', encoding='latin1', on_bad_lines='skip')
    except Exception as e:
        os.unlink(tmp_path)
        raise e
    os.unlink(tmp_path)
    return df

def parse_date(date_str):
    if pd.isna(date_str):
        return ''
    date_str = str(date_str)
    if '.' in date_str:
        parts = date_str.split('.')
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]
    if '-' in date_str and len(date_str) >= 10:
        return date_str[:10]
    return date_str[:10] if len(date_str) >= 10 else date_str

def parse_amount(amount_str):
    if pd.isna(amount_str):
        return 0
    amount_str = str(amount_str).strip()
    if amount_str == '' or amount_str == 'nan':
        return 0
    amount_str = amount_str.replace(',', '.')
    amount_str = amount_str.replace(' ', '')
    try:
        return float(amount_str)
    except:
        match = re.search(r'(-?\d+\.?\d*)', amount_str)
        if match:
            try:
                return float(match.group(1))
            except:
                return 0
        return 0

def find_header_row(df, file_name):
    """Ищет строку с заголовками данных"""
    header_keywords = [
        'Дата транзакции', 'Date', 'Datum', 'Booking Date', 'Value Date',
        'From Account', 'Amount', 'Transaction Details', 'Əməliyyat tarixi',
        'account number', 'posting date', 'payment amount', 'Type', 'Date and time',
        'Account Title', 'From Account', 'Amount'
    ]
    
    for idx, row in df.iterrows():
        row_text = ' '.join(str(v) for v in row.values if pd.notna(v))
        for keyword in header_keywords:
            if keyword.lower() in row_text.lower():
                return idx
    return None

def parse_file(file_content, file_name):
    df = read_file(file_content, file_name)
    if df is None:
        st.error("❌ Не удалось прочитать файл")
        return []
    
    st.write(f"=== ОТЛАДКА: файл {file_name} ===")
    st.write(f"Столбцы в файле: {list(df.columns)}")
    st.write(f"Количество строк: {len(df)}")
    
    # Специальная обработка для UniCredit файлов (Garpiz, Koruna, TwoHills)
    name_lower = file_name.lower()
    if 'garpiz' in name_lower or 'koruna' in name_lower or 'twohills' in name_lower:
        # Для UniCredit файлов данные начинаются после строки с "From Account"
        header_row = None
        for idx, row in df.iterrows():
            row_text = ' '.join(str(v) for v in row.values if pd.notna(v))
            if 'From Account' in row_text:
                header_row = idx
                st.write(f"Найдена строка UniCredit с заголовками на индексе {idx}")
                break
        
        if header_row is not None:
            df.columns = df.iloc[header_row]
            df = df.iloc[header_row + 1:].reset_index(drop=True)
            st.write(f"Столбцы после переопределения: {list(df.columns)}")
            st.write(f"Количество строк после: {len(df)}")
        else:
            # Если не нашли "From Account", пробуем найти другие заголовки
            for idx, row in df.iterrows():
                row_text = ' '.join(str(v) for v in row.values if pd.notna(v))
                if 'Booking Date' in row_text or 'Amount' in row_text:
                    header_row = idx
                    st.write(f"Найдены альтернативные заголовки на индексе {idx}")
                    break
            
            if header_row is not None:
                df.columns = df.iloc[header_row]
                df = df.iloc[header_row + 1:].reset_index(drop=True)
                st.write(f"Столбцы после переопределения: {list(df.columns)}")
                st.write(f"Количество строк после: {len(df)}")
    
    # Общий поиск заголовков (если ещё не нашли)
    if len(df.columns) <= 5 or len(df) > 0:
        header_row = find_header_row(df, file_name)
        if header_row is not None and header_row > 0:
            df.columns = df.iloc[header_row]
            df = df.iloc[header_row + 1:].reset_index(drop=True)
            st.write(f"Найдены общие заголовки на строке {header_row}")
            st.write(f"Столбцы после переопределения: {list(df.columns)}")
            st.write(f"Количество строк после: {len(df)}")
    
    # Показываем первые строки для отладки
    st.write("Первые 5 строк после обработки заголовков:")
    for i in range(min(5, len(df))):
        st.write(f"Строка {i}: {df.iloc[i].to_dict()}")
    
    # Поиск столбцов
    date_col = None
    amount_col = None
    debit_col = None
    credit_col = None
    income_col = None
    expense_col = None
    
    # Приоритетные названия для даты
    date_priority = ['booking date', 'posting date', 'value date', 'date', 'дата транзакции', 'Date and time']
    for col in df.columns:
        col_lower = str(col).lower()
        for priority in date_priority:
            if priority in col_lower:
                date_col = col
                st.write(f"Найден столбец даты: {date_col}")
                break
        if date_col:
            break
    
    # Приоритетные названия для суммы
    amount_priority = ['amount', 'payment amount', 'сумма', 'məxaric', 'mədaxil', 'debit', 'credit', 'Amount and currency']
    for col in df.columns:
        col_lower = str(col).lower()
        for priority in amount_priority:
            if priority in col_lower:
                amount_col = col
                st.write(f"Найден столбец суммы: {amount_col}")
                break
        if amount_col:
            break
    
    # Дебет/Кредит
    for col in df.columns:
        col_lower = str(col).lower()
        if 'дебет' in col_lower or 'debit' in col_lower:
            debit_col = col
        if 'кредит' in col_lower or 'credit' in col_lower:
            credit_col = col
        if 'mədaxil' in col_lower:
            income_col = col
        if 'məxaric' in col_lower:
            expense_col = col
    
    st.write(f"Итоговый столбец даты: {date_col}")
    st.write(f"Итоговый столбец суммы: {amount_col}")
    
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]
        st.write(f"Используем первый столбец как дату: {date_col}")
    
    # Обработка транзакций
    transactions = []
    for idx, row in df.iterrows():
        try:
            if date_col and pd.notna(row[date_col]):
                date = parse_date(row[date_col])
            else:
                continue
            
            amount = 0
            if amount_col and pd.notna(row[amount_col]):
                amount = parse_amount(row[amount_col])
            elif debit_col and pd.notna(row[debit_col]) and row[debit_col] != 0:
                amount = -parse_amount(row[debit_col])
            elif credit_col and pd.notna(row[credit_col]) and row[credit_col] != 0:
                amount = parse_amount(row[credit_col])
            elif income_col and pd.notna(row[income_col]) and row[income_col] != 0:
                amount = parse_amount(row[income_col])
            elif expense_col and pd.notna(row[expense_col]) and row[expense_col] != 0:
                amount = -parse_amount(row[expense_col])
            
            if amount == 0:
                continue
            
            description = ''
            desc_cols = ['message to beneficiary and payer', 'transaction type', 'Description', 
                        'Təyinat', 'Информация о транзакции', 'Transaction Details', 'Purpose of payment']
            for col in desc_cols:
                if col in df.columns and pd.notna(row[col]):
                    description = str(row[col])
                    break
            if not description:
                for col in df.columns:
                    if col not in [date_col, amount_col, debit_col, credit_col, income_col, expense_col]:
                        val = str(row[col]) if pd.notna(row[col]) else ''
                        if val and val != 'nan':
                            description += val + ' '
            
            desc_lower = description.lower()
            
            # Определение статьи
            if any(kw in desc_lower for kw in ['комиссия', 'commission', 'fee', 'charge', 'maintenance', 'rko']):
                if amount > 0:
                    amount = -amount
                article = '1.2.17 РКО'
                direction = 'Расходы'
                subdir = 'Банковские комиссии'
            elif any(kw in desc_lower for kw in ['арендн', 'rent', 'money added', 'from', 'ire', 'dzivoklis']):
                article = '1.1.1.1 Арендная плата'
                direction = 'Доходы'
                subdir = 'Арендная плата'
            elif any(kw in desc_lower for kw in ['зарплат', 'salary', 'darba alga']):
                if amount > 0:
                    amount = -amount
                article = '1.2.15.1 Зарплата'
                direction = 'Расходы'
                subdir = 'Зарплата'
            elif any(kw in desc_lower for kw in ['налог', 'vid', 'budžets', 'nodokļu']):
                if amount > 0:
                    amount = -amount
                article = '1.2.16 Налоги'
                direction = 'Расходы'
                subdir = 'Налоги'
            elif any(kw in desc_lower for kw in ['latvenergo']):
                if amount > 0:
                    amount = -amount
                article = '1.2.10.5 Электричество'
                direction = 'Расходы'
                subdir = 'Электричество'
            elif any(kw in desc_lower for kw in ['rigas udens', 'ūdens']):
                if amount > 0:
                    amount = -amount
                article = '1.2.10.3 Вода'
                direction = 'Расходы'
                subdir = 'Вода'
            elif any(kw in desc_lower for kw in ['balta']):
                if amount > 0:
                    amount = -amount
                article = '1.2.8.2 Страхование'
                direction = 'Расходы'
                subdir = 'Страхование'
            elif any(kw in desc_lower for kw in ['airbnb', 'booking']):
                article = '1.1.1.2 Поступления систем бронирования'
                direction = 'Доходы'
                subdir = 'Краткосрочная аренда'
            else:
                if amount > 0:
                    article = '1.1.1.1 Арендная плата'
                    direction = 'Доходы'
                    subdir = 'Арендная плата'
                else:
                    article = '1.2.8.1 Обслуживание объектов'
                    direction = 'Расходы'
                    subdir = 'Обслуживание'
            
            account_name = file_name
            for ext in ['.xls', '.xlsx', '.csv', '.CSV', '.xlsm']:
                account_name = account_name.replace(ext, '')
            
            currency = 'EUR'
            if 'Currency' in df.columns and pd.notna(row['Currency']):
                currency = str(row['Currency'])
            elif 'payment currency' in df.columns and pd.notna(row['payment currency']):
                currency = str(row['payment currency'])
            elif 'account currency' in df.columns and pd.notna(row['account currency']):
                currency = str(row['account currency'])
            
            transactions.append({
                'date': date,
                'amount': amount,
                'currency': currency,
                'account_name': account_name,
                'description': description[:300],
                'article_name': article,
                'direction': direction,
                'subdirection': subdir
            })
            st.write(f"✅ Найдена транзакция: {date} | {amount} {currency} | {description[:50]}")
        except Exception as e:
            st.write(f"❌ Ошибка в строке {idx}: {e}")
            continue
    
    st.write(f"=== ИТОГО найдено транзакций: {len(transactions)} ===")
    return transactions

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
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Транзакции')
                    output.seek(0)
                    st.download_button("📥 Скачать Excel", data=output, file_name=f"анализ_{uploaded_file.name}.xlsx")
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
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Все транзакции')
                output.seek(0)
                st.download_button("📥 Скачать сводный Excel", data=output, file_name=f"сводка.xlsx")
