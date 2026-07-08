"""Service layer for ctrack.

Business logic that used to live in fat models and fat views is collected here.
Views stay thin (parse input -> call service -> serialize) and models hold data
plus trivial accessors. Import the focused modules directly, e.g.::

    from ctrack.services import import_service
    from ctrack.services import categorisation_service
    from ctrack.services import progress_service
"""
