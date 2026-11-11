"""Deterministic validation. Naive input times mean Asia/Shanghai by contract."""
from datetime import datetime, timedelta, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

"""
使用 Pydantic 定义规则:
设备 ID 必须是正整数。
设备 ID 不能重复。
开始时间不能晚于结束时间。
查询窗口不能超过 7 天。
多设备诊断预览至少需要两个设备。
工具参数不能夹带未定义字段。
"""

PositiveId = Annotated[StrictInt, Field(gt=0)]


class DeviceArgs(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ne_id: PositiveId


class AncestorArgs(DeviceArgs):
    max_depth: Annotated[StrictInt, Field(ge=1, le=64)] = 10


class CommonArgs(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ne_ids: list[PositiveId] = Field(min_length=2, max_length=32)
    max_depth: Annotated[StrictInt, Field(ge=1, le=64)] = 10

    @model_validator(mode='after')
    def distinct(self):
        if len(set(self.ne_ids)) != len(self.ne_ids):
            raise ValueError('设备ID不得重复')
        return self


class WindowArgs(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start_time: str
    end_time: str

    @model_validator(mode='after')
    def valid_window(self):
        values = []
        for name in ('start_time', 'end_time'):
            text = getattr(self, name)
            if 'T' not in text and ' ' not in text:
                raise ValueError('必须提供明确日期和时刻')
            value = datetime.fromisoformat(text)
            # Java's API accepts LocalDateTime; explicitly normalize to Shanghai.
            if value.tzinfo is not None:
                value = value.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)
            setattr(self, name, value.isoformat())
            values.append(value)
        if values[0] > values[1]:
            raise ValueError('开始时间不能晚于结束时间')
        if values[1] - values[0] > timedelta(days=7):
            raise ValueError('诊断查询窗口最多7天')
        return self


class DeviceWindowArgs(WindowArgs):
    ne_id: PositiveId


class KpiArgs(DeviceWindowArgs):
    metric_code: str = Field(min_length=1, max_length=128)


class PreviewArgs(WindowArgs):
    affected_ne_ids: list[PositiveId] = Field(min_length=2, max_length=32)
    max_depth: Annotated[StrictInt, Field(ge=1, le=64)] = 10

    @model_validator(mode='after')
    def distinct(self):
        if len(set(self.affected_ne_ids)) != len(self.affected_ne_ids):
            raise ValueError('设备ID不得重复')
        return self


class DiagnosisInput(WindowArgs):
    affected_ne_ids: list[PositiveId] = Field(min_length=1, max_length=32)

    @model_validator(mode='after')
    def distinct(self):
        if len(set(self.affected_ne_ids)) != len(self.affected_ne_ids):
            raise ValueError('设备ID不得重复')
        return self


"""
ARGUMENT_MODELS 和 validate_arguments()：检查每次工具调用
"""

ARGUMENT_MODELS = {
    'get_network_element': DeviceArgs, 'get_ancestors': AncestorArgs,
    'find_common_upstream': CommonArgs, 'get_kpi_statistics': KpiArgs,
    'get_alarm_window': DeviceWindowArgs, 'get_anomalies_by_ne': DeviceArgs,
    'preview_diagnosis': PreviewArgs, 'list_kpi_metrics': DeviceWindowArgs,
    'get_anomalies_in_window': DeviceWindowArgs,
}


def validate_arguments(name: str, arguments: dict) -> dict:
    model = ARGUMENT_MODELS.get(name)
    if model is None:
        raise ValueError('未知或未授权工具')
    return model.model_validate(arguments).model_dump()
