from .base_parser import BaseParser

class GarpizUnicreditParser(BaseParser):
    """Парсер для Garpiz UniCredit Bank CZK_0226.csv (UniCredit)"""
    
    def parse(self, file_content, file_name):
        df = self._read_file(file_content, file_name)
        
        # Ищем столбцы
        amount_col = None
        date_col = None
        desc_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'amount' in col_lower:
                amount_col = col
            if 'booking' in col_lower or 'date' in col_lower:
                date_col = col
            if 'transaction' in col_lower or 'details' in col_lower:
                desc_col = col
        
        if amount_col is None:
            return []
        
        transactions = []
        for _, row in df.iterrows():
            amount = 0
            try:
                amount_str = str(row[amount_col]).replace(',', '.')
                amount = float(amount_str)
            except:
                continue
            
            if amount == 0:
                continue
            
            # Дата
            date = ''
            if date_col and pd.notna(row[date_col]):
                date_str = str(row[date_col])
                date = self._parse_date(date_str)
            
            # Описание
            description = ''
            if desc_col and pd.notna(row[desc_col]):
                description = str(row[desc_col])
            
            if date:
                article, direction, subdirection, amount = self._get_article(description, amount)
                
                transactions.append({
                    'date': date,
                    'amount': amount,
                    'currency': 'CZK',
                    'account_name': file_name.replace('.csv', '').replace('.xls', '').replace('.xlsx', ''),
                    'description': description[:300],
                    'article_name': article,
                    'direction': direction,
                    'subdirection': subdirection
                })
        
        return transactions
