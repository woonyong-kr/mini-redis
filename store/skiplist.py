"""Skiplist-backed sorted-set primitives.

`ZSet` combines a member-to-score dictionary for O(1) lookups with a skiplist
for ordered ranges and rank queries.
"""

from __future__ import annotations

import random
from typing import Iterable, List, Optional, Tuple


SKIPLIST_MAX_LEVEL = 16
SKIPLIST_P = 0.25


class SkipListNode:
    __slots__ = ("score", "member", "forward", "span", "backward")

    def __init__(self, level: int, score: float, member: Optional[str]):
        self.score = score
        self.member = member
        self.forward = [None] * level
        self.span = [0] * level
        self.backward = None


class SkipList:
    __slots__ = ("header", "tail", "level", "length", "_rng")

    def __init__(self):
        self.header = SkipListNode(SKIPLIST_MAX_LEVEL, float("-inf"), None)
        self.tail = None
        self.level = 1
        self.length = 0
        self._rng = random.Random(0)

    def _random_level(self) -> int:
        level = 1
        while level < SKIPLIST_MAX_LEVEL and self._rng.random() < SKIPLIST_P:
            level += 1
        return level

    @staticmethod
    def _less_than(score: float, member: str, node: SkipListNode) -> bool:
        return (node.score, node.member) < (score, member)

    def insert(self, score: float, member: str) -> None:
        update = [None] * SKIPLIST_MAX_LEVEL
        rank = [0] * SKIPLIST_MAX_LEVEL
        current = self.header

        for index in range(self.level - 1, -1, -1):
            rank[index] = 0 if index == self.level - 1 else rank[index + 1]
            while current.forward[index] is not None and self._less_than(score, member, current.forward[index]):
                rank[index] += current.span[index]
                current = current.forward[index]
            update[index] = current

        level = self._random_level()
        if level > self.level:
            for index in range(self.level, level):
                rank[index] = 0
                update[index] = self.header
                self.header.span[index] = self.length
            self.level = level

        node = SkipListNode(level, score, member)
        for index in range(level):
            node.forward[index] = update[index].forward[index]
            update_span = update[index].span[index]
            distance = rank[0] - rank[index]
            node.span[index] = update_span - distance if update_span else self.length - rank[0]
            update[index].forward[index] = node
            update[index].span[index] = distance + 1

        for index in range(level, self.level):
            update[index].span[index] += 1

        node.backward = None if update[0] is self.header else update[0]
        if node.forward[0] is not None:
            node.forward[0].backward = node
        else:
            self.tail = node

        self.length += 1

    def delete(self, score: float, member: str) -> bool:
        update = [None] * SKIPLIST_MAX_LEVEL
        current = self.header

        for index in range(self.level - 1, -1, -1):
            while current.forward[index] is not None and self._less_than(score, member, current.forward[index]):
                current = current.forward[index]
            update[index] = current

        target = current.forward[0]
        if target is None or (target.score, target.member) != (score, member):
            return False

        for index in range(self.level):
            if update[index].forward[index] is target:
                update[index].span[index] += target.span[index] - 1
                update[index].forward[index] = target.forward[index]
            else:
                update[index].span[index] -= 1

        if target.forward[0] is not None:
            target.forward[0].backward = target.backward
        else:
            self.tail = target.backward

        while self.level > 1 and self.header.forward[self.level - 1] is None:
            self.level -= 1

        self.length -= 1
        return True

    def rank(self, score: float, member: str) -> Optional[int]:
        traversed = 0
        current = self.header

        for index in range(self.level - 1, -1, -1):
            while current.forward[index] is not None and (
                current.forward[index].score < score or
                (current.forward[index].score == score and current.forward[index].member <= member)
            ):
                traversed += current.span[index]
                current = current.forward[index]

            if current.member == member and current.score == score:
                return traversed - 1

        return None

    def node_by_rank(self, rank: int) -> Optional[SkipListNode]:
        if rank < 0 or rank >= self.length:
            return None

        current = self.header
        traversed = 0
        target = rank + 1

        for index in range(self.level - 1, -1, -1):
            while current.forward[index] is not None and traversed + current.span[index] <= target:
                traversed += current.span[index]
                current = current.forward[index]
            if traversed == target:
                return current

        return None

    def range_entries(self, start: int, stop: int) -> List[Tuple[str, float]]:
        if self.length == 0:
            return []

        if start < 0:
            start += self.length
        if stop < 0:
            stop += self.length
        if start < 0:
            start = 0
        if stop >= self.length:
            stop = self.length - 1
        if start > stop or start >= self.length:
            return []

        node = self.node_by_rank(start)
        result = []
        index = start
        while node is not None and index <= stop:
            result.append((node.member, node.score))
            node = node.forward[0]
            index += 1
        return result

    def range_by_score(self, minimum: float, maximum: float) -> List[Tuple[str, float]]:
        current = self.header
        for index in range(self.level - 1, -1, -1):
            while current.forward[index] is not None and current.forward[index].score < minimum:
                current = current.forward[index]

        current = current.forward[0]
        result = []
        while current is not None and current.score <= maximum:
            result.append((current.member, current.score))
            current = current.forward[0]
        return result

    def items(self) -> List[Tuple[str, float]]:
        return self.range_entries(0, self.length - 1)


class ZSet:
    __slots__ = ("_scores", "_index")

    def __init__(self):
        self._scores: dict[str, float] = {}
        self._index = SkipList()

    @classmethod
    def from_items(cls, items: Iterable[Tuple[str, float]]) -> "ZSet":
        zset = cls()
        for member, score in items:
            zset.set(member, float(score))
        return zset

    def __contains__(self, member: str) -> bool:
        return member in self._scores

    def __len__(self) -> int:
        return len(self._scores)

    def set(self, member: str, score: float) -> int:
        existing = self._scores.get(member)
        if existing is not None:
            if existing == score:
                return 0
            self._index.delete(existing, member)
            self._scores[member] = score
            self._index.insert(score, member)
            return 0

        self._scores[member] = score
        self._index.insert(score, member)
        return 1

    def remove(self, member: str) -> int:
        score = self._scores.pop(member, None)
        if score is None:
            return 0
        self._index.delete(score, member)
        return 1

    def get_score(self, member: str) -> Optional[float]:
        return self._scores.get(member)

    def rank(self, member: str) -> Optional[int]:
        score = self._scores.get(member)
        if score is None:
            return None
        return self._index.rank(score, member)

    def range_entries(self, start: int, stop: int) -> List[Tuple[str, float]]:
        return self._index.range_entries(start, stop)

    def revrange_entries(self, start: int, stop: int) -> List[Tuple[str, float]]:
        if len(self) == 0:
            return []

        if start < 0:
            start += len(self)
        if stop < 0:
            stop += len(self)
        if start < 0:
            start = 0
        if stop >= len(self):
            stop = len(self) - 1
        if start > stop or start >= len(self):
            return []

        asc_start = len(self) - 1 - stop
        asc_stop = len(self) - 1 - start
        entries = self._index.range_entries(asc_start, asc_stop)
        entries.reverse()
        return entries

    def range_by_score(self, minimum: float, maximum: float) -> List[Tuple[str, float]]:
        return self._index.range_by_score(minimum, maximum)

    def items(self) -> List[Tuple[str, float]]:
        return self._index.items()
