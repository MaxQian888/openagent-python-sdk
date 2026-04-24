"""App-defined protocol layer for the multi_agent_support example.

What:
    Deps (CustomerStore, TicketStore, trace log), pydantic envelopes,
    and ToolPlugin subclasses that compose the four-agent customer-support
    topology on top of the SDK kernel. The kernel is not aware of any
    types defined here.

Structure:
    - ``deps.py``: SupportDeps (data layer for tools).
    - ``protocol.py``: pydantic models + state keys.
    - ``plugins.py``: ToolPlugin subclasses (lookup, router-bound, action).
"""
