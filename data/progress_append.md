
---
## 2026-05-22 (13) Gemini SJIS→slot mapping

### Mapping Strategy
The mapping is implemented via a Lookup Table (LUT) in ROM.
- **SJIS Table Location**: 0x08BE717A
- **Font Base**: 0x08B974D0
- **Formula**: `slot = index_in_sjis_table(sjis_char)`
- **Font Offset**: `ROM_Address = 0x08B974D0 + slot * 32`
- **Glyph Format**: 8x8, 4bpp (32 bytes per glyph).

### 30-Sample Verification Table
| SJIS Code | Char | Table Index / Slot |
|-----------|------|--------------------|
| 0x8250    | ０   | 0                  |
| 0x8251    | １   | 1                  |
| 0x8252    | ２   | 2                  |
| 0x8253    | ３   | 3                  |
| 0x8254    | ４   | 4                  |
| 0x8255    | ５   | 5                  |
| 0x8256    | ６   | 6                  |
| 0x8257    | ７   | 7                  |
| 0x8258    | ８   | 8                  |
| 0x8341    | ア   | 9                  |
| 0x8343    | イ   | 10                 |
| 0x8345    | ウ   | 11                 |
| 0x8347    | エ   | 12                 |
| 0x8349    | オ   | 13                 |
| 0x834A    | カ   | 14                 |
| 0x834C    | キ   | 15                 |
| 0x834E    | ク   | 16                 |
| 0x8350    | ケ   | 17                 |
| 0x8352    | コ   | 18                 |
| 0x8354    | サ   | 19                 |
| 0x8356    | シ   | 20                 |
| 0x8358    | ス   | 21                 |
| 0x835A    | セ   | 22                 |
| 0x835C    | ソ   | 23                 |
| 0x835E    | タ   | 24                 |
| 0x8373    | ピ   | 95                 |
| 0x88EA    | 一   | 108                |
| 0x89EF    | 会   | 110                |
| 0x93FA    | 日   | 101                |
| 0x8D91    | 国   | 111                |

*(Note: Table contains zeros for some indices; these slots are reserved or unused.)*

### Caveats
- The dialogue system uses a dynamic cache in VRAM (slots 291-314).
- The mapping from SJIS to the Main Font Slot (0-7618) is constant.
- For Korean translation:
  1. Append Korean font to ROM.
  2. Redirect SJIS chars to Korean font slots.
  3. Modify the font-base literal at 0x08B11B74 (and others) to point to the new font.
