import pandas as pd
import os
import re
import tempfile
import chardet

class BaseParser:
    """Базовый класс для всех парсеров"""
    
    def _read_file(self, file_content, file_name):
        """Универсальное чтение файла (Excel или CSV)"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            if file_name.lower().endswith(('.xls', '.xlsx')):
                try:
                    df = pd.read_excel(tmp_path, engine='xlrd')
                except:
                    df = pd.read_excel(tmp_path, engine='openpyxl')
            else:
                with open(tmp_path, 'rb') as f:
                    raw = f.read()
                result = chardet.detect(raw[:10000])
                encoding = result['encoding'] if result['encoding'] else 'utf-8'
                
                for sep in [';', ',', '\t']:
                    try:
                        df = pd.read_csv(tmp_path, sep=sep, encoding=encoding, on_bad_lines='skip')
                        if len(df.columns) > 1:
                            break
                    except:
                        continue
                if len(df.columns) <= 1:
                    df = pd.read_csv(tmp_path, sep=';', encoding='latin1', on_bad_lines='skip')
        except Exception as e:
            os.unlink(tmp_path)
            raise e
        
        os.unlink(tmp_path)
        return df
    
    def _get_article(self, description, amount):
        """Определение статьи по описанию"""
        desc_lower = description.lower()
        
        articles = [
            ('комиссия', '1.2.17 РКО', 'Расходы', 'Банковские комиссии'),
            ('commission', '1.2.17 РКО', 'Расходы', 'Банковские комиссии'),
            ('fee', '1.2.17 РКО', 'Расходы', 'Банковские комиссии'),
            ('арендн', '1.1.1.1 Арендная плата', 'Доходы', 'Арендная плата'),
            ('rent', '1.1.1.1 Арендная плата', 'Доходы', 'Арендная плата'),
            ('money added', '1.1.1.1 Арендная плата', 'Доходы', 'Арендная плата'),
            ('компенсац', '1.1.2.3 Компенсация по коммунальным расходам', 'Доходы', 'Компенсация'),
            ('зарплат', '1.2.15.1 Зарплата', 'Расходы', 'Зарплата'),
            ('налог', '1.2.16 Налоги', 'Расходы', 'Налоги'),
            ('vid', '1.2.16 Налоги', 'Расходы', 'Налоги'),
            ('latvenergo', '1.2.10.5 Электричество', 'Расходы', 'Электричество'),
            ('rigas udens', '1.2.10.3 Вода', 'Расходы', 'Вода'),
            ('balta', '1.2.8.2 Страхование', 'Расходы', 'Страхование'),
            ('airbnb', '1.1.1.2 Поступления систем бронирования', 'Доходы', 'Краткосрочная аренда'),
            ('booking', '1.1.1.2 Поступления систем бронирования', 'Доходы', 'Краткосрочная аренда'),
            ('careem', '1.2.2 Командировочные расходы', 'Расходы', 'Транспорт'),
            ('flydubai', '1.2.2 Командировочные расходы', 'Расходы', 'Авиабилеты'),
            ('tiktok', '1.2.3 Оплата рекламных систем', 'Расходы', 'Маркетинг'),
            ('facebook', '1.2.3 Оплата рекламных систем', 'Расходы', 'Маркетинг'),
            ('asana', '1.2.9.3 IT сервисы', 'Расходы', 'IT сервисы'),
        ]
        
        for kw, article, direction, subdirection in articles:
            if kw in desc_lower:
                if direction == 'Расходы' and amount > 0:
                    amount = -amount
                return article, direction, subdirection, amount
        
        if amount > 0:
            return '1.1.1.1 Арендная плата', 'Доходы', 'Арендная плата', amount
        else:
            return '1.2.8.1 Обслуживание объектов', 'Расходы', 'Обслуживание', amount
