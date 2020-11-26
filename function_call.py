import ast

from sqlalchemy import Column, Integer, Boolean, UniqueConstraint, ForeignKey
from sqlalchemy.orm import relationship

from function_def import Base, FunctionNode


class FunctionCall(Base):

    __tablename__ = 'function_call'

    id = Column(Integer, primary_key=True)
    caller_id = Column(Integer, ForeignKey('function_node.id'), nullable=False)
    callee_id = Column(Integer, ForeignKey('function_node.id'), nullable=False)
    line_no = Column(Integer)
    exact_call = Column(Boolean, default=False)

    caller = relationship(FunctionNode, foreign_keys=[caller_id])
    callee = relationship(FunctionNode, foreign_keys=[callee_id])
