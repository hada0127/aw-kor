"""Accepted artifacts survive validation and publication failures."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from build_publication import BuildPublication
from editor_storage import atomic_write_bytes
from localization_evidence import write_build_receipt

ROOT=Path(__file__).resolve().parents[1]


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'temp',prefix='publication-test-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def accepted(self):
        files={self.root/name:('previous '+name).encode() for name in
               ('full.gba','final.gba','title.gba','map.json','manifest.json','receipt.json')}
        for path,payload in files.items():path.write_bytes(payload)
        return files

    def test_late_validator_cannot_replace_outputs_or_metadata(self):
        previous=self.accepted()
        with self.assertRaisesRegex(AssertionError,'late B-team'):
            with BuildPublication(self.root) as staged:
                staged.path('candidate.gba').write_bytes(b'new candidate')
                staged.path('map.json').write_bytes(b'new map')
                raise AssertionError('late B-team validation failure')
        self.assertTrue(all(path.read_bytes()==old for path,old in previous.items()))
        self.assertFalse(list(self.root.glob('build-stage-*')))

    def test_partial_publication_failure_restores_existing_bundle(self):
        previous=self.accepted();calls=[]
        def writer(path,data):
            calls.append(Path(path))
            if len(calls)==3:raise OSError('injected replacement failure')
            atomic_write_bytes(path,data)
        with BuildPublication(self.root) as staged,patch('build_publication.atomic_write_bytes',side_effect=writer):
            with self.assertRaisesRegex(OSError,'injected'):
                staged.publish([(path,b'new validated bytes') for path in previous])
        self.assertTrue(all(path.read_bytes()==old for path,old in previous.items()))

    def test_partial_publication_failure_removes_only_newly_created_file(self):
        new=self.root/'new.gba';old=self.root/'old.gba';old.write_bytes(b'accepted')
        calls=[]
        def writer(path,data):
            calls.append(path)
            if len(calls)==2:raise OSError('injected')
            atomic_write_bytes(path,data)
        with BuildPublication(self.root) as staged,patch('build_publication.atomic_write_bytes',side_effect=writer):
            with self.assertRaises(OSError):staged.publish([(new,b'new'),(old,b'changed')])
        self.assertFalse(new.exists());self.assertEqual(old.read_bytes(),b'accepted')

    def test_failure_after_replace_also_restores_attempted_path(self):
        previous=self.accepted();calls=[]
        def writer(path,data):
            calls.append(Path(path))
            atomic_write_bytes(path,data)
            if len(calls)==2:raise OSError('injected directory fsync failure after replace')
        with BuildPublication(self.root) as staged,patch('build_publication.atomic_write_bytes',side_effect=writer):
            with self.assertRaisesRegex(OSError,'after replace'):
                staged.publish([(path,b'new validated bytes') for path in previous])
        self.assertTrue(all(path.read_bytes()==old for path,old in previous.items()))

    def test_receipt_hashes_staged_metadata_without_publishing_it(self):
        source=self.root/'original.gba';source.write_bytes(b'original')
        with BuildPublication(self.root) as staged:
            rom=staged.path('candidate.gba');rom.write_bytes(b'validated ROM')
            meta={name:staged.path(Path(name).name) for name in ('temp/integrity_map.json','temp/repoint_manifest.json')}
            for name,path in meta.items():path.write_bytes(name.encode())
            before={'files':{}}
            write_build_receipt(rom,source,before,before,hashlib.sha256(source.read_bytes()).hexdigest(),metadata_paths=meta)
            receipt=Path(str(rom)+'.build.json').read_bytes();data=json.loads(receipt)
            self.assertEqual(data['build_metadata'],{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in meta.items()})
            outputs=[self.root/name for name in ('full.gba','final.gba','title.gba')]
            staged.publish([*[(p,rom.read_bytes()) for p in outputs],*[(Path(str(p)+'.build.json'),receipt) for p in outputs]])
            self.assertTrue(all(p.read_bytes()==b'validated ROM' for p in outputs))
            self.assertTrue(all(Path(str(p)+'.build.json').read_bytes()==receipt for p in outputs))


if __name__=='__main__':unittest.main()
