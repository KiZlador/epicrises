import unittest
from unittest.mock import Mock

from domain.config import Settings
from extraction.citation_candidates import candidate_lines
from extraction.llm import LocalModel

TEXT = """Гипертоническая болезнь II стадии.
Сахарный диабет отрицает.
ЭКГ: подъёма ST не зарегистрировано.
Поступил 01.01.2024.
"""


class CitationSelection(unittest.TestCase):
    def test_absence_requires_negative_statement_for_that_field(self):
        selected = candidate_lines(
            TEXT.splitlines(),
            {"art_hyper": "0", "dm": "0", "copd": "0", "ecg_avb": "0", "ecg_elevation": "0"},
        )
        self.assertEqual(
            selected, {"art_hyper": [], "dm": [2], "copd": [], "ecg_avb": [], "ecg_elevation": [3]}
        )

    def model(self, content):
        model = LocalModel(Settings())
        model._model = Mock()
        model._model.create_chat_completion.return_value = {
            "choices": [{"finish_reason": "stop", "message": {"content": content}}]
        }
        return model

    def test_model_selects_literal_source_without_rewriting(self):
        model = self.model('{"dm":2,"copd":2}')
        self.assertEqual(
            model.locate_evidence(TEXT, {"dm": "0", "copd": "0"}),
            {"dm": "Сахарный диабет отрицает."},
        )
        schema = model._model.create_chat_completion.call_args.kwargs["response_format"]["schema"]
        self.assertEqual(schema["properties"], {"dm": {"enum": [None, 2]}})

    def test_ineligible_source_line_is_rejected(self):
        model = self.model('{"dm":1}')
        self.assertEqual(model.locate_evidence(TEXT, {"dm": "0"}), {})

    def test_no_candidates_skips_inference(self):
        model = self.model("{}")
        self.assertEqual(model.locate_evidence(TEXT, {"copd": "0"}), {})
        model._model.create_chat_completion.assert_not_called()


if __name__ == "__main__":
    unittest.main()
