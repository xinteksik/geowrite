# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Reverse-engineered source code for **geoWrite 2.1**, a WYSIWYG rich text editor for the Commodore 64 GEOS operating system (Berkeley Softworks, 1985–1988). Reverse-engineered by Michael Steil in 2020. Extensive documentation at [pagetable.com](https://www.pagetable.com/?p=1450).

## Build Commands

```bash
# Assemble, link, and encrypt (default locale: en)
make

# Build a specific locale (en, de, cs)
make LOCALE=cs

# Create VLIR/CVT file (with metadata header for disk image)
make cvt LOCALE=cs

# Create D64 disk image (formatted, with geoWrite installed as GEOS file)
make d64 LOCALE=cs

# Upload D64 to FTP
make upload LOCALE=cs          # → ftp://anonymous:@192.168.1.250/Temp/

# Remove build artifacts
make clean
```

**Requirements:** `cc65` suite (ca65 assembler + ld65 linker), Python 3, and `c1541` (from VICE).

Output lands in `build/{locale}/` as 11 binary files + `geoWrite.cvt` + `geoWrite.d64`.

## Architecture

### File Format: VLIR (Variable Length Indexed Record)

geoWrite uses GEOS's overlay architecture. Only record 0 is always resident; records 1–8 are swapped in/out from disk on demand. This is the fundamental constraint behind all code organization decisions — each record must fit within available memory.

| Record | File | Purpose | Notes |
|--------|------|---------|-------|
| 0 | geoWrite-0.s | Library code, core text rendering | Always resident; 90% documented |
| 1 | geoWrite-1.s | Initialization, copy protection | 100% documented |
| 2 | geoWrite-2.s | Core text editing | 30% documented |
| 3 | geoWrite-3.s | Cut, copy, paste | 100% documented |
| 4 | geoWrite-4.s | Ruler editing | 20% documented |
| 5 | geoWrite-5.s | Startup, file open/convert | 80% documented |
| 6 | geoWrite-6.s | Navigation, search/replace, headers/footers | 70% documented |
| 7 | geoWrite-7.s | Printing | 20% documented |
| 8 | geoWrite-8.s | Print settings | 10% documented |
| — | geoWrite-fhdr.s | File header (icon data) | 100% documented |
| — | protection.s | Copy protection check | 100% documented |
| — | cvt.s | CVT format wrapper | — |

### Localization

Three locales, each in its own directory with 5 UI graphics files (`graph1.s`–`graph5.s`) and 8 string include files:

- `en/` — English (primary, GEOS 2.0)
- `de/` — German
- `cs/` — Czech (added by repo owner)

Locale is selected via `config.inc` defines (`LOCALE_EN`, `LOCALE_DE`, `LOCALE_CS`). Locale-specific differences include decimal separator, character encoding, date format, and UI string placement.

---

## Czech Locale (`cs/`)

### Configuration (`config.inc`)

```asm
LANG           = LANG_EN
CHAR_ENCODING  = CHAR_ENCODING_CS
DECIMAL_SEPARATOR = ','
DATE_FORMAT_US = 0              ; European format: DD. Month YYYY, 24h time
PROT_EXEC_TRACK = 13
PROT_EXEC_SECTOR = 7
PROT_SERIAL_TRACK = 14
PROT_SERIAL_SECTOR = 13
SERIAL = $58B5
```

All UI strings in `cs/` are identical to `en/`. No translated content remains.

---

### CP852 Print-Time Character Remapping (`geoWrite-8.s`, `convertToCp852`)

At print time, record 7 calls `convertToCp852` (in record 8) to translate GEOS character codes to CP852 bytes before sending to the printer. The table is a parallel src/tgt array scanned with `ldy #N` / `cmp cp852_src-1,y`.

Current mapping table (34 entries):

| GEOS key | CP852 | Char | GEOS key | CP852 | Char |
|----------|-------|------|----------|-------|------|
| `2` | $D8 | ě | `3` | $E7 | š |
| `4` | $9F | č | `5` | $FD | ř |
| `6` | $A7 | ž | `7` | $EC | ý |
| `8` | $A0 | á | `9` | $A1 | í |
| `0` | $82 | é | `1` | $A2 | ó |
| `@` | $A3 | ú | `:` | $85 | ů |
| `!` (Shift+1) | $31 | 1 | `"` (Shift+2) | $32 | 2 |
| `#` (Shift+3) | $33 | 3 | `$` (Shift+4) | $34 | 4 |
| `%` (Shift+5) | $35 | 5 | `&` (Shift+6) | $36 | 6 |
| `'` (Shift+7) | $37 | 7 | `(` (Shift+8) | $38 | 8 |
| `)` (Shift+9) | $39 | 9 | `^` | $9C | ť |
| `}` | $D4 | ď | `{` | $E5 | ň |
| `~` | $28 | `(` | `*` | $29 | `)` |
| `_` | $FC | Ú | `\|` | $E6 | (—) |
| `;` | $AC | ¬ | `\` | $A6 | Ž |
| `[` | $27 | `'` | `]` | $21 | `!` |
| `<` | $3B | `;` | `>` | $3A | `:` |

**To add new entries:** append to `cp852_src`/`cp852_tgt` in `geoWrite-8.s` and increment `ldy #N`.

---

### Known CODE8 Pitfalls for Future Changes

`geoWrite-8.s` contains three `i_BitmapUp` calls whose first two inline bytes are the bitmap address (little-endian). These are now fixed with `.lobyte(graph_rect16x16)` / `.lobyte(graph_rect32x16)` so the linker resolves them correctly regardless of CODE8 size.

The embedded `JSR L089F` after the first `i_BitmapUp` was originally encoded as raw `.byte` values with a LANG conditional. It is now a proper `jsr L089F` instruction.

**Both fixes are required whenever the size of CODE8 changes** (e.g. adding entries to `convertToCp852` shifts all subsequent labels). The `.lobyte()` expressions and symbolic `jsr` are self-correcting.

---

### Y2K Fix (`geoWrite-7.s`, `getYear`)

```asm
getYear:
    lda     year
    add     #<2000      ; was #<1900 — gives correct 4-digit year 2000–2099
    sta     r3L
    lda     #>2000
    adc     #0
    sta     r3H
```

---

### 4-Drive Support (MegaPatch 3)

The Czech build includes patches from `4drivePatch/geoWritev2.1_mp3.cvt`, implemented at source level. **Target platform: MegaPatch 3 (MP3)** — not standard GEOS 2.0.

#### Files changed

**`geoWrite-0.s` — `findDocDevice`:**
Replaced the 2-drive check (drives 8 and 9 hardcoded) with a loop that probes all drives 8…8+NUMDRV−1 using `GetPtrCurDkNm` ($C298). The function now finds the document on whichever drive holds the matching disk name.

**`geoWrite-5.s` — `swapDrive`:**
Changed from cycling 8↔9 to direct drive selection from MegaPatch button return value:
```asm
swapDrive:
    and     #$0F    ; MegaPatch buttons: A=$88→8, B=$89→9, C=$8A→10, D=$8B→11
    sta     docDrive
    jsr     swapUserZp
    jsr     SetDevice
    jsr     swapUserZp
    jmp     _OpenDisk
```

**`geoWrite-5.s` — `L36C4` (disk name fetch):**
Replaced hardcoded drive-8/drive-9 pointer table with `jsr OpenDisk` ($C2A1), which sets r5 to the disk name for the current drive. Supports any drive number.

**`geoWrite-5.s` — `pickDocument`:**
- Drive button detection changed: `cmp #DRIVE; bne` → `cmp #$87; bcc` (MegaPatch drive buttons return $88–$8B)
- DISK button: removed showError prompt, goes straight to `_OpenDisk`
- Removed `LoadB L35B8` calls (DISK icon enable/disable no longer needed)

**`geoWrite-5.s` — `dlgbox_getfiles`:**
Replaced `DBGETFILES` + `DBUSRICON` block with MegaPatch type `$50` (multi-drive widget that shows A/B/C/D buttons):
```asm
.byte   $50         ; MegaPatch multi-drive widget
.byte   $04, $04    ; x, y position
.byte   OPEN        ; OK button type
.byte   $11, $19    ; button position
.byte   CANCEL
...
```

**`geoWrite-6.s` — `UpdateDocFileHeader`:**
Removed `jsr setDocDrive` call (redundant with 4-drive support).

#### GEOS kernel entries used

From `jumptab.inc`:
- `GetPtrCurDkNm = $C298` — returns pointer to disk name for current drive (pass X=#$FB)
- `OpenDisk = $C2A1` — opens disk in current drive; sets r5 to disk name pointer
- `SetDevice = $C2B0` — sets current device to A

From `sym.inc`:
- `DrACurDkNm = $841E`, `DrBCurDkNm = $8430` — drive 8/9 disk names in GEOS RAM
- `NUMDRV = $848D` — number of configured drives
- `curDrive = $8489` — current active drive

---

### Key Include Files

- `config.inc` — Locale selection, serial number, copy protection track/sector, UI tweaks
- `const.inc` — System constants and addresses (~12 KB)
- `zeropage.inc` / `zeropage.s` — Zero page layout (0x80–0xFF); performance-critical variables
- `geosmac.inc` — GEOS convenience macros (`LoadB`, `LoadW`, `MoveB`, etc.)
- `jumptab.inc` — GEOS ROM jump table entries
- `sym.inc` — Global symbol exports shared across records

### Copy Protection & Encryption

Two layers:
1. **protection.s** — Verifies disk has signature bytes in sector headers at `PROT_EXEC_TRACK`/`PROT_EXEC_SECTOR` (defined in `config.inc`).
2. **encrypt.py** — Post-build step; XOR-obfuscates records 0 and 1 using calculated checksums.

### Zero Page

128 bytes (0x80–0xFF) are fully custom-allocated for speed. Includes cursor structures (cursor0–3), font cache pointers, text metrics, pagination state, and UI variables. See `zeropage.s` and `zeropage.inc` for the full layout.

### CVT File Format

`cvt.s` / `geoWrite-cvt.cfg` build a GEOS Convert file. The magic string must be `"PRG formatted GEOS file V1.0"` (with ` V1.0` suffix) for `c1541 -geoswrite` to accept it.

`make d64 LOCALE=cs` creates `build/cs/geoWrite.d64`: a formatted C1541 disk image with geoWrite installed as a GEOS USR file, ready to use directly in a GEOS environment.
