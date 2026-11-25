# Frozen original implementation

These two files are **byte-for-byte copies** of the pre-refactor modules
(`EdgeQuantAI/EdgeQuantAI.py` and `EdgeQuantAI/fundamental_analyzer.py` at
commit `a1feaa5`). They are never imported by the library.

`tests/test_differential.py` loads them and asserts that the refactored package
produces *exactly* the same outputs (values, dtypes, column order, return
types) for the same inputs. Do not edit or lint these files.

Verify provenance with:

    # The original files sat in a sub-folder in that commit, so look the path up:
    old=$(git ls-tree -r --name-only a1feaa5 | grep '/EdgeQuantAI/EdgeQuantAI.py$')
    git show "a1feaa5:$old" | diff - tests/legacy/EdgeQuantAI.py
