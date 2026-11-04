/*
 * 1편 이름 입력 두벌식 조합 — 표시 헬퍼 (PLAN B T2b, D2·D3·D5).
 *
 * 조합 상태 전이는 Part 2 core.c(nc_press/nc_confirm/nc_backspace)를 그대로 쓰고, 이 파일은 1편 화면에 필요한
 * 순수 헬퍼만 둔다: 빈칸 패딩, 확장 한자표 조회, 이름 화면 사전(compact) 캐시 조회, VRAM 타일 업로드.
 * 게임 함수 호출·전역 쓰기·나눗셈 없음(core.c 와 같은 제약). VRAM 쓰기는 16비트 저장만 쓴다.
 *
 * 같은 소스를 ROM(Thumb-1, 절대 주소 = p1_config.h)과 host 테스트(-DNC1_HOST: 주소 대신 extern 포인터)에서
 * 컴파일한다. host 쪽 포인터·표 정의는 테스트가 따로 준다.
 *
 * 1편 obj(0x80 블록, §3.1): +0x2C slot[max] u16 BE · +0x61 len(= C + active) · +0x62 max(6/8) ·
 *   +0x70 active · +0x71 L(0xFF 없음) · +0x72 V(0xFF 없음) · +0x73 T · +0x74..+0x7F 0.
 *
 * 사전 캐시(T0 NR-1, cache_base 0x02010AD4, bank 1):
 *   +cache_count_off u16 = 코드 수, +cache_list_off + 2i = 코드 i(바이트 hi,lo = SJIS 순서),
 *   +cache_tile_off u16 = tile_start. 코드 i 의 타일 = tile_start + 2i(top), +1(bottom).
 * VRAM 타일 t = vram_charblock + t*32 (4bpp 8x8, 리맵 없음 NR-2).
 * 확장 한자표 엔트리 6B = [code BE][top u16 LE][bot u16 LE]. 한글/자모는 top bit15, 글리프 = kor_base + (idx&0x7FFF)*32.
 */
#include <stdint.h>
#include "p1_config.h"

#if NC1_PAL_REMAP
#error "palette remap is not implemented (T0 NR-2: loader copies raw tiles)"
#endif
#if !NC1_CACHE_CODE_BE
#error "dictionary list byte order other than SJIS (hi,lo) is not implemented"
#endif
#if NC1_PLACEHOLDER_COUNT != 8
#error "nc1_preview_codes assumes 8 placeholders (mode1 max)"
#endif

#define OFF_SLOT   0x2Cu
#define OFF_LEN    0x61u
#define OFF_MAX    0x62u
#define OFF_TAIL   0x70u
#define SPACE_HI   0x81u
#define SPACE_LO   0x40u
#define PREVIEW_MAX 8u          /* placeholder 수 = mode1 max */
#define KOREAN_MARKER 0x8000u

extern const uint8_t nc1_host_tab[];        /* 33 x {u8 jamo index, u8 0, u16 host LE} (grid_p1.inc) */
extern const uint8_t nc1_placeholders[];    /* 8 x u16 LE (grid_p1.inc) */

#ifdef NC1_HOST
extern const uint8_t *nc1_h_tbl_start;
extern const uint8_t *nc1_h_tbl_end;
extern const uint8_t *nc1_h_kor;
extern const uint8_t *nc1_h_cache;
extern volatile uint16_t *nc1_h_vram;
#define TBL_START nc1_h_tbl_start
#define TBL_END   nc1_h_tbl_end
#define KOR       nc1_h_kor
#define CACHE     nc1_h_cache
#define VRAM      nc1_h_vram
#else
#define TBL_START ((const uint8_t *)NC1_TBL_START)
#define TBL_END   ((const uint8_t *)NC1_TBL_END)
#define KOR       ((const uint8_t *)NC1_KOR_BASE)
#define CACHE     ((const uint8_t *)(NC1_CACHE_BASE))
#define VRAM      ((volatile uint16_t *)NC1_VRAM_CHARBLOCK)
#endif

void nc1_pad(uint8_t *obj);
void nc1_tail_init(uint8_t *obj);
unsigned nc1_korean_tiles(unsigned code, unsigned *top, unsigned *bot);
int nc1_cache_tile(unsigned code);
void nc1_upload(unsigned vram_tile, unsigned top, unsigned bot);
void nc1_upload_hosts(void);
void nc1_display_init(uint8_t *obj);
unsigned nc1_preview_codes(const uint8_t *obj, uint8_t out[16]);

static unsigned max_slots(const uint8_t *obj)
{
    unsigned max = obj[OFF_MAX];
    return max > PREVIEW_MAX ? PREVIEW_MAX : max;
}

static unsigned slot_code(const uint8_t *obj, unsigned i)
{
    return ((unsigned)obj[OFF_SLOT + 2u * i] << 8) | obj[OFF_SLOT + 2u * i + 1u];
}

/* D5 불변식: slot[len..max) = 81 40. +0x2C + max*2 밖은 쓰지 않는다(max 는 8 로 자른다). */
void nc1_pad(uint8_t *obj)
{
    unsigned i, max = max_slots(obj);
    for (i = obj[OFF_LEN]; i < max; i++) {
        obj[OFF_SLOT + 2u * i] = SPACE_HI;
        obj[OFF_SLOT + 2u * i + 1u] = SPACE_LO;
    }
}

/* D3 tail: +70 active 0, +71 L FF, +72 V FF, +73 T 0, +74..+7F 0. */
void nc1_tail_init(uint8_t *obj)
{
    unsigned i;
    for (i = 0; i < 16u; i++)
        obj[OFF_TAIL + i] = 0;
    obj[OFF_TAIL + 1u] = 0xFF;
    obj[OFF_TAIL + 2u] = 0xFF;
}

/* 확장 한자표에서 code 를 찾는다. bit15(한글/자모) 엔트리면 top·bot = 글리프 타일 index(&0x7FFF), 1 반환. */
unsigned nc1_korean_tiles(unsigned code, unsigned *top, unsigned *bot)
{
    const uint8_t *p = TBL_START;
    const uint8_t *end = TBL_END;
    unsigned hi = (code >> 8) & 0xFFu, lo = code & 0xFFu;

    for (; p + 6 <= end; p += 6) {
        if (p[0] == hi && p[1] == lo) {
            unsigned t = p[2] | ((unsigned)p[3] << 8);
            unsigned b = p[4] | ((unsigned)p[5] << 8);
            if (!(t & KOREAN_MARKER))
                return 0;
            *top = t & 0x7FFFu;
            *bot = b & 0x7FFFu;
            return 1;
        }
    }
    return 0;
}

/* 이름 화면 사전 bank 목록에서 code 의 top 타일 번호. 없으면 -1. */
int nc1_cache_tile(unsigned code)
{
    const uint8_t *cache = CACHE;
    unsigned count = cache[NC1_CACHE_COUNT_OFF] | ((unsigned)cache[NC1_CACHE_COUNT_OFF + 1u] << 8);
    unsigned start = cache[NC1_CACHE_TILE_OFF] | ((unsigned)cache[NC1_CACHE_TILE_OFF + 1u] << 8);
    const uint8_t *list = cache + NC1_CACHE_LIST_OFF;
    unsigned hi = (code >> 8) & 0xFFu, lo = code & 0xFFu;
    unsigned i;

    for (i = 0; i < count; i++)
        if (list[2u * i] == hi && list[2u * i + 1u] == lo)
            return (int)(start + 2u * i);
    return -1;
}

static void copy_tile(volatile uint16_t *dst, const uint8_t *src)
{
    unsigned i;
    for (i = 0; i < 16u; i++)
        dst[i] = (uint16_t)(src[2u * i] | ((unsigned)src[2u * i + 1u] << 8));
}

/* KOR_BASE 글리프 top/bot(32B 씩)를 VRAM 타일 vram_tile, vram_tile+1 로 16비트 저장 32회. */
void nc1_upload(unsigned vram_tile, unsigned top, unsigned bot)
{
    volatile uint16_t *dst = VRAM + vram_tile * 16u;
    copy_tile(dst, KOR + top * 32u);
    copy_tile(dst + 16, KOR + bot * 32u);
}

/* 그리드 자모 라벨: host 코드의 사전 타일에 자모 타일(jamo_first_tile + 2*index, +1)을 한 번 복사. */
void nc1_upload_hosts(void)
{
    unsigned i;
    for (i = 0; i < NC1_HOST_COUNT; i++) {
        const uint8_t *e = nc1_host_tab + 4u * i;
        unsigned host = e[2] | ((unsigned)e[3] << 8);
        int tile = nc1_cache_tile(host);
        if (tile >= 0)
            nc1_upload((unsigned)tile, NC1_JAMO_FIRST_TILE + 2u * e[0], NC1_JAMO_FIRST_TILE + 2u * e[0] + 1u);
    }
}

/* H4(D1): tail 초기화 + host 자모 업로드. */
void nc1_display_init(uint8_t *obj)
{
    nc1_tail_init(obj);
    nc1_upload_hosts();
}

/*
 * H5 미리보기 코드: 칸 i(0..min(max,8)-1)마다 out[2i..2i+1] = 그릴 코드(BE).
 * i < len 이고 한글(확장표 bit15)이면 placeholder[i] 의 사전 타일에 그 글리프를 올리고 placeholder 를 낸다.
 * 그 외(숫자·기호·공백·legacy 가나, 또는 placeholder 가 사전에 없을 때)는 slot 바이트 그대로. 반환 = 칸 수.
 */
unsigned nc1_preview_codes(const uint8_t *obj, uint8_t out[16])
{
    unsigned i, n = max_slots(obj), len = obj[OFF_LEN];

    for (i = 0; i < n; i++) {
        unsigned code = slot_code(obj, i);
        unsigned top, bot;
        if (i < len && nc1_korean_tiles(code, &top, &bot)) {
            unsigned ph = nc1_placeholders[2u * i] | ((unsigned)nc1_placeholders[2u * i + 1u] << 8);
            int tile = nc1_cache_tile(ph);
            if (tile >= 0) {
                nc1_upload((unsigned)tile, top, bot);
                code = ph;
            }
        }
        out[2u * i] = (uint8_t)(code >> 8);
        out[2u * i + 1u] = (uint8_t)code;
    }
    return n;
}
