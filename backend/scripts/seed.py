"""Database seed script for RecallOS.

Populates a test user, sample deck, 30 cards across 4 topics, and card states
with varied due dates (overdue, due today, upcoming).
Refuses to run if ENV=production.
"""
import os
import sys
from datetime import timedelta
from typing import List, Dict, Any

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.core.time import today_ist, now_ist, ist_midnight
from app.core.security import hash_password
from app.models.base import Base
from app.models.user import User
from app.models.deck import Deck
from app.models.card import Card
from app.models.card_state import CardState
from app.models.review import Review




SAMPLE_CARDS: List[Dict[str, Any]] = [
    # Topic 1: Computer Networks (8 cards)
    {
        "topic": "Computer Networks",
        "question": "What is the primary function of the Address Resolution Protocol (ARP)?",
        "answer": "Resolves an IPv4 address to its corresponding physical MAC address on a local network segment.",
        "distractors": [
            "Translates domain names to IP addresses across the internet.",
            "Dynamically assigns IP configuration parameters to host interfaces.",
            "Routes packets across different autonomous system boundaries.",
        ],
    },
    {
        "topic": "Computer Networks",
        "question": "How does TCP guarantee reliable data delivery compared to UDP?",
        "answer": "Through sequence numbers, cumulative acknowledgments, checksums, and sliding window retransmissions.",
        "distractors": [
            "By establishing dedicated circuit-switched optical lines between hosts.",
            "By dropping corrupt packets without notifying the transmitter.",
            "By broadcasting every payload to all peers simultaneously.",
        ],
    },
    {
        "topic": "Computer Networks",
        "question": "Which HTTP status code signifies that a resource has been permanently moved to a new URI?",
        "answer": "301 Moved Permanently",
        "distractors": [
            "302 Found",
            "307 Temporary Redirect",
            "410 Gone",
        ],
    },
    {
        "topic": "Computer Networks",
        "question": "What is the maximum transmission unit (MTU) standard for Ethernet frames?",
        "answer": "1500 bytes",
        "distractors": [
            "576 bytes",
            "4096 bytes",
            "9000 bytes",
        ],
    },
    {
        "topic": "Computer Networks",
        "question": "In the TCP 3-way handshake, what flags are sent by the server in response to SYN?",
        "answer": "SYN + ACK",
        "distractors": [
            "ACK only",
            "SYN only",
            "FIN + ACK",
        ],
    },
    {
        "topic": "Computer Networks",
        "question": "What mechanism does TCP use to avoid congesting the network pipe?",
        "answer": "Congestion window (cwnd) with slow start, congestion avoidance, fast retransmit, and fast recovery.",
        "distractors": [
            "Fixed baud rate throttle per network adapter.",
            "Strict round-robin scheduling on client routers.",
            "Priority queue packet dropping based on TTL values.",
        ],
    },
    {
        "topic": "Computer Networks",
        "question": "Which layer of the OSI model does a standard Layer 2 switch operate on?",
        "answer": "Data Link Layer",
        "distractors": [
            "Physical Layer",
            "Network Layer",
            "Transport Layer",
        ],
    },
    {
        "topic": "Computer Networks",
        "question": "What is the purpose of DNS TTL (Time To Live)?",
        "answer": "Specifies the number of seconds a resolver may cache the DNS query record before re-querying authoritative servers.",
        "distractors": [
            "The maximum hop count for DNS UDP datagrams.",
            "The lifespan of the domain registration at the registrar.",
            "The socket timeout for the TCP fallback query.",
        ],
    },

    # Topic 2: Operating Systems (8 cards)
    {
        "topic": "Operating Systems",
        "question": "What are the four necessary conditions for a deadlock to occur (Coffman conditions)?",
        "answer": "Mutual Exclusion, Hold and Wait, No Preemption, and Circular Wait.",
        "distractors": [
            "Starvation, Priority Inversion, Race Condition, and Thrashing.",
            "Context Switching, Demand Paging, Segmentation, and Fragmentation.",
            "Mutual Exclusion, Semaphore signaled, Spinlock locked, and Timeout.",
        ],
    },
    {
        "topic": "Operating Systems",
        "question": "What is the fundamental difference between a process and a thread?",
        "answer": "A process has its own isolated virtual address space; threads share the memory space of their parent process.",
        "distractors": [
            "Processes run in kernel mode while all threads run in user mode.",
            "Threads can execute across multiple machines whereas processes cannot.",
            "Processes do not possess a program counter or call stack.",
        ],
    },
    {
        "topic": "Operating Systems",
        "question": "What problem does the translation lookaside buffer (TLB) solve in virtual memory?",
        "answer": "Caches virtual-to-physical address translations to avoid multiple high-latency memory accesses per page table lookup.",
        "distractors": [
            "Stores dirty pages directly to non-volatile flash storage.",
            "Prevents stack overflow during deep recursion.",
            "Buffers asynchronous I/O read operations from disks.",
        ],
    },
    {
        "topic": "Operating Systems",
        "question": "What phenomenon occurs when excessive paging causes the OS to spend more time swapping than executing code?",
        "answer": "Thrashing",
        "distractors": [
            "Belady's Anomaly",
            "Priority Inversion",
            "Deadlock Convoy",
        ],
    },
    {
        "topic": "Operating Systems",
        "question": "How does the Copy-on-Write (COW) optimization improve fork() performance?",
        "answer": "Parent and child share physical pages marked read-only until either attempts a write, creating a duplicate page on demand.",
        "distractors": [
            "Immediately duplicates the entire physical memory allocation upon fork().",
            "Moves all memory pages into the OS swap partition before exec().",
            "Disables memory paging until the child process terminates.",
        ],
    },
    {
        "topic": "Operating Systems",
        "question": "What is Belady's Anomaly in page replacement algorithms?",
        "answer": "For FIFO page replacement, increasing page frames can paradoxically increase the number of page faults.",
        "distractors": [
            "LRU page replacement fails when working set size exceeds RAM.",
            "Optimal page replacement produces non-deterministic page hit ratios.",
            "Clock algorithm causes infinite loops on memory write contention.",
        ],
    },
    {
        "topic": "Operating Systems",
        "question": "What is the primary role of a counting semaphore?",
        "answer": "A synchronization primitive with an integer counter used to control access to a finite pool of shared resources.",
        "distractors": [
            "A hardware timer interrupt triggering CPU schedule ticks.",
            "A memory barrier preventing compiler instruction reordering.",
            "An encryption cipher securing inter-process communication sockets.",
        ],
    },
    {
        "topic": "Operating Systems",
        "question": "Why is the Shortest Job First (SJF) scheduling algorithm difficult to implement in real general-purpose systems?",
        "answer": "It requires knowing the length of the next CPU burst in advance, which is generally unpredictable.",
        "distractors": [
            "It causes guaranteed system deadlock within finite clock cycles.",
            "Hardware clocks cannot measure burst lengths in nanoseconds.",
            "It cannot be combined with priority queues.",
        ],
    },

    # Topic 3: Database Management (7 cards)
    {
        "topic": "Database Management",
        "question": "What are the four ACID properties in relational database transactions?",
        "answer": "Atomicity, Consistency, Isolation, and Durability.",
        "distractors": [
            "Availability, Consistency, Idempotency, and Durability.",
            "Atomicity, Concurrency, Indexing, and Distribution.",
            "Accuracy, Scalability, Isolation, and Decoupling.",
        ],
    },
    {
        "topic": "Database Management",
        "question": "Why are B+ Trees preferred over Binary Search Trees for disk-based relational storage engines?",
        "answer": "High fan-out yields low tree height, drastically minimizing expensive disk I/O seek operations.",
        "distractors": [
            "B+ Trees store all internal node keys and values entirely in CPU L1 cache.",
            "Binary search trees cannot handle numeric primary key sorting.",
            "B+ Trees consume zero memory overhead compared to hashtables.",
        ],
    },
    {
        "topic": "Database Management",
        "question": "What is the key difference between optimistic and pessimistic concurrency control?",
        "answer": "Pessimistic locks rows upfront before access; optimistic checks for collision/version mismatch at commit time.",
        "distractors": [
            "Optimistic locks the whole database; pessimistic only locks dirty pages.",
            "Pessimistic does not support rollback on transaction failure.",
            "Optimistic concurrency requires two-phase commit over networks.",
        ],
    },
    {
        "topic": "Database Management",
        "question": "What is a write-ahead log (WAL) and what guarantees does it provide?",
        "answer": "Changes are appended sequentially to persistent log files before dirty pages are flushed to disk, ensuring Durability and Crash Recovery.",
        "distractors": [
            "A memory cache holding pre-parsed SQL query execution plans.",
            "A secondary index recording unique foreign key constraints.",
            "An asynchronous read replica streaming client telemetry.",
        ],
    },
    {
        "topic": "Database Management",
        "question": "Which SQL isolation level prevents dirty reads, non-repeatable reads, and phantom reads?",
        "answer": "Serializable",
        "distractors": [
            "Read Committed",
            "Repeatable Read",
            "Read Uncommitted",
        ],
    },
    {
        "topic": "Database Management",
        "question": "In database normalization, what distinguishes BCNF from 3NF?",
        "answer": "For every non-trivial functional dependency X -> Y, X must be a superkey in BCNF.",
        "distractors": [
            "3NF requires no repeating groups, while BCNF removes transitive dependencies.",
            "BCNF allows multi-valued dependencies whereas 3NF bans them.",
            "BCNF requires every table to feature a composite primary key.",
        ],
    },
    {
        "topic": "Database Management",
        "question": "What does a composite index on (user_id, created_at) allow the query planner to optimize?",
        "answer": "Queries filtering on user_id alone or user_id combined with created_at, but not created_at alone (leftmost prefix rule).",
        "distractors": [
            "Queries filtering on created_at alone without referencing user_id.",
            "Cross-table joins without specifying foreign key relationships.",
            "Full text search indexing across arbitrary string columns.",
        ],
    },

    # Topic 4: System Design (7 cards)
    {
        "topic": "System Design",
        "question": "What does the CAP Theorem state about distributed data stores?",
        "answer": "In the presence of a network partition (P), a distributed system can guarantee at most Consistency (C) or Availability (A), but not both.",
        "distractors": [
            "A system can guarantee Capacity, Accuracy, and Performance simultaneously.",
            "Partitions can be avoided by scaling up RAM and bandwidth.",
            "Consistent hashing eliminates latency in distributed key-value caches.",
        ],
    },
    {
        "topic": "System Design",
        "question": "How does Consistent Hashing minimize re-mapping during cache cluster resizing?",
        "answer": "Nodes and keys are mapped to a circular hash ring; adding or removing a node only reassigns keys adjacent on the ring.",
        "distractors": [
            "Computes modulus of key hashes over the entire cluster size on every write.",
            "Stores all keys in a centralized master registry without hashing.",
            "Replicates 100% of data to all cluster machines continuously.",
        ],
    },
    {
        "topic": "System Design",
        "question": "What is the Token Bucket rate-limiting algorithm?",
        "answer": "Tokens are added to a bucket at a constant rate; requests consume a token and are dropped or queued if the bucket is empty.",
        "distractors": [
            "A sliding window log recording every timestamp in a Redis sorted set.",
            "A fixed window counter that resets to zero on minute boundaries.",
            "A queue that drops the oldest message whenever capacity is exceeded.",
        ],
    },
    {
        "topic": "System Design",
        "question": "What is the primary advantage of write-through caching over write-back caching?",
        "answer": "Write-through provides strong consistency and prevents data loss by writing to both cache and DB before acknowledging.",
        "distractors": [
            "Write-through offers significantly lower write latency than write-back.",
            "Write-through caches data only in client browser local storage.",
            "Write-through avoids ever invalidating stale cache keys.",
        ],
    },
    {
        "topic": "System Design",
        "question": "What problem do Bloom Filters solve in distributed storage engines like Cassandra or Bigtable?",
        "answer": "Rapidly tests whether an element definitely does not exist in an SSTable, preventing unnecessary high-latency disk reads.",
        "distractors": [
            "Encrypts data at rest using asymmetric public/private keys.",
            "Guarantees 100% false-negative-free and false-positive-free exact membership.",
            "Compresses write-ahead log files using LZO algorithms.",
        ],
    },
    {
        "topic": "System Design",
        "question": "What is the purpose of database sharding?",
        "answer": "Horizontally partitioning a database across multiple machines based on a shard key to scale beyond single-node hardware limits.",
        "distractors": [
            "Creating identical read-only replicas of the primary database node.",
            "Archiving deleted records into cold S3 storage buckets.",
            "Normalizing tables into Fourth Normal Form (4NF).",
        ],
    },
    {
        "topic": "System Design",
        "question": "How does the Circuit Breaker pattern protect microservices from cascading failures?",
        "answer": "Fails fast when downstream error thresholds are reached (Open state), periodically probing for recovery (Half-Open state).",
        "distractors": [
            "Automatically restarts crashing container pods in Kubernetes.",
            "Encrypts internal RPC payloads using mutual TLS certificates.",
            "Caches HTTP 500 error responses indefinitely for all clients.",
        ],
    },
]


def seed_database() -> None:
    """Seeds test data into the database."""
    env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development")).lower()
    if env == "production":
        print("ERROR: Refusing to seed database because ENV=production is active.")
        sys.exit(1)

    db = SessionLocal()
    today = today_ist()
    now = now_ist()

    print(f"Connecting to database (Current IST Date: {today})...")
    Base.metadata.create_all(bind=engine)

    try:
        # 1. Create or fetch test user
        test_email = "testuser@example.com"
        user = db.scalar(select(User).where(User.email == test_email))
        if not user:
            user = User(
                email=test_email,
                password_hash=hash_password("password123"),
                display_name="Test Student",
                exam_date=now + timedelta(days=21),  # Exam 3 weeks from now
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Created test user: {user.email} (Exam Date: {user.exam_date.date()})")
        else:
            print(f"Test user already exists: {user.email}")

        # 2. Create or fetch sample deck
        deck_hash = "seeded_cs_core_deck_hash_001"
        deck = db.scalar(
            select(Deck).where(
                Deck.user_id == user.id,
                Deck.file_hash == deck_hash,
            )
        )
        if not deck:
            deck = Deck(
                user_id=user.id,
                title="Computer Science Core (GATE & Interview Prep)",
                source_filename="cs_core_notes.pdf",
                file_hash=deck_hash,
            )
            db.add(deck)
            db.commit()
            db.refresh(deck)
            print(f"Created sample deck: '{deck.title}' (ID: {deck.id})")
        else:
            print(f"Sample deck already exists (ID: {deck.id})")

        # 3. Create cards and varied card states
        existing_cards_count = db.scalar(
            select(Card).where(Card.deck_id == deck.id)
        )
        if not existing_cards_count:
            print(f"Seeding {len(SAMPLE_CARDS)} cards with varied due dates...")
            for i, card_info in enumerate(SAMPLE_CARDS):
                card = Card(
                    deck_id=deck.id,
                    topic=card_info["topic"],
                    question=card_info["question"],
                    answer=card_info["answer"],
                    distractors=card_info["distractors"],
                )
                db.add(card)
                db.flush()

                # Stagger due dates:
                # 10 cards overdue (due 1 to 5 days ago)
                # 10 cards due today
                # 10 cards upcoming (due in 1 to 7 days)
                if i < 10:
                    due_date = today - timedelta(days=(i % 5) + 1)
                    repetitions = 2
                    interval_days = (i % 5) + 1
                    ease_factor = 2.4
                elif i < 20:
                    due_date = today
                    repetitions = 1
                    interval_days = 1
                    ease_factor = 2.5
                else:
                    due_date = today + timedelta(days=(i % 7) + 1)
                    repetitions = 3
                    interval_days = (i % 7) + 1
                    ease_factor = 2.6

                state = CardState(
                    card_id=card.id,
                    user_id=user.id,
                    ease_factor=ease_factor,
                    interval_days=interval_days,
                    repetitions=repetitions,
                    due_date=due_date,
                    lapses=0,
                )
                db.add(state)

            db.commit()
            print("Successfully inserted 30 cards and initial card states.")
        else:
            print("Cards already exist for this deck. Skipping card insertion.")

        # 4. Seed ~80 historical reviews across past 14 days
        existing_reviews_count = db.scalar(
            select(Review).where(Review.user_id == user.id)
        )
        if not existing_reviews_count:
            print("Seeding ~80 historical reviews over past 14 days...")
            all_cards = db.scalars(
                select(Card).where(Card.deck_id == deck.id)
            ).all()

            cards_by_topic: Dict[str, List[Card]] = {}
            for c in all_cards:
                cards_by_topic.setdefault(c.topic, []).append(c)

            latest_card_reviews: Dict[int, tuple] = {}

            # Review distribution plan: 14 days, total 80 reviews
            # Days 0 to 8 guarantee at least 9 consecutive review days ending today
            review_plan = [
                (13, 4),
                (12, 4),
                (11, 4),
                (10, 4),
                (9, 5),
                (8, 6),
                (7, 6),
                (6, 6),
                (5, 7),
                (4, 6),
                (3, 7),
                (2, 6),
                (1, 7),
                (0, 8),  # today
            ]
            total_seeded_reviews = 0

            # "Operating Systems": weak topic (accuracy < 60%, >= 5 reviews)
            os_ratings = [1, 2, 1, 2, 3, 1, 2, 1, 1, 2, 2, 1, 3, 1, 2, 1, 2, 1, 2, 3]
            os_idx = 0

            # Other 3 topics: strong (accuracy ~85-90%)
            strong_ratings = [3, 4, 4, 3, 4, 4, 3, 4, 4, 3, 4, 4, 2, 4, 3, 4, 4]
            strong_idx = 0

            for day_offset, num_reviews in review_plan:
                rev_date = today - timedelta(days=day_offset)
                base_time = ist_midnight(rev_date)

                for rev_i in range(num_reviews):
                    # Operating Systems gets ~25% of the reviews
                    if rev_i % 4 == 1 and "Operating Systems" in cards_by_topic:
                        topic = "Operating Systems"
                        card = cards_by_topic[topic][rev_i % len(cards_by_topic[topic])]
                        rating = os_ratings[os_idx % len(os_ratings)]
                        os_idx += 1
                    else:
                        other_topics = [t for t in cards_by_topic if t != "Operating Systems"]
                        topic = other_topics[rev_i % len(other_topics)]
                        card = cards_by_topic[topic][rev_i % len(cards_by_topic[topic])]
                        rating = strong_ratings[strong_idx % len(strong_ratings)]
                        strong_idx += 1

                    rev_dt = base_time + timedelta(hours=9 + (rev_i * 2), minutes=(rev_i * 7) % 60)
                    prev_int = 1 if rating <= 2 else 3
                    new_int = 1 if rating <= 2 else 6

                    review = Review(
                        user_id=user.id,
                        card_id=card.id,
                        rating=rating,
                        reviewed_at=rev_dt,
                        prev_interval=prev_int,
                        new_interval=new_int,
                    )
                    db.add(review)
                    total_seeded_reviews += 1

                    if card.id not in latest_card_reviews or rev_dt > latest_card_reviews[card.id][0]:
                        latest_card_reviews[card.id] = (rev_dt, new_int)

            # Update CardStates with last_reviewed_at and interval_days
            card_states = db.scalars(
                select(CardState).where(CardState.user_id == user.id)
            ).all()
            for cs in card_states:
                if cs.card_id in latest_card_reviews:
                    last_dt, new_interval = latest_card_reviews[cs.card_id]
                    cs.last_reviewed_at = last_dt
                    cs.interval_days = new_interval

            db.commit()
            print(f"Successfully seeded {total_seeded_reviews} historical reviews across 14 days.")
            print("Operating Systems seeded as weak topic (< 60% accuracy, >= 5 reviews).")
            print("Guaranteed at least 9 consecutive review days ending today.")
        else:
            print("Historical reviews already exist. Skipping review seeding.")

        print("Database seed completed successfully!")
    finally:
        db.close()



if __name__ == "__main__":
    seed_database()
