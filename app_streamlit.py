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
    # Формат DD.MM.YYYY
    if '.' in date_str:
        parts = date_str.split('.')
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    # Формат YYYY-MM-DD
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]
    if '-' in date_str and len(date_str) >= 10:
        return date_str[:10]
    return date_str[:10] if len(date_str) >= 10 else date_str

def parse_amount(amount_str):
    """Преобразует строку суммы в число, обрабатывая запятые и минусы"""
    if pd.isna(amount_str):
        return 0
    amount_str = str(amount_str).strip()
    if amount_str == '' or amount_str == 'nan':
        return 0
    # Заменяем запятую на точку
    amount_str = amount_str.replace(',', '.')
    # Удаляем пробелы
    amount_str = amount_str.replace(' ', '')
    try:
        return float(amount_str)
    except:
        # Пробуем извлечь число через регулярное выражение
        match = re.search(r'(-?\d+\.?\d*)', amount_str)
        if match:
            try:
                return float(match.group(1))
            except:
                return 0
        return 0

def parse_file(file_content, file_name):
    df = read_file(file_content, file_name)
    if df is None:
        st.error("❌ Не удалось прочитать файл")
        return []
    
    st.write(f"=== ОТЛАДКА: файл {file_name} ===")
    st.write(f"Столбцы в файле: {list(df.columns)}")
    st.write(f"Количество строк: {len(df)}")
    
    # ==================== ПОИСК ЗАГОЛОВКОВ ====================
    header_row = None
    
    # 1. Ищем строку с заголовками для Industra (Дата транзакции)
    for idx, row in df.iterrows():
        row_text = ' '.join(str(v) for v in row.values if pd.notna(v))
        if 'Дата транзакции' in row_text:
            header_row = idx
            st.write(f"Найдена строка Industra с заголовками на индексе {idx}")
            break
    
    # 2. Ищем строку с заголовками для Pasha Bank (Əməliyyat tarixi)
    if header_row is None:
        for idx, row in df.iterrows():
            row_text = ' '.join(str(v) for v in row.values if pd.notna(v))
            if 'Əməliyyat tarixi' in row_text:
                header_row = idx
                st.write(f"Найдена строка Pasha Bank с заголовками на индексе {idx}")
                break
    
    if header_row is not None:
        df.columns = df.iloc[header_row]
        df = df.iloc[header_row + 1:].reset_index(drop=True)
        st.write(f"Столбцы после переопределения: {list(df.columns)}")
        st.write(f"Количество строк после: {len(df)}")
    
    st.write("Первые 5 строк:")
    for i in range(min(5, len(df))):
        st.write(f"Строка {i}: {df.iloc[i].to_dict()}")
    
    # ==================== ПОИСК СТОЛБЦОВ ====================
    date_col = None
    amount_col = None
    debit_col = None
    credit_col = None
    income_col = None
    expense_col = None
    
    # Сначала ищем posting date (для CSOB)
    for col in df.columns:
        col_lower = str(col).lower()
        if 'posting date' in col_lower:
            date_col = col
            st.write(f"Найден столбец даты (posting date): {date_col}")
            break
    
    # Если не нашли, ищем другие варианты
    if date_col is None:
        for col in df.columns:
            col_lower = str(col).lower()
            if 'дата' in col_lower or 'date' in col_lower:
                date_col = col
                st.write(f"Найден столбец даты: {date_col}")
                break
    
    # Ищем сумму (сначала payment amount для CSOB)
    for col in df.columns:
        col_lower = str(col).lower()
        if 'payment amount' in col_lower:
            amount_col = col
            st.write(f"Найден столбец суммы (payment amount): {amount_col}")
            break
    
    if amount_col is None:
        for col in df.columns:
            col_lower = str(col).lower()
            if 'amount' in col_lower and col_lower != 'total amount':
                amount_col = col
                st.write(f"Найден столбец суммы: {amount_col}")
                break
    
    # Ищем дебет/кредит
    for col in df.columns:
        col_lower = str(col).lower()
        if 'дебет' in col_lower or 'debit' in col_lower:
            debit_col = col
        if 'кредит' in col_lower or 'credit' in col_lower:
            credit_col = col
        if 'mədaxil' in col_lower or 'income' in col_lower:
            income_col = col
        if 'məxaric' in col_lower or 'expense' in col_lower:
            expense_col = col
    
    st.write(f"Итоговый столбец даты: {date_col}")
    st.write(f"Итоговый столбец суммы: {amount_col}")
    st.write(f"Найден столбец дебета: {debit_col}")
    st.write(f"Найден столбец кредита: {credit_col}")
    st.write(f"Найден столбец доходов: {income_col}")
    st.write(f"Найден столбец расходов: {expense_col}")
    
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]
        st.write(f"Используем первый столбец как дату: {date_col}")
    
    # ==================== ОБРАБОТКА ТРАНЗАКЦИЙ ====================
    transactions = []
    for idx, row in df.iterrows():
        try:
            # Получаем дату
            if date_col and pd.notna(row[date_col]):
                date = parse_date(row[date_col])
            else:
                continue
            
            # Получаем сумму
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
            
            # Описание
            description = ''
            if 'message to beneficiary and payer' in df.columns and pd.notna(row['message to beneficiary and payer']):
                description = str(row['message to beneficiary and payer'])
            elif 'transaction type' in df.columns and pd.notna(row['transaction type']):
                description = str(row['transaction type'])
            elif 'Description' in df.columns and pd.notna(row['Description']):
                description = str(row['Description'])
            elif 'Təyinat' in df.columns and pd.notna(row['Təyinat']):
                description = str(row['Təyinat'])
            elif 'Информация о транзакции' in df.columns and pd.notna(row['Информация о транзакции']):
                description = str(row['Информация о транзакции'])
            elif 'Тип транзакции' in df.columns and pd.notna(row['Тип транзакции']):
                description = str(row['Тип транзакции'])
            else:
                for col in df.columns:
                    if col not in [date_col, amount_col, debit_col, credit_col, income_col, expense_col]:
                        val = str(row[col]) if pd.notna(row[col]) else ''
                        if val and val != 'nan':
                            description += val + ' '
            
            desc_lower = description.lower()
            
            # ==================== ОПРЕДЕЛЕНИЕ СТАТЬИ ====================
            if 'комиссия' in desc_lower or 'commission' in desc_lower or 'fee' in desc_lower:
                if amount > 0:
                    amount = -amount
                article = '1.2.17 РКО'
                direction = 'Расходы'
                subdir = 'Банковские комиссии'
            elif 'арендн' in desc_lower or 'rent' in desc_lower or 'money added' in desc_lower:
                article = '1.1.1.1 Арендная плата'
                direction = 'Доходы'
                subdir = 'Арендная плата'
            elif 'зарплат' in desc_lower or 'salary' in desc_lower:
                if amount > 0:
                    amount = -amount
                article = '1.2.15.1 Зарплата'
                direction = 'Расходы'
                subdir = 'Зарплата'
            elif 'налог' in desc_lower or 'vid' in desc_lower or 'budžets' in desc_lower:
                if amount > 0:
                    amount = -amount
                article = '1.2.16 Налоги'
                direction = 'Расходы'
                subdir = 'Налоги'
            elif 'latvenergo' in desc_lower:
                if amount > 0:
                    amount = -amount
                article = '1.2.10.5 Электричество'
                direction = 'Расходы'
                subdir = 'Электричество'
            elif 'rigas udens' in desc_lower or 'ūdens' in desc_lower:
                if amount > 0:
                    amount = -amount
                article = '1.2.10.3 Вода'
                direction = 'Расходы'
                subdir = 'Вода'
            elif 'balta' in desc_lower:
                if amount > 0:
                    amount = -amount
                article = '1.2.8.2 Страхование'
                direction = 'Расходы'
                subdir = 'Страхование'
            elif 'airbnb' in desc_lower or 'booking' in desc_lower:
                article = '1.1.1.2 Поступления систем бронирования'
                direction = 'Доходы'
                subdir = 'Краткосрочная аренда'
            elif 'careem' in desc_lower or 'flydubai' in desc_lower:
                if amount > 0:
                    amount = -amount
                article = '1.2.2 Командировочные расходы'
                direction = 'Расходы'
                subdir = 'Командировки'
            elif 'currency exchange' in desc_lower or 'conversion' in desc_lower:
                article = '1.2.17 РКО'
                direction = 'Расходы'
                subdir = 'Банковские комиссии'
                if amount > 0:
                    amount = -amount
            elif 'maintenance' in desc_lower or 'charge' in desc_lower:
                if amount > 0:
                    amount = -amount
                article = '1.2.17 РКО'
                direction = 'Расходы'
                subdir = 'Банковские комиссии'
            else:
                if amount > 0:
                    article = '1.1.1.1 Арендная плата'
                    direction = 'Доходы'
                    subdir = 'Арендная плата'
                else:
                    article = '1.2.8.1 Обслуживание объектов'
                    direction = 'Расходы'
                    subdir = 'Обслуживание'
            
            # Очистка имени счета
            account_name = file_name
            for ext in ['.xls', '.xlsx', '.csv', '.CSV', '.xlsm']:
                account_name = account_name.replace(ext, '')
            
            # Определяем валюту
            currency = 'CZK' if 'CZK' in str(df.columns) else 'EUR'
            if 'payment currency' in df.columns and pd.notna(row['payment currency']):
                currency = str(row['payment currency'])
            
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
            st.write(f"✅ Найдена транзакция: {date} | {amount} | {description[:50]}")
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
