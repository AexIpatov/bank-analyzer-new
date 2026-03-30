import streamlit as st
import pandas as pd
import io
import tempfile
import os
import chardet
import re
from datetime import datetime
from io import BytesIO
import numpy as np
from typing import List, Dict, Tuple, Optional
import csv

st.set_page_config(page_title="Финансовый аналитик выписок", page_icon="📈", layout="wide")

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
.success-box {
    background-color: #d4edda;
    border: 1px solid #c3e6cb;
    border-radius: 10px;
    padding: 1rem;
    margin: 1rem 0;
}
.warning-box {
    background-color: #fff3cd;
    border: 1px solid #ffeaa7;
    border-radius: 10px;
    padding: 1rem;
    margin: 1rem 0;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>📊 Финансовый аналитик выписок v5.1</h1><p>Полная поддержка всех форматов банковских выписок</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🧠 О программе")
    st.markdown("**Поддерживаемые форматы:**")
    st.markdown("- Excel (.xlsx, .xls)")
    st.markdown("- CSV (разные разделители)")
    st.markdown("- Текстовые файлы")
    st.markdown("---")
    st.markdown("**Поддерживаемые банки:**")
    st.markdown("- Pasha Bank (AZN, AED)")
    st.markdown("- CSOB Bank (CZK)")
    st.markdown("- UniCredit Bank (CZK)")
    st.markdown("- Industra Bank (EUR)")
    st.markdown("- Kapital Bank (AZN)")
    st.markdown("- Mashreq Bank (AED)")
    st.markdown("- WIO Bank (AED)")
    st.markdown("- Revolut (EUR)")
    st.markdown("- Paysera (EUR)")
    st.markdown("---")
    st.markdown("**Версия 5.1** — исправлена обработка всех операций")

# ==================== КОНФИГУРАЦИЯ ====================
class Config:
    """Конфигурация приложения"""
    # Форматы дат для парсинга
    DATE_FORMATS = [
        "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d",
        "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d", "%d.%m.%y",
        "%d/%m/%y", "%y-%m-%d", "%d-%b-%y", "%d-%b-%Y",
        "%b %d, %Y", "%d %b %Y", "%Y%m%d"
    ]
    
    # Разделители для CSV
    CSV_DELIMITERS = [';', ',', '\t', '|', ':', '~']
    
    # Кодировки для текстовых файлов
    ENCODINGS = ['utf-8', 'utf-8-sig', 'windows-1251', 'cp1251', 'iso-8859-1', 'latin-1', 'cp1252', 'mac_roman']
    
    # Валюты
    CURRENCIES = {
        'EUR': 'EUR',
        'CZK': 'CZK',
        'HUF': 'HUF',
        'AZN': 'AZN',
        'AED': 'AED',
        'RUB': 'RUB',
        'USD': 'USD',
        'GBP': 'GBP',
        'PLN': 'PLN'
    }

# ==================== КЛАСС УМНОГО ДЕТЕКТОРА ЗАГОЛОВКОВ ====================
class HeaderDetector:
    """Умный детектор заголовков с поддержкой всех форматов"""
    def __init__(self):
        self.header_patterns = {
            'date': [
                'date', 'дата', 'datum', 'dátum', 'transaction date', 'value date',
                'booking date', 'дата транзакции', 'дата операции', 'posting date',
                'Date started (UTC)', 'Дата', 'Date completed (UTC)', 'дата валютирования',
                'value date', 'booking date', 'posting date', 'datum transakce',
                'datum zaúčtování', 'data', 'data operacji', 'transaction date/time',
                'date/time', 'date of transaction'
            ],
            'amount': [
                'amount', 'сумма', 'összeg', 'betrag', 'дебет', 'кредит', 'debit(d)',
                'credit(c)', 'сумма списания', 'сумма зачисления', 'доход', 'расход',
                'orig amount', 'payment amount', 'Total amount', 'Payment currency',
                'Amount', 'Сумма', 'payment amount', 'сумма платежа', 'částka',
                'kwota', 'importo', 'montant', 'betrag', 'bedrag', 'importe',
                'сумма операции', 'сумма транзакции', 'transaction amount'
            ],
            'debit': [
                'debit', 'дебет', 'расход', 'withdrawal', 'списание', 'debet', 'Расход',
                'дебет(d)', 'debit(d)', 'списано', 'снятие', 'odchozí platba',
                'wydatek', 'uitgaand', 'salida', 'sortie', 'ausgang'
            ],
            'credit': [
                'credit', 'кредит', 'доход', 'deposit', 'зачисление', 'Доход',
                'кредит(c)', 'credit(c)', 'зачислено', 'пополнение', 'příchozí platba',
                'przychód', 'inkomend', 'entrada', 'entrée', 'eingang'
            ],
            'description': [
                'description', 'описание', 'leírás', 'beschreibung', 'details', 'детали',
                'transaction details', 'назначение платежа', 'примечание', 'narrative',
                'information', 'Transaction Details', 'Purpose of payment', 'particulars',
                'beneficiary', 'Description', 'Назначение платежа', 'Информация о транзакции',
                'Транзакция', 'Описание', 'message', 'сообщение', 'details', 'детали операции',
                'popis', 'descrizione', 'description de la transaction', 'transactiebeschrijving',
                'descripción', 'beschrijving', 'komentář', 'uwagi', 'причина платежа'
            ],
            'balance': [
                'balance', 'остаток', 'egyenleg', 'saldo', 'closing balance',
                'конечный остаток', 'баланс', 'остаток на счете', 'zůstatek',
                'bilans', 'saldo conto', 'solde', 'saldo de la cuenta'
            ],
            'payer': [
                'payer', 'плательщик', 'отправитель', 'sender', 'контрагент',
                'counterparty', 'получатель', 'beneficiary', 'recipient',
                'имя плательщика', 'имя получателя', 'platitel', 'nadawca',
                'pagatore', 'payeur', 'betaler', 'remitente', 'zahradnik',
                'odbiorca', 'destinatario', 'beneficiario'
            ],
            'account': [
                'account', 'счет', 'account number', 'номер счета', 'iban',
                'номер счета получателя', 'номер счета плательщика', 'číslo účtu',
                'numer konta', 'conto', 'compte', 'rekening', 'cuenta',
                'bank account', 'bankovní účet', 'konto bankowe'
            ],
            'currency': [
                'currency', 'валюта', 'валюта платежа', 'payment currency',
                'account currency', 'валюта счета', 'měna', 'waluta',
                'valuta', 'devise', 'valuta del conto', 'moneda'
            ],
            'type': [
                'type', 'тип', 'вид операции', 'operation type', 'transaction type',
                'typ', 'tipo', 'type de transaction', 'soort', 'tipo de operación',
                'kategorie', 'category', 'категория'
            ]
        }
        
        self.file_patterns = {
            'industra': [r'industra', r'индустра', r'plavas'],
            'revolut': [r'revolut', r'револют'],
            'budapest': [r'budapest', r'будапешт'],
            'pasha': [r'pasha', r'паша', r'bunda'],
            'kapital': [r'kapital', r'капитал', r'saida'],
            'csob': [r'csob', r'čsob'],
            'unicredit': [r'unicredit', r'uni credit', r'garpiz', r'koruna', r'twohills'],
            'mashreq': [r'mashreq'],
            'wio': [r'wio'],
            'wise': [r'wise'],
            'paysera': [r'paysera'],
            'seb': [r'seb'],
            'swedbank': [r'swedbank'],
            'luminor': [r'luminor']
        }
    
    def detect_file_type(self, filename: str) -> str:
        """Определение типа файла по имени"""
        filename_lower = filename.lower()
        for file_type, patterns in self.file_patterns.items():
            for pattern in patterns:
                if re.search(pattern, filename_lower, re.IGNORECASE):
                    return file_type
        return "unknown"
    
    def find_header_row(self, df: pd.DataFrame, max_rows_to_check: int = 50) -> int:
        """Нахождение строки с заголовками"""
        if df.empty:
            return -1
        
        rows_to_check = min(max_rows_to_check, len(df))
        best_score = 0
        best_row = -1
        
        for row_idx in range(rows_to_check):
            row = df.iloc[row_idx]
            score = self._calculate_header_score(row)
            if score > best_score:
                best_score = score
                best_row = row_idx
        
        # Минимальный порог для определения заголовка
        if best_score >= 2:
            return best_row
        return -1
    
    def _calculate_header_score(self, row: pd.Series) -> int:
        """Расчет оценки строки как заголовка"""
        score = 0
        header_keywords_found = set()
        
        for cell in row:
            if pd.isna(cell):
                continue
            
            cell_str = str(cell).lower().strip()
            
            # Проверка на ключевые слова заголовков
            for category, keywords in self.header_patterns.items():
                for kw in keywords:
                    if kw in cell_str:
                        if category not in header_keywords_found:
                            header_keywords_found.add(category)
                            score += 2
                        else:
                            score += 1
                        break
            
            # Штраф за числовые значения
            if re.match(r'^-?\d+[.,]\d{2}$', cell_str.replace(' ', '')):
                score -= 2
            
            # Штраф за даты
            if re.match(r'\d{4}[-./]\d{1,2}[-./]\d{1,2}', cell_str):
                score -= 2
        
        return max(0, score)
    
    def validate_header_row(self, df: pd.DataFrame, header_row: int) -> bool:
        """Валидация найденной строки заголовков"""
        if header_row < 0 or header_row >= len(df):
            return False
        
        header = df.iloc[header_row]
        numeric_count = 0
        total_cells = len(header)
        
        for cell in header:
            if pd.isna(cell):
                continue
            
            cell_str = str(cell).strip()
            
            # Проверка на числовое значение
            try:
                float(cell_str.replace(',', '.'))
                numeric_count += 1
            except:
                # Проверка на дату
                if re.match(r'\d{4}[-./]\d{1,2}[-./]\d{1,2}', cell_str):
                    numeric_count += 1
        
        # Если более 40% ячеек числовые, это не заголовок
        return numeric_count <= total_cells * 0.4

# ==================== ФУНКЦИИ ПАРСИНГА ====================
def detect_csv_delimiter(file_path: str, sample_size: int = 2048) -> str:
    """Автоматическое определение разделителя CSV"""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        sample = f.read(sample_size)
    
    # Подсчет различных разделителей
    delimiter_counts = {}
    for delimiter in Config.CSV_DELIMITERS:
        count = sample.count(delimiter)
        if count > 0:
            delimiter_counts[delimiter] = count
    
    if not delimiter_counts:
        # Проверяем, есть ли кавычки и запятые
        if '"' in sample and ',' in sample:
            return ','
        return ','  # По умолчанию запятая
    
    # Возвращаем наиболее часто встречающийся разделитель
    return max(delimiter_counts.items(), key=lambda x: x[1])[0]

def detect_file_encoding(file_path: str, sample_size: int = 4096) -> str:
    """Определение кодировки файла"""
    with open(file_path, 'rb') as f:
        raw_data = f.read(sample_size)
    
    result = chardet.detect(raw_data)
    encoding = result['encoding'] if result['encoding'] else 'utf-8'
    
    # Корректировка распространенных кодировок
    if encoding.lower() in ['windows-1251', 'cp1251']:
        return 'windows-1251'
    elif encoding.lower() == 'iso-8859-1':
        return 'latin-1'
    elif encoding.lower() == 'ascii':
        return 'utf-8'
    
    return encoding

def read_file(file_content: bytes, file_name: str) -> pd.DataFrame:
    """Чтение файла с автоматическим определением формата"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        file_ext = os.path.splitext(file_name)[1].lower()
        
        # Обработка Excel файлов
        if file_ext in ['.xlsx', '.xls']:
            try:
                # Пробуем прочитать все листы
                excel_file = pd.ExcelFile(tmp_path, engine='openpyxl')
                sheet_names = excel_file.sheet_names
                
                # Если есть лист с транзакциями, используем его
                for sheet in sheet_names:
                    sheet_lower = sheet.lower()
                    if any(keyword in sheet_lower for keyword in ['транзакции', 'transactions', 'операции', 'operations', 'statement', 'выписка']):
                        df = pd.read_excel(tmp_path, sheet_name=sheet, header=None, engine='openpyxl')
                        break
                else:
                    # Используем первый лист
                    df = pd.read_excel(tmp_path, header=None, engine='openpyxl')
                
                return df
            except Exception as e:
                # Fallback на стандартный парсер
                try:
                    df = pd.read_excel(tmp_path, header=None)
                except:
                    # Читаем как CSV если Excel не работает
                    encoding = detect_file_encoding(tmp_path)
                    delimiter = detect_csv_delimiter(tmp_path)
                    df = pd.read_csv(tmp_path, sep=delimiter, encoding=encoding, header=None,
                                    engine='python', on_bad_lines='skip')
                return df
        
        # Обработка CSV и текстовых файлов
        else:
            # Определяем кодировку
            encoding = detect_file_encoding(tmp_path)
            
            # Определяем разделитель
            delimiter = detect_csv_delimiter(tmp_path)
            
            # Читаем файл с учетом особенностей
            try:
                # Пробуем прочитать как CSV с определенным разделителем
                df = pd.read_csv(tmp_path, sep=delimiter, encoding=encoding, header=None,
                                engine='python', on_bad_lines='skip', quotechar='"')
            except Exception as e:
                # Если не получается, пробуем другие разделители
                for delim in Config.CSV_DELIMITERS:
                    if delim != delimiter:
                        try:
                            df = pd.read_csv(tmp_path, sep=delim, encoding=encoding, header=None,
                                            engine='python', on_bad_lines='skip', quotechar='"')
                            break
                        except:
                            continue
                else:
                    # Если все разделители не подходят, читаем построчно
                    with open(tmp_path, 'r', encoding=encoding, errors='ignore') as f:
                        lines = f.readlines()
                    
                    data = []
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Пробуем разные разделители
                        parts_found = False
                        for delim in Config.CSV_DELIMITERS:
                            if delim in line:
                                parts = [part.strip('"\' ') for part in line.split(delim)]
                                data.append(parts)
                                parts_found = True
                                break
                        
                        if not parts_found:
                            # Если разделитель не найден, используем всю строку как одну колонку
                            data.append([line])
                    
                    # Выравниваем количество колонок
                    if data:
                        max_cols = max(len(row) for row in data)
                        for row in data:
                            while len(row) < max_cols:
                                row.append('')
                        df = pd.DataFrame(data)
                    else:
                        df = pd.DataFrame()
            
            return df
    
    except Exception as e:
        st.error(f"Ошибка при чтении файла {file_name}: {str(e)}")
        return pd.DataFrame()
    
    finally:
        # Удаляем временный файл
        try:
            os.unlink(tmp_path)
        except:
            pass

def parse_date(date_str) -> str:
    """Парсинг даты из различных форматов"""
    if pd.isna(date_str):
        return ''
    
    date_str = str(date_str).strip()
    
    # Удаляем время, если есть
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    
    # Удаляем лишние символы
    date_str = re.sub(r'[^\d./\- :]', '', date_str)
    
    # Пробуем все форматы
    for fmt in Config.DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except:
            continue
    
    # Специальная обработка для формата DD.MM.YYYY
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
    
    # Обработка для формата YYYYMMDD
    if re.match(r'^\d{8}$', date_str):
        try:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        except:
            pass
    
    # Если ничего не помогло, возвращаем исходную строку
    return date_str

def parse_amount(amount_str, is_debit_col=False, is_credit_col=False, description="") -> float:
    """Парсинг суммы с учетом особенностей разных банков"""
    if pd.isna(amount_str):
        return 0.0
    
    amount_str = str(amount_str).strip()
    
    # Очистка строки
    if amount_str in ['', 'nan', '-', 'None', 'null', 'NaN', 'N/A', 'n/a']:
        return 0.0
    
    original_str = amount_str
    
    # Обработка специальных форматов (Industra Bank: "-+50.00")
    if amount_str.startswith('-+'):
        amount_str = '-' + amount_str[2:]
    elif amount_str.startswith('+-'):
        amount_str = '-' + amount_str[2:]
    
    # Удаление валюты в конце или начале
    amount_str = re.sub(r'\s*[A-Z]{3}\s*$', '', amount_str)
    amount_str = re.sub(r'^\s*[A-Z]{3}\s*', '', amount_str)
    
    # Удаление пробелов (для тысяч)
    amount_str = amount_str.replace(' ', '').replace('\xa0', '')
    
    # Замена запятой на точку
    amount_str = amount_str.replace(',', '.')
    
    # Удаление всех нечисловых символов кроме минуса и точки
    amount_str = re.sub(r'[^\d.\-]', '', amount_str)
    
    # Если строка пустая после очистки
    if not amount_str or amount_str == '-':
        return 0.0
    
    # Определение знака
    is_negative = amount_str.startswith('-')
    amount_str = amount_str.lstrip('-')
    
    # Если есть явное указание на дебет/кредит
    if is_debit_col:
        is_negative = True
    elif is_credit_col:
        is_negative = False
    
    # Анализ описания для определения знака
    desc_lower = description.lower() if description else ""
    if not is_negative:
        # Ключевые слова для расходов
        expense_keywords = [
            'fee', 'charge', 'комиссия', 'tax', 'налог', 'to ', 'transfer to',
            'списание', 'снятие', 'оплата', 'payment', 'платеж', 'withdrawal',
            'дебит', 'расход', 'стоимость', 'цена', 'cost', 'price', 'purchase',
            'buy', 'купить', 'оплачено', 'paid', 'withdraw', 'снятие средств',
            'вывод средств', 'отправлено', 'sent', 'перевод', 'transfer',
            'плата', 'оплата за', 'оплата по', 'оплата услуги'
        ]
        
        income_keywords = [
            'from', 'received', 'incoming', 'deposit', 'зачисление', 'пополнение',
            'возврат', 'refund', 'компенсация', 'compensation', 'income',
            'доход', 'поступление', 'receipt', 'получено', 'got', 'received from'
        ]
        
        # Проверяем ключевые слова
        has_expense = any(keyword in desc_lower for keyword in expense_keywords)
        has_income = any(keyword in desc_lower for keyword in income_keywords)
        
        if has_expense and not has_income:
            is_negative = True
        elif has_income and not has_expense:
            is_negative = False
    
    try:
        value = float(amount_str)
        return -abs(value) if is_negative else abs(value)
    except:
        # Пробуем извлечь число из строки
        numbers = re.findall(r'-?\d+[.,]\d+', original_str)
        if numbers:
            try:
                value = float(numbers[0].replace(',', '.'))
                return -abs(value) if is_negative else abs(value)
            except:
                pass
        
        # Пробуем найти целые числа
        numbers = re.findall(r'-?\d+', original_str)
        if numbers:
            try:
                value = float(numbers[0])
                return -abs(value) if is_negative else abs(value)
            except:
                pass
        
        return 0.0

# ==================== ОПРЕДЕЛЕНИЕ СТАТЕЙ ====================
class ArticleClassifier:
    """Классификатор статей учета"""
    def __init__(self):
        # Родительские статьи
        self.parent_articles = {
            '1.1.1': 'Поступления за аренду недвижимости и земельных участков',
            '1.1.2': 'Прочие поступления',
            '1.1.4': 'Поступления за оказание услуг',
            '1.2.1': 'Закупка до 1000 евро',
            '1.2.2': 'Командировочные расходы',
            '1.2.3': 'Оплата рекламных систем (бюджет)',
            '1.2.8': 'Обслуживание объектов',
            '1.2.9': 'Услуги ИТ и связи',
            '1.2.10': 'Коммунальные платежи',
            '1.2.15': 'Зарплата и налоги на ФОТ',
            '1.2.16': 'Налоги',
            '1.2.17': 'РКО',
            '1.2.21': 'Офисные расходы',
            '1.2.24': 'Расходы по отдельному бизнесу',
            '1.2.27': 'Расходы в ожидании возмещения ЗП по другим бизнесам',
            '1.2.28': 'Расходы, произведённые за другие компании группы (к возмещению)',
            '1.2.33': 'Непредвиденные расходы',
            '1.2.34': 'Вознаграждение инвестора',
            '1.2.37': 'Возврат гарантийных депозитов',
            '1.2.38': 'НДС в составе комиссий банка',
            '2.2.4': 'Прочее',
            '2.2.7': 'Расходы по приобретению недвижимости',
            '2.2.9': 'Перемещение расход отдельный бизнес',
            '3.1.1': 'Ввод средств',
            '3.1.3': 'Получение внутригруппового займа',
            '3.1.4': 'Возврат выданного внутригруппового займа'
        }
        
        # Статьи расходов
        self.expense_articles = {
            '1.2.17 РКО': [
                'комиссия', 'commission', 'fee', 'charge', 'maintenance', 'rko', 'subscription',
                'atm withdrawal', 'плата за обслуживание', 'service package', 'számlakivonat díja',
                'netbankár monthly fee', 'conversion fee', 'charge for', 'bank charge',
                'pasha bank charge', 'monthly fee', 'account maintenance', 'card fee',
                'banking fee', 'transaction fee', 'service charge', 'tariff', 'тариф',
                'revolut business fee', 'grow plan fee', 'expenses app charge',
                'conversion fee', 'foreign exchange transaction fee', 'fee for',
                'popl.', 'vedeni', 'balicek', 'vypis', 'postou', 'tuz', 'ok', 'odch',
                'prich', 'intc', 'pl', 'st', 'tp', 'bankovní poplatek', 'opłata bankowa',
                'banka ücreti', 'bank fee', 'service fee', 'administrative fee'
            ],
            '1.2.15.1 Зарплата': [
                'зарплат', 'salary', 'darba alga', 'algas izmaksa', 'darba algas izmaksa',
                'wage', 'payroll', 'alga', 'зарплата', 'зарплату', 'algas', 'salary amount',
                'darba algas izmaksa par', 'mzda', 'płaca', 'maaş', 'wages', 'payment to employee'
            ],
            '1.2.15.2 Налоги на ФОТ': [
                'nodokļu nomaksa', 'vid', 'budžets', 'налог', 'valsts budžets',
                'nodokļu', 'darba devēja', 'nodoku nomaksa', 'state revenue service',
                'social tax', 'социальный налог', 'подоходный налог', 'income tax',
                'dsmf', 'государственные сборы', 'taxes', 'налоги', 'daň', 'podatek',
                'vergi', 'tax payment', 'tax deduction'
            ],
            '1.2.16.3 НДС': [
                'value added tax', 'vat', 'ндс', 'pvn', 'output tax', 'pvn nodoklis',
                'pvns', 'н.д.с.', 'добавленная стоимость', 'value added tax - output',
                'dph', 'iva', 'kdv', 'moms', 'btw', 'tva'
            ],
            '1.2.16.1 Налог на недвижимость': [
                'nekustamā īpašuma nodoklis', 'налог на недвижимость', 'pašvaldība',
                'property tax', 'real estate tax', 'имущественный налог',
                'rigas valstspilsētas pašvaldība', 'daň z nemovitosti', 'podatek od nieruchomości',
                'emlak vergisi'
            ],
            '1.2.10.5 Электричество': [
                'latvenergo', 'elektri', 'электричеств', 'electricity', 'power',
                'elektrība', 'электроэнергия', 'light', 'освещение', 'электричество',
                'elektřina', 'prąd', 'elektrik'
            ],
            '1.2.10.3 Вода': [
                'rigas udens', 'ūdens', 'вода', 'water', 'woda', 'víz',
                'водоснабжение', 'водопровод', 'rīgas ūdens', 'voda', 'su'
            ],
            '1.2.10.2 Газ': [
                'gāze', 'газ', 'gas', 'heating', 'отопление', 'тепло',
                'gáz', 'газовое', 'газоснабжение', 'plyn', 'gaz'
            ],
            '1.2.10.1 Мусор': [
                'atkritumi', 'мусор', 'eco baltia', 'clean r', 'waste', 'garbage',
                'вывоз мусора', 'утилизация', 'trash', 'rubbish', 'odpad', 'çöp'
            ],
            '1.2.10.6 Коммунальные УК дома': [
                'rigas namu pārvaldnieks', 'latvijas namsaimnieks', 'biedrība',
                'dzīvokļu īpašnieku', 'apartment owners', 'management fee',
                'управляющая компания', 'ук', 'house management', 'condominium',
                'vecruni', 'nia nami', 'mūsu nams', 'správa domu', 'yönetim ücreti'
            ],
            '1.2.9.1 Связь, интернет, TV': [
                'tele2', 'bite', 'tet', 'internet', 'связь', 'telenet', 'wifi', 'broadband',
                'телефон', 'phone', 'мобильная связь', 'mobile', 'телевидение', 'tv',
                'телеком', 'telecom', 'связь и интернет', 'bite latvija', 'telekomunikace',
                'telekomunikacja', 'iletişim'
            ],
            '1.2.9.3 IT сервисы': [
                'google one', 'lovable', 'openai', 'chatgpt', 'browsec', 'adobe',
                'albato', 'slack', 'it сервисы', 'software', 'subscription',
                'microsoft', 'office 365', 'cloud', 'хостинг', 'hosting', 'domain',
                'домен', 'сервер', 'server', 'vps', 'vpn', 'антивирус', 'antivirus',
                'asana', 'zapier', 'google *google', 'digitalocean', 'aws', 'azure',
                'github', 'gitlab', 'bitbucket', 'jira', 'confluence', 'trello',
                'notion', 'figma', 'sketch', 'zoom', 'teams', 'slack'
            ],
            '1.2.3 Оплата рекламных систем (бюджет)': [
                'facebook', 'facbk', 'tiktok', 'ads', 'marketing', 'реклам', 'advertising',
                'instagram', 'google ads', 'fb ads', 'яндекс директ', 'yandex direct',
                'контекстная реклама', 'contextual advertising', 'promotion', 'продвижение',
                'propertyfinder', 'tiktok ads', 'linkedin ads', 'twitter ads', 'pinterest ads',
                'реклама в', 'рекламная кампания', 'ad campaign'
            ],
            '1.2.2 Командировочные расходы': [
                'flydubai', 'taxi', 'flixbus', 'bolt', 'uber', 'flix', 'careem',
                'travel', 'transport', 'hotel', 'accommodation', 'авиабилеты',
                'билеты', 'tickets', 'проживание', 'питание', 'meal', 'food',
                'командировка', 'business trip', 'транспортные расходы', 'dubai taxi',
                'cars taxi', 'enoc', 'emarat', 'hotel', 'отель', 'restaurant', 'ресторан',
                'airbnb', 'booking.com', 'expedia', 'hostel', 'hostelworld', 'train',
                'bus', 'metro', 'subway', 'car rental', 'rental car'
            ],
            '1.2.8.1 Обслуживание объектов (бытовые вопросы, без ремонта)': [
                'apmaksa par rēķinu', 'обслуживание', 'ремонт', 'lifti', 'taipans',
                'sidorans', 'komval', 'rīgas lifti', 'maintenance', 'repair',
                'уборка', 'cleaning', 'клининг', 'сантехник', 'электрик',
                'plumber', 'electrician', 'техническое обслуживание', 'atlas materials',
                'údržba', 'bakım', 'cleaning service', 'janitor', 'уборщик'
            ],
            '1.2.8.2 Страхование': [
                'balta', 'страхование', 'insurance', 'insure', 'страховка',
                'страховой взнос', 'insurance premium', 'pojištění', 'sigorta'
            ],
            '1.2.12 Бухгалтер': [
                'lubova loseva', 'loseva', 'бухгалтер', 'accounting', 'bookkeeping',
                'бухгалтерские услуги', 'бухгалтерия', 'accountant', 'audit', 'аудит',
                'účetní', 'muhasebeci'
            ],
            '2.2.7 Расходы по приобретению недвижимости': [
                'pirkuma liguma', 'приобретение недвижимости', 'аванс покупной стоимости',
                'property purchase', 'real estate purchase', 'покупка недвижимости',
                'advance payment', 'авансовый платеж', 'rezervacni smlouva',
                'kupní smlouva', 'satın alma'
            ],
            '1.2.27 Расходы в ожидании возмещения ЗП по другим бизнесам': [
                'jl/nf', 'jl/zp', 'расходы в ожидании', 'other business',
                'временные расходы', 'temporary expenses', 'alexander plyatsevoy'
            ],
            '1.2.37 Возврат гарантийных депозитов': [
                'deposit return', 'возврат депозита', 'depozīta atgriešana',
                'гарантийный депозит', 'security deposit refund', 'vrácení zálohy',
                'depozito iade'
            ],
            '1.2.21.1 Аренда офиса': [
                'office rent', 'аренда офиса', 'icare odәnisi', 'rent payment',
                'аренда помещения', 'office space', 'kancelář', 'ofis kirası'
            ],
            '1.2.21.2 Административные офисные расходы': [
                'office', 'офис', 'stationery', 'канцелярия', 'post office', 'ceska posta',
                'почта', 'post', 'канцелярские товары', 'kancelářské potřeby',
                'ofis malzemeleri'
            ],
            '1.2.24 Расходы по отдельному бизнесу': [
                'vzr div', 'nav', 'personal income', 'social security', 'social contribution',
                'giro payment', 'transaction fee part', 'nav corporate tax', 'nav tarsasagi ado'
            ],
            '1.2.28 Расходы, произведённые за другие компании группы (к возмещению)': [
                'относится к александру', 'за другие компании', 'revelton',
                'расходы за другие компании', 'other companies', 'pro jiné společnosti',
                'diğer şirketler için'
            ],
            '1.2.33 Непредвиденные расходы': [
                'kompensācija', 'непредвиденные', 'unexpected', 'compensation',
                'neočekávané výdaje', 'beklenmedik giderler'
            ],
            '1.2.34 Вознаграждение инвестора': [
                'вознаграждение инвестора', 'investor reward', 'bs property', 'bs rerum',
                'odměna investora', 'yatırımcı ödülü'
            ],
            '1.2.38 НДС в составе комиссий банка': [
                'value added tax', 'vat', 'ндс', 'tax on commission', 'bank commission vat',
                'dph z bankovních poplatků', 'banka komisyonu kdv'
            ],
            'Перевод между счетами': [
                'currency exchange', 'конвертация', 'internal payment',
                'transfer to own account', 'между своими счетами', 'own transfer',
                'внутренний перевод', 'межбанковский перевод', 'bank transfer',
                'перевод между счетами', 'перевод в кассу', 'перевод на счет',
                'ipp transfer', 'inter company transfer', 'same-day own account transfer',
                'převod mezi účty', 'hesap transferi'
            ]
        }
        
        # Статьи доходов
        self.income_articles = {
            '1.1.1.2 Поступления систем бронирования (Airbnb, Booking и пр.)': [
                'airbnb', 'booking.com', 'booking b.v.', 'booking', 'airbnb payments',
                'vrbo', 'homeaway', 'expedia', 'tripadvisor', 'agoda'
            ],
            '1.1.1.4 Получение гарантийного депозита': [
                'depozits', 'депозит', 'deposit', 'guarantee', 'security deposit',
                'гарантийный депозит', 'záloha', 'depozito'
            ],
            '1.1.1.5 Возмещения': [
                'atlıdzība', 'возмещение', 'compensation', 'refund', 'возврат',
                'компенсация', 'náhrada', 'tazminat'
            ],
            '1.1.4.1 Комиссия за продажу недвижимости': [
                'commission', 'agency commissions', 'incoming swift payment',
                'marketing and advertisement', 'consultancy fees', 'real estate commission',
                'agent commission', 'комиссия за продажу', 'inward remittance',
                'fund transfer', 'provision', 'komise', 'komisyon'
            ],
            '3.1.3 Получение внутригруппового займа': [
                'loan', 'займ', 'baltic solutions', 'payment acc loan agreement',
                'loan payment', 'loan repayment', 'получение займа', 'půjčka', 'kredi'
            ],
            '3.1.4 Возврат выданного внутригруппового займа': [
                'loan return', 'возврат займа', 'partial repayment', 'repayment',
                'partial repayment of the loan', 'возврат выданного займа',
                'splátka půjčky', 'kredi geri ödemesi'
            ],
            '3.1.1 Ввод средств': [
                'transfer to own account', 'между своими счетами', 'own transfer', 'ввод средств',
                'fx spot/fwd payment', 'конвертация валюты', 'vklad', 'yatırım'
            ],
            '1.1.2.3 Компенсация по коммунальным расходам': [
                'komunālie', 'utilities', 'компенсац', 'возмещени', 'utility',
                'communal', 'heating cost', 'water cost', 'коммунальные', 'компенсация',
                'возмещение коммунальных', 'kompenzace', 'tazminat'
            ],
            '1.1.2.4 Прочие мелкие поступления': [
                'кэшбэк', 'cashback', 'u rok do', 'interest', 'проценты', 'урок',
                'urok do', 'процент', 'interest payment', 'cash back', 'cash-back',
                'cashback bonus', 'cashback reward'
            ],
            '1.1.2.2 Возвраты от поставщиков': [
                'return on request', 'возврат', 'refund', 'reversal', 'vat reversal',
                'возврат от поставщика', 'supplier refund', 'vrácení od dodavatele',
                'tedarikçi iadesi'
            ],
            '1.1.1.1 Арендная плата (наличные)': [
                'наличные', 'cash', 'cash payment', 'hotovost', 'nakit'
            ],
            '1.1.1.3 Арендная плата (счёт)': [
                'арендн', 'rent', 'money added', 'ire', 'dzivoklis', 'from',
                'credit of sepa', 'topup', 'received', 'incoming payment',
                'partial repayment', 'payment acc loan agreement', 'sent from',
                'поступление', 'received from', 'rent payment', 'арендная плата',
                'плата за аренду', 'ire par', 'par dzivokli', 'nájemné', 'kira'
            ]
        }
    
    def get_article(self, description: str, amount: float, file_name: str) -> Tuple[str, str]:
        """Определение статьи и родительской статьи"""
        desc_lower = description.lower()
        file_lower = file_name.lower()
        
        # Для расходов
        if amount < 0:
            for article, keywords in self.expense_articles.items():
                for keyword in keywords:
                    if keyword in desc_lower:
                        # Определяем родительскую статью
                        article_code = article.split(' ')[0]
                        parent_code = '.'.join(article_code.split('.')[:2])
                        parent_article = self.parent_articles.get(parent_code, "")
                        return article, parent_article
            
            # Если статья не найдена, используем умолчание
            return '1.2.8.1 Обслуживание объектов (бытовые вопросы, без ремонта)', '1.2.8 Обслуживание объектов'
        
        # Для доходов
        else:
            for article, keywords in self.income_articles.items():
                for keyword in keywords:
                    if keyword in desc_lower:
                        # Определяем родительскую статью
                        article_code = article.split(' ')[0]
                        parent_code = '.'.join(article_code.split('.')[:2])
                        parent_article = self.parent_articles.get(parent_code, "")
                        return article, parent_article
            
            # Если статья не найдена, используем умолчание
            return '1.1.1.3 Арендная плата (счёт)', '1.1.1 Поступления за аренду недвижимости и земельных участков'

# ==================== ОПРЕДЕЛЕНИЕ НАПРАВЛЕНИЙ ====================
class DirectionClassifier:
    """Классификатор направлений и субнаправлений"""
    def __init__(self):
        self.directions = {
            'Latvia': [
                ('AN14 Антониас 14 (дом + парковка)', ['antonijas', 'an14', 'antonias']),
                ('AC89 Чака 89 (дом + парковка)', ['caka', 'ac89', 'čaka', 'caka iela', 'chaka']),
                ('M81 - Matisa 81', ['matisa', 'm81', 'matīsa']),
                ('B117 Бривибас, 117', ['brīvības 117', 'b117', 'brivibas', 'brīvības']),
                ('B78 Бривибас, 78', ['brīvības 78', 'b78']),
                ('G77 Гертрудес, 77', ['gertrudes', 'g77', 'gertrūdes']),
                ('V22 К. Валдемара 22', ['valdemara', 'v22', 'valdemāra']),
                ('MU3 - Mucenieku 3 - 4', ['mucenieku', 'mu3']),
                ('DS1 Дзирнаву, 1', ['dzirnavu', 'ds1', 'dzirnavu iela']),
                ('C23 Цесу, 23', ['cesu', 'c23', 'cesu iela']),
                ('SK3-Skunju 3', ['skunu', 'sk3', 'skunju', 'skunu iela']),
                ('D4 Парковка-Deglava4', ['deglava', 'd4', 'deglava iela']),
                ('H5 Хоспиталю', ['hospitalu', 'h5', 'hospitalu iela']),
                ('BRN_Brunieku', ['bruninieku', 'brn', 'bruņinieku', 'bruninieku iela']),
                ('AC87 Гараж Чака', ['ac87', 'caka 87']),
                ('UK_Latvia', ['uk_latvia', 'латвия', 'latvia', 'riga', 'рига'])
            ],
            'Europe': [
                ('F6 Помещение в доме Будапешт', ['budapest', 'f6', 'yulia galvin', 'будапешт']),
                ('DZ1_Dzibik1', ['dzibik', 'dz1', 'bilych nadiia']),
                ('J91 Ялтская - Помещение маленькое', ['j91', 'ялтская', 'bastet']),
                ('TGM45 Масарика - Bagel Lounge', ['masaryka', 'tgm45', 'bagel lounge', 'restco', 'masaryk']),
                ('OT1_Otovice Участок Свалка', ['otovice', 'ot1', 'komplekt', 'sedlecky kaolin']),
                ('MOL - Офис Molly', ['twohills', 'molly', 'mol']),
                ('LT_Vilnus', ['sveciy', 'vilnus', 'vilnius', 'вильнюс']),
                ('TGM20-Masaryka20', ['garpiz', 'tgm20', 'masaryka20']),
                ('Pernik', ['pernik']),
                ('UK_EU', ['uk_eu', 'европа', 'europe', 'eu', 'чехия', 'czech', 'чехия'])
            ],
            'East-Восток': [
                ('BIS - Baku, Icheri Sheher 1,2', ['icheri', 'bis', 'baku', 'cordiality', 'баку']),
                ('UKA - UK_AZ-Аренда', ['uka', 'uk_az', 'азербайджан', 'azerbaijan', 'azn'])
            ],
            'Nomiqa': [
                ('BNQ_BAKU-Nomiqa', ['bnq', 'baku-nomiqa', 'bunda']),
                ('DNQ_Dubai-Nomiqa', ['dnq', 'dubai-nomiqa', 'nomiqa real estate', 'mashreq', 'dubai', 'дубай'])
            ],
            'Unelma': [
                ('UK_Unelma', ['unelma'])
            ],
            'Отдельный бизнес': [
                ('', ['jl/nf', 'jl/zp', 'отдельный бизнес', 'в ожидании возмещения',
                     'alexander plyatsevoy', 'временные расходы', 'temporary business'])
            ],
            'UK Estate': [
                ('', ['uk estate', 'общие расходы', 'general expenses', 'head office'])
            ]
        }
    
    def get_direction(self, file_name: str, description: str, payer: str = "") -> Tuple[str, str]:
        """Определение направления и субнаправления"""
        file_lower = file_name.lower()
        desc_lower = description.lower()
        payer_lower = payer.lower() if payer else ""
        
        combined_text = f"{desc_lower} {payer_lower} {file_lower}"
        
        # Проверка по специфичным субнаправлениям
        for direction, subdirections in self.directions.items():
            for subdirection, keywords in subdirections:
                for keyword in keywords:
                    if keyword in combined_text:
                        return direction, subdirection
        
        # Проверка по общим ключевым словам для направлений
        if any(x in file_lower for x in ['pasha', 'kapital', 'bunda', 'azn', 'azerbaijan', 'баку']):
            return 'East-Восток', 'UKA - UK_AZ-Аренда'
        
        if any(x in file_lower for x in ['mashreq', 'wio', 'aed', 'dubai', 'uae', 'оаэ']):
            return 'Nomiqa', 'DNQ_Dubai-Nomiqa'
        
        if any(x in file_lower for x in ['csob', 'unicredit', 'czk', 'чехия', 'czech', 'praha', 'prague']):
            return 'Europe', 'UK_EU'
        
        if any(x in file_lower for x in ['industra', 'revolut', 'paysera', 'латвия', 'latvia', 'riga', 'lv']):
            return 'Latvia', 'UK_Latvia'
        
        # По умолчанию
        return 'UK Estate', ''

# ==================== РАЗБИВКА АРЕНДНЫХ ПЛАТЕЖЕЙ ====================
class RentalSplitter:
    """Класс для разбивки арендных платежей"""
    def __init__(self):
        self.split_ratios = {
            'AC89 Чака 89 (дом + парковка)': (0.836, 0.164),
            'AN14 Антониас 14 (дом + парковка)': (0.80, 0.20),
            'M81 - Matisa 81': (0.70, 0.30),
            'B117 Бривибас, 117': (0.85, 0.15),
            'V22 К. Валдемара 22': (0.55, 0.45),
            'G77 Гертрудес, 77': (0.85, 0.15),
            'default': (0.85, 0.15)
        }
    
    def should_split(self, description: str, amount: float, file_name: str, subdirection: str) -> bool:
        """Определение, нужно ли разбивать платеж"""
        if amount <= 0:
            return False
        
        desc_lower = description.lower()
        file_lower = file_name.lower()
        
        # Исключаем определенные типы платежей
        exclude_keywords = [
            'booking.com', 'airbnb', 'loan', 'deposit', 'депозит',
            'commission', 'комиссия', 'fee', 'charge', 'tax', 'налог',
            'salary', 'зарплата', 'refund', 'возврат', 'interest', 'проценты',
            'valsts budžets', 'budžets', 'vid', 'rigas valstpilsētas pašvaldība',
            'latvenergo', 'rigas udens', 'eco baltia', 'bite', 'tele2', 'tet',
            'rīgas lifti', 'taipans', 'sidorans', 'komval', 'apmaksa par',
            'inward remittance', 'fund transfer', 'swift payment', 'bank transfer',
            'transfer from', 'transfer to', 'conversion', 'exchange'
        ]
        
        for kw in exclude_keywords:
            if kw in desc_lower:
                return False
        
        # Проверяем, относится ли к аренде
        rent_keywords = [
            'rent', 'аренд', 'caka', 'antonijas', 'matisa', 'valdemara',
            'for rent', 'dzivoklis', 'apartment', 'flat', 'ire',
            'money added', 'topup', 'from', 'received', 'incoming',
            'brīvības', 'gertrudes', 'mucenieku', 'dzirnavu', 'cesu',
            'skunu', 'deglava', 'hospitalu', 'bruninieku', 'nájemné',
            'kira', 'rental', 'lease', 'лизинг'
        ]
        
        has_rent_keyword = any(kw in desc_lower for kw in rent_keywords)
        
        # Проверяем субнаправление
        valid_subdirections = list(self.split_ratios.keys())
        has_valid_subdirection = subdirection in valid_subdirections
        
        return has_rent_keyword and has_valid_subdirection
    
    def calculate_split(self, amount: float, subdirection: str) -> Tuple[float, float]:
        """Расчет разбивки платежа"""
        ratio = self.split_ratios.get(subdirection, self.split_ratios['default'])
        rent_share = round(amount * ratio[0], 2)
        utility_share = round(amount * ratio[1], 2)
        
        # Корректировка для точного соответствия исходной сумме
        total = rent_share + utility_share
        if abs(total - amount) > 0.01:
            if rent_share > utility_share:
                rent_share = round(rent_share + (amount - total), 2)
            else:
                utility_share = round(utility_share + (amount - total), 2)
        
        return rent_share, utility_share

# ==================== ОСНОВНАЯ ФУНКЦИЯ ПАРСИНГА ====================
def parse_file(file_content: bytes, file_name: str) -> List[Dict]:
    """Основная функция парсинга файла"""
    # Чтение файла
    df = read_file(file_content, file_name)
    
    if df is None or df.empty:
        st.warning(f"⚠️ Не удалось прочитать файл {file_name}")
        return []
    
    # Инициализация детектора заголовков
    detector = HeaderDetector()
    
    # Поиск строки заголовков
    header_row = detector.find_header_row(df)
    
    if header_row >= 0 and detector.validate_header_row(df, header_row):
        # Извлекаем заголовки
        headers = []
        for i, h in enumerate(df.iloc[header_row].values):
            if pd.isna(h):
                headers.append(f'col_{i}')
            else:
                headers.append(str(h).strip())
        
        # Создаем DataFrame с данными
        data_rows = []
        for idx in range(header_row + 1, len(df)):
            row = list(df.iloc[idx].values)
            if len(row) < len(headers):
                row.extend([''] * (len(headers) - len(row)))
            elif len(row) > len(headers):
                row = row[:len(headers)]
            data_rows.append(row)
        
        df = pd.DataFrame(data_rows, columns=headers)
    
    if df.empty:
        st.warning(f"⚠️ В файле {file_name} не найдено данных для обработки")
        return []
    
    # Определение колонок
    date_col = None
    amount_col = None
    debit_col = None
    credit_col = None
    desc_col = None
    type_col = None
    payer_col = None
    account_col = None
    currency_col = None
    
    # Сначала ищем точные совпадения
    for col in df.columns:
        col_lower = str(col).lower()
        
        # Дата
        if date_col is None and any(kw in col_lower for kw in detector.header_patterns['date']):
            date_col = col
        
        # Сумма
        if amount_col is None and any(kw in col_lower for kw in detector.header_patterns['amount']):
            amount_col = col
        
        # Дебет
        if debit_col is None and any(kw in col_lower for kw in detector.header_patterns['debit']):
            debit_col = col
        
        # Кредит
        if credit_col is None and any(kw in col_lower for kw in detector.header_patterns['credit']):
            credit_col = col
        
        # Описание
        if desc_col is None and any(kw in col_lower for kw in detector.header_patterns['description']):
            desc_col = col
        
        # Тип
        if type_col is None and any(kw in col_lower for kw in detector.header_patterns['type']):
            type_col = col
        
        # Плательщик
        if payer_col is None and any(kw in col_lower for kw in detector.header_patterns['payer']):
            payer_col = col
        
        # Счет
        if account_col is None and any(kw in col_lower for kw in detector.header_patterns['account']):
            account_col = col
        
        # Валюта
        if currency_col is None and any(kw in col_lower for kw in detector.header_patterns['currency']):
            currency_col = col
    
    # Если не нашли нужные колонки, используем эвристики
    if date_col is None:
        # Ищем колонки с датами
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                date_col = col
                break
            else:
                # Пробуем преобразовать первые несколько значений
                sample = df[col].head(10).dropna()
                if len(sample) > 0:
                    date_count = 0
                    for val in sample:
                        try:
                            parse_date(str(val))
                            date_count += 1
                        except:
                            pass
                    if date_count > len(sample) * 0.5:
                        date_col = col
                        break
    
    if desc_col is None:
        # Ищем колонку с самым длинным текстом
        max_len = 0
        for col in df.columns:
            if df[col].dtype == 'object':
                avg_len = df[col].astype(str).str.len().mean()
                if avg_len > max_len:
                    max_len = avg_len
                    desc_col = col
    
    if amount_col is None and (debit_col is None or credit_col is None):
        # Ищем колонки с числами
        numeric_cols = []
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                numeric_cols.append(col)
        
        if len(numeric_cols) >= 2:
            # Предполагаем, что первые две числовые колонки - дебет и кредит
            debit_col = numeric_cols[0]
            credit_col = numeric_cols[1]
        elif len(numeric_cols) == 1:
            # Одна числовая колонка - сумма
            amount_col = numeric_cols[0]
    
    # Если все еще не нашли, используем первые колонки по умолчанию
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]
    
    if desc_col is None and len(df.columns) > 1:
        desc_col = df.columns[1]
    
    if amount_col is None and debit_col is None and credit_col is None and len(df.columns) > 2:
        # Пробуем третью колонку как сумму
        amount_col = df.columns[2]
    
    # Инициализация классификаторов
    article_classifier = ArticleClassifier()
    direction_classifier = DirectionClassifier()
    rental_splitter = RentalSplitter()
    
    transactions = []
    
    for idx in range(len(df)):
        try:
            row = df.iloc[idx]
            
            # Извлечение описания
            description = ''
            if desc_col is not None and desc_col in row:
                desc_val = row[desc_col]
                if pd.notna(desc_val):
                    description = str(desc_val)
            
            # Добавление типа операции к описанию
            if type_col is not None and type_col in row:
                type_val = row[type_col]
                if pd.notna(type_val) and str(type_val).strip():
                    description = f"{str(type_val)} {description}"
            
            # Добавление плательщика/получателя
            payer = ''
            if payer_col is not None and payer_col in row:
                payer_val = row[payer_col]
                if pd.notna(payer_val) and str(payer_val).strip():
                    payer = str(payer_val)
            
            # Добавление других колонок к описанию
            for col in df.columns:
                if col not in [date_col, amount_col, debit_col, credit_col, desc_col, type_col, payer_col, currency_col]:
                    val = row[col]
                    if pd.notna(val) and str(val).strip() and str(val) != 'nan':
                        try:
                            float(str(val).replace(',', '.'))
                            continue
                        except:
                            description += ' ' + str(val)
            
            description = description.strip()
            
            # Извлечение даты
            date = ''
            if date_col is not None and date_col in row:
                date_val = row[date_col]
                if pd.notna(date_val):
                    date = parse_date(date_val)
            
            if not date:
                # Пробуем найти дату в других колонках
                for col in df.columns:
                    if col != date_col:
                        val = row[col]
                        if pd.notna(val):
                            parsed_date = parse_date(str(val))
                            if parsed_date and re.match(r'\d{4}-\d{2}-\d{2}', parsed_date):
                                date = parsed_date
                                break
            
            if not date:
                continue
            
            # Извлечение суммы
            amount = 0.0
            
            # Пробуем amount_col
            if amount_col is not None and amount_col in row:
                amount_val = row[amount_col]
                if pd.notna(amount_val) and str(amount_val).strip() and str(amount_val).strip() != '':
                    amount = parse_amount(amount_val, description=description)
            
            # Если не нашли в amount_col, пробуем debit/credit
            if amount == 0:
                if debit_col is not None and debit_col in row:
                    debit_val = row[debit_col]
                    if pd.notna(debit_val) and str(debit_val).strip() and str(debit_val).strip() != '':
                        amount = parse_amount(debit_val, is_debit_col=True, is_credit_col=False, description=description)
                
                if amount == 0 and credit_col is not None and credit_col in row:
                    credit_val = row[credit_col]
                    if pd.notna(credit_val) and str(credit_val).strip() and str(credit_val).strip() != '':
                        amount = parse_amount(credit_val, is_debit_col=False, is_credit_col=True, description=description)
            
            # Если все еще 0, ищем в других числовых колонках
            if amount == 0:
                for col in df.columns:
                    if col not in [date_col, desc_col, type_col, payer_col, amount_col, debit_col, credit_col, currency_col]:
                        val = row[col]
                        if pd.notna(val):
                            try:
                                num_val = float(str(val).replace(',', '.'))
                                if num_val != 0:
                                    temp_amount = parse_amount(str(val), description=description)
                                    if temp_amount != 0:
                                        amount = temp_amount
                                        break
                            except:
                                pass
            
            if amount == 0:
                continue
            
            # Определение валюты
            currency = 'EUR'
            if currency_col is not None and currency_col in row:
                currency_val = row[currency_col]
                if pd.notna(currency_val):
                    currency_str = str(currency_val).upper().strip()
                    if currency_str in Config.CURRENCIES:
                        currency = currency_str
            
            # Определение по имени файла
            file_lower = file_name.lower()
            if 'czk' in file_lower or 'чехия' in file_lower or 'czech' in file_lower:
                currency = 'CZK'
            elif 'huf' in file_lower or 'венгрия' in file_lower or 'hungary' in file_lower:
                currency = 'HUF'
            elif 'azn' in file_lower or 'азербайджан' in file_lower or 'azerbaijan' in file_lower:
                currency = 'AZN'
            elif 'aed' in file_lower or 'оаэ' in file_lower or 'дирхам' in file_lower or 'uae' in file_lower:
                currency = 'AED'
            elif 'rub' in file_lower or 'россия' in file_lower or 'russia' in file_lower:
                currency = 'RUB'
            elif 'usd' in file_lower or 'доллар' in file_lower or 'dollar' in file_lower:
                currency = 'USD'
            elif 'gbp' in file_lower or 'фунт' in file_lower or 'pound' in file_lower:
                currency = 'GBP'
            elif 'pln' in file_lower or 'злотый' in file_lower or 'poland' in file_lower:
                currency = 'PLN'
            
            # Имя счета
            account_name = file_name.replace('.csv', '').replace('.xlsx', '').replace('.xls', '').replace('.txt', '')
            
            # Определение направления
            direction, subdirection = direction_classifier.get_direction(file_name, description, payer)
            
            # Определение статьи
            article, parent_article = article_classifier.get_article(description, amount, file_name)
            
            # Проверка на разбивку арендного платежа
            if rental_splitter.should_split(description, amount, file_name, subdirection):
                rent_share, utility_share = rental_splitter.calculate_split(amount, subdirection)
                
                # Транзакция аренды
                if rent_share > 0:
                    transactions.append({
                        'Дата': date,
                        'Сумма': rent_share,
                        'НДС': 0.0,
                        'Счет': account_name,
                        'Валюта': currency,
                        'Контрагент': payer,
                        'Статья': article,
                        'Род. статья': parent_article,
                        'Описание': f"{description[:300]} (аренда)",
                        'Направление': direction,
                        'Субнаправление': subdirection,
                        'Месяц начисления': date[:7] if date else '',
                        'Исходный файл': file_name
                    })
                
                # Транзакция компенсации КУ
                if utility_share > 0:
                    transactions.append({
                        'Дата': date,
                        'Сумма': utility_share,
                        'НДС': 0.0,
                        'Счет': account_name,
                        'Валюта': currency,
                        'Контрагент': payer,
                        'Статья': '1.1.2.3 Компенсация по коммунальным расходам',
                        'Род. статья': '1.1.2 Прочие поступления',
                        'Описание': f"{description[:300]} (компенсация КУ)",
                        'Направление': direction,
                        'Субнаправление': subdirection,
                        'Месяц начисления': date[:7] if date else '',
                        'Исходный файл': file_name
                    })
            else:
                # Обычная транзакция
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'НДС': 0.0,
                    'Счет': account_name,
                    'Валюта': currency,
                    'Контрагент': payer,
                    'Статья': article,
                    'Род. статья': parent_article,
                    'Описание': description[:500],
                    'Направление': direction,
                    'Субнаправление': subdirection,
                    'Месяц начисления': date[:7] if date else '',
                    'Исходный файл': file_name
                })
        
        except Exception as e:
            # Пропускаем проблемные строки
            continue
    
    return transactions

# ==================== ИНТЕРФЕЙС ====================
def main():
    """Основная функция интерфейса"""
    tab1, tab2, tab3 = st.tabs(["📂 Один файл", "📚 Несколько файлов", "⚙️ Настройки"])
    
    with tab1:
        st.markdown("### Загрузите выписку для анализа")
        uploaded_file = st.file_uploader("Выберите файл", type=['csv', 'xlsx', 'xls', 'txt'], key="single")
        
        if uploaded_file:
            st.success(f"✅ Файл загружен: {uploaded_file.name}")
            
            if st.button("🚀 Запустить анализ", key="single_btn"):
                with st.spinner("Анализируем..."):
                    content = uploaded_file.read()
                    transactions = parse_file(content, uploaded_file.name)
                    
                    if transactions:
                        df = pd.DataFrame(transactions)
                        
                        # Отображение метрик
                        st.markdown("---")
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("📊 Всего операций", len(transactions))
                        
                        with col2:
                            доход = df[df['Сумма'] > 0]['Сумма'].sum()
                            st.metric("📈 Доходы", f"{доход:,.2f}")
                        
                        with col3:
                            расход = abs(df[df['Сумма'] < 0]['Сумма'].sum())
                            st.metric("📉 Расходы", f"{расход:,.2f}")
                        
                        with col4:
                            баланс = доход - расход
                            st.metric("💰 Баланс", f"{баланс:,.2f}")
                        
                        # Отображение данных
                        st.markdown("### 📋 Обработанные транзакции")
                        st.dataframe(df, use_container_width=True)
                        
                        # Сводка по статьям
                        st.markdown("### 📊 Сводка по статьям")
                        article_summary = df.groupby('Статья').agg({
                            'Сумма': ['sum', 'count']
                        }).round(2)
                        article_summary.columns = ['Сумма', 'Количество']
                        st.dataframe(article_summary, use_container_width=True)
                        
                        # Экспорт
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df.to_excel(writer, sheet_name='Транзакции', index=False)
                            article_summary.to_excel(writer, sheet_name='Сводка по статьям')
                        
                        output.seek(0)
                        
                        st.download_button(
                            label="📥 Скачать Excel",
                            data=output,
                            file_name=f"анализ_{uploaded_file.name.split('.')[0]}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.error("❌ Не удалось обработать файл. Проверьте формат файла.")
    
    with tab2:
        st.markdown("### Загрузите несколько файлов для анализа")
        uploaded_files = st.file_uploader(
            "Выберите файлы", 
            type=['csv', 'xlsx', 'xls', 'txt'], 
            accept_multiple_files=True,
            key="multiple"
        )
        
        if uploaded_files:
            st.success(f"✅ Загружено файлов: {len(uploaded_files)}")
            
            if st.button("🚀 Запустить анализ всех файлов", key="multiple_btn"):
                all_transactions = []
                
                with st.spinner("Анализируем файлы..."):
                    progress_bar = st.progress(0)
                    
                    for i, uploaded_file in enumerate(uploaded_files):
                        try:
                            content = uploaded_file.read()
                            transactions = parse_file(content, uploaded_file.name)
                            all_transactions.extend(transactions)
                            
                            # Обновляем прогресс
                            progress_bar.progress((i + 1) / len(uploaded_files))
                            
                            st.info(f"✅ Обработан {uploaded_file.name}: {len(transactions)} операций")
                        except Exception as e:
                            st.error(f"❌ Ошибка при обработке {uploaded_file.name}: {str(e)}")
                    
                    if all_transactions:
                        df = pd.DataFrame(all_transactions)
                        
                        # Отображение метрик
                        st.markdown("---")
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("📊 Всего операций", len(all_transactions))
                        
                        with col2:
                            доход = df[df['Сумма'] > 0]['Сумма'].sum()
                            st.metric("📈 Доходы", f"{доход:,.2f}")
                        
                        with col3:
                            расход = abs(df[df['Сумма'] < 0]['Сумма'].sum())
                            st.metric("📉 Расходы", f"{расход:,.2f}")
                        
                        with col4:
                            баланс = доход - расход
                            st.metric("💰 Баланс", f"{баланс:,.2f}")
                        
                        # Отображение данных
                        st.markdown("### 📋 Все обработанные транзакции")
                        st.dataframe(df, use_container_width=True)
                        
                        # Сводка по статьям
                        st.markdown("### 📊 Сводка по статьям")
                        article_summary = df.groupby('Статья').agg({
                            'Сумма': ['sum', 'count']
                        }).round(2)
                        article_summary.columns = ['Сумма', 'Количество']
                        st.dataframe(article_summary, use_container_width=True)
                        
                        # Сводка по файлам
                        st.markdown("### 📊 Сводка по файлам")
                        file_summary = df.groupby('Исходный файл').agg({
                            'Сумма': ['sum', 'count']
                        }).round(2)
                        file_summary.columns = ['Сумма', 'Количество']
                        st.dataframe(file_summary, use_container_width=True)
                        
                        # Экспорт
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df.to_excel(writer, sheet_name='Транзакции', index=False)
                            article_summary.to_excel(writer, sheet_name='Сводка по статьям')
                            file_summary.to_excel(writer, sheet_name='Сводка по файлам')
                        
                        output.seek(0)
                        
                        st.download_button(
                            label="📥 Скачать Excel",
                            data=output,
                            file_name="анализ_всех_файлов.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.error("❌ Не удалось обработать файлы. Проверьте форматы файлов.")
    
    with tab3:
        st.markdown("### Настройки анализа")
        
        st.markdown("#### Форматы дат")
        st.write("Поддерживаемые форматы дат:")
        for fmt in Config.DATE_FORMATS:
            st.write(f"- `{fmt}`")
        
        st.markdown("#### Разделители CSV")
        st.write("Поддерживаемые разделители:")
        for delim in Config.CSV_DELIMITERS:
            if delim == '\t':
                st.write("- `\\t` (табуляция)")
            else:
                st.write(f"- `{delim}`")
        
        st.markdown("#### Кодировки")
        st.write("Поддерживаемые кодировки:")
        for encoding in Config.ENCODINGS:
            st.write(f"- `{encoding}`")
        
        st.markdown("#### Валюты")
        st.write("Поддерживаемые валюты:")
        for code, name in Config.CURRENCIES.items():
            st.write(f"- `{code}`")

# ==================== ЗАПУСК ПРИЛОЖЕНИЯ ====================
if __name__ == "__main__":
    main()
