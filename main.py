from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean, text as sa_text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import bcrypt
from datetime import datetime, timedelta
import pandas as pd
import os
import uuid

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

engine = create_engine("sqlite:///./chance.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DBUser(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    age = Column(Integer, default=18)
    city = Column(String)
    gender = Column(String)
    attracted_to = Column(String)
    photo = Column(String)
    status = Column(String, default="Online")
    bio = Column(Text, default="")
    ai_bio_score = Column(Float, default=0.0)
    disclosure_tone = Column(String, default="Neutral")

class DBOutcomeLog(Base):
    __tablename__ = "outcome_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    outcome_type = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class DBMessage(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer)
    receiver_id = Column(Integer)
    text = Column(Text)
    tone = Column(String)
    ai_score = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=datetime.utcnow)

class DBConnectionRequest(Base):
    __tablename__ = "connection_requests"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer)
    receiver_id = Column(Integer)
    status = Column(String, default="pending")
    timestamp = Column(DateTime, default=datetime.utcnow)

class DBBlock(Base):
    __tablename__ = "blocks"
    id = Column(Integer, primary_key=True, index=True)
    blocker_id = Column(Integer)
    blocked_id = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

for col_sql in [
    "ALTER TABLE users ADD COLUMN bio TEXT DEFAULT ''",
    "ALTER TABLE users ADD COLUMN ai_bio_score REAL DEFAULT 0.0",
    "ALTER TABLE users ADD COLUMN disclosure_tone TEXT DEFAULT 'Neutral'",
    "ALTER TABLE users ADD COLUMN age INTEGER DEFAULT 18",
    "ALTER TABLE messages ADD COLUMN ai_score REAL DEFAULT 0.0",
]:
    try:
        with engine.connect() as conn:
            conn.execute(sa_text(col_sql))
            conn.commit()
    except Exception:
        pass

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@app.get("/")
def serve_index():
    return FileResponse("index.html")

class UserSignup(BaseModel):
    name: str; email: str; password: str; age: int; city: str; gender: str; attractedTo: str; photo: str; bio: Optional[str] = ""; disclosureTone: Optional[str] = "Neutral"

class UserLogin(BaseModel):
    email: str; password: str

class UserUpdate(BaseModel):
    id: int; name: str; age: int; city: str; status: str; attractedTo: str; bio: Optional[str] = ""; disclosureTone: Optional[str] = "Neutral"; photo: Optional[str] = None

class PasswordChange(BaseModel):
    id: int; oldPassword: str; newPassword: str

class MessageSend(BaseModel):
    senderId: int; receiverId: int; text: str; tone: str

class ConnectionAction(BaseModel):
    senderId: int; receiverId: int

class BlockAction(BaseModel):
    blockerId: int; blockedId: int

class OutcomeReport(BaseModel):
    userId: int; outcomeType: str

def sync_excel(db: Session):
    try:
        users = db.query(DBUser).all()
        df = pd.DataFrame([{
            "User ID": u.id, "Full Name": u.name, "Email": u.email, "Age": u.age,
            "City": u.city, "Gender": u.gender, "Attracted To": u.attracted_to,
            "Status": u.status, "Bio": u.bio or "", "Disclosure Tone": u.disclosure_tone
        } for u in users])
        df.to_excel("Users_Database.xlsx", index=False)
    except Exception:
        pass

@app.post("/api/upload-photo")
async def upload_photo(file: UploadFile = File(...)):
    file_extension = file.filename.split(".")[-1]
    file_name = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, file_name)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    return {"url": f"/uploads/{file_name}"}

@app.post("/api/log-outcome")
def log_outcome(data: OutcomeReport, db: Session = Depends(get_db)):
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_log = db.query(DBOutcomeLog).filter(
        DBOutcomeLog.user_id == data.userId,
        DBOutcomeLog.outcome_type == data.outcomeType,
        DBOutcomeLog.timestamp >= seven_days_ago
    ).first()

    if recent_log:
        raise HTTPException(400, "Cooldown active: You can only report this specific success milestone once per week.")

    if "Offline" in data.outcomeType or "Ending" in data.outcomeType or "Meeting" in data.outcomeType:
        has_connections = db.query(DBConnectionRequest).filter(
            ((DBConnectionRequest.sender_id == data.userId) | (DBConnectionRequest.receiver_id == data.userId)),
            DBConnectionRequest.status == "accepted"
        ).first()
        if not has_connections:
            raise HTTPException(400, "Milestone locked: You must have an active connection to log relational outcomes.")

    log = DBOutcomeLog(user_id=data.userId, outcome_type=data.outcomeType)
    db.add(log)
    db.commit()
    return {"status": "recorded", "message": "Thank you! Success milestone securely logged."}

@app.post("/api/signup")
def signup(user: UserSignup, db: Session = Depends(get_db)):
    email_clean = user.email.strip().lower()
    if db.query(DBUser).filter(DBUser.email == email_clean).first():
        raise HTTPException(400, "Email already exists")
    
    hashed = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
    
    new_user = DBUser(
        name=user.name, email=email_clean, password_hash=hashed.decode('utf-8'),
        age=user.age, city=user.city, gender=user.gender, attracted_to=user.attractedTo,
        photo=user.photo, bio=user.bio or "", disclosure_tone=user.disclosureTone or "Neutral"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    sync_excel(db)
    
    return {"id": new_user.id, "name": new_user.name, "email": new_user.email, "age": new_user.age, "city": new_user.city, "gender": new_user.gender, "attractedTo": new_user.attracted_to, "photo": new_user.photo, "status": new_user.status, "bio": new_user.bio or "", "disclosureTone": new_user.disclosure_tone}

@app.post("/api/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    email_clean = user.email.strip().lower()
    db_user = db.query(DBUser).filter(DBUser.email == email_clean).first()
    
    if not db_user or not bcrypt.checkpw(user.password.encode('utf-8'), db_user.password_hash.encode('utf-8')):
        raise HTTPException(400, "Invalid credentials")
        
    return {"id": db_user.id, "name": db_user.name, "email": db_user.email, "age": db_user.age, "city": db_user.city, "gender": db_user.gender, "attractedTo": db_user.attracted_to, "photo": db_user.photo, "status": db_user.status, "bio": db_user.bio or "", "disclosureTone": db_user.disclosure_tone}

@app.post("/api/update-profile")
def update_profile(data: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.id == data.id).first()
    if not user: raise HTTPException(404, "User not found")
    user.name = data.name
    user.age = data.age
    user.city = data.city
    user.status = data.status
    user.attracted_to = data.attractedTo
    user.bio = data.bio if data.bio is not None else (user.bio or "")
    user.disclosure_tone = data.disclosureTone or "Neutral"
    if data.photo:
        user.photo = data.photo
    db.commit()
    sync_excel(db)
    
    return {"id": user.id, "name": user.name, "email": user.email, "age": user.age, "city": user.city, "gender": user.gender, "attractedTo": user.attracted_to, "photo": user.photo, "status": user.status, "bio": user.bio, "disclosureTone": user.disclosure_tone}

@app.post("/api/change-password")
def change_password(data: PasswordChange, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.id == data.id).first()
    if not user or not bcrypt.checkpw(data.oldPassword.encode('utf-8'), user.password_hash.encode('utf-8')):
        raise HTTPException(400, "Incorrect old password")
    user.password_hash = bcrypt.hashpw(data.newPassword.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.commit()
    return {"status": "success"}

@app.get("/api/users")
def get_users(db: Session = Depends(get_db)):
    users = db.query(DBUser).all()
    return [{"id": u.id, "name": u.name, "city": u.city, "gender": u.gender, "attractedTo": u.attracted_to, "photo": u.photo, "status": u.status, "email": u.email, "age": u.age, "bio": u.bio or "", "disclosureTone": u.disclosure_tone} for u in users]

@app.post("/api/send-request")
def send_request(data: ConnectionAction, db: Session = Depends(get_db)):
    db.add(DBConnectionRequest(sender_id=data.senderId, receiver_id=data.receiverId, status="pending"))
    db.commit()
    return {"status": "sent"}

@app.post("/api/accept-request")
def accept_request(data: ConnectionAction, db: Session = Depends(get_db)):
    req = db.query(DBConnectionRequest).filter(DBConnectionRequest.sender_id == data.senderId, DBConnectionRequest.receiver_id == data.receiverId, DBConnectionRequest.status == "pending").first()
    if req: req.status = "accepted"; db.commit()
    return {"status": "accepted"}

@app.post("/api/reject-request")
def reject_request(data: ConnectionAction, db: Session = Depends(get_db)):
    req = db.query(DBConnectionRequest).filter(DBConnectionRequest.sender_id == data.senderId, DBConnectionRequest.receiver_id == data.receiverId, DBConnectionRequest.status == "pending").first()
    if req: req.status = "rejected"; db.commit()
    return {"status": "rejected"}

@app.get("/api/pending-requests/{userId}")
def get_pending(userId: int, db: Session = Depends(get_db)):
    inc = db.query(DBConnectionRequest).filter(DBConnectionRequest.receiver_id == userId, DBConnectionRequest.status == "pending").all()
    out = db.query(DBConnectionRequest).filter(DBConnectionRequest.sender_id == userId, DBConnectionRequest.status == "pending").all()
    return {"incoming": [{"senderId": r.sender_id} for r in inc], "outgoing": [{"receiverId": r.receiver_id} for r in out]}

@app.get("/api/connections/{userId}")
def get_conns(userId: int, db: Session = Depends(get_db)):
    accepted = db.query(DBConnectionRequest).filter(((DBConnectionRequest.sender_id == userId) | (DBConnectionRequest.receiver_id == userId)), DBConnectionRequest.status == "accepted").all()
    return {"connections": [r.receiver_id if r.sender_id == userId else r.sender_id for r in accepted]}

@app.post("/api/block")
def block(data: BlockAction, db: Session = Depends(get_db)):
    db.add(DBBlock(blocker_id=data.blockerId, blocked_id=data.blockedId))
    db.commit()
    return {"status": "blocked"}

@app.post("/api/unblock")
def unblock(data: BlockAction, db: Session = Depends(get_db)):
    b = db.query(DBBlock).filter(DBBlock.blocker_id == data.blockerId, DBBlock.blocked_id == data.blockedId).first()
    if b: db.delete(b); db.commit()
    return {"status": "unblocked"}

@app.get("/api/blocked/{userId}")
def get_blocked(userId: int, db: Session = Depends(get_db)):
    return {"blocked": [b.blocked_id for b in db.query(DBBlock).filter(DBBlock.blocker_id == userId).all()]}

@app.post("/api/messages")
def send_msg(msg: MessageSend, db: Session = Depends(get_db)):
    db.add(DBMessage(sender_id=msg.senderId, receiver_id=msg.receiverId, text=msg.text, tone=msg.tone, ai_score=0.0))
    db.commit()
    return {"status": "sent"}

@app.get("/api/messages/{u1}/{u2}")
def get_msgs(u1: int, u2: int, db: Session = Depends(get_db)):
    msgs = db.query(DBMessage).filter(((DBMessage.sender_id == u1) & (DBMessage.receiver_id == u2)) | ((DBMessage.sender_id == u2) & (DBMessage.receiver_id == u1))).order_by(DBMessage.timestamp.asc()).all()
    return [{"senderId": m.sender_id, "receiverId": m.receiver_id, "text": m.text, "tone": m.tone, "aiScore": m.ai_score} for m in msgs]
