# Bit Bloom Filter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a new bit-based Bloom filter example under `bloom_filter/bit_bloom_filter.py` with clear Chinese comments and inline self-test.

**Architecture:** Keep the existing teaching version untouched and add a second implementation beside it. Store the Bloom filter bitset inside one Python integer and use bitwise OR and shift operations to set and read positions derived from SHA-256 hashes.

**Tech Stack:** Python standard library only

---

### Task 1: Create the failing self-test file

**Files:**
- Create: `docs/plans/2026-03-23-bit-bloom-filter-design.md`
- Create: `docs/plans/2026-03-23-bit-bloom-filter.md`
- Create: `bloom_filter/bit_bloom_filter.py`

**Step 1: Write the failing test**

```python
def _run_self_test():
    bloom = BitBloomFilter(expected_items=100, error_rate=0.01)
    bloom.add("apple")
    assert "apple" in bloom
    assert "banana" not in bloom
```

**Step 2: Run test to verify it fails**

Run: `python .\bloom_filter\bit_bloom_filter.py`
Expected: FAIL with `NameError` because `BitBloomFilter` is not implemented yet

**Step 3: Write minimal implementation**

```python
class BitBloomFilter:
    ...
```

**Step 4: Run test to verify it passes**

Run: `python .\bloom_filter\bit_bloom_filter.py`
Expected: PASS and print a success message

### Task 2: Final verification

**Files:**
- Verify: `bloom_filter/bit_bloom_filter.py`

**Step 1: Run the script again**

Run: `python .\bloom_filter\bit_bloom_filter.py`
Expected: PASS

**Step 2: Inspect repository status**

Run: `git status --short`
Expected: shows the new file and plan/docs files as added or modified
