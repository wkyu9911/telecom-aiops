TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_network_element",
            "description": (
                "根据网络元素ID查询设备详细信息，包括设备编码、名称、"
                "类型、厂商和当前状态。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ne_id": {
                        "type": "integer",
                        "description": "网络元素ID"
                    }
                },
                "required": ["ne_id"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "get_ancestors",
            "description": (
                "查询某网络元素的所有上游祖先设备以及拓扑距离。"
                "适用于分析故障传播路径。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ne_id": {
                        "type": "integer",
                        "description": "网络元素ID"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "最大向上追溯深度，默认10"
                    }
                },
                "required": ["ne_id"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "find_common_upstream",
            "description": (
                "查询多个受影响网络元素的共同上游节点。"
                "用于识别可能导致多个下游设备同时故障的共同根因候选。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ne_ids": {
                        "type": "array",
                        "items": {
                            "type": "integer"
                        },
                        "description": "两个或多个网络元素ID"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "最大拓扑追溯深度，默认10"
                    }
                },
                "required": ["ne_ids"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "get_kpi_statistics",
            "description": (
                "查询指定网络元素、指标和时间窗口内的KPI统计信息；不确定指标时先用list_kpi_metrics查询，"
                "包括平均值、最小值、最大值、标准差和变化率。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ne_id": {
                        "type": "integer"
                    },
                    "metric_code": {
                        "type": "string"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "ISO时间，例如2026-08-27T17:45:00"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "ISO时间，例如2026-08-27T18:10:00"
                    }
                },
                "required": [
                    "ne_id",
                    "metric_code",
                    "start_time",
                    "end_time"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "get_alarm_window",
            "description": (
                "查询某网络元素在指定故障时间窗口内发生的告警。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ne_id": {
                        "type": "integer"
                    },
                    "start_time": {
                        "type": "string"
                    },
                    "end_time": {
                        "type": "string"
                    }
                },
                "required": [
                    "ne_id",
                    "start_time",
                    "end_time"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "get_anomalies_by_ne",
            "description": (
                "查询指定网络元素全部异常；故障诊断优先用get_anomalies_in_window限定窗口。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ne_id": {
                        "type": "integer"
                    }
                },
                "required": ["ne_id"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "preview_diagnosis",
            "description": (
                "调用Java根因诊断引擎，对多个受影响设备进行综合诊断，"
                "结合拓扑、告警和异常计算根因候选及评分。"
                "该工具不会写入DiagnosisCase。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "affected_ne_ids": {
                        "type": "array",
                        "items": {
                            "type": "integer"
                        }
                    },
                    "start_time": {
                        "type": "string"
                    },
                    "end_time": {
                        "type": "string"
                    },
                    "max_depth": {
                        "type": "integer"
                    }
                },
                "required": [
                    "affected_ne_ids",
                    "start_time",
                    "end_time"
                ]
            }
        }
    }
]

TOOLS.extend([
    {"type": "function", "function": {
        "name": "list_kpi_metrics",
        "description": "发现指定网元在故障窗口内实际拥有的KPI指标编码，避免猜测指标。",
        "parameters": {"type": "object", "properties": {
            "ne_id": {"type": "integer", "minimum": 1},
            "start_time": {"type": "string"}, "end_time": {"type": "string"}},
            "required": ["ne_id", "start_time", "end_time"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "get_anomalies_in_window",
        "description": "查询与故障窗口重叠的异常，不把无关历史异常作为当前证据。",
        "parameters": {"type": "object", "properties": {
            "ne_id": {"type": "integer", "minimum": 1},
            "start_time": {"type": "string"}, "end_time": {"type": "string"}},
            "required": ["ne_id", "start_time", "end_time"], "additionalProperties": False}}}
])

