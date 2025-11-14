"""
Database models for projects and material takeoffs
SQLAlchemy ORM models
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class ProjectStatus(str, enum.Enum):
    """Project status enumeration."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class Project(Base):
    """Project model - represents a construction project."""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.ACTIVE, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    drawings = relationship("Drawing", back_populates="project", cascade="all, delete-orphan")
    takeoffs = relationship("MaterialTakeoffRecord", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}')>"


class DrawingFormat(str, enum.Enum):
    """Drawing file format enumeration."""
    DWG = "dwg"
    DXF = "dxf"
    PDF = "pdf"
    PNG = "png"
    JPG = "jpg"
    JPEG = "jpeg"


class Drawing(Base):
    """Drawing model - represents an architectural drawing file."""
    __tablename__ = "drawings"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)

    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_format = Column(Enum(DrawingFormat), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)

    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Metadata extracted from drawing (using drawing_metadata to avoid SQLAlchemy reserved word)
    drawing_metadata = Column(JSON, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="drawings")
    takeoffs = relationship("MaterialTakeoffRecord", back_populates="drawing", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Drawing(id={self.id}, filename='{self.filename}', format={self.file_format.value})>"


class TakeoffStatus(str, enum.Enum):
    """Material takeoff processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MaterialTakeoffRecord(Base):
    """Material takeoff record - stores takeoff results."""
    __tablename__ = "material_takeoffs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    drawing_id = Column(Integer, ForeignKey("drawings.id"), nullable=False, index=True)

    status = Column(Enum(TakeoffStatus), default=TakeoffStatus.PENDING, nullable=False)

    # Processing details
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)

    # Results stored as JSON
    result_data = Column(JSON, nullable=True)

    # Quality metrics
    confidence_score = Column(Float, nullable=True)
    total_items = Column(Integer, default=0)
    total_waste_percentage = Column(Float, nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    warnings = Column(JSON, nullable=True)

    # Processing metadata
    processing_metadata = Column(JSON, nullable=True)  # Stores which methods were used (CV, LLM, rules)

    # Relationships
    project = relationship("Project", back_populates="takeoffs")
    drawing = relationship("Drawing", back_populates="takeoffs")

    def __repr__(self):
        return f"<MaterialTakeoffRecord(id={self.id}, drawing_id={self.drawing_id}, status={self.status.value})>"


class GroundTruth(Base):
    """Ground truth data for validation and training."""
    __tablename__ = "ground_truth"

    id = Column(Integer, primary_key=True, index=True)
    drawing_id = Column(Integer, ForeignKey("drawings.id"), nullable=False, index=True)

    # Manually verified material data
    verified_data = Column(JSON, nullable=False)

    # Verification metadata
    verified_by = Column(String(255), nullable=True)
    verified_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(Text, nullable=True)

    # Drawing relationship
    drawing = relationship("Drawing")

    def __repr__(self):
        return f"<GroundTruth(id={self.id}, drawing_id={self.drawing_id})>"
