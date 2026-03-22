import pandas as pd
import re
from .base_parser import BaseParser

class PayseraPropertyParser(BaseParser):
    """Парсер для Paysera-BS PROPERTY, SIA (Excel/CSV)"""
    
    def parse(self, file_content, file_name):
        df = self._read_file(file_content, file_name)
        
        header_row = None
        for idx, row in df.iterrows():
            row_text = ' '.join(str(v) for v in row.values if pd.notna(v))
            if 'Date and time' in row_text:
                header_row = idx
                break
        
        if header_row is not None:
            df.columns = df.iloc[header_row]
            df = df.iloc[header_row + 1:].reset_index(drop=True)
        
        transactions = []
        for _, row in df.iterrows():
            if pd.isna(row.get('Date and time', pd.NA)):
                continue
            
            date_str = str(row.get('Date and time', ''))
            date = date_str[:10] if len(date_str) >= 10 else ''
            
            amount_str = str(row.get('Amount and currency', '0'))
            amount = 0
            amount_match = re.search(r'([-]?\d+[.,]?\d*)', amount_str)
            if amount_match:
                try:
                    amount = float(amount_match.group(1).replace(',', '.'))
                except:
                    amount = 0
            
            cd = str(row.get('Credit/Debit', '')).upper()
            if cd == 'D' and amount > 0:
                amount = -amount
            
            description = str(row.get('Purpose of payment', ''))
            if not description or description == 'nan':
                description = str(row.get('Recipient / Payer', ''))
            
            if date and amount != 0:
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
