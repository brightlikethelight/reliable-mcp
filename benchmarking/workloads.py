#!/usr/bin/env python3
"""
Realistic workload definitions for MCP server benchmarking.
Each workload represents a real-world usage pattern.
"""

import random
import uuid
from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class WorkloadPattern(Enum):
    """Execution patterns for workloads."""
    SEQUENTIAL = "sequential"  # Operations run one after another
    PARALLEL = "parallel"      # Operations run concurrently
    MIXED = "mixed"           # Mix of sequential and parallel
    BURST = "burst"           # Bursts of activity with pauses


@dataclass
class Operation:
    """Single operation in a workload."""
    tool: str
    weight: float
    params_generator: callable = None
    
    def generate_params(self) -> Dict[str, Any]:
        """Generate parameters for this operation."""
        if self.params_generator:
            return self.params_generator()
        
        # Default parameter generators
        if self.tool == "write_file":
            return {
                "path": f"/private/tmp/bench_{uuid.uuid4().hex[:8]}.txt",
                "content": "x" * random.randint(100, 1000)
            }
        elif self.tool == "read_text_file":
            return {
                "path": "/private/tmp/bench_read.txt"  # Assumes file exists
            }
        elif self.tool == "list_directory":
            return {
                "path": "/private/tmp"
            }
        elif self.tool == "create_directory":
            return {
                "path": f"/private/tmp/bench_dir_{uuid.uuid4().hex[:8]}"
            }
        elif self.tool == "delete_file":
            return {
                "path": f"/private/tmp/bench_delete_{uuid.uuid4().hex[:8]}.txt"
            }
        elif self.tool == "get_file_info":
            return {
                "path": "/private/tmp"
            }
        else:
            return {}


@dataclass
class Workload:
    """Complete workload definition."""
    name: str
    description: str
    operations: List[Operation]
    pattern: WorkloadPattern
    duration_seconds: int = 60
    warmup_seconds: int = 5
    
    def select_operation(self) -> Operation:
        """Select an operation based on weights."""
        total_weight = sum(op.weight for op in self.operations)
        random_value = random.uniform(0, total_weight)
        
        cumulative = 0
        for op in self.operations:
            cumulative += op.weight
            if random_value <= cumulative:
                return op
        
        return self.operations[-1]
    
    def get_operations_sequence(self, count: int) -> List[Operation]:
        """Get a sequence of operations for benchmarking."""
        return [self.select_operation() for _ in range(count)]


class StandardWorkloads:
    """Collection of standard workloads for benchmarking."""
    
    @staticmethod
    def crud_heavy() -> Workload:
        """CRUD-heavy workload simulating typical application usage."""
        return Workload(
            name="CRUD Heavy",
            description="Balanced mix of Create, Read, Update, Delete operations",
            operations=[
                Operation("write_file", weight=0.3),
                Operation("read_text_file", weight=0.4),
                Operation("write_file", weight=0.2),  # Update via overwrite
                Operation("delete_file", weight=0.1)
            ],
            pattern=WorkloadPattern.MIXED
        )
    
    @staticmethod
    def read_intensive() -> Workload:
        """Read-intensive workload for cache-friendly systems."""
        return Workload(
            name="Read Intensive",
            description="80% reads, 20% directory listings",
            operations=[
                Operation("read_text_file", weight=0.8),
                Operation("list_directory", weight=0.15),
                Operation("get_file_info", weight=0.05)
            ],
            pattern=WorkloadPattern.PARALLEL
        )
    
    @staticmethod
    def write_intensive() -> Workload:
        """Write-intensive workload for testing write performance."""
        
        def small_file_generator():
            return {
                "path": f"/private/tmp/write_small_{uuid.uuid4().hex[:8]}.txt",
                "content": "x" * random.randint(10, 100)
            }
        
        def large_file_generator():
            return {
                "path": f"/private/tmp/write_large_{uuid.uuid4().hex[:8]}.txt",
                "content": "x" * random.randint(1000, 10000)
            }
        
        return Workload(
            name="Write Intensive",
            description="70% writes, 30% directory operations",
            operations=[
                Operation("write_file", weight=0.5, params_generator=small_file_generator),
                Operation("write_file", weight=0.2, params_generator=large_file_generator),
                Operation("create_directory", weight=0.2),
                Operation("list_directory", weight=0.1)
            ],
            pattern=WorkloadPattern.SEQUENTIAL
        )
    
    @staticmethod
    def real_world_mix() -> Workload:
        """Realistic mixed workload based on typical usage patterns."""
        return Workload(
            name="Real World Mix",
            description="Balanced mix simulating real application usage",
            operations=[
                Operation("list_directory", weight=0.2),
                Operation("read_text_file", weight=0.3),
                Operation("write_file", weight=0.2),
                Operation("get_file_info", weight=0.15),
                Operation("create_directory", weight=0.1),
                Operation("delete_file", weight=0.05)
            ],
            pattern=WorkloadPattern.MIXED
        )
    
    @staticmethod
    def burst_load() -> Workload:
        """Burst load pattern simulating periodic high activity."""
        return Workload(
            name="Burst Load",
            description="Bursts of high activity with quiet periods",
            operations=[
                Operation("write_file", weight=0.4),
                Operation("read_text_file", weight=0.4),
                Operation("list_directory", weight=0.2)
            ],
            pattern=WorkloadPattern.BURST
        )
    
    @staticmethod
    def metadata_heavy() -> Workload:
        """Metadata-heavy workload focusing on file info and listings."""
        return Workload(
            name="Metadata Heavy",
            description="Focus on metadata operations",
            operations=[
                Operation("list_directory", weight=0.4),
                Operation("get_file_info", weight=0.4),
                Operation("create_directory", weight=0.1),
                Operation("read_text_file", weight=0.1)
            ],
            pattern=WorkloadPattern.PARALLEL
        )
    
    @staticmethod
    def sequential_processing() -> Workload:
        """Sequential processing pattern for ETL-like workloads."""
        return Workload(
            name="Sequential Processing",
            description="Read-process-write pattern",
            operations=[
                Operation("read_text_file", weight=0.33),
                Operation("write_file", weight=0.33),
                Operation("delete_file", weight=0.34)
            ],
            pattern=WorkloadPattern.SEQUENTIAL,
            duration_seconds=30
        )
    
    @staticmethod
    def get_all() -> Dict[str, Workload]:
        """Get all standard workloads."""
        return {
            "crud_heavy": StandardWorkloads.crud_heavy(),
            "read_intensive": StandardWorkloads.read_intensive(),
            "write_intensive": StandardWorkloads.write_intensive(),
            "real_world_mix": StandardWorkloads.real_world_mix(),
            "burst_load": StandardWorkloads.burst_load(),
            "metadata_heavy": StandardWorkloads.metadata_heavy(),
            "sequential_processing": StandardWorkloads.sequential_processing()
        }
    
    @staticmethod
    def get_quick_benchmarks() -> Dict[str, Workload]:
        """Get quick benchmarks for rapid testing (shorter duration)."""
        workloads = {
            "quick_read": StandardWorkloads.read_intensive(),
            "quick_write": StandardWorkloads.write_intensive(),
            "quick_mixed": StandardWorkloads.real_world_mix()
        }
        
        # Reduce duration for quick testing
        for workload in workloads.values():
            workload.duration_seconds = 10
            workload.warmup_seconds = 2
        
        return workloads


def create_custom_workload(
    name: str,
    operations: List[tuple],  # List of (tool, weight) tuples
    pattern: str = "mixed",
    duration: int = 60
) -> Workload:
    """Create a custom workload from specifications."""
    
    ops = [Operation(tool, weight) for tool, weight in operations]
    
    return Workload(
        name=name,
        description=f"Custom workload: {name}",
        operations=ops,
        pattern=WorkloadPattern(pattern),
        duration_seconds=duration
    )


if __name__ == "__main__":
    # Test workload generation
    workloads = StandardWorkloads.get_all()
    
    print("Available Standard Workloads:")
    print("=" * 60)
    
    for key, workload in workloads.items():
        print(f"\n{workload.name}")
        print(f"  Description: {workload.description}")
        print(f"  Pattern: {workload.pattern.value}")
        print(f"  Duration: {workload.duration_seconds}s")
        print(f"  Operations:")
        for op in workload.operations:
            print(f"    - {op.tool}: {op.weight*100:.0f}%")
    
    # Test operation selection
    print("\n" + "=" * 60)
    print("Testing operation selection for Real World Mix:")
    
    workload = workloads["real_world_mix"]
    operations_count = {}
    
    for _ in range(1000):
        op = workload.select_operation()
        operations_count[op.tool] = operations_count.get(op.tool, 0) + 1
    
    print("\nOperation distribution (1000 samples):")
    for tool, count in sorted(operations_count.items()):
        print(f"  {tool}: {count/10:.1f}%")