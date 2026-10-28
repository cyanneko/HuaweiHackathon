"""Verify statement conversion and PDF text; never run or change the reference engine."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from markdown_it import MarkdownIt
import pymupdf

ROOT = Path(__file__).resolve().parent
SOURCE_MD_HASH = '464a542ad56f0b81ebad23371846a705c202c4461589a5f37d65af5a65c99d69'
SOURCE_PDF_HASH = '5438db9bcee81b9c5fde8cfbe46dbbf471d1d0e460e3c0eb75a637fefff6f41c'


def compact(value):
    return re.sub(r'\s+', '', value)


def check(source_md, source_pdf=None):
    assert hashlib.sha256(source_md).hexdigest() == SOURCE_MD_HASH
    original = source_md.decode()
    enhanced = (ROOT / 'STATEMENT_ENHANCED.md').read_text()
    original_blocks = re.findall(r'```cpp\n(.*?)```', original, re.S)
    blocks = re.findall(r'```cpp\n(.*?)```', enhanced, re.S)
    assert len(original_blocks) == len(blocks) == 3
    def code_lines(block):
        return [line.replace('\xa0', ' ').rstrip() for line in block.splitlines() if line.strip()]

    assert all(code_lines(a) == code_lines(b) for a, b in zip(original_blocks, blocks))
    sample = re.search(r'### 样例输入.*?```text\n(.*?)```', enhanced, re.S).group(1)
    lines = sample.splitlines()
    k = int(lines[0].split()[0])
    n = int(lines[1].split()[0])
    operations = lines[2 + k:]
    assert len(operations) == n == 11 and all(line.strip() for line in operations)
    assert sum(line.startswith('INSERT') for line in operations) == 6
    assert sum(line.startswith('SWITCH') for line in operations) == 1
    assert sum(line.startswith('PROBE') for line in operations) == 4

    pdf = pymupdf.open(ROOT / 'STATEMENT_ENHANCED.pdf')
    # Omit only the generated page footer; retain actual reading order.
    pdf_body = '\n'.join(page.get_text(clip=pymupdf.Rect(0, 0, page.rect.width, page.rect.height - 35)) for page in pdf)
    assert '\x00' not in pdf_body and '\ufffd' not in pdf_body
    visible = compact(pdf_body)
    tokens = MarkdownIt('commonmark').enable('table').parse(enhanced)
    cursor = 0
    pieces = []
    for token in tokens:
        if token.type == 'inline':
            pieces.append(''.join(child.content for child in token.children or []
                                  if child.type in ('text', 'code_inline', 'html_inline')))
        elif token.type == 'fence':
            pieces.extend(token.content.splitlines())
    for piece in pieces:
        needle = compact(piece)
        if not needle:
            continue
        index = visible.find(needle, cursor)
        assert index >= 0, f'Missing/out-of-order PDF text: {piece[:120]!r}'
        cursor = index + len(needle)
    # The short input block must remain on one page, not just survive extraction.
    sample_pages = [i + 1 for i, page in enumerate(pdf)
                    if compact(sample) in compact(page.get_text())]
    assert len(sample_pages) == 1
    assert compact('1. 未完整形式化的输入范围') in visible
    assert compact('5. 评分边界') in visible
    assert '•' in pdf_body
    for page in pdf:
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines', []):
                x0, y0, x1, y1 = line['bbox']
                if y0 < page.rect.height - 35:
                    assert 39 <= x0 <= x1 <= page.rect.width - 39, line['bbox']
    assert visible.count('<value>') == 6  # Five output fields plus the conversion note.
    assert 'std::make_unique<MySpillScheduler>()' in visible
    code_checks = []
    for block in blocks:
        assert compact(block) in visible, 'C++ block lost/reordered characters in rendered PDF'
        code_checks.append(True)
    result = {
        'source_markdown_sha256': SOURCE_MD_HASH,
        'code_blocks_match_source_ignoring_whitespace': len(blocks),
        'code_nonblank_lines_exact_after_nbsp_and_trailing_space_normalization': True,
        'sample': {'N': n, 'physical_operation_lines': len(operations), 'insert': 6,
                   'switch': 1, 'probe': 4, 'pdf_page': sample_pages[0]},
        'pdf': {'pages': len(pdf), 'ordered_text_pieces_verified': len(pieces),
                'cpp_blocks_preserved': len(code_checks), 'no_nul_or_replacement': True, 'margins_valid': True,
                'list_markers_and_angle_bracket_text_preserved': True},
    }
    if source_pdf:
        source_bytes = Path(source_pdf).read_bytes()
        assert hashlib.sha256(source_bytes).hexdigest() == SOURCE_PDF_HASH
        source = pymupdf.open(stream=source_bytes, filetype='pdf')
        body = []
        for i, page in enumerate(source):
            selected = []
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines', []):
                    x0, y0, x1, y1 = line['bbox']
                    keep = x0 >= 47 and x0 < 450 and y0 >= 28 and y1 <= 815
                    if i == 0:
                        keep = keep and y0 >= 160 and not 235 < y0 < 290
                    if i == 14:
                        keep = keep and y1 < 365
                    if keep:
                        selected.append((round(y0, 1), x0, ''.join(span['text'] for span in line['spans'])))
            body.append('\n'.join(text for _, _, text in sorted(selected)))
        source_body = '\n'.join(body)
        for block in blocks:
            assert compact(block) in compact(source_body), 'C++ differs from original PDF body'
        raw_sample = source_body.split('样例输入\n', 1)[1].split('样例输出', 1)[0]
        assert compact(raw_sample) == compact(sample)
        result['source_pdf'] = {'sha256': SOURCE_PDF_HASH, 'pages': len(source),
                                'cpp_blocks_match': 3, 'sample_matches_ignoring_page_whitespace': True,
                                'code_and_sample_cross_page_continuity_verified': True}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-markdown', type=Path)
    parser.add_argument('--source-pdf', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    source_md = args.source_markdown.read_bytes() if args.source_markdown else subprocess.check_output(
        ['git', 'show', '11b719b:docs/statement-2026-10-20/statement.md'], cwd=ROOT)
    result = check(source_md, args.source_pdf)
    output = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.out:
        args.out.write_text(output)
    print(output, end='')
