import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype

DATA_CALC_TYPE = "ROW_IN_ROW_OUT"
ALLOWED_DTYPES = {"numeric", "time", "string"}
ALLOWED_METHODS = {"fill", "delete"}
MISSING_STRING_MARKERS = {"null", "none", "nan"}
STRATEGIES_BY_DTYPE = {
    "numeric": {"mean", "median", "mode", "constant", "forward_fill", "backward_fill"},
    "time": {"constant", "forward_fill", "backward_fill"},
    "string": {"mode", "constant"},
}

MISSING_VALUE_META = {
    "code": "missing_value",
    "title": "缺失值处理",
    "description": "对结构化表格数据中的缺失值进行填充或删行处理，支持数值字段与时间字段分别配置不同的处理策略。",
    "version": "2.0.0",
    "dependencies": [
        "pandas>=2.0.0",
        "numpy>=1.24.0",
    ],
    "inputs": [
        {
            "name": "dataset",
            "label": "数据集",
            "type": "数组",
            "required": True,
            "description": "原始输入数据，支持字典列表或二维数组",
        },
        {
            "name": "field_meta",
            "label": "字段元信息",
            "type": "数组",
            "required": False,
            "description": "可选字段元信息。若未传，算法会在字典列表输入场景下自动推断列名与字段类型",
            "visible": False,
        },
        {
            "name": "fill_rules",
            "label": "处理规则",
            "type": "数组",
            "required": True,
            "description": "用户定义的逐列处理规则列表，每条规则指定目标列、处理方法和填充策略",
            "item_schema": {
                "field_group": {
                    "label": "字段类型",
                    "type": "enum",
                    "options": ["numeric", "time", "string"],
                    "required": True,
                    "description": "目标列的字段类型标识，用于约束可选策略范围",
                },
                "columns": {
                    "label": "目标列",
                    "type": "array",
                    "required": True,
                    "description": "要处理的列名列表，列名必须存在于 field_meta 中",
                    "dependsOn": "field_group",
                },
                "method": {
                    "label": "处理方式",
                    "type": "enum",
                    "options": ["fill", "delete"],
                    "required": True,
                    "description": "fill=填充缺失值, delete=删除含缺失值的行",
                },
                "strategy": {
                    "label": "填充策略",
                    "type": "enum",
                    "options": ["mean", "median", "mode", "constant", "forward_fill", "backward_fill"],
                    "required": False,
                    "description": "具体的填充算法，method=fill 时必填",
                    "dependsOn": "method=='fill'",
                },
                "fill_value": {
                    "label": "指定填充值",
                    "type": "any",
                    "required": False,
                    "description": "strategy=constant 时必填，数值字段传数字，时间字段传时间字符串",
                    "dependsOn": "strategy=='constant'",
                },
            },
        },
    ],
    "outputs": [
        {
            "name": "data",
            "label": "处理后数据集",
            "type": "数组",
            "description": "清洗后的结果数据",
        },
        {
            "name": "summary",
            "label": "执行摘要",
            "type": "对象",
            "description": "包含 input_rows, output_rows, deleted_rows, filled_cells, warnings 等统计信息",
        },
    ],
}


@dataclass
class RuntimeContext:
    task_id: str
    logger: logging.Logger
    log_level: int
    node_config: Optional[dict] = None
    platform_ctx: Optional[Any] = None


class AlgorithmError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ValidationError(AlgorithmError):
    def __init__(self, message: str):
        super().__init__(400, message)


class ProcessingError(AlgorithmError):
    def __init__(self, message: str):
        super().__init__(422, message)


def get_logger(_ctx: Optional[RuntimeContext]) -> Optional[logging.Logger]:
    """
    获取平台注入的日志对象。

    Args:
        _ctx: 运行上下文，可为空。

    Returns:
        平台 logger；若上下文或 logger 不存在则返回 None。
    """
    return _ctx.logger if getattr(_ctx, "logger", None) else None


def build_result(
    code: int,
    msg: str,
    data: Optional[List[Dict[str, Any]]],
    summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    组装平台统一返回结构。

    Args:
        code: 业务状态码。
        msg: 状态说明。
        data: 结果数据集，失败时通常为 None。
        summary: 执行摘要，可为空。

    Returns:
        符合平台约定的结果字典。
    """
    result = {
        "code": code,
        "msg": msg,
        "dataCalcType": DATA_CALC_TYPE,
        "data": data,
    }
    if summary is not None:
        result["summary"] = summary
    return result


def normalize_missing_value(value: Any) -> Any:
    """
    将单个值归一化为算法内部的缺失值表示。

    Args:
        value: 原始单元格值。

    Returns:
        归一化后的值；若识别为缺失则返回 np.nan，否则返回原值。
    """
    if value is None:
        return np.nan

    if isinstance(value, str):
        # 平台常见的空串、空白串和文本型空值占位统一视作缺失。
        stripped = value.strip()
        if not stripped or stripped.lower() in MISSING_STRING_MARKERS:
            return np.nan
        return value

    if pd.isna(value):
        return np.nan

    return value


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    对整张表执行缺失值归一化。

    Args:
        df: 原始 DataFrame。

    Returns:
        归一化后的 DataFrame。
    """
    return df.apply(lambda column: column.map(normalize_missing_value))


def parse_numeric_fill_value(fill_value: Any) -> float:
    """
    校验并解析 numeric 类型的常量填充值。

    Args:
        fill_value: 用户配置的 fill_value。

    Returns:
        可用于数值列填充的 float 值。
    """
    if isinstance(fill_value, bool):
        raise ValidationError("numeric 类型的 fill_value 不能为布尔值")

    parsed = pd.to_numeric(pd.Series([fill_value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        raise ValidationError(f"numeric 类型的 fill_value 非法: {fill_value}")
    return float(parsed)


def parse_time_value(value: Any, column: str, time_format: Optional[str]) -> pd.Timestamp:
    """
    解析并校验单个时间值。

    Args:
        value: 待解析的原始值。
        column: 所属列名，用于错误提示。
        time_format: 时间格式，未提供时走 pandas 默认解析。

    Returns:
        解析成功后的 pandas Timestamp。
    """
    if time_format:
        # 有显式格式时走严格校验，避免 pandas 的宽松解析把非法值放过去。
        if isinstance(value, pd.Timestamp):
            return value
        if isinstance(value, datetime):
            return pd.Timestamp(value)
        try:
            return pd.Timestamp(datetime.strptime(str(value), time_format))
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                f"列 {column} 的时间值不符合格式 {time_format}: {value}"
            ) from exc

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValidationError(f"列 {column} 的时间值非法: {value}")
    return parsed


def parse_time_fill_value(fill_value: Any, column: str, time_format: Optional[str]) -> pd.Timestamp:
    """
    校验并解析 time 类型的常量填充值。

    Args:
        fill_value: 用户配置的 fill_value。
        column: 所属列名，用于错误提示。
        time_format: 时间格式，未提供时走 pandas 默认解析。

    Returns:
        可用于时间列填充的 pandas Timestamp。
    """
    if fill_value is None or (isinstance(fill_value, str) and not fill_value.strip()):
        raise ValidationError(f"列 {column} 的时间常量 fill_value 不能为空")
    return parse_time_value(fill_value, column, time_format)


def validate_string_fill_value(fill_value: Any) -> str:
    """
    校验 string 类型的常量填充值。

    Args:
        fill_value: 用户配置的 fill_value。

    Returns:
        合法的非空字符串。
    """
    if not isinstance(fill_value, str) or not fill_value.strip():
        raise ValidationError("string 类型的 fill_value 必须为非空字符串")
    return fill_value


def coerce_numeric_series(series: pd.Series, column: str) -> pd.Series:
    """
    将数值列转为可计算的数值序列，并拦截非法字符串。

    Args:
        series: 原始列数据。
        column: 列名，用于错误提示。

    Returns:
        转换后的数值型 Series。
    """
    converted = pd.to_numeric(series, errors="coerce")
    invalid_mask = series.notna() & converted.isna()
    if invalid_mask.any():
        invalid_values = series[invalid_mask].astype(str).unique().tolist()
        raise ValidationError(f"列 {column} 存在非法数值: {invalid_values[:3]}")
    return converted


def coerce_time_series(series: pd.Series, column: str, time_format: Optional[str]) -> pd.Series:
    """
    将时间列转为 datetime 序列，并按要求做严格格式校验。

    Args:
        series: 原始列数据。
        column: 列名，用于错误提示。
        time_format: 时间格式，未提供时走 pandas 默认解析。

    Returns:
        转换后的 datetime64 Series。
    """
    converted_values = []
    invalid_values = []

    for value in series.tolist():
        if pd.isna(value):
            converted_values.append(pd.NaT)
            continue
        try:
            converted_values.append(parse_time_value(value, column, time_format))
        except ValidationError:
            invalid_values.append(str(value))
            converted_values.append(pd.NaT)

    if invalid_values:
        if time_format:
            raise ValidationError(f"列 {column} 存在不符合格式 {time_format} 的时间值: {invalid_values[:3]}")
        raise ValidationError(f"列 {column} 存在非法时间值: {invalid_values[:3]}")

    return pd.Series(converted_values, index=series.index, dtype="datetime64[ns]")


def build_field_meta_map(field_meta: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    将字段元信息整理为按列名索引的映射。

    Args:
        field_meta: 字段元信息列表。

    Returns:
        以列名为 key 的字段配置映射。
    """
    if not isinstance(field_meta, list) or not field_meta:
        raise ValidationError("field_meta 必须为非空列表")

    meta_map: Dict[str, Dict[str, Any]] = {}
    for index, item in enumerate(field_meta):
        if not isinstance(item, dict):
            raise ValidationError(f"field_meta[{index}] 必须为对象")

        name = item.get("name")
        dtype = item.get("dtype")
        if not isinstance(name, str) or not name.strip():
            raise ValidationError(f"field_meta[{index}].name 非法")
        if dtype not in ALLOWED_DTYPES:
            raise ValidationError(f"field_meta[{index}].dtype 非法: {dtype}")
        if name in meta_map:
            raise ValidationError(f"field_meta 中存在重复字段: {name}")

        meta_map[name] = {
            "dtype": dtype,
            "format": item.get("format"),
        }

    return meta_map


def collect_rule_declared_dtypes(fill_rules: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    从 fill_rules 中提取列到 field_group 的声明映射。

    Args:
        fill_rules: 用户输入的处理规则列表。

    Returns:
        以列名为 key、field_group 为 value 的映射。
    """
    if not isinstance(fill_rules, list):
        return {}

    declared: Dict[str, str] = {}
    for index, rule in enumerate(fill_rules):
        if not isinstance(rule, dict):
            continue

        field_group = rule.get("field_group")
        columns = rule.get("columns")
        if field_group not in ALLOWED_DTYPES or not isinstance(columns, list):
            continue

        for column in columns:
            if not isinstance(column, str) or not column.strip():
                continue

            normalized_column = column.strip()
            existing_group = declared.get(normalized_column)
            if existing_group and existing_group != field_group:
                raise ValidationError(
                    f"fill_rules[{index}] 中列 {normalized_column} 的 field_group 与其它规则冲突"
                )
            declared[normalized_column] = field_group

    return declared


def infer_dtype_from_values(values: List[Any]) -> str:
    """
    根据列值粗略推断字段类型。

    Args:
        values: 某列的全部原始值。

    Returns:
        推断后的字段类型，默认回退为 string。
    """
    normalized_values = [normalize_missing_value(value) for value in values]
    non_missing_values = [value for value in normalized_values if not pd.isna(value)]

    if not non_missing_values:
        return "string"

    if all(
        not isinstance(value, bool)
        and not pd.isna(pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0])
        for value in non_missing_values
    ):
        return "numeric"

    if all(not pd.isna(pd.to_datetime(value, errors="coerce")) for value in non_missing_values):
        return "time"

    return "string"


def infer_field_meta(
    dataset: List[Any],
    fill_rules: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    在未传 field_meta 时，根据字典列表输入和 fill_rules 自动推断字段元信息。

    Args:
        dataset: 原始输入数据。
        fill_rules: 用户输入的处理规则列表。

    Returns:
        推断得到的字段元信息列表。
    """
    if not isinstance(dataset, list):
        raise ValidationError("dataset 必须为列表")

    rule_declared_dtypes = collect_rule_declared_dtypes(fill_rules)
    if not dataset:
        return [{"name": column, "dtype": dtype} for column, dtype in rule_declared_dtypes.items()]

    if not all(isinstance(row, dict) for row in dataset):
        raise ValidationError("field_meta 缺失时，dataset 必须为字典列表")

    ordered_columns: List[str] = []
    seen_columns = set()
    for row_index, row in enumerate(dataset):
        for raw_column in row.keys():
            if not isinstance(raw_column, str) or not raw_column.strip():
                raise ValidationError(f"dataset[{row_index}] 中存在非法列名: {raw_column}")

            column = raw_column.strip()
            if column not in seen_columns:
                seen_columns.add(column)
                ordered_columns.append(column)

    for column in rule_declared_dtypes:
        if column not in seen_columns:
            ordered_columns.append(column)

    inferred_field_meta: List[Dict[str, Any]] = []
    for column in ordered_columns:
        values = [row.get(column) for row in dataset]
        inferred_field_meta.append(
            {
                "name": column,
                "dtype": rule_declared_dtypes.get(column, infer_dtype_from_values(values)),
            }
        )

    return inferred_field_meta


def resolve_field_meta(
    dataset: List[Any],
    field_meta: Optional[List[Dict[str, Any]]],
    fill_rules: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    解析最终用于执行的字段元信息。

    Args:
        dataset: 原始输入数据。
        field_meta: 平台显式传入的字段元信息，可为空。
        fill_rules: 用户输入的处理规则列表。

    Returns:
        最终生效的字段元信息列表。
    """
    if field_meta:
        return field_meta
    return infer_field_meta(dataset, fill_rules)


def normalize_dataset_records(
    dataset: List[Any],
    field_meta_map: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    兼容矩阵和表格两种输入，并统一转换为字典列表。

    Args:
        dataset: 原始输入数据，可以是字典列表或二维数组。
        field_meta_map: 字段元信息映射，用于矩阵转表格时提供列顺序。

    Returns:
        标准化后的字典列表，每个元素代表一行记录。
    """
    if not isinstance(dataset, list):
        raise ValidationError("dataset 必须为列表")

    if not dataset:
        return []

    if all(isinstance(row, dict) for row in dataset):
        return dataset

    if all(isinstance(row, (list, tuple)) for row in dataset):
        column_names = list(field_meta_map.keys())
        expected_width = len(column_names)
        normalized_rows: List[Dict[str, Any]] = []

        for index, row in enumerate(dataset):
            if len(row) != expected_width:
                raise ValidationError(
                    f"dataset[{index}] 的列数与 field_meta 不一致，期望 {expected_width}，实际 {len(row)}"
                )
            normalized_rows.append(dict(zip(column_names, row)))
        return normalized_rows

    raise ValidationError("dataset 必须为字典列表或二维数组")


def validate_and_normalize_rules(
    fill_rules: List[Dict[str, Any]],
    field_meta_map: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    校验 fill_rules 合法性并补齐执行期需要的标准结构。

    Args:
        fill_rules: 用户输入的规则列表。
        field_meta_map: 字段元信息映射。

    Returns:
        规范化后的规则列表。
    """
    if not isinstance(fill_rules, list) or not fill_rules:
        raise ValidationError("fill_rules 必须为非空列表")

    normalized_rules: List[Dict[str, Any]] = []
    for index, rule in enumerate(fill_rules):
        if not isinstance(rule, dict):
            raise ValidationError(f"fill_rules[{index}] 必须为对象")

        field_group = rule.get("field_group")
        columns = rule.get("columns")
        method = rule.get("method")

        if field_group not in ALLOWED_DTYPES:
            raise ValidationError(f"fill_rules[{index}].field_group 非法: {field_group}")
        if method not in ALLOWED_METHODS:
            raise ValidationError(f"fill_rules[{index}].method 非法: {method}")
        if not isinstance(columns, list) or not columns or not all(isinstance(col, str) and col.strip() for col in columns):
            raise ValidationError(f"fill_rules[{index}].columns 必须为非空字符串列表")

        normalized_columns = [col.strip() for col in columns]
        for column in normalized_columns:
            if column not in field_meta_map:
                raise ValidationError(f"fill_rules[{index}] 引用了不存在的列: {column}")
            actual_dtype = field_meta_map[column]["dtype"]
            # field_group 只作为前端辅助选择项，真正执行仍以后端 field_meta 为准。
            if actual_dtype != field_group:
                raise ValidationError(
                    f"fill_rules[{index}] 中列 {column} 的 field_group={field_group} 与 field_meta 中的 dtype={actual_dtype} 不一致"
                )

        normalized_rule = {
            "field_group": field_group,
            "columns": normalized_columns,
            "method": method,
        }

        if method == "fill":
            strategy = rule.get("strategy")
            if strategy not in STRATEGIES_BY_DTYPE[field_group]:
                raise ValidationError(
                    f"fill_rules[{index}] 中策略 {strategy} 不支持字段类型 {field_group}"
                )
            normalized_rule["strategy"] = strategy

            if strategy == "constant":
                fill_value = rule.get("fill_value")
                if field_group == "numeric":
                    normalized_rule["fill_value"] = parse_numeric_fill_value(fill_value)
                elif field_group == "string":
                    normalized_rule["fill_value"] = validate_string_fill_value(fill_value)
                else:
                    normalized_rule["fill_value"] = fill_value

        normalized_rules.append(normalized_rule)

    return normalized_rules


def apply_delete_rules(df: pd.DataFrame, delete_columns: List[str]) -> tuple[pd.DataFrame, int]:
    """
    按删行规则删除指定列中包含缺失值的记录。

    Args:
        df: 归一化后的输入数据。
        delete_columns: 参与删行判断的列名列表。

    Returns:
        处理后的 DataFrame，以及被删除的行数。
    """
    if not delete_columns:
        return df, 0

    # 删行规则统一先执行，避免和后续 fill 规则产生先后歧义。
    dedup_columns = list(dict.fromkeys(delete_columns))
    before_rows = len(df)
    output_df = df.dropna(subset=dedup_columns).copy()
    return output_df, before_rows - len(output_df)


def apply_fill_rules(
    df: pd.DataFrame,
    fill_rules: List[Dict[str, Any]],
    field_meta_map: Dict[str, Dict[str, Any]],
    warnings: List[str],
) -> tuple[pd.DataFrame, int]:
    """
    按规则逐列执行填充，并累计填充数量与告警。

    Args:
        df: 已完成删行的数据表。
        fill_rules: 规范化后的规则列表。
        field_meta_map: 字段元信息映射。
        warnings: 告警列表，会在函数内追加内容。

    Returns:
        填充后的 DataFrame，以及成功填充的单元格数量。
    """
    filled_cells = 0

    for rule in fill_rules:
        if rule["method"] != "fill":
            continue

        strategy = rule["strategy"]
        for column in rule["columns"]:
            if column not in df.columns:
                # 数据里缺失整列时补一个空列，便于统一复用后续处理逻辑。
                df[column] = np.nan

            dtype = field_meta_map[column]["dtype"]
            time_format = field_meta_map[column].get("format")

            if dtype == "numeric":
                working_series = coerce_numeric_series(df[column], column)
            elif dtype == "time":
                working_series = coerce_time_series(df[column], column, time_format)
            else:
                working_series = df[column].astype(object)

            before_missing = int(working_series.isna().sum())
            if before_missing == 0:
                continue

            if dtype == "numeric":
                filled_series = fill_numeric_series(working_series, strategy, rule.get("fill_value"), column)
            elif dtype == "time":
                fill_value = None
                if strategy == "constant":
                    fill_value = parse_time_fill_value(rule.get("fill_value"), column, time_format)
                filled_series = fill_time_series(working_series, strategy, fill_value, column)
            else:
                filled_series = fill_string_series(working_series, strategy, rule.get("fill_value"), column)

            after_missing = int(filled_series.isna().sum())
            filled_cells += before_missing - after_missing
            df[column] = filled_series

            # 前向/后向填充在边界位置可能天然无解，这里保留为空并记录告警。
            if strategy in {"forward_fill", "backward_fill"} and after_missing > 0:
                warnings.append(f"列 {column} 使用 {strategy} 后仍有 {after_missing} 个缺失值保留为空")

    return df, filled_cells


def fill_numeric_series(series: pd.Series, strategy: str, fill_value: Any, column: str) -> pd.Series:
    """
    对数值列执行单列填充。

    Args:
        series: 已转为数值型的列数据。
        strategy: 填充策略。
        fill_value: 常量填充值，仅 constant 时使用。
        column: 列名，用于错误提示。

    Returns:
        填充后的数值型 Series。
    """
    if strategy == "constant":
        return series.fillna(fill_value)
    if strategy == "mean":
        if series.dropna().empty:
            raise ProcessingError(f"列 {column} 全为空，无法计算 mean")
        return series.fillna(series.mean())
    if strategy == "median":
        if series.dropna().empty:
            raise ProcessingError(f"列 {column} 全为空，无法计算 median")
        return series.fillna(series.median())
    if strategy == "mode":
        modes = series.dropna().mode()
        if modes.empty:
            raise ProcessingError(f"列 {column} 全为空，无法计算 mode")
        return series.fillna(modes.iloc[0])
    if strategy == "forward_fill":
        return series.ffill()
    if strategy == "backward_fill":
        return series.bfill()
    raise ValidationError(f"不支持的 numeric 策略: {strategy}")


def fill_time_series(series: pd.Series, strategy: str, fill_value: Any, column: str) -> pd.Series:
    """
    对时间列执行单列填充。

    Args:
        series: 已转为时间型的列数据。
        strategy: 填充策略。
        fill_value: 常量填充值，仅 constant 时使用。
        column: 列名，用于错误提示。

    Returns:
        填充后的时间型 Series。
    """
    if strategy == "constant":
        return series.fillna(fill_value)
    if strategy == "forward_fill":
        return series.ffill()
    if strategy == "backward_fill":
        return series.bfill()
    raise ValidationError(f"不支持的 time 策略: {strategy}，列: {column}")


def fill_string_series(series: pd.Series, strategy: str, fill_value: Any, column: str) -> pd.Series:
    """
    对字符串列执行单列填充。

    Args:
        series: 原始字符串列数据。
        strategy: 填充策略。
        fill_value: 常量填充值，仅 constant 时使用。
        column: 列名，用于错误提示。

    Returns:
        填充后的字符串 Series。
    """
    if strategy == "constant":
        return series.fillna(fill_value)
    if strategy == "mode":
        modes = series.dropna().mode()
        if modes.empty:
            raise ProcessingError(f"列 {column} 全为空，无法计算 mode")
        return series.fillna(modes.iloc[0])
    raise ValidationError(f"不支持的 string 策略: {strategy}，列: {column}")


def format_time_value(value: Any, time_format: Optional[str]) -> Any:
    """
    将内部时间值格式化为平台可序列化的输出值。

    Args:
        value: DataFrame 中的时间值。
        time_format: 原字段声明的输出格式。

    Returns:
        None、格式化后的时间字符串，或原值。
    """
    if pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        if time_format:
            return value.strftime(time_format)
        return value.isoformat(sep=" ")

    return value


def serialize_output(df: pd.DataFrame, field_meta_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    将处理完成的 DataFrame 转回平台要求的字典列表。

    Args:
        df: 处理完成后的数据表。
        field_meta_map: 字段元信息映射。

    Returns:
        可直接返回给平台的 records 列表。
    """
    output_df = df.copy()

    for column, meta in field_meta_map.items():
        if column not in output_df.columns or meta["dtype"] != "time":
            continue
        if is_datetime64_any_dtype(output_df[column]):
            # DataFrame 内部可用 Timestamp，输出时统一还原成平台更易消费的字符串。
            output_df[column] = output_df[column].map(lambda value: format_time_value(value, meta.get("format")))

    output_df = output_df.astype(object).where(pd.notna(output_df), None)
    return output_df.to_dict(orient="records")


class MissingValueProcessor:
    """
    缺失值处理执行器。

    :param dataset: 输入数据集，支持字典列表或二维数组。
    :param field_meta: 字段元信息列表。
    :param fill_rules: 用户配置的处理规则列表。
    :param ctx: 平台运行上下文，可选。
    """

    def __init__(
        self,
        dataset: List[Any],
        field_meta: Optional[List[Dict[str, Any]]] = None,
        fill_rules: Optional[List[Dict[str, Any]]] = None,
        ctx: Optional[RuntimeContext] = None,
    ) -> None:
        self.dataset = dataset
        self.field_meta = field_meta
        self.fill_rules = fill_rules or []
        self.ctx = ctx
        self.logger = get_logger(ctx)
        self.input_rows = len(dataset) if isinstance(dataset, list) else 0

    def run(self) -> Dict[str, Any]:
        """
        执行完整的缺失值处理流程。

        :return: 平台标准结果字典。
        """
        if self.logger:
            self.logger.info("开启缺失值处理算法，输入数据行数: %s", self.input_rows)

        try:
            effective_field_meta = resolve_field_meta(self.dataset, self.field_meta, self.fill_rules)
            field_meta_map = build_field_meta_map(effective_field_meta)
            dataset_records = normalize_dataset_records(self.dataset, field_meta_map)
            normalized_rules = validate_and_normalize_rules(self.fill_rules, field_meta_map)

            if not dataset_records:
                return self._build_empty_result()

            df = self._build_dataframe(dataset_records, field_meta_map)

            delete_columns = [
                column
                for rule in normalized_rules
                if rule["method"] == "delete"
                for column in rule["columns"]
            ]
            df, deleted_rows = apply_delete_rules(df, delete_columns)

            warnings: List[str] = []
            if deleted_rows and df.empty:
                warnings.append("删行后结果为空")

            df, filled_cells = apply_fill_rules(df, normalized_rules, field_meta_map, warnings)
            output_data = serialize_output(df, field_meta_map)
            summary = self._build_summary(len(output_data), deleted_rows, filled_cells, warnings)

            if self.logger:
                self.logger.info(
                    "缺失值处理完成，输出行数: %s，删行数: %s，填充单元格数: %s",
                    len(output_data),
                    deleted_rows,
                    filled_cells,
                )

            return build_result(200, "执行缺失值处理算法成功", output_data, summary)
        except AlgorithmError as exc:
            if self.logger:
                self.logger.warning("缺失值处理业务异常(code=%s): %s", exc.code, exc.message)
            return build_result(exc.code, exc.message, None)
        except Exception as exc:  # pragma: no cover
            if self.logger:
                self.logger.exception("缺失值处理发生未捕获异常")
            return build_result(500, f"系统异常: {exc}", None)

    def _build_empty_result(self) -> Dict[str, Any]:
        """
        构造空数据集场景的标准返回值。

        :return: 空结果集对应的结果字典。
        """
        summary = {
            "input_rows": 0,
            "output_rows": 0,
            "deleted_rows": 0,
            "filled_cells": 0,
            "warnings": ["空数据集跳过处理"],
        }
        return build_result(200, "空数据集跳过", [], summary)

    def _build_dataframe(
        self,
        dataset_records: List[Dict[str, Any]],
        field_meta_map: Dict[str, Dict[str, Any]],
    ) -> pd.DataFrame:
        """
        将标准化记录集转换为进入算法主流程的 DataFrame。

        :param dataset_records: 标准化后的字典列表。
        :param field_meta_map: 字段元信息映射。
        :return: 归一化后的 DataFrame。
        """
        df = pd.DataFrame(dataset_records)
        for column in field_meta_map:
            if column not in df.columns:
                df[column] = np.nan

        # 先统一识别缺失值，再进入删行/填充两阶段处理。
        return normalize_dataframe(df)

    def _build_summary(
        self,
        output_rows: int,
        deleted_rows: int,
        filled_cells: int,
        warnings: List[str],
    ) -> Dict[str, Any]:
        """
        组装执行摘要信息。

        :param output_rows: 输出数据行数。
        :param deleted_rows: 删行数量。
        :param filled_cells: 填充单元格数量。
        :param warnings: 执行过程中产生的告警列表。
        :return: summary 字典。
        """
        return {
            "input_rows": self.input_rows,
            "output_rows": output_rows,
            "deleted_rows": deleted_rows,
            "filled_cells": filled_cells,
            "warnings": warnings,
        }


def do_missing_value(
    dataset: List[Any],
    field_meta: Optional[List[Dict[str, Any]]] = None,
    fill_rules: Optional[List[Dict[str, Any]]] = None,
    _ctx: Optional[RuntimeContext] = None,
) -> Dict[str, Any]:
    """
    缺失值处理算法主入口。

    :param dataset: 输入数据集，标准场景为字典列表；若传二维数组则需配合 field_meta 使用。
    :param field_meta: 可选字段元信息列表；未传时会在字典列表输入场景下自动推断。
    :param fill_rules: 用户配置的缺失值处理规则列表。
    :param _ctx: 平台运行上下文，可选，未传时默认为 None。
    :return: 算法执行结果字典，固定包含 code、msg、dataCalcType、data，可选 summary。
    """
    processor = MissingValueProcessor(dataset, field_meta, fill_rules, _ctx)
    return processor.run()


if __name__ == "__main__":
    print("正在执行缺失值处理算法的本地测试...")
    test_data = {
        "dataset": [
            [1, 2]
        ],
        "fill_rules": [
            {"field_group": "numeric", "columns": ["temperature"], "method": "fill", "strategy": "mean"}
        ]
    }

    result = do_missing_value(**test_data)
    print(result)
