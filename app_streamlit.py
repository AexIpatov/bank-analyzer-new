import streamlit as st
import pandas as pd
import io
import tempfile
import os
import chardet
import re
from datetime import datetime
from io import BytesIO
from typing import Optional, List, Tuple, Dict, Any
import warnings

# Отключаем предупреждения
warnings.filterwarnings('ignore')

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

# ==================== КЛАСС УМНОГО ДЕТЕКТОРА ЗАГОЛОВКОВ ====================

class HeaderDetector:
    """Умный детектор заголовков для финансовых выписок"""
    
    def __init__(self):
        self.header_patterns = {
            'date': [
                'date', 'дата', 'datum', 'dátum', 'data',
                'transaction date', 'value date', 'booking date',
                'дата транзакции', 'дата операции'
            ],
            'amount': [
                'amount', 'сумма', 'összeg', 'betrag',
                'debit', 'credit', 'дебет', 'кредит',
                'debit(d)', 'credit(c)', 'сумма списания', 'сумма зачисления'
            ],
            'description': [
                'description', 'описание', 'leírás', 'beschreibung',
                'details', 'детали', 'transaction details',
                'назначение платежа', 'примечание'
            ],
            'balance': [
                'balance', 'остаток', 'egyenleg', 'saldo',
                'closing balance', 'конечный остаток'
            ]
        }
        
        self.file_patterns = {
            'industra': [r'industra', r'индустра', r'банк.*индустра'],
            'revolut': [r'revolut', r'револют', r'.*revolut.*statement'],
            'budapest': [r'budapest', r'будапешт', r'budapest.*bank'],
            'pasha': [r'pasha', r'паша', r'kapital', r'капитал']
        }
    
    def detect_file_type(self, filename: str) -> str:
        filename_lower = filename.lower()
        for file_type, patterns in self.file_patterns.items():
            for pattern in patterns:
                if re.search(pattern, filename_lower, re.IGNORECASE):
                    return file_type
        return "unknown"
    
    def find_header_row(self, df: pd.DataFrame, max_rows_to_check: int = 20) -> Optional[int]:
        if df.empty:
            return None
        
        rows_to_check = min(max_rows_to_check, len(df))
        best_match_score = 0
        best_match_row = None
        
        for row_idx in range(rows_to_check):
            row = df.iloc[row_idx]
            score = self._calculate_header_score(row)
            if score > best_match_score:
                best_match_score = score
                best_match_row = row_idx
        
        if best_match_score >= 2:
            return best_match_row
        return None
    
    def _calculate_header_score(self, row: pd.Series) -> int:
        score = 0
        for cell in row:
            if pd.isna(cell):
                continue
            cell_str = str(cell).lower().strip()
            for column_type, keywords in self.header_patterns.items():
                for keyword in keywords:
                    if keyword in cell_str:
                        score += 1
                        break
        
        for cell in row:
            if pd.isna(cell):
                continue
            cell_str = str(cell).strip()
            if self._looks_like_date(cell_str):
                score -= 1
            if self._looks_like_amount(cell_str):
                score -= 1
        
        return max(0, score)
    
    def _looks_like_date(self, value: str) -> bool:
        date_patterns = [
            r'\d{4}[-./]\d{1,2}[-./]\d{1,2}',
            r'\d{1,2}[-./]\d{1,2}[-./]\d{4}',
            r'\d{1,2}[-./]\d{1,2}[-./]\d{2}',
        ]
        for pattern in date_patterns:
            if re.match(pattern, value):
                return True
        return False
    
    def _looks_like_amount(self, value: str) -> bool:
        clean_value = value.replace(' ', '')
        amount_patterns = [
            r'^-?\d+[.,]\d{2}$',
            r'^-?\d+[.,]\d{2}[A-Z]{3}$',
            r'^-?\d+[A-Z]{3}$',
        ]
        for pattern in amount_patterns:
            if re.match(pattern, clean_value):
                return True
        return False
    
    def get_expected_columns(self, file_type: str) -> List[str]:
        column_templates = {
            'industra': ['Дата транзакции', 'Дебет(D)', 'Кредит(C)', 'Информация о транзакции'],
            'revolut': ['Date started (UTC)', 'Type', 'Description', 'Amount'],
            'budapest': ['Serial number', 'Value date', 'Amount', 'Narrative'],
            'pasha': ['Дата', 'Сумма', 'Валюта', 'Описание'],
            'unknown': ['Date', 'Amount', 'Currency', 'Description']
        }
        return column_templates.get(file_type, column_templates['unknown'])
    
    def validate_header_row(self, df: pd.DataFrame, header_row: int) -> bool:
        if header_row is None or header_row >= len(df):
            return False
        header = df.iloc[header_row]
        numeric_count = 0
        for cell in header:
            if pd.isna(cell):
                continue
            cell_str = str(cell).strip()
            try:
                float(cell_str.replace(',', '.'))
                numeric_count += 1
            except ValueError:
                if self._looks_like_date(cell_str):
                    numeric_count += 1
        if numeric_count > len(header) * 0.5:
            return False
        return True

# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================

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
            
            with open(tmp_path, 'r', encoding=encoding) as f:
                lines = f.readlines()
            
            data = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if ';' in line:
                    parts = line.split(';')
                elif ',' in line:
                    parts = line.split(',')
                else:
                    parts = [line]
                data.append(parts)
            
            max_cols = max(len(row) for row in data) if data else 0
            for row in data:
                while len(row) < max_cols:
                    row.append('')
            
            df = pd.DataFrame(data)
    except Exception as e:
        os.unlink(tmp_path)
        raise e
    os.unlink(tmp_path)
    return df

def parse_date(date_str):
    if pd.isna(date_str):
        return ''
    date_str = str(date_str).strip()
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]
    
    formats = [
        "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y",
        "%Y.%m.%d", "%d-%m-%Y", "%Y/%m/%d"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    if '.' in date_str:
        parts = date_str.split('.')
        if len(parts) == 3 and len(parts[2]) == 4:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
        if len(parts) == 3 and len(parts[2]) == 2:
            year = 2000 + int(parts[2])
            return f"{year}-{parts[1]}-{parts[0]}"
    if '-' in date_str and len(date_str) >= 10:
        return date_str[:10]
    return date_str

def parse_amount(amount_str):
    if pd.isna(amount_str):
        return 0
    amount_str = str(amount_str).strip()
    if amount_str == '' or amount_str == 'nan':
        return 0
    
    if re.match(r'^\d{1,2}\.\d{1,2}\.\d{2,4}$', amount_str):
        return 0
    if re.match(r'^\d{4}-\d{2}-\d{2}', amount_str):
        return 0
    
    if amount_str.startswith('-+'):
        amount_str = '-' + amount_str[2:]
    
    amount_str = amount_str.replace(',', '.').replace(' ', '')
    has_minus = amount_str.startswith('-')
    amount_str = re.sub(r'[^0-9\.\-]', '', amount_str)
    if amount_str == '' or amount_str == '-':
        return 0
    try:
        val = float(amount_str)
        if has_minus and val > 0:
            val = -val
        return val
    except:
        return 0

def get_article_by_description(description, amount):
    desc_lower = description.lower()
    
    if amount < 0:
        if any(kw in desc_lower for kw in ['комиссия', 'commission', 'fee', 'charge', 'maintenance', 'rko', 'subscription', 'плата за обслуживание', 'service package', 'számlakivonat díja', 'netbankár monthly fee']):
            return '1.2.17 РКО', 'Расходы', 'Банковские комиссии'
        
        if any(kw in desc_lower for kw in ['service package monthly fee']):
            return '1.2.21.2 Административные офисные расходы', 'Расходы', 'Офисные расходы'
        
        if any(kw in desc_lower for kw in ['зарплат', 'salary', 'darba alga', 'algas izmaksa']):
            return '1.2.15.1 Зарплата', 'Расходы', 'Зарплата'
        
        if any(kw in desc_lower for kw in ['nodokļu nomaksa', 'vid', 'budžets', 'налог']):
            return '1.2.15.2 Налоги на ФОТ', 'Расходы', 'Налоги на ФОТ'
        
        if any(kw in desc_lower for kw in ['latvenergo', 'elektri', 'электричеств', 'electricity']):
            return '1.2.10.5 Электричество', 'Расходы', 'Электричество'
        
        if any(kw in desc_lower for kw in ['rigas udens', 'ūdens', 'вода']):
            return '1.2.10.3 Вода', 'Расходы', 'Вода'
        
        if any(kw in desc_lower for kw in ['gāze', 'газ']):
            return '1.2.10.2 Газ', 'Расходы', 'Газ'
        
        if any(kw in desc_lower for kw in ['atkritumi', 'мусор', 'eco baltia', 'clean r']):
            return '1.2.10.1 Мусор', 'Расходы', 'Вывоз мусора'
        
        if any(kw in desc_lower for kw in ['tele2', 'bite', 'tet', 'internet', 'связь']):
            return '1.2.9.1 Связь, интернет, TV', 'Расходы', 'Связь и интернет'
        
        if any(kw in desc_lower for kw in ['google one', 'lovable', 'openai', 'chatgpt', 'browsec']):
            return '1.2.9.3 IT сервисы', 'Расходы', 'IT сервисы'
        
        if any(kw in desc_lower for kw in ['facebook', 'facbk', 'tiktok', 'ads', 'marketing', 'реклам']):
            return '1.2.3 Оплата рекламных систем (бюджет)', 'Расходы', 'Маркетинг'
        
        if any(kw in desc_lower for kw in ['apmaksa par rēķinu', 'обслуживание', 'ремонт', 'lifti', 'taipans']):
            return '1.2.8.1 Обслуживание объектов', 'Расходы', 'Обслуживание объектов'
        
        return '1.2.8.1 Обслуживание объектов', 'Расходы', 'Обслуживание объектов'
    
    else:
        if any(kw in desc_lower for kw in ['airbnb', 'booking.com']):
            return '1.1.1.2 Поступления систем бронирования (Airbnb, Booking и пр.)', 'Доходы', 'Краткосрочная аренда'
        
        if any(kw in desc_lower for kw in ['depozits', 'депозит', 'deposit']):
            return '1.1.1.4 Получение гарантийного депозита', 'Доходы', 'Гарантийный депозит'
        
        if any(kw in desc_lower for kw in ['commission', 'agency commissions', 'incoming swift payment']):
            return '1.1.4.1 Комиссия за продажу недвижимости', 'Доходы', 'Комиссия за продажу'
        
        if any(kw in desc_lower for kw in ['loan', 'займ', 'baltic solutions']):
            return '3.1.3 Получение внутригруппового займа', 'Доходы', 'Внутригрупповой займ'
        
        if any(kw in desc_lower for kw in ['loan return', 'возврат займа']):
            return '3.1.4 Возврат выданного внутригруппового займа', 'Доходы', 'Возврат займа'
        
        if any(kw in desc_lower for kw in ['наличные', 'cash']):
            return '1.1.1.1 Арендная плата (наличные)', 'Доходы', 'Арендная плата наличные'
        
        if any(kw in desc_lower for kw in ['komunālie', 'utilities', 'компенсац', 'возмещени']):
            return '1.1.2.3 Компенсация по коммунальным расходам', 'Доходы', 'Компенсация коммунальных'
        
        if any(kw in desc_lower for kw in ['арендн', 'rent', 'money added', 'ire', 'dzivoklis', 'from', 'credit of sepa']):
            return '1.1.1.3 Арендная плата (счёт)', 'Доходы', 'Арендная плата'
        
        return '1.1.1.3 Арендная плата (счёт)', 'Доходы', 'Арендная плата'

def parse_file(file_content, file_name):
    df = read_file(file_content, file_name)
    if df is None:
        st.error("❌ Не удалось прочитать файл")
        return []
    
    file_lower = file_name.lower()
    
    # Определяем тип файла
    detector = HeaderDetector()
    file_type = detector.detect_file_type(file_name)
    
    # Находим строку заголовков
    header_row = detector.find_header_row(df)
    
    if header_row is not None and detector.validate_header_row(df, header_row):
        headers = list(df.iloc[header_row].values)
        clean_headers = []
        for h in headers:
            if pd.notna(h) and str(h).strip():
                clean_headers.append(str(h).strip())
            else:
                clean_headers.append(f'col_{len(clean_headers)}')
        
        seen = {}
        unique_headers = []
        for h in clean_headers:
            if h in seen:
                seen[h] += 1
                unique_headers.append(f"{h}_{seen[h]}")
            else:
                seen[h] = 0
                unique_headers.append(h)
        
        data_rows = []
        for idx in range(header_row + 1, len(df)):
            row = list(df.iloc[idx].values)
            if len(row) < len(unique_headers):
                row.extend([''] * (len(unique_headers) - len(row)))
            data_rows.append(row[:len(unique_headers)])
        
        df = pd.DataFrame(data_rows, columns=unique_headers)
    
    if len(df) == 0:
        st.warning("⚠️ В файле не найдено данных для обработки")
        return []
    
    # Поиск столбцов
    date_col = None
    amount_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in ['date', 'дата', 'datum', 'booking', 'value', 'posting']):
            date_col = col
            break
    
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]
    
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in ['amount', 'сумма', 'debit', 'credit', 'дебет', 'кредит', 'доход', 'расход']):
            amount_col = col
            break
    
    if amount_col is None and len(df.columns) > 1:
        amount_col = df.columns[1]
    
    # Обработка транзакций
    transactions = []
    
    for idx in range(len(df)):
        try:
            row = df.iloc[idx]
            
            date = ''
            if date_col is not None:
                date_val = row[date_col]
                if pd.notna(date_val):
                    date = parse_date(date_val)
            
            if not date:
                continue
            
            amount = 0
            if amount_col is not None:
                amount_val = row[amount_col]
                if pd.notna(amount_val):
                    amount = parse_amount(amount_val)
            
            if amount == 0:
                continue
            
            description = ''
            for col in df.columns:
                if col not in [date_col, amount_col]:
                    val = row[col]
                    if pd.notna(val) and str(val).strip() and str(val) != 'nan':
                        description += str(val) + ' '
            
            article, direction, subdir = get_article_by_description(description, amount)
            
            currency = 'EUR'
            if 'CZK' in file_lower:
                currency = 'CZK'
            elif 'HUF' in file_lower:
                currency = 'HUF'
            elif 'RUB' in file_lower:
                currency = 'RUB'
            elif 'AED' in file_lower:
                currency = 'AED'
            elif 'AZN' in file_lower:
                currency = 'AZN'
            
            account_name = file_name.replace('.csv', '').replace('.xlsx', '').replace('.xls', '')
            
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
            
        except Exception as e:
            continue
    
    return transactions

# ==================== ИНТЕРФЕЙС ====================

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
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Транзакции')
                    output.seek(0)
                    st.download_button(
                        "📥 Скачать Excel", 
                        data=output, 
                        file_name=f"анализ_{uploaded_file.name}.xlsx"
                    )
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
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Все транзакции')
                output.seek(0)
                st.download_button(
                    "📥 Скачать сводный Excel", 
                    data=output, 
                    file_name="сводка.xlsx"
                )
