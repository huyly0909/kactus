"""Snowflake ID generator for distributed unique IDs."""

import hashlib
import os
import random
import socket
import time
from typing import Optional

from snowflake import SnowflakeGenerator
from snowflake.snowflake import MAX_INSTANCE


def _generate_instance_id() -> int:
    """Generate a unique instance ID using multiple factors."""
    hostname = socket.gethostname()
    pid = os.getpid()
    timestamp = int(time.time() * 1000)
    random_num = random.randint(0, 1000000)

    try:
        ip = socket.gethostbyname(hostname)
    except socket.error:
        ip = "127.0.0.1"

    combined = f"{hostname}:{ip}:{pid}:{timestamp}:{random_num}"
    hash_object = hashlib.md5(combined.encode())
    hash_hex = hash_object.hexdigest()
    instance_id = int(hash_hex[:8], 16) % MAX_INSTANCE
    return instance_id


def create_generator(
    instance: Optional[int] = None, epoch: Optional[int] = None
) -> SnowflakeGenerator:
    if not instance:
        instance = _generate_instance_id()
    if not epoch:
        epoch = int(time.mktime((2022, 8, 5, 17, 30, 0, 0, 0, 0))) * 1000
    return SnowflakeGenerator(instance, epoch=epoch)


__gen = create_generator()


def next_id() -> int:
    return next(__gen)


if __name__ == "__main__":
    print(next_id())
    print(next_id())
