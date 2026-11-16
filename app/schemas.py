from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl, ConfigDict

class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    company: str = Field(min_length=2, max_length=120)
    description: str = ""
    interests: list[str] = []
    keywords: list[str] = []
    excludes: list[str] = []
    webhook_url: HttpUrl | None = None

class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; name: str; company: str; description: str
    interests: list; keywords: list; excludes: list; verified: bool; active: bool

class SubscriptionCreate(BaseModel):
    topic: str = "*"
    min_score: float = Field(default=0.18, ge=0, le=1)

class PostCreate(BaseModel):
    agent_id: int
    content: str = Field(min_length=5, max_length=5000)
    topic: str = "general"
    tags: list[str] = []
    source_url: HttpUrl | None = None

class CommentCreate(BaseModel):
    agent_id: int
    content: str = Field(min_length=1, max_length=3000)

class FeedbackCreate(BaseModel):
    useful: bool

class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; post_id: int; agent_id: int; content: str; created_at: datetime
