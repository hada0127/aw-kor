/*
 * 2편 맵 에디터 이름 입력 두벌식 조합 코어 (PLAN-v5 §1.3·§1.4·§1.6, T2).
 *
 * 순수 로직만 있다: 게임 함수 호출·전역 쓰기·나눗셈·구조체 복사 없음. 상태는 obj 버퍼뿐이다.
 * 같은 소스를 ROM(Thumb, nc_dense = 0x08F70000 절대 심볼)과 host 테스트(nc_dense = 실제 배열)에서
 * 그대로 컴파일한다. 전이 계약은 tools/hangul_compose.py(Composer)와 같다.
 *
 * obj 배치(0x80B 객체):
 *   +0x2C slot[8]  코드 u16 BE. slot[0..C) = 확정 코드, active 면 slot[C] = 현재 표시 코드.
 *   +0x61 len      = C + active. len < 8 이면 slot[len] = 00 00.
 *   +0x70 active   0/1
 *   +0x71 L        초성 인덱스, 없음 0xFF
 *   +0x72 V        모음 인덱스, 없음 0xFF
 *   +0x73 T        종성 인덱스 0..27
 *   +0x74..+0x7F   0 (쓰지 않음)
 * 반환: 0 = 수락(상태 갱신), 1 = 거부(obj 불변).
 */
#include <stdint.h>
#include "tables.h"

extern const uint16_t nc_dense[11172];   /* (L*21+V)*28+T → 2350 코드, 없음 0 */

#define OFF_SLOT   0x2Cu
#define OFF_LEN    0x61u
#define OFF_ACTIVE 0x70u
#define OFF_L      0x71u
#define OFF_V      0x72u
#define OFF_T      0x73u

int nc_press(uint8_t *obj, uint16_t cell);
int nc_confirm(uint8_t *obj);
int nc_backspace(uint8_t *obj);

static unsigned lookup(unsigned l, unsigned v, unsigned t)
{
    return nc_dense[(l * 21u + v) * 28u + t];
}

static void put_slot(uint8_t *obj, unsigned i, unsigned code)
{
    obj[OFF_SLOT + 2u * i] = (uint8_t)(code >> 8);
    obj[OFF_SLOT + 2u * i + 1u] = (uint8_t)code;
}

/*
 * 새 상태를 검사한 뒤 한 번에 기록한다(종성 이동 등 두 슬롯 변경도 원자적).
 * base: 기존 확정 개수(지우기면 C-1), n: base 뒤에 붙일 확정 코드 수(0..2) code1/code2,
 * act/l/v/t: 새 active. 슬롯 초과 또는 완성 후보가 표에 없으면 1(아무것도 쓰지 않음).
 */
static int commit(uint8_t *obj, unsigned base, unsigned n, unsigned code1, unsigned code2,
                  unsigned act, unsigned l, unsigned v, unsigned t)
{
    unsigned c = base + n;
    unsigned len = c + act;
    unsigned shown = 0;

    if (len > NC_MAX_SLOTS)
        return 1;
    if (act) {
        if (l != NC_NONE && v != NC_NONE) {
            shown = lookup(l, v, t);
            if (shown == 0)
                return 1;
        } else {
            shown = (l != NC_NONE) ? NC_L_CODE[l] : NC_V_CODE[v];
        }
    } else {
        l = NC_NONE;
        v = NC_NONE;
        t = 0;
    }
    if (n >= 1)
        put_slot(obj, base, code1);
    if (n >= 2)
        put_slot(obj, base + 1u, code2);
    if (act)
        put_slot(obj, c, shown);
    if (len < NC_MAX_SLOTS)
        put_slot(obj, len, 0);
    obj[OFF_LEN] = (uint8_t)len;
    obj[OFF_ACTIVE] = (uint8_t)act;
    obj[OFF_L] = (uint8_t)l;
    obj[OFF_V] = (uint8_t)v;
    obj[OFF_T] = (uint8_t)t;
    return 0;
}

static unsigned compound_vowel(unsigned first, unsigned second)
{
    unsigned i;
    for (i = 0; i < NC_CV_COUNT; i++)
        if (NC_CV_FIRST[i] == first && NC_CV_SECOND[i] == second)
            return NC_CV_RESULT[i];
    return NC_NONE;
}

static unsigned final_cluster(unsigned first_t, unsigned second_l)
{
    unsigned i;
    for (i = 0; i < NC_FC_COUNT; i++)
        if (NC_FC_FIRST[i] == first_t && NC_FC_SECOND_L[i] == second_l)
            return NC_FC_RESULT[i];
    return NC_NONE;
}

/* 겹받침이면 인덱스, 아니면 NC_FC_COUNT. */
static unsigned cluster_index(unsigned t)
{
    unsigned i;
    for (i = 0; i < NC_FC_COUNT; i++)
        if (NC_FC_RESULT[i] == t)
            break;
    return i;
}

/* 복합 모음이면 인덱스, 아니면 NC_CV_COUNT. */
static unsigned compound_index(unsigned v)
{
    unsigned i;
    for (i = 0; i < NC_CV_COUNT; i++)
        if (NC_CV_RESULT[i] == v)
            break;
    return i;
}

/* 확정 코드 뒤에 코드 하나(공백·리터럴)를 붙인다. 미완성 active 는 거부, 완성은 먼저 확정. */
static int append_code(uint8_t *obj, unsigned c, unsigned act, unsigned l, unsigned v,
                       unsigned t, unsigned code)
{
    if (!act)
        return commit(obj, c, 1, code, 0, 0, 0, 0, 0);
    if (l == NC_NONE || v == NC_NONE)
        return 1;
    return commit(obj, c, 2, lookup(l, v, t), code, 0, 0, 0, 0);
}

int nc_press(uint8_t *obj, uint16_t cell)
{
    unsigned len = obj[OFF_LEN];
    unsigned act = obj[OFF_ACTIVE] ? 1u : 0u;
    unsigned l = obj[OFF_L], v = obj[OFF_V], t = obj[OFF_T];
    unsigned c = len - act;
    unsigned jl = NC_NONE, jv = NC_NONE;
    unsigned i, cur, comb;

    for (i = 0; i < NC_L_COUNT; i++)
        if (NC_L_CODE[i] == cell)
            jl = i;
    for (i = 0; i < NC_SEL_V_COUNT; i++)
        if (NC_V_CODE[NC_SEL_V[i]] == cell)
            jv = NC_SEL_V[i];
    if (jl == NC_NONE && jv == NC_NONE)          /* 공백 8140 과 숫자·문장부호 리터럴 */
        return append_code(obj, c, act, l, v, t, cell);

    if (!act)
        return commit(obj, c, 0, 0, 0, 1, jl, jv, 0);
    if (l == NC_NONE || v == NC_NONE) {          /* 미완성 active */
        if (jl != NC_NONE)
            return 1;                            /* incomplete */
        if (l != NC_NONE)
            return commit(obj, c, 0, 0, 0, 1, l, jv, 0);
        comb = compound_vowel(v, jv);
        if (comb == NC_NONE)
            return 1;                            /* invalid_transition */
        return commit(obj, c, 0, 0, 0, 1, NC_NONE, comb, 0);
    }
    cur = lookup(l, v, t);
    if (jl != NC_NONE) {                         /* 완성 + 자음 */
        if (t) {
            comb = final_cluster(t, jl);
            if (comb != NC_NONE)
                return commit(obj, c, 0, 0, 0, 1, l, v, comb);
        } else if (NC_T_OF_L[jl]) {
            return commit(obj, c, 0, 0, 0, 1, l, v, NC_T_OF_L[jl]);
        }
        return commit(obj, c, 1, cur, 0, 1, jl, NC_NONE, 0);
    }
    if (!t) {                                    /* 완성(받침 없음) + 모음 */
        comb = compound_vowel(v, jv);
        if (comb != NC_NONE)
            return commit(obj, c, 0, 0, 0, 1, l, comb, 0);
        return commit(obj, c, 1, cur, 0, 1, NC_NONE, jv, 0);
    }
    /* 종성 이동: 앞 음절과 새 음절을 모두 조회한 뒤 두 슬롯을 함께 적용 */
    i = cluster_index(t);
    {
        unsigned rest = (i < NC_FC_COUNT) ? NC_FC_FIRST[i] : 0u;
        unsigned moving = (i < NC_FC_COUNT) ? NC_FC_SECOND_L[i] : NC_L_OF_T[t];
        unsigned front = lookup(l, v, rest);
        if (front == 0 || lookup(moving, jv, 0) == 0)
            return 1;                            /* not_in_2350 */
        return commit(obj, c, 1, front, 0, 1, moving, jv, 0);
    }
}

int nc_confirm(uint8_t *obj)
{
    unsigned len = obj[OFF_LEN];
    unsigned act = obj[OFF_ACTIVE] ? 1u : 0u;
    unsigned l = obj[OFF_L], v = obj[OFF_V], t = obj[OFF_T];

    if (!act)
        return 0;
    if (l == NC_NONE || v == NC_NONE)
        return 1;                                /* incomplete: 자모 유지 */
    return commit(obj, len - 1u, 1, lookup(l, v, t), 0, 0, 0, 0, 0);
}

int nc_backspace(uint8_t *obj)
{
    unsigned len = obj[OFF_LEN];
    unsigned act = obj[OFF_ACTIVE] ? 1u : 0u;
    unsigned l = obj[OFF_L], v = obj[OFF_V], t = obj[OFF_T];
    unsigned c = len - act;
    unsigned i;

    if (!act) {
        if (c == 0)
            return 1;                            /* empty */
        return commit(obj, c - 1u, 0, 0, 0, 0, 0, 0, 0);
    }
    if (t) {
        i = cluster_index(t);
        return commit(obj, c, 0, 0, 0, 1, l, v, (i < NC_FC_COUNT) ? NC_FC_FIRST[i] : 0u);
    }
    if (v != NC_NONE) {
        i = compound_index(v);
        if (i < NC_CV_COUNT)
            return commit(obj, c, 0, 0, 0, 1, l, NC_CV_FIRST[i], 0);
    }
    if (l != NC_NONE && v != NC_NONE)
        return commit(obj, c, 0, 0, 0, 1, l, NC_NONE, 0);
    return commit(obj, c, 0, 0, 0, 0, 0, 0, 0);
}
