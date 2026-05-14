from sqlalchemy import create_all, Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    url = Column(String(255))
    type = Column(String(50)) # rss, api, web
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SourceItem(Base):
    __tablename__ = "source_items"
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id"))
    title = Column(String(255))
    url = Column(String(255))
    content = Column(Text)
    published_at = Column(DateTime)
    content_hash = Column(String(64), unique=True)
    summary = Column(Text)
    importance_score = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Episode(Base):
    __tablename__ = "episodes"
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=datetime.utcnow)
    title = Column(String(255))
    description = Column(Text)
    script = Column(Text)
    status = Column(String(50)) # draft, approved, published, failed
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    audio_assets = relationship("AudioAsset", back_populates="episode")

class AudioAsset(Base):
    __tablename__ = "audio_assets"
    id = Column(Integer, primary_key=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"))
    voice_name = Column(String(50))
    audio_url = Column(String(255))
    duration_seconds = Column(Integer)
    file_size = Column(Integer)
    format = Column(String(10)) # mp3, m4a
    created_at = Column(DateTime, default=datetime.utcnow)
    
    episode = relationship("Episode", back_populates="audio_assets")
