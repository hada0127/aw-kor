/*
 * 2편 이름 조합 코드 이미지 링크 스크립트 (PLAN-v5 §1.6·§1.8, T2).
 * 단일 할당 섹션 .image 를 ROM 버스 주소 0x08F75800(파일 0xF75800)에 둔다. 상한 8,192B 는
 * build_image.py 가 검사한다. nc_dense 는 이미지 밖의 절대 심볼(파일 0xF70000, 22,344B)이다.
 */
OUTPUT_FORMAT("elf32-littlearm")
OUTPUT_ARCH(arm)
ENTRY(nc_tramp_press)

nc_dense = 0x08F70000;

SECTIONS
{
  . = 0x08F75800;
  .image : ALIGN(4) { *(.text .text.*) *(.rodata .rodata.*) }
  .ARM.attributes 0 : { *(.ARM.attributes) }
  /DISCARD/ : { *(.ARM.exidx .ARM.exidx.*) *(.comment) *(.note.GNU-stack) }
}
