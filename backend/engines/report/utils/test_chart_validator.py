ï»¿"""
å¾è¡¨éªè¯å¨åä¿®å¤å¨çæµè¯ç¨ä¾ï¿½?

è¿è¡æµè¯ï¿½?
    python -m pytest ReportEngine/utils/test_chart_validator.py -v
"""

import pytest
from backend.engines.report.utils.chart_validator import (
    ChartValidator,
    ChartRepairer,
    ValidationResult,
    RepairResult,
    create_chart_validator,
    create_chart_repairer
)


class TestChartValidator:
    """æµè¯ChartValidatorï¿½?""

    def setup_method(self):
        """æ¯ä¸ªæµè¯ååå§å"""
        self.validator = create_chart_validator()

    def test_valid_bar_chart(self):
        """æµè¯ææçæ±ç¶å¾"""
        widget_block = {
            "type": "widget",
            "widgetType": "chart.js/bar",
            "widgetId": "chart-001",
            "props": {
                "type": "bar",
                "title": "éå®æ°ï¿½?
            },
            "data": {
                "labels": ["ä¸ï¿½?, "äºæ", "ä¸æ"],
                "datasets": [
                    {
                        "label": "éå®é¢",
                        "data": [100, 200, 150]
                    }
                ]
            }
        }

        result = self.validator.validate(widget_block)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_valid_line_chart(self):
        """æµè¯ææçæçº¿å¾"""
        widget_block = {
            "type": "widget",
            "widgetType": "chart.js/line",
            "widgetId": "chart-002",
            "props": {
                "type": "line"
            },
            "data": {
                "labels": ["å¨ä¸", "å¨äº", "å¨ä¸"],
                "datasets": [
                    {
                        "label": "è®¿é®ï¿½?,
                        "data": [50, 75, 60]
                    }
                ]
            }
        }

        result = self.validator.validate(widget_block)
        assert result.is_valid

    def test_valid_pie_chart(self):
        """æµè¯ææçé¥¼ï¿½?""
        widget_block = {
            "widgetType": "chart.js/pie",
            "props": {"type": "pie"},
            "data": {
                "labels": ["A", "B", "C"],
                "datasets": [
                    {
                        "data": [30, 40, 30]
                    }
                ]
            }
        }

        result = self.validator.validate(widget_block)
        assert result.is_valid

    def test_missing_widgetType(self):
        """æµè¯ç¼ºå°widgetType"""
        widget_block = {
            "props": {},
            "data": {}
        }

        result = self.validator.validate(widget_block)
        assert not result.is_valid
        assert "widgetType" in result.errors[0]

    def test_missing_data_field(self):
        """æµè¯ç¼ºå°dataå­æ®µ"""
        widget_block = {
            "widgetType": "chart.js/bar",
            "props": {"type": "bar"}
        }

        result = self.validator.validate(widget_block)
        assert not result.is_valid
        assert "data" in result.errors[0]

    def test_missing_datasets(self):
        """æµè¯ç¼ºå°datasets"""
        widget_block = {
            "widgetType": "chart.js/bar",
            "props": {"type": "bar"},
            "data": {
                "labels": ["A", "B"]
            }
        }

        result = self.validator.validate(widget_block)
        assert not result.is_valid
        assert "datasets" in result.errors[0]

    def test_empty_datasets(self):
        """æµè¯ç©ºdatasets"""
        widget_block = {
            "widgetType": "chart.js/bar",
            "props": {"type": "bar"},
            "data": {
                "labels": ["A", "B"],
                "datasets": []
            }
        }

        result = self.validator.validate(widget_block)
        assert not result.is_valid
        assert "ï¿½? in result.errors[0]

    def test_missing_labels_for_bar_chart(self):
        """æµè¯æ±ç¶å¾ç¼ºå°labels"""
        widget_block = {
            "widgetType": "chart.js/bar",
            "props": {"type": "bar"},
            "data": {
                "datasets": [
                    {
                        "label": "ç³»å1",
                        "data": [10, 20, 30]
                    }
                ]
            }
        }

        result = self.validator.validate(widget_block)
        assert not result.is_valid
        assert "labels" in result.errors[0]

    def test_invalid_data_type(self):
        """æµè¯æ°æ®ç±»åéè¯¯"""
        widget_block = {
            "widgetType": "chart.js/bar",
            "props": {"type": "bar"},
            "data": {
                "labels": ["A", "B"],
                "datasets": [
                    {
                        "label": "ç³»å1",
                        "data": ["abc", "def"]  # åºè¯¥æ¯æ°ï¿½?
                    }
                ]
            }
        }

        result = self.validator.validate(widget_block)
        assert not result.is_valid
        assert "æ°å¼ç±»ï¿½? in result.errors[0]

    def test_data_length_mismatch_warning(self):
        """æµè¯æ°æ®é¿åº¦ä¸å¹éï¼è­¦åï¿½?""
        widget_block = {
            "widgetType": "chart.js/bar",
            "props": {"type": "bar"},
            "data": {
                "labels": ["A", "B", "C"],
                "datasets": [
                    {
                        "label": "ç³»å1",
                        "data": [10, 20]  # é¿åº¦ä¸å¹ï¿½?
                    }
                ]
            }
        }

        result = self.validator.validate(widget_block)
        # é¿åº¦ä¸å¹éæ¯è­¦åï¼ä¸æ¯éï¿½?
        assert len(result.warnings) > 0
        assert "ä¸å¹ï¿½? in result.warnings[0]

    def test_scatter_chart(self):
        """æµè¯æ£ç¹å¾ï¼ç¹æ®æ°æ®æ ¼å¼ï¿½?""
        widget_block = {
            "widgetType": "chart.js/scatter",
            "props": {"type": "scatter"},
            "data": {
                "datasets": [
                    {
                        "label": "æ°æ®ï¿½?,
                        "data": [
                            {"x": 10, "y": 20},
                            {"x": 15, "y": 25}
                        ]
                    }
                ]
            }
        }

        result = self.validator.validate(widget_block)
        assert result.is_valid

    def test_non_chart_widget(self):
        """æµè¯éå¾è¡¨ç±»åçwidgetï¼åºè¯¥è·³è¿éªè¯ï¼"""
        widget_block = {
            "widgetType": "custom/widget",
            "props": {},
            "data": {}
        }

        result = self.validator.validate(widget_block)
        # échart.jsç±»åï¼è·³è¿éªè¯ï¼è¿åvalid
        assert result.is_valid


class TestChartRepairer:
    """æµè¯ChartRepairerï¿½?""

    def setup_method(self):
        """æ¯ä¸ªæµè¯ååå§å"""
        self.validator = create_chart_validator()
        self.repairer = create_chart_repairer(validator=self.validator)

    def test_repair_missing_props(self):
        """æµè¯ä¿®å¤ç¼ºå°propså­æ®µ"""
        widget_block = {
            "widgetType": "chart.js/bar",
            "data": {
                "labels": ["A", "B"],
                "datasets": [
                    {
                        "label": "ç³»å1",
                        "data": [10, 20]
                    }
                ]
            }
        }

        result = self.repairer.repair(widget_block)
        assert result.success
        assert "props" in result.repaired_block
        assert result.method == "local"

    def test_repair_missing_chart_type(self):
        """æµè¯ä¿®å¤ç¼ºå°å¾è¡¨ç±»å"""
        widget_block = {
            "widgetType": "chart.js/bar",
            "props": {},
            "data": {
                "labels": ["A", "B"],
                "datasets": [
                    {
                        "label": "ç³»å1",
                        "data": [10, 20]
                    }
                ]
            }
        }

        result = self.repairer.repair(widget_block)
        assert result.success
        assert result.repaired_block["props"]["type"] == "bar"
        assert "å¾è¡¨ç±»å" in str(result.changes)

    def test_repair_missing_datasets(self):
        """æµè¯ä¿®å¤ç¼ºå°datasets"""
        widget_block = {
            "widgetType": "chart.js/bar",
            "props": {"type": "bar"},
            "data": {
                "labels": ["A", "B"]
            }
        }

        result = self.repairer.repair(widget_block)
        assert result.success
        assert "datasets" in result.repaired_block["data"]
        assert isinstance(result.repaired_block["data"]["datasets"], list)

    def test_repair_missing_labels(self):
        """æµè¯ä¿®å¤ç¼ºå°labels"""
        widget_block = {
            "widgetType": "chart.js/bar",
            "props": {"type": "bar"},
            "data": {
                "datasets": [
                    {
                        "label": "ç³»å1",
                        "data": [10, 20, 30]
                    }
                ]
            }
        }

        result = self.repairer.repair(widget_block)
        assert result.success
        assert "labels" in result.repaired_block["data"]
        assert len(result.repaired_block["data"]["labels"]) == 3

    def test_repair_data_length_mismatch(self):
        """æµè¯ä¿®å¤æ°æ®é¿åº¦ä¸å¹ï¿½?""
        widget_block = {
            "widgetType": "chart.js/bar",
            "props": {"type": "bar"},
            "data": {
                "labels": ["A", "B", "C", "D"],
                "datasets": [
                    {
                        "label": "ç³»å1",
                        "data": [10, 20]  # é¿åº¦ä¸è¶³
                    }
                ]
            }
        }

        result = self.repairer.repair(widget_block)
        assert result.success
        # åºè¯¥è¡¥åï¿½?ä¸ªåï¿½?
        assert len(result.repaired_block["data"]["datasets"][0]["data"]) == 4

    def test_repair_string_to_number(self):
        """æµè¯ä¿®å¤å­ç¬¦ä¸²ç±»åçæ°ï¿½?""
        widget_block = {
            "widgetType": "chart.js/bar",
            "props": {"type": "bar"},
            "data": {
                "labels": ["A", "B"],
                "datasets": [
                    {
                        "label": "ç³»å1",
                        "data": ["10", "20"]  # å­ç¬¦ä¸²æ°ï¿½?
                    }
                ]
            }
        }

        result = self.repairer.repair(widget_block)
        assert result.success
        # åºè¯¥è½¬æ¢ä¸ºæ°ï¿½?
        assert isinstance(result.repaired_block["data"]["datasets"][0]["data"][0], float)

    def test_repair_construct_datasets_from_values(self):
        """æµè¯ä»valueså­æ®µæé datasets"""
        widget_block = {
            "widgetType": "chart.js/bar",
            "props": {"type": "bar"},
            "data": {
                "labels": ["A", "B"],
                "values": [10, 20]  # ä½¿ç¨valuesèä¸æ¯datasets
            }
        }

        result = self.repairer.repair(widget_block)
        assert result.success
        assert "datasets" in result.repaired_block["data"]
        assert len(result.repaired_block["data"]["datasets"]) > 0

    def test_no_repair_needed(self):
        """æµè¯ä¸éè¦ä¿®å¤çæåµ"""
        widget_block = {
            "widgetType": "chart.js/bar",
            "props": {"type": "bar"},
            "data": {
                "labels": ["A", "B"],
                "datasets": [
                    {
                        "label": "ç³»å1",
                        "data": [10, 20]
                    }
                ]
            }
        }

        result = self.repairer.repair(widget_block)
        assert result.success
        assert result.method == "none"
        assert len(result.changes) == 0

    def test_repair_adds_default_label(self):
        """æµè¯ä¿®å¤æ·»å é»è®¤label"""
        widget_block = {
            "widgetType": "chart.js/bar",
            "props": {"type": "bar"},
            "data": {
                "labels": ["A", "B"],
                "datasets": [
                    {
                        # ç¼ºå°label
                        "data": [10, 20]
                    }
                ]
            }
        }

        result = self.repairer.repair(widget_block)
        assert result.success
        assert "label" in result.repaired_block["data"]["datasets"][0]


class TestValidatorIntegration:
    """éææµè¯"""

    def test_full_validation_and_repair_workflow(self):
        """æµè¯å®æ´çéªè¯åä¿®å¤æµç¨"""
        validator = create_chart_validator()
        repairer = create_chart_repairer(validator=validator)

        # ä¸ä¸ªæå¤ä¸ªé®é¢çå¾ï¿½?
        widget_block = {
            "widgetType": "chart.js/bar",
            "data": {
                "datasets": [
                    {
                        "data": ["10", "20", "30"]  # å­ç¬¦ä¸²æ°ï¿½?
                    }
                ]
            }
        }

        # 1. éªè¯ï¼åºè¯¥å¤±è´¥ï¼
        validation = validator.validate(widget_block)
        assert not validation.is_valid

        # 2. ä¿®å¤
        repair_result = repairer.repair(widget_block, validation)
        assert repair_result.success

        # 3. åæ¬¡éªè¯ï¼åºè¯¥éè¿ï¿½?
        final_validation = validator.validate(repair_result.repaired_block)
        assert final_validation.is_valid


if __name__ == "__main__":
    # è¿è¡æµè¯
    pytest.main([__file__, "-v", "--tb=short"])
