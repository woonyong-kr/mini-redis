"""
커스텀 Redis-like hash 구조 구현.

- seed 정책: MurmurHash3 seed는 항상 0을 사용한다.
- compact 표현: 작은 hash는 (field, value) 튜플 리스트로 저장한다.
- 런타임 hashtable 표현: Separate Chaining을 사용한다.
- Open Addressing 구현은 성능 비교와 회귀 테스트용으로 함께 유지한다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional, Tuple, Union


MURMURHASH3_SEED = 0
INITIAL_CAPACITY = 8
MAX_LOAD_FACTOR = 0.7
MIN_LOAD_FACTOR = 0.2
COMPACT_MAX_ENTRIES = 32
COMPACT_MAX_BYTES = 64

SLOT_EMPTY = 0
SLOT_OCCUPIED = 1
SLOT_TOMBSTONE = 2


def _murmurhash3_32_bytes(data: bytes) -> int:
    length = len(data)
    nblocks = length // 4
    h1 = MURMURHASH3_SEED & 0xFFFFFFFF
    c1 = 0xCC9E2D51
    c2 = 0x1B873593

    for block_index in range(nblocks):
        block_start = block_index * 4
        k1 = int.from_bytes(data[block_start:block_start + 4], "little")
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xFFFFFFFF
        k1 = (k1 * c2) & 0xFFFFFFFF

        h1 ^= k1
        h1 = ((h1 << 13) | (h1 >> 19)) & 0xFFFFFFFF
        h1 = (h1 * 5 + 0xE6546B64) & 0xFFFFFFFF

    tail = data[nblocks * 4:]
    k1 = 0
    if len(tail) == 3:
        k1 ^= tail[2] << 16
    if len(tail) >= 2:
        k1 ^= tail[1] << 8
    if len(tail) >= 1:
        k1 ^= tail[0]
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xFFFFFFFF
        k1 = (k1 * c2) & 0xFFFFFFFF
        h1 ^= k1

    h1 ^= length
    h1 ^= (h1 >> 16)
    h1 = (h1 * 0x85EBCA6B) & 0xFFFFFFFF
    h1 ^= (h1 >> 13)
    h1 = (h1 * 0xC2B2AE35) & 0xFFFFFFFF
    h1 ^= (h1 >> 16)
    return h1 & 0xFFFFFFFF


@lru_cache(maxsize=65536)
def _murmurhash3_32_str_cached(value: str) -> int:
    return _murmurhash3_32_bytes(value.encode("utf-8"))


def murmurhash3_32(value: Union[str, bytes], seed: int = MURMURHASH3_SEED) -> int:
    """
    MurmurHash3 x86 32-bit 구현.

    이 프로젝트의 hash 경로는 seed 0을 기본 정책으로 사용한다.
    """
    if seed != MURMURHASH3_SEED:
        raise ValueError("MurmurHash3 seed policy is fixed to 0")

    if isinstance(value, str):
        return _murmurhash3_32_str_cached(value)
    return _murmurhash3_32_bytes(value)


class BaseHashTable(ABC):
    """공통 hash table 인터페이스."""

    @abstractmethod
    def set(self, key: str, value: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get(self, key: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def contains(self, key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def items(self) -> List[Tuple[str, str]]:
        raise NotImplementedError

    @abstractmethod
    def __len__(self) -> int:
        raise NotImplementedError


@dataclass
class _Slot:
    state: int = SLOT_EMPTY
    hash_code: int = 0
    key: str = ""
    value: str = ""


class OpenAddressHashTable(BaseHashTable):
    """
    Open Addressing + Double Hashing 기반 hash table.

    - capacity는 항상 2의 거듭제곱을 유지한다.
    - step은 hash에서 파생한 odd 값으로 만들어 전체 table 순회가 가능하다.
    - used는 OCCUPIED + TOMBSTONE 수를 의미한다.
    """

    def __init__(self, capacity: int = INITIAL_CAPACITY):
        if capacity < INITIAL_CAPACITY:
            capacity = INITIAL_CAPACITY
        if capacity & (capacity - 1):
            raise ValueError("capacity must be a power of two")

        self.capacity = capacity
        self.live_count = 0
        self.used = 0
        self.slots = [_Slot() for _ in range(self.capacity)]

    def _hash(self, key: str) -> int:
        return murmurhash3_32(key)

    def _home_index(self, hash_code: int) -> int:
        return hash_code & (self.capacity - 1)

    def _probe_step(self, hash_code: int) -> int:
        # power-of-two capacity에서 odd step이면 전체 table을 순회할 수 있다.
        derived = ((hash_code >> 16) ^ (hash_code << 1)) & 0xFFFFFFFF
        step = (derived | 1) & (self.capacity - 1)
        return step if step != 0 else 1

    def _find_slot(self, key: str, hash_code: int) -> tuple[int | None, int | None]:
        start_index = self._home_index(hash_code)
        step = self._probe_step(hash_code)
        first_tombstone = None

        for probe_count in range(self.capacity):
            index = (start_index + probe_count * step) & (self.capacity - 1)
            slot = self.slots[index]

            if slot.state == SLOT_EMPTY:
                return None, first_tombstone if first_tombstone is not None else index

            if slot.state == SLOT_TOMBSTONE:
                if first_tombstone is None:
                    first_tombstone = index
                continue

            if slot.hash_code == hash_code and slot.key == key:
                return index, None

        return None, first_tombstone

    def _needs_grow_after_insert(self) -> bool:
        return (self.used / self.capacity) > MAX_LOAD_FACTOR

    def _needs_shrink_after_delete(self) -> bool:
        return (
            self.capacity > INITIAL_CAPACITY
            and (self.live_count / self.capacity) < MIN_LOAD_FACTOR
        )

    def _insert_rehashed(self, hash_code: int, key: str, value: str) -> None:
        start_index = hash_code & (self.capacity - 1)
        step = self._probe_step(hash_code)

        for probe_count in range(self.capacity):
            index = (start_index + probe_count * step) & (self.capacity - 1)
            slot = self.slots[index]
            if slot.state == SLOT_EMPTY:
                slot.state = SLOT_OCCUPIED
                slot.hash_code = hash_code
                slot.key = key
                slot.value = value
                self.live_count += 1
                self.used += 1
                return

        raise RuntimeError("rehash insert failed")

    def _resize(self, new_capacity: int) -> None:
        if new_capacity < INITIAL_CAPACITY:
            new_capacity = INITIAL_CAPACITY
        if new_capacity & (new_capacity - 1):
            raise ValueError("new_capacity must be a power of two")

        old_slots = self.slots
        self.capacity = new_capacity
        self.live_count = 0
        self.used = 0
        self.slots = [_Slot() for _ in range(self.capacity)]

        for slot in old_slots:
            if slot.state == SLOT_OCCUPIED:
                self._insert_rehashed(slot.hash_code, slot.key, slot.value)

    def set(self, key: str, value: str) -> bool:
        hash_code = self._hash(key)
        existing_index, insert_index = self._find_slot(key, hash_code)

        if existing_index is not None:
            self.slots[existing_index].value = value
            return False

        if insert_index is None:
            self._resize(self.capacity * 2)
            return self.set(key, value)

        target_slot = self.slots[insert_index]
        was_empty = target_slot.state == SLOT_EMPTY
        target_slot.state = SLOT_OCCUPIED
        target_slot.hash_code = hash_code
        target_slot.key = key
        target_slot.value = value
        self.live_count += 1
        if was_empty:
            self.used += 1

        if self._needs_grow_after_insert():
            self._resize(self.capacity * 2)

        return True

    def get(self, key: str) -> str | None:
        hash_code = self._hash(key)
        existing_index, _ = self._find_slot(key, hash_code)
        if existing_index is None:
            return None
        return self.slots[existing_index].value

    def delete(self, key: str) -> bool:
        hash_code = self._hash(key)
        existing_index, _ = self._find_slot(key, hash_code)
        if existing_index is None:
            return False

        slot = self.slots[existing_index]
        slot.state = SLOT_TOMBSTONE
        slot.hash_code = 0
        slot.key = ""
        slot.value = ""
        self.live_count -= 1

        if self._needs_shrink_after_delete():
            self._resize(max(INITIAL_CAPACITY, self.capacity // 2))

        return True

    def contains(self, key: str) -> bool:
        return self.get(key) is not None

    def items(self) -> List[Tuple[str, str]]:
        result: List[Tuple[str, str]] = []
        for slot in self.slots:
            if slot.state == SLOT_OCCUPIED:
                result.append((slot.key, slot.value))
        return result

    def flat_items(self) -> List[str]:
        result: List[str] = []
        for slot in self.slots:
            if slot.state == SLOT_OCCUPIED:
                result.append(slot.key)
                result.append(slot.value)
        return result

    def keys(self) -> List[str]:
        result: List[str] = []
        for slot in self.slots:
            if slot.state == SLOT_OCCUPIED:
                result.append(slot.key)
        return result

    def values(self) -> List[str]:
        result: List[str] = []
        for slot in self.slots:
            if slot.state == SLOT_OCCUPIED:
                result.append(slot.value)
        return result

    def __len__(self) -> int:
        return self.live_count


@dataclass
class _ChainNode:
    hash_code: int
    key: str
    value: str
    next: Optional["_ChainNode"] = None


class ChainedHashTable(BaseHashTable):
    """
    Separate Chaining 기반 hash table.

    - capacity는 power-of-two를 유지해 bucket 계산을 단순화한다.
    - 각 bucket은 연결 리스트 head를 가진다.
    - load factor는 live_count / capacity로 계산한다.
    - resize 시 live entry만 새 bucket 배열에 재삽입한다.
    """

    def __init__(self, capacity: int = INITIAL_CAPACITY):
        if capacity < INITIAL_CAPACITY:
            capacity = INITIAL_CAPACITY
        if capacity & (capacity - 1):
            raise ValueError("capacity must be a power of two")

        self.capacity = capacity
        self.live_count = 0
        self.buckets: List[Optional[_ChainNode]] = [None] * self.capacity

    def _hash(self, key: str) -> int:
        return murmurhash3_32(key)

    def _bucket_index(self, hash_code: int) -> int:
        return hash_code & (self.capacity - 1)

    def _needs_grow_after_insert(self) -> bool:
        return (self.live_count / self.capacity) > MAX_LOAD_FACTOR

    def _needs_shrink_after_delete(self) -> bool:
        return (
            self.capacity > INITIAL_CAPACITY
            and (self.live_count / self.capacity) < MIN_LOAD_FACTOR
        )

    def _insert_rehashed(self, hash_code: int, key: str, value: str) -> None:
        index = self._bucket_index(hash_code)
        node = _ChainNode(hash_code=hash_code, key=key, value=value, next=self.buckets[index])
        self.buckets[index] = node
        self.live_count += 1

    def _resize(self, new_capacity: int) -> None:
        if new_capacity < INITIAL_CAPACITY:
            new_capacity = INITIAL_CAPACITY
        if new_capacity & (new_capacity - 1):
            raise ValueError("new_capacity must be a power of two")

        old_buckets = self.buckets
        self.capacity = new_capacity
        self.live_count = 0
        self.buckets = [None] * self.capacity

        for bucket in old_buckets:
            current = bucket
            while current is not None:
                self._insert_rehashed(current.hash_code, current.key, current.value)
                current = current.next

    def set(self, key: str, value: str) -> bool:
        hash_code = self._hash(key)
        index = self._bucket_index(hash_code)

        current = self.buckets[index]
        while current is not None:
            if current.hash_code == hash_code and current.key == key:
                current.value = value
                return False
            current = current.next

        self.buckets[index] = _ChainNode(
            hash_code=hash_code,
            key=key,
            value=value,
            next=self.buckets[index],
        )
        self.live_count += 1

        if self._needs_grow_after_insert():
            self._resize(self.capacity * 2)

        return True

    def get(self, key: str) -> str | None:
        hash_code = self._hash(key)
        index = self._bucket_index(hash_code)

        current = self.buckets[index]
        while current is not None:
            if current.hash_code == hash_code and current.key == key:
                return current.value
            current = current.next
        return None

    def delete(self, key: str) -> bool:
        hash_code = self._hash(key)
        index = self._bucket_index(hash_code)

        previous: Optional[_ChainNode] = None
        current = self.buckets[index]
        while current is not None:
            if current.hash_code == hash_code and current.key == key:
                if previous is None:
                    self.buckets[index] = current.next
                else:
                    previous.next = current.next
                self.live_count -= 1

                if self._needs_shrink_after_delete():
                    self._resize(max(INITIAL_CAPACITY, self.capacity // 2))
                return True

            previous = current
            current = current.next

        return False

    def contains(self, key: str) -> bool:
        return self.get(key) is not None

    def items(self) -> List[Tuple[str, str]]:
        result: List[Tuple[str, str]] = []
        for bucket in self.buckets:
            current = bucket
            while current is not None:
                result.append((current.key, current.value))
                current = current.next
        return result

    def flat_items(self) -> List[str]:
        result: List[str] = []
        for bucket in self.buckets:
            current = bucket
            while current is not None:
                result.append(current.key)
                result.append(current.value)
                current = current.next
        return result

    def keys(self) -> List[str]:
        result: List[str] = []
        for bucket in self.buckets:
            current = bucket
            while current is not None:
                result.append(current.key)
                current = current.next
        return result

    def values(self) -> List[str]:
        result: List[str] = []
        for bucket in self.buckets:
            current = bucket
            while current is not None:
                result.append(current.value)
                current = current.next
        return result

    def __len__(self) -> int:
        return self.live_count


class Hash:
    """
    Redis-like hash 상위 구조.

    작은 데이터셋은 compact 리스트로 시작하고,
    개수 또는 원소 크기 임계치를 넘으면 hash table로 승격한다.
    """

    compact_max_entries = COMPACT_MAX_ENTRIES
    compact_max_bytes = COMPACT_MAX_BYTES

    def __init__(self):
        self._compact_entries: List[Tuple[str, str]] = []
        self._table: BaseHashTable | None = None

    @property
    def is_compact(self) -> bool:
        return self._table is None

    def _byte_length(self, value: str) -> int:
        return len(value.encode("utf-8"))

    def _should_promote(self, key: str, value: str, existing_index: int) -> bool:
        if self._byte_length(key) > self.compact_max_bytes:
            return True
        if self._byte_length(value) > self.compact_max_bytes:
            return True

        prospective_length = len(self._compact_entries)
        if existing_index == -1:
            prospective_length += 1
        return prospective_length > self.compact_max_entries

    def _promote_to_table(self) -> None:
        if self._table is not None:
            return

        self._table = ChainedHashTable()
        for key, value in self._compact_entries:
            self._table.set(key, value)
        self._compact_entries = []

    def set(self, key: str, value: str) -> bool:
        if self._table is not None:
            return self._table.set(key, value)

        existing_index = -1
        for index, (current_key, _) in enumerate(self._compact_entries):
            if current_key == key:
                existing_index = index
                break

        if self._should_promote(key, value, existing_index):
            self._promote_to_table()
            return self._table.set(key, value)

        if existing_index != -1:
            self._compact_entries[existing_index] = (key, value)
            return False

        self._compact_entries.append((key, value))
        return True

    def get(self, key: str) -> str | None:
        if self._table is not None:
            return self._table.get(key)

        for current_key, current_value in self._compact_entries:
            if current_key == key:
                return current_value
        return None

    def delete(self, key: str) -> bool:
        if self._table is not None:
            return self._table.delete(key)

        for index, (current_key, _) in enumerate(self._compact_entries):
            if current_key == key:
                self._compact_entries.pop(index)
                return True
        return False

    def contains(self, key: str) -> bool:
        return self.get(key) is not None

    def items(self) -> List[Tuple[str, str]]:
        if self._table is not None:
            return self._table.items()
        return list(self._compact_entries)

    def flat_items(self) -> List[str]:
        if self._table is not None:
            return self._table.flat_items()

        result: List[str] = []
        for key, value in self._compact_entries:
            result.append(key)
            result.append(value)
        return result

    def keys(self) -> List[str]:
        if self._table is not None:
            return self._table.keys()
        return [key for key, _ in self._compact_entries]

    def values(self) -> List[str]:
        if self._table is not None:
            return self._table.values()
        return [value for _, value in self._compact_entries]

    def __len__(self) -> int:
        if self._table is not None:
            return len(self._table)
        return len(self._compact_entries)
