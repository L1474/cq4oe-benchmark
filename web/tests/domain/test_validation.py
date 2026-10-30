from pathlib import Path

from web.domain.catalog import _cq_file, _load_cqs
from web.domain.validation import validate_cq2onto_confirmation, validate_cq_term_prediction


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _valid_prediction():
    return [
        {"id": cq["id"], "value": cq["value"], "class": [], "property": []}
        for cq in _load_cqs(_cq_file(PROJECT_ROOT, "cq2term", "wine"))
    ]


def test_valid_cq2term_prediction_passes():
    assert validate_cq_term_prediction(PROJECT_ROOT, "wine", _valid_prediction()).valid


def test_cq2term_rejects_missing_duplicate_unknown_ids_and_bad_arrays():
    prediction = _valid_prediction()
    assert not validate_cq_term_prediction(PROJECT_ROOT, "wine", prediction[:-1]).valid

    duplicate = prediction + [prediction[0]]
    assert not validate_cq_term_prediction(PROJECT_ROOT, "wine", duplicate).valid

    unknown = prediction[:-1] + [{**prediction[-1], "id": "UNKNOWN"}]
    assert not validate_cq_term_prediction(PROJECT_ROOT, "wine", unknown).valid

    malformed = [{**prediction[0], "class": ["Wine"], "property": "hasColor"}] + prediction[1:]
    assert not validate_cq_term_prediction(PROJECT_ROOT, "wine", malformed).valid


def test_cq2term_requires_list_of_object_rows():
    assert not validate_cq_term_prediction(PROJECT_ROOT, "wine", {}).valid
    assert not validate_cq_term_prediction(PROJECT_ROOT, "wine", ["CQ1"]).valid


def test_cq2onto_confirmation_requires_each_expected_id_exactly_once():
    cqs = _load_cqs(_cq_file(PROJECT_ROOT, "cq2onto", "wine"))
    ids = [cq["id"] for cq in cqs]

    assert validate_cq2onto_confirmation(PROJECT_ROOT, "wine", ids).valid
    assert not validate_cq2onto_confirmation(PROJECT_ROOT, "wine", ids[:-1]).valid
    assert not validate_cq2onto_confirmation(PROJECT_ROOT, "wine", ids + [ids[0]]).valid
    assert not validate_cq2onto_confirmation(PROJECT_ROOT, "wine", ids[:-1] + ["UNKNOWN"]).valid
