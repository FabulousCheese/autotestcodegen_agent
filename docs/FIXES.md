# 修复总结

## 1. 断言生成逻辑问题

**问题**：TestGenerator 生成的测试断言不够健壮，导致测试失败。

**具体问题**：
- 浮点数精度：`assert divide(1, 1e-15) == 1e15` 失败
  - 原因：`1 / 1e-15 = 999999999999999.9`，与 `1e15` 精确比较不相等
- NaN 比较：`assert divide(inf, inf) == float('nan')` 失败
  - 原因：NaN 不能与自己比较（`nan != nan` 永远为真）

**解决方案**：

### 1.1 更新 LLM 提示词

文件：`agents/test_generator/agent.py`

在 `TEST_GENERATION_PROMPT` 中添加浮点数断言规则：

```
重要：浮点数断言规则
- 禁止使用 == 精确比较浮点数结果！
- 必须导入 math 模块并使用以下方法：
  * 对于浮点数比较：使用 math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12)
  * 对于 NaN 检查：使用 math.isnan(value) 而非 value == float('nan')
  * 对于无穷大检查：使用 math.isinf(value) 而非 value == float('inf')
```

### 1.2 添加后处理函数

文件：`core/tools/code_tools.py`

添加 `fix_floating_point_assertions()` 函数，自动转换不健壮的断言：

- `== float('nan')` → `math.isnan()`
- `== float('inf')` → `math.isinf()`
- 浮点数精确比较 → `math.isclose(rel_tol=1e-9, abs_tol=1e-12)`

### 1.3 集成到 TestGenerator

文件：`agents/test_generator/agent.py`

在 LLM 生成测试后自动调用修复函数：

```python
# 后处理：修复浮点数断言问题
from core.tools.code_tools import fix_floating_point_assertions
tests_code = fix_floating_point_assertions(tests_code)
```

---

## 2. 浮点数比较的正确方式

Python 中浮点数比较应该使用 `math` 模块提供的函数：

| 场景 | 错误写法 | 正确写法 |
|------|---------|---------|
| 浮点数相等 | `assert x == 0.1` | `assert math.isclose(x, 0.1)` |
| NaN 检查 | `assert x == float('nan')` | `assert math.isnan(x)` |
| 无穷大检查 | `assert x == float('inf')` | `assert math.isinf(x)` |

`math.isclose()` 参数说明：
- `rel_tol`: 相对容差，默认 1e-9
- `abs_tol`: 绝对容差，默认 1e-12
