from pydantic import ValidationError

from app.agent.validation import DiagnosisInput


VALID_INPUT = {
    "affected_ne_ids": [9, 10],
    "start_time": "2026-08-27T17:50:00",
    "end_time": "2026-08-27T18:10:00",
}

cases = [
    (
        "1. 缺少时间",
        {"affected_ne_ids": [9, 10]},
    ),
    (
        "2. 设备ID重复",
        {**VALID_INPUT, "affected_ne_ids": [9, 9]},
    ),
    (
        "3. 开始时间晚于结束时间",
        {
            **VALID_INPUT,
            "start_time": "2026-08-27T18:20:00",
        },
    ),
    (
        "4. 合法输入",
        VALID_INPUT.copy(),
    ),
(
    "5. 设备ID是字符串",
    {**VALID_INPUT, "affected_ne_ids": ["9", 10]},
),
(
    "6. 携带未定义字段",
    {**VALID_INPUT, "root_cause_ne_id": 7},
),
]


for title, values in cases:
    print(f"\n=== {title} ===")
    print("输入：", values)

    try:
        validated = DiagnosisInput.model_validate(values)

        print("校验通过，对象类型：", type(validated).__name__)
        print("转为字典：", validated.model_dump())

    except ValidationError as exc:
        print("校验失败：")

        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"])
            print(
                f"  位置：{location or '整个模型'}"
                f"；原因：{error['msg']}"
            )