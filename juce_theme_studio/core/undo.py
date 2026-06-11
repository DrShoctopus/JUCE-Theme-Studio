"""Undo/redo command stack."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable


class Command(ABC):
    @abstractmethod
    def execute(self) -> None: ...

    @abstractmethod
    def undo(self) -> None: ...


class UndoStack:
    def __init__(self, max_depth: int = 100) -> None:
        self._undo: list[Command] = []
        self._redo: list[Command] = []
        self._max_depth = max_depth

    def push(self, command: Command) -> None:
        command.execute()
        self._undo.append(command)
        if len(self._undo) > self._max_depth:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self) -> bool:
        if not self._undo:
            return False
        cmd = self._undo.pop()
        cmd.undo()
        self._redo.append(cmd)
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        cmd = self._redo.pop()
        cmd.execute()
        self._undo.append(cmd)
        return True

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()


class CallableCommand(Command):
    """Simple command wrapping do/undo callables."""

    def __init__(self, do_fn: Callable[[], None], undo_fn: Callable[[], None]) -> None:
        self._do = do_fn
        self._undo_fn = undo_fn

    def execute(self) -> None:
        self._do()

    def undo(self) -> None:
        self._undo_fn()
