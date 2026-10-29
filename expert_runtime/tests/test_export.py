import importlib.util
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest


class ExportTests(unittest.TestCase):
    def setUp(self):
        script = Path(__file__).resolve().parents[1] / 'export.py'
        if not script.is_file():
            self.fail('single-file exporter is not implemented')
        spec = importlib.util.spec_from_file_location('expert_export', script)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, name, text):
        path = self.root / name
        path.write_text(text, encoding='utf8')
        return path

    def test_recursive_dedup_and_reproducibility(self):
        self.put('a.hpp', '#pragma once\n#include <vector>\nstruct Helper {};\n')
        self.put('b.hpp', '#include "a.hpp"\nstruct Other {};\n')
        entry = self.put('standalone.cpp', '#include "a.hpp"\n#include "b.hpp"\nclass MySpillScheduler {};\n')
        text = self.module.flatten(entry, self.root)
        self.assertEqual(text, self.module.flatten(entry, self.root))
        self.assertEqual(text.count('struct Helper'), 1)
        self.assertIn('#include <vector>', text)
        self.assertNotIn('#include "', text)
        self.assertNotIn('#pragma once', text)
        self.assertNotIn(str(self.root), text)

    def test_cycle_is_reported(self):
        entry = self.put('a.hpp', '#include "b.hpp"\n')
        self.put('b.hpp', '#include "a.hpp"\n')
        with self.assertRaisesRegex(ValueError, 'cycle'):
            self.module.flatten(entry, self.root)

    def test_conditional_local_include_is_rejected(self):
        self.put('common.hpp', 'struct Common {};\n')
        entry = self.put('a.hpp', '#if 0\n#include "common.hpp"\n#endif\n#include "common.hpp"\n')
        with self.assertRaisesRegex(ValueError, 'conditional'):
            self.module.flatten(entry, self.root)

    def test_normal_outer_include_guard_is_supported(self):
        self.put('common.hpp', 'struct Common {};\n')
        entry = self.put('a.hpp', '#ifndef A_HPP\n#define A_HPP\n#include "common.hpp"\n#endif\n')
        self.assertIn('struct Common', self.module.flatten(entry, self.root))

    def test_macro_include_is_rejected(self):
        entry = self.put('a.hpp', '#include HEADER_MACRO\n')
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            self.module.flatten(entry, self.root)

    def test_line_splicing_is_rejected_even_in_comments(self):
        self.put('common.hpp', 'struct Common {};\n')
        entry = self.put('a.hpp', '// continued comment'+'\\'+'\n#include "common.hpp"\n')
        with self.assertRaisesRegex(ValueError, 'continuation'):
            self.module.flatten(entry, self.root)

    def test_outside_repository_is_rejected(self):
        entry = self.put('a.hpp', '#include "../outside.hpp"\n')
        with self.assertRaisesRegex(ValueError, 'outside'):
            self.module.flatten(entry, self.root)

    def test_cli_does_not_overwrite_existing_output(self):
        output = self.put('existing.cpp', 'keep original bytes\n')
        real_entry = Path(self.module.__file__).parent/'v1/context.hpp'
        result = subprocess.run([sys.executable, '-B', self.module.__file__,
                                 '--entry', str(real_entry), '--out', str(output)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_text(encoding='utf8'), 'keep original bytes\n')


if __name__ == '__main__':
    unittest.main()
