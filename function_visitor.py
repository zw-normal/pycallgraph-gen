import ast

from function_def import FunctionNode, get_function_def_node, get_function_callee_def_nodes
from function_call import FunctionCall


class FunctionDefVisitorPhase1(ast.NodeVisitor):

    def __init__(self, session, source_file, module_name):
        self.session = session
        self.source_file = source_file
        self.module_name = module_name
        self.class_name = ''

    def visit_FunctionDef(self, node):
        if node.name != '__init__':
            # The visit_ClassDef handles the constructor
            func_node = FunctionNode.from_def_node(
                self.source_file, self.module_name, self.class_name, node)
            self.session.add(func_node)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        # The following visit_FunctionDef is in this class
        self.class_name = node.name

        for method in (member for member in node.body if isinstance(member, ast.FunctionDef)):
            if method.name == '__init__':
                func_node = FunctionNode.from_class_constructor(
                    self.source_file, self.module_name, node.name, method)
                self.session.add(func_node)
                break

        self.generic_visit(node)


class FunctionDefVisitorPhase2(ast.NodeVisitor):
    # Phase 2 is to build the call graph

    def __init__(self, session, source_file, module_name):
        self.session = session
        self.source_file = source_file
        self.module_name = module_name

    def visit_FunctionDef(self, node):
        if node.name != '__init__':
            self.inspect_function_call(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        for method in (member for member in node.body if isinstance(member, ast.FunctionDef)):
            if method.name == '__init__':
                self.inspect_function_call(method)
        self.generic_visit(node)

    def inspect_function_call(self, node):
        FunctionCallVisitor(self.session, self.source_file, node).visit(node)


class FunctionCallVisitor(ast.NodeVisitor):

    def __init__(self, session, source_file, caller):
        self.session = session
        self.source_file = source_file
        self.caller = caller
        self.caller_def = get_function_def_node(
            self.session, self.source_file, caller.lineno, caller.col_offset)

    def visit_Call(self, node):
        # Caller -> Callee
        callee_name = self.get_function_callee_name(node)
        if (callee_name is not None) and (not self.is_buildin_function(callee_name)):
            callee_args_length = len(node.args) + len(node.keywords)
            callee_defs = get_function_callee_def_nodes(self.session, callee_name, callee_args_length)
            if len(callee_defs) == 1:
                func_call = FunctionCall(
                    caller_id=self.caller_def.id,
                    callee_id=callee_defs[0].id,
                    line_no=node.lineno,
                    exact_call=True)
                self.session.add(func_call)
            else:
                for callee_def in callee_defs:
                    func_call = FunctionCall(
                        caller_id=self.caller_def.id,
                        callee_id=callee_def.id,
                        line_no=node.lineno)
                    self.session.add(func_call)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # Do not iterate 'def func' in func
        if node == self.caller:
            self.generic_visit(node)

    def visit_ClassDef(self, node):
        # Do not iterate 'inner class' in func
        pass

    @staticmethod
    def get_function_callee_name(callee_node):
        if isinstance(callee_node.func, ast.Attribute):
            return callee_node.func.attr
        elif isinstance(callee_node.func, ast.Name):
            return callee_node.func.id
        return None

    @staticmethod
    def is_buildin_function(name):
        return name in __builtins__ or \
               name in dir(dict) or \
               name in dir(list) or \
               name in dir(set) or \
               name in dir(tuple) or \
               name in dir(str)
