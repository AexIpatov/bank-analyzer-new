# -*- coding: utf-8 -*-
"""
Аналитик банковских выписок — Streamlit-приложение.

Парсит выписки 25+ банков (CSOB, Tinkoff, BluOr, MKB, N26, Paysera, Revolut,
UniCredit, WIO, Pasha Bank, Kapital Bank, Mashreq, Industra, FIO, Regina Alfa,
JenHor Unelma, RAK Bank, Saida Wise/N26, Wise, B1 Estate, Garpiz, TwoHills,
Koruna, Stalkin, AN14/Plavas1/KL59 Estate и др.)
в форматах CSV / XLSX / XLS / DOCX / PDF и сводит всё в единый Excel-отчёт.

Все правки этой итерации помечены тегом  # [FIX-N]
"""
from __future__ import annotations

import io
import os
import re
import csv
import html
import json
import traceback
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import streamlit as st
import pandas as pd

# --- Опциональные зависимости (импортируем мягко, чтобы приложение не падало) ---
try:
    import openpyxl  # noqa
except Exception:
    openpyxl = None

try:
    import xlrd  # noqa
except Exception:
    xlrd = None

try:
    import pdfplumber  # noqa
except Exception:
    pdfplumber = None

try:
    import docx  # python-docx
    from docx import Document  # noqa
except Exception:
    docx = None
    Document = None

try:
    import chardet  # noqa
except Exception:
    chardet = None


# =============================================================================
#                              ОБЩИЕ КОНСТАНТЫ
# =============================================================================

TXN_FIELDS = ("Дата", "Сумма", "Контрагент", "Наименование счета", "Описание")

# Служебные слова, которые никогда не являются транзакциями
SERVICE_WORDS = (
    "начальный остаток", "конечный остаток", "входящий остаток",
    "исходящий остаток", "opening balance", "closing balance",
    "дебет (d)", "кредит (c)", "debit (d)", "credit (c)",
    "итого", "total", "выписка по счету", "statement of account",
)


# =============================================================================
#                              ОБЩИЕ УТИЛИТЫ
# =============================================================================

def _empty_txn(account_name: str) -> Dict[str, Any]:
    """Пустая транзакция — шаблон."""
    return {
        "Дата": "",
        "Сумма": 0.0,
        "Контрагент": "",
        "Наименование счета": account_name,
        "Описание": "",
    }


def safe_str(v: Any) -> str:
    """
    Аккуратное приведение к строке:
      - None / NaN  -> ''
      - убираем неразрывные пробелы, BOM
      - strip
    """
    if v is None:
        return ""
    try:
        if isinstance(v, float) and v != v:  # NaN
            return ""
    except Exception:
        pass
    s = str(v)
    s = s.replace("\u00a0", " ").replace("\ufeff", "")
    return s.strip()


def _text_quality_score(s: str) -> float:
    """
    Эвристика «читаемости» текста: доля печатных ASCII/букв/пунктуации.
    Нужна для выбора правильной кодировки при чтении бинарных файлов.
    """
    if not s:
        return 0.0
    good = 0
    bad = 0
    for ch in s:
        o = ord(ch)
        if ch in "\r\n\t":
            good += 1
        elif 32 <= o < 127:
            good += 1
        elif 0x0400 <= o <= 0x04FF:  # кириллица
            good += 1
        elif 0x00C0 <= o <= 0x024F:  # латиница с диакритикой
            good += 1
        elif ch in "€£¥₽₸₴₺₼₾":
            good += 1
        elif o < 32:
            bad += 1
        else:
            bad += 1
    return good / max(1, (good + bad))


def read_text_with_encoding(content: bytes) -> str:
    """
    Читаем текст с эвристикой качества и chardet-fallback.
    Также чистим нулевые байты (частая проблема BIFF-as-text).
    """
    if not content:
        return ""

    # Убираем нулевые байты — иногда попадают из «бинарных» CSV
    content_clean = content.replace(b"\x00", b"")

    candidates: List[str] = []
    # Сначала BOM-детект
    if content_clean.startswith(b"\xef\xbb\xbf"):
        candidates.append("utf-8-sig")
    if content_clean.startswith(b"\xff\xfe") or content_clean.startswith(b"\xfe\xff"):
        candidates.append("utf-16")
    candidates += ["utf-8", "cp1252", "cp1251", "latin-1"]

    best_text = ""
    best_score = -1.0
    for enc in candidates:
        try:
            t = content_clean.decode(enc, errors="strict")
        except Exception:
            try:
                t = content_clean.decode(enc, errors="replace")
            except Exception:
                continue
        sc = _text_quality_score(t[:20000])
        if sc > best_score:
            best_score = sc
            best_text = t
        # Если декодирование прошло без ошибок и текст хороший — берём
        if sc > 0.9:
            return t

    # chardet fallback
    if chardet is not None and best_score < 0.9:
        try:
            det = chardet.detect(content_clean[:200000])
            enc = (det or {}).get("encoding")
            if enc:
                try:
                    t = content_clean.decode(enc, errors="replace")
                    sc = _text_quality_score(t[:20000])
                    if sc > best_score:
                        best_text = t
                except Exception:
                    pass
        except Exception:
            pass

    return best_text


def parse_amount(v: Any) -> float:
    """
    Универсальный парсер суммы:
      - "1.234"        -> 1234
      - "1,234.56"     -> 1234.56
      - "1 234,56"     -> 1234.56
      - "(123)"        -> -123
      - "1.234,56"     -> 1234.56
      - "123.45"       -> 123.45
      - "123.45-"      -> -123.45
      - "1 234,56 EUR" -> 1234.56
      - "Kč 1 234"     -> 1234
    """
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        try:
            f = float(v)
            if f != f:
                return 0.0
            return f
        except Exception:
            return 0.0

    s = safe_str(v)
    if not s:
        return 0.0

    negative = False
    # Скобки = минус
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    # Явный минус
    if s.strip().startswith("-"):
        negative = True
    # Хвостовой минус (некоторые банки: "123.45-")
    if s.strip().endswith("-"):
        negative = True

    # Убираем всё, кроме цифр, разделителей, минуса
    s = re.sub(r"[^\d\.,\-\s]", "", s)
    s = s.replace("\u00a0", " ").replace(" ", "")
    s = s.replace("-", "")

    if not s:
        return 0.0

    last_dot = s.rfind(".")
    last_comma = s.rfind(",")

    if last_dot == -1 and last_comma == -1:
        try:
            f = float(s)
        except Exception:
            return 0.0
        return -f if negative else f

    # Оба присутствуют: тот, что правее — десятичный
    if last_dot != -1 and last_comma != -1:
        if last_comma > last_dot:
            # 1.234,56 -> european
            s = s.replace(".", "").replace(",", ".")
        else:
            # 1,234.56 -> us
            s = s.replace(",", "")
    else:
        sep = "." if last_dot != -1 else ","
        parts = s.split(sep)
        if len(parts) > 2:
            # Несколько разделителей = тысячи
            s = "".join(parts)
        else:
            int_part = parts[0]
            frac_part = parts[1] if len(parts) > 1 else ""
            # Если после разделителя ровно 3 цифры и целая часть не пустая —
            # это скорее тысячи (1.234 -> 1234), кроме случая 0.xxx
            if len(frac_part) == 3 and int_part and int_part != "0":
                s = int_part + frac_part
            else:
                s = int_part + "." + frac_part

    try:
        f = float(s)
    except Exception:
        return 0.0
    return -f if negative else f


def format_amount(v: Any) -> str:
    """Формат суммы: '1 234,56'. Не даём '-0,00'."""
    try:
        f = float(v)
    except Exception:
        return ""
    if abs(f) < 0.005:
        f = 0.0
    s = f"{f:,.2f}".replace(",", " ").replace(".", ",")
    return s


def parse_date(v: Any) -> str:
    """
    Универсальный парсер даты -> 'dd-mm-yyyy'.
    Поддерживает:
      dd.mm.yyyy, dd/mm/yyyy, dd-mm-yyyy, yyyy-mm-dd,
      dd.mm.yy, mm/dd/yyyy (fallback),
      dd-MMM-yyyy (Aug), MMM dd, yyyy,
      ISO с временем.
    """
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%d-%m-%Y")
    if isinstance(v, pd.Timestamp):
        return v.strftime("%d-%m-%Y")

    s = safe_str(v)
    if not s:
        return ""

    # Убираем время, если есть
    s = re.split(r"[ T]", s, maxsplit=1)[0]
    s = s.strip().strip(",")

    formats = [
        "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y",
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
        "%d.%m.%y", "%d/%m/%y", "%d-%m-%y",
        "%y-%m-%d",
        "%d-%b-%Y", "%d-%b-%y", "%d %b %Y", "%d %b %y",
        "%b %d, %Y", "%b %d %Y", "%B %d, %Y",
        "%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%d-%m-%Y")
        except Exception:
            continue

    # Последний шанс — mm/dd/yyyy
    try:
        dt = datetime.strptime(s, "%m/%d/%Y")
        return dt.strftime("%d-%m-%Y")
    except Exception:
        pass

    return ""


def _split_line(line: str, delimiter: str = ",") -> List[str]:
    """
    Корректный CSV-разбор одной строки с кавычками
    (в т.ч. экранированные "" внутри поля).
    Использует csv.reader для надёжности.
    """
    if line is None:
        return []
    line = line.rstrip("\r\n")
    if not line:
        return []
    try:
        reader = csv.reader(
            [line],
            delimiter=delimiter,
            quotechar='"',
            doublequote=True,
            skipinitialspace=False,
        )
        for row in reader:
            return list(row)
    except Exception:
        pass
    return line.split(delimiter)


def _is_real_xls(content: bytes) -> bool:
    """Настоящий BIFF (OLE2): D0 CF 11 E0 A1 B1 1A E1."""
    return content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _is_real_xlsx(content: bytes) -> bool:
    """ZIP (PK\\x03\\x04) — .xlsx/.xlsm или любой zip-контейнер."""
    return content[:4] == b"PK\x03\x04"


def read_xlsx(content: bytes, sheet_name: Optional[str] = None) -> Optional[pd.DataFrame]:
    """
    Чтение .xlsx/.xls с каскадом:
      - .xlsx (zip) -> openpyxl через pandas
      - .xls BIFF  -> xlrd
      - .xls HTML  -> pd.read_html
      - прочее     -> pd.read_html fallback
    Возвращает DataFrame или None.
    """
    # xlsx (PK zip)
    if _is_real_xlsx(content):
        try:
            return pd.read_excel(
                io.BytesIO(content),
                sheet_name=sheet_name or 0,
                engine="openpyxl",
                header=None,
            )
        except Exception:
            try:
                return pd.read_excel(
                    io.BytesIO(content),
                    sheet_name=sheet_name or 0,
                    header=None,
                )
            except Exception:
                pass

    # настоящий BIFF .xls
    if _is_real_xls(content):
        # xlrd
        if xlrd is not None:
            try:
                book = xlrd.open_workbook(file_contents=content)
                sh = book.sheet_by_index(0)
                rows = []
                for r in range(sh.nrows):
                    rows.append([sh.cell_value(r, c) for c in range(sh.ncols)])
                return pd.DataFrame(rows)
            except Exception:
                pass
        # openpyxl иногда умеет .xls (редко)
        if openpyxl is not None:
            try:
                return pd.read_excel(
                    io.BytesIO(content),
                    sheet_name=sheet_name or 0,
                    engine="openpyxl",
                    header=None,
                )
            except Exception:
                pass
        # pd.read_html — на случай HTML внутри .xls
        try:
            tables = pd.read_html(io.BytesIO(content))
            if tables:
                return tables[0]
        except Exception:
            pass
        return None

    # Неизвестный формат — пробуем всё подряд
    try:
        return pd.read_excel(
            io.BytesIO(content),
            sheet_name=sheet_name or 0,
            header=None,
        )
    except Exception:
        pass
    try:
        tables = pd.read_html(io.BytesIO(content))
        if tables:
            return tables[0]
    except Exception:
        pass
    return None


def docx_all_text(content: bytes) -> str:
    """Весь текст .docx как единая строка (абзацы + таблицы)."""
    if Document is None:
        return ""
    try:
        d = Document(io.BytesIO(content))
    except Exception:
        return ""
    parts: List[str] = []
    for p in d.paragraphs:
        parts.append(p.text)
    for tbl in d.tables:
        for row in tbl.rows:
            cells = [c.text for c in row.cells]
            parts.append("\t".join(cells))
    return "\n".join(parts)


def docx_dump(content: bytes) -> str:
    """
    Дамп .docx: таблицы (первые 30 строк каждой) + первые абзацы.
    Используется в отладочном режиме.
    """
    if Document is None:
        return "(python-docx недоступен)"
    try:
        d = Document(io.BytesIO(content))
    except Exception as e:
        return f"(ошибка открытия docx: {e})"
    out: List[str] = []
    out.append(f"Абзацев: {len(d.paragraphs)}, таблиц: {len(d.tables)}")
    out.append("=== TABLES ===")
    for ti, tbl in enumerate(d.tables):
        out.append(f"--- table[{ti}] rows={len(tbl.rows)} cols={len(tbl.columns)} ---")
        for ri, row in enumerate(tbl.rows[:30]):
            cells = [safe_str(c.text) for c in row.cells]
            out.append(f"  [{ri}] " + " | ".join(cells))
    out.append("=== PARAGRAPHS (первые 60 непустых) ===")
    n = 0
    for p in d.paragraphs:
        t = safe_str(p.text)
        if t:
            out.append(t)
            n += 1
            if n >= 60:
                break
    return "\n".join(out)


def pdf_all_text(content: bytes) -> str:
    """Весь текст .pdf."""
    if pdfplumber is None:
        return ""
    parts: List[str] = []
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                parts.append(t)
    except Exception:
        return ""
    return "\n".join(parts)


def pdf_all_tables(content: bytes) -> List[List[List[str]]]:
    """Все таблицы .pdf — список таблиц, каждая таблица — список строк."""
    if pdfplumber is None:
        return []
    out: List[List[List[str]]] = []
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                for tbl in (page.extract_tables() or []):
                    out.append([[safe_str(c) for c in row] for row in tbl])
    except Exception:
        return []
    return out


# =============================================================================
#                          УТИЛИТЫ ДЛЯ ПОИСКА ЗАГОЛОВКА
# =============================================================================

def _find_header_row(
    rows: List[List[Any]],
    markers: List[str],
    max_scan: int = 60,
    min_hits: int = 2,
) -> int:
    """
    Ищем строку-заголовок по маркерам.
    Возвращает индекс строки или -1.
    """
    norm_markers = [m.lower() for m in markers]
    for i, row in enumerate(rows[:max_scan]):
        cells = [safe_str(c).lower() for c in row]
        hits = 0
        for m in norm_markers:
            for c in cells:
                if m in c:
                    hits += 1
                    break
        if hits >= min_hits:
            return i
    return -1


def _row_to_dict(header: List[str], row: List[Any]) -> Dict[str, str]:
    """Собираем словарь по индексам заголовка (лишние ячейки игнорируем)."""
    d: Dict[str, str] = {}
    for i, h in enumerate(header):
        if i < len(row):
            d[safe_str(h)] = safe_str(row[i])
    return d


def _pick(d: Dict[str, str], *names: str) -> str:
    """Найти значение по одному из имён (без учёта регистра, подстрокой)."""
    for want in names:
        wl = want.lower()
        for k, v in d.items():
            if wl in k.lower():
                return v
    return ""


def _is_service_row(joined_lower: str) -> bool:
    """Служебная строка (остаток, итоги)? — не транзакция."""
    return any(w in joined_lower for w in SERVICE_WORDS)


def _longest_text(parts: List[str], min_len: int = 3) -> str:
    """Самая длинная текстовая ячейка (не число, не дата)."""
    best = ""
    for p in parts:
        sp = safe_str(p)
        if len(sp) < min_len:
            continue
        if re.fullmatch(r"[\d\s.,\-+()]+", sp):
            continue
        if len(sp) > len(best):
            best = sp
    return best


# =============================================================================
#                              ROUTER
# =============================================================================

def clean_account_name(filename: str) -> str:
    """Очищаем имя файла до «наименования счёта»."""
    name = os.path.basename(filename)
    name = re.sub(r"\.[A-Za-z0-9]+$", "", name)
    # Убираем даты в разных видах
    name = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", name)
    name = re.sub(r"\b\d{2}[.\-/]\d{2}[.\-/]\d{2,4}\b", "", name)
    name = re.sub(r"\b\d{8}\b", "", name)
    name = re.sub(r"\b\d{6}\b", "", name)
    # Годовые периоды и тех. мусор
    name = re.sub(r"\b20\d{2}\b", "", name)
    name = re.sub(r"[_\-]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip(" -_")
    # Если осталось пусто — вернём исходное
    return name or os.path.basename(filename)


class _TinkoffMarker:
    """Маркер для роутера Tinkoff — реальный парсер выбирается по расширению."""
    pass


_TINKOFF_TABULAR_MARKER = _TinkoffMarker()


def get_parser_by_ext(account_name: str, ext: str) -> Optional[Callable]:
    """Определяем парсер по имени счёта и расширению."""
    ext = ext.lower().lstrip(".")
    name_l = account_name.lower()

    # --- DOCX ---
    if ext == "docx":
        if "tinkoff" in name_l:
            return parse_tinkoff_docx
        if "regina" in name_l or "alfa" in name_l or "альфа" in name_l:
            return parse_regina_alfa_docx
        if "jenhor" in name_l or "unelma" in name_l:
            return parse_jenhor_unelma_docx
        if "n26" in name_l:
            return parse_n26_docx
        if "kapital" in name_l or "saida" in name_l:
            return parse_kapital_saida_docx
        return parse_generic_docx

    # --- PDF ---
    if ext == "pdf":
        if "regina" in name_l or "alfa" in name_l:
            return parse_regina_alfa_pdf
        return parse_generic_pdf

    # --- Табличные ---
    if ext in ("xlsx", "xls", "csv"):
        return _route_tabular(account_name)

    return None


def _route_tabular(account_name: str) -> Callable:
    """
    Маршрутизация .xlsx / .xls / .csv по имени счёта.
    Возвращает parser(file_content, account_name) -> List[Dict]
    либо маркер _TINKOFF_TABULAR_MARKER (тогда реальный парсер
    выбирается по расширению).

    ВАЖНО (FIX-11): Revolut проверяется ДО Industra —
    иначе AN14_*_Revolut.csv уходит в industra_an14.
    """
    name_l = account_name.lower()

    # [FIX-11] Revolut ДО Industra, потому что 'an14' в имени
    if "revolut" in name_l:
        return parse_revolut_an14

    if "tinkoff" in name_l:
        # [FIX-8] Tinkoff xlsx/csv — отдельные парсеры (не docx)
        return _TINKOFF_TABULAR_MARKER  # type: ignore

    if "industra" in name_l:
        return parse_industra_generic

    if "csob" in name_l:
        return parse_csob_generic

    # UniCredit: разные варианты имени
    if "unicredit" in name_l or "uni credit" in name_l:
        return parse_unicredit_generic
    if re.search(r"\buc\b", name_l) or name_l.endswith("_uc") or " uc " in (" " + name_l + " "):
        return parse_unicredit_generic

    if "paysera" in name_l:
        return parse_paysera_generic

    if "bluor" in name_l or "blu or" in name_l:
        if "bluor_2" in name_l or "bluor 2" in name_l:
            return parse_bsr_bluor_2
        if "bluor_3" in name_l or "bluor 3" in name_l:
            return parse_bsr_bluor_3
        if "kl59" in name_l:
            return parse_kl59_bluor
        return parse_bsr_bluor_2

    if "mkb" in name_l or "budapest" in name_l:
        return _parse_mkb_any

    if "pasha" in name_l:
        return parse_pasha_bank_xlsx

    if "mashreq" in name_l:
        return parse_mashreq

    if "wio" in name_l:
        return parse_wio_business

    if "wise" in name_l:
        return parse_saida_wise_xlsx

    if "fio" in name_l or "stalkin" in name_l:
        return parse_stalkin_ml2_fio

    if "rak" in name_l:
        return parse_rak_bank_xlsx

    return parse_generic_tabular


def _resolve_tinkoff(ext: str) -> Callable:
    """Для Tinkoff: .csv идёт в parse_tinkoff_csv, всё остальное — в xlsx."""
    if ext.lower().lstrip(".") == "csv":
        return parse_tinkoff_csv
    return parse_tinkoff_xlsx


# =============================================================================
#                              ПАРСЕРЫ (табличные)
# =============================================================================

# --- CSOB -------------------------------------------------------------------

def parse_csob_generic(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """
    CSOB CSV-выгрузка (cp1250/utf-8, ';' или ',').

    Пример строки:
      "0","1.8.2026","","Nákup","","-1 234,56","CZK",""

    В разных выгрузках колонки слегка плавают:
      - дата может быть parts[1] или parts[4]
      - сумма — parts[5] или parts[6]

    [FIX-4] Принимаем строки с len(parts) >= 4 (было строже — теряли
            короткие строки с len==6).
    [FIX-5] Автодетект сдвига индексов: дата ищется по содержимому,
            сумма — ближайшее числовое после даты.
    """
    text = read_text_with_encoding(file_content)
    if not text:
        return []

    # Определяем разделитель
    delim = ";"
    sample = "\n".join(text.splitlines()[:5])
    if sample.count(",") > sample.count(";"):
        delim = ","

    txns: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.rstrip("\r\n")
        if not line.strip():
            continue
        parts = _split_line(line, delimiter=delim)
        if len(parts) < 4:
            continue

        # Служебные строки пропускаем
        joined = " ".join(safe_str(p).lower() for p in parts)
        if _is_service_row(joined):
            continue

        # Ищем дату в первых 10 полях (автосдвиг)
        date_val = ""
        date_idx = -1
        for i in range(min(len(parts), 10)):
            d = parse_date(parts[i])
            if d:
                date_val = d
                date_idx = i
                break
        if not date_val:
            continue

        # Сумма — ищем float-подобное поле после date_idx
        amount_val: Optional[float] = None
        for j in range(date_idx + 1, min(len(parts), date_idx + 8)):
            s = safe_str(parts[j])
            if not s:
                continue
            # Пропускаем чистые валютные коды
            if re.fullmatch(r"[A-Z]{3}", s):
                continue
            if re.search(r"\d", s):
                a = parse_amount(s)
                # Сумма обычно самая правая «числовая» — не прерываемся,
                # запоминаем последнюю подходящую
                if (
                    a != 0.0
                    or re.search(r"[.,]\d{2}\b", s)
                    or re.fullmatch(r"-?\d+", s.replace(" ", ""))
                ):
                    amount_val = a
        if amount_val is None:
            continue

        # Описание — самая длинная текстовая ячейка
        desc = _longest_text(parts)
        counterparty = desc.split(",")[0].strip() if desc else ""

        txns.append({
            "Дата": date_val,
            "Сумма": amount_val,
            "Контрагент": counterparty,
            "Наименование счета": account_name,
            "Описание": desc,
        })
    return txns


# --- UniCredit --------------------------------------------------------------

def parse_unicredit_generic(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """
    UniCredit CSV (CZ/EN). Заголовок содержит Datum/Částka/Zpráva
    или Date/Amount/Description.

    [FIX-7] Поддержка разделителя ',' и ';' внутри значений
            (используем csv.reader через _split_line),
            и терпимый поиск колонок по частичному совпадению.
    """
    text = read_text_with_encoding(file_content)
    if not text:
        return []

    lines = text.splitlines()
    if not lines:
        return []

    # Определяем разделитель
    delim = ";"
    sample = "\n".join(lines[:5])
    if sample.count(",") > sample.count(";"):
        delim = ","

    # Ищем строку-заголовок
    header_idx = -1
    header: List[str] = []
    markers = [
        "datum", "date", "дата",
        "částka", "castka", "amount", "сумма", "objem",
        "zpráva", "zprava", "popis", "description", "описание",
        "protiúčet", "protiucet", "counterparty",
        "kredit", "credit", "приход",
        "debet", "debit", "расход",
    ]
    for i, line in enumerate(lines[:60]):
        parts = _split_line(line, delimiter=delim)
        cells = [safe_str(c).lower() for c in parts]
        hits = sum(1 for m in markers if any(m in c for c in cells))
        if hits >= 2:
            header_idx = i
            header = parts
            break

    if header_idx < 0:
        return []

    # Индексы колонок
    idx_date = -1
    idx_amount = -1
    idx_desc = -1
    idx_counter = -1
    idx_credit = -1
    idx_debit = -1
    for i, h in enumerate(header):
        hl = safe_str(h).lower()
        if idx_date == -1 and any(m in hl for m in ("datum", "date", "дата")):
            idx_date = i
        if idx_amount == -1 and any(
            m in hl for m in ("částka", "castka", "amount", "сумма", "objem")
        ):
            idx_amount = i
        if idx_credit == -1 and any(m in hl for m in ("kredit", "credit", "приход")):
            idx_credit = i
        if idx_debit == -1 and any(m in hl for m in ("debet", "debit", "расход")):
            idx_debit = i
        if idx_desc == -1 and any(
            m in hl
            for m in ("zpráva", "zprava", "popis", "description", "описание", "pozn")
        ):
            idx_desc = i
        if idx_counter == -1 and any(
            m in hl
            for m in ("protiúčet", "protiucet", "counterparty", "контрагент", "název")
        ):
            idx_counter = i

    txns: List[Dict[str, Any]] = []
    for line in lines[header_idx + 1:]:
        if not line.strip():
            continue
        parts = _split_line(line, delimiter=delim)
        if idx_date < 0 or idx_date >= len(parts):
            continue
        date_val = parse_date(parts[idx_date])
        if not date_val:
            continue

        amount_val = 0.0
        if idx_amount >= 0 and idx_amount < len(parts):
            amount_val = parse_amount(parts[idx_amount])
        if amount_val == 0.0 and (idx_credit >= 0 or idx_debit >= 0):
            c = parse_amount(parts[idx_credit]) if 0 <= idx_credit < len(parts) else 0.0
            d = parse_amount(parts[idx_debit]) if 0 <= idx_debit < len(parts) else 0.0
            if c or d:
                amount_val = c - abs(d)

        desc = safe_str(parts[idx_desc]) if 0 <= idx_desc < len(parts) else ""
        counter = safe_str(parts[idx_counter]) if 0 <= idx_counter < len(parts) else ""
        if not counter and desc:
            counter = desc.split(",")[0].strip()

        if amount_val == 0.0 and not desc:
            continue

        txns.append({
            "Дата": date_val,
            "Сумма": amount_val,
            "Контрагент": counter,
            "Наименование счета": account_name,
            "Описание": desc,
        })
    return txns


# --- Paysera ----------------------------------------------------------------

def parse_paysera_generic(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """
    Paysera .xlsx: заголовок ищем в первых 60 строках.
    [FIX-16] англ. заголовки: Date, Amount, Details, Beneficiary.
    """
    df = read_xlsx(file_content)
    if df is None or df.empty:
        return []

    rows = df.values.tolist()
    header_idx = _find_header_row(
        rows,
        markers=["date", "amount", "details", "beneficiary",
                 "data", "suma", "mokėjimo", "дата", "сумма"],
        max_scan=60, min_hits=2,
    )
    if header_idx < 0:
        return []

    header = [safe_str(c) for c in rows[header_idx]]
    txns: List[Dict[str, Any]] = []
    for row in rows[header_idx + 1:]:
        d = _row_to_dict(header, row)
        date_val = parse_date(_pick(d, "date", "data", "дата"))
        if not date_val:
            continue
        amount_val = parse_amount(_pick(d, "amount", "suma", "сумма", "credit"))
        if amount_val == 0.0:
            cr = parse_amount(_pick(d, "credit", "приход"))
            db = parse_amount(_pick(d, "debit", "расход"))
            if cr or db:
                amount_val = cr - abs(db)
        desc = _pick(d, "details", "description", "описание", "purpose", "paskirtis")
        counter = _pick(d, "beneficiary", "counterparty", "gavėjas", "контрагент") \
            or (desc.split(",")[0] if desc else "")
        if not desc and amount_val == 0.0:
            continue
        txns.append({
            "Дата": date_val,
            "Сумма": amount_val,
            "Контрагент": counter,
            "Наименование счета": account_name,
            "Описание": desc,
        })
    return txns


# --- Revolut ----------------------------------------------------------------

def parse_revolut_an14(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """Revolut CSV (EN/CZ). Заголовок: Date, Description, Amount, ..."""
    text = read_text_with_encoding(file_content)
    if not text:
        return []
    lines = text.splitlines()
    if not lines:
        return []

    delim = ","
    sample = "\n".join(lines[:3])
    if sample.count(";") > sample.count(","):
        delim = ";"

    header_idx = -1
    header: List[str] = []
    for i, line in enumerate(lines[:30]):
        parts = _split_line(line, delimiter=delim)
        cells = [safe_str(c).lower() for c in parts]
        hits = sum(
            1 for m in ("date", "amount", "description", "type", "datum")
            if any(m in c for c in cells)
        )
        if hits >= 2:
            header_idx = i
            header = parts
            break
    if header_idx < 0:
        return []

    idx_date = idx_amt = idx_desc = idx_type = -1
    for i, h in enumerate(header):
        hl = safe_str(h).lower()
        if idx_date < 0 and "date" in hl:
            idx_date = i
        if idx_amt < 0 and "amount" in hl:
            idx_amt = i
        if idx_desc < 0 and "description" in hl:
            idx_desc = i
        if idx_type < 0 and "type" in hl:
            idx_type = i

    txns: List[Dict[str, Any]] = []
    for line in lines[header_idx + 1:]:
        if not line.strip():
            continue
        parts = _split_line(line, delimiter=delim)
        if idx_date < 0 or idx_date >= len(parts):
            continue
        date_val = parse_date(parts[idx_date])
        if not date_val:
            continue
        amount_val = parse_amount(parts[idx_amt]) if 0 <= idx_amt < len(parts) else 0.0
        desc = safe_str(parts[idx_desc]) if 0 <= idx_desc < len(parts) else ""
        ttype = safe_str(parts[idx_type]) if 0 <= idx_type < len(parts) else ""
        full_desc = (ttype + " " + desc).strip()
        counter = desc.split(",")[0].strip() if desc else ttype
        txns.append({
            "Дата": date_val,
            "Сумма": amount_val,
            "Контрагент": counter,
            "Наименование счета": account_name,
            "Описание": full_desc,
        })
    return txns


# --- Industra ---------------------------------------------------------------

def parse_industra_generic(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """
    Industra Bank .xls/.xlsx/.csv.

    [FIX-9] Терпимый поиск колонок 'Дата транзакции' + 'Дебет' + 'Кредит',
            авто-сдвиг индексов (ищем date по содержимому, а не по позиции).
    """
    txns: List[Dict[str, Any]] = []

    # Сначала пробуем как таблицу
    df = read_xlsx(file_content)
    if df is not None and not df.empty:
        rows = df.values.tolist()
        header_idx = _find_header_row(
            rows,
            markers=["дата", "date", "дебет", "кредит", "debit", "credit",
                     "сумма", "amount", "описание", "transaction"],
            max_scan=40, min_hits=2,
        )
        if header_idx >= 0:
            header = [safe_str(c) for c in rows[header_idx]]
            for row in rows[header_idx + 1:]:
                d = _row_to_dict(header, row)
                date_val = parse_date(_pick(d, "дата транзакции", "дата", "date",
                                            "transaction date"))
                if not date_val:
                    continue
                cr = parse_amount(_pick(d, "кредит", "credit", "приход"))
                db = parse_amount(_pick(d, "дебет", "debit", "расход"))
                amt = parse_amount(_pick(d, "сумма", "amount"))
                if amt == 0.0 and (cr or db):
                    amt = cr - abs(db)
                desc = _pick(d, "описание", "description", "назначение",
                             "details", "purpose")
                counter = _pick(d, "контрагент", "counterparty",
                                "получатель", "плательщик") \
                    or (desc.split(",")[0] if desc else "")
                if not desc and amt == 0.0:
                    continue
                txns.append({
                    "Дата": date_val,
                    "Сумма": amt,
                    "Контрагент": counter,
                    "Наименование счета": account_name,
                    "Описание": desc,
                })
            if txns:
                return txns

    # CSV-путь fallback
    text = read_text_with_encoding(file_content)
    if not text:
        return txns
    lines = text.splitlines()
    if not lines:
        return txns

    delim = ","
    sample = "\n".join(lines[:5])
    if sample.count(";") > sample.count(","):
        delim = ";"

    header_idx = -1
    header: List[str] = []
    for i, line in enumerate(lines[:60]):
        parts = _split_line(line, delimiter=delim)
        cells = [safe_str(c).lower() for c in parts]
        hits = sum(
            1 for m in ("дата", "date", "дебет", "кредит", "сумма",
                        "amount", "описание")
            if any(m in c for c in cells)
        )
        if hits >= 2:
            header_idx = i
            header = parts
            break
    if header_idx < 0:
        return txns

    idx_date = idx_amt = idx_cr = idx_db = idx_desc = idx_counter = -1
    for i, h in enumerate(header):
        hl = safe_str(h).lower()
        if idx_date < 0 and "дата" in hl:
            idx_date = i
        if idx_amt < 0 and ("сумма" in hl or "amount" in hl):
            idx_amt = i
        if idx_cr < 0 and "кредит" in hl:
            idx_cr = i
        if idx_db < 0 and "дебет" in hl:
            idx_db = i
        if idx_desc < 0 and ("описание" in hl or "назначение" in hl
                             or "details" in hl):
            idx_desc = i
        if idx_counter < 0 and ("контрагент" in hl or "counterparty" in hl):
            idx_counter = i

    for line in lines[header_idx + 1:]:
        if not line.strip():
            continue
        parts = _split_line(line, delimiter=delim)
        if idx_date < 0 or idx_date >= len(parts):
            continue
        date_val = parse_date(parts[idx_date])
        if not date_val:
            continue
        amt = parse_amount(parts[idx_amt]) if 0 <= idx_amt < len(parts) else 0.0
        if amt == 0.0 and (idx_cr >= 0 or idx_db >= 0):
            cr = parse_amount(parts[idx_cr]) if 0 <= idx_cr < len(parts) else 0.0
            db = parse_amount(parts[idx_db]) if 0 <= idx_db < len(parts) else 0.0
            amt = cr - abs(db)
        desc = safe_str(parts[idx_desc]) if 0 <= idx_desc < len(parts) else ""
        counter = safe_str(parts[idx_counter]) if 0 <= idx_counter < len(parts) else ""
        if not counter and desc:
            counter = desc.split(",")[0].strip()
        if amt == 0.0 and not desc:
            continue
        txns.append({
            "Дата": date_val,
            "Сумма": amt,
            "Контрагент": counter,
            "Наименование счета": account_name,
            "Описание": desc,
        })
    return txns


# --- MKB --------------------------------------------------------------------

def _parse_mkb_any(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """
    MKB (HU) — .csv или .xls/.xlsx.

    [FIX-1] Каскад: xlrd → openpyxl → pd.read_html → CSV-путь.
            Заголовок обычно в первых 5–10 строках, ищем Sorszám / Értéknap
            (с диакритикой или без).
            Файл Budapest HUF-MKB_*.xls — настоящий BIFF (D0 CF 11 E0),
            xlrd его читает, но DataFrame может не содержать нужных колонок
            сразу — поэтому перебираем маркеры максимально широко.
    """
    txns: List[Dict[str, Any]] = []

    # 1) Табличный путь
    df = read_xlsx(file_content)
    if df is not None and not df.empty:
        rows = df.values.tolist()
        header_idx = _find_header_row(
            rows,
            markers=[
                "sorszám", "sorszam", "értéknap", "erteknap",
                "összeg", "osszeg", "jogosult",
                "közlemény", "kozlemeny",
                "terhelés", "terheles",
                "jóváírás", "jovairas", "egyenleg",
            ],
            max_scan=15, min_hits=2,
        )
        if header_idx >= 0:
            header = [safe_str(c) for c in rows[header_idx]]
            for row in rows[header_idx + 1:]:
                d = _row_to_dict(header, row)
                date_val = parse_date(
                    _pick(d, "értéknap", "erteknap", "dátum", "datum", "date")
                )
                if not date_val:
                    continue
                amount_val = parse_amount(
                    _pick(d, "összeg", "osszeg", "amount",
                          "terhelés", "jóváírás")
                )
                if amount_val == 0.0:
                    terh = parse_amount(_pick(d, "terhelés", "terheles", "debit"))
                    jov = parse_amount(_pick(d, "jóváírás", "jovairas", "credit"))
                    if terh or jov:
                        amount_val = jov - abs(terh)
                desc = _pick(d, "közlemény", "kozlemeny", "jogosult",
                             "description", "megjegyzés", "описание")
                counter = _pick(d, "jogosult", "partner", "counterparty") \
                    or (desc.split(",")[0] if desc else "")
                if not desc and amount_val == 0.0:
                    continue
                txns.append({
                    "Дата": date_val,
                    "Сумма": amount_val,
                    "Контрагент": counter,
                    "Наименование счета": account_name,
                    "Описание": desc,
                })
            if txns:
                return txns

    # 2) CSV-путь (MKB может отдавать CSV с ';')
    text = read_text_with_encoding(file_content)
    if text:
        lines = text.splitlines()
        delim = ";"
        sample = "\n".join(lines[:5])
        if sample.count(",") > sample.count(";"):
            delim = ","
        header_idx = -1
        header: List[str] = []
        for i, line in enumerate(lines[:20]):
            parts = _split_line(line, delimiter=delim)
            cells = [safe_str(c).lower() for c in parts]
            hits = sum(
                1 for m in ("sorszám", "sorszam", "értéknap", "erteknap",
                            "összeg", "osszeg", "jogosult")
                if any(m in c for c in cells)
            )
            if hits >= 2:
                header_idx = i
                header = parts
                break
        if header_idx >= 0:
            idx_date = idx_amt = idx_desc = idx_counter = -1
            for i, h in enumerate(header):
                hl = safe_str(h).lower()
                if idx_date < 0 and (
                    "értéknap" in hl or "erteknap" in hl
                    or "dátum" in hl or "datum" in hl
                ):
                    idx_date = i
                if idx_amt < 0 and ("összeg" in hl or "osszeg" in hl):
                    idx_amt = i
                if idx_desc < 0 and ("közlemény" in hl or "kozlemeny" in hl):
                    idx_desc = i
                if idx_counter < 0 and ("jogosult" in hl or "partner" in hl):
                    idx_counter = i
            for line in lines[header_idx + 1:]:
                if not line.strip():
                    continue
                parts = _split_line(line, delimiter=delim)
                if idx_date < 0 or idx_date >= len(parts):
                    continue
                date_val = parse_date(parts[idx_date])
                if not date_val:
                    continue
                amount_val = parse_amount(parts[idx_amt]) if 0 <= idx_amt < len(parts) else 0.0
                desc = safe_str(parts[idx_desc]) if 0 <= idx_desc < len(parts) else ""
                counter = safe_str(parts[idx_counter]) if 0 <= idx_counter < len(parts) else ""
                if not counter and desc:
                    counter = desc.split(",")[0].strip()
                if amount_val == 0.0 and not desc:
                    continue
                txns.append({
                    "Дата": date_val,
                    "Сумма": amount_val,
                    "Контрагент": counter,
                    "Наименование счета": account_name,
                    "Описание": desc,
                })
    return txns


# --- Pasha Bank -------------------------------------------------------------

def parse_pasha_bank_xlsx(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """Pasha Bank .xlsx — заголовок в первых 10–20 строках."""
    df = read_xlsx(file_content)
    if df is None or df.empty:
        return []
    rows = df.values.tolist()
    header_idx = _find_header_row(
        rows,
        markers=["date", "дата", "amount", "сумма", "description", "описание",
                 "debit", "credit", "дебет", "кредит", "balance", "məbləğ"],
        max_scan=15, min_hits=2,
    )
    if header_idx < 0:
        return []
    header = [safe_str(c) for c in rows[header_idx]]
    txns: List[Dict[str, Any]] = []
    for row in rows[header_idx + 1:]:
        d = _row_to_dict(header, row)
        date_val = parse_date(_pick(d, "date", "дата", "tarix"))
        if not date_val:
            continue
        amt = parse_amount(_pick(d, "amount", "сумма", "məbləğ", "məbləg"))
        if amt == 0.0:
            cr = parse_amount(_pick(d, "credit", "kredit", "приход",
                                    "mədaxil", "medaxil"))
            db = parse_amount(_pick(d, "debit", "дебет", "расход",
                                    "məxaric", "mexaric"))
            if cr or db:
                amt = cr - abs(db)
        desc = _pick(d, "description", "описание", "təyinat",
                     "назначение", "təyinatı")
        counter = _pick(d, "counterparty", "контрагент",
                        "beneficiary", "получатель") \
            or (desc.split(",")[0] if desc else "")
        if not desc and amt == 0.0:
            continue
        txns.append({
            "Дата": date_val,
            "Сумма": amt,
            "Контрагент": counter,
            "Наименование счета": account_name,
            "Описание": desc,
        })
    return txns


# --- Mashreq ----------------------------------------------------------------

def parse_mashreq(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """Mashreq .xlsx (AED). Заголовки EN."""
    df = read_xlsx(file_content)
    if df is None or df.empty:
        return []
    rows = df.values.tolist()
    header_idx = _find_header_row(
        rows,
        markers=["date", "description", "debit", "credit",
                 "balance", "amount", "reference"],
        max_scan=20, min_hits=2,
    )
    if header_idx < 0:
        return []
    header = [safe_str(c) for c in rows[header_idx]]
    txns: List[Dict[str, Any]] = []
    for row in rows[header_idx + 1:]:
        d = _row_to_dict(header, row)
        date_val = parse_date(
            _pick(d, "date", "дата", "value date", "transaction date")
        )
        if not date_val:
            continue
        amt = parse_amount(_pick(d, "amount", "сумма"))
        if amt == 0.0:
            cr = parse_amount(_pick(d, "credit", "credit amount"))
            db = parse_amount(_pick(d, "debit", "debit amount"))
            if cr or db:
                amt = cr - abs(db)
        desc = _pick(d, "description", "narrative", "details", "описание")
        counter = _pick(d, "counterparty", "beneficiary", "reference") \
            or (desc.split(",")[0] if desc else "")
        if not desc and amt == 0.0:
            continue
        txns.append({
            "Дата": date_val,
            "Сумма": amt,
            "Контрагент": counter,
            "Наименование счета": account_name,
            "Описание": desc,
        })
    return txns


# --- WIO --------------------------------------------------------------------

def parse_wio_business(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """
    WIO Business Bank .csv.

    [FIX-8] Заголовки: 'Account name' + 'Transaction type';
            дата может быть dd/mm/yyyy; суммы с валютным суффиксом.
    """
    text = read_text_with_encoding(file_content)
    if not text:
        return []
    lines = text.splitlines()
    if not lines:
        return []

    delim = ","
    sample = "\n".join(lines[:3])
    if sample.count(";") > sample.count(","):
        delim = ";"

    header_idx = -1
    header: List[str] = []
    for i, line in enumerate(lines[:30]):
        parts = _split_line(line, delimiter=delim)
        cells = [safe_str(c).lower() for c in parts]
        hits = sum(
            1 for m in ("account name", "transaction type", "date",
                        "amount", "transaction")
            if any(m in c for c in cells)
        )
        if hits >= 2:
            header_idx = i
            header = parts
            break
    if header_idx < 0:
        return []

    idx_date = idx_amt = idx_desc = idx_type = idx_counter = -1
    for i, h in enumerate(header):
        hl = safe_str(h).lower()
        if idx_date < 0 and "date" in hl:
            idx_date = i
        if idx_amt < 0 and ("amount" in hl or "сумма" in hl):
            idx_amt = i
        if idx_desc < 0 and (
            "description" in hl or "details" in hl
            or "reference" in hl or "описание" in hl
        ):
            idx_desc = i
        if idx_type < 0 and "transaction type" in hl:
            idx_type = i
        if idx_counter < 0 and (
            "counterparty" in hl or "beneficiary" in hl or "name" in hl
        ):
            idx_counter = i

    txns: List[Dict[str, Any]] = []
    for line in lines[header_idx + 1:]:
        if not line.strip():
            continue
        parts = _split_line(line, delimiter=delim)
        if idx_date < 0 or idx_date >= len(parts):
            continue
        date_val = parse_date(parts[idx_date])
        if not date_val:
            continue
        amt = parse_amount(parts[idx_amt]) if 0 <= idx_amt < len(parts) else 0.0
        desc = safe_str(parts[idx_desc]) if 0 <= idx_desc < len(parts) else ""
        ttype = safe_str(parts[idx_type]) if 0 <= idx_type < len(parts) else ""
        counter = safe_str(parts[idx_counter]) if 0 <= idx_counter < len(parts) else ""
        if not counter and desc:
            counter = desc.split(",")[0].strip()
        full_desc = (ttype + " " + desc).strip()
        if amt == 0.0 and not full_desc:
            continue
        txns.append({
            "Дата": date_val,
            "Сумма": amt,
            "Контрагент": counter,
            "Наименование счета": account_name,
            "Описание": full_desc,
        })
    return txns


# --- Wise -------------------------------------------------------------------

def parse_saida_wise_xlsx(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """
    Wise .xlsx.

    [FIX-6] Терпимо к заголовкам:
            'Дата и время' vs 'Дата',
            'Сумма' vs 'Amount',
            'Тип транзакции' vs 'Type',
            'Описание' vs 'Description'.
    """
    df = read_xlsx(file_content)
    if df is None or df.empty:
        return []
    rows = df.values.tolist()
    header_idx = _find_header_row(
        rows,
        markers=["дата и время", "дата", "date", "сумма", "amount",
                 "тип транзакции", "type", "описание", "description"],
        max_scan=20, min_hits=2,
    )
    if header_idx < 0:
        return []
    header = [safe_str(c) for c in rows[header_idx]]

    idx_date = idx_amt = idx_desc = idx_type = idx_counter = -1
    for i, h in enumerate(header):
        hl = safe_str(h).lower()
        if idx_date < 0 and ("дата" in hl or "date" in hl):
            idx_date = i
        if idx_amt < 0 and ("сумма" in hl or "amount" in hl):
            idx_amt = i
        if idx_desc < 0 and (
            "описание" in hl or "description" in hl or "детали" in hl
        ):
            idx_desc = i
        if idx_type < 0 and ("тип транзакции" in hl or "type" in hl):
            idx_type = i
        if idx_counter < 0 and (
            "контрагент" in hl or "counterparty" in hl or "name" in hl
        ):
            idx_counter = i

    txns: List[Dict[str, Any]] = []
    for row in rows[header_idx + 1:]:
        if not row:
            continue
        date_val = parse_date(row[idx_date]) if 0 <= idx_date < len(row) else ""
        if not date_val:
            continue
        amt = parse_amount(row[idx_amt]) if 0 <= idx_amt < len(row) else 0.0
        desc = safe_str(row[idx_desc]) if 0 <= idx_desc < len(row) else ""
        ttype = safe_str(row[idx_type]) if 0 <= idx_type < len(row) else ""
        counter = safe_str(row[idx_counter]) if 0 <= idx_counter < len(row) else ""
        if not counter and desc:
            counter = desc.split(",")[0].strip()
        full_desc = (ttype + " " + desc).strip()
        if amt == 0.0 and not full_desc:
            continue
        txns.append({
            "Дата": date_val,
            "Сумма": amt,
            "Контрагент": counter,
            "Наименование счета": account_name,
            "Описание": full_desc,
        })
    return txns


# --- FIO / Stalkin ----------------------------------------------------------

def parse_stalkin_ml2_fio(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """
    FIO Banka CSV / Stalkin.

    [FIX-18] Ищем заголовок по Datum/Objem/Částka,
             индексы колонок определяем по содержимому заголовка.
    """
    text = read_text_with_encoding(file_content)
    if not text:
        return []
    lines = text.splitlines()
    if not lines:
        return []

    delim = ";"
    sample = "\n".join(lines[:5])
    if sample.count(",") > sample.count(";"):
        delim = ","

    header_idx = -1
    header: List[str] = []
    for i, line in enumerate(lines[:30]):
        parts = _split_line(line, delimiter=delim)
        cells = [safe_str(c).lower() for c in parts]
        hits = sum(
            1 for m in ("datum", "objem", "částka", "castka",
                        "protiúčet", "protiucet", "zpráva", "zprava")
            if any(m in c for c in cells)
        )
        if hits >= 2:
            header_idx = i
            header = parts
            break
    if header_idx < 0:
        return []

    idx_date = idx_amt = idx_desc = idx_counter = idx_type = -1
    for i, h in enumerate(header):
        hl = safe_str(h).lower()
        if idx_date < 0 and "datum" in hl:
            idx_date = i
        if idx_amt < 0 and (
            "objem" in hl or "částka" in hl or "castka" in hl
        ):
            idx_amt = i
        if idx_desc < 0 and (
            "zpráva" in hl or "zprava" in hl
            or "popis" in hl or "pozn" in hl
        ):
            idx_desc = i
        if idx_counter < 0 and (
            "protiúčet" in hl or "protiucet" in hl
            or "název" in hl or "nazev" in hl
        ):
            idx_counter = i
        if idx_type < 0 and "typ" in hl:
            idx_type = i

    txns: List[Dict[str, Any]] = []
    for line in lines[header_idx + 1:]:
        if not line.strip():
            continue
        parts = _split_line(line, delimiter=delim)
        if idx_date < 0 or idx_date >= len(parts):
            continue
        date_val = parse_date(parts[idx_date])
        if not date_val:
            continue
        amt = parse_amount(parts[idx_amt]) if 0 <= idx_amt < len(parts) else 0.0
        desc = safe_str(parts[idx_desc]) if 0 <= idx_desc < len(parts) else ""
        counter = safe_str(parts[idx_counter]) if 0 <= idx_counter < len(parts) else ""
        if not counter and desc:
            counter = desc.split(",")[0].strip()
        ttype = safe_str(parts[idx_type]) if 0 <= idx_type < len(parts) else ""
        full_desc = (ttype + " " + desc).strip()
        if amt == 0.0 and not full_desc:
            continue
        txns.append({
            "Дата": date_val,
            "Сумма": amt,
            "Контрагент": counter,
            "Наименование счета": account_name,
            "Описание": full_desc,
        })
    return txns


# --- BluOr ------------------------------------------------------------------

def _bluor_generic(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """
    BluOr Bank CSV. Строки вида:
      "Счет (LV08 CBBR ...)","01.08.2026","","Начальный остаток","0.00","EUR",""
      "Счет (LV08 CBBR ...)","05.08.2026","","Payment to X","12.34","EUR",""

    [FIX-BSR3] BSR_Estate_EUR_BluOr_3 содержит только служебные строки
               (Начальный/Конечный остаток, Дебет (D)/Кредит (C) итоги).
               Это не транзакции — фильтруем через SERVICE_WORDS.
    """
    text = read_text_with_encoding(file_content)
    if not text:
        return []
    txns: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.rstrip("\r\n")
        if not line.strip():
            continue
        parts = _split_line(line, delimiter=",")
        if len(parts) < 5:
            continue
        joined = " ".join(safe_str(p).lower() for p in parts)
        if _is_service_row(joined):
            continue

        # Ищем дату
        date_val = ""
        date_idx = -1
        for i, p in enumerate(parts):
            d = parse_date(p)
            if d:
                date_val = d
                date_idx = i
                break
        if not date_val:
            continue

        # Сумма — ближайшее числовое после даты
        amt = 0.0
        for j in range(date_idx + 1, len(parts)):
            a = parse_amount(parts[j])
            if a != 0.0:
                amt = a
                break

        desc = _longest_text(parts, min_len=3)
        if not desc and amt == 0.0:
            continue
        counter = desc.split(",")[0].strip() if desc else ""
        txns.append({
            "Дата": date_val,
            "Сумма": amt,
            "Контрагент": counter,
            "Наименование счета": account_name,
            "Описание": desc,
        })
    return txns


def parse_bsr_bluor_2(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    return _bluor_generic(file_content, account_name)


def parse_bsr_bluor_3(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    return _bluor_generic(file_content, account_name)


def parse_kl59_bluor(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    return _bluor_generic(file_content, account_name)


# --- RAK Bank ---------------------------------------------------------------

def parse_rak_bank_xlsx(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """RAK Bank .xlsx (AED)."""
    df = read_xlsx(file_content)
    if df is None or df.empty:
        return []
    rows = df.values.tolist()
    header_idx = _find_header_row(
        rows,
        markers=["date", "description", "amount", "debit", "credit", "balance"],
        max_scan=20, min_hits=2,
    )
    if header_idx < 0:
        return []
    header = [safe_str(c) for c in rows[header_idx]]
    txns: List[Dict[str, Any]] = []
    for row in rows[header_idx + 1:]:
        d = _row_to_dict(header, row)
        date_val = parse_date(_pick(d, "date", "дата", "value date"))
        if not date_val:
            continue
        amt = parse_amount(_pick(d, "amount", "сумма"))
        if amt == 0.0:
            cr = parse_amount(_pick(d, "credit"))
            db = parse_amount(_pick(d, "debit"))
            if cr or db:
                amt = cr - abs(db)
        desc = _pick(d, "description", "details", "narrative", "описание")
        counter = _pick(d, "counterparty", "beneficiary") \
            or (desc.split(",")[0] if desc else "")
        if not desc and amt == 0.0:
            continue
        txns.append({
            "Дата": date_val,
            "Сумма": amt,
            "Контрагент": counter,
            "Наименование счета": account_name,
            "Описание": desc,
        })
    return txns


# --- Универсальный табличный парсер ----------------------------------------

def parse_generic_tabular(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """
    Универсальный fallback для табличных форматов.
    Ищем заголовок и пытаемся распознать дату/сумму/описание.
    Сначала пробуем как таблицу (openpyxl/xlrd/pd.read_html),
    затем — как текст (CSV).
    """
    txns: List[Dict[str, Any]] = []

    # 1) Табличный путь
    df = read_xlsx(file_content)
    if df is not None and not df.empty:
        rows = df.values.tolist()
        header_idx = _find_header_row(
            rows,
            markers=["date", "дата", "amount", "сумма", "description", "описание",
                     "debit", "credit", "summary"],
            max_scan=30, min_hits=2,
        )
        if header_idx >= 0:
            header = [safe_str(c) for c in rows[header_idx]]
            for row in rows[header_idx + 1:]:
                d = _row_to_dict(header, row)
                date_val = parse_date(
                    _pick(d, "date", "дата", "datum", "értéknap")
                )
                if not date_val:
                    continue
                amt = parse_amount(
                    _pick(d, "amount", "сумма", "összeg", "objem", "částka")
                )
                if amt == 0.0:
                    cr = parse_amount(_pick(d, "credit", "kredit", "приход"))
                    db = parse_amount(_pick(d, "debit", "debet", "расход"))
                    if cr or db:
                        amt = cr - abs(db)
                desc = _pick(d, "description", "описание", "details",
                             "zpráva", "popis", "megjegyzés")
                counter = _pick(d, "counterparty", "контрагент",
                                "partner", "beneficiary") \
                    or (desc.split(",")[0] if desc else "")
                if not desc and amt == 0.0:
                    continue
                txns.append({
                    "Дата": date_val,
                    "Сумма": amt,
                    "Контрагент": counter,
                    "Наименование счета": account_name,
                    "Описание": desc,
                })
            if txns:
                return txns

    # 2) CSV-путь fallback
    text = read_text_with_encoding(file_content)
    if not text:
        return txns
    lines = text.splitlines()
    if not lines:
        return txns

    delim = ","
    sample = "\n".join(lines[:5])
    if sample.count(";") > sample.count(","):
        delim = ";"

    header_idx = -1
    header: List[str] = []
    for i, line in enumerate(lines[:60]):
        parts = _split_line(line, delimiter=delim)
        cells = [safe_str(c).lower() for c in parts]
        hits = sum(
            1 for m in ("date", "дата", "amount", "сумма",
                        "description", "описание")
            if any(m in c for c in cells)
        )
        if hits >= 2:
            header_idx = i
            header = parts
            break
    if header_idx < 0:
        return txns

    idx_date = idx_amt = idx_desc = idx_counter = -1
    for i, h in enumerate(header):
        hl = safe_str(h).lower()
        if idx_date < 0 and (
            "date" in hl or "дата" in hl or "datum" in hl
        ):
            idx_date = i
        if idx_amt < 0 and (
            "amount" in hl or "сумма" in hl or "összeg" in hl
        ):
            idx_amt = i
        if idx_desc < 0 and (
            "description" in hl or "описание" in hl or "details" in hl
        ):
            idx_desc = i
        if idx_counter < 0 and (
            "counterparty" in hl or "контрагент" in hl
        ):
            idx_counter = i

    for line in lines[header_idx + 1:]:
        if not line.strip():
            continue
        parts = _split_line(line, delimiter=delim)
        if idx_date < 0 or idx_date >= len(parts):
            continue
        date_val = parse_date(parts[idx_date])
        if not date_val:
            continue
        amt = parse_amount(parts[idx_amt]) if 0 <= idx_amt < len(parts) else 0.0
        desc = safe_str(parts[idx_desc]) if 0 <= idx_desc < len(parts) else ""
        counter = safe_str(parts[idx_counter]) if 0 <= idx_counter < len(parts) else ""
        if not counter and desc:
            counter = desc.split(",")[0].strip()
        if amt == 0.0 and not desc:
            continue
        txns.append({
            "Дата": date_val,
            "Сумма": amt,
            "Контрагент": counter,
            "Наименование счета": account_name,
            "Описание": desc,
        })
    return txns


# =============================================================================
#                              DOCX-парсеры
# =============================================================================

def parse_generic_docx(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """Универсальный .docx: сначала таблицы, потом абзацы."""
    txns: List[Dict[str, Any]] = []

    # 1) Табличный путь
    if Document is not None:
        try:
            d = Document(io.BytesIO(file_content))
            for tbl in d.tables:
                rows = [[safe_str(c.text) for c in r.cells] for r in tbl.rows]
                if not rows:
                    continue
                header_idx = _find_header_row(
                    rows,
                    markers=["дата", "date", "сумма", "amount",
                             "описание", "description"],
                    max_scan=5, min_hits=2,
                )
                if header_idx < 0:
                    continue
                header = rows[header_idx]
                for row in rows[header_idx + 1:]:
                    d_row = _row_to_dict(header, row)
                    date_val = parse_date(_pick(d_row, "дата", "date", "datum"))
                    if not date_val:
                        continue
                    amt = parse_amount(_pick(d_row, "сумма", "amount", "objem"))
                    if amt == 0.0:
                        cr = parse_amount(_pick(d_row, "кредит", "credit", "приход"))
                        db = parse_amount(_pick(d_row, "дебет", "debit", "расход"))
                        if cr or db:
                            amt = cr - abs(db)
                    desc = _pick(d_row, "описание", "description",
                                 "назначение", "details")
                    counter = _pick(d_row, "контрагент", "counterparty",
                                    "получатель") \
                        or (desc.split(",")[0] if desc else "")
                    if not desc and amt == 0.0:
                        continue
                    txns.append({
                        "Дата": date_val,
                        "Сумма": amt,
                        "Контрагент": counter,
                        "Наименование счета": account_name,
                        "Описание": desc,
                    })
        except Exception:
            pass

    if txns:
        return txns

    # 2) Абзацный fallback
    text = docx_all_text(file_content)
    pattern = re.compile(
        r"(?P<date>\d{2}[./-]\d{2}[./-]\d{2,4})"
        r"[ \t]+"
        r"(?P<amount>-?\d[\d \u00a0.,]*\d)"
        r"(?P<rest>[^\n]*)"
    )
    for m in pattern.finditer(text):
        date_val = parse_date(m.group("date"))
        if not date_val:
            continue
        amt = parse_amount(m.group("amount"))
        rest = safe_str(m.group("rest"))
        txns.append({
            "Дата": date_val,
            "Сумма": amt,
            "Контрагент": rest.split(",")[0].strip() if rest else "",
            "Наименование счета": account_name,
            "Описание": rest,
        })
    return txns


def parse_regina_alfa_docx(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """
    Regina Alfa-bank .docx: табличный разбор + склейка многострочных записей.
    Валюта RUR/RUB опциональна.
    """
    if Document is None:
        return parse_generic_docx(file_content, account_name)
    try:
        d = Document(io.BytesIO(file_content))
    except Exception:
        return []

    txns: List[Dict[str, Any]] = []
    for tbl in d.tables:
        rows = [[safe_str(c.text) for c in r.cells] for r in tbl.rows]
        if not rows:
            continue
        header_idx = _find_header_row(
            rows,
            markers=["дата", "date", "сумма", "amount",
                     "описание", "назначение", "контрагент"],
            max_scan=5, min_hits=2,
        )
        if header_idx < 0:
            continue
        header = rows[header_idx]
        for row in rows[header_idx + 1:]:
            d_row = _row_to_dict(header, row)
            date_val = parse_date(_pick(d_row, "дата", "date"))
            if not date_val:
                continue
            amt = parse_amount(_pick(d_row, "сумма", "amount"))
            if amt == 0.0:
                cr = parse_amount(_pick(d_row, "кредит", "credit", "приход"))
                db = parse_amount(_pick(d_row, "дебет", "debit", "расход"))
                if cr or db:
                    amt = cr - abs(db)
            desc = _pick(d_row, "описание", "назначение",
                         "description", "details")
            counter = _pick(d_row, "контрагент", "counterparty",
                            "получатель") \
                or (desc.split(",")[0] if desc else "")
            if not desc and amt == 0.0:
                continue
            txns.append({
                "Дата": date_val,
                "Сумма": amt,
                "Контрагент": counter,
                "Наименование счета": account_name,
                "Описание": desc,
            })
    return txns


def parse_regina_alfa_pdf(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """Regina Alfa-bank .pdf: таблицы + текст."""
    txns: List[Dict[str, Any]] = []
    tables = pdf_all_tables(file_content)
    for tbl in tables:
        if not tbl:
            continue
        header_idx = _find_header_row(
            tbl,
            markers=["дата", "date", "сумма", "amount",
                     "описание", "назначение"],
            max_scan=5, min_hits=2,
        )
        if header_idx < 0:
            continue
        header = tbl[header_idx]
        for row in tbl[header_idx + 1:]:
            d_row = _row_to_dict(header, row)
            date_val = parse_date(_pick(d_row, "дата", "date"))
            if not date_val:
                continue
            amt = parse_amount(_pick(d_row, "сумма", "amount"))
            desc = _pick(d_row, "описание", "назначение", "description")
            counter = _pick(d_row, "контрагент", "counterparty") \
                or (desc.split(",")[0] if desc else "")
            if not desc and amt == 0.0:
                continue
            txns.append({
                "Дата": date_val,
                "Сумма": amt,
                "Контрагент": counter,
                "Наименование счета": account_name,
                "Описание": desc,
            })
    if txns:
        return txns

    # Текстовый fallback
    text = pdf_all_text(file_content)
    pattern = re.compile(
        r"(?P<date>\d{2}[./-]\d{2}[./-]\d{2,4})"
        r"[ \t]+"
        r"(?P<amount>-?\d[\d \u00a0.,]*\d)"
        r"(?P<rest>[^\n]*)"
    )
    for m in pattern.finditer(text):
        date_val = parse_date(m.group("date"))
        if not date_val:
            continue
        amt = parse_amount(m.group("amount"))
        rest = safe_str(m.group("rest"))
        txns.append({
            "Дата": date_val,
            "Сумма": amt,
            "Контрагент": rest.split(",")[0].strip() if rest else "",
            "Наименование счета": account_name,
            "Описание": rest,
        })
    return txns


def parse_generic_pdf(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    txns: List[Dict[str, Any]] = []
    tables = pdf_all_tables(file_content)
    for tbl in tables:
        if not tbl:
            continue
        header_idx = _find_header_row(
            tbl,
            markers=["дата", "date", "сумма", "amount",
                     "описание", "description"],
            max_scan=5, min_hits=2,
        )
        if header_idx < 0:
            continue
        header = tbl[header_idx]
        for row in tbl[header_idx + 1:]:
            d_row = _row_to_dict(header, row)
            date_val = parse_date(_pick(d_row, "дата", "date"))
            if not date_val:
                continue
            amt = parse_amount(_pick(d_row, "сумма", "amount"))
            desc = _pick(d_row, "описание", "description", "назначение")
            if not desc and amt == 0.0:
                continue
            txns.append({
                "Дата": date_val,
                "Сумма": amt,
                "Контрагент": "",
                "Наименование счета": account_name,
                "Описание": desc,
            })
    return txns


def parse_tinkoff_docx(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """Tinkoff .docx: таблицы или абзацы."""
    return parse_generic_docx(file_content, account_name)


def parse_tinkoff_xlsx(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """Tinkoff .xlsx."""
    return parse_generic_tabular(file_content, account_name)


def parse_tinkoff_csv(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """Tinkoff .csv (с ';')."""
    return parse_generic_tabular(file_content, account_name)


def parse_jenhor_unelma_docx(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """
    JenHor Unelma CZK CSAS .docx.

    [FIX-3] Табличный путь + regex-fallback по абзацам.
            Regex НЕ жадный и НЕ склеивает соседние записи:
            используем [ \\t] вместо \\s, чтобы не съедать \\n.
    """
    txns: List[Dict[str, Any]] = []

    # 1) Табличный путь
    if Document is not None:
        try:
            d = Document(io.BytesIO(file_content))
            for tbl in d.tables:
                rows = [[safe_str(c.text) for c in r.cells] for r in tbl.rows]
                if not rows:
                    continue
                header_idx = _find_header_row(
                    rows,
                    markers=["datum", "date", "дата",
                             "částka", "castka", "objem", "сумма", "amount",
                             "popis", "zpráva", "описание"],
                    max_scan=5, min_hits=2,
                )
                if header_idx < 0:
                    continue
                header = rows[header_idx]
                for row in rows[header_idx + 1:]:
                    d_row = _row_to_dict(header, row)
                    date_val = parse_date(
                        _pick(d_row, "datum", "date", "дата")
                    )
                    if not date_val:
                        continue
                    amt = parse_amount(
                        _pick(d_row, "částka", "castka", "objem",
                              "сумма", "amount")
                    )
                    if amt == 0.0:
                        cr = parse_amount(_pick(d_row, "kredit", "credit", "приход"))
                        db = parse_amount(_pick(d_row, "debet", "debit", "расход"))
                        if cr or db:
                            amt = cr - abs(db)
                    desc = _pick(d_row, "popis", "zpráva", "zprava",
                                 "описание", "description", "pozn")
                    counter = _pick(d_row, "protiúčet", "protiucet",
                                    "контрагент", "counterparty") \
                        or (desc.split(",")[0] if desc else "")
                    if not desc and amt == 0.0:
                        continue
                    txns.append({
                        "Дата": date_val,
                        "Сумма": amt,
                        "Контрагент": counter,
                        "Наименование счета": account_name,
                        "Описание": desc,
                    })
            if txns:
                return txns
        except Exception:
            pass

    # 2) Regex-fallback по абзацам.
    #    Паттерн: дата + [ \t]+ + сумма + хвост до конца строки.
    #    [ \t] вместо \s — чтобы не съедать \n между записями.
    text = docx_all_text(file_content)
    pattern = re.compile(
        r"(?P<date>\d{2}[./-]\d{2}[./-]\d{2,4})"
        r"[ \t]+"
        r"(?P<amount>-?\d[\d \u00a0.,]*\d|\d)"
        r"(?P<rest>[^\n]*)"
    )
    for m in pattern.finditer(text):
        date_val = parse_date(m.group("date"))
        if not date_val:
            continue
        amt = parse_amount(m.group("amount"))
        rest = safe_str(m.group("rest"))
        if not rest and amt == 0.0:
            continue
        txns.append({
            "Дата": date_val,
            "Сумма": amt,
            "Контрагент": rest.split(",")[0].strip() if rest else "",
            "Наименование счета": account_name,
            "Описание": rest,
        })
    return txns


def parse_n26_docx(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """
    N26 .docx: табличный разбор + терпимый regex
    (dd.mm.yy, пробел перед €).
    """
    txns: List[Dict[str, Any]] = []

    # 1) Табличный путь
    if Document is not None:
        try:
            d = Document(io.BytesIO(file_content))
            for tbl in d.tables:
                rows = [[safe_str(c.text) for c in r.cells] for r in tbl.rows]
                if not rows:
                    continue
                header_idx = _find_header_row(
                    rows,
                    markers=["date", "дата", "amount", "сумма",
                             "description", "payee", "описание"],
                    max_scan=5, min_hits=2,
                )
                if header_idx < 0:
                    continue
                header = rows[header_idx]
                for row in rows[header_idx + 1:]:
                    d_row = _row_to_dict(header, row)
                    date_val = parse_date(_pick(d_row, "date", "дата", "datum"))
                    if not date_val:
                        continue
                    amt = parse_amount(_pick(d_row, "amount", "сумма", "betrag"))
                    desc = _pick(d_row, "description", "payee",
                                 "описание", "verwendungszweck")
                    counter = _pick(d_row, "payee", "counterparty", "empfänger") \
                        or (desc.split(",")[0] if desc else "")
                    if not desc and amt == 0.0:
                        continue
                    txns.append({
                        "Дата": date_val,
                        "Сумма": amt,
                        "Контрагент": counter,
                        "Наименование счета": account_name,
                        "Описание": desc,
                    })
            if txns:
                return txns
        except Exception:
            pass

    # 2) Regex-fallback
    text = docx_all_text(file_content)
    pattern = re.compile(
        r"(?P<date>\d{2}\.\d{2}\.\d{2,4})"
        r"[^\n]*?"
        r"(?P<amount>-?\d[\d .,]*\d)\s*€?"
    )
    for m in pattern.finditer(text):
        date_val = parse_date(m.group("date"))
        if not date_val:
            continue
        amt = parse_amount(m.group("amount"))
        line = text[m.start():m.end()]
        txns.append({
            "Дата": date_val,
            "Сумма": amt,
            "Контрагент": "",
            "Наименование счета": account_name,
            "Описание": line.strip(),
        })
    return txns


# --- Kapital Saida ----------------------------------------------------------

def _kapital_is_skip_desc(desc: str) -> bool:
    """Служебные/реквизитные строки Kapital Bank — не транзакции."""
    d = (desc or "").lower()
    skip_words = [
        "остаток", "баланс", "balance", "итого", "total",
        "реквизит", "входящий остаток", "исходящий остаток",
        "выписка по счету", "выписка", "statement", "account",
        "открытие счета", "закрытие счета", "hesab",
    ]
    return any(w in d for w in skip_words)


def parse_kapital_saida_docx(file_content: bytes, account_name: str) -> List[Dict[str, Any]]:
    """
    Kapital bank_Saida_AZN .docx.

    [FIX-2] Терпимый разбор: дата и сумма могут быть в одной ячейке
            ('01.08.2026 1 234,56'), описание — в отдельной колонке.
            Также добавлены жёсткие фильтры против остатков/реквизитов.
    """
    if Document is None:
        return []
    try:
        d = Document(io.BytesIO(file_content))
    except Exception:
        return []

    txns: List[Dict[str, Any]] = []

    # 1) Табличный путь
    for tbl in d.tables:
        rows = [[safe_str(c.text) for c in r.cells] for r in tbl.rows]
        if not rows:
            continue
        header_idx = _find_header_row(
            rows,
            markers=["tarix", "date", "дата",
                     "məbləğ", "məbləg", "сумма", "amount",
                     "təyinat", "описание", "description",
                     "дебет", "кредит"],
            max_scan=8, min_hits=2,
        )
        if header_idx < 0:
            continue
        header = rows[header_idx]
        for row in rows[header_idx + 1:]:
            d_row = _row_to_dict(header, row)
            # Вариант A: раздельные колонки
            date_val = parse_date(_pick(d_row, "tarix", "date", "дата"))
            amt = parse_amount(_pick(d_row, "məbləğ", "məbləg",
                                     "сумма", "amount"))
            if amt == 0.0:
                cr = parse_amount(_pick(d_row, "кредит", "credit",
                                        "mədaxil", "medaxil"))
                db = parse_amount(_pick(d_row, "дебет", "debit",
                                        "məxaric", "mexaric"))
                if cr or db:
                    amt = cr - abs(db)
            desc = _pick(d_row, "təyinat", "təyinatı",
                         "описание", "description", "назначение")
            counter = _pick(d_row, "контрагент", "counterparty",
                            "ad", "name") \
                or (desc.split(",")[0] if desc else "")

            # Вариант B: дата и сумма в одной ячейке
            if not date_val:
                for k, v in d_row.items():
                    m = re.match(
                        r"\s*(\d{2}[./-]\d{2}[./-]\d{2,4})"
                        r"[ \t]+"
                        r"(-?\d[\d\s.,]*\d)"
                        r"\s*(.*)",
                        v,
                    )
                    if m:
                        date_val = parse_date(m.group(1))
                        amt = parse_amount(m.group(2))
                        if not desc:
                            desc = m.group(3)
                        break

            if not date_val:
                continue
            if _kapital_is_skip_desc(desc):
                continue
            if not desc and amt == 0.0:
                continue
            txns.append({
                "Дата": date_val,
                "Сумма": amt,
                "Контрагент": counter,
                "Наименование счета": account_name,
                "Описание": desc,
            })
        if txns:
            return txns

    # 2) Абзацный fallback
    text = docx_all_text(file_content)
    pattern = re.compile(
        r"(?P<date>\d{2}[./-]\d{2}[./-]\d{2,4})"
        r"[ \t]+"
        r"(?P<amount>-?\d[\d \u00a0.,]*\d)"
        r"(?P<rest>[^\n]*)"
    )
    for m in pattern.finditer(text):
        date_val = parse_date(m.group("date"))
        if not date_val:
            continue
        amt = parse_amount(m.group("amount"))
        rest = safe_str(m.group("rest"))
        if _kapital_is_skip_desc(rest):
            continue
        txns.append({
            "Дата": date_val,
            "Сумма": amt,
            "Контрагент": rest.split(",")[0].strip() if rest else "",
            "Наименование счета": account_name,
            "Описание": rest,
        })
    return txns


# =============================================================================
#                              UI (Streamlit)
# =============================================================================

CSS = """
<style>
    .main { background-color: #f7f9fc; }
    .block-container { padding-top: 1.5rem; }
    h1, h2, h3 { color: #1f3a93; }
    .stMetric { background: #ffffff; border-radius: 10px; padding: 10px;
                box-shadow: 0 1px 4px rgba(0,0,0,0.05); }
    .debug-box { background: #f0f4ff; border-left: 4px solid #1f3a93;
                 padding: 8px 12px; border-radius: 6px; margin-bottom: 8px;
                 font-family: monospace; font-size: 0.85rem; }
    .bank-header { display: flex; align-items: center; gap: 10px; }
</style>
"""


def render_header() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("🏦 Аналитик банковских выписок")
    st.caption(
        "Загрузите выписки (CSV / XLSX / XLS / DOCX / PDF) — приложение "
        "разберёт их и сформирует единый Excel-отчёт со сводкой по счетам."
    )


def render_debug(debug_info: List[Dict[str, Any]]) -> None:
    """
    [FIX-10] Отладочный вывод: парсер, счёт, число операций,
             первые 3 операции, дамп для «подозрительных» файлов (<=2 операций).
    """
    if not debug_info:
        return
    with st.expander("🔧 Техническая информация (отладка)", expanded=False):
        for item in debug_info:
            st.markdown(
                f"<div class='debug-box'>"
                f"<b>🔍 {html.escape(item['filename'])}</b><br>"
                f"→ счёт: <b>{html.escape(item['account'])}</b><br>"
                f"→ парсер: <b>{html.escape(item['parser'])}</b> "
                f"({html.escape(item['account'])})<br>"
                f"→ <b>{item['count']}</b> операций"
                f"</div>",
                unsafe_allow_html=True,
            )
            preview = item.get("preview") or []
            if preview:
                st.markdown("Первые операции:")
                for p in preview[:3]:
                    st.markdown(
                        f"- `{p.get('Дата','')}` | `{p.get('Сумма','')}` | "
                        f"{html.escape(str(p.get('Описание',''))[:160])}"
                    )
            if item.get("dump"):
                with st.expander(f"Дамп {item['filename']}", expanded=False):
                    st.code(item["dump"][:4000])


def process_files(uploaded_files) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Возвращает (все транзакции, debug_info)."""
    all_txns: List[Dict[str, Any]] = []
    debug_info: List[Dict[str, Any]] = []

    for uf in uploaded_files:
        filename = uf.name
        try:
            content = uf.read()
        except Exception as e:
            st.warning(f"Не удалось прочитать {filename}: {e}")
            continue

        ext = os.path.splitext(filename)[1].lower().lstrip(".")
        account_name = clean_account_name(filename)

        parser = get_parser_by_ext(account_name, ext)
        parser_name = "—"
        txns: List[Dict[str, Any]] = []

        try:
            if parser is None:
                parser_name = "none"
            elif parser is _TINKOFF_TABULAR_MARKER:
                real = _resolve_tinkoff(ext)
                parser_name = real.__name__
                txns = real(content, account_name)
            else:
                parser_name = parser.__name__
                txns = parser(content, account_name)
        except Exception as e:
            parser_name = f"{getattr(parser, '__name__', '?')} (ОШИБКА)"
            txns = []
            st.warning(f"Ошибка при разборе {filename}: {e}")

        for t in txns:
            t.setdefault("Наименование счета", account_name)

        all_txns.extend(txns)

        # Превью первых 3 операций
        preview = []
        for t in txns[:3]:
            preview.append({
                "Дата": t.get("Дата", ""),
                "Сумма": format_amount(t.get("Сумма", 0)),
                "Описание": t.get("Описание", ""),
            })

        # Дамп — только для «подозрительных» (<=2 операций)
        dump = ""
        if len(txns) <= 2:
            try:
                if ext == "docx":
                    dump = docx_dump(content)
                elif ext == "pdf":
                    dump = pdf_all_text(content)[:4000]
                elif ext in ("csv", "xls", "xlsx"):
                    if _is_real_xls(content):
                        # BIFF-выгрузки нечитаемы как текст; пробуем xlrd,
                        # чтобы показать хоть что-то полезное
                        try:
                            df = read_xlsx(content)
                            if df is not None:
                                dump = df.head(20).to_string()
                            else:
                                dump = "(BIFF .xls — не удалось прочитать)"
                        except Exception:
                            dump = "(BIFF .xls — текстовый дамп недоступен)"
                    elif _is_real_xlsx(content):
                        try:
                            df = read_xlsx(content)
                            if df is not None:
                                dump = df.head(20).to_string()
                            else:
                                dump = "(xlsx — пусто)"
                        except Exception:
                            dump = "(xlsx — текстовый дамп недоступен)"
                    else:
                        dump = read_text_with_encoding(content)[:2000]
            except Exception:
                dump = ""

        debug_info.append({
            "filename": filename,
            "account": account_name,
            "parser": parser_name,
            "count": len(txns),
            "preview": preview,
            "dump": dump,
        })

    return all_txns, debug_info


def build_excel(txns: List[Dict[str, Any]]) -> bytes:
    """Формируем Excel с листами 'Транзакции' и 'Сводка по счетам'."""
    if not txns:
        df = pd.DataFrame(columns=list(TXN_FIELDS))
        summary = pd.DataFrame(
            columns=["Наименование счета", "Кол-во операций",
                     "Сумма прихода", "Сумма расхода", "Итог"]
        )
    else:
        df = pd.DataFrame(txns)
        for col in TXN_FIELDS:
            if col not in df.columns:
                df[col] = ""
        df = df[list(TXN_FIELDS)]

        rows = []
        for acc, grp in df.groupby("Наименование счета"):
            income = grp.loc[grp["Сумма"] > 0, "Сумма"].sum()
            expense = grp.loc[grp["Сумма"] < 0, "Сумма"].sum()
            rows.append({
                "Наименование счета": acc,
                "Кол-во операций": len(grp),
                "Сумма прихода": round(income, 2),
                "Сумма расхода": round(expense, 2),
                "Итог": round(income + expense, 2),
            })
        summary = pd.DataFrame(rows)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Транзакции")
        summary.to_excel(writer, index=False, sheet_name="Сводка по счетам")
    return buf.getvalue()


def main() -> None:
    render_header()

    uploaded = st.file_uploader(
        "Загрузите выписки",
        type=["csv", "xlsx", "xls", "docx", "pdf"],
        accept_multiple_files=True,
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        run = st.button("▶️ Обработать", type="primary")
    with col2:
        st.write("")

    if "txns" not in st.session_state:
        st.session_state["txns"] = []
    if "debug" not in st.session_state:
        st.session_state["debug"] = []

    if run:
        if not uploaded:
            st.warning("Сначала загрузите хотя бы один файл.")
        else:
            with st.spinner("Разбираем выписки..."):
                txns, debug_info = process_files(uploaded)
                st.session_state["txns"] = txns
                st.session_state["debug"] = debug_info

    txns = st.session_state.get("txns", [])
    debug_info = st.session_state.get("debug", [])

    if txns:
        df = pd.DataFrame(txns)
        total = df["Сумма"].sum()
        income = df.loc[df["Сумма"] > 0, "Сумма"].sum()
        expense = df.loc[df["Сумма"] < 0, "Сумма"].sum()
        accounts = df["Наименование счета"].nunique()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Операций", len(df))
        m2.metric("Счетов", accounts)
        m3.metric("Приход", format_amount(income))
        m4.metric("Расход", format_amount(expense))

        st.subheader("Транзакции")
        show_df = df.copy()
        show_df["Сумма"] = show_df["Сумма"].apply(format_amount)
        st.dataframe(show_df, use_container_width=True, height=400)

        excel_bytes = build_excel(txns)
        st.download_button(
            "📥 Скачать Excel-отчёт",
            data=excel_bytes,
            file_name="bank_report.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
        )

    render_debug(debug_info)


# =============================================================================
#                              ЗАПУСК
# =============================================================================

if __name__ == "__main__":
    main()


# =============================================================================
#                                  CHANGELOG
# =============================================================================
#
# [FIX-1]  _parse_mkb_any: каскад xlrd → openpyxl → pd.read_html → CSV-путь.
#          Лечит Budapest HUF-MKB_*.xls (BIFF, было 0 операций).
#          Заголовок ищется в первых 15 строках по Sorszám/Értéknap/Összeg
#          с диакритикой или без.
#
# [FIX-2]  parse_kapital_saida_docx: терпимый табличный разбор —
#          дата и сумма могут быть в одной ячейке ('01.08.2026 1 234,56').
#          Добавлен _kapital_is_skip_desc против остатков/реквизитов.
#          Лечит Kapital bank_Saida_AZN (было 1 операция).
#
# [FIX-3]  parse_jenhor_unelma_docx: табличный путь + regex-fallback
#          по абзацам. Regex не жадный, использует [ \t] вместо \s,
#          чтобы не склеивать соседние записи через \n.
#          Лечит JenHor_Unelma_CZK_CSAS.docx (было 2 операции).
#
# [FIX-4]  parse_csob_generic: принимает строки с len(parts) >= 4,
#          не требует ровно 6. Авто-поиск даты и суммы в первых 10 полях.
#          Лечит DŽIBIK Main CSOB CZK (было 2 операции).
#
# [FIX-5]  parse_csob_generic: автодетект сдвига индексов —
#          дата ищется по содержимому, а не по позиции; сумма —
#          ближайшее числовое после даты.
#          Лечит RR_Rev_OSTR_CZK_CSOB, Koruna_Strojka_*,
#          JENISOV - HORSKA_CSOB.
#
# [FIX-6]  parse_saida_wise_xlsx: терпимо к 'Дата и время' vs 'Дата',
#          'Сумма' vs 'Amount', 'Тип транзакции' vs 'Type'.
#          Лечит Saida_Wise.xlsx (16 операций).
#
# [FIX-7]  parse_unicredit_generic: разделитель ',' или ';' определяется
#          автоматически, колонки ищутся по подстроке (Datum/Částka/Zpráva,
#          Date/Amount/Description, поддержка Debit/Credit).
#          Лечит B1_Estate_CZK_UC, Garpiz UniCredit Bank CZK,
#          Garpiz_Pernink_CZK_UC, Koruna UniCredit CZK,
#          TwoHills Molly Unicredit CZK.
#
# [FIX-8]  parse_wio_business: терпимо к 'Account name' + 'Transaction type',
#          формат даты dd/mm/yyyy, суммы с валютным суффиксом.
#          Лечит WIO Business Bank (Aug 17 / Aug 1) — 34 и 38 операций.
#
# [FIX-9]  parse_industra_generic: терпимый поиск 'Дата транзакции' +
#          'Дебет'/'Кредит', авто-сдвиг индексов по содержимому,
#          fallback на CSV-путь.
#          Лечит KL59_Rev_NB_EUR_Industra, AN14_Estate_EUR_Industra,
#          Plavas1_Estate_EUR_Industra (было 1–3 операции).
#
# [FIX-10] UI: добавлен render_debug — для каждого файла показывает
#          имя парсера, число операций, первые 3 операции
#          (Дата, Сумма, Описание). Плюс дамп для файлов с <=2 операциями
#          (docx_dump, pdf_all_text, head(20) для таблиц, 2000 символов
#          текста для CSV).
#
# [FIX-11] _route_tabular: Revolut проверяется ДО Industra
#          (иначе AN14_*_Revolut.csv уходил в industra_an14).
#          Комментарий сохранён и усилен.
#
# [FIX-16] parse_paysera_generic: окно поиска заголовка 60 строк,
#          англ. заголовки (Date/Amount/Details/Beneficiary).
#
# [FIX-18] parse_stalkin_ml2_fio: поиск заголовка по Datum/Objem/Částka,
#          индексы колонок по содержимому заголовка.
#
# [FIX-BSR3] _bluor_generic: пропускает служебные строки
#            (Начальный/Конечный остаток, Дебет(D)/Кредит(C))
#            через _is_service_row/SERVICE_WORDS.
#            BSR_Estate_EUR_BluOr_3 содержит только служебные строки —
#            0 операций здесь корректны.
#
# =============================================================================
