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
            if date_col
