from app.services.fingerprint_utils import evidence_signature


def test_evidence_signature_stable_for_different_list_order() -> None:
    a = {
        "group_id": "g1",
        "pairs": [{"left": "a", "right": "b"}, {"left": "c", "right": "d"}],
    }
    b = {
        "pairs": [{"right": "d", "left": "c"}, {"right": "b", "left": "a"}],
        "group_id": "g1",
    }
    assert evidence_signature(a) == evidence_signature(b)
