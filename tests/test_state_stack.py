import unittest

from unredact.document_state import DocState
from unredact.state_stack import StateStack

# ===========================================================================
# StateStack tests
# ===========================================================================

class TestStateStack(unittest.TestCase):

    def _state(self, **kw):
        return DocState(**kw)

    def test_push_and_len(self):
        stack = StateStack()
        stack.push(self._state())
        self.assertEqual(len(stack), 1)

    def test_peek_returns_top(self):
        stack = StateStack()
        s1 = self._state(fill_color=[1, 0, 0])
        s2 = self._state(fill_color=[0, 1, 0])
        stack.push(s1)
        stack.push(s2)
        self.assertIs(stack.peek(), s2)

    def test_peek_does_not_remove(self):
        stack = StateStack()
        stack.push(self._state())
        stack.peek()
        self.assertEqual(len(stack), 1)

    def test_pop_returns_and_removes_top(self):
        stack = StateStack()
        s = self._state()
        stack.push(s)
        result = stack.pop()
        self.assertIs(result, s)
        self.assertEqual(len(stack), 0)

    def test_pop_restores_previous_state(self):
        stack = StateStack()
        s1 = self._state(fill_color=[0, 0, 0])
        s2 = self._state(fill_color=[1, 1, 1])
        stack.push(s1)
        stack.push(s2)
        stack.pop()
        self.assertIs(stack.peek(), s1)

    def test_pop_empty_raises(self):
        stack = StateStack()
        with self.assertRaises(IndexError):
            stack.pop()

    def test_peek_empty_raises(self):
        stack = StateStack()
        with self.assertRaises(IndexError):
            stack.peek()

    def test_push_wrong_type_raises(self):
        stack = StateStack()
        with self.assertRaises(TypeError):
            stack.push("not a DocState")

    def test_push_none_raises(self):
        stack = StateStack()
        with self.assertRaises(TypeError):
            stack.push(None)

    def test_multiple_pushes_and_pops(self):
        stack = StateStack()
        states = [self._state(fill_color=[i/10, 0, 0]) for i in range(5)]
        for s in states:
            stack.push(s)
        for s in reversed(states):
            self.assertIs(stack.pop(), s)


