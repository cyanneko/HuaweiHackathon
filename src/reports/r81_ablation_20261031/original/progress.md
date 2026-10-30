# SDD ledger — plan: tmp/r81_ablation_20261031/PLAN.md

Root approved design and text-only preparation; native compile/run waits for Root GO.
Ruling: use exclusively assigned tmp/r81_ablation_20261031 rather than a Git worktree or skill workspace — Root forbids shared Git edits and assigns this isolated artifact directory — no branch integration is performed.
Pre-flight: Task1 source manifest feeds Task2 runner; exact method names, source/TU hashes and framework prefix/suffix hashes match interfaces.
Pre-flight: Task2 complete selection feeds Task3; expected108+648+90 cells, one repeat and global2200s deadline match.
Task1 RED: test_sources.py failed ModuleNotFoundError for generate before implementation.
