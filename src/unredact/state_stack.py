from collections import deque
from .document_state import DocState

class StateStack:
    """A LIFO stack specifically for tracking DocState history."""
    
    def __init__(self):
        # Enforce that this deque only holds CanvasState objects
        self._items: deque[DocState] = deque()

    def push(self, state: DocState):
        """Push a new state checkpoint onto the history stack."""
        if not isinstance(state, DocState):
            raise TypeError("Only CanvasState objects can be pushed.")
        self._items.append(state)

    def pop(self):
        """Remove and return the most recent state."""
        try:
            return self._items.pop()
        except IndexError:
            raise IndexError("No state history left to pop.")

    def peek(self):
        """Look at the current state without removing it."""
        if not self._items:
            raise IndexError("No current state available.")
        return self._items[-1]


    def __len__(self):
        return len(self._items)
