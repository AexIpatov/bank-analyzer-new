import pandas as pd
import re
from .base_parser import BaseParser

class AntonijasIndustraParser(BaseParser):
    """Парсер для ANTONIJAS NAMS 14 SIA-Industra (Excel/CSV)"""
    
    def parse(self, file_content, file_name):
        df = self._read_file(file_content, file_name)
        
        # Ищем строку с заголовками
        header_row = None
        for idx, row in df.iterrows():
            row_text = ' '.join(str(v) for v in row.values if pd.notna(v))
            if 'Дата транзакции' in row_text:
                header_row = idx
                break
        
        if header_row is not None:
            df.columns = df.iloc[header_row]
            df = df.iloc[header_row + 1:].reset_index(drop=True)
        
        transactions = []
        for _, row in df.iterrows():
            date_val = row.get('Дата транзакции', '')
            if pd.isna(date_val):
                continue
            date = str(date_val)[:10] if len(str(date_val)) >= 10 else str(date_val)
            
            amount = 0
            debit = row.get('Дебет(D)', row.get('Дебет(Д)', 0))
            credit = row.get('Кредит(C)', row.get('Кредит(С)', 0))
            
            if pd.notna(credit) and credit != 0:
                amount = float(credit)
            elif pd.notna(debit) and debit != 0:
                amount = -float(debit)
            
            if amount != 0:
                description = str(row.get('Информация о транзакции', ''))
                if not description or description == 'nan':
                    description = str(row.get('Тип транзакции', ''))
                if not description or description == 'nan':
                    description = str(row.get('Получатель / Плательщик', ''))
                
                article, direction, subdirection, amount = self._get_article(description, amount)
                
                transactions.append({
                    'date': date,
                    'amount': amount,
                    'currency': 'EUR',
                    'account_name': file_name.replace('.xls', '').replace('.xlsx', '').replace('.csv', ''),
                    'description': description[:200],
                    'article_name': article,
                    'direction': direction,
                    'subdirection': subdirection
                })
        return transactions
