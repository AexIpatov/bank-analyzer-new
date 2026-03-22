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
    st.markdown("**Статьи определяются по ключевым словам**")

# ============================================
# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
# ============================================

def detect_encoding(file_content):
    result = chardet.detect(file_content[:10000])
    return result['encoding'] if result['encoding'] else 'utf-8'

def read_file(file_content, file_name):
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    try:
        if file_name.lower().endswith(('.xls', '.xlsx')):
            # Сначала пробуем openpyxl для .xlsx
            if file_name.lower().endswith('.xlsx'):
                try:
                    df = pd.read_excel(tmp_path, engine='openpyxl')
                except:
                    df = pd.read_excel(tmp_path)
            # Для .xls используем xlrd
            else:
                try:
                    df = pd.read_excel(tmp_path, engine='xlrd')
                except:
                    # Если xlrd не работает, пробуем openpyxl
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
    if '.' in date_str:
        parts = date_str.split('.')
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]
    if '-' in date_str and len(date_str) >= 10:
        return date_str[:10]
    return date_str[:10] if len(date_str) >= 10 else date_str

def get_article(description, amount):
    desc_lower = description.lower()
    
    articles = [
        ('комиссия', '1.2.17 РКО', 'Расходы', 'Банковские комиссии'),
        ('commission', '1.2.17 РКО', 'Расходы', 'Банковские комиссии'),
        ('fee', '1.2.17 РКО', 'Расходы', 'Банковские комиссии'),
        ('арендн', '1.1.1.1 Арендная плата', 'Доходы', 'Арендная плата'),
        ('rent', '1.1.1.1 Арендная плата', 'Доходы', 'Арендная плата'),
        ('money added', '1.1.1.1 Арендная плата', 'Доходы', 'Арендная плата'),
        ('компенсац', '1.1.2.3 Компенсация по коммунальным расходам', 'Доходы', 'Компенсация'),
        ('зарплат', '1.2.15.1 Зарплата', 'Расходы', 'Зарплата'),
        ('налог', '1.2.16 Налоги', 'Расходы', 'Налоги'),
        ('latvenergo', '1.2.10.5 Электричество', 'Расходы', 'Электричество'),
        ('balta', '1.2.8.2 Страхование', 'Расходы', 'Страхование'),
        ('airbnb', '1.1.1.2 Поступления систем бронирования', 'Доходы', 'Краткосрочная аренда'),
        ('booking', '1.1.1.2 Поступления систем бронирования', 'Доходы', 'Краткосрочная аренда'),
        ('careem', '1.2.2 Командировочные расходы', 'Расходы', 'Транспорт'),
        ('flydubai', '1.2.2 Командировочные расходы', 'Расходы', 'Авиабилеты'),
        ('facebook', '1.2.3 Оплата рекламных систем', 'Расходы', 'Маркетинг'),
        ('asana', '1.2.9.3 IT сервисы', 'Расходы', 'IT сервисы'),
    ]
    
    for kw, article, direction, subdirection in articles:
        if kw in desc_lower:
            if direction == 'Расходы' and amount > 0:
                amount = -amount
            return article, direction, subdirection, amount
    
    if amount > 0:
        return '1.1.1.1 Арендная плата', 'Доходы', 'Арендная плата', amount
    else:
        return '1.2.8.1 Обслуживание объектов', 'Расходы', 'Обслуживание', amount

# ============================================
# === ПАРСЕРЫ ===
# ============================================

def parse_antonijas_industra(df, file_name):
    # Ищем строку с заголовками
    header_row = None
    for idx, row in df.iterrows():
        row_text = ' '.join(str(v) for v in row.values if pd.notna(v))
        if 'Дата транзакции' in row_text:
            header_row = idx
            break
    
    if header_row is None:
        return []
    
    df.columns = df.iloc[header_row]
    df = df.iloc[header_row + 1:].reset_index(drop=True)
    
    transactions = []
    for _, row in df.iterrows():
        date_val = row.get('Дата транзакции', '')
        if pd.isna(date_val):
            continue
        date = parse_date(date_val)
        
        amount = 0
        debit = row.get('Дебет(D)', row.get('Дебет(Д)', 0))
        credit = row.get('Кредит(C)', row.get('Кредит(С)', 0))
        
        if pd.notna(credit) and credit != 0:
            amount = float(credit)
        elif pd.notna(debit) and debit != 0:
            amount = -float(debit)
        
        if amount == 0:
            continue
        
        description = str(row.get('Информация о транзакции', ''))
        if not description or description == 'nan':
            description = str(row.get('Тип транзакции', ''))
        if not description or description == 'nan':
            description = str(row.get('Получатель / Плательщик', ''))
        
        article, direction, subdirection, amount = get_article(description, amount)
        
        transactions.append({
            'date': date,
            'amount': amount,
            'currency': 'EUR',
            'account_name': file_name.replace('.xls', '').replace('.xlsx', '').replace('.csv', ''),
            'description': description[:300],
            'article_name': article,
            'direction': direction,
            'subdirection': subdirection
        })
    return transactions

def parse_antonijas_revolut(df, file_name):
    transactions = []
    for _, row in df.iterrows():
        date_str = str(row.get('Date started (UTC)', ''))
        if not date_str or date_str == 'nan':
            continue
        date = parse_date(date_str)
        amount = float(row.get('Amount', 0)) if pd.notna(row.get('Amount', 0)) else 0
        if amount == 0:
            continue
        description = str(row.get('Description', ''))
        if 'To ' in description and amount > 0:
            amount = -amount
        article, direction, subdirection, amount = get_article(description, amount)
        transactions.append({
            'date': date,
            'amount': amount,
            'currency': row.get('Payment currency', 'EUR'),
            'account_name': file_name.replace('.csv', '').replace('.xls', '').replace('.xlsx', ''),
            'description': description[:300],
            'article_name': article,
            'direction': direction,
            'subdirection': subdirection
        })
    return transactions

def parse_paysera(df, file_name):
    header_row = None
    for idx, row in df.iterrows():
        row_text = ' '.join(str(v) for v in row.values if pd.notna(v))
        if 'Date and time' in row_text:
            header_row = idx
            break
    if header_row is None:
        return []
    df.columns = df.iloc[header_row]
    df = df.iloc[header_row + 1:].reset_index(drop=True)
    
    transactions = []
    for _, row in df.iterrows():
        if pd.isna(row.get('Date and time', pd.NA)):
            continue
        date = parse_date(str(row.get('Date and time', '')))
        amount_str = str(row.get('Amount and currency', '0'))
        amount = 0
        amount_match = re.search(r'([-]?\d+[.,]?\d*)', amount_str)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', '.'))
            except:
                amount = 0
        cd = str(row.get('Credit/Debit', '')).upper()
        if cd == 'D' and amount > 0:
            amount = -amount
        description = str(row.get('Purpose of payment', ''))
        if not description or description == 'nan':
            description = str(row.get('Recipient / Payer', ''))
        if date and amount != 0:
            article, direction, subdirection, amount = get_article(description, amount)
            transactions.append({
                'date': date,
                'amount': amount,
                'currency': 'EUR',
                'account_name': file_name.replace('.xls', '').replace('.xlsx', '').replace('.csv', ''),
                'description': description[:300],
                'article_name': article,
                'direction': direction,
                'subdirection': subdirection
            })
    return transactions

def parse_wio(df, file_name):
    transactions = []
    for _, row in df.iterrows():
        date_str = str(row.get('Date', ''))
        if not date_str or date_str == 'nan':
            continue
        date = parse_date(date_str)
        amount = float(row.get('Amount', 0)) if pd.notna(row.get('Amount', 0)) else 0
        if amount == 0:
            continue
        description = str(row.get('Description', ''))
        article, direction, subdirection, amount = get_article(description, amount)
        transactions.append({
            'date': date,
            'amount': amount,
            'currency': row.get('Account currency', 'AED'),
            'account_name': file_name.replace('.csv', '').replace('.xls', '').replace('.xlsx', ''),
            'description': description[:300],
            'article_name': article,
            'direction': direction,
            'subdirection': subdirection
        })
    return transactions

def parse_unicredit(df, file_name):
    amount_col = None
    date_col = None
    desc_col = None
    for col in df.columns:
        col_lower = str(col).lower()
        if 'amount' in col_lower:
            amount_col = col
        if 'booking' in col_lower or 'date' in col_lower:
            date_col = col
        if 'transaction' in col_lower or 'details' in col_lower:
            desc_col = col
    if amount_col is None:
        return []
    
    transactions = []
    for _, row in df.iterrows():
        amount = 0
        try:
            amount = float(str(row[amount_col]).replace(',', '.'))
        except:
            continue
        if amount == 0:
            continue
        date = ''
        if date_col and pd.notna(row[date_col]):
            date = parse_date(str(row[date_col]))
        description = ''
        if desc_col and pd.notna(row[desc_col]):
            description = str(row[desc_col])
        if date:
            article, direction, subdirection, amount = get_article(description, amount)
            transactions.append({
                'date': date,
                'amount': amount,
                'currency': 'CZK',
                'account_name': file_name.replace('.csv', '').replace('.xls', '').replace('.xlsx', ''),
                'description': description[:300],
                'article_name': article,
                'direction': direction,
                'subdirection': subdirection
            })
    return transactions

def parse_mashreq(df, file_name):
    try:
        df.columns = df.iloc[8]
        df = df.iloc[9:].reset_index(drop=True)
    except:
        pass
    
    transactions = []
    for _, row in df.iterrows():
        date_str = str(row.get('Date', ''))
        if pd.isna(date_str) or date_str == 'nan':
            continue
        date = parse_date(date_str)
        credit = row.get('Credit', 0)
        debit = row.get('Debit', 0)
        amount = credit if pd.notna(credit) and credit != 0 else -debit if pd.notna(debit) and debit != 0 else 0
        if amount == 0:
            continue
        description = str(row.get('Description', ''))
        article, direction, subdirection, amount = get_article(description, amount)
        transactions.append({
            'date': date,
            'amount': amount,
            'currency': 'AED',
            'account_name': file_name.replace('.xlsx', '').replace('.xls', '').replace('.csv', ''),
            'description': description[:300],
            'article_name': article,
            'direction': direction,
            'subdirection': subdirection
        })
    return transactions

def parse_pasha(df, file_name):
    header_row = None
    for idx, row in df.iterrows():
        row_text = ' '.join(str(v) for v in row.values if pd.notna(v))
        if 'Əməliyyat tarixi' in row_text:
            header_row = idx
            break
    if header_row is None:
        return []
    df.columns = df.iloc[header_row]
    df = df.iloc[header_row + 1:].reset_index(drop=True)
    
    transactions = []
    for _, row in df.iterrows():
        date_str = str(row.get('Əməliyyat tarixi', ''))
        if pd.isna(date_str) or date_str == 'nan':
            continue
        date = parse_date(date_str)
        income = row.get('Mədaxil', 0)
        expense = row.get('Məxaric', 0)
        amount = income if pd.notna(income) and income != 0 else -expense if pd.notna(expense) and expense != 0 else 0
        if amount == 0:
            continue
        description = str(row.get('Təyinat', ''))
        article, direction, subdirection, amount = get_article(description, amount)
        transactions.append({
            'date': date,
            'amount': amount,
            'currency': 'AZN' if 'AZN' in file_name else 'AED',
            'account_name': file_name.replace('.xlsx', '').replace('.xls', '').replace('.csv', ''),
            'description': description[:300],
            'article_name': article,
            'direction': direction,
            'subdirection': subdirection
        })
    return transactions

# ============================================
# === ОСНОВНАЯ ФУНКЦИЯ ===
# ============================================

def process_file(file_content, file_name):
    df = read_file(file_content, file_name)
    if df is None:
        return []
    
    name_lower = file_name.lower()
    
    # Antonijas Industra
    if 'antonijas nams 14 sia-industra' in name_lower:
        return parse_antonijas_industra(df, file_name)
    
    # Antonijas Revolut
    if 'antonijas nams 14-revolut' in name_lower:
        return parse_antonijas_revolut(df, file_name)
    
    # Industra Plavas
    if 'industra bank-plavas 1' in name_lower:
        return parse_antonijas_industra(df, file_name)
    
    # Paysera
    if 'paysera' in name_lower:
        return parse_paysera(df, file_name)
    
    # WIO
    if 'wio' in name_lower:
        return parse_wio(df, file_name)
    
    # Mashreq
    if 'mashreq' in name_lower:
        return parse_mashreq(df, file_name)
    
    # Pasha / Bunda
    if 'pasha' in name_lower or 'bunda' in name_lower:
        return parse_pasha(df, file_name)
    
    # UniCredit (Garpiz, Koruna, TwoHills)
    if 'unicredit' in name_lower or 'garpiz' in name_lower or 'koruna' in name_lower or 'twohills' in name_lower:
        return parse_unicredit(df, file_name)
    
    # CSOB (Džibik)
    if 'csob' in name_lower or 'dzibik' in name_lower:
        return parse_unicredit(df, file_name)
    
    return []

# ============================================
# === ИНТЕРФЕЙС ===
# ============================================

tab1, tab2 = st.tabs(["📂 Один файл", "📚 Несколько файлов"])

with tab1:
    st.markdown("### Загрузите выписку для анализа")
    uploaded_file = st.file_uploader("Выберите файл", type=['csv', 'xlsx', 'xls'], key="single")
    if uploaded_file:
        st.success(f"✅ Файл загружен: {uploaded_file.name}")
        if st.button("🚀 Запустить анализ", key="single_btn"):
            with st.spinner("Анализируем..."):
                content = uploaded_file.read()
                transactions = process_file(content, uploaded_file.name)
                
                if transactions:
                    df = pd.DataFrame([{
                        'Дата': t['date'],
                        'Сумма': t['amount'],
                        'Валюта': t['currency'],
                        'Счет': t['account_name'],
                        'Статья': t.get('article_name', 'Требует уточнения'),
                        'Направление': t.get('direction', 'Требует уточнения'),
                        'Субнаправление': t.get('subdirection', ''),
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
                trans = process_file(content, f.name)
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
                    'Статья': t.get('article_name', 'Требует уточнения'),
                    'Направление': t.get('direction', 'Требует уточнения'),
                    'Субнаправление': t.get('subdirection', ''),
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
