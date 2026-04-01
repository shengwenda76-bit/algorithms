# missing_value.py 测试文档

##  文档目的

本文档用于验证当前目录下 `missing_value.py` 算法在平台真实入参场景下的执行结果，并作为提交平台时的测试说明材料。

当前确认的平台输入口径：

- `dataset` 为字典列表
- `field_meta` 可能不传
- 算法需要根据 `dataset` 与 `fill_rules` 自动推断字段信息

本次测试依据：

- `missing_value.py` 当前代码实现
- [code_design.md](./code_design.md) 中“异常处理”章节
- [missing_value_desing.md](./missing_value_desing.md) 中的处理规则与返回约束

本次验证结果：

- 自动化测试 `test_missing_value.py`：`6` 个用例全部通过
- 补充人工验收样例：覆盖空数据、整列全空、删空结果、时间格式错误、前向填充边界、高删除比例等场景

测试时间：`2026-03-30`

测试环境：

- Python `3.14`
- numpy `2.4.4`
- pandas `3.0.1`

---

##  标准输入格式

###  输入参数总览

算法主入口：

```python
do_missing_value(dataset, field_meta=None, fill_rules=None, _ctx=None)
```

标准输入示例：

```python
dataset = [
    {
        "temperature": "20",                  # 温度
        "humidity": "30",                     # 湿度
        "sample_time": "2024-01-01 00:00:00",# 采样时间
        "device_id": "A",                     # 设备编号
        "category": "pump",                   # 类别
    },
    {
        "temperature": None,
        "humidity": "30",
        "sample_time": None,
        "device_id": "B",
        "category": None,
    },
]

fill_rules = [
    {
        "field_group": "numeric",      # 规则作用字段类型
        "columns": ["temperature"],    # 目标列名
        "method": "fill",              # fill=填充，delete=删行
        "strategy": "median",          # 中位数填充
    },
    {
        "field_group": "time",
        "columns": ["sample_time"],
        "method": "fill",
        "strategy": "forward_fill",    # 前向填充
    }
]

# field_meta 可选：
# 1. 平台不传时，算法会自动推断
# 2. 平台若希望做严格时间格式校验，可显式传 field_meta

_ctx = RuntimeContext(...)  # 可选，平台注入日志上下文
```

### 输入关键词说明

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `dataset` | `list[dict]` | 是 | 原始输入数据。每个元素代表一行记录，每个 key 代表一个字段。 |
| `field_meta` | `list[dict]` | 否 | 可选字段元信息。未传时算法会自动推断列名和字段类型。 |
| `fill_rules` | `list[dict]` | 是 | 缺失值处理规则列表。 |
| `_ctx` | `RuntimeContext` | 否 | 平台注入的日志与运行上下文。 |

常用关键词说明：

| 关键词 | 含义 |
| --- | --- |
| `dataset` | 原始输入数据集 |
| `field_meta` | 字段元信息，可选 |
| `fill_rules` | 处理规则集合 |
| `field_group` | 字段类型分组 |
| `columns` | 当前规则作用的列名列表 |
| `method` | 处理方式，`fill` 或 `delete` |
| `strategy` | 具体填充策略 |
| `fill_value` | 常量填充值 |
| `ROW_IN_ROW_OUT` | 输入多少行，输出仍按行返回结果 |

###  `field_meta` 的作用

默认情况下，平台可以不传 `field_meta`，算法会自动处理：

- 从 `dataset` 的 key 中提取列名
- 从 `fill_rules.field_group` 中确定处理列的字段类型
- 对未在规则中声明的其它列做简单类型推断，主要用于保留输出

以下场景建议平台显式传 `field_meta`：

- 需要对时间字段做严格格式校验
- `dataset` 不是字典列表，而是二维数组
- 平台希望固定字段类型，不希望算法自动推断

### field_meta` 可选示例

```json
[
  {"name": "temperature", "dtype": "numeric"},
  {"name": "humidity", "dtype": "numeric"},
  {"name": "sample_time", "dtype": "time", "format": "%Y-%m-%d %H:%M:%S"},
  {"name": "device_id", "dtype": "string"},
  {"name": "category", "dtype": "string"}
]
```

子字段说明：

| 字段 | 说明 |
| --- | --- |
| `name` | 列名 |
| `dtype` | 字段类型，仅允许 `numeric`、`time`、`string` |
| `format` | 时间字段格式，示例 `%Y-%m-%d %H:%M:%S` |

### `fill_rules` 子字段说明

| 字段 | 说明 |
| --- | --- |
| `field_group` | 规则目标字段类型，通常与实际字段类型一致 |
| `columns` | 目标列名列表 |
| `method` | `fill` 或 `delete` |
| `strategy` | `method=fill` 时必填 |
| `fill_value` | `strategy=constant` 时使用，需与字段类型匹配 |

###  缺失值识别规则

当前实现会将以下内容统一识别为缺失值：

- `null`
- `None`
- `NaN`
- `""`
- 仅空格字符串
- `"null"`
- `"none"`
- `"nan"`

---

##  标准返回格式

成功或失败均返回统一结构：

```json
{
  "code": 200,
  "msg": "执行缺失值处理算法成功",
  "dataCalcType": "ROW_IN_ROW_OUT",
  "data": [],
  "summary": {
    "input_rows": 0,
    "output_rows": 0,
    "deleted_rows": 0,
    "filled_cells": 0,
    "warnings": []
  }
}
```

返回字段说明：

| 字段 | 说明 |
| --- | --- |
| `code` | 状态码，常见为 `200`、`400`、`422`、`500` |
| `msg` | 执行结果说明 |
| `dataCalcType` | 固定为 `ROW_IN_ROW_OUT` |
| `data` | 处理后结果；失败时通常为 `null` |
| `summary` | 成功场景下的执行摘要 |

---

## 核心测试用例

说明：

- 除特别说明外，以下测试用例默认**不传 `field_meta`**
- 算法按平台真实场景，从 `dataset` 和 `fill_rules` 自动推断字段信息

### 正常场景：删行 + 填充联合执行

测试目的：验证在不传 `field_meta` 时，字典列表输入也能正确完成删行、数值填充、时间填充、字符串填充。

输入：

```json
{
  "dataset": [
    {"temperature": "20", "humidity": null, "sample_time": "2024-01-01 00:00:00", "device_id": "A", "category": "pump"},
    {"temperature": "", "humidity": "30", "sample_time": null, "device_id": "B", "category": null},
    {"temperature": "40", "humidity": "35", "sample_time": "2024-01-01 02:00:00", "device_id": null, "category": "pump"}
  ],
  "fill_rules": [
    {"field_group": "string", "columns": ["device_id"], "method": "delete"},
    {"field_group": "numeric", "columns": ["temperature"], "method": "fill", "strategy": "median"},
    {"field_group": "numeric", "columns": ["humidity"], "method": "fill", "strategy": "constant", "fill_value": 0},
    {"field_group": "time", "columns": ["sample_time"], "method": "fill", "strategy": "forward_fill"},
    {"field_group": "string", "columns": ["category"], "method": "fill", "strategy": "mode"}
  ]
}
```

返回：

```json
{
  "code": 200,
  "msg": "执行缺失值处理算法成功",
  "dataCalcType": "ROW_IN_ROW_OUT",
  "data": [
    {"temperature": 20.0, "humidity": 0.0, "sample_time": "2024-01-01 00:00:00", "device_id": "A", "category": "pump"},
    {"temperature": 20.0, "humidity": 30.0, "sample_time": "2024-01-01 00:00:00", "device_id": "B", "category": "pump"}
  ],
  "summary": {
    "input_rows": 3,
    "output_rows": 2,
    "deleted_rows": 1,
    "filled_cells": 4,
    "warnings": []
  }
}
```

结论：通过。

### 空数据集

测试目的：验证空数据集在不传 `field_meta` 时仍能正常返回。

输入：

```json
{
  "dataset": [],
  "fill_rules": [
    {"field_group": "numeric", "columns": ["temperature"], "method": "fill", "strategy": "mean"}
  ]
}
```

返回：

```json
{
  "code": 200,
  "msg": "空数据集跳过",
  "dataCalcType": "ROW_IN_ROW_OUT",
  "data": [],
  "summary": {
    "input_rows": 0,
    "output_rows": 0,
    "deleted_rows": 0,
    "filled_cells": 0,
    "warnings": ["空数据集跳过处理"]
  }
}
```

结论：通过。

### 整列全部缺失，使用均值填充

测试目的：验证不传 `field_meta` 时，统计量填充仍能识别“整列全空”并报错。

输入：

```json
{
  "dataset": [
    {"temperature": null},
    {"temperature": ""}
  ],
  "fill_rules": [
    {"field_group": "numeric", "columns": ["temperature"], "method": "fill", "strategy": "mean"}
  ]
}
```

返回：

```json
{
  "code": 422,
  "msg": "列 temperature 全为空，无法计算 mean",
  "dataCalcType": "ROW_IN_ROW_OUT",
  "data": null
}
```

结论：通过。

### 删除后结果为空

测试目的：验证删行后数据全部为空时，会返回空结果并给出告警。

输入：

```json
{
  "dataset": [
    {"temperature": "20", "device_id": null},
    {"temperature": "25", "device_id": ""}
  ],
  "fill_rules": [
    {"field_group": "string", "columns": ["device_id"], "method": "delete"}
  ]
}
```

返回：

```json
{
  "code": 200,
  "msg": "执行缺失值处理算法成功",
  "dataCalcType": "ROW_IN_ROW_OUT",
  "data": [],
  "summary": {
    "input_rows": 2,
    "output_rows": 0,
    "deleted_rows": 2,
    "filled_cells": 0,
    "warnings": ["删行后结果为空"]
  }
}
```

结论：通过。

###  时间字段格式非法

测试目的：验证当平台显式传 `field_meta.format` 时，算法会按指定格式做严格校验。

输入：

```json
{
  "dataset": [
    {"sample_time": "2024/01/01"}
  ],
  "field_meta": [
    {"name": "temperature", "dtype": "numeric"},
    {"name": "humidity", "dtype": "numeric"},
    {"name": "sample_time", "dtype": "time", "format": "%Y-%m-%d %H:%M:%S"},
    {"name": "device_id", "dtype": "string"},
    {"name": "category", "dtype": "string"}
  ],
  "fill_rules": [
    {"field_group": "time", "columns": ["sample_time"], "method": "fill", "strategy": "forward_fill"}
  ]
}
```

返回：

```json
{
  "code": 400,
  "msg": "列 sample_time 存在不符合格式 %Y-%m-%d %H:%M:%S 的时间值: ['2024/01/01']",
  "dataCalcType": "ROW_IN_ROW_OUT",
  "data": null
}
```

结论：通过。

### 前向填充边界告警

测试目的：验证不传 `field_meta` 时，时间字段前向填充仍能输出边界告警。

输入：

```json
{
  "dataset": [
    {"sample_time": null},
    {"sample_time": "2024-01-01 01:00:00"},
    {"sample_time": null}
  ],
  "fill_rules": [
    {"field_group": "time", "columns": ["sample_time"], "method": "fill", "strategy": "forward_fill"}
  ]
}
```

返回：

```json
{
  "code": 200,
  "msg": "执行缺失值处理算法成功",
  "dataCalcType": "ROW_IN_ROW_OUT",
  "data": [
    {"sample_time": null},
    {"sample_time": "2024-01-01 01:00:00"},
    {"sample_time": "2024-01-01 01:00:00"}
  ],
  "summary": {
    "input_rows": 3,
    "output_rows": 3,
    "deleted_rows": 0,
    "filled_cells": 1,
    "warnings": ["列 sample_time 使用 forward_fill 后仍有 1 个缺失值保留为空"]
  }
}
```

结论：通过。

### 指定值不合法

测试目的：验证不传 `field_meta` 时，`numeric` 字段非法常量仍会被拦截。

输入：

```json
{
  "dataset": [
    {"temperature": null}
  ],
  "fill_rules": [
    {"field_group": "numeric", "columns": ["temperature"], "method": "fill", "strategy": "constant", "fill_value": true}
  ]
}
```

返回：

```json
{
  "code": 400,
  "msg": "numeric 类型的 fill_value 不能为布尔值",
  "dataCalcType": "ROW_IN_ROW_OUT",
  "data": null
}
```

结论：通过。

### 未传 `field_meta` 且输入不是字典列表

测试目的：验证自动推断仅适用于字典列表；若平台传二维数组，仍需显式传 `field_meta`。

输入：

```json
{
  "dataset": [
    [1, 2]
  ],
  "fill_rules": [
    {"field_group": "numeric", "columns": ["temperature"], "method": "fill", "strategy": "mean"}
  ]
}
```

返回：

```json
{
  "code": 400,
  "msg": "field_meta 缺失时，dataset 必须为字典列表",
  "dataCalcType": "ROW_IN_ROW_OUT",
  "data": null
}
```

结论：通过。

---

## 补充观察项

### 删除比例过高

设计文档中提到“删除比例过高”应输出告警。当前实现的实际表现如下：

输入：

```json
{
  "dataset": [
    {"device_id": "A"},
    {"device_id": null},
    {"device_id": ""},
    {"device_id": null},
    {"device_id": null}
  ],
  "fill_rules": [
    {"field_group": "string", "columns": ["device_id"], "method": "delete"}
  ]
}
```

返回：

```json
{
  "code": 200,
  "msg": "执行缺失值处理算法成功",
  "dataCalcType": "ROW_IN_ROW_OUT",
  "summary": {
    "input_rows": 5,
    "output_rows": 1,
    "deleted_rows": 4,
    "filled_cells": 0,
    "warnings": []
  }
}
```

观察结论：

- 算法可以正常执行
- `deleted_rows=4`，删除比例达到 `80%`
- 当前版本**未输出“删除比例过高”告警**

### 严格时间格式校验依赖 `field_meta`

当前版本支持自动推断字段类型，但如果平台完全不传 `field_meta`：

- 算法仍可根据 `fill_rules.field_group='time'` 处理时间列
- 但时间字符串的严格格式约束会弱化
- 若平台要求严格按 `%Y-%m-%d %H:%M:%S` 校验，建议显式传 `field_meta.format`

---

## 测试结论

本次测试结果表明，`missing_value.py` 当前版本已经和平台真实输入口径对齐：

- 标准输入以字典列表为主
- `field_meta` 可以不传
- 不传 `field_meta` 时，算法能根据 `dataset` 与 `fill_rules` 自动推断字段信息

当前版本已验证通过的能力包括：

- 正常删行与填充流程
- 空数据集处理
- 整列全空阻断统计量填充
- 删除后结果为空告警
- 非法常量拦截
- 前向填充边界告警
- 显式 `field_meta` 下的严格时间格式校验
- 未传 `field_meta` 且输入类型不符时的异常拦截

提交平台时建议同步说明两点：

- 当前版本**未实现“删除比例过高”告警**
- 若平台要求严格时间格式校验，建议同时传 `field_meta.format`
