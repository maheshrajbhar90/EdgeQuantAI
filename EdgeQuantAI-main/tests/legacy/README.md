# Frozen original implementation

These two files are **byte-for-byte copies** of the pre-refactor modules
(`EdgeQuantAI/EdgeQuantAI.py` and `EdgeQuantAI/fundamental_analyzer.py` at
commit `811823c`). They are never imported by the library.

`tests/test_differential.py` loads them and asserts that the refactored package
produces *exactly* the same outputs (values, dtypes, column order, return
types) for the same inputs. Do not edit or lint these files.

Verify provenance with:

    git show 811823c:EdgeQuantAI-main/EdgeQuantAI/EdgeQuantAI.py | diff - tests/legacy/EdgeQuantAI.py
