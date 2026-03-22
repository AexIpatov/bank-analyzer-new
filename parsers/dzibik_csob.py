from .base_parser import BaseParser

class DzibikCsobParser(BaseParser):
    """Парсер для DŽIBIK Main CSOB CZK (Excel/CSV)"""
    
    def parse(self, file_content, file_name):
        df = self._read_file(file_content, file_name)
        
        transactions = []
        for _, row in df.iterrows():
            date_val = row.get('value date', row.get('posting date', ''))
            if pd.isna(date_val):
                continue
            date = str(date_val)[:10] if len(str(date_val)) >= 10 else ''
            amount_str = str(row.get('payment amount', '0')).replace(',', '.')
            try:
                amount = float(amount_str)
            except:
                amount = 0
            if amount == 0:
                continue
            description = str(row.get('message to beneficiary and payer', ''))
            
            article, direction, subdirection, amount = self._get_article(description, amount)
            
            transactions.append({
                'date': date,
                'amount': amount,
                'currency': 'CZK',
                'account_name': file_name.replace('.csv', '').replace('.xls', '').replace('.xlsx', ''),
                'description': description[:200],
                'article_name': article,
                'direction': direction,
                'subdirection': subdirection
            })
        return transactions
