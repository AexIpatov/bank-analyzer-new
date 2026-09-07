import streamlit as st
import pandas as pd
import os
import re
import tempfile
import chardet
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Tuple, Optional

st.set_page_config(page_title="Аналитик банковских выписок", page_icon="🏦", layout="wide")

st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
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

st.markdown('<div class="main-header"><h1>🏦 Аналитик банковских выписок</h1><p>Загрузите выписки — получите структурированные данные</p></div>', unsafe_allow_html=True)

# ==================== СПРАВОЧНИК БАНКОВ ====================
BANK_REFERENCE = {
    'csob': {'name': 'ČSOB', 'country': 'Czech Republic', 'currency': 'CZK'},
    'čsob': {'name': 'ČSOB', 'country': 'Czech Republic', 'currency': 'CZK'},
    'unicredit': {'name': 'UniCredit Bank', 'country': 'Czech Republic', 'currency': 'CZK'},
    'uni credit': {'name': 'UniCredit Bank', 'country': 'Czech Republic', 'currency': 'CZK'},
    'industra': {'name': 'Industra Bank', 'country': 'Latvia', 'currency': 'EUR'},
    'revolut': {'name': 'Revolut', 'country': 'UK', 'currency': 'EUR'},
    'paysera': {'name': 'Paysera', 'country': 'Lithuania', 'currency': 'EUR'},
    'budapest': {'name': 'MKB Bank', 'country': 'Hungary', 'currency': 'HUF'},
    'mkb': {'name': 'MKB Bank', 'country': 'Hungary', 'currency': 'HUF'},
    'pasha': {'name': 'Pasha Bank', 'country': 'Azerbaijan', 'currency': 'AZN'},
    'kapital': {'name': 'Kapital Bank', 'country': 'Azerbaijan', 'currency': 'AZN'},
    'bunda': {'name': 'Pasha Bank', 'country': 'Azerbaijan', 'currency': 'AED'},
    'mashreq': {'name': 'Mashreq Bank', 'country': 'UAE', 'currency': 'AED'},
    'wio': {'name': 'WIO Bank', 'country': 'UAE', 'currency': 'AED'},
    'tinkoff': {'name': 'Тинькофф', 'country': 'Russia', 'currency': 'RUB'},
}

# ==================== ОПРЕДЕЛЕНИЕ ТИПА ФАЙЛА ====================
def detect_file_type(filename: str) -> str:
    """Определяет тип банка по имени файла"""
    filename_lower = filename.lower()
    
    bank_patterns = {
        'csob': ['csob', 'čsob', 'dzibik', 'koruna', 'strojka', 'ostrava'],
        'unicredit': ['unicredit', 'uni credit', 'garpiz'],
        'industra': ['industra', 'plavas'],
        'revolut': ['revolut'],
        'paysera': ['paysera', 'bs property', 'bs rerum'],
        'budapest': ['budapest', 'mkb'],
        'pasha': ['pasha', 'bunda'],
        'kapital': ['kapital', 'saida'],
        'mashreq': ['mashreq'],
        'tinkoff': ['tinkoff'],
    }
    
    for bank_type, patterns in bank_patterns.items():
        for pattern in patterns:
            if pattern in filename_lower:
                return bank_type
    
    return 'unknown'

def detect_file_encoding(file_path: str) -> str:
    """Определяет кодировку файла"""
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)
        result = chardet.detect(raw_data)
        return result['encoding'] if result['encoding'] else 'utf-8'
    except:
        return 'utf-8'

def detect_csv_delimiter(file_path: str) -> str:
    """Определяет разделитель в CSV файле"""
    delimiters = [';', ',', '\t', '|']
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            first_line = f.readline()
        
        counts = {}
        for delim in delimiters:
            counts[delim] = first_line.count(delim)
        
        max_delim = max(counts, key=counts.get)
        return max_delim if counts[max_delim] > 0 else ';'
    except:
        return ';'

# ==================== ПАРСИНГ ФАЙЛОВ ====================
class BankStatementParser:
    """Основной парсер банковских выписок"""
    
    def __init__(self):
        self.transactions = []
        self.bank_name = ''
    
    def parse_file(self, file_content: bytes, filename: str) -> List[Dict]:
        """Основной метод парсинга"""
        self.bank_name = self._get_bank_name(filename)
        
        file_type = detect_file_type(filename)
        ext = os.path.splitext(filename)[1].lower()
        
        if ext in ['.csv']:
            return self._parse_csv(file_content, filename, file_type)
        elif ext in ['.xlsx', '.xls']:
            return self._parse_excel(file_content, filename, file_type)
        else:
            st.warning(f"Неподдерживаемый формат файла: {filename}")
            return []
    
    def _get_bank_name(self, filename: str) -> str:
        """Получает наименование банка из справочника"""
        file_lower = filename.lower()
        
        for key, info in BANK_REFERENCE.items():
            if key in file_lower:
                return info['name']
        
        name = os.path.splitext(filename)[0]
        name = re.sub(r'\d{4}-\d{2}-\d{2}', '', name)
        name = re.sub(r'[_-]', ' ', name).strip()
        return name if name else 'Unknown Bank'
    
    def _parse_csv(self, file_content: bytes, filename: str, file_type: str) -> List[Dict]:
        """Парсинг CSV файлов"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            encoding = detect_file_encoding(tmp_path)
            delimiter = detect_csv_delimiter(tmp_path)
            
            df = pd.read_csv(
                tmp_path,
                sep=delimiter,
                encoding=encoding,
                header=None,
                dtype=str,
                on_bad_lines='skip'
            )
            
            header_row = self._find_header_row(df)
            
            if header_row >= 0:
                headers = [str(h).strip() for h in df.iloc[header_row].values]
                headers = [f'col_{i}' if pd.isna(h) or h == '' else h for i, h in enumerate(headers)]
                
                data_rows = []
                for idx in range(header_row + 1, len(df)):
                    row = list(df.iloc[idx].values)
                    if len(row) < len(headers):
                        row.extend([''] * (len(headers) - len(row)))
                    data_rows.append(row[:len(headers)])
                
                df = pd.DataFrame(data_rows, columns=headers)
            
            if file_type == 'csob':
                return self._parse_csob_csv(df, filename)
            elif file_type == 'unicredit':
                return self._parse_unicredit_csv(df, filename)
            elif file_type == 'industra':
                return self._parse_industra_csv(df, filename)
            elif file_type == 'revolut':
                return self._parse_revolut_csv(df, filename)
            elif file_type == 'paysera':
                return self._parse_paysera_csv(df, filename)
            else:
                return self._parse_generic_csv(df, filename)
                
        except Exception as e:
            st.error(f"Ошибка при парсинге CSV {filename}: {str(e)}")
            return []
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    def _parse_excel(self, file_content: bytes, filename: str, file_type: str) -> List[Dict]:
        """Парсинг Excel файлов"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            df = pd.read_excel(tmp_path, header=None, dtype=str)
            
            header_row = self._find_header_row(df)
            
            if header_row >= 0:
                headers = [str(h).strip() for h in df.iloc[header_row].values]
                headers = [f'col_{i}' if pd.isna(h) or h == '' else h for i, h in enumerate(headers)]
                
                data_rows = []
                for idx in range(header_row + 1, len(df)):
                    row = list(df.iloc[idx].values)
                    if len(row) < len(headers):
                        row.extend([''] * (len(headers) - len(row)))
                    data_rows.append(row[:len(headers)])
                
                df = pd.DataFrame(data_rows, columns=headers)
            
            if file_type in ['pasha', 'kapital']:
                return self._parse_pasha_excel(df, filename)
            elif file_type == 'mashreq':
                return self._parse_mashreq_excel(df, filename)
            elif file_type == 'budapest':
                return self._parse_budapest_excel(df, filename)
            else:
                return self._parse_generic_excel(df, filename)
                
        except Exception as e:
            st.error(f"Ошибка при парсинге Excel {filename}: {str(e)}")
            return []
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    def _find_header_row(self, df: pd.DataFrame) -> int:
        """Находит строку с заголовками в DataFrame"""
        header_keywords = [
            'date', 'дата', 'datum', 'posting date', 'value date',
            'amount', 'сумма', 'payment amount',
            'description', 'описание', 'transaction details',
            'counterparty', 'контрагент', 'payee',
            'account number', 'balance'
        ]
        
        for idx in range(min(20, len(df))):
            row = df.iloc[idx]
            row_text = ' '.join(str(v).lower() for v in row if pd.notna(v))
            
            matches = 0
            for keyword in header_keywords:
                if keyword in row_text:
                    matches += 1
            
            if matches >= 3:
                return idx
        
        return -1
    
    # ==================== ПАРСЕРЫ ДЛЯ РАЗНЫХ БАНКОВ ====================
    
    def _parse_csob_csv(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Парсинг выписок ČSOB"""
        transactions = []
        
        date_col = None
        amount_col = None
        desc_col = None
        counterparty_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'posting date' in col_lower:
                date_col = col
            elif 'payment amount' in col_lower:
                amount_col = col
            elif 'transaction type' in col_lower:
                desc_col = col
            elif 'counterparty' in col_lower:
                counterparty_col = col
            elif 'message to beneficiary and payer' in col_lower and desc_col is None:
                desc_col = col
        
        if date_col is None and len(df.columns) > 4:
            date_col = df.columns[4]
        if amount_col is None and len(df.columns) > 6:
            amount_col = df.columns[6]
        
        for idx, row in df.iterrows():
            try:
                date_val = row[date_col] if date_col in row else None
                if pd.isna(date_val):
                    continue
                date = self._parse_date(str(date_val))
                if not date:
                    continue
                
                amount = 0
                if amount_col in row:
                    amount_str = str(row[amount_col]).strip()
                    amount = self._parse_amount(amount_str)
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                counterparty = ''
                if counterparty_col in row:
                    counterparty = str(row[counterparty_col]) if pd.notna(row[counterparty_col]) else ''
                
                if not description:
                    for col in df.columns:
                        if col not in [date_col, amount_col, counterparty_col]:
                            val = row[col]
                            if pd.notna(val) and str(val).strip():
                                description += str(val) + ' '
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': counterparty[:200] if counterparty else '',
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_unicredit_csv(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Парсинг выписок UniCredit"""
        transactions = []
        
        data_start = 0
        for idx in range(min(5, len(df))):
            row_text = ' '.join(str(v) for v in df.iloc[idx].values if pd.notna(v))
            if 'From Account' in row_text or 'Amount' in row_text:
                data_start = idx + 1
                break
        
        date_col = None
        amount_col = None
        desc_col = None
        counterparty_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'booking date' in col_lower:
                date_col = col
            elif 'amount' in col_lower and 'total' not in col_lower:
                amount_col = col
            elif 'transaction details' in col_lower:
                desc_col = col
            elif 'name' in col_lower:
                counterparty_col = col
        
        for idx in range(data_start, len(df)):
            try:
                row = df.iloc[idx]
                
                if all(pd.isna(v) or str(v).strip() == '' for v in row):
                    continue
                
                date = ''
                if date_col in row:
                    date = self._parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
                
                if not date:
                    continue
                
                amount = 0
                if amount_col in row:
                    amount = self._parse_amount(str(row[amount_col])) if pd.notna(row[amount_col]) else 0
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                counterparty = ''
                if counterparty_col in row:
                    counterparty = str(row[counterparty_col]) if pd.notna(row[counterparty_col]) else ''
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': counterparty[:200],
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_industra_csv(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Парсинг выписок Industra Bank"""
        transactions = []
        
        header_row = -1
        for idx in range(min(20, len(df))):
            row_text = ' '.join(str(v) for v in df.iloc[idx].values if pd.notna(v))
            if 'Дата транзакции' in row_text:
                header_row = idx
                break
        
        if header_row >= 0:
            headers = [str(h).strip() for h in df.iloc[header_row].values]
            df.columns = headers
            df = df.iloc[header_row + 1:].reset_index(drop=True)
        
        date_col = None
        amount_col = None
        desc_col = None
        counterparty_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'дата транзакции' in col_lower:
                date_col = col
            elif 'дебет' in col_lower and '(' in col_lower:
                amount_col = col
            elif 'информация' in col_lower:
                desc_col = col
            elif 'плательщик' in col_lower:
                counterparty_col = col
        
        if date_col is None and len(df.columns) > 0:
            date_col = df.columns[0]
        if amount_col is None and len(df.columns) > 10:
            amount_col = df.columns[10]
        
        for idx, row in df.iterrows():
            try:
                date = ''
                if date_col in row:
                    date = self._parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
                
                if not date:
                    continue
                
                amount = 0
                if amount_col in row and pd.notna(row[amount_col]):
                    amount_str = str(row[amount_col]).strip()
                    if amount_str.startswith('-+'):
                        amount_str = '-' + amount_str[2:]
                    amount = self._parse_amount(amount_str)
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                counterparty = ''
                if counterparty_col in row:
                    counterparty = str(row[counterparty_col]) if pd.notna(row[counterparty_col]) else ''
                
                type_col = None
                for col in df.columns:
                    if 'тип' in str(col).lower():
                        type_col = col
                        break
                
                if type_col in row and pd.notna(row[type_col]):
                    transaction_type = str(row[type_col])
                    if transaction_type and 'комиссия' not in transaction_type.lower():
                        description = f"{transaction_type} {description}"
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': counterparty[:200],
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_revolut_csv(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Парсинг выписок Revolut"""
        transactions = []
        
        if len(df) > 0:
            headers = [str(h).strip() for h in df.iloc[0].values]
            df.columns = headers
            df = df.iloc[1:].reset_index(drop=True)
        
        date_col = None
        amount_col = None
        desc_col = None
        counterparty_col = None
        type_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'started' in col_lower and 'date' in col_lower:
                date_col = col
            elif 'orig amount' in col_lower:
                amount_col = col
            elif 'description' in col_lower:
                desc_col = col
            elif 'type' in col_lower:
                type_col = col
        
        if amount_col is None:
            for col in df.columns:
                if 'amount' in str(col).lower() and 'orig' not in str(col).lower():
                    amount_col = col
                    break
        
        for idx, row in df.iterrows():
            try:
                date = ''
                if date_col in row:
                    date = self._parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
                
                if not date:
                    continue
                
                amount = 0
                if amount_col in row and pd.notna(row[amount_col]):
                    amount = self._parse_amount(str(row[amount_col]))
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                ref_col = None
                for col in df.columns:
                    if 'reference' in str(col).lower():
                        ref_col = col
                        break
                
                if ref_col in row and pd.notna(row[ref_col]):
                    ref = str(row[ref_col])
                    if ref and ref not in description:
                        description = f"{description} {ref}"
                
                counterparty = ''
                for col in df.columns:
                    if 'payer' in str(col).lower():
                        counterparty = str(row[col]) if pd.notna(row[col]) else ''
                        break
                
                if type_col in row and pd.notna(row[type_col]):
                    ttype = str(row[type_col]).upper()
                    if ttype == 'TRANSFER' and amount > 0:
                        amount = -amount
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': counterparty[:200] if counterparty else '',
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_paysera_csv(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Парсинг выписок Paysera"""
        transactions = []
        
        header_row = -1
        for idx in range(min(10, len(df))):
            row_text = ' '.join(str(v) for v in df.iloc[idx].values if pd.notna(v))
            if 'Дата' in row_text and 'Плательщик' in row_text:
                header_row = idx
                break
        
        if header_row >= 0:
            headers = [str(h).strip() for h in df.iloc[header_row].values]
            headers = [h if h else f'col_{i}' for i, h in enumerate(headers)]
            df.columns = headers
            df = df.iloc[header_row + 1:].reset_index(drop=True)
        
        date_col = None
        amount_col = None
        desc_col = None
        counterparty_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'дата' in col_lower:
                date_col = col
            elif 'сумма' in col_lower:
                amount_col = col
            elif 'назначение' in col_lower:
                desc_col = col
            elif 'плательщик' in col_lower or 'получатель' in col_lower:
                counterparty_col = col
        
        if date_col is None and len(df.columns) > 0:
            date_col = df.columns[0]
        if amount_col is None and len(df.columns) > 4:
            amount_col = df.columns[4]
        
        for idx, row in df.iterrows():
            try:
                date = ''
                if date_col in row:
                    date = self._parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
                
                if not date:
                    continue
                
                amount = 0
                if amount_col in row:
                    amount = self._parse_amount(str(row[amount_col])) if pd.notna(row[amount_col]) else 0
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                counterparty = ''
                if counterparty_col in row:
                    counterparty = str(row[counterparty_col]) if pd.notna(row[counterparty_col]) else ''
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': counterparty[:200],
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_pasha_excel(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Парсинг выписок Pasha Bank (Excel)"""
        transactions = []
        
        header_row = -1
        for idx in range(min(20, len(df))):
            row_text = ' '.join(str(v) for v in df.iloc[idx].values if pd.notna(v))
            if 'Əməliyyat tarixi' in row_text:
                header_row = idx
                break
        
        if header_row >= 0:
            headers = [str(h).strip() for h in df.iloc[header_row].values]
            df.columns = headers
            df = df.iloc[header_row + 1:].reset_index(drop=True)
        
        date_col = None
        amount_col = None
        desc_col = None
        counterparty_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'tarixi' in col_lower:
                date_col = col
            elif 'доход' in col_lower:
                amount_col = col
            elif 'təyinat' in col_lower:
                desc_col = col
            elif 'benefisiar' in col_lower:
                counterparty_col = col
        
        if date_col is None and len(df.columns) > 0:
            date_col = df.columns[0]
        
        for idx, row in df.iterrows():
            try:
                date = ''
                if date_col in row:
                    date = self._parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
                
                if not date:
                    continue
                
                desc_text = ' '.join(str(v) for v in row if pd.notna(v))
                if any(kw in desc_text.lower() for kw in ['dövrün sonuna', 'mövcud balans', 'toplam']):
                    continue
                
                amount = 0
                if amount_col in row:
                    amount = self._parse_amount(str(row[amount_col])) if pd.notna(row[amount_col]) else 0
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                counterparty = ''
                if counterparty_col in row:
                    counterparty = str(row[counterparty_col]) if pd.notna(row[counterparty_col]) else ''
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': counterparty[:200],
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_mashreq_excel(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Парсинг выписок Mashreq Bank (Excel)"""
        transactions = []
        
        header_row = -1
        for idx in range(min(20, len(df))):
            row_text = ' '.join(str(v) for v in df.iloc[idx].values if pd.notna(v))
            if 'Date' in row_text and 'Value Date' in row_text:
                header_row = idx
                break
        
        if header_row >= 0:
            headers = [str(h).strip() for h in df.iloc[header_row].values]
            df.columns = headers
            df = df.iloc[header_row + 1:].reset_index(drop=True)
        
        date_col = None
        amount_col = None
        desc_col = None
        credit_col = None
        debit_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if col_lower == 'date':
                date_col = col
            elif 'credit' in col_lower:
                credit_col = col
            elif 'debit' in col_lower:
                debit_col = col
            elif 'description' in col_lower:
                desc_col = col
        
        if date_col is None and len(df.columns) > 0:
            date_col = df.columns[0]
        
        for idx, row in df.iterrows():
            try:
                date = ''
                if date_col in row:
                    date = self._parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
                
                if not date:
                    continue
                
                amount = 0
                if credit_col in row and pd.notna(row[credit_col]):
                    amount = self._parse_amount(str(row[credit_col]))
                elif debit_col in row and pd.notna(row[debit_col]):
                    amount = -self._parse_amount(str(row[debit_col]))
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': '',
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_budapest_excel(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Парсинг выписок Budapest Bank (Excel)"""
        transactions = []
        
        header_row = -1
        for idx in range(min(20, len(df))):
            row_text = ' '.join(str(v) for v in df.iloc[idx].values if pd.notna(v))
            if 'Serial number' in row_text and 'Value date' in row_text:
                header_row = idx
                break
        
        if header_row >= 0:
            headers = [str(h).strip() for h in df.iloc[header_row].values]
            df.columns = headers
            df = df.iloc[header_row + 1:].reset_index(drop=True)
        
        date_col = None
        amount_col = None
        desc_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'value date' in col_lower:
                date_col = col
            elif 'amount' in col_lower:
                amount_col = col
            elif 'narrative' in col_lower:
                desc_col = col
        
        if date_col is None and len(df.columns) > 1:
            date_col = df.columns[1]
        if amount_col is None and len(df.columns) > 9:
            amount_col = df.columns[9]
        
        for idx, row in df.iterrows():
            try:
                date = ''
                if date_col in row:
                    date = self._parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
                
                if not date:
                    continue
                
                amount = 0
                if amount_col in row and pd.notna(row[amount_col]):
                    amount = self._parse_amount(str(row[amount_col]))
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                type_col = None
                for col in df.columns:
                    if 'transaction type' in str(col).lower():
                        type_col = col
                        break
                
                if type_col in row and pd.notna(row[type_col]):
                    ttype = str(row[type_col])
                    if ttype and ttype not in description:
                        description = f"{ttype} {description}"
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': '',
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_generic_csv(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Универсальный парсер для CSV файлов"""
        transactions = []
        
        date_col = None
        amount_col = None
        desc_col = None
        counterparty_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'date' in col_lower and date_col is None:
                date_col = col
            elif 'amount' in col_lower and amount_col is None:
                amount_col = col
            elif 'description' in col_lower and desc_col is None:
                desc_col = col
            elif 'counterparty' in col_lower and counterparty_col is None:
                counterparty_col = col
            elif 'name' in col_lower and counterparty_col is None:
                counterparty_col = col
        
        for idx, row in df.iterrows():
            try:
                date = ''
                if date_col in row:
                    date = self._parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
                
                if not date:
                    continue
                
                amount = 0
                if amount_col in row:
                    amount = self._parse_amount(str(row[amount_col])) if pd.notna(row[amount_col]) else 0
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                counterparty = ''
                if counterparty_col in row:
                    counterparty = str(row[counterparty_col]) if pd.notna(row[counterparty_col]) else ''
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': counterparty[:200],
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_generic_excel(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Универсальный парсер для Excel файлов"""
        transactions = []
        
        date_col = None
        amount_col = None
        desc_col = None
        counterparty_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'date' in col_lower and date_col is None:
                date_col = col
            elif 'amount' in col_lower and amount_col is None:
                amount_col = col
            elif 'description' in col_lower and desc_col is None:
                desc_col
    import streamlit as st
import pandas as pd
import os
import re
import tempfile
import chardet
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Tuple, Optional

st.set_page_config(page_title="Аналитик банковских выписок", page_icon="🏦", layout="wide")

st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
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

st.markdown('<div class="main-header"><h1>🏦 Аналитик банковских выписок</h1><p>Загрузите выписки — получите структурированные данные</p></div>', unsafe_allow_html=True)

# ==================== СПРАВОЧНИК БАНКОВ ====================
BANK_REFERENCE = {
    'csob': {'name': 'ČSOB', 'country': 'Czech Republic', 'currency': 'CZK'},
    'čsob': {'name': 'ČSOB', 'country': 'Czech Republic', 'currency': 'CZK'},
    'unicredit': {'name': 'UniCredit Bank', 'country': 'Czech Republic', 'currency': 'CZK'},
    'uni credit': {'name': 'UniCredit Bank', 'country': 'Czech Republic', 'currency': 'CZK'},
    'industra': {'name': 'Industra Bank', 'country': 'Latvia', 'currency': 'EUR'},
    'revolut': {'name': 'Revolut', 'country': 'UK', 'currency': 'EUR'},
    'paysera': {'name': 'Paysera', 'country': 'Lithuania', 'currency': 'EUR'},
    'budapest': {'name': 'MKB Bank', 'country': 'Hungary', 'currency': 'HUF'},
    'mkb': {'name': 'MKB Bank', 'country': 'Hungary', 'currency': 'HUF'},
    'pasha': {'name': 'Pasha Bank', 'country': 'Azerbaijan', 'currency': 'AZN'},
    'kapital': {'name': 'Kapital Bank', 'country': 'Azerbaijan', 'currency': 'AZN'},
    'bunda': {'name': 'Pasha Bank', 'country': 'Azerbaijan', 'currency': 'AED'},
    'mashreq': {'name': 'Mashreq Bank', 'country': 'UAE', 'currency': 'AED'},
    'wio': {'name': 'WIO Bank', 'country': 'UAE', 'currency': 'AED'},
    'tinkoff': {'name': 'Тинькофф', 'country': 'Russia', 'currency': 'RUB'},
}

# ==================== ОПРЕДЕЛЕНИЕ ТИПА ФАЙЛА ====================
def detect_file_type(filename: str) -> str:
    """Определяет тип банка по имени файла"""
    filename_lower = filename.lower()
    
    bank_patterns = {
        'csob': ['csob', 'čsob', 'dzibik', 'koruna', 'strojka', 'ostrava'],
        'unicredit': ['unicredit', 'uni credit', 'garpiz'],
        'industra': ['industra', 'plavas'],
        'revolut': ['revolut'],
        'paysera': ['paysera', 'bs property', 'bs rerum'],
        'budapest': ['budapest', 'mkb'],
        'pasha': ['pasha', 'bunda'],
        'kapital': ['kapital', 'saida'],
        'mashreq': ['mashreq'],
        'tinkoff': ['tinkoff'],
    }
    
    for bank_type, patterns in bank_patterns.items():
        for pattern in patterns:
            if pattern in filename_lower:
                return bank_type
    
    return 'unknown'

def detect_file_encoding(file_path: str) -> str:
    """Определяет кодировку файла"""
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)
        result = chardet.detect(raw_data)
        return result['encoding'] if result['encoding'] else 'utf-8'
    except:
        return 'utf-8'

def detect_csv_delimiter(file_path: str) -> str:
    """Определяет разделитель в CSV файле"""
    delimiters = [';', ',', '\t', '|']
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            first_line = f.readline()
        
        counts = {}
        for delim in delimiters:
            counts[delim] = first_line.count(delim)
        
        max_delim = max(counts, key=counts.get)
        return max_delim if counts[max_delim] > 0 else ';'
    except:
        return ';'

# ==================== ПАРСИНГ ФАЙЛОВ ====================
class BankStatementParser:
    """Основной парсер банковских выписок"""
    
    def __init__(self):
        self.transactions = []
        self.bank_name = ''
    
    def parse_file(self, file_content: bytes, filename: str) -> List[Dict]:
        """Основной метод парсинга"""
        self.bank_name = self._get_bank_name(filename)
        
        file_type = detect_file_type(filename)
        ext = os.path.splitext(filename)[1].lower()
        
        if ext in ['.csv']:
            return self._parse_csv(file_content, filename, file_type)
        elif ext in ['.xlsx', '.xls']:
            return self._parse_excel(file_content, filename, file_type)
        else:
            st.warning(f"Неподдерживаемый формат файла: {filename}")
            return []
    
    def _get_bank_name(self, filename: str) -> str:
        """Получает наименование банка из справочника"""
        file_lower = filename.lower()
        
        for key, info in BANK_REFERENCE.items():
            if key in file_lower:
                return info['name']
        
        name = os.path.splitext(filename)[0]
        name = re.sub(r'\d{4}-\d{2}-\d{2}', '', name)
        name = re.sub(r'[_-]', ' ', name).strip()
        return name if name else 'Unknown Bank'
    
    def _parse_csv(self, file_content: bytes, filename: str, file_type: str) -> List[Dict]:
        """Парсинг CSV файлов"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            encoding = detect_file_encoding(tmp_path)
            delimiter = detect_csv_delimiter(tmp_path)
            
            df = pd.read_csv(
                tmp_path,
                sep=delimiter,
                encoding=encoding,
                header=None,
                dtype=str,
                on_bad_lines='skip'
            )
            
            header_row = self._find_header_row(df)
            
            if header_row >= 0:
                headers = [str(h).strip() for h in df.iloc[header_row].values]
                headers = [f'col_{i}' if pd.isna(h) or h == '' else h for i, h in enumerate(headers)]
                
                data_rows = []
                for idx in range(header_row + 1, len(df)):
                    row = list(df.iloc[idx].values)
                    if len(row) < len(headers):
                        row.extend([''] * (len(headers) - len(row)))
                    data_rows.append(row[:len(headers)])
                
                df = pd.DataFrame(data_rows, columns=headers)
            
            if file_type == 'csob':
                return self._parse_csob_csv(df, filename)
            elif file_type == 'unicredit':
                return self._parse_unicredit_csv(df, filename)
            elif file_type == 'industra':
                return self._parse_industra_csv(df, filename)
            elif file_type == 'revolut':
                return self._parse_revolut_csv(df, filename)
            elif file_type == 'paysera':
                return self._parse_paysera_csv(df, filename)
            else:
                return self._parse_generic_csv(df, filename)
                
        except Exception as e:
            st.error(f"Ошибка при парсинге CSV {filename}: {str(e)}")
            return []
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    def _parse_excel(self, file_content: bytes, filename: str, file_type: str) -> List[Dict]:
        """Парсинг Excel файлов"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            df = pd.read_excel(tmp_path, header=None, dtype=str)
            
            header_row = self._find_header_row(df)
            
            if header_row >= 0:
                headers = [str(h).strip() for h in df.iloc[header_row].values]
                headers = [f'col_{i}' if pd.isna(h) or h == '' else h for i, h in enumerate(headers)]
                
                data_rows = []
                for idx in range(header_row + 1, len(df)):
                    row = list(df.iloc[idx].values)
                    if len(row) < len(headers):
                        row.extend([''] * (len(headers) - len(row)))
                    data_rows.append(row[:len(headers)])
                
                df = pd.DataFrame(data_rows, columns=headers)
            
            if file_type in ['pasha', 'kapital']:
                return self._parse_pasha_excel(df, filename)
            elif file_type == 'mashreq':
                return self._parse_mashreq_excel(df, filename)
            elif file_type == 'budapest':
                return self._parse_budapest_excel(df, filename)
            else:
                return self._parse_generic_excel(df, filename)
                
        except Exception as e:
            st.error(f"Ошибка при парсинге Excel {filename}: {str(e)}")
            return []
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    def _find_header_row(self, df: pd.DataFrame) -> int:
        """Находит строку с заголовками в DataFrame"""
        header_keywords = [
            'date', 'дата', 'datum', 'posting date', 'value date',
            'amount', 'сумма', 'payment amount',
            'description', 'описание', 'transaction details',
            'counterparty', 'контрагент', 'payee',
            'account number', 'balance'
        ]
        
        for idx in range(min(20, len(df))):
            row = df.iloc[idx]
            row_text = ' '.join(str(v).lower() for v in row if pd.notna(v))
            
            matches = 0
            for keyword in header_keywords:
                if keyword in row_text:
                    matches += 1
            
            if matches >= 3:
                return idx
        
        return -1
    
    # ==================== ПАРСЕРЫ ДЛЯ РАЗНЫХ БАНКОВ ====================
    
    def _parse_csob_csv(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Парсинг выписок ČSOB"""
        transactions = []
        
        date_col = None
        amount_col = None
        desc_col = None
        counterparty_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'posting date' in col_lower:
                date_col = col
            elif 'payment amount' in col_lower:
                amount_col = col
            elif 'transaction type' in col_lower:
                desc_col = col
            elif 'counterparty' in col_lower:
                counterparty_col = col
            elif 'message to beneficiary and payer' in col_lower and desc_col is None:
                desc_col = col
        
        if date_col is None and len(df.columns) > 4:
            date_col = df.columns[4]
        if amount_col is None and len(df.columns) > 6:
            amount_col = df.columns[6]
        
        for idx, row in df.iterrows():
            try:
                date_val = row[date_col] if date_col in row else None
                if pd.isna(date_val):
                    continue
                date = self._parse_date(str(date_val))
                if not date:
                    continue
                
                amount = 0
                if amount_col in row:
                    amount_str = str(row[amount_col]).strip()
                    amount = self._parse_amount(amount_str)
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                counterparty = ''
                if counterparty_col in row:
                    counterparty = str(row[counterparty_col]) if pd.notna(row[counterparty_col]) else ''
                
                if not description:
                    for col in df.columns:
                        if col not in [date_col, amount_col, counterparty_col]:
                            val = row[col]
                            if pd.notna(val) and str(val).strip():
                                description += str(val) + ' '
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': counterparty[:200] if counterparty else '',
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_unicredit_csv(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Парсинг выписок UniCredit"""
        transactions = []
        
        data_start = 0
        for idx in range(min(5, len(df))):
            row_text = ' '.join(str(v) for v in df.iloc[idx].values if pd.notna(v))
            if 'From Account' in row_text or 'Amount' in row_text:
                data_start = idx + 1
                break
        
        date_col = None
        amount_col = None
        desc_col = None
        counterparty_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'booking date' in col_lower:
                date_col = col
            elif 'amount' in col_lower and 'total' not in col_lower:
                amount_col = col
            elif 'transaction details' in col_lower:
                desc_col = col
            elif 'name' in col_lower:
                counterparty_col = col
        
        for idx in range(data_start, len(df)):
            try:
                row = df.iloc[idx]
                
                if all(pd.isna(v) or str(v).strip() == '' for v in row):
                    continue
                
                date = ''
                if date_col in row:
                    date = self._parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
                
                if not date:
                    continue
                
                amount = 0
                if amount_col in row:
                    amount = self._parse_amount(str(row[amount_col])) if pd.notna(row[amount_col]) else 0
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                counterparty = ''
                if counterparty_col in row:
                    counterparty = str(row[counterparty_col]) if pd.notna(row[counterparty_col]) else ''
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': counterparty[:200],
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_industra_csv(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Парсинг выписок Industra Bank"""
        transactions = []
        
        header_row = -1
        for idx in range(min(20, len(df))):
            row_text = ' '.join(str(v) for v in df.iloc[idx].values if pd.notna(v))
            if 'Дата транзакции' in row_text:
                header_row = idx
                break
        
        if header_row >= 0:
            headers = [str(h).strip() for h in df.iloc[header_row].values]
            df.columns = headers
            df = df.iloc[header_row + 1:].reset_index(drop=True)
        
        date_col = None
        amount_col = None
        desc_col = None
        counterparty_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'дата транзакции' in col_lower:
                date_col = col
            elif 'дебет' in col_lower and '(' in col_lower:
                amount_col = col
            elif 'информация' in col_lower:
                desc_col = col
            elif 'плательщик' in col_lower:
                counterparty_col = col
        
        if date_col is None and len(df.columns) > 0:
            date_col = df.columns[0]
        if amount_col is None and len(df.columns) > 10:
            amount_col = df.columns[10]
        
        for idx, row in df.iterrows():
            try:
                date = ''
                if date_col in row:
                    date = self._parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
                
                if not date:
                    continue
                
                amount = 0
                if amount_col in row and pd.notna(row[amount_col]):
                    amount_str = str(row[amount_col]).strip()
                    if amount_str.startswith('-+'):
                        amount_str = '-' + amount_str[2:]
                    amount = self._parse_amount(amount_str)
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                counterparty = ''
                if counterparty_col in row:
                    counterparty = str(row[counterparty_col]) if pd.notna(row[counterparty_col]) else ''
                
                type_col = None
                for col in df.columns:
                    if 'тип' in str(col).lower():
                        type_col = col
                        break
                
                if type_col in row and pd.notna(row[type_col]):
                    transaction_type = str(row[type_col])
                    if transaction_type and 'комиссия' not in transaction_type.lower():
                        description = f"{transaction_type} {description}"
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': counterparty[:200],
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_revolut_csv(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Парсинг выписок Revolut"""
        transactions = []
        
        if len(df) > 0:
            headers = [str(h).strip() for h in df.iloc[0].values]
            df.columns = headers
            df = df.iloc[1:].reset_index(drop=True)
        
        date_col = None
        amount_col = None
        desc_col = None
        counterparty_col = None
        type_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'started' in col_lower and 'date' in col_lower:
                date_col = col
            elif 'orig amount' in col_lower:
                amount_col = col
            elif 'description' in col_lower:
                desc_col = col
            elif 'type' in col_lower:
                type_col = col
        
        if amount_col is None:
            for col in df.columns:
                if 'amount' in str(col).lower() and 'orig' not in str(col).lower():
                    amount_col = col
                    break
        
        for idx, row in df.iterrows():
            try:
                date = ''
                if date_col in row:
                    date = self._parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
                
                if not date:
                    continue
                
                amount = 0
                if amount_col in row and pd.notna(row[amount_col]):
                    amount = self._parse_amount(str(row[amount_col]))
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                ref_col = None
                for col in df.columns:
                    if 'reference' in str(col).lower():
                        ref_col = col
                        break
                
                if ref_col in row and pd.notna(row[ref_col]):
                    ref = str(row[ref_col])
                    if ref and ref not in description:
                        description = f"{description} {ref}"
                
                counterparty = ''
                for col in df.columns:
                    if 'payer' in str(col).lower():
                        counterparty = str(row[col]) if pd.notna(row[col]) else ''
                        break
                
                if type_col in row and pd.notna(row[type_col]):
                    ttype = str(row[type_col]).upper()
                    if ttype == 'TRANSFER' and amount > 0:
                        amount = -amount
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': counterparty[:200] if counterparty else '',
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_paysera_csv(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Парсинг выписок Paysera"""
        transactions = []
        
        header_row = -1
        for idx in range(min(10, len(df))):
            row_text = ' '.join(str(v) for v in df.iloc[idx].values if pd.notna(v))
            if 'Дата' in row_text and 'Плательщик' in row_text:
                header_row = idx
                break
        
        if header_row >= 0:
            headers = [str(h).strip() for h in df.iloc[header_row].values]
            headers = [h if h else f'col_{i}' for i, h in enumerate(headers)]
            df.columns = headers
            df = df.iloc[header_row + 1:].reset_index(drop=True)
        
        date_col = None
        amount_col = None
        desc_col = None
        counterparty_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'дата' in col_lower:
                date_col = col
            elif 'сумма' in col_lower:
                amount_col = col
            elif 'назначение' in col_lower:
                desc_col = col
            elif 'плательщик' in col_lower or 'получатель' in col_lower:
                counterparty_col = col
        
        if date_col is None and len(df.columns) > 0:
            date_col = df.columns[0]
        if amount_col is None and len(df.columns) > 4:
            amount_col = df.columns[4]
        
        for idx, row in df.iterrows():
            try:
                date = ''
                if date_col in row:
                    date = self._parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
                
                if not date:
                    continue
                
                amount = 0
                if amount_col in row:
                    amount = self._parse_amount(str(row[amount_col])) if pd.notna(row[amount_col]) else 0
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                counterparty = ''
                if counterparty_col in row:
                    counterparty = str(row[counterparty_col]) if pd.notna(row[counterparty_col]) else ''
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': counterparty[:200],
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_pasha_excel(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Парсинг выписок Pasha Bank (Excel)"""
        transactions = []
        
        header_row = -1
        for idx in range(min(20, len(df))):
            row_text = ' '.join(str(v) for v in df.iloc[idx].values if pd.notna(v))
            if 'Əməliyyat tarixi' in row_text:
                header_row = idx
                break
        
        if header_row >= 0:
            headers = [str(h).strip() for h in df.iloc[header_row].values]
            df.columns = headers
            df = df.iloc[header_row + 1:].reset_index(drop=True)
        
        date_col = None
        amount_col = None
        desc_col = None
        counterparty_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'tarixi' in col_lower:
                date_col = col
            elif 'доход' in col_lower:
                amount_col = col
            elif 'təyinat' in col_lower:
                desc_col = col
            elif 'benefisiar' in col_lower:
                counterparty_col = col
        
        if date_col is None and len(df.columns) > 0:
            date_col = df.columns[0]
        
        for idx, row in df.iterrows():
            try:
                date = ''
                if date_col in row:
                    date = self._parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
                
                if not date:
                    continue
                
                desc_text = ' '.join(str(v) for v in row if pd.notna(v))
                if any(kw in desc_text.lower() for kw in ['dövrün sonuna', 'mövcud balans', 'toplam']):
                    continue
                
                amount = 0
                if amount_col in row:
                    amount = self._parse_amount(str(row[amount_col])) if pd.notna(row[amount_col]) else 0
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                counterparty = ''
                if counterparty_col in row:
                    counterparty = str(row[counterparty_col]) if pd.notna(row[counterparty_col]) else ''
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': counterparty[:200],
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_mashreq_excel(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Парсинг выписок Mashreq Bank (Excel)"""
        transactions = []
        
        header_row = -1
        for idx in range(min(20, len(df))):
            row_text = ' '.join(str(v) for v in df.iloc[idx].values if pd.notna(v))
            if 'Date' in row_text and 'Value Date' in row_text:
                header_row = idx
                break
        
        if header_row >= 0:
            headers = [str(h).strip() for h in df.iloc[header_row].values]
            df.columns = headers
            df = df.iloc[header_row + 1:].reset_index(drop=True)
        
        date_col = None
        amount_col = None
        desc_col = None
        credit_col = None
        debit_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if col_lower == 'date':
                date_col = col
            elif 'credit' in col_lower:
                credit_col = col
            elif 'debit' in col_lower:
                debit_col = col
            elif 'description' in col_lower:
                desc_col = col
        
        if date_col is None and len(df.columns) > 0:
            date_col = df.columns[0]
        
        for idx, row in df.iterrows():
            try:
                date = ''
                if date_col in row:
                    date = self._parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
                
                if not date:
                    continue
                
                amount = 0
                if credit_col in row and pd.notna(row[credit_col]):
                    amount = self._parse_amount(str(row[credit_col]))
                elif debit_col in row and pd.notna(row[debit_col]):
                    amount = -self._parse_amount(str(row[debit_col]))
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': '',
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_budapest_excel(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Парсинг выписок Budapest Bank (Excel)"""
        transactions = []
        
        header_row = -1
        for idx in range(min(20, len(df))):
            row_text = ' '.join(str(v) for v in df.iloc[idx].values if pd.notna(v))
            if 'Serial number' in row_text and 'Value date' in row_text:
                header_row = idx
                break
        
        if header_row >= 0:
            headers = [str(h).strip() for h in df.iloc[header_row].values]
            df.columns = headers
            df = df.iloc[header_row + 1:].reset_index(drop=True)
        
        date_col = None
        amount_col = None
        desc_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'value date' in col_lower:
                date_col = col
            elif 'amount' in col_lower:
                amount_col = col
            elif 'narrative' in col_lower:
                desc_col = col
        
        if date_col is None and len(df.columns) > 1:
            date_col = df.columns[1]
        if amount_col is None and len(df.columns) > 9:
            amount_col = df.columns[9]
        
        for idx, row in df.iterrows():
            try:
                date = ''
                if date_col in row:
                    date = self._parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
                
                if not date:
                    continue
                
                amount = 0
                if amount_col in row and pd.notna(row[amount_col]):
                    amount = self._parse_amount(str(row[amount_col]))
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                type_col = None
                for col in df.columns:
                    if 'transaction type' in str(col).lower():
                        type_col = col
                        break
                
                if type_col in row and pd.notna(row[type_col]):
                    ttype = str(row[type_col])
                    if ttype and ttype not in description:
                        description = f"{ttype} {description}"
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': '',
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_generic_csv(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Универсальный парсер для CSV файлов"""
        transactions = []
        
        date_col = None
        amount_col = None
        desc_col = None
        counterparty_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'date' in col_lower and date_col is None:
                date_col = col
            elif 'amount' in col_lower and amount_col is None:
                amount_col = col
            elif 'description' in col_lower and desc_col is None:
                desc_col = col
            elif 'counterparty' in col_lower and counterparty_col is None:
                counterparty_col = col
            elif 'name' in col_lower and counterparty_col is None:
                counterparty_col = col
        
        for idx, row in df.iterrows():
            try:
                date = ''
                if date_col in row:
                    date = self._parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
                
                if not date:
                    continue
                
                amount = 0
                if amount_col in row:
                    amount = self._parse_amount(str(row[amount_col])) if pd.notna(row[amount_col]) else 0
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                counterparty = ''
                if counterparty_col in row:
                    counterparty = str(row[counterparty_col]) if pd.notna(row[counterparty_col]) else ''
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': counterparty[:200],
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_generic_excel(self, df: pd.DataFrame, filename: str) -> List[Dict]:
        """Универсальный парсер для Excel файлов"""
        transactions = []
        
        date_col = None
        amount_col = None
        desc_col = None
        counterparty_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'date' in col_lower and date_col is None:
                date_col = col
            elif 'amount' in col_lower and amount_col is None:
                amount_col = col
            elif 'description' in col_lower and desc_col is None:
                desc_col = col
            elif 'name' in col_lower and counterparty_col is None:
                counterparty_col = col
            elif 'beneficiary' in col_lower and counterparty_col is None:
                counterparty_col = col
        
        for idx, row in df.iterrows():
            try:
                date = ''
                if date_col in row:
                    date = self._parse_date(str(row[date_col])) if pd.notna(row[date_col]) else ''
                
                if not date:
                    continue
                
                amount = 0
                if amount_col in row:
                    amount = self._parse_amount(str(row[amount_col])) if pd.notna(row[amount_col]) else 0
                
                if amount == 0:
                    continue
                
                description = ''
                if desc_col in row:
                    description = str(row[desc_col]) if pd.notna(row[desc_col]) else ''
                
                counterparty = ''
                if counterparty_col in row:
                    counterparty = str(row[counterparty_col]) if pd.notna(row[counterparty_col]) else ''
                
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': counterparty[:200],
                    'Наименование банка': self.bank_name,
                    'Направление': 'Расход' if amount < 0 else 'Доход',
                    'Описание': description[:500]
                })
            except Exception as e:
                continue
        
        return transactions
    
    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================
    
    def _parse_date(self, date_str: str) -> str:
        """Парсинг даты из разных форматов"""
        if not date_str or pd.isna(date_str):
            return ''
        
        date_str = str(date_str).strip()
        
        if ' ' in date_str:
            date_str = date_str.split(' ')[0]
        if 'T' in date_str:
            date_str = date_str.split('T')[0]
        
        formats = [
            "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d",
            "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d", "%d.%m.%y",
            "%d/%m/%y", "%y-%m-%d", "%d-%b-%y", "%d-%b-%Y",
            "%b %d, %Y", "%d %b %Y", "%Y%m%d"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
            except:
                continue
        
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
        
        return date_str
    
    def _parse_amount(self, amount_str: str) -> float:
        """Парсинг суммы из строки"""
        if not amount_str or pd.isna(amount_str):
            return 0.0
        
        amount_str = str(amount_str).strip()
        
        if amount_str in ['', 'nan', '-', 'None', 'null', 'NaN', 'N/A', 'n/a']:
            return 0.0
        
        is_negative = False
        if amount_str.startswith('-'):
            is_negative = True
            amount_str = amount_str[1:]
        elif amount_str.startswith('-+'):
            is_negative = True
            amount_str = amount_str[2:]
        
        amount_str = re.sub(r'\s*[A-Z]{3}\s*$', '', amount_str)
        amount_str = re.sub(r'^\s*[A-Z]{3}\s*', '', amount_str)
        amount_str = amount_str.replace(' ', '').replace('\xa0', '')
        amount_str = amount_str.replace(',', '.')
        amount_str = re.sub(r'[^\d.\-]', '', amount_str)
        
        if not amount_str or amount_str == '.':
            return 0.0
        
        try:
            value = float(amount_str)
            return -abs(value) if is_negative else abs(value)
        except:
            return 0.0

# ==================== ИНТЕРФЕЙС ====================

def main():
    st.markdown("### 📂 Загрузите банковские выписки")
    st.markdown("Поддерживаются форматы: **CSV, XLSX, XLS**")
    
    uploaded_files = st.file_uploader(
        "Выберите файлы",
        type=['csv', 'xlsx', 'xls'],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        st.success(f"✅ Загружено файлов: {len(uploaded_files)}")
        
        if st.button("🚀 Обработать файлы"):
            all_transactions = []
            failed_files = []
            parser = BankStatementParser()
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Обработка: {uploaded_file.name}")
                
                try:
                    content = uploaded_file.read()
                    transactions = parser.parse_file(content, uploaded_file.name)
                    
                    if transactions:
                        all_transactions.extend(transactions)
                        st.info(f"✅ {uploaded_file.name}: {len(transactions)} операций")
                    else:
                        failed_files.append(uploaded_file.name)
                except Exception as e:
                    failed_files.append(f"{uploaded_file.name} (ошибка: {str(e)})")
                
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            status_text.text("✅ Обработка завершена!")
            
            if all_transactions:
                df = pd.DataFrame(all_transactions)
                
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("📊 Всего операций", len(all_transactions))
                with col2:
                    доход = df[df['Сумма'] > 0]['Сумма'].sum()
                    st.metric("📈 Доходы", f"{доход:,.2f}")
                with col3:
                    расход = abs(df[df['Сумма'] < 0]['Сумма'].sum())
                    st.metric("📉 Расходы", f"{расход:,.2f}")
                
                st.markdown("### 📋 Результат обработки")
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Транзакции', index=False)
                    
                    bank_summary = df.groupby('Наименование банка').agg({
                        'Сумма': ['count', 'sum']
                    }).round(2)
                    bank_summary.columns = ['Количество операций', 'Сумма']
                    bank_summary.to_excel(writer, sheet_name='Сводка по банкам')
                
                output.seek(0)
                st.download_button(
                    label="📥 Скачать Excel",
                    data=output,
                    file_name="анализ_банковских_выписок.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            if failed_files:
                st.warning(f"⚠️ Не удалось обработать: {len(failed_files)} файлов")
                for f in failed_files:
                    st.write(f"- {f}")

if __name__ == "__main__":
    main()
