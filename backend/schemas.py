from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any


class LoginRequest(BaseModel):
    email: str
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    business_unit: Optional[str] = None
    password: Optional[str] = None


class DocumentCreate(BaseModel):
    doc_type: str = "Contract"
    business_unit: str = "Corporate"
    counterparty: Optional[str] = None
    jurisdiction: Optional[str] = None
    confidentiality: str = "Confidential"
    review_priority: str = "Normal"


class ReviewAction(BaseModel):
    action: str = Field(..., pattern="^(approve|edit|reject|escalate|comment)$")
    risk_id: Optional[int] = None
    clause_id: Optional[int] = None
    note: Optional[str] = None
    edited_summary: Optional[str] = None
    escalation_level: Optional[str] = None


class SettingsUpdate(BaseModel):
    ai_mode: Optional[str] = None
    llm_model: Optional[str] = None
    auto_review_routing: Optional[str] = None


class RetrievalQuery(BaseModel):
    query: str
    doc_type: Optional[str] = None
    top_k: int = 5
