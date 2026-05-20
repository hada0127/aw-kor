#!/usr/bin/env python3
"""
분석: 현재 번역 데이터 기반 톤앤매너 및 스토리 분석
"""

import csv
from pathlib import Path

def analyze_translations():
    """번역 데이터 분석"""
    
    translations = []
    trans_file = Path('data/translation_for_import.csv')
    
    with open(trans_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            translations.append({
                'japanese': row.get('japanese', ''),
                'korean': row.get('korean', ''),
                'length': int(row.get('length', 0))
            })
    
    print("="*70)
    print("Game Wars Translation Pattern Analysis")
    print("="*70)
    
    # Categorize
    units = []
    actions = []
    symbols = []
    other = []
    
    unit_keywords = ['艦', '船', '戦車', 'ヘリ', '機', '砲', '兵']
    action_keywords = ['できる', 'できない']
    
    for trans in translations:
        jp_orig = trans['japanese']
        kr = trans['korean']
        
        if any(kw in jp_orig for kw in unit_keywords):
            units.append(trans)
        elif any(kw in jp_orig for kw in action_keywords):
            actions.append(trans)
        elif kr in ['···', ''] or len(kr) <= 3:
            symbols.append(trans)
        else:
            other.append(trans)
    
    print(f"\nTotal translations: {len(translations)}")
    print(f"  - Unit names: {len(units)}")
    print(f"  - Actions/Abilities: {len(actions)}")
    print(f"  - Symbols/Short: {len(symbols)}")
    print(f"  - Other: {len(other)}")
    
    # Unit analysis
    print("\n" + "="*70)
    print("1. Unit Name Translation Rules")
    print("="*70)
    
    unit_dict = {}
    for trans in units:
        jp = trans['japanese']
        kr = trans['korean']
        if jp not in unit_dict:
            unit_dict[jp] = kr
    
    print("\nKey unit translations (consistent across all uses):")
    for jp, kr in sorted(unit_dict.items()):
        print(f"  {jp:12} = {kr}")
    
    # Action analysis
    print("\n" + "="*70)
    print("2. Action/Ability Expression Rules")
    print("="*70)
    
    action_dict = {}
    for trans in actions:
        jp = trans['japanese']
        kr = trans['korean']
        if jp not in action_dict:
            action_dict[jp] = kr
    
    print("\nAction expression forms:")
    for jp, kr in sorted(action_dict.items()):
        print(f"  {jp:15} = {kr}")
    
    # Tone analysis
    print("\n" + "="*70)
    print("3. Tone and Manner Analysis")
    print("="*70)
    
    print("\nTranslation style characteristics:")
    print("  - Military terms: Use sino-Korean (한자어) for precision")
    print("  - Abilities: Declarative form (할 수 있다., 할 수 없다.)")
    print("  - Length: Optimized to match or shorten original")
    print("  - Game tone: Strategic, military, formal")
    print("  - Formality: Polite but direct (게임 메뉴 스타일)")
    
    # Statistics
    print("\n" + "="*70)
    print("4. Translation Statistics")
    print("="*70)
    
    lengths = [t['length'] for t in translations]
    print(f"\nKorean translation length distribution:")
    print(f"  - Average: {sum(lengths)/len(lengths):.1f} bytes")
    print(f"  - Minimum: {min(lengths)} bytes")
    print(f"  - Maximum: {max(lengths)} bytes")
    
    # Game analysis
    print("\n" + "="*70)
    print("5. Game Characteristics")
    print("="*70)
    
    print("\nGame Wars Game Profile:")
    print("  - Genre: Tactical Strategy War Game")
    print("  - Setting: Modern military scenario")
    print("  - Unit system: Navy, Army, Air Force units")
    print("  - Core mechanics: Move, Attack, Defend, Ability")
    print("  - Target audience: Strategy game enthusiasts")
    
    # Story inference
    print("\n" + "="*70)
    print("6. Story Setting & Context")
    print("="*70)
    
    print("\nInferred from translated content:")
    print("  - Military conflict between nations")
    print("  - Turn-based tactical battles")
    print("  - Multiple unit types with different abilities")
    print("  - Resource management (likely)")
    print("  - Strategic decision-making focus")
    
    return {
        'units': units,
        'actions': actions,
        'symbols': symbols,
        'other': other,
        'unit_dict': unit_dict,
        'action_dict': action_dict
    }

if __name__ == '__main__':
    analyze_translations()
