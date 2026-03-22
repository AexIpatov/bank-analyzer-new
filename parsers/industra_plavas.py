import pandas as pd
from .base_parser import BaseParser

class IndustriPlavasParser(BaseParser):
    """Парсер для Industra Bank-Plavas 1.xls"""
    
    def parse(self, file_content, file_name):
        df = self._read_file(file_content, file_name)
        
        header_row = None
        for idx, row in df.iterrows():
            row_text = ' '.join(str(v) for v in row.values if pd.notna(v))
            if 'Дата транзакции' in row_text:
                header_row = idx
                break
        
        if header_row is None:
            return []
        
        df.columns = df.iloc[header_row]
        df = df.iloc[header_row + 1:].reset_index(drop=True)
        
        transactions = []
        for _, row in df.iterrows():
            date_val = row.get('Дата транзакции', '')
            if pd.isna(date_val):
                continue
            
            date_str = str(date_val)
            if '.' in date_str:
                parts = date_str.split('.')
                if len(parts) == 3:
                    date = f"{parts[2]}-{parts[1]}-{parts[0]}"
                else:
                    date = date_str[:10]
            else:
                date = date_str[:10]
            
            amount = 0
            debit = row.get('Дебет(D)', row.get('Дебет(Д)', 0))
            credit = row.get('Кредит(C)', row.get('Кредит(С)', 0))
            
            if pd.notna(credit) and credit != 0:
                amount = float(credit)
            elif pd.notna(debit) and debit != 0:
                amount = -float(debit)
            
            if amount == 0:
                continue
            
            description = str(row.get('Информация о транзакции', ''))
            if not description or description == 'nan':
                description = str(row.get('Тип транзакции', ''))
            if not description or description == 'nan':
                description = str(row.get('Получатель / Плательщик', ''))
            
            # Простое определение статьи
            desc_lower = description.lower()
            if 'комиссия' in desc_lower:
                article = '1.2.17 РКО'
                direction = 'Расходы'
                subdirection = 'Банковские комиссии'
            elif 'арендн' in desc_lower or 'rent' in desc_lower:
                article = '1.1.1.1 Арендная плата'
                direction = 'Доходы'
                subdirection = 'Арендная плата'
            elif 'зарплат' in desc_lower:
                article = '1.2.15.1 Зарплата'
                direction = 'Расходы'
                subdirection = 'Зарплата'
                if amount > 0:
                    amount = -amount
            elif 'налог' in desc_lower:
                article = '1.2.16 Налоги'
                direction = 'Расходы'
                subdirection = 'Налоги'
                if amount > 0:
                    amount = -amount
            else:
                if amount > 0:
                    article = '1.1.1.1 Арендная плата'
                    direction = 'Доходы'
                    subdirection = 'Арендная плата'
                else:
                    article = '1.2.8.1 Обслуживание объектов'
                    direction = 'Расходы'
                    subdirection = 'Обслуживание'
            
            transactions.append({
                'date': date,
                'amount': amount,
                'currency': 'EUR',
                'account_name': file_name.replace('.xls', '').replace('.xlsx', '').replace('.csv', ''),
                'description': description[:300],
                'article_name': article,
                'direction': direction,
                'subdirection': subdirection
            })
        
        return transactions
