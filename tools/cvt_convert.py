#!/usr/bin/env python3
"""
geoWrite 2.1 CVT <-> TXT converter — Czech locale (cs)

Two CVT header variants are auto-detected:

  DOC-CVT (GEOS document, created by geoConvert/geosWrite):
    [30]  directory entry (CBM file type + filename + GEOS flags)
    [29]  magic "PRG formatted GEOS file V1.0\\0"
    [195] zero padding
    [254] info sector data   (no CBM link bytes)
    [254] VLIR record block  (no CBM link bytes)
    = 762 bytes header; record data follows as raw bytes

  APP-CVT (application binary, created by this project's cvt.s):
    magic at offset 0, followed by 256-byte sectors with CBM link bytes

Directory entry structure (DOC-CVT):
  byte 0:     CBM file type ($83=USR)
  bytes 1-2:  track/sector of first block
  bytes 3-18: filename (16 bytes, $A0-padded)
  bytes 19-20: GEOS info block track/sector
  byte 21:    GEOS structure type (1=VLIR)
  byte 22:    GEOS file type (7=APPL_DATA)
  bytes 23-28: date/time (year_offset, month, day, hour, min, sec)

geoWrite page record (one VLIR record per page):
  byte 0:     ESC_RULER (0x11)
  bytes 1-26: ruler data  (26 bytes; sym.inc .sizeof(ruler) = 26)
  byte 27:    NEWCARDSET (0x17)
  bytes 26-27: font ID (little-endian word)
  byte 28:    style byte
  bytes 29+:  text content (NUL-padded to fill the record)

Text escape codes inside content:
  0x10  ESC_GRAPHICS  inline image; 2-byte GOTOX then bitmap
  0x11  ESC_RULER     mid-page formatting change; 24 bytes ruler data
  0x17  NEWCARDSET    font/style change; 3 bytes (font_lo, font_hi, style)
  0x0A  LF            paragraph / line break
  0x0D  CR            line break (used at paragraph/page end)
  0x00  NUL           padding; long NUL runs mark end-of-page within a record

Character encoding (cs locale):
  Unshifted digit/symbol keys store Czech diacritics as their ASCII key code.
  Shifted digit keys (!="...) store the actual digit characters (1-9).
  Mapping is the inverse of cp852_src/cp852_tgt in geoWrite-8.s.
"""

import os
import re
import sys
import struct
import argparse

# ---------------------------------------------------------------------------
# Constants (from const.inc)
# ---------------------------------------------------------------------------
ESC_GRAPHICS = 0x10
ESC_RULER    = 0x11
NEWCARDSET   = 0x17   # = 23
LF           = 0x0A
CR           = 0x0D

VLIR         = 1

MAGIC        = b"PRG formatted GEOS file V1.0\r\x00"
MAGIC_OLD    = b"PRG formatted GEOS file\r\x00"
MAGIC_DOC    = b"PRG formatted GEOS file V1.0\x00"  # document CVT (no CR)

# Ruler data bytes after the ESC_RULER byte.
# sym.inc declares .sizeof(ruler) = 26; confirmed empirically from binary documents.
RULER_DATA_BYTES = 26
CARDSET_BYTES    = 4   # NEWCARDSET + font_id(word) + style

# DOC-CVT header layout (all sizes in bytes, no CBM link bytes anywhere)
_DIR_ENTRY_SIZE   = 30
_MAGIC_SIZE       = len(MAGIC)         # 31
_ZEROS_SIZE       = 254 - _DIR_ENTRY_SIZE - _MAGIC_SIZE  # = 195
_INFO_SIZE        = 254                # info sector data
_VLIR_BLOCK_SIZE  = 254                # VLIR record block (127 × 2-byte pairs)

DOC_HEADER_SIZE   = (_DIR_ENTRY_SIZE + _MAGIC_SIZE + _ZEROS_SIZE +
                     _INFO_SIZE + _VLIR_BLOCK_SIZE)  # = 762

_FNAME_OFFSET = 3   # byte offset of filename within dir entry
_FNAME_LEN    = 16  # filename field length (0xA0-padded)


def _set_dir_filename(dir_entry: bytes, name: str) -> bytes:
    """Return a copy of dir_entry with the GEOS filename replaced by name."""
    encoded = name[:_FNAME_LEN].encode('ascii', errors='replace')
    padded  = encoded.ljust(_FNAME_LEN, b'\xa0')
    entry   = bytearray(dir_entry)
    entry[_FNAME_OFFSET:_FNAME_OFFSET + _FNAME_LEN] = padded
    return bytes(entry)

_GSTRUC_OFF_IN_INFO = 68   # GEOS structure type within info sector data
                            # (offset 0 of info sector = icon width byte)

# ---------------------------------------------------------------------------
# Czech locale character mapping
# Source: cp852_src / cp852_tgt tables in geoWrite-8.s
# (geos_stored_byte, cp852_target_byte)
# ---------------------------------------------------------------------------
_CP852_PAIRS = [
    (0x32, 0xD8),  # '2' -> ě
    (0x33, 0xE7),  # '3' -> š
    (0x34, 0x9F),  # '4' -> č
    (0x35, 0xFD),  # '5' -> ř
    (0x36, 0xA7),  # '6' -> ž
    (0x37, 0xEC),  # '7' -> ý
    (0x38, 0xA0),  # '8' -> á
    (0x39, 0xA1),  # '9' -> í
    (0x30, 0x82),  # '0' -> é
    (0x31, 0xA2),  # '1' -> ó
    (0x40, 0xA3),  # '@' -> ú
    (0x3A, 0x85),  # ':' -> ů
    (0x21, 0x31),  # '!' (Shift+1) -> digit 1
    (0x22, 0x32),  # '"' (Shift+2) -> digit 2
    (0x23, 0x33),  # '#' (Shift+3) -> digit 3
    (0x24, 0x34),  # '$' (Shift+4) -> digit 4
    (0x25, 0x35),  # '%' (Shift+5) -> digit 5
    (0x26, 0x36),  # '&' (Shift+6) -> digit 6
    (0x27, 0x37),  # "'" (Shift+7) -> digit 7
    (0x28, 0x38),  # '(' (Shift+8) -> digit 8
    (0x29, 0x39),  # ')' (Shift+9) -> digit 9
    (0x5E, 0x9C),  # '^' -> ť
    (0x7D, 0xD4),  # '}' -> ď
    (0x7B, 0xE5),  # '{' -> ň
    (0x7E, 0x28),  # '~' -> '('
    (0x2A, 0x29),  # '*' -> ')'
    (0x5F, 0xFC),  # '_' -> Ú
    (0x7C, 0xE6),  # '|' -> (CP852 0xE6)
    (0x3B, 0xAC),  # ';' -> Č (CP852 0xAC = U+010C)
    (0x5C, 0xA6),  # '\' -> Ž
    (0x5B, 0x27),  # '[' -> apostrophe
    (0x5D, 0x21),  # ']' -> '!'
    (0x3C, 0x3B),  # '<' -> ';'
    (0x3E, 0x3A),  # '>' -> ':'
]

GEOS_TO_UNICODE: dict[int, str] = {}
for _geos, _cp852 in _CP852_PAIRS:
    GEOS_TO_UNICODE[_geos] = bytes([_cp852]).decode('cp852')

UNICODE_TO_GEOS: dict[str, int] = {v: k for k, v in GEOS_TO_UNICODE.items()}

# Uppercase Czech accented letters not in UNICODE_TO_GEOS → fold to their lowercase equivalent
_UPPERCASE_FOLD: dict[str, str] = {
    'Á': 'á', 'É': 'é', 'Í': 'í', 'Ó': 'ó',
    'Ě': 'ě', 'Š': 'š', 'Ř': 'ř', 'Ý': 'ý',
    'Ň': 'ň', 'Ť': 'ť', 'Ď': 'ď',
    # Ú, Č, Ž are already in UNICODE_TO_GEOS as uppercase
}


# ---------------------------------------------------------------------------
# CVT format detection and header parsing
# ---------------------------------------------------------------------------

_DOC_MAGIC_NEEDLE = b"PRG formatted GEOS file"  # common prefix for all variants


def _is_doc_cvt(data: bytes) -> bool:
    """Return True if this looks like a document CVT (dir-entry-first format)."""
    if len(data) < 64:
        return False
    # Document CVT: first byte is CBM file type ($81/$82/$83/$84), magic at offset 30
    cbm_type = data[0] & 0x0F
    if cbm_type not in (1, 2, 3, 4):  # SEQ, PRG, USR, REL
        return False
    return data[30:30 + len(_DOC_MAGIC_NEEDLE)] == _DOC_MAGIC_NEEDLE


def _is_app_cvt(data: bytes) -> bool:
    """Return True if this looks like an application CVT (magic-first format)."""
    return data[:len(MAGIC)] == MAGIC or data[:len(MAGIC_OLD)] == MAGIC_OLD


def _parse_doc_cvt_header(data: bytes) -> tuple[bytes, int, int]:
    """
    Parse a document CVT header.
    Returns (dir_entry, num_records, data_offset).
    """
    if len(data) < DOC_HEADER_SIZE:
        raise ValueError(f"File too short for DOC-CVT header ({len(data)} < {DOC_HEADER_SIZE})")

    dir_entry = data[0:_DIR_ENTRY_SIZE]

    geos_structure = data[_DIR_ENTRY_SIZE + _MAGIC_SIZE + _ZEROS_SIZE + _GSTRUC_OFF_IN_INFO]
    if geos_structure != VLIR:
        raise ValueError(
            f"Not a VLIR file (structure type byte = {geos_structure}); "
            "only VLIR geoWrite documents are supported"
        )

    vlir_block_start = _DIR_ENTRY_SIZE + _MAGIC_SIZE + _ZEROS_SIZE + _INFO_SIZE
    vlir_block = data[vlir_block_start:vlir_block_start + _VLIR_BLOCK_SIZE]

    num_records = 0
    for i in range(127):
        t = vlir_block[i * 2]
        s = vlir_block[i * 2 + 1]
        if t == 0x00 and s == 0x00:
            break
        num_records += 1

    return dir_entry, num_records, DOC_HEADER_SIZE


def _parse_app_cvt_header(data: bytes) -> tuple[bytes, int, int]:
    """
    Parse an application CVT header (magic-first, 256-byte sectors with link bytes).
    Returns (info_sector_data, num_records, data_offset).
    """
    if data[:len(MAGIC)] == MAGIC:
        pos = len(MAGIC)
    else:
        pos = len(MAGIC_OLD)

    info_sector = data[pos:pos + 256]
    pos += 256

    geos_structure = info_sector[_GSTRUC_OFF_IN_INFO + 2]  # +2 for the link bytes
    if geos_structure != VLIR:
        raise ValueError(f"Not a VLIR file (structure type = {geos_structure})")

    record_block = data[pos:pos + 256]
    pos += 256

    num_records = 0
    for i in range(127):
        t = record_block[2 + i * 2]
        s = record_block[3 + i * 2]
        if t == 0x00 and s == 0x00:
            break
        num_records += 1

    return info_sector, num_records, pos


# ---------------------------------------------------------------------------
# Text stream decoding  (works on raw record-data bytes, no link bytes)
# ---------------------------------------------------------------------------

NUL_PAGE_BREAK_THRESHOLD = 4   # NUL bytes in a row = end-of-page within a record


def decode_text_stream(record_data: bytes) -> list[str]:
    """
    Decode raw record data bytes into a list of page strings.

    Page boundaries are detected heuristically:
    - NUL_PAGE_BREAK_THRESHOLD or more consecutive NUL bytes, followed by ESC_RULER
    - Alternatively, after a CR-terminated section followed immediately by ESC_RULER

    Returns a list of strings, one per detected page.
    """
    pages: list[str] = []
    current: list[str] = []
    i = 0
    n = len(record_data)

    def flush_page() -> None:
        text = ''.join(current).strip()
        if text:
            pages.append(text)
        current.clear()

    # Skip leading non-page content before first ESC_RULER
    while i < n and record_data[i] != ESC_RULER:
        i += 1

    at_page_start = True

    while i < n:
        b = record_data[i]

        if b == ESC_RULER:
            ruler_end = i + 1 + RULER_DATA_BYTES
            # Scan for NEWCARDSET within the next ~30 bytes to handle ruler size variation
            scan_end = min(i + 35, n)
            newcard_pos = None
            for j in range(i + 1, scan_end):
                if record_data[j] == NEWCARDSET:
                    newcard_pos = j
                    break

            if at_page_start:
                # Start of a page: skip ruler + cardset, begin reading text
                if newcard_pos is not None:
                    i = newcard_pos + CARDSET_BYTES
                else:
                    i = ruler_end + CARDSET_BYTES
                at_page_start = False
            else:
                # Mid-page ruler change: skip ruler + cardset without page break
                if newcard_pos is not None:
                    i = newcard_pos + CARDSET_BYTES
                else:
                    i = ruler_end + CARDSET_BYTES

        elif b == NEWCARDSET:
            # Standalone cardset change mid-text (without preceding ESC_RULER)
            i += CARDSET_BYTES

        elif b == ESC_GRAPHICS:
            # Skip GOTOX (2 bytes) + bitmap data until next control byte or NUL
            i += 3  # ESC_GRAPHICS + GOTOX hi + GOTOX lo
            while i < n and record_data[i] not in (0x00, LF, CR, ESC_RULER, ESC_GRAPHICS, NEWCARDSET):
                i += 1

        elif b == LF or b == CR:
            current.append('\n')
            i += 1

        elif b == 0x00:
            # Count consecutive NUL bytes
            nul_count = 0
            j = i
            while j < n and record_data[j] == 0x00:
                nul_count += 1
                j += 1
            if nul_count >= NUL_PAGE_BREAK_THRESHOLD and j < n and record_data[j] == ESC_RULER:
                # End of this page, new page starts
                flush_page()
                at_page_start = True
            # Either way, skip all NUL bytes
            i = j

        elif b in GEOS_TO_UNICODE:
            current.append(GEOS_TO_UNICODE[b])
            i += 1

        elif 0x20 <= b <= 0x7E:
            current.append(chr(b))
            i += 1

        else:
            i += 1  # skip unknown control bytes

    flush_page()
    return pages


# ---------------------------------------------------------------------------
# Text encoding (Unicode → GEOS cs bytes)
# ---------------------------------------------------------------------------

def encode_text(text: str) -> bytes:
    """Encode UTF-8 text to geoWrite cs-locale byte sequence."""
    out = bytearray()
    for ch in text:
        if ch == '\n':
            out.append(LF)
        elif ch == '\f':
            pass  # page breaks handled at a higher level
        elif ch in UNICODE_TO_GEOS:
            out.append(UNICODE_TO_GEOS[ch])
        elif ch in _UPPERCASE_FOLD:
            folded = _UPPERCASE_FOLD[ch]
            if folded in UNICODE_TO_GEOS:
                out.append(UNICODE_TO_GEOS[folded])
        elif 0x20 <= ord(ch) <= 0x7E:
            b = ord(ch)
            # Only store literal byte when it does NOT conflict with cs locale mapping.
            # e.g. b=0x30 ('0') maps to 'é' in cs locale — storing it would corrupt the document.
            if b not in GEOS_TO_UNICODE:
                out.append(b)
        # else: unsupported character; drop silently
    return bytes(out)


def _build_ruler(right_margin: int = 0x0130, justification: int = 0x10) -> bytes:
    """Build a 26-byte ruler block (sym.inc .sizeof(ruler) = 26)."""
    ruler = bytearray(RULER_DATA_BYTES)               # 26 bytes, zero-filled
    struct.pack_into('<H', ruler, 0, 0)               # left_margin = 0
    struct.pack_into('<H', ruler, 2, right_margin)    # right_margin
    for k in range(0, 16, 2):                         # 8 tab pairs
        struct.pack_into('<H', ruler, 4 + k, right_margin)
    struct.pack_into('<H', ruler, 20, 0)              # paragraph_margin = 0
    ruler[22] = justification                          # justification
    ruler[23] = 0x00                                   # text color
    # bytes 24-25: reserved, left as zero
    return bytes(ruler)


_SECTOR_DATA = 254  # bytes of data per GEOS sector (256 - 2 link bytes)


def build_page_record(text: str, font_id: int = 76, style: int = 0) -> bytes:
    """Build a raw geoWrite page record (ruler + cardset + text, no sector padding)."""
    ruler   = bytes([ESC_RULER]) + _build_ruler()
    cardset = bytes([NEWCARDSET, font_id & 0xFF, (font_id >> 8) & 0xFF, style])
    return ruler + cardset + encode_text(text)


def _pack_record_sectors(data: bytes) -> tuple[bytes, int, int]:
    """
    Pack raw record data into 254-byte sectors (no link bytes, matching DOC-CVT format).

    Returns (packed_bytes, num_sectors, last_count) where:
      num_sectors = total 254-byte sectors used
      last_count  = valid bytes in last sector INCLUDING 2 would-be link bytes
                    (0 means the last sector is full = 254 valid data bytes)

    At least 4 trailing NUL bytes are guaranteed so the page-break heuristic
    in decode_text_stream can detect the boundary between records.
    """
    # Ensure at least 4 trailing NUL bytes for the page-break detector
    n_trail = 0
    for b in reversed(data):
        if b == 0:
            n_trail += 1
        else:
            break
    if n_trail < NUL_PAGE_BREAK_THRESHOLD:
        data = data + bytes(NUL_PAGE_BREAK_THRESHOLD - n_trail)

    size      = len(data)
    remaining = size % _SECTOR_DATA

    if remaining == 0:
        # All sectors are full
        num_sectors = size // _SECTOR_DATA
        last_count  = 0           # 254 + 2 = 256 ≡ 0 (mod 256)
        packed      = data
    else:
        # Pad last partial sector to 254 bytes
        num_sectors = size // _SECTOR_DATA + 1
        last_count  = remaining + 2
        packed      = data + bytes(_SECTOR_DATA - remaining)

    return packed, num_sectors, last_count


# ---------------------------------------------------------------------------
# DOC-CVT sector packing for import
# ---------------------------------------------------------------------------

def _build_doc_cvt(dir_entry: bytes, info_data: bytes,
                   all_records: list[bytes]) -> bytes:
    """Assemble a complete DOC-CVT byte string from its components."""
    assert len(dir_entry) == _DIR_ENTRY_SIZE
    assert len(info_data) == _INFO_SIZE

    # Padding to fill the header's 254-byte first block.
    # Documents use MAGIC_DOC (no \r before \x00).
    magic_bytes  = MAGIC_DOC
    padding_size = DOC_HEADER_SIZE - _DIR_ENTRY_SIZE - len(magic_bytes) - _INFO_SIZE - _VLIR_BLOCK_SIZE
    padding      = bytes(padding_size)

    # VLIR record block (254 bytes = 127 × 2-byte entries).
    # Encoding: (num_sectors, last_sector_count+2), where last_sector_count+2=0 means full sector.
    # Unused slots: (0x00, 0xFF) = "empty page" (matches real geoWrite documents).
    vlir_block = bytearray(b'\x00\xff' * 127)
    packed_data = bytearray()
    for i, rec in enumerate(all_records):
        packed, num_secs, last_count = _pack_record_sectors(rec)
        vlir_block[i * 2]     = num_secs & 0xFF
        vlir_block[i * 2 + 1] = last_count & 0xFF
        packed_data.extend(packed)

    out = bytearray()
    out.extend(dir_entry)
    out.extend(magic_bytes)
    out.extend(padding)
    out.extend(info_data)
    out.extend(vlir_block)
    out.extend(packed_data)
    return bytes(out)


# ---------------------------------------------------------------------------
# Public API: CVT -> TXT
# ---------------------------------------------------------------------------

def cvt_to_txt(cvt_path: str, txt_path: str) -> None:
    """Export a geoWrite CVT document to a plain UTF-8 text file."""
    with open(cvt_path, 'rb') as f:
        data = f.read()

    if _is_doc_cvt(data):
        _, num_records, data_offset = _parse_doc_cvt_header(data)
        record_data = data[data_offset:]
    elif _is_app_cvt(data):
        # Application CVT with 256-byte sectors and CBM link bytes.
        # Strip link bytes from each 256-byte sector and concatenate data.
        _, num_records, data_offset = _parse_app_cvt_header(data)
        raw = bytearray()
        pos = data_offset
        while pos + 256 <= len(data):
            sector = data[pos:pos + 256]
            pos += 256
            link_track = sector[0]
            link_count = sector[1]
            if link_track == 0:
                raw.extend(sector[2:2 + link_count])
                # end of current record chain; next sector starts next record
            else:
                raw.extend(sector[2:])
        record_data = bytes(raw)
    else:
        raise ValueError("Unrecognised CVT format (neither doc-CVT nor app-CVT)")

    pages = decode_text_stream(record_data)

    output = '\f'.join(pages)

    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"{len(pages)} page(s) exported → {txt_path}")


# ---------------------------------------------------------------------------
# Public API: TXT -> CVT
# ---------------------------------------------------------------------------

def txt_to_cvt(txt_path: str, template_cvt_path: str, out_cvt_path: str) -> None:
    """
    Convert UTF-8 plain text to a geoWrite CVT document.

    A template CVT is required to supply the info sector (icon, filename, etc.).
    Pages in the text file are separated by form-feed characters (\\f).
    """
    with open(txt_path, 'r', encoding='utf-8') as f:
        text = f.read()

    with open(template_cvt_path, 'rb') as f:
        template = f.read()

    if _is_doc_cvt(template):
        dir_entry, _, _ = _parse_doc_cvt_header(template)
        info_start = _DIR_ENTRY_SIZE + _MAGIC_SIZE + _ZEROS_SIZE
        info_data  = template[info_start:info_start + _INFO_SIZE]
    elif _is_app_cvt(template):
        if template[:len(MAGIC)] == MAGIC:
            hdr = len(MAGIC)
        else:
            hdr = len(MAGIC_OLD)
        info_sector = template[hdr:hdr + 256]
        info_data   = info_sector[2:]  # strip 2-byte CBM link
        dir_entry   = bytes(_DIR_ENTRY_SIZE)  # empty dir entry
    else:
        raise ValueError("Template is not a valid CVT file")

    out_name     = os.path.splitext(os.path.basename(out_cvt_path))[0]
    dir_entry    = _set_dir_filename(dir_entry, out_name)

    page_texts   = [p for p in text.split('\f') if p.strip()]
    page_records = [build_page_record(pt) for pt in page_texts]

    with open(out_cvt_path, 'wb') as f:
        f.write(_build_doc_cvt(dir_entry, info_data, page_records))

    print(f"{len(page_records)} page(s) imported → {out_cvt_path}")


# ---------------------------------------------------------------------------
# Markdown preprocessing
# ---------------------------------------------------------------------------

def md_to_pages(md_text: str) -> list[str]:
    """
    Convert Markdown text to a list of plain-text page strings.

    Each # heading starts a new page.  Images and bare URLs are dropped.
    """
    pages: list[str] = []
    current: list[str] = []

    def flush() -> None:
        joined = '\n'.join(current).strip()
        joined = re.sub(r'\n{3,}', '\n\n', joined)  # collapse excess blank lines
        if joined:
            pages.append(joined)
        current.clear()

    for line in md_text.splitlines():
        line = re.sub(r'!\[.*?\]\(.*?\)', '', line)               # strip images
        line = re.sub(r'^\s*\(https?://[^\)]*\)\s*$', '', line)   # strip bare URL lines
        line = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', line)     # links: keep label

        m = re.match(r'^#{1,6}\s+(.*)', line)
        if m:
            flush()
            heading = m.group(1).strip()
            if heading:
                current.append(heading)
        else:
            current.append(line.rstrip())

    flush()
    return [p for p in pages if p.strip()]


def md_to_cvt(md_path: str, template_cvt_path: str, out_cvt_path: str) -> None:
    """Convert a Markdown file to a geoWrite CVT document."""
    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    with open(template_cvt_path, 'rb') as f:
        template = f.read()

    if _is_doc_cvt(template):
        dir_entry, _, _ = _parse_doc_cvt_header(template)
        info_start = _DIR_ENTRY_SIZE + _MAGIC_SIZE + _ZEROS_SIZE
        info_data  = template[info_start:info_start + _INFO_SIZE]
    elif _is_app_cvt(template):
        hdr = len(MAGIC) if template[:len(MAGIC)] == MAGIC else len(MAGIC_OLD)
        info_sector = template[hdr:hdr + 256]
        info_data   = info_sector[2:]
        dir_entry   = bytes(_DIR_ENTRY_SIZE)
    else:
        raise ValueError("Template is not a valid CVT file")

    out_name     = os.path.splitext(os.path.basename(out_cvt_path))[0]
    dir_entry    = _set_dir_filename(dir_entry, out_name)

    page_texts   = md_to_pages(md_text)
    page_records = [build_page_record(pt) for pt in page_texts]

    with open(out_cvt_path, 'wb') as f:
        f.write(_build_doc_cvt(dir_entry, info_data, page_records))

    print(f"{len(page_records)} page(s) imported → {out_cvt_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description='geoWrite 2.1 CVT <-> TXT converter (Czech locale)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s export document.cvt document.txt
  %(prog)s import edited.txt original.cvt new_document.cvt
        """,
    )
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_exp = sub.add_parser('export', help='CVT → UTF-8 TXT')
    p_exp.add_argument('cvt', help='Input geoWrite CVT file')
    p_exp.add_argument('txt', help='Output plain text file (UTF-8)')

    p_imp = sub.add_parser('import', help='UTF-8 TXT → CVT')
    p_imp.add_argument('txt',      help='Input plain text file (UTF-8)')
    p_imp.add_argument('template', help='Template CVT file (supplies metadata/icon)')
    p_imp.add_argument('cvt',      help='Output geoWrite CVT file')

    p_imd = sub.add_parser('import-md', help='Markdown → CVT (one # heading = one page)')
    p_imd.add_argument('md',       help='Input Markdown file (UTF-8)')
    p_imd.add_argument('template', help='Template CVT file (supplies metadata/icon)')
    p_imd.add_argument('cvt',      help='Output geoWrite CVT file')

    args = parser.parse_args()

    if args.cmd == 'export':
        cvt_to_txt(args.cvt, args.txt)
    elif args.cmd == 'import':
        txt_to_cvt(args.txt, args.template, args.cvt)
    else:
        md_to_cvt(args.md, args.template, args.cvt)


if __name__ == '__main__':
    main()
