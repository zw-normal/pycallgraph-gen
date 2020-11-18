import ast
import sys
import enum

from sqlalchemy import Column, Integer, String, Enum, UniqueConstraint, select, Index
from sqlalchemy.orm import declarative_base


Base = declarative_base()

class FunctionNodeType(enum.Enum):
    Normal = 1
    Class = 2
    Property = 3
    ClassMethod = 4
    StaticMethod = 5
    InstanceMethod = 6
    AmbiguityCallError = 7


class FunctionNodeDef:
    @staticmethod
    def is_buildin_func(name):
        return name in __builtins__.__dict__.keys() or \
               name in dir(dict) or \
               name in dir(list) or \
               name in dir(set) or \
               name in dir(tuple) or \
               name in dir(str)

    @staticmethod
    def is_instance_method(func):
        args_len = len(func.args.args)
        if args_len > 0:
            first_arg = func.args.args[0]
            if sys.version_info.major >= 3:
                first_arg = first_arg.arg
            elif isinstance(first_arg, ast.Name):
                first_arg = first_arg.id
            if isinstance(first_arg, str) and first_arg == 'self':
                return True
        return False

    @staticmethod
    def get_function_type(func):
        for decorator in func.decorator_list:
            if isinstance(decorator, ast.Name):
                if decorator.id == 'property':
                    return FunctionNodeType.Property
                elif decorator.id == 'classmethod':
                    return FunctionNodeType.ClassMethod
                elif decorator.id == 'staticmethod':
                    return FunctionNodeType.StaticMethod

        if FunctionNodeDef.is_instance_method(func):
            return FunctionNodeType.InstanceMethod
        return FunctionNodeType.Normal

    @staticmethod
    def get_min_args(func, func_type):
        min_args = len(func.args.args) - len(func.args.defaults)
        if func_type not in (FunctionNodeType.Normal, FunctionNodeType.StaticMethod):
            return min_args - 1
        return min_args

    @staticmethod
    def get_max_args(func, func_type):
        if (func.args.vararg is not None) or \
                (func.args.kwarg is not None):
            return 255

        max_args = len(func.args.args)
        if func_type not in (FunctionNodeType.Normal, FunctionNodeType.StaticMethod):
            return max_args - 1
        return max_args


class FunctionNode(Base):

    __tablename__ = 'function_node'

    id = Column(Integer, primary_key=True)
    source_file = Column(String)
    line_no = Column(Integer)
    col_offset = Column(Integer)

    module_name = Column(String)
    class_name = Column(String)
    func_type = Column(Enum(FunctionNodeType))
    func_name = Column(String, index=True)
    min_args = Column(Integer, index=True)
    max_args = Column(Integer, index=True)

    __table_args__ = (
        UniqueConstraint('source_file', 'line_no', 'col_offset', name='function_def_pos'),)

    @classmethod
    def from_def_node(cls, source_file, module_name, class_name, node):
        func_type = FunctionNodeDef.get_function_type(node)
        return cls(
            source_file=source_file, line_no=node.lineno, col_offset=node.col_offset,
            module_name=module_name, class_name=class_name,
            func_type=func_type, func_name=node.name,
            min_args=FunctionNodeDef.get_min_args(node, func_type),
            max_args=FunctionNodeDef.get_max_args(node, func_type)
        )

    @classmethod
    def from_class_constructor(cls, source_file, module_name, class_name, node):
        func_def = cls.from_def_node(source_file, module_name, class_name, node)
        func_def.func_name = class_name
        func_def.func_type = FunctionNodeType.Class
        return func_def

    def __eq__(self, other):
        if isinstance(other, FunctionNode):
            return (self.source_file == other.source_file) and \
                   (self.line_no == other.line_no) and \
                   (self.col_offset == other.col_offset)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.source_file, self.line_no, self.col_offset))


def get_function_def_node(session, source_file, line_no, column_offset):
    stmt = (select(FunctionNode).
            where(FunctionNode.source_file == source_file,
                  FunctionNode.line_no == line_no,
                  FunctionNode.col_offset == column_offset))
    return session.execute(stmt).scalar_one()


def get_function_callee_def_nodes(session, func_name, args_length):
    stmt = (select(FunctionNode).
            where(FunctionNode.func_name==func_name,
                  FunctionNode.min_args<=args_length,
                  FunctionNode.max_args>=args_length))
    return session.execute(stmt).scalars().all()
