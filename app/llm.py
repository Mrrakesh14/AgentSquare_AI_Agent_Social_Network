import os

def draft_comment(agent, post) -> str:
    """Use OpenAI when configured; otherwise provide a clearly deterministic demo reply."""
    key = os.getenv("OPENAI_API_KEY")
    if key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=key)
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                temperature=0.4,
                messages=[
                    {"role": "system", "content": f"You are {agent.name}, an AI agent representing {agent.company}. Write one concise, useful, factual comment only if you can add relevant value. Do not invent partnerships, prices, or commitments. If you cannot add value, return exactly SKIP."},
                    {"role": "user", "content": f"Post: {post.content}\nYour interests: {', '.join(agent.interests or [])}"},
                ],
            )
            result = (response.choices[0].message.content or "").strip()
            return "" if result.upper() == "SKIP" else result
        except Exception:
            pass
    topic = (post.topic or "this update").replace("_", " ")
    if "payment" in topic or "finance" in topic:
        return f"We can explore a relevant payment or financial benefit for customers engaging with this {topic} update."
    return f"This is relevant to our {', '.join(agent.interests[:2]) or 'business'} focus. We would be interested in exploring a useful customer benefit."
