import time
from functools import wraps
from typing import Dict, Any, Callable, List, Optional, Tuple


class BenchmarkResult:
    """Contains the result of a performance benchmark."""

    def __init__(self, name: str, execution_time: float, metadata: Optional[Dict[str, Any]] = None):
        """Initialize the benchmark result.

        Args:
            name: Name of the benchmarked function or operation
            execution_time: Time taken to execute in seconds
            metadata: Additional metadata about the benchmark
        """
        self.name = name
        self.execution_time = execution_time
        self.metadata = metadata or {}

    def __str__(self) -> str:
        """String representation of the benchmark result."""
        return f"{self.name}: {self.execution_time:.4f}s"


class BenchmarkTracker:
    """Tracks and manages benchmarks for performance analysis."""

    _results: List[BenchmarkResult] = []

    @classmethod
    def add_result(cls, result: BenchmarkResult) -> None:
        """Add a benchmark result to the tracker.

        Args:
            result: The benchmark result to add
        """
        cls._results.append(result)

    @classmethod
    def get_results(cls) -> List[BenchmarkResult]:
        """Get all benchmark results.

        Returns:
            List of benchmark results
        """
        return cls._results

    @classmethod
    def clear_results(cls) -> None:
        """Clear all benchmark results."""
        cls._results.clear()

    @classmethod
    def get_total_execution_time(cls) -> float:
        """Get the total execution time of all benchmarks.

        Returns:
            Total execution time in seconds
        """
        return sum(result.execution_time for result in cls._results)

    @classmethod
    def get_summary(cls) -> str:
        """Get a formatted summary of all benchmark results.

        Returns:
            Formatted summary string
        """
        if not cls._results:
            return "No benchmarks recorded."

        summary = "Performance Benchmark Summary:\n"
        summary += "=================================\n"
        
        for result in cls._results:
            summary += f"{result}\n"
            
            # Add metadata if present
            if result.metadata:
                for key, value in result.metadata.items():
                    summary += f"  - {key}: {value}\n"
                    
        summary += "=================================\n"
        summary += f"Total execution time: {cls.get_total_execution_time():.4f}s\n"
        
        return summary


def benchmark(name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Callable:
    """Decorator to benchmark a function's execution time.
    
    Args:
        name: Optional name for the benchmark
        metadata: Optional metadata about the benchmark
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            benchmark_name = name if name else func.__name__
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            
            execution_time = end_time - start_time
            
            # Add dynamic metadata if provided
            final_metadata = metadata.copy() if metadata else {}
            if 'args_count' not in final_metadata:
                final_metadata['args_count'] = len(args)
                
            benchmark_result = BenchmarkResult(
                name=benchmark_name,
                execution_time=execution_time,
                metadata=final_metadata
            )
            
            BenchmarkTracker.add_result(benchmark_result)
            return result
        return wrapper
    return decorator


def benchmark_block(name: str, metadata: Optional[Dict[str, Any]] = None) -> Tuple[Callable, Callable]:
    """Context manager for benchmarking a block of code.
    
    Args:
        name: Name for the benchmark
        metadata: Optional metadata about the benchmark
        
    Returns:
        Start and end functions for the benchmark
    """
    start_time = [0.0]  # Use a list to allow modification in nested scope
    
    def start() -> None:
        start_time[0] = time.time()
        
    def end() -> None:
        execution_time = time.time() - start_time[0]
        benchmark_result = BenchmarkResult(
            name=name,
            execution_time=execution_time,
            metadata=metadata
        )
        BenchmarkTracker.add_result(benchmark_result)
        
    return start, end
