""" Facade for storage service (tables manager)

"""
from .tables.comp_tasks_table import comp_tasks
from .tables.comp_pipeline_table import comp_pipeline

__all__ = [
    "comp_tasks",
    "comp_pipeline"
]
