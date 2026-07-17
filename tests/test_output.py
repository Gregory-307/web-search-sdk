import csv
import json

from web_search_sdk.utils.output import to_csv, to_json


def test_to_json_append(tmp_path):
    fp = tmp_path / "out.json"
    to_json({"a": 1}, fp)
    to_json({"b": 2}, fp, append=True)
    data = json.loads(fp.read_text("utf-8"))
    assert data == [{"a": 1}, {"b": 2}]


def test_to_csv_append(tmp_path):
    fp = tmp_path / "out.csv"
    to_csv([{"a": 1, "b": 2}], fp)
    to_csv([{"a": 3, "b": 4}], fp, append=True)
    rows = list(csv.DictReader(fp.open()))
    assert rows == [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]
