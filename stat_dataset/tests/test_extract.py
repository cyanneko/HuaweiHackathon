import contextlib,gzip,hashlib,importlib.util,io,json,sys,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('stat_extract',Path(__file__).resolve().parents[1]/'tools/extract.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class ExtractTest(unittest.TestCase):
    def test_integrity_and_existing_version(self):
        scratch=Path(__file__).resolve().parents[1]/'.local_tests';scratch.mkdir(exist_ok=True)
        # Keep tiny fixtures in the workspace; some Windows sessions cannot
        # create children beneath the operating system's redirected TEMP.
        with contextlib.nullcontext(tempfile.mkdtemp(dir=scratch)) as tmp:
            root=Path(tmp)/'package';root.mkdir();payload=b'test bytes\n';z=root/'data.gz';z.write_bytes(gzip.compress(payload,mtime=0))
            row={'split':'eval','archive':'data.gz','input':'eval/one.txt','sha256':hashlib.sha256(payload).hexdigest(),'archive_sha256':mod.sha(z)}
            (root/'manifest.json').write_text(json.dumps({'version':'1.0.0','cases':[row]}));original=mod.ROOT;mod.ROOT=root
            out=Path(tmp)/'restored';(out/'eval').mkdir(parents=True);(out/'eval/VERSION').write_text('old\n')
            argv=sys.argv;sys.argv=['extract.py','--split','eval','--out',str(out)]
            try:
                with self.assertRaises(ValueError):mod.main()
                self.assertFalse((out/'eval/one.txt').exists())
                (out/'eval/VERSION').write_text('1.0.0\n')
                with contextlib.redirect_stdout(io.StringIO()):mod.main();mod.main()
                self.assertEqual((out/'eval/one.txt').read_bytes(),payload)
                (out/'eval/one.txt').write_bytes(b'wrong')
                with self.assertRaises(ValueError):mod.main()
                with self.assertRaises(ValueError):mod.contained(out.resolve(),'../escape.txt')
            finally:sys.argv=argv;mod.ROOT=original
if __name__=='__main__':unittest.main()
