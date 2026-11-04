/*
 * 1편 이름 조합 코드 이미지 링크 스크립트 (PLAN B T3, D8).
 * 단일 할당 섹션 .image 를 ROM 버스 주소 0x08F77800(파일 0xF77800, 2편 nc_image 끝 바로 뒤)에 둔다.
 * 상한 8,192B(0xF79800 까지)는 build_image_p1.py 가 검사한다. nc_dense 는 2편과 공유하는 이미지 밖 절대 심볼
 * (파일 0xF70000, 22,344B)이다. ld.lld 로 링크한다(이 PC 에는 GNU binutils 가 없다 — plan_B_approval).
 */
OUTPUT_FORMAT("elf32-littlearm")
OUTPUT_ARCH(arm)
ENTRY(nc1_tramp_press)

nc_dense = 0x08F70000;

SECTIONS
{
  . = 0x08F77800;
  .image : ALIGN(4) { *(.text .text.*) *(.rodata .rodata.*) }
  .ARM.attributes 0 : { *(.ARM.attributes) }
  /DISCARD/ : { *(.ARM.exidx .ARM.exidx.*) *(.comment) *(.note.GNU-stack) }
}
