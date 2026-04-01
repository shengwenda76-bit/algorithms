# 布隆算法 Design

**目标**

在仓库根目录下新增 `布隆算法` 文件夹，包含一个 Python 版本的布隆过滤器实现与自测示例，以及一个中文 README 说明其含义和常见用法。

**设计**

- 目录结构保持最小，只创建 `布隆算法/bloom_filter.py` 与 `布隆算法/README.md`
- `bloom_filter.py` 提供 `BloomFilter` 类，支持 `add()`、`contains()` 与 `in` 语法
- 自测使用 `assert` 写在 `if __name__ == "__main__":` 中，便于直接运行验证
- README 使用中文说明布隆算法定义、核心特性、优缺点与典型使用场景

**测试策略**

- 先写依赖 `BloomFilter` 的自测代码并运行，确认因缺少实现而失败
- 再补充最小实现并重新运行，确认自测通过
