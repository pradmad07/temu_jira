from app.services.duplicates import DuplicateDetector
from tests.helpers import make_incident

def test_similar_report_is_suggested():   # TODO(Pradhyumn)
    new = make_incident(title="Unable to make payment", description="payment page fails")
    old = make_incident(title="Payment application unavailable", description="payment transactions failing")
    assert old in [i for i, _ in DuplicateDetector().find_candidates(new, [old])]

def test_unrelated_report_not_suggested():
    new = make_incident(title="Payment down", description="payment fails")
    other = make_incident(title="Printer jammed", description="third floor printer paper jam")
    assert DuplicateDetector().find_candidates(new, [other]) == []
