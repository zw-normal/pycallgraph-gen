import os
import ast
import fnmatch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from function_def import Base
from function_config import source_roots, exclude_folders
from function_visitor import FunctionDefVisitorPhase1, FunctionDefVisitorPhase2


engine = create_engine("sqlite+pysqlite:///functions_graph.sqlite3", future=True)
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)


def get_module_name(source_root, source_file):
    return source_file[len(source_root)+1:-3].replace(os.path.sep, '.')


def scan_source_files(visitor_cls):
    for source_root in source_roots:
        for folder, dirs, files in os.walk(source_root):
            dirs[:] = [d for d in dirs if d not in exclude_folders]
            for source_file in files:
                if fnmatch.fnmatch(source_file, '*.py') and ('test' not in source_file):
                    with open(os.path.join(folder, source_file), 'r') as source:
                        print('Scanning {}'.format(source.name))
                        ast_tree = ast.parse(source.read())
                        with Session(engine) as session:
                            visitor = visitor_cls(
                                session, source.name,
                                get_module_name(source_root, source.name))
                            visitor.visit(ast_tree)
                            session.commit()

if __name__ == '__main__':
    scan_source_files(FunctionDefVisitorPhase1)
    scan_source_files(FunctionDefVisitorPhase2)
