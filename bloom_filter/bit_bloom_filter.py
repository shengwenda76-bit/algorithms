import hashlib
import math


class BitBloomFilter:
    """使用一个整数保存所有位信息的布隆过滤器。"""

    def __init__(self, expected_items, error_rate=0.01):
        if expected_items <= 0:
            raise ValueError("expected_items 必须大于 0")
        if not 0 < error_rate < 1:
            raise ValueError("error_rate 必须在 0 和 1 之间")

        # 根据期望元素数量和误判率，估算需要多少位。
        bit_count = -expected_items * math.log(error_rate) / (math.log(2) ** 2)
        # 估算应使用多少个哈希函数，数量越多，误判率通常越低。
        hash_count = (bit_count / expected_items) * math.log(2)

        self.size = max(1, math.ceil(bit_count))
        self.hash_count = max(1, math.ceil(hash_count))
        # 用一个整数保存全部位。初始值为 0，表示每一位都还是 0。
        self.bits = 0

    def _hashes(self, item):
        # 同一个元素配合不同序号做哈希，得到多个要置位的位置。
        value = str(item).encode("utf-8")
        for index in range(self.hash_count):
            digest = hashlib.sha256(index.to_bytes(2, "big") + value).hexdigest()
            yield int(digest, 16) % self.size

    def _set_bit(self, position):
        # 1 << position 表示“只有第 position 位是 1，其余位都是 0”的掩码。
        # 使用按位或 | 可以把目标位设置成 1，而不影响其他位。
        self.bits |= 1 << position

    def _get_bit(self, position):
        # 先把目标位右移到最右边，再和 1 做按位与，
        # 结果如果是 1，说明这一位被设置过；如果是 0，说明没被设置过。
        return (self.bits >> position) & 1

    def add(self, item):
        # 把这个元素对应的所有位置都置为 1。
        for position in self._hashes(item):
            self._set_bit(position)

    def contains(self, item):
        # 只要有任意一个位置还是 0，就能确定该元素一定不存在。
        # 如果所有位置都是 1，只能说明“可能存在”，这就是布隆过滤器的特点。
        return all(self._get_bit(position) for position in self._hashes(item))

    def __contains__(self, item):
        # 支持使用 "item in bloom" 的写法。
        return self.contains(item)


def _run_self_test():
    # 这里故意把位数设得更大一些，让示例中的未加入元素更不容易误判。
    bloom = BitBloomFilter(expected_items=100, error_rate=1e-9)
    bloom.add("apple")

    # 已加入的元素应当命中。
    assert "apple" in bloom
    assert bloom.contains("apple")

    # 未加入的元素在这个固定示例中应当不命中。
    assert "banana" not in bloom

    # 重复加入同一个元素不会报错，结果仍然应当命中。
    bloom.add("apple")
    assert "apple" in bloom


if __name__ == "__main__":
    _run_self_test()
    print("按位版布隆过滤器自测通过。")
