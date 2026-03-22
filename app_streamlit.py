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
            # Для CSV файлов читаем без заголовков
            with open(tmp_path, 'rb') as f:
                raw = f.read()
            result = chardet.detect(raw[:10000])
            encoding = result['encoding'] if result['encoding'] else 'utf-8'
            
            # Читаем файл без заголовков
            df = pd.read_csv(tmp_path, sep=';', encoding=encoding, header=None, on_bad_lines='skip')
            
            # Если столбцов мало, пробуем с запятой
            if len(df.columns) <= 1:
                df = pd.read_csv(tmp_path, sep=',', encoding=encoding, header=None, on_bad_lines='skip')
            
            # Если всё ещё мало, пробуем latin1
            if len(df.columns) <= 1:
                df = pd.read_csv(tmp_path, sep=';', encoding='latin1', header=None, on_bad_lines='skip')
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

def find_data_start_row(df):
    """Находит строку, с которой начинаются данные (где есть дата в формате DD.MM.YYYY или число)"""
    for idx, row in df.iterrows():
        for val in row.values:
            if pd.notna(val):
                val_str = str(val)
                # Ищем дату в формате DD.MM.YYYY
                if re.match(r'\d{2}\.\d{2}\.\d{4}', val_str):
                    return idx
                # Ищем число (сумму) с возможным минусом
                if re.match(r'^-?\d+[.,]?\d*$', val_str.replace(',', '.')):
                    return max(0, idx - 1)
    return 0

def parse_file(file_content, file_name):
    df = read_file(file_content, file_name)
    if df is None:
        st.error("❌ Не удалось прочитать файл")
        return []
    
    st.write(f"=== ОТЛАДКА: файл {file_name} ===")
    st.write(f"Столбцы в файле: {list(df.columns)}")
    st.write(f"Количество строк: {len(df)}")
    
    # Показываем первые строки для отладки
    st.write("Первые 10 строк файла (без обработки):")
    for i in range(min(10, len(df))):
        st.write(f"Строка {i}: {list(df.iloc[i].values)}")
    
    # Находим строку с заголовками
    name_lower = file_name.lower()
    header_row = None
    
    # Для UniCredit файлов ищем строку с "From Account"
    if 'garpiz' in name_lower or 'koruna' in name_lower or 'twohills' in name_lower:
        for idx, row in df.iterrows():
            row_text = ' '.join(str(v) for v in row.values if pd.notna(v))
            if 'From Account' in row_text:
                header_row = idx
                st.write(f"Найдена строка с заголовками (From Account) на индексе {idx}")
                break
    
    # Если не нашли, ищем строку с датой или заголовками
    if header_row is None:
        for idx, row in df.iterrows():
            row_text = ' '.join(str(v) for v in row.values if pd.notna(v))
            if any(kw in row_text for kw in ['Дата транзакции', 'Date and time', 'Date', 'Amount', 'Booking Date']):
                header_row = idx
                st.write(f"Найдена строка с заголовками на индексе {idx}")
                break
    
    if header_row is not None:
        # Устанавливаем заголовки
        df.columns = df.iloc[header_row]
        df = df.iloc[header_row + 1:].reset_index(drop=True)
        st.write(f"Столбцы после переопределения: {list(df.columns)}")
        st.write(f"Количество строк после: {len(df)}")
    
    # Если после удаления заголовков строк мало, пробуем найти начало данных
    if len(df) < 3:
        start_row = find_data_start_row(df)
        if start_row > 0:
            df = df.iloc[start_row:].reset_index(drop=True)
            st.write(f"Найдено начало данных на строке {start_row}")
    
    # Показываем первые строки после обработки
    st.write("Первые 5 строк после обработки заголовков:")
    for i in range(min(5, len(df))):
        st.write(f"Строка {i}: {df.iloc[i].to_dict()}")
    
    # Если строк всё ещё нет, возвращаем пустой список
    if len(df) == 0:
        st.warning("⚠️ В файле не найдено данных для обработки")
        return []
    
    # Поиск столбцов
    date_col = None
    amount_col = None
    
    # Ищем столбец с датой
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in ['booking', 'posting', 'date', 'дата']):
            date_col = col
            st.write(f"Найден столбец даты: {date_col}")
            break
    
    # Ищем столбец с суммой
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in ['amount', 'сумма', 'payment']):
            amount_col = col
            st.write(f"Найден столбец суммы: {amount_col}")
            break
    
    # Если не нашли по названиям, пробуем по данным
    if date_col is None and len(df.columns) > 0:
        # Ищем столбец, где есть даты
        for col in df.columns:
            sample = df[col].dropna().head(5)
            for val in sample:
                val_str = str(val)
                if re.match(r'\d{2}\.\d{2}\.\d{4}', val_str):
                    date_col = col
                    st.write(f"Найден столбец даты по данным: {date_col}")
                    break
            if date_col:
                break
    
    if amount_col is None and len(df.columns) > 0:
        # Ищем столбец, где есть числа
        for col in df.columns:
            if col != date_col:
                sample = df[col].dropna().head(5)
                for val in sample:
                    try:
                        float(str(val).replace(',', '.'))
                        amount_col = col
                        st.write(f"Найден столбец суммы по данным: {amount_col}")
                        break
                    except:
                        continue
            if amount_col:
                break
    
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]
        st.write(f"Используем первый столбец как дату: {date_col}")
    
    if amount_col is None and len(df.columns) > 1:
        amount_col = df.columns[1]
        st.write(f"Используем второй столбец как сумму: {amount_col}")
    
    st.write(f"Итоговый столбец даты: {date_col}")
    st.write(f"Итоговый столбец суммы: {amount_col}")
    
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
            
            if amount == 0:
                continue
            
            description = ''
            for col in df.columns:
                if col not in [date_col, amount_col]:
                    val = str(row[col]) if pd.notna(row[col]) else ''
                    if val and val != 'nan':
                        description += val + ' '
            
            desc_lower = description.lower()
            
            # Определение статьи
            if any(kw in desc_lower for kw in ['комиссия', 'commission', 'fee', 'charge', 'maintenance']):
                if amount > 0:
                    amount = -amount
                article = '1.2.17 РКО'
                direction = 'Расходы'
                subdir = 'Банковские комиссии'
            elif any(kw in desc_lower for kw in ['арендн', 'rent', 'money added', 'from']):
                article = '1.1.1.1 Арендная плата'
                direction = 'Доходы'
                subdir = 'Арендная плата'
            elif any(kw in desc_lower for kw in ['зарплат', 'salary']):
                if amount > 0:
                    amount = -amount
                article = '1.2.15.1 Зарплата'
                direction = 'Расходы'
                subdir = 'Зарплата'
            elif any(kw in desc_lower for kw in ['налог', 'vid']):
                if amount > 0:
                    amount = -amount
                article = '1.2.16 Налоги'
                direction = 'Расходы'
                subdir = 'Налоги'
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
            
            currency = 'CZK' if 'CZK' in str(df.columns) else 'EUR'
            
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
