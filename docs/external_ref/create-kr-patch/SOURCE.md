# 출처 및 라이선스 (External Reference)

이 디렉토리(`docs/external_ref/create-kr-patch/`)의 모든 파일은 외부 공개 레포에서
**원문 그대로 보존**한 참고 자료다. 우리 프로젝트의 산출물이 아니다.

- **레포**: [mcpads/create-retro-game-kr-patch](https://github.com/mcpads/create-retro-game-kr-patch)
- **설명**: 레트로 게임 한글 패치 제작 전 파이프라인 Claude Code 스킬 (methodology only — ROM/저작 자산 미포함)
- **default branch**: `main`
- **라이선스**: **MIT License** (레포 LICENSE 파일 기준)
- **가져온 시점**: 2026-06-23 (레포 마지막 push: 2026-06-17)
- **가져온 방법**: `gh api` 트리 조회 + `raw.githubusercontent.com` 원문 다운로드

## 가져온 파일

| 경로 | 원본 경로 (레포 내) |
|------|---------------------|
| `SKILL.md` | `skills/create-kr-patch/SKILL.md` |
| `strategy/*.md` (13종) | `skills/create-kr-patch/references/strategy/*.md` |
| `platforms/snes.md` | `skills/create-kr-patch/references/platforms/snes.md` |
| `platforms/megadrive.md` | `skills/create-kr-patch/references/platforms/megadrive.md` |
| `LICENSE` | `LICENSE` (MIT) |

> strategy 문서는 작업 지시상 "12종"으로 언급되었으나 레포 실제 보유분은 **13종**이라
> 전부 가져왔다(`tips.md` 포함). 플랫폼 문서는 GBA가 없어 가장 구조가 유사한
> 카트리지 ROM 2종(SNES 65816 / 메가드라이브 68000)만 받았다.

## 사용 원칙
- 원문은 수정하지 않는다(보존 목적). 우리 프로젝트 적용 분석은 상위 폴더
  `../CREATE_KR_PATCH_NOTES.md`에 별도로 정리한다.
- MIT 라이선스이므로 재사용·인용 가능하나, 인용 시 출처를 표기한다.
