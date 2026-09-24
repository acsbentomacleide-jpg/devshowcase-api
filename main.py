from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.sql import func
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./devshowcase.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ProjectDB(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    technology = Column(String, index=True, nullable=False)
    upvotes = Column(Integer, default=0)
    average_rating = Column(Float, default=0.0)

class FeedbackDB(Base):
    __tablename__ = "feedbacks"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DevShowcase API",
    description="API para apresentação, avaliação e upvotes de projetos de desenvolvedores.",
    version="1.0.0",
    docs_url="/swagger",
    redoc_url="/redoc"
)

class FeedbackCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Nota de 1 a 5")
    comment: Optional[str] = Field(None, description="Comentário sobre o projeto")

class FeedbackResponse(BaseModel):
    id: int
    project_id: int
    rating: int
    comment: Optional[str]
    class Config:
        from_attributes = True

class ProjectResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    technology: str
    upvotes: int
    average_rating: float
    class Config:
        from_attributes = True

def seed_data():
    db = SessionLocal()
    if db.query(ProjectDB).count() == 0:
        p1 = ProjectDB(title="DevShowcase API", description="API de projetos de devs", technology="Java", upvotes=5, average_rating=4.5)
        p2 = ProjectDB(title="E-commerce Mobile", description="App mobile de vendas", technology="React", upvotes=12, average_rating=5.0)
        p3 = ProjectDB(title="Sistema de Tarefas", description="Gestor de tarefas", technology="Java", upvotes=3, average_rating=3.0)
        p4 = ProjectDB(title="Dashboard Analítico", description="Dashboard com gráficos", technology="Python", upvotes=8, average_rating=4.0)
        db.add_all([p1, p2, p3, p4])
        db.commit()
    db.close()

seed_data()

@app.get("/")
def read_root():
    return {"message": "DevShowcase API está online!", "swagger_docs": "/swagger"}

@app.get("/api/projects", response_model=List[ProjectResponse], tags=["Projects"])
def get_projects(
    tecnologia: Optional[str] = Query(None, description="Filtrar por tecnologia (ex: Java, Python)"),
    page: int = Query(0, ge=0, description="Número da página (inicia em 0)"),
    size: int = Query(10, ge=1, le=50, description="Tamanho da página"),
):
    db = SessionLocal()
    query = db.query(ProjectDB)
    if tecnologia:
        query = query.filter(ProjectDB.technology.ilike(f"%{tecnologia}%"))
    projects = query.offset(page * size).limit(size).all()
    db.close()
    return projects

@app.put("/api/projects/{id}/upvote", response_model=ProjectResponse, tags=["Projects"])
def upvote_project(id: int):
    db = SessionLocal()
    project = db.query(ProjectDB).filter(ProjectDB.id == id).first()
    if not project:
        db.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Projeto com o ID {id} não foi encontrado."
        )
    project.upvotes += 1
    db.commit()
    db.refresh(project)
    db.close()
    return project

@app.post("/api/projects/{id}/feedbacks", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED, tags=["Feedbacks"])
def create_feedback(id: int, feedback: FeedbackCreate):
    if feedback.rating < 1 or feedback.rating > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nota do feedback deve ser entre 1 e 5."
        )
    db = SessionLocal()
    project = db.query(ProjectDB).filter(ProjectDB.id == id).first()
    if not project:
        db.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Projeto com o ID {id} não foi encontrado."
        )
    new_fb = FeedbackDB(project_id=id, rating=feedback.rating, comment=feedback.comment)
    db.add(new_fb)
    db.commit()
    db.refresh(new_fb)
    avg_rating = db.query(func.avg(FeedbackDB.rating)).filter(FeedbackDB.project_id == id).scalar()
    project.average_rating = round(float(avg_rating), 2) if avg_rating else 0.0
    db.commit()
    db.close()
    return new_fb
