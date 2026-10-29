"""SQLite for local work, ordered like the Postgres production database.

SQLite puts NULLs first in ascending order and last in descending; Postgres does
the opposite. Unseeded entrants, unranked results and unscheduled fixtures would
otherwise sort differently on a laptop than on the hosted site.
"""

from django.db.backends.sqlite3 import base, operations


class DatabaseOperations(operations.DatabaseOperations):
    compiler_module = "config.db.sqlite_pglike.compiler"


class DatabaseWrapper(base.DatabaseWrapper):
    ops_class = DatabaseOperations
