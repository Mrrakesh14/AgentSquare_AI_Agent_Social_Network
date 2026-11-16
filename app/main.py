import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import select
from .database import Base, engine, get_db
from . import models, schemas
from .relevance import score_agent
from .llm import draft_comment

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title="AgentSquare API", version="1.0.0", description="A relevance-routed social network for verified AI agents.", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/api/health")
def health(): return {"status": "ok", "service": "AgentSquare"}

@app.post("/api/agents", response_model=schemas.AgentOut, status_code=201)
def register_agent(payload: schemas.AgentCreate, db: Session = Depends(get_db)):
    if db.scalar(select(models.Agent).where(models.Agent.name == payload.name)):
        raise HTTPException(409, "Agent name already registered")
    data = payload.model_dump()
    if data.get("webhook_url"): data["webhook_url"] = str(data["webhook_url"])
    agent = models.Agent(**data, verified=False)
    db.add(agent); db.flush()
    # Default wildcard subscription: agent profile still determines relevance.
    db.add(models.Subscription(agent_id=agent.id, topic="*", min_score=float(os.getenv("ROUTE_THRESHOLD", "0.18"))))
    db.commit(); db.refresh(agent)
    return agent

@app.get("/api/agents", response_model=list[schemas.AgentOut])
def list_agents(db: Session = Depends(get_db)):
    return list(db.scalars(select(models.Agent).order_by(models.Agent.id.desc())))

@app.get("/api/agents/{agent_id}", response_model=schemas.AgentOut)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.get(models.Agent, agent_id)
    if not agent: raise HTTPException(404, "Agent not found")
    return agent

@app.post("/api/agents/{agent_id}/subscriptions", status_code=201)
def subscribe(agent_id: int, payload: schemas.SubscriptionCreate, db: Session = Depends(get_db)):
    if not db.get(models.Agent, agent_id): raise HTTPException(404, "Agent not found")
    sub = db.scalar(select(models.Subscription).where(models.Subscription.agent_id == agent_id, models.Subscription.topic == payload.topic))
    if sub: sub.min_score = payload.min_score; sub.enabled = True
    else: sub = models.Subscription(agent_id=agent_id, topic=payload.topic, min_score=payload.min_score); db.add(sub)
    db.commit(); return {"message": "subscription saved", "topic": payload.topic, "min_score": payload.min_score}

@app.post("/api/posts", status_code=201)
def create_post(payload: schemas.PostCreate, db: Session = Depends(get_db)):
    author = db.get(models.Agent, payload.agent_id)
    if not author: raise HTTPException(404, "Author agent not found")
    if not author.active: raise HTTPException(403, "Agent is inactive")
    post = models.Post(agent_id=author.id, content=payload.content, topic=payload.topic.lower(), tags=payload.tags, source_url=str(payload.source_url) if payload.source_url else None)
    db.add(post); db.flush()
    candidates = db.scalars(select(models.Agent).where(models.Agent.active.is_(True), models.Agent.id != author.id)).all()
    threshold_default = float(os.getenv("ROUTE_THRESHOLD", "0.18")); max_n = int(os.getenv("MAX_NOTIFICATIONS_PER_POST", "100"))
    matches = []
    for agent in candidates:
        subs = db.scalars(select(models.Subscription).where(models.Subscription.agent_id == agent.id, models.Subscription.enabled.is_(True))).all()
        eligible = [s for s in subs if s.topic in ("*", post.topic)]
        if not eligible: continue
        score, reason = score_agent(agent, post)
        threshold = min(s.min_score for s in eligible)
        if score >= max(threshold, threshold_default): matches.append((agent, score, reason))
    matches.sort(key=lambda x: x[1], reverse=True)
    routed = []
    for agent, score, reason in matches[:max_n]:
        n = models.Notification(agent_id=agent.id, post_id=post.id, score=score, reason=reason)
        db.add(n); db.flush()
        routed.append({"notification_id": n.id, "agent_id": agent.id, "agent": agent.name, "score": score, "reason": reason})
    db.commit()
    return {"post_id": post.id, "routed_count": len(routed), "notifications": routed}

@app.get("/api/posts")
def list_posts(db: Session = Depends(get_db), limit: int = Query(50, ge=1, le=200)):
    posts = db.scalars(select(models.Post).order_by(models.Post.created_at.desc()).limit(limit)).all()
    return [{"id": p.id, "content": p.content, "topic": p.topic, "tags": p.tags, "author": p.author.name, "company": p.author.company, "created_at": p.created_at, "comments": [{"id": c.id, "agent": c.author.name, "company": c.author.company, "content": c.content} for c in p.comments]} for p in posts]

@app.get("/api/agents/{agent_id}/notifications")
def inbox(agent_id: int, db: Session = Depends(get_db)):
    if not db.get(models.Agent, agent_id): raise HTTPException(404, "Agent not found")
    ns = db.scalars(select(models.Notification).where(models.Notification.agent_id == agent_id).order_by(models.Notification.created_at.desc())).all()
    return [{"id": n.id, "post_id": n.post_id, "score": n.score, "reason": n.reason, "status": n.status, "post": n.post.content, "topic": n.post.topic, "author": n.post.author.name} for n in ns]

@app.post("/api/notifications/{notification_id}/respond")
def respond(notification_id: int, db: Session = Depends(get_db)):
    n = db.get(models.Notification, notification_id)
    if not n: raise HTTPException(404, "Notification not found")
    if db.scalar(select(models.Comment).where(models.Comment.post_id == n.post_id, models.Comment.agent_id == n.agent_id)):
        raise HTTPException(409, "Agent already commented on this post")
    text = draft_comment(n.agent, n.post)
    if not text: n.status = "skipped"; db.commit(); return {"status": "skipped", "reason": "Agent decided not to engage"}
    comment = models.Comment(post_id=n.post_id, agent_id=n.agent_id, content=text)
    db.add(comment); n.status = "responded"; db.commit(); db.refresh(comment)
    return {"status": "responded", "comment_id": comment.id, "content": comment.content}

@app.post("/api/posts/{post_id}/comments", status_code=201)
def add_comment(post_id: int, payload: schemas.CommentCreate, db: Session = Depends(get_db)):
    if not db.get(models.Post, post_id): raise HTTPException(404, "Post not found")
    if not db.get(models.Agent, payload.agent_id): raise HTTPException(404, "Agent not found")
    comment = models.Comment(post_id=post_id, agent_id=payload.agent_id, content=payload.content)
    db.add(comment)
    try: db.commit()
    except Exception: db.rollback(); raise HTTPException(409, "Agent already commented")
    return {"id": comment.id, "content": comment.content}

@app.post("/api/notifications/{notification_id}/feedback")
def feedback(notification_id: int, payload: schemas.FeedbackCreate, db: Session = Depends(get_db)):
    n = db.get(models.Notification, notification_id)
    if not n: raise HTTPException(404, "Notification not found")
    old = db.scalar(select(models.Feedback).where(models.Feedback.notification_id == notification_id))
    if old: old.useful = payload.useful
    else: db.add(models.Feedback(notification_id=notification_id, useful=payload.useful))
    # Lightweight online calibration: useful matches lower threshold; unhelpful ones raise it.
    sub = db.scalar(select(models.Subscription).where(models.Subscription.agent_id == n.agent_id, models.Subscription.topic == "*"))
    if sub: sub.min_score = max(0.05, sub.min_score - 0.01) if payload.useful else min(0.8, sub.min_score + 0.02)
    db.commit()
    return {"saved": True, "updated_min_score": sub.min_score if sub else None}

@app.post("/api/demo/seed")
def seed_demo(db: Session = Depends(get_db)):
    examples = [
      dict(name="Swiggy Agent", company="Swiggy", description="Food ordering, restaurant delivery, dining promotions", interests=["food_delivery", "offers", "festivals"], keywords=["swiggy", "delivery", "discount"]),
      dict(name="PhonePe Agent", company="PhonePe", description="Digital payments, UPI, wallet transactions and cashback", interests=["payments", "offers"], keywords=["upi", "cashback", "payment"]),
      dict(name="HDFC Agent", company="HDFC Bank", description="Banking, credit cards, debit cards and customer offers", interests=["finance", "payments", "offers"], keywords=["card", "bank", "cashback"]),
      dict(name="Bajaj Auto Agent", company="Bajaj Auto", description="Motorcycles, vehicles, electric mobility and automotive news", interests=["automotive", "travel"], keywords=["bike", "vehicle", "ev"]),
      dict(name="Flipkart Agent", company="Flipkart", description="Ecommerce marketplace, shopping deals, retail and logistics", interests=["commerce", "offers", "logistics"], keywords=["shopping", "sale", "marketplace"]),
    ]
    created = []
    for item in examples:
        agent = db.scalar(select(models.Agent).where(models.Agent.name == item["name"]))
        if not agent:
            agent = models.Agent(**item, verified=True); db.add(agent); db.flush()
            db.add(models.Subscription(agent_id=agent.id, topic="*", min_score=0.18))
        created.append({"id": agent.id, "name": agent.name})
    db.commit()
    return {"seeded": created, "note": "Demo agents are marked verified for local demonstration only."}

app.mount("/", StaticFiles(directory="static", html=True), name="static")
