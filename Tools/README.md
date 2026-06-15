# Nástroje / Tools

## cvt_convert.py — Konvertor geoWrite CVT (česká lokalizace)

### Popis (česky)

Python skript pro konverzi mezi formátem geoWrite CVT a prostým textem nebo Markdownem.
Určen pro českou lokalizaci (`cs`), která používá vlastní kódování češtiny v GEOS prostředí.

**Funkce:**

- **export** — Převede dokument geoWrite (`.cvt`) na prostý text UTF-8 (`.txt`).
- **import** — Převede textový soubor UTF-8 zpět na dokument geoWrite (`.cvt`); vyžaduje šablonu CVT pro metadata (ikona, název souboru).
- **import-md** — Převede soubor Markdown na dokument geoWrite; každé nadpis `#` začíná novou stránku.

Skript automaticky rozpozná dva varianty CVT formátu:
- **DOC-CVT** — dokumenty vytvořené přímo v geoWrite / geoConvert
- **APP-CVT** — aplikační binárky sestavené tímto projektem (`cvt.s`)

Kódování češtiny odpovídá tabulce `cp852_src`/`cp852_tgt` v `geoWrite-8.s`.

**Použití:**

**Šablony CVT:**

| Soubor | Popis |
|--------|-------|
| `Tools/BLANK.cvt` | Prázdný dokument — základní verze |
| `Tools/BLANK2.cvt` | Prázdný dokument pro geoWrite 2.1 |

```bash
# Exportovat dokument do textu
python3 Tools/cvt_convert.py export dokument.cvt dokument.txt

# Importovat text jako dokument geoWrite (geoWrite 2.1)
python3 Tools/cvt_convert.py import upraveny.txt Tools/BLANK2.cvt novy_dokument.cvt

# Importovat Markdown jako dokument geoWrite (geoWrite 2.1)
python3 Tools/cvt_convert.py import-md clanek.md Tools/BLANK2.cvt clanek.cvt
```

---

### Description (English)

Python script for converting between the geoWrite CVT format and plain text or Markdown.
Designed for the Czech locale (`cs`), which uses a custom Czech character encoding within the GEOS environment.

**Features:**

- **export** — Converts a geoWrite document (`.cvt`) to a plain UTF-8 text file (`.txt`).
- **import** — Converts a UTF-8 text file back to a geoWrite document (`.cvt`); requires a template CVT file to supply metadata (icon, filename).
- **import-md** — Converts a Markdown file to a geoWrite document; each `#` heading starts a new page.

The script auto-detects two CVT format variants:
- **DOC-CVT** — documents created directly in geoWrite / geoConvert
- **APP-CVT** — application binaries built by this project (`cvt.s`)

The Czech character encoding matches the `cp852_src`/`cp852_tgt` table in `geoWrite-8.s`.

**Usage:**

**CVT templates:**

| File | Description |
|------|-------------|
| `Tools/BLANK.cvt` | Blank document — basic version |
| `Tools/BLANK2.cvt` | Blank document for geoWrite 2.1 |

```bash
# Export a document to text
python3 Tools/cvt_convert.py export document.cvt document.txt

# Import text as a geoWrite document (geoWrite 2.1)
python3 Tools/cvt_convert.py import edited.txt Tools/BLANK2.cvt new_document.cvt

# Import Markdown as a geoWrite document (geoWrite 2.1)
python3 Tools/cvt_convert.py import-md article.md Tools/BLANK2.cvt article.cvt
```

**Requirements:** Python 3.6+, no external dependencies.
