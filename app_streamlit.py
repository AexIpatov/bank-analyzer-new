import streamlit as st
import pandas as pd
import io
from datetime import datetime
from parsers import *

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

PARSERS = {
    'ANTONIJAS NAMS 14 SIA-Industra': AntonijasIndustraParser,
    'Antonijas nams 14-Revolut International': AntonijasRevolutParser,
    'Industra Bank-Plavas 1': IndustriPlavasParser,
    'Paysera-BS PROPERTY, SIA': PayseraPropertyParser,
    'Paysera-BS RERUM, SIA': PayseraRerumParser,
    'Paysera Sveciy Namai Lithuania EUR': PayseraSveciyParser,
    'TwoHills_Molly_Unicredit_CZK': TwoHillsMollyParser,
    'WIO Business Bank': WioBusinessParser,
    'MASHREQ BANK-AED-NOMIQA': MashreqNomiqaParser,
    'Pasha Bunda AED': PashaBundaParser,
    'Pasha Bunda AZN': PashaBundaParser,
    'DŽIBIK Main CSOB CZK': DzibikCsobParser,
    'Garpiz UniCredit Bank CZK': GarpizUnicreditParser,
    'Koruna UniCredit- CZK': KorunaUnicreditParser,
    'BUNDA LLC-Pasha Bank - AED-дирхам': BundaAEDParser,
    'BUNDA LLC-Pasha Bank-AZN': BundaAZNParser,
}

def get_parser(file_name):
    for key, parser in PARSERS.items():
        if key in file_name:
            return parser()
    return None

tab1, tab2 = st.tabs(["📂 Один файл", "📚 Несколько файлов"])

with tab1:
    st.markdown("### Загрузите выписку для анализа")
    uploaded_file = st.file_uploader("Выберите файл", type=['csv', 'xlsx', 'xls'], key="single")
    if uploaded_file:
        st.success(f"✅ Файл загружен: {uploaded_file.name}")
        if st.button("🚀 Запустить анализ", key="single_btn"):
            with st.spinner("Анализируем..."):
                content = uploaded_file.read()
                parser = get_parser(uploaded_file.name)
                
                if parser:
                    transactions = parser.parse(content, uploaded_file.name)
                else:
                    st.error(f"❌ Не найден парсер для файла: {uploaded_file.name}")
                    transactions = []
                
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
                parser = get_parser(f.name)
                
                if parser:
                    trans = parser.parse(content, f.name)
                else:
                    st.error(f"❌ Не найден парсер для файла: {f.name}")
                    trans = []
                
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
