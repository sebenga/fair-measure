from django.db.models.expressions import OrderBy
from django.db.models.sql import compiler
from django.db.models.sql.compiler import (  # noqa: F401
    SQLAggregateCompiler,
    SQLDeleteCompiler,
    SQLInsertCompiler,
    SQLUpdateCompiler,
)


class SQLCompiler(compiler.SQLCompiler):
    def compile(self, node):
        if isinstance(node, OrderBy) and node.nulls_first is None and node.nulls_last is None:
            node = node.copy()
            if node.descending:
                node.nulls_first = True
            else:
                node.nulls_last = True
        return super().compile(node)
