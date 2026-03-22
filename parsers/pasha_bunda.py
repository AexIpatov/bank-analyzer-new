import pandas as pd
from .base_parser import BaseParser

class PashaBundaParser(BaseParser):
    """Парсер для Pasha Bunda (Pasha Bank)"""
    
    def parse(self, file_content, file_name):
        df = self._read_file(file_content, file_name)
        
        # Ищем строку с заголовками
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
            
            # Преобразование даты из DD.MM.YYYY
            date = self._parse_date(date_str)
            
            income = row.get('Mədaxil', 0)
            expense = row.get('Məxaric', 0)
            amount = income if pd.notna(income) and income != 0 else -expense if pd.notna(expense) and expense != 0 else 0
            if amount == 0:
                continue
            
            description = str(row.get('Təyinat', ''))
            
            article, direction, subdirection, amount = self._get_article(description, amount)
            
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
