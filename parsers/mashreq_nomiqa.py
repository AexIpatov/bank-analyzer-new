import pandas as pd
from .base_parser import BaseParser

class MashreqNomiqaParser(BaseParser):
    """Парсер для MASHREQ BANK-AED-NOMIQA (Excel/CSV)"""
    
    def parse(self, file_content, file_name):
        df = self._read_file(file_content, file_name)
        
        # Заголовки на 9-й строке
        try:
            df.columns = df.iloc[8]
            df = df.iloc[9:].reset_index(drop=True)
        except:
            pass
        
        transactions = []
        for _, row in df.iterrows():
            date_str = str(row.get('Date', ''))
            if pd.isna(date_str) or date_str == 'nan':
                continue
            date = date_str[:10] if len(date_str) >= 10 else ''
            
            credit = row.get('Credit', 0)
            debit = row.get('Debit', 0)
            amount = credit if pd.notna(credit) and credit != 0 else -debit if pd.notna(debit) and debit != 0 else 0
            if amount == 0:
                continue
            description = str(row.get('Description', ''))
            
            article, direction, subdirection, amount = self._get_article(description, amount)
            
            transactions.append({
                'date': date,
                'amount': amount,
                'currency': 'AED',
                'account_name': file_name.replace('.xlsx', '').replace('.xls', '').replace('.csv', ''),
                'description': description[:200],
                'article_name': article,
                'direction': direction,
                'subdirection': subdirection
            })
        return transactions
