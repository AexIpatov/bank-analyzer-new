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

# ==================== ЗАГРУЗКА СПРАВОЧНИКОВ ====================
@st.cache_data
def load_reference_books():
    """Загружает справочники из файлов"""
    reference_books = {
        'accounts': {},
        'articles': {},
        'directions': {}
    }
    
    # Справочник банковских счетов
    try:
        df_accounts = pd.read_excel('Справочник банковских счетов_для_агента.xlsx', sheet_name='Для_агента')
        for _, row in df_accounts.iterrows():
            account_name = str(row['Название']).strip()
            if account_name and account_name != 'nan':
                reference_books['accounts'][account_name.lower()] = {
                    'direction': row['Направление'] if pd.notna(row['Направление']) else '',
                    'subdirection': row['Субнаправление (Объект аренды)'] if pd.notna(row['Субнаправление (Объект аренды)']) else '',
                    'currency': row['Валюта'] if pd.notna(row['Валюта']) else 'EUR',
                    'business': row['Бизнес'] if pd.notna(row['Бизнес']) else ''
                }
    except Exception as e:
        st.warning(f"Не удалось загрузить справочник счетов: {e}")
    
    # Справочник статей
    try:
        df_articles = pd.read_excel('Справочник статей_для_агента.xlsx', sheet_name='Для_агента')
        for _, row in df_articles.iterrows():
            subarticle = str(row['Название субстатьи']).strip()
            parent = str(row['Название родительской статьи']).strip()
            if subarticle and subarticle != 'nan':
                reference_books['articles'][subarticle.lower()] = {
                    'code': subarticle,
                    'parent': parent,
                    'description': row['Описание'] if pd.notna(row['Описание']) else ''
                }
    except Exception as e:
        st.warning(f"Не удалось загрузить справочник статей: {e}")
    
    # Справочник направлений
    try:
        df_directions = pd.read_excel('Справочник направлений_для_агента.xlsx', sheet_name='Для_агента')
        for _, row in df_directions.iterrows():
            direction = str(row['Направление']).strip()
            subdirection = str(row['Субнаправление']).strip()
            if direction and direction != 'nan':
                if direction not in reference_books['directions']:
                    reference_books['directions'][direction] = []
                if subdirection and subdirection != 'nan':
                    reference_books['directions'][direction].append(subdirection.lower())
    except Exception as e:
        st.warning(f"Не удалось загрузить справочник направлений: {e}")
    
    return reference_books

# Загружаем справочники
REF = load_reference_books()

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

def get_account_info(file_name, df):
    """Определяет счет и по нему направление и субнаправление"""
    file_lower = file_name.lower()
    
    # Ищем по имени файла
    for acc_name, info in REF['accounts'].items():
        if acc_name in file_lower:
            return info['direction'], info['subdirection'], info['currency'], acc_name
    
    # Если не нашли, возвращаем значения по умолчанию
    return 'UK Estate', '', 'EUR', file_name.replace('.csv', '').replace('.xlsx', '').replace('.xls', '')

def get_article_by_description(description, amount):
    """Определяет статью по описанию из справочника"""
    desc_lower = description.lower()
    
    # ========== РАСХОДЫ (отрицательные суммы) ==========
    if amount < 0:
        # 1.2.17 РКО — банковские комиссии
        if any(kw in desc_lower for kw in ['комиссия', 'commission', 'fee', 'charge', 'maintenance', 'rko', 'subscription', 'atm withdrawal', 'foreign exchange', 'плата за обслуживание', 'service package', 'számlakivonat díja', 'netbankár monthly fee']):
            return '1.2.17 РКО', 'Расходы', 'Банковские комиссии'
        
        # 1.2.21.2 Административные офисные расходы
        if any(kw in desc_lower for kw in ['service package monthly fee']):
            return '1.2.21.2 Административные офисные расходы', 'Расходы', 'Офисные расходы'
        
        # Зарплата
        if any(kw in desc_lower for kw in ['зарплат', 'salary', 'darba alga', 'algas izmaksa']):
            return '1.2.15.1 Зарплата', 'Расходы', 'Зарплата'
        
        # Налоги
        if any(kw in desc_lower for kw in ['nodokļu nomaksa', 'vid', 'budžets', 'налог']):
            if '1.2.15.2' in desc_lower:
                return '1.2.15.2 Налоги на ФОТ', 'Расходы', 'Налоги на ФОТ'
            if '1.2.16.4' in desc_lower:
                return '1.2.16.3 НДС', 'Расходы', 'НДС'
            return '1.2.16 Налоги', 'Расходы', 'Налоги'
        
        # Электричество
        if any(kw in desc_lower for kw in ['latvenergo', 'elektri', 'электричеств', 'electricity']):
            return '1.2.10.5 Электричество', 'Расходы', 'Электричество'
        
        # Вода
        if any(kw in desc_lower for kw in ['rigas udens', 'ūdens', 'вода']):
            return '1.2.10.3 Вода', 'Расходы', 'Вода'
        
        # Газ
        if any(kw in desc_lower for kw in ['gāze', 'газ']):
            return '1.2.10.2 Газ', 'Расходы', 'Газ'
        
        # Мусор
        if any(kw in desc_lower for kw in ['atkritumi', 'мусор', 'eco baltia', 'clean r']):
            return '1.2.10.1 Мусор', 'Расходы', 'Вывоз мусора'
        
        # Коммунальные УК дома
        if any(kw in desc_lower for kw in ['rigas namu pārvaldnieks', 'latvijas namsaimnieks', 'biedrība', 'dzīvokļu īpašnieku']):
            return '1.2.10.6 Коммунальные УК дома', 'Расходы', 'Управляющая компания'
        
        # Связь и интернет
        if any(kw in desc_lower for kw in ['tele2', 'bite', 'tet', 'internet', 'связь']):
            return '1.2.9.1 Связь, интернет, TV', 'Расходы', 'Связь и интернет'
        
        # IT сервисы
        if any(kw in desc_lower for kw in ['google one', 'lovable', 'openai', 'chatgpt', 'browsec', 'adobe']):
            return '1.2.9.3 IT сервисы', 'Расходы', 'IT сервисы'
        
        # Реклама
        if any(kw in desc_lower for kw in ['facebook', 'facbk', 'tiktok', 'ads', 'marketing', 'реклам']):
            return '1.2.3 Оплата рекламных систем (бюджет)', 'Расходы', 'Маркетинг'
        
        # Командировочные расходы
        if any(kw in desc_lower for kw in ['flydubai', 'taxi', 'flixbus', 'bolt', 'uber', 'flix']):
            return '1.2.2 Командировочные расходы', 'Расходы', 'Командировки'
        
        # Обслуживание объектов
        if any(kw in desc_lower for kw in ['apmaksa par rēķinu', 'обслуживание', 'ремонт', 'lifti', 'taipans']):
            return '1.2.8.1 Обслуживание объектов', 'Расходы', 'Обслуживание объектов'
        
        # Страхование
        if any(kw in desc_lower for kw in ['balta', 'страхование', 'insurance']):
            return '1.2.8.2 Страхование', 'Расходы', 'Страхование'
        
        # Аренда офиса
        if any(kw in desc_lower for kw in ['аренда офиса', 'office rent']):
            return '1.2.21.1 Аренда офиса', 'Расходы', 'Аренда офиса'
        
        # Бухгалтер
        if any(kw in desc_lower for kw in ['lubova loseva', 'loseva', 'бухгалтер']):
            return '1.2.12 Бухгалтер', 'Расходы', 'Бухгалтерские услуги'
        
        # Расходы по приобретению недвижимости
        if any(kw in desc_lower for kw in ['pirkuma liguma', 'приобретение недвижимости']):
            return '2.2.7 Расходы по приобретению недвижимости', 'Расходы', 'Покупка недвижимости'
        
        # Прочее
        if any(kw in desc_lower for kw in ['notāra', 'tiesu administrācija', 'valsts kase']):
            return '2.2.4 Прочее', 'Расходы', 'Прочие расходы'
        
        # Перевод между счетами
        if any(kw in desc_lower for kw in ['currency exchange', 'конвертация', 'internal payment']):
            return 'Перевод между счетами', 'Расходы', 'Внутренний перевод'
        
        # По умолчанию для расходов
        return '1.2.8.1 Обслуживание объектов', 'Расходы', 'Обслуживание объектов'
    
    # ========== ДОХОДЫ (положительные суммы) ==========
    else:
        # Краткосрочная аренда (Airbnb, Booking)
        if any(kw in desc_lower for kw in ['airbnb', 'booking.com']):
            return '1.1.1.2 Поступления систем бронирования (Airbnb, Booking и пр.)', 'Доходы', 'Краткосрочная аренда'
        
        # Гарантийный депозит
        if any(kw in desc_lower for kw in ['depozits', 'депозит', 'deposit']):
            return '1.1.1.4 Получение гарантийного депозита', 'Доходы', 'Гарантийный депозит'
        
        # Комиссия за продажу недвижимости
        if any(kw in desc_lower for kw in ['commission', 'agency commissions', 'incoming swift payment']):
            return '1.1.4.1 Комиссия за продажу недвижимости', 'Доходы', 'Комиссия за продажу'
        
        # Внутригрупповой займ
        if any(kw in desc_lower for kw in ['loan', 'займ', 'baltic solutions']):
            return '3.1.3 Получение внутригруппового займа', 'Доходы', 'Внутригрупповой займ'
        
        # Возврат займа
        if any(kw in desc_lower for kw in ['loan return', 'возврат займа']):
            return '3.1.4 Возврат выданного внутригруппового займа', 'Доходы', 'Возврат займа'
        
        # Ввод средств
        if any(kw in desc_lower for kw in ['transfer to own account', 'между своими счетами']):
            return '3.1.1 Ввод средств', 'Доходы', 'Ввод средств'
        
        # Арендная плата (наличные)
        if any(kw in desc_lower for kw in ['наличные', 'cash', 'rent for january', 'c89-1(3)']):
            return '1.1.1.1 Арендная плата (наличные)', 'Доходы', 'Арендная плата наличные'
        
        # Компенсация коммунальных расходов
        if any(kw in desc_lower for kw in ['komunālie', 'utilities', 'компенсац', 'возмещени']):
            return '1.1.2.3 Компенсация по коммунальным расходам', 'Доходы', 'Компенсация коммунальных'
        
        # Прочие мелкие поступления (кэшбэк)
        if any(kw in desc_lower for kw in ['кэшбэк', 'cashback', 'u rok do']):
            return '1.1.2.4 Прочие мелкие поступления', 'Доходы', 'Прочие доходы'
        
        # Арендная плата (счёт)
        if any(kw in desc_lower for kw in ['арендн', 'rent', 'money added', 'ire', 'dzivoklis', 'from', 'credit of sepa']):
            return '1.1.1.3 Арендная плата (счёт)', 'Доходы', 'Арендная плата'
        
        # По умолчанию для доходов
        return '1.1.1.3 Арендная плата (счёт)', 'Доходы', 'Арендная плата'

def find_header_row(df, file_name):
    """Ищет строку с заголовками данных"""
    header_keywords = [
        'Дата транзакции', 'Date', 'Datum', 'Booking Date', 'Value Date',
        'From Account', 'Amount', 'Transaction Details', 'Əməliyyat tarixi',
        'account number', 'posting date', 'payment amount', 'Type', 'Date and time',
        'Дата', 'Плательщик/ Получатель', 'Сумма', 'Валюта',
        'Date started (UTC)', 'State', 'Description', 'Serial number'
    ]
    
    for idx in range(min(50, len(df))):
        row_values = list(df.iloc[idx].values)
        row_text = ' '.join(str(v) for v in row_values if pd.notna(v) and str(v) != '')
        for keyword in header_keywords:
            if keyword.lower() in row_text.lower():
                return idx
    return None

def parse_file(file_content, file_name):
    df = read_file(file_content, file_name)
    if df is None:
        st.error("❌ Не удалось прочитать файл")
        return []
    
    file_lower = file_name.lower()
    
    # Определяем счет и связанные с ним данные
    direction, subdirection, default_currency, account_name = get_account_info(file_name, df)
    
    # ==================== СПЕЦИАЛЬНАЯ ОБРАБОТКА ДЛЯ INDUSTRA ====================
    if 'industra' in file_lower:
        st.write(f"=== Обработка INDUSTRA: {file_name} ===")
        
        # Показываем первые строки для отладки
        st.write("Первые 15 строк файла:")
        for i in range(min(15, len(df))):
            st.write(f"Строка {i}: {list(df.iloc[i].values)}")
        
        # Ищем строку с заголовками
        header_row = None
        for idx in range(min(50, len(df))):
            row_values = list(df.iloc[idx].values)
            row_text = ' '.join(str(v) for v in row_values if pd.notna(v))
            if 'Дата транзакции' in row_text and 'Дебет(D)' in row_text:
                header_row = idx
                st.write(f"Найдена строка заголовков на индексе {idx}")
                break
        
        if header_row is None:
            header_row = find_header_row(df, file_name)
        
        if header_row is not None:
            headers = list(df.iloc[header_row].values)
            clean_headers = []
            for h in headers:
                if pd.notna(h) and str(h).strip():
                    clean_headers.append(str(h).strip())
                else:
                    clean_headers.append(f'col_{len(clean_headers)}')
            
            data_rows = []
            for idx in range(header_row + 1, len(df)):
                row = list(df.iloc[idx].values)
                if len(row) < len(clean_headers):
                    row.extend([''] * (len(clean_headers) - len(row)))
                data_rows.append(row[:len(clean_headers)])
            
            df = pd.DataFrame(data_rows, columns=clean_headers)
            st.write(f"Создан DataFrame с колонками: {list(df.columns)}")
        
        # Определяем колонки
        date_col = None
        amount_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'дата транзакции' in col_lower:
                date_col = col
            if 'дебет(d)' in col_lower:
                amount_col = col
            if 'кредит(c)' in col_lower and amount_col is None:
                amount_col = col
        
        if date_col is None and len(df.columns) > 0:
            date_col = df.columns[0]
        
        st.write(f"Столбец даты: {date_col}")
        st.write(f"Столбец суммы: {amount_col}")
        
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
                
                article, direction_type, subdir_type = get_article_by_description(description, amount)
                
                transactions.append({
                    'date': date,
                    'amount': amount,
                    'currency': default_currency,
                    'account_name': account_name,
                    'description': description[:300],
                    'article_name': article,
                    'direction': direction if direction else direction_type,
                    'subdirection': subdirection if subdirection else subdir_type
                })
                st.write(f"✅ Найдена транзакция: {date} | {amount} | {description[:50]}")
            except Exception as e:
                st.write(f"❌ Ошибка в строке {idx}: {e}")
                continue
        
        st.write(f"=== Найдено транзакций INDUSTRA: {len(transactions)} ===")
        return transactions
    
    # ==================== СПЕЦИАЛЬНАЯ ОБРАБОТКА ДЛЯ REVOLUT ====================
    if 'revolut' in file_lower:
        st.write(f"=== Обработка REVOLUT: {file_name} ===")
        
        # Ищем строку с заголовками
        header_row = None
        for idx in range(min(50, len(df))):
            row_values = list(df.iloc[idx].values)
            row_text = ' '.join(str(v) for v in row_values if pd.notna(v))
            if 'Date started (UTC)' in row_text and 'Type' in row_text:
                header_row = idx
                break
        
        if header_row is None:
            header_row = find_header_row(df, file_name)
        
        if header_row is not None:
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
        
        # Определяем колонки
        date_col = None
        amount_col = None
        type_col = None
        desc_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'started' in col_lower and 'date' in col_lower:
                date_col = col
            if col_lower == 'type':
                type_col = col
            if 'description' in col_lower:
                desc_col = col
            if 'orig amount' in col_lower:
                amount_col = col
            if 'amount' in col_lower and amount_col is None:
                amount_col = col
        
        if date_col is None:
            date_col = df.columns[0] if len(df.columns) > 0 else None
        
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
                
                transaction_type = ''
                if type_col is not None:
                    transaction_type = str(row[type_col]).upper() if pd.notna(row[type_col]) else ''
                
                description = ''
                if desc_col is not None:
                    desc_val = row[desc_col]
                    if pd.notna(desc_val):
                        description = str(desc_val)
                
                for col in df.columns:
                    if col not in [date_col, amount_col, type_col, desc_col]:
                        val = row[col]
                        if pd.notna(val) and str(val).strip() and str(val) != 'nan':
                            description += ' ' + str(val)
                
                # Корректируем знак суммы в зависимости от типа
                if transaction_type == 'TRANSFER' and amount > 0:
                    amount = -amount
                if transaction_type == 'FEE' and amount > 0:
                    amount = -amount
                
                # Определяем статью
                article, direction_type, subdir_type = get_article_by_description(description, amount)
                
                transactions.append({
                    'date': date,
                    'amount': amount,
                    'currency': default_currency,
                    'account_name': account_name,
                    'description': description[:300],
                    'article_name': article,
                    'direction': direction if direction else direction_type,
                    'subdirection': subdirection if subdirection else subdir_type
                })
            except Exception as e:
                continue
        
        st.write(f"=== Найдено транзакций REVOLUT: {len(transactions)} ===")
        return transactions
    
    # ==================== СПЕЦИАЛЬНАЯ ОБРАБОТКА ДЛЯ BUDAPEST ====================
    if 'budapest' in file_lower:
        st.write(f"=== Обработка BUDAPEST: {file_name} ===")
        
        # Ищем строку с заголовками
        header_row = None
        for idx in range(min(50, len(df))):
            row_values = list(df.iloc[idx].values)
            row_text = ' '.join(str(v) for v in row_values if pd.notna(v) and str(v).strip())
            if 'Serial number' in row_text and 'Value date' in row_text and 'Amount' in row_text:
                header_row = idx
                break
        
        if header_row is None:
            for idx in range(min(50, len(df))):
                row_values = list(df.iloc[idx].values)
                row_text = ' '.join(str(v) for v in row_values if pd.notna(v) and str(v).strip())
                if 'Value date' in row_text and 'Amount' in row_text:
                    header_row = idx
                    break
        
        if header_row is not None:
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
        
        # Ищем столбцы
        date_col = None
        amount_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'value date' in col_lower:
                date_col = col
            if 'amount' in col_lower and 'return' not in col_lower:
                amount_col = col
        
        if date_col is None and len(df.columns) > 1:
            date_col = df.columns[1]
        if amount_col is None and len(df.columns) > 9:
            amount_col = df.columns[9]
        
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
                
                article, direction_type, subdir_type = get_article_by_description(description, amount)
                
                transactions.append({
                    'date': date,
                    'amount': amount,
                    'currency': 'HUF' if 'HUF' in file_lower else 'EUR',
                    'account_name': account_name,
                    'description': description[:300],
                    'article_name': article,
                    'direction': direction if direction else direction_type,
                    'subdirection': subdirection if subdirection else subdir_type
                })
            except Exception as e:
                continue
        
        st.write(f"=== Найдено транзакций BUDAPEST: {len(transactions)} ===")
        return transactions
    
    # ==================== СПЕЦИАЛЬНАЯ ОБРАБОТКА ДЛЯ PASHA BANK ====================
    if 'pasha' in file_lower or 'kapital' in file_lower:
        st.write(f"=== Обработка PASHA/KAPITAL: {file_name} ===")
        
        # Ищем строку с заголовками
        header_row = None
        for idx in range(min(30, len(df))):
            row_values = list(df.iloc[idx].values)
            row_text = ' '.join(str(v) for v in row_values if pd.notna(v))
            if 'Əməliyyat tarixi' in row_text or 'Дата' in row_text:
                header_row = idx
                break
        
        if header_row is not None:
            headers = list(df.iloc[header_row].values)
            clean_headers = []
            for h in headers:
                if pd.notna(h) and str(h).strip():
                    clean_headers.append(str(h).strip())
                else:
                    clean_headers.append(f'col_{len(clean_headers)}')
            
            data_rows = []
            for idx in range(header_row + 1, len(df)):
                row = list(df.iloc[idx].values)
                if len(row) < len(clean_headers):
                    row.extend([''] * (len(clean_headers) - len(row)))
                data_rows.append(row[:len(clean_headers)])
            
            df = pd.DataFrame(data_rows, columns=clean_headers)
        
        # Ищем столбцы
        date_col = None
        amount_col = None
        desc_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'tarixi' in col_lower or 'дата' in col_lower:
                date_col = col
            if 'доход' in col_lower or 'расход' in col_lower:
                amount_col = col
            if 'təyinat' in col_lower or 'комментарии' in col_lower:
                desc_col = col
        
        if date_col is None and len(df.columns) > 0:
            date_col = df.columns[0]
        
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
                
                description = ''
                if desc_col is not None:
                    desc_val = row[desc_col]
                    if pd.notna(desc_val):
                        description = str(desc_val)
                
                for col in df.columns:
                    if col not in [date_col, amount_col, desc_col]:
                        val = row[col]
                        if pd.notna(val) and str(val).strip():
                            description += ' ' + str(val)
                
                # Пропускаем итоговые строки
                if any(kw in description.lower() for kw in ['dövrün sonuna', 'mövcud balans', 'toplam']):
                    continue
                
                amount = 0
                if amount_col is not None:
                    amount_val = row[amount_col]
                    if pd.notna(amount_val):
                        amount = parse_amount(amount_val)
                
                if amount == 0:
                    continue
                
                article, direction_type, subdir_type = get_article_by_description(description, amount)
                
                currency = 'AED' if 'AED' in file_lower else 'AZN' if 'AZN' in file_lower else default_currency
                
                transactions.append({
                    'date': date,
                    'amount': amount,
                    'currency': currency,
                    'account_name': account_name,
                    'description': description[:300],
                    'article_name': article,
                    'direction': direction if direction else direction_type,
                    'subdirection': subdirection if subdirection else subdir_type
                })
            except Exception as e:
                continue
        
        st.write(f"=== Найдено транзакций PASHA/KAPITAL: {len(transactions)} ===")
        return transactions
    
    # ==================== ОБЩАЯ ОБРАБОТКА ====================
    
    # Ищем строку с заголовками
    header_row = find_header_row(df, file_name)
    
    if header_row is not None:
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
    
    # Поиск столбцов даты и суммы
    date_col = None
    amount_col = None
    
    date_keywords = ['date', 'дата', 'booking date', 'posting date', 'value date', 'datum']
    for col in df.columns:
        col_lower = str(col).lower()
        for kw in date_keywords:
            if kw in col_lower:
                date_col = col
                break
        if date_col:
            break
    
    amount_keywords = ['amount', 'сумма', 'payment amount', 'orig amount', 'total amount', 'credit', 'debit', 'доход', 'расход']
    for col in df.columns:
        col_lower = str(col).lower()
        for kw in amount_keywords:
            if kw in col_lower:
                amount_col = col
                break
        if amount_col:
            break
    
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]
    if amount_col is None and len(df.columns) > 1:
        amount_col = df.columns[1]
    
    transactions = []
    for idx in range(len(df)):
        try:
            row = df.iloc[idx]
            
            date = ''
            if date_col is not None:
                date_val = row[date_col]
                if pd.notna(date_val) and str(date_val).strip():
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
            
            if abs(amount) > 1000000:
                continue
            
            description = ''
            for col in df.columns:
                if col not in [date_col, amount_col]:
                    val = row[col]
                    if pd.notna(val) and str(val).strip() and str(val) != 'nan':
                        description += str(val) + ' '
            
            article, direction_type, subdir_type = get_article_by_description(description, amount)
            
            currency = default_currency
            if 'CZK' in file_lower:
                currency = 'CZK'
            elif 'HUF' in file_lower:
                currency = 'HUF'
            elif 'RUB' in file_lower:
                currency = 'RUB'
            
            transactions.append({
                'date': date,
                'amount': amount,
                'currency': currency,
                'account_name': account_name,
                'description': description[:300],
                'article_name': article,
                'direction': direction if direction else direction_type,
                'subdirection': subdirection if subdirection else subdir_type
            })
        except Exception as e:
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
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Все транзакции')
                output.seek(0)
                st.download_button(
                    "📥 Скачать сводный Excel", 
                    data=output, 
                    file_name="сводка.xlsx"
                )
