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
    date_str = str(date_str)
    # Убираем время
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]
    # Формат DD.MM.YYYY
    if '.' in date_str:
        parts = date_str.split('.')
        if len(parts) == 3 and len(parts[2]) == 4:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    # Формат YYYY-MM-DD
    if '-' in date_str and len(date_str) >= 10:
        return date_str[:10]
    return date_str[:10] if len(date_str) >= 10 else date_str

def parse_amount(amount_str):
    if pd.isna(amount_str):
        return 0
    amount_str = str(amount_str).strip()
    if amount_str == '' or amount_str == 'nan':
        return 0
    
    # Убираем валюту и лишние символы
    amount_str = amount_str.replace(',', '.').replace(' ', '')
    # Убираем знаки + и - в начале, но сохраняем для определения
    has_minus = amount_str.startswith('-') or amount_str.startswith('-+')
    amount_str = re.sub(r'[^0-9\.\-]', '', amount_str)
    if amount_str == '' or amount_str == '-':
        return 0
    try:
        val = float(amount_str)
        if has_minus and val > 0:
            val = -val
        return val
    except:
        match = re.search(r'(-?\d+\.?\d*)', amount_str)
        if match:
            try:
                return float(match.group(1))
            except:
                return 0
        return 0

def get_article(description, amount, transaction_type=None):
    """Определение статьи на основе описания и суммы"""
    desc_lower = description.lower()
    
    # Проверяем, является ли строка итоговой (не транзакция)
    if any(kw in desc_lower for kw in ['dövrün sonuna balans', 'mövcud balans', 'start balance', 'final balance', 'debit turnover', 'credit turnover']):
        return None, None, None, None
    
    # ========== ДОХОДЫ (положительные суммы) ==========
    if amount > 0:
        # 1.1.1.2 Поступления систем бронирования (Airbnb, Booking)
        if any(kw in desc_lower for kw in ['airbnb', 'booking.com', 'booking b.v.']):
            return '1.1.1.2 Поступления систем бронирования (Airbnb, Booking и пр.)', 'Доходы', 'Краткосрочная аренда', amount
        
        # 1.1.1.4 Получение гарантийного депозита
        if any(kw in desc_lower for kw in ['depozits', 'депозит', 'deposit', 'garantijas depozits']):
            return '1.1.1.4 Получение гарантийного депозита', 'Доходы', 'Гарантийный депозит', amount
        
        # 1.1.4.1 Комиссия за продажу недвижимости (Nomiqa, Bunda)
        if any(kw in desc_lower for kw in ['commission', 'agency commissions', 'marketing and advertisement', 'consultancy fees', 'комиссия за продажу', 'incoming swift payment']):
            return '1.1.4.1 Комиссия за продажу недвижимости', 'Доходы', 'Комиссия за продажу', amount
        
        # 3.1.3 Получение внутригруппового займа
        if any(kw in desc_lower for kw in ['loan', 'займ', 'baltic solutions', 'payment acc loan agreement']):
            return '3.1.3 Получение внутригруппового займа', 'Доходы', 'Внутригрупповой займ', amount
        
        # 3.1.4 Возврат выданного внутригруппового займа
        if any(kw in desc_lower for kw in ['loan return', 'возврат займа']):
            return '3.1.4 Возврат выданного внутригруппового займа', 'Доходы', 'Возврат займа', amount
        
        # 3.1.1 Ввод средств
        if any(kw in desc_lower for kw in ['transfer to own account', 'между своими счетами']):
            return '3.1.1 Ввод средств', 'Доходы', 'Ввод средств', amount
        
        # 1.1.1.1 Арендная плата (наличные)
        if any(kw in desc_lower for kw in ['наличные', 'cash', 'rent for january']):
            return '1.1.1.1 Арендная плата (наличные)', 'Доходы', 'Арендная плата наличные', amount
        
        # 1.1.2.3 Компенсация по коммунальным расходам
        if any(kw in desc_lower for kw in ['komunālie', 'utilities', 'компенсац', 'возмещени']):
            return '1.1.2.3 Компенсация по коммунальным расходам', 'Доходы', 'Компенсация коммунальных', amount
        
        # 1.1.2.4 Прочие мелкие поступления (кэшбэк, возвраты)
        if any(kw in desc_lower for kw in ['кэшбэк', 'cashback', 'refund', 'возврат', 'прочие', 'u rok do']):
            return '1.1.2.4 Прочие мелкие поступления', 'Доходы', 'Прочие доходы', amount
        
        # 1.1.1.3 Арендная плата (счёт) — только для TOPUP в Revolut
        if transaction_type == 'TOPUP' or any(kw in desc_lower for kw in ['арендн', 'rent', 'money added', 'ire', 'dzivoklis', 'apmaksa par dzivokli', 'ires maksa', 'rekina numurs']):
            return '1.1.1.3 Арендная плата (счёт)', 'Доходы', 'Арендная плата', amount
        
        # По умолчанию для доходов
        return '1.1.1.3 Арендная плата (счёт)', 'Доходы', 'Арендная плата', amount
    
    # ========== РАСХОДЫ (отрицательные суммы) ==========
    else:
        # 1.2.17 РКО — банковские комиссии
        if any(kw in desc_lower for kw in ['комиссия', 'commission', 'fee', 'charge', 'maintenance', 'rko', 'subscription', 'atm withdrawal', 'foreign exchange', 'плата за обслуживание', 'service package', 'számlakivonat díja', 'netbankár monthly fee', 'charge for', 'conversion fee']):
            return '1.2.17 РКО', 'Расходы', 'Банковские комиссии', amount
        
        # 1.2.15.1 Зарплата
        if any(kw in desc_lower for kw in ['зарплат', 'salary', 'darba alga', 'algas izmaksa', 'darba algas izmaksa']):
            return '1.2.15.1 Зарплата', 'Расходы', 'Зарплата', amount
        
        # 1.2.15.2 Налоги на ФОТ
        if any(kw in desc_lower for kw in ['nodokļu nomaksa', 'vid', 'budžets', 'налог', 'valsts budžets']):
            return '1.2.15.2 Налоги на ФОТ', 'Расходы', 'Налоги на ФОТ', amount
        
        # 1.2.16.3 НДС
        if any(kw in desc_lower for kw in ['value added tax', 'vat', 'ндс', 'pvn']):
            return '1.2.16.3 НДС', 'Расходы', 'НДС', amount
        
        # 1.2.16.1 Налог на недвижимость
        if any(kw in desc_lower for kw in ['nekustamā īpašuma nodoklis', 'налог на недвижимость', 'pašvaldība']):
            return '1.2.16.1 Налог на недвижимость', 'Расходы', 'Налог на недвижимость', amount
        
        # 1.2.10.5 Электричество
        if any(kw in desc_lower for kw in ['latvenergo', 'elektri', 'электричеств', 'electricity']):
            return '1.2.10.5 Электричество', 'Расходы', 'Электричество', amount
        
        # 1.2.10.2 Газ
        if any(kw in desc_lower for kw in ['gāze', 'газ']):
            return '1.2.10.2 Газ', 'Расходы', 'Газ', amount
        
        # 1.2.10.3 Вода
        if any(kw in desc_lower for kw in ['rigas udens', 'ūdens', 'вода']):
            return '1.2.10.3 Вода', 'Расходы', 'Вода', amount
        
        # 1.2.10.1 Мусор
        if any(kw in desc_lower for kw in ['atkritumi', 'мусор', 'eco baltia', 'clean r']):
            return '1.2.10.1 Мусор', 'Расходы', 'Вывоз мусора', amount
        
        # 1.2.10.6 Коммунальные УК дома
        if any(kw in desc_lower for kw in ['rigas namu pārvaldnieks', 'latvijas namsaimnieks', 'biedrība', 'dzīvokļu īpašnieku']):
            return '1.2.10.6 Коммунальные УК дома', 'Расходы', 'Управляющая компания', amount
        
        # 1.2.9.1 Связь, интернет, TV
        if any(kw in desc_lower for kw in ['tele2', 'bite', 'tet', 'internet', 'связь', 'telenet']):
            return '1.2.9.1 Связь, интернет, TV', 'Расходы', 'Связь и интернет', amount
        
        # 1.2.9.3 IT сервисы
        if any(kw in desc_lower for kw in ['asana', 'albato', 'slack', 'google one', 'lovable', 'openai', 'chatgpt', 'browsec', 'it сервисы', 'lovable.dev']):
            return '1.2.9.3 IT сервисы', 'Расходы', 'IT сервисы', amount
        
        # 1.2.3 Оплата рекламных систем (бюджет)
        if any(kw in desc_lower for kw in ['facebook', 'facbk', 'tiktok', 'ads', 'marketing', 'реклам', 'meta', 'airbnb', 'airbnb payments']):
            return '1.2.3 Оплата рекламных систем (бюджет)', 'Расходы', 'Маркетинг', amount
        
        # 1.2.2 Командировочные расходы
        if any(kw in desc_lower for kw in ['careem', 'flydubai', 'taxi', 'командир', 'flixbus', 'bolt', 'uber', 'inflight internet', 'flix']):
            return '1.2.2 Командировочные расходы', 'Расходы', 'Командировки', amount
        
        # 1.2.8.1 Обслуживание объектов
        if any(kw in desc_lower for kw in ['apmaksa par rēķinu', 'обслуживание', 'ремонт', 'lifti', 'taipans', 'sidorans', 'komval', 'rīgas lifti', 'sedlecky kaolin']):
            return '1.2.8.1 Обслуживание объектов', 'Расходы', 'Обслуживание объектов', amount
        
        # 1.2.8.2 Страхование
        if any(kw in desc_lower for kw in ['balta', 'страхование', 'insurance']):
            return '1.2.8.2 Страхование', 'Расходы', 'Страхование', amount
        
        # 1.2.21.1 Аренда офиса
        if any(kw in desc_lower for kw in ['аренда офиса', 'office rent', 'icare od']):
            return '1.2.21.1 Аренда офиса', 'Расходы', 'Аренда офиса', amount
        
        # 1.2.12 Бухгалтер
        if any(kw in desc_lower for kw in ['lubova loseva', 'loseva', 'бухгалтер']):
            return '1.2.12 Бухгалтер', 'Расходы', 'Бухгалтерские услуги', amount
        
        # 1.2.37 Возврат гарантийных депозитов
        if any(kw in desc_lower for kw in ['deposit return', 'depozīta atgriešana', 'возврат депозита']):
            return '1.2.37 Возврат гарантийных депозитов', 'Расходы', 'Возврат депозита', amount
        
        # 2.2.7 Расходы по приобретению недвижимости
        if any(kw in desc_lower for kw in ['pirkuma liguma', 'приобретение недвижимости']):
            return '2.2.7 Расходы по приобретению недвижимости', 'Расходы', 'Покупка недвижимости', amount
        
        # 2.2.4 Прочее (судебные, нотариусы)
        if any(kw in desc_lower for kw in ['notāra', 'tiesu administrācija', 'valsts kase']):
            return '2.2.4 Прочее', 'Расходы', 'Прочие расходы', amount
        
        # 4.1 Перевод между счетами
        if any(kw in desc_lower for kw in ['currency exchange', 'конвертация', 'transfer to own account', 'между своими счетами', 'internal payment']):
            return 'Перевод между счетами', 'Расходы', 'Внутренний перевод', amount
        
        # По умолчанию для расходов
        return '1.2.8.1 Обслуживание объектов', 'Расходы', 'Обслуживание объектов', amount

def find_header_row(df, file_name):
    """Ищет строку с заголовками данных"""
    header_keywords = [
        'Дата транзакции', 'Date', 'Datum', 'Booking Date', 'Value Date',
        'From Account', 'Amount', 'Transaction Details', 'Əməliyyat tarixi',
        'account number', 'posting date', 'payment amount', 'Type', 'Date and time',
        'Дата', 'Плательщик/ Получатель', 'Сумма', 'Валюта',
        'Date started (UTC)', 'Type', 'State', 'Description'
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
    
    # ==================== СПЕЦИАЛЬНАЯ ОБРАБОТКА ДЛЯ REVOLUT ====================
    if 'revolut' in file_lower:
        st.write(f"=== Специальная обработка REVOLUT: {file_name} ===")
        
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
        type_col = None
        desc_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'started' in col_lower and 'date' in col_lower:
                date_col = col
            if 'amount' in col_lower and 'orig' in col_lower:
                amount_col = col
            if col_lower == 'type':
                type_col = col
            if 'description' in col_lower:
                desc_col = col
        
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
                
                # Определяем тип операции для правильной классификации
                transaction_type = ''
                if type_col is not None:
                    transaction_type = str(row[type_col]).upper() if pd.notna(row[type_col]) else ''
                
                # Собираем описание
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
                
                article, direction, subdir, amount = get_article(description, amount, transaction_type)
                
                if article is None:
                    continue
                
                account_name = file_name.replace('.csv', '').replace('.xlsx', '').replace('.xls', '')
                
                transactions.append({
                    'date': date,
                    'amount': amount,
                    'currency': 'EUR',
                    'account_name': account_name,
                    'description': description[:300],
                    'article_name': article,
                    'direction': direction,
                    'subdirection': subdir
                })
            except Exception as e:
                continue
        
        return transactions
    
    # ==================== СПЕЦИАЛЬНАЯ ОБРАБОТКА ДЛЯ PASHA BANK ====================
    if 'pasha' in file_lower:
        st.write(f"=== Специальная обработка PASHA BANK: {file_name} ===")
        
        # Ищем строку с заголовками
        header_row = None
        for idx in range(min(30, len(df))):
            row_values = list(df.iloc[idx].values)
            row_text = ' '.join(str(v) for v in row_values if pd.notna(v))
            if 'Əməliyyat tarixi' in row_text and 'İcra tarixi' in row_text:
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
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'tarixi' in col_lower:
                date_col = col
            if 'доход' in col_lower:
                amount_col = col
        
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
                
                # Пропускаем итоговые строки
                desc_text = ''
                for col in df.columns:
                    val = row[col]
                    if pd.notna(val) and str(val).strip():
                        desc_text += str(val) + ' '
                
                if any(kw in desc_text.lower() for kw in ['dövrün sonuna', 'mövcud balans']):
                    continue
                
                amount = 0
                if amount_col is not None:
                    amount_val = row[amount_col]
                    if pd.notna(amount_val):
                        amount = parse_amount(amount_val)
                
                if amount == 0:
                    continue
                
                description = desc_text[:300]
                article, direction, subdir, amount = get_article(description, amount)
                
                if article is None:
                    continue
                
                account_name = file_name.replace('.xlsx', '').replace('.xls', '')
                currency = 'AED' if 'AED' in file_lower else 'AZN' if 'AZN' in file_lower else 'EUR'
                
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
    
    date_keywords = ['date', 'дата', 'booking date', 'posting date', 'value date', 'datum', 'transaction date']
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
    
    # Обработка транзакций
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
            
            if not ('2026' in date or '2025' in date):
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
            
            article, direction, subdir, amount = get_article(description, amount)
            
            if article is None:
                continue
            
            account_name = file_name
            for ext in ['.xls', '.xlsx', '.csv', '.CSV', '.xlsm']:
                account_name = account_name.replace(ext, '')
            
            currency = 'EUR'
            if 'CZK' in str(df.columns) or 'czk' in file_lower:
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
                'direction': direction,
                'subdirection': subdir
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
                    st.download_button("📥 Скачать Excel", data=output, file_name=f"анализ_{uploaded_file
