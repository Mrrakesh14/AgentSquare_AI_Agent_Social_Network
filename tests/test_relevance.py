from types import SimpleNamespace
from app.relevance import score_agent

def agent(**kwargs):
    base=dict(description="Digital payments, UPI and cashback offers", interests=["payments", "offers"], keywords=["upi", "cashback"], excludes=[])
    base.update(kwargs); return SimpleNamespace(**base)

def post(**kwargs):
    base=dict(content="5% off all food deliveries on Diwali. Pay with UPI and get cashback.", topic="offers", tags=["diwali", "discount"])
    base.update(kwargs); return SimpleNamespace(**base)

def test_payment_agent_matches_food_delivery_offer():
    score, reason=score_agent(agent(), post())
    assert score > 0.18
    assert "related concepts" in reason

def test_automotive_agent_does_not_match_payment_offer():
    a=agent(description="Motorcycles, cars, electric vehicles", interests=["automotive"], keywords=["bike", "vehicle"])
    score,_=score_agent(a,post())
    assert score < 0.18

def test_excluded_terms_block_match():
    a=agent(excludes=["diwali"])
    score,reason=score_agent(a,post())
    assert score == 0
    assert "excluded" in reason
