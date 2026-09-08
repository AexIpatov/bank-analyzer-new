# ==================== УНИВЕРСАЛЬНЫЙ ПАРСЕР ====================

def parse_generic(df: pd.DataFrame, account_name: str) -> List[Dict]:
    """Универсальный парсер для неизвестных форматов"""
    transactions = []
    
    # Ищем первую строку с датой и суммой
    for idx, row in df.iterrows():
        try:
            # Проверяем все колонки на наличие даты
            date = None
            amount = 0.0
            description = ''
            
            for col in range(len(row)):
                val = str(row.iloc[col]) if pd.notna(row.iloc[col]) else ''
                if not val:
                    continue
                
                # Проверяем, не является ли значение датой
                parsed_date = parse_date(val)
                if parsed_date and parsed_date != val:
                    date = parsed_date
                    continue
                
                # Проверяем, не является ли значение суммой
                parsed_amount = parse_amount(val)
                if parsed_amount != 0.0:
                    amount = parsed_amount
                    continue
                
                # Собираем описание
                if val and len(val) > 2:
                    description += val + ' '
            
            if date and amount != 0.0:
                transactions.append({
                    'Дата': date,
                    'Сумма': amount,
                    'Контрагент': '',
                    'Наименование счета': account_name,
                    'Описание': description[:500]
                })
        except Exception as e:
            continue
    
    return transactions
