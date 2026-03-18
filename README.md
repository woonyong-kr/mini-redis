# mini-redis Hash Stack 설계 문서

## 프로젝트 개요
이 저장소는 Redis-like 동작을 학습하고 구현하기 위한 Python 기반 mini-redis 프로젝트입니다.

이번 문서의 초점은 hash 자료구조 경로를 Python 내장 `dict`에 기대지 않고, 명시적으로 설계된 커스텀 해시 스택으로 구현하는 것입니다.

현재 저장소에는 hash 명령과 저장 계층의 스켈레톤이 존재하며, 이 문서는 구현 설계와 실제 반영 결과를 함께 정리합니다.

## 구현 상태
- `store/hash_table.py`에 `BaseHashTable`, `OpenAddressHashTable`, `Hash`를 구현했습니다.
- `store/datastore.py`의 hash 저장 경로는 내장 `dict` 대신 `Hash`를 사용하도록 연결했습니다.
- `commands/hash_cmds.py`에 `HSET/HGET/HMSET/HMGET/HGETALL/HDEL/HEXISTS/HKEYS/HVALS/HLEN`을 구현했습니다.
- 해시 전용 검증은 `tests/test_hash_table.py`, `tests/test_hash_cmds.py`에 추가했습니다.

## 최종 설계 요약
- 해싱은 `store/hash_table.py`의 `murmurhash3_32()`에 있습니다.
- probing과 resize는 `store/hash_table.py`의 `OpenAddressHashTable`에 있습니다.
- compact representation과 promotion은 `store/hash_table.py`의 `Hash`에 있습니다.
- seed 정책은 고정값 `0`입니다.
- probe는 `index = (start + i * step) & (capacity - 1)` 방식이며, `step`은 같은 hash 결과에서 파생한 odd/non-zero 값으로 계산합니다.

## 테스트 실행 예시
가상 환경 기준:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pytest tests/test_hash_table.py tests/test_hash_cmds.py -v
```

## 무엇을 구현할 예정인가
다음 세 계층을 구현 대상으로 둡니다.

1. `BaseHashTable`
2. `OpenAddressHashTable`
3. `Hash`

각 계층의 역할은 다음과 같습니다.

- `BaseHashTable`
  - 공통 인터페이스를 정의합니다.
- `OpenAddressHashTable`
  - 실제 해시 테이블 동작을 담당합니다.
  - 배열 기반 슬롯, 해싱, 프로빙, tombstone, 리사이즈를 가집니다.
- `Hash`
  - 상위 자료구조입니다.
  - 작은 데이터에서는 compact representation을 사용하고, 커지면 hashtable로 승격합니다.

## 무엇을 사용했는가
이번 hash stack 설계는 아래 요소를 사용합니다.

- MurmurHash3
- Open Addressing with Double Hashing
- tombstone deletion
- compact representation + promotion

추가 의존성은 기본적으로 사용하지 않습니다.

## 왜 이것을 선택했는가

### MurmurHash3
- 비교적 단순하게 프로젝트 내부에 직접 구현할 수 있습니다.
- 빠르고 분산이 좋아 커스텀 해시 테이블 실험에 적합합니다.
- seed 정책을 명시하면 테스트와 재현성이 좋아집니다.

### Open Addressing with Double Hashing
- 별도 체이닝 구조 없이 배열 기반으로 동작을 통제할 수 있습니다.
- 충돌이 발생했을 때 probe sequence를 명확하게 설명하고 테스트하기 좋습니다.
- second hash를 활용해 선형 탐사보다 군집화 문제를 줄이는 방향을 취할 수 있습니다.

### Tombstone deletion
- open addressing에서 삭제 후 탐색 정확성을 유지하기 위한 핵심 전략입니다.
- 삭제된 슬롯을 즉시 비움 처리하지 않고 tombstone으로 표시하면, 그 뒤에 있는 키 탐색이 끊기지 않습니다.
- insert 시 tombstone 재사용 정책을 별도로 테스트할 수 있어 구현 통제가 분명합니다.

### Compact representation + promotion
- 작은 hash는 단순 선형 탐색 구조가 더 읽기 쉽고 구현 비용이 낮습니다.
- 데이터가 커졌을 때만 hashtable로 승격하면 작은 데이터와 큰 데이터 양쪽에서 균형 잡힌 설계를 만들 수 있습니다.
- Redis-like 자료구조의 “작을 때는 compact, 커지면 승격” 흐름을 학습하기 좋습니다.

## 핵심 정책

### 해싱
- 알고리즘: MurmurHash3
- seed: `0`

### 충돌 해결
- 방식: Open Addressing with Double Hashing
- probe sequence는 결정적이어야 합니다.
- second hash / probe step은 `0`이 아니어야 합니다.
- capacity가 2의 거듭제곱일 때 전체 테이블을 순회할 수 있어야 합니다.

### 삭제
- tombstone 전략을 사용합니다.
- lookup은 tombstone을 지나 계속 진행해야 합니다.
- insert는 첫 tombstone을 기억하되, 뒤에 같은 키가 있는지 먼저 확인한 후에만 재사용합니다.

### 리사이즈
- initial capacity = `8`
- grow when `used / capacity > 0.7`
- grow target = `capacity * 2`
- shrink when `live_count / capacity < 0.2`
- shrink target = `max(8, capacity // 2)`

정의:
- `live_count`: 현재 살아 있는 엔트리 수
- `used`: live entry + tombstone 수

리사이즈 시에는 live entry만 재삽입하고 tombstone은 버립니다.

### Compact mode와 promotion
- 기본 compact 유지 조건:
  - entry count `<= 32`
  - `max(field length, value length) <= 64 bytes`
- compact 표현은 `(field, value)` 쌍의 명시적 리스트 기반을 기본안으로 사용합니다.
- 임계치를 넘으면 `OpenAddressHashTable`로 promotion 합니다.
- promotion 후에도 논리적 내용은 유지되어야 합니다.

## 저장소 내 예상 반영 위치
현재 저장소 기준으로 예상되는 반영 위치는 다음과 같습니다.

- `store/hash_table.py`
  - hash 코어 구현
- `store/datastore.py`
  - hash 저장 경로 연결
- `commands/hash_cmds.py`
  - hash 명령 구현
- `tests/test_hash_table.py`
  - 해시 테이블 단위 테스트
- `tests/test_hash_cmds.py`
  - 명령/스토어 통합 테스트

이 범위를 넘는 광범위한 마이그레이션은 기본 계획에 포함하지 않습니다.

## 현재 상태와 목표 상태

### 현재 상태
- hash 저장 경로는 커스텀 `Hash` / `OpenAddressHashTable`로 연결되어 있습니다.
- hash 명령 경로는 동작 가능한 상태이며, Redis-like 응답 형태를 반환합니다.
- 해시 전용 테스트가 추가되어 probing, tombstone, resize, promotion을 검증합니다.

### 목표 상태
- hash 저장 경로가 커스텀 `Hash` / `OpenAddressHashTable`로 동작합니다.
- 해싱, 프로빙, tombstone, 리사이즈, promotion 정책이 코드와 테스트에서 확인 가능합니다.
- hash 관련 명령이 일관된 Redis-like 동작을 제공합니다.

## 테스트 및 검증 계획
구현 시 아래 시나리오를 테스트 대상으로 둡니다.

- insert
- update existing key
- lookup hit / miss
- delete
- tombstone-aware lookup
- tombstone reuse on insert
- collision-heavy cases
- grow resize
- shrink resize
- compact-to-hashtable promotion
- behavior preservation after promotion
- repeated delete / reinsert edge cases

## 제한사항
- 대상 hash-table 동작에 Python 내장 `dict`를 사용하지 않습니다.
- built-in `dict`를 전역적으로 대체하지 않습니다.
- dependency는 기본적으로 추가하지 않습니다.
- public API를 바꾸는 방향은 사전 승인 없이는 진행하지 않습니다.

## 후속 아이디어
아래 항목은 구현 이후 검토할 수 있는 후속 주제입니다.

- hash 내부 통계 정보 노출 여부 검토
- probe 길이와 충돌 패턴 관찰용 디버그 도구 추가
- compact threshold 튜닝 실험
- hash 외 자료구조에도 유사한 설계 원칙을 적용할지 검토
