import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path('tools').resolve()))
import build_korean_full as B
B.P.ROM='/home/taro1/project/aw-kor/original/Game Boy Wars Advance 1+2 (Japan).gba'
names=['test_pair_title_fit_contract','test_qa_text_fit_cli',
 'test_part2_mission_title_fit.MissionTitleFitTests.test_builder_encoding_and_actual_direct_writer_keep_title_pairs',
 'test_part2_mission_title_fit.MissionTitleFitTests.test_title_encoder_preserves_digits_letters_signs_and_full_spacing']
r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
sys.exit(not r.wasSuccessful())
