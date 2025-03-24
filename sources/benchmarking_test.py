import time

import pytest

from benchmarking import benchmark, benchmark_block, BenchmarkTracker, BenchmarkResult


@pytest.fixture
def clear_benchmark_results():
    """Fixture to clear benchmark results before and after each test."""
    BenchmarkTracker.clear_results()
    yield
    BenchmarkTracker.clear_results()


def test_benchmark_decorator(clear_benchmark_results):
    """Test the benchmark decorator functionality."""

    # Define a function to benchmark
    @benchmark()
    def example_function(sleep_time):
        time.sleep(sleep_time)
        return "result"

    # Run the function
    result = example_function(0.01)

    # Check the function still returns correctly
    assert result == "result"

    # Check that the benchmark was recorded
    benchmark_results = BenchmarkTracker.get_results()
    assert len(benchmark_results) == 1
    assert benchmark_results[0].name == "example_function"
    assert benchmark_results[0].execution_time >= 0.01
    assert benchmark_results[0].metadata.get("args_count") == 1


def test_benchmark_with_custom_name(clear_benchmark_results):
    """Test benchmark decorator with custom name."""

    @benchmark(name="CustomTest")
    def example_function():
        return "result"

    example_function()

    benchmark_results = BenchmarkTracker.get_results()
    assert len(benchmark_results) == 1
    assert benchmark_results[0].name == "CustomTest"


def test_benchmark_with_metadata(clear_benchmark_results):
    """Test benchmark decorator with custom metadata."""

    @benchmark(metadata={"category": "io_operations"})
    def example_function():
        return "result"

    example_function()

    benchmark_results = BenchmarkTracker.get_results()
    assert len(benchmark_results) == 1
    assert benchmark_results[0].metadata.get("category") == "io_operations"
    assert benchmark_results[0].metadata.get("args_count") == 0


def test_benchmark_block(clear_benchmark_results):
    """Test the benchmark_block context manager."""
    start, end = benchmark_block("test_block", {"type": "code_block"})

    start()
    time.sleep(0.01)
    end()

    benchmark_results = BenchmarkTracker.get_results()
    assert len(benchmark_results) == 1
    assert benchmark_results[0].name == "test_block"
    assert benchmark_results[0].execution_time >= 0.01
    assert benchmark_results[0].metadata.get("type") == "code_block"


def test_benchmark_tracker_get_total_execution_time(clear_benchmark_results):
    """Test getting total execution time from the tracker."""
    BenchmarkTracker.add_result(BenchmarkResult("test1", 1.5))
    BenchmarkTracker.add_result(BenchmarkResult("test2", 2.5))

    assert BenchmarkTracker.get_total_execution_time() == 4.0


def test_benchmark_tracker_get_summary(clear_benchmark_results):
    """Test getting a summary from the tracker."""
    BenchmarkTracker.add_result(BenchmarkResult("test1", 1.5, {"category": "api_calls"}))
    BenchmarkTracker.add_result(BenchmarkResult("test2", 2.5, {"category": "data_processing"}))

    summary = BenchmarkTracker.get_summary()

    assert "Performance Benchmark Summary:" in summary
    assert "test1: 1.5000s" in summary
    assert "test2: 2.5000s" in summary
    assert "category: api_calls" in summary
    assert "category: data_processing" in summary
    assert "Total execution time: 4.0000s" in summary


def test_benchmark_tracker_get_summary_empty(clear_benchmark_results):
    """Test getting a summary when no benchmarks are recorded."""
    assert BenchmarkTracker.get_summary() == "No benchmarks recorded."


def test_benchmark_tracker_clear_results(clear_benchmark_results):
    """Test clearing benchmark results."""
    BenchmarkTracker.add_result(BenchmarkResult("test1", 1.5))
    assert len(BenchmarkTracker.get_results()) == 1

    BenchmarkTracker.clear_results()
    assert len(BenchmarkTracker.get_results()) == 0


def test_benchmark_result_str():
    """Test string representation of benchmark result."""
    result = BenchmarkResult("test_func", 1.2345)
    assert str(result) == "test_func: 1.2345s"
