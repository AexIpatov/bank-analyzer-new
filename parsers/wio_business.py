from .base_parser import BaseParser

class WioBusinessParser(BaseParser):
    """Парсер для WIO Business Bank (Excel/CSV)"""
    
    def parse(self, file_content, file_name):
        df = self._read_file(file_content, file_name)
        
        transactions = []
        for _, row in df.iterrows():
            date_str = str(row.get('Date', ''))
            date = date_str[:10] if len(date_str) >= 10 else ''
            amount = float(row.get('Amount', 0)) if pd.notna(row.get('Amount', 0)) else 0
            if amount == 0:
                continue
            description = str(row.get('Description', ''))
            
            article, direction, subdirection, amount = self._get_article(description, amount)
            
            transactions.append({
                'date': date,
                'amount': amount,
                'currency': row.get('Account currency', 'AED'),
                'account_name': file_name.replace('.csv', '').replace('.xls', '').replace('.xlsx', ''),
                'description': description[:200],
                'article_name': article,
                'direction': direction,
                'subdirection': subdirection
            })
        return transactions
