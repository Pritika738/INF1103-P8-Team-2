import json

import pytest

from ai_manager import AIManager, AIServiceError
from app import Application
from data_manager import DataManager, JsonRecordRepository, SqliteRecordRepository
from data_manager import ConsultationPdfArchive, OriginalReportArchive
from io_manager import ConsoleInterface, IOManager, InputValidator, UserInterface
from models import RecordQuery, UploadedReport
from tests.helpers import FakeAIClient, ScriptedInterface, all_supported_json, extraction_json


# --------------------------------------------------------------------------
# IO Manager
# --------------------------------------------------------------------------

class TestInputValidator:
    def test_number_reprompts_then_accepts(self):
        ui = ScriptedInterface(["abc", "12.5"])
        assert InputValidator(ui).number("n: ") == 12.5
        assert "valid number" in ui.text

    def test_number_blank_is_none(self):
        assert InputValidator(ScriptedInterface([""])).number("n: ") is None

    def test_non_empty_string(self):
        ui = ScriptedInterface(["", "  ", " hi "])
        assert InputValidator(ui).non_empty_string("s: ") == "hi"

    def test_optional_date(self):
        ui = ScriptedInterface(["2026-13-01", "2026-02-30", "2026-02-10"])
        assert InputValidator(ui).optional_date("d: ") == "2026-02-10"
        assert InputValidator(ScriptedInterface([""])).optional_date("d: ") is None

    def test_confirm(self):
        assert InputValidator(ScriptedInterface(["maybe", "Y"])).confirm("ok?") is True
        assert InputValidator(ScriptedInterface(["no"])).confirm("ok?") is False

    def test_choice(self):
        assert InputValidator(ScriptedInterface(["9", "2"])).choice("c: ", ["1", "2"]) == "2"


class TestIOManager:
    def test_interface_implementations_are_substitutable(self):
        assert issubclass(ConsoleInterface, UserInterface)
        assert issubclass(ScriptedInterface, UserInterface)
        with pytest.raises(TypeError):
            UserInterface()

    def test_menu_shows_all_options(self):
        ui = ScriptedInterface(["3"])
        io = IOManager(ui)
        io.show_main_menu()
        assert io.get_menu_choice() == "3"
        assert "Exit" in ui.text and "Summary report" in ui.text

    def test_prompt_report_file_reads_supported_file(self, tmp_path):
        path = tmp_path / "r.PDF"
        path.write_bytes(b"data")
        report = IOManager(ScriptedInterface([str(path)])).prompt_report_file()
        assert report.data == b"data" and report.mime_type == "application/pdf"
        assert report.filename == "r.PDF"

    def test_prompt_report_file_rejects_bad_input(self, tmp_path):
        text = tmp_path / "x.txt"
        text.write_text("hi")
        for answer in (str(text), str(tmp_path / "missing.pdf"), ""):
            ui = ScriptedInterface([answer])
            assert IOManager(ui).prompt_report_file() is None

    def test_prompt_report_file_too_large(self, tmp_path, monkeypatch):
        path = tmp_path / "big.pdf"
        path.write_bytes(b"12345")
        monkeypatch.setattr(IOManager, "MAX_UPLOAD_BYTES", 2)
        ui = ScriptedInterface([str(path)])
        assert IOManager(ui).prompt_report_file() is None
        assert "too large" in ui.text

    def test_supported_types(self):
        io = IOManager(ScriptedInterface())
        assert io.is_supported_upload_type("image/png")
        assert not io.is_supported_upload_type("text/plain")

    def test_prompt_record_query(self):
        io = IOManager(ScriptedInterface(["2026-01-01", "", "urgent"]))
        query = io.prompt_record_query()
        assert (query.date_from, query.date_to, query.decision) == ("2026-01-01", None, "URGENT")

    def test_show_empty_history(self):
        ui = ScriptedInterface()
        IOManager(ui).show_health_records([])
        assert "No health records" in ui.text


# --------------------------------------------------------------------------
# Pipeline + application (fake AI, temp storage)
# --------------------------------------------------------------------------

def build_app(tmp_path, responses, answers=(), repository=None):
    data = DataManager(
        repository or JsonRecordRepository(str(tmp_path / "records.json")),
        OriginalReportArchive(str(tmp_path / "orig"), str(tmp_path / "orig.json")),
        ConsultationPdfArchive(str(tmp_path / "pdf"), str(tmp_path / "pdf.json")),
    )
    client = FakeAIClient(responses)
    ui = ScriptedInterface(list(answers))
    from logic_manager import LogicManager
    app = Application(IOManager(ui), AIManager(client, max_retries=2), LogicManager(), data)
    return app, client, ui


@pytest.fixture(params=["json", "sqlite"])
def repo(request, tmp_path):
    if request.param == "json":
        return JsonRecordRepository(str(tmp_path / "records.json"))
    return SqliteRecordRepository(str(tmp_path / "records.db"))


class TestReportPipeline:
    urgent = extraction_json(heart_rate=150, report_date="2026-05-01")

    def test_record_passes_through_ai_logic_and_data(self, tmp_path, repo):
        app, client, _ = build_app(tmp_path, [self.urgent, all_supported_json()], repository=repo)
        result = app.pipeline.process_and_store(UploadedReport(b"pdf", "application/pdf", "r.pdf"), "ann")
        assert client.call_count == 2          # AI was used (extract + verify)
        assert result.saved
        stored = app.data.load_health_records()[0]
        assert stored["decision"] == "URGENT"  # AI output influenced the rule outcome
        assert stored["date"] == "2026-05-01" and stored["username"] == "ann"
        assert app.data.get_original_report_by_id(stored["report_id"]) is not None

    def test_ai_failure_is_not_stored_and_does_not_crash(self, tmp_path):
        app, _, _ = build_app(tmp_path, [AIServiceError("down")] * 2)
        result = app.pipeline.process_and_store(UploadedReport(b"x", "application/pdf"), "ann")
        assert result.record["decision"] == "REJECTED"
        assert not result.saved
        assert app.data.load_health_records() == []

    def test_non_medical_document_never_reaches_history(self, tmp_path):
        text = extraction_json(is_medical_report=False, classification_reason="timetable")
        app, _, _ = build_app(tmp_path, [text])
        result = app.pipeline.process_and_store(UploadedReport(b"x", "application/pdf"), "ann")
        assert result.record["decision"] == "NOT_MEDICAL_REPORT"
        assert app.data.load_health_records() == []

    def test_history_is_per_user_and_drives_trend_rule(self, tmp_path):
        app, _, _ = build_app(tmp_path, [])
        for day, glucose in (("2026-01-01", 7.5), ("2026-02-01", 8.0)):
            app.data.save_record({"username": "ann", "date": day, "metrics": {"blood_glucose": glucose}})
        app.data.save_record({"username": "bob", "date": "2026-02-15", "metrics": {"blood_glucose": 99}})
        text = extraction_json(blood_glucose=9.0, report_date="2026-03-01")
        app.ai._client._responses.extend([text, all_supported_json()])
        result = app.pipeline.process_and_store(UploadedReport(b"x", "application/pdf"), "ann")
        assert result.record["decision"] == "FLAGGED"

    def test_consultation_summary_uses_ai_and_can_fail_softly(self, tmp_path):
        app, _, _ = build_app(tmp_path, [json.dumps({"narrative": "Notes."}), "junk", "junk"])
        assert app.pipeline.generate_consultation_summary({"decision": "ACCEPTED"}) == "Notes."
        assert app.pipeline.generate_consultation_summary({"decision": "ACCEPTED"}) is None


class TestApplicationMenu:
    def test_invalid_option_then_exit(self, tmp_path):
        app, _, ui = build_app(tmp_path, [], answers=["x", "4"])
        app.run()
        assert "Invalid option" in ui.text and "Goodbye" in ui.text

    def test_upload_then_view_history_then_summary_report(self, tmp_path):
        report_file = tmp_path / "report.pdf"
        report_file.write_bytes(b"pdf")
        responses = [extraction_json(heart_rate=150, report_date="2026-05-01"), all_supported_json()]
        answers = ["1", str(report_file), "2", "3", "", "", "", "4"]
        app, _, ui = build_app(tmp_path, responses, answers=answers)
        app.run()
        assert "Record saved." in ui.text
        assert "Health History (1 record(s))" in ui.text
        assert "Health Summary Report" in ui.text
        assert "Heart Rate: latest 150" in ui.text

    def test_summary_report_filters_apply(self, tmp_path):
        app, _, ui = build_app(tmp_path, [], answers=["3", "2026-06-01", "", "", "4"])
        app.data.save_record({"username": Application.DEFAULT_USERNAME, "date": "2026-01-01",
                              "decision": "ACCEPTED", "metrics": {"heart_rate": 70}})
        app.run()
        assert "Records analysed: 0" in ui.text

    def test_non_medical_upload_message(self, tmp_path):
        report_file = tmp_path / "t.png"
        report_file.write_bytes(b"png")
        text = extraction_json(is_medical_report=False, classification_reason="timetable")
        app, _, ui = build_app(tmp_path, [text], answers=["1", str(report_file), "4"])
        app.run()
        assert "not added to your health history" in ui.text

    def test_create_factory_builds_the_object_graph(self, tmp_path):
        app = Application.create(ai_client=FakeAIClient([]), ui=ScriptedInterface([]),
                                 repository=JsonRecordRepository(str(tmp_path / "r.json")))
        assert app.pipeline is not None and app.io and app.ai and app.logic and app.data
