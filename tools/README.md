# Nástroje / Tools

## cvt_convert.py — Konvertor geoWrite CVT (česká lokalizace)

### Popis

Python skript pro konverzi mezi formátem geoWrite CVT a prostým textem nebo Markdownem.
Určen pro českou lokalizaci (`cs`), která používá vlastní kódování češtiny v GEOS prostředí.

**Funkce:**

- **export** — Převede dokument geoWrite (`.cvt`) na prostý text UTF-8 (`.txt`).
- **import** — Převede textový soubor UTF-8 zpět na dokument geoWrite (`.cvt`); vyžaduje šablonu CVT pro metadata (ikona, název souboru).
- **import-md** — Převede soubor Markdown na dokument geoWrite; každý nadpis `#` začíná novou stránku.

Skript automaticky rozpozná dvě varianty CVT formátu:
- **DOC-CVT** — dokumenty vytvořené přímo v geoWrite
- **APP-CVT** — aplikační binárky sestavené tímto projektem (`cvt.s`)

Kódování češtiny odpovídá tabulce `cp852_src`/`cp852_tgt` v `cs/geoWrite-8.s`.

**Použití:**

**Šablony CVT:**

| Soubor | Popis |
|--------|-------|
| `BLANK.cvt` | Prázdný dokument — základní verze |
| `BLANK2.cvt` | Prázdný dokument pro geoWrite 2.1 |

```bash
# Export geoWrite dokumentu do textu
python3 cvt_convert.py export dokument.cvt text.txt

# Import textu do geoWrite dokumentu (geoWrite 2.1)
python3 cvt_convert.py import text.txt BLANK2.cvt dokument.cvt

# Import Markdown do geoWrite dokumentu (geoWrite 2.1)
python3 cvt_convert.py import-md text.md BLANK2.cvt dokument.cvt
```
