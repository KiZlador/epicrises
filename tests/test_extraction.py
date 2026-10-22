import unittest
from unittest.mock import Mock

from epicrises.processing.inference.local_model import LocalModel
from epicrises.processing.inference.response_review import apply_review
from epicrises.processing.processing_types import Hit
from epicrises.processing.rules.normalization import normalize_hits
from epicrises.shared.field_schema import NA
from epicrises.shared.settings import Settings


class ReviewContracts(unittest.TestCase):
    def test_invalid_rule_values_use_field_defaults_without_mutating_evidence(self):
        hits = {
            "dm": Hit("unknown", "Исходная цитата", warn=["original warning"]),
            "ca_fact": Hit("unknown"),
            "type_acs": Hit("unknown"),
            "mi_localisation": Hit("unknown"),
            "glu": Hit("5,2", "Глюкоза 5,2 ммоль/л"),
            "height": Hit("500"),
        }
        normalized = normalize_hits(hits)
        self.assertEqual(
            {key: hit.value for key, hit in normalized.items()},
            {
                "dm": "0",
                "ca_fact": "N",
                "type_acs": "NA",
                "mi_localisation": "N",
                "glu": "5.2",
                "height": NA,
            },
        )
        self.assertEqual(hits["glu"].value, "5,2")
        self.assertEqual(hits["dm"].warn, ["original warning"])
        self.assertEqual(normalized["dm"].ev, "")
        self.assertEqual(normalized["glu"].ev, hits["glu"].ev)

    def test_review_only_applies_valid_requested_changes_and_keeps_rule_evidence(self):
        hits = {
            "glu": Hit("5.2", "Глюкоза 5,2", warn=["review"]),
            "height": Hit("170", "Рост 170 см"),
            "dm": Hit("0"),
            "ace_ing_sartan": Hit(NA),
        }
        reviewed, changes, warnings = apply_review(
            hits,
            {
                "glu": " 6,1 ",
                "height": "500",
                "dm": "1",
                "ace_ing_sartan": "Аторвастатин 80 мг вечером",
            },
            ["glu", "height", "ace_ing_sartan"],
        )
        self.assertEqual(changes, {"glu": {"before": "5.2", "after": "6.1"}})
        self.assertEqual(reviewed["glu"].value, "6.1")
        self.assertEqual(reviewed["glu"].ev, "")
        self.assertEqual(reviewed["height"].value, "170")
        self.assertEqual(reviewed["dm"].value, "0")
        self.assertEqual(reviewed["ace_ing_sartan"].value, NA)
        self.assertEqual(len(warnings), 2)
        reviewed["height"].warn.append("later cross-check")
        self.assertEqual(hits["height"].warn, [])
        self.assertEqual(hits["glu"].ev, "Глюкоза 5,2")


class ModelResponseContracts(unittest.TestCase):
    def model(self, content, finish_reason="stop"):
        model = LocalModel(Settings())
        model._model = Mock()
        model._model.create_chat_completion.return_value = {
            "choices": [{"finish_reason": finish_reason, "message": {"content": content}}]
        }
        return model

    def test_truncated_answers_are_rejected_in_both_model_workflows(self):
        model = self.model('{"dm":"0"}', finish_reason="length")
        with self.assertRaisesRegex(RuntimeError, "MODEL_MAX_TOKENS"):
            model.review("Сахарный диабет отрицает.", ["dm"], {"dm": "0"}, {"triggered_rules": {}})
        with self.assertRaisesRegex(RuntimeError, "MODEL_MAX_TOKENS"):
            model.locate_evidence("Сахарный диабет отрицает.", {"dm": "0"})

    def test_non_object_answers_are_rejected_in_both_model_workflows(self):
        model = self.model("[]")
        with self.assertRaisesRegex(ValueError, "JSON-контракта"):
            model.review("Сахарный диабет отрицает.", ["dm"], {"dm": "0"}, {"triggered_rules": {}})
        with self.assertRaisesRegex(ValueError, "JSON-контракта"):
            model.locate_evidence("Сахарный диабет отрицает.", {"dm": "0"})


if __name__ == "__main__":
    unittest.main()
