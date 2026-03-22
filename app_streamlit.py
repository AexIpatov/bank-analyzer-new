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
    st.markdown("**Статьи определяются автоматически**")

def read_file(file_content, file_name):
    """Чтение файла (Excel или CSV)"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        if file_name.lower().endswith(('.xls', '.xlsx')):
            try:
                df = pd.read_excel(tmp_path, engine='xlrd')
            except:
                df = pd.read_excel(tmp_path, engine='openpyxl')
        else:
            with open(tmp_path, 'rb') as f:
                raw = f.read()
            result = chardet.detect(raw[:10000])
            encoding = result['encoding'] if result['encoding'] else 'utf-8'
            
            for sep in [';', ',', '\t']:
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
        return None
    
    os.unlink(tmp_path)
    return df

def get_article(description, amount):
    """Определение статьи по описанию"""
    desc_lower = description.lower()
    
    articles = [
        ('комиссия', '1.2.17 РКО', 'Расходы', 'Банковские комиссии'),
        ('commission', '1.2.17 РКО', 'Расходы', 'Банковские комиссии'),
        ('fee', '1.2.17 РКО', 'Расходы', 'Банковские комиссии'),
        ('арендн', '1.1.1.1 Арендная плата', 'Доходы', 'Арендная плата'),
        ('rent', '1.1.1.1 Арендная плата', 'Доходы', 'Арендная плата'),
        ('money added', '1.1.1.1 Арендная плата', 'Доходы', 'Арендная плата'),
        ('компенсац', '1.1.2.3 Компенсация по коммунальным расходам', 'Доходы', 'Компенсация'),
        ('utilities', '1.1.2.3 Компенсация по коммунальным расходам', 'Доходы', 'Компенсация'),
        ('зарплат', '1.2.15.1 Зарплата', 'Расходы', 'Зарплата'),
        ('salary', '1.2.15.1 Зарплата', 'Расходы', 'Зарплата'),
        ('налог', '1.2.16 Налоги', 'Расходы', 'Налоги'),
        ('vid', '1.2.16 Налоги', 'Расходы', 'Налоги'),
        ('latvenergo', '1.2.10.5 Электричество', 'Расходы', 'Электричество'),
        ('rigas udens', '1.2.10.3 Вода', 'Расходы', 'Вода'),
        ('balta', '1.2.8.2 Страхование', 'Расходы', 'Страхование'),
        ('airbnb', '1.1.1.2 Поступления систем бронирования', 'Доходы', 'Краткосрочная аренда'),
        ('booking', '1.1.1.2 Поступления систем бронирования', 'Доходы', 'Краткосрочная аренда'),
        ('careem', '1.2.2 Командировочные расходы', 'Расходы', 'Транспорт'),
        ('flydubai', '1.2.2 Командировочные расходы', 'Расходы', 'Авиабилеты'),
        ('tiktok', '1.2.3 Оплата рекламных систем', 'Расходы', 'Маркетинг'),
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

def parse_file(file_content, file_name):
    """Парсинг файла"""
    df = read_file(file_content, file_name)
    if df is None:
        return []
    
    transactions = []
    date_col = None
    amount_col = None
    
    # Ищем столбцы с датой и суммой
    for col in df.columns:
        col_lower = str(col).lower()
        if 'дата' in col_lower or 'date' in col_lower:
            date_col = col
        if 'сумм' in col_lower or 'amount' in col_lower:
            amount_col = col
    
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]
    if amount_col is None and len(df.columns) > 1:
        amount_col = df.columns[1]
    
    for _, row in df.iterrows():
        try:
            # Дата
            if date_col and pd.notna(row[date_col]):
                date_str = str(row[date_col])
                # Преобразование даты
                if '.' in date_str:
                    parts = date_str.split('.')
                    if len(parts) == 3:
                        date = f"{parts[2]}-{parts[1]}-{parts[0]}"
                    else:
                        date = date_str[:10]
                else:
                    date = date_str[:10]
            else:
                continue
            
            # Сумма
            amount = 0
            if amount_col and pd.notna(row[amount_col]):
                try:
                    amount = float(str(row[amount_col]).replace(',', '.'))
                except:
                    amount = 0
            
            if amount == 0:
                continue
            
            # Описание
            description = ''
            for col in df.columns:
                if col not in [date_col, amount_col]:
                    val = str(row[col]) if pd.notna(row[col]) else ''
                    if val and val != 'nan':
                        description += val + ' '
            
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
        except:
            continue
    
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
