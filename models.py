from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Table, Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

db = SQLAlchemy()

# 多對多關聯表
session_tags = Table('session_tags',
    db.metadata,
    Column('session_id', Integer, ForeignKey('sessions.id')),
    Column('tag_id', Integer, ForeignKey('tags.id'))
)

segment_tags = Table('segment_tags',
    db.metadata,
    Column('segment_id', Integer, ForeignKey('segments.id')),
    Column('tag_id', Integer, ForeignKey('tags.id'))
)

segment_attachments = Table('segment_attachments',
    db.metadata,
    Column('segment_id', Integer, ForeignKey('segments.id')),
    Column('attachment_id', Integer, ForeignKey('attachments.id'))
)

# 標籤關聯表（用於標籤之間的關係）
tag_relations = Table('tag_relations',
    db.metadata,
    Column('parent_tag_id', Integer, ForeignKey('tags.id')),
    Column('child_tag_id', Integer, ForeignKey('tags.id'))
)

class Tag(db.Model):
    __tablename__ = 'tags'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    category = db.Column(db.String(50))  # 領域/手法/症狀/位置等
    description = db.Column(db.Text)
    color = db.Column(db.String(7))  # HEX color code
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 自關聯：標籤階層
    parent_tags = relationship(
        'Tag',
        secondary=tag_relations,
        primaryjoin=(tag_relations.c.child_tag_id == id),
        secondaryjoin=(tag_relations.c.parent_tag_id == id),
        backref='child_tags'
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'color': self.color
        }

class Session(db.Model):
    __tablename__ = 'sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    overview = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 關聯
    tags = relationship('Tag', secondary=session_tags, backref='sessions')
    segments = relationship('Segment', backref='session', lazy='dynamic', cascade='all, delete-orphan')

class Segment(db.Model):
    __tablename__ = 'segments'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, ForeignKey('sessions.id'), nullable=False)
    segment_type = db.Column(db.String(50))  # 診斷/治療/理論等
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    order_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 關聯
    tags = relationship('Tag', secondary=segment_tags, backref='segments')
    attachments = relationship('Attachment', secondary=segment_attachments, backref='segments')
    
    # 段落之間的關聯
    related_segment_id = db.Column(db.Integer, ForeignKey('segments.id'))
    related_segments = relationship('Segment', 
                                  backref=db.backref('related_to', remote_side=[id]))

class Attachment(db.Model):
    __tablename__ = 'attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255))
    file_type = db.Column(db.String(50))  # image/video/document
    file_path = db.Column(db.String(500))
    description = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

# 查詢關聯表（用於記錄複雜查詢）
class QueryRelation(db.Model):
    __tablename__ = 'query_relations'
    
    id = db.Column(db.Integer, primary_key=True)
    relation_type = db.Column(db.String(50))  # 症狀->病因, 病因->治療等
    source_type = db.Column(db.String(50))  # tag/segment
    source_id = db.Column(db.Integer)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.Integer)
    strength = db.Column(db.Float, default=1.0)  # 關聯強度
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
