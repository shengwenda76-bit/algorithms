import hashlib
import math


class BloomFilter:
    """一个只依赖 Python 标准库实现的简易布隆过滤器。"""

    def __init__(self, expected_items, error_rate=0.01):
        if expected_items <= 0:
            raise ValueError("expected_items 必须大于 0")
        if not 0 < error_rate < 1:
            raise ValueError("error_rate 必须在 0 和 1 之间")

        # 根据期望容量和误判率，估算位数组长度与哈希函数个数。
        bit_array_size = -expected_items * math.log(error_rate) / (math.log(2) ** 2)
        hash_count = (bit_array_size / expected_items) * math.log(2)

        self.size = max(1, math.ceil(bit_array_size))
        self.hash_count = max(1, math.ceil(hash_count))
        self.bit_array = [0] * self.size

    def _hashes(self, item):
        # 同一个元素经过多次带序号的哈希，得到多个落点位置。
        value = str(item).encode("utf-8")
        for index in range(self.hash_count):
            digest = hashlib.sha256(index.to_bytes(2, "big") + value).hexdigest()
            yield int(digest, 16) % self.size

    def add(self, item):
        # 把该元素对应的所有位置都置为 1。
        for position in self._hashes(item):
            self.bit_array[position] = 1

    def contains(self, item):
        # 只要有一个位置不是 1，就能确定元素一定不存在。
        return all(self.bit_array[position] for position in self._hashes(item))

    def __contains__(self, item):
        # 支持使用 "item in bloom" 这种更自然的写法。
        return self.contains(item)


def _run_self_test():
    # 创建一个可容纳约 100 个元素、误判率约 1% 的布隆过滤器。
    bloom = BloomFilter(expected_items=100, error_rate=0.01)
    bloom.add("apple")

    # 已加入的元素应该命中。
    assert "apple" in bloom
    assert bloom.contains("apple")

    # 没加入过的元素在这个简单示例里应当不命中。
    assert "banana" not in bloom

    # 重复加入同一个元素不会出错。
    bloom.add("apple")
    assert "apple" in bloom


if __name__ == "__main__":
    _run_self_test()
    print("布隆过滤器自测通过。")
