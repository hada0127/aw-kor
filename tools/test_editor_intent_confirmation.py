"""Restore a lost editor receipt without replacing protected source prose."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import editor_storage

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('dialogue_intent_editor',ROOT/'tools/dialogue_editor/server.py')
DE=importlib.util.module_from_spec(spec);spec.loader.exec_module(DE)

class ProtectedIntentConfirmation(unittest.TestCase):
    def test_only_explicit_confirmation_of_matching_source_restores_receipt(self):
        for is_bteam in [False,True]:
            for source in ['새 문구','다른 원문',None]:
                with self.subTest(bteam=is_bteam,source=source), tempfile.TemporaryDirectory(dir=ROOT/'temp') as directory:
                    root=Path(directory)
                    (root/'data').mkdir();(root/'temp').mkdir()
                    paths={name:root/name for name in ['DIALOGUE_PATH','GROUPS_PATH','OVERRIDES_PATH','ADDRESS_TEXT_OVERRIDES_TSV','EDITOR_INTENTS_PATH']}
                    address='0x00DC3C63'
                    paths['DIALOGUE_PATH'].write_text(json.dumps({'lines':[{'address':address,'ko':'새 문구'}]}))
                    paths['GROUPS_PATH'].write_text('{"groups":[]}')
                    paths['OVERRIDES_PATH'].write_text(json.dumps({address:source} if source is not None else {}))
                    paths['ADDRESS_TEXT_OVERRIDES_TSV'].write_text('address\ttext\n'+address+'\t새 문구\n')
                    before={p:p.read_bytes() for k,p in paths.items() if k!='EDITOR_INTENTS_PATH'}
                    handler=object.__new__(DE.Handler)
                    with patch.multiple(DE,**paths), patch.object(editor_storage,'ROOT',root), patch.object(DE,'is_bteam',return_value=is_bteam), patch.object(handler,'_save_line',return_value={'ok':True,'address':address,'ko':'새 문구'}):
                        result=handler._save_lines({'lines':[{'address':address,'ko':'새 문구'}]})
                        self.assertEqual(result['saved'],0);self.assertEqual(result['confirmed'],0)
                        self.assertFalse(paths['EDITOR_INTENTS_PATH'].exists())
                        result=handler._save_lines({'lines':[{'address':address,'ko':'새 문구','confirm_current':True}]})
                        self.assertEqual(result['saved'],0)
                        self.assertEqual(result['confirmed'],int(source=='새 문구'))
                        if source=='새 문구':
                            self.assertEqual(json.loads(paths['EDITOR_INTENTS_PATH'].read_text()),{address:DE.B.editor_text_digest('새 문구')})
                            repeated=handler._save_lines({'lines':[{'address':address,'ko':'새 문구','confirm_current':True}]})
                            self.assertEqual(repeated['confirmed'],0)
                        else:self.assertFalse(paths['EDITOR_INTENTS_PATH'].exists())
                        self.assertEqual(before,{p:p.read_bytes() for p in before})

if __name__=='__main__':unittest.main()
