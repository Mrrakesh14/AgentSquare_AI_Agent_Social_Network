"""Explainable hybrid relevance: concept expansion + TF-IDF cosine + explicit topic/tag rules."""
import math, re
from collections import Counter

# Small domain ontology makes related concepts match without an external embedding service.
CONCEPTS = {
    "payments": {"payment", "payments", "upi", "wallet", "transaction", "checkout", "cashback", "card", "banking"},
    "food_delivery": {"food", "delivery", "restaurant", "swiggy", "zomato", "order", "meal", "dining"},
    "commerce": {"shopping", "ecommerce", "e-commerce", "retail", "flipkart", "seller", "marketplace", "product"},
    "finance": {"finance", "bank", "banking", "credit", "debit", "loan", "insurance", "interest", "hdfc"},
    "automotive": {"auto", "automotive", "vehicle", "car", "bike", "motorcycle", "bajaj", "ev", "electric vehicle"},
    "offers": {"offer", "offers", "discount", "deal", "promotion", "coupon", "sale", "cashback"},
    "festivals": {"diwali", "festival", "festive", "holi", "christmas", "new year"},
    "logistics": {"shipping", "delivery", "logistics", "warehouse", "supply", "fulfillment", "fulfilment"},
    "travel": {"travel", "flight", "hotel", "booking", "ticket", "mobility"},
}
STOP = {"the", "and", "for", "with", "from", "this", "that", "are", "all", "your", "our", "will", "when", "into", "on", "to", "a", "an", "of", "in", "is", "by", "be"}

def tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in STOP and len(w) > 1]

def expand(text: str) -> set[str]:
    words = set(tokens(text))
    expanded = set(words)
    for concept, members in CONCEPTS.items():
        if words & members or concept in words:
            expanded.update(members)
            expanded.add(concept)
    return expanded

def cosine(a: set[str], b: set[str]) -> float:
    if not a or not b: return 0.0
    # Binary TF-IDF-like weighting: downweights generic words shared by large profiles.
    common = a & b
    if not common: return 0.0
    weights = {w: 1.0 / (1.0 + math.log1p(sum(w in group for group in CONCEPTS.values()))) for w in a | b}
    dot = sum(weights[w] ** 2 for w in common)
    na = math.sqrt(sum(weights[w] ** 2 for w in a)); nb = math.sqrt(sum(weights[w] ** 2 for w in b))
    return dot / (na * nb) if na and nb else 0.0

def score_agent(agent, post) -> tuple[float, str]:
    profile = " ".join([agent.description or "", *(agent.interests or []), *(agent.keywords or [])])
    content = " ".join([post.content, post.topic, *(post.tags or [])])
    p_tokens = set(tokens(content))
    blocked = set(tokens(" ".join(agent.excludes or [])))
    if blocked and blocked & p_tokens:
        return 0.0, "excluded terms: " + ", ".join(sorted(blocked & p_tokens))
    semantic = cosine(expand(profile), expand(content))
    interests = {x.lower().strip() for x in (agent.interests or [])}
    topic_match = 1.0 if post.topic.lower() in interests or "*" in interests else 0.0
    explicit = {x.lower().strip() for x in (agent.keywords or [])}
    explicit_hits = explicit & p_tokens
    tag_hits = {x.lower().strip() for x in (post.tags or [])} & (interests | explicit)
    keyword_score = min(1.0, (len(explicit_hits) + len(tag_hits)) / 2.0)
    score = min(1.0, 0.55 * semantic + 0.25 * topic_match + 0.20 * keyword_score)
    reasons = []
    if semantic >= 0.08: reasons.append("related concepts")
    if topic_match: reasons.append("subscribed topic")
    if explicit_hits or tag_hits: reasons.append("matching keywords/tags")
    return round(score, 4), ", ".join(reasons) or "weak semantic overlap"
