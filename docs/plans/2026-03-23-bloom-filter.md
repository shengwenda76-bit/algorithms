# Bloom Filter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a minimal Chinese-language Bloom filter example under `布隆算法` with a Python implementation, inline self-test, and README documentation.

**Architecture:** Keep the feature intentionally small. Put the production code and assert-based self-test in `布隆算法/bloom_filter.py`, and place concept and usage notes in `布隆算法/README.md`. The filter stores a bit array in a Python list and derives multiple hash positions from SHA-256 based digests.

**Tech Stack:** Python standard library only

---

### Task 1: Create the failing self-test script

**Files:**
- Create: `docs/plans/2026-03-23-bloom-filter-design.md`
- Create: `docs/plans/2026-03-23-bloom-filter.md`
- Create: `布隆算法/bloom_filter.py`

**Step 1: Write the failing test**

```python
def _run_self_test():
    bloom = BloomFilter(expected_items=100, error_rate=0.01)
    bloom.add("apple")
    assert "apple" in bloom
    assert bloom.contains("apple")
    assert "banana" not in bloom
```

**Step 2: Run test to verify it fails**

Run: `python .\布隆算法\bloom_filter.py`
Expected: FAIL with `NameError` because `BloomFilter` is not implemented yet

**Step 3: Write minimal implementation**

```python
class BloomFilter:
    ...
```

**Step 4: Run test to verify it passes**

Run: `python .\布隆算法\bloom_filter.py`
Expected: PASS and print a success message

### Task 2: Add the README

**Files:**
- Create: `布隆算法/README.md`

**Step 1: Write the documentation**

Document:
- what a Bloom filter is
- why it is useful
- common use cases
- strengths and trade-offs

**Step 2: Verify content exists**

Run: `Get-Content .\布隆算法\README.md`
Expected: Chinese documentation describing meaning and common uses

### Task 3: Final verification

**Files:**
- Verify: `布隆算法/bloom_filter.py`
- Verify: `布隆算法/README.md`

**Step 1: Run the script again**

Run: `python .\布隆算法\bloom_filter.py`
Expected: PASS

**Step 2: Inspect repository status**

Run: `git status --short`
Expected: shows the new folder and plan/docs files as added or untracked
