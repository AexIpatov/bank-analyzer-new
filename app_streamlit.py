import pandas as pd
import re
from typing import Optional, List, Tuple

class HeaderDetector:
    """Умный детектор заголовков для финансовых выписок"""
    
    def __init__(self):
        # Расширенный список ключевых слов для заголовков
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
        
        # Паттерны для определения типа файла
        self.file_patterns = {
            'industra': [
                r'industra', r'индустра', r'банк.*индустра',
                r'.*industra.*\.(csv|xlsx|xls)$'
            ],
            'revolut': [
                r'revolut', r'револют', r'.*revolut.*statement',
                r'account-statement.*\.csv$'
            ],
            'budapest': [
                r'budapest', r'будапешт', r'budapest.*bank',
                r'bb.*\.(csv|xlsx|xls)$'
            ],
            'pasha': [
                r'pasha', r'паша', r'kapital', r'капитал',
                r'pasha.*bank', r'kapital.*bank'
            ]
        }
    
    def detect_file_type(self, filename: str) -> str:
        """Определяет тип файла по имени"""
        filename_lower = filename.lower()
        
        for file_type, patterns in self.file_patterns.items():
            for pattern in patterns:
                if re.search(pattern, filename_lower, re.IGNORECASE):
                    return file_type
        
        # Проверяем содержимое первых строк для определения
        return "unknown"
    
    def find_header_row(self, df: pd.DataFrame, max_rows_to_check: int = 20) -> Optional[int]:
        """
        Находит строку с заголовками в DataFrame
        
        Args:
            df: DataFrame для поиска
            max_rows_to_check: максимальное количество строк для проверки
        
        Returns:
            Номер строки с заголовками или None если не найдено
        """
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
        
        # Минимальный порог для уверенности
        if best_match_score >= 2:  # Найдено как минимум 2 ключевых столбца
            return best_match_row
        
        return None
    
    def _calculate_header_score(self, row: pd.Series) -> int:
        """Вычисляет оценку того, является ли строка заголовком"""
        score = 0
        
        for cell in row:
            if pd.isna(cell):
                continue
            
            cell_str = str(cell).lower().strip()
            
            # Проверяем соответствие паттернам
            for column_type, keywords in self.header_patterns.items():
                for keyword in keywords:
                    if keyword in cell_str:
                        score += 1
                        break  # Не учитываем повторные совпадения в одной ячейке
        
        # Штрафуем строки, которые выглядят как данные (содержат даты или числа)
        for cell in row:
            if pd.isna(cell):
                continue
            
            cell_str = str(cell).strip()
            
            # Проверяем, является ли ячейка датой
            if self._looks_like_date(cell_str):
                score -= 1
            
            # Проверяем, является ли ячейка числом (суммой)
            if self._looks_like_amount(cell_str):
                score -= 1
        
        return max(0, score)
    
    def _looks_like_date(self, value: str) -> bool:
        """Проверяет, похоже ли значение на дату"""
        date_patterns = [
            r'\d{4}[-./]\d{1,2}[-./]\d{1,2}',  # YYYY-MM-DD
            r'\d{1,2}[-./]\d{1,2}[-./]\d{4}',  # DD-MM-YYYY
            r'\d{1,2}[-./]\d{1,2}[-./]\d{2}',  # DD-MM-YY
        ]
        
        for pattern in date_patterns:
            if re.match(pattern, value):
                return True
        
        return False
    
    def _looks_like_amount(self, value: str) -> bool:
        """Проверяет, похоже ли значение на денежную сумму"""
        amount_patterns = [
            r'^-?\d+[.,]\d{2}$',  # 123.45 или -123.45
            r'^-?\d+[.,]\d{2}\s*[A-Z]{3}$',  # 123.45 EUR
            r'^-?\d+\s*[A-Z]{3}$',  # 123 EUR
        ]
        
        for pattern in amount_patterns:
            if re.match(pattern, value.replace(' ', '')):
                return True
        
        return False
    
    def get_expected_columns(self, file_type: str) -> List[str]:
        """Возвращает ожидаемые колонки для типа файла"""
        column_templates = {
            'industra': ['Дата транзакции', 'Дебет(D)', 'Кредит(C)', 'Описание'],
            'revolut': ['Date started (UTC)', 'Type', 'Description', 'Amount'],
            'budapest': ['Serial number', 'Value date', 'Amount', 'Description'],
            'pasha': ['Дата', 'Сумма', 'Валюта', 'Описание'],
            'unknown': ['Date', 'Amount', 'Currency', 'Description']
        }
        
        return column_templates.get(file_type, column_templates['unknown'])
    
    def validate_header_row(self, df: pd.DataFrame, header_row: int) -> bool:
        """
        Проверяет, действительно ли найденная строка является заголовком
        
        Args:
            df: DataFrame
            header_row: предполагаемая строка заголовка
        
        Returns:
            True если строка похожа на заголовок
        """
        if header_row is None or header_row >= len(df):
            return False
        
        header = df.iloc[header_row]
        
        # Проверяем, что в заголовке нет числовых значений
        numeric_count = 0
        for cell in header:
            if pd.isna(cell):
                continue
            
            cell_str = str(cell).strip()
            
            # Проверяем, является ли значение числом
            try:
                float(cell_str.replace(',', '.'))
                numeric_count += 1
            except ValueError:
                # Проверяем, является ли значение датой
                if self._looks_like_date(cell_str):
                    numeric_count += 1
        
        # Если больше половины ячеек выглядят как данные, это не заголовок
        if numeric_count > len(header) * 0.5:
            return False
        
        return True
