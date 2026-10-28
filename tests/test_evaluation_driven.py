import unittest
from prubeth.evaluation.benchmark import AutonomousBenchmarkRunner, BenchmarkResult, BenchmarkSuiteReport

class TestEvaluationDrivenDevelopment(unittest.TestCase):
    """Evaluation-Driven Development: Measuring Autonomous Agent Performance and Preventing Regressions."""

    def test_benchmark_runner_mock_eval(self):
        """Evaluation-Driven Development: Calculate Autonomy Quotient across simulated tasks."""
        runner = AutonomousBenchmarkRunner(controller=None)
        tasks = [
            {"name": "Fix Factorial Bug", "goal": "Implement math factorial with negative guards"},
            {"name": "Write Fast Fibonacci", "goal": "Write memoized fibonacci function"}
        ]
        report = runner.run_benchmark(tasks)

        self.assertIsInstance(report, BenchmarkSuiteReport)
        self.assertEqual(report.total_tasks, 2)
        self.assertEqual(report.completed_tasks, 2)
        self.assertEqual(report.failed_tasks, 0)
        self.assertEqual(report.autonomy_quotient, 100.0)
        self.assertEqual(len(report.results), 2)
        for r in report.results:
            self.assertTrue(r.success)
            self.assertEqual(r.state, "COMPLETED")

    def test_standard_benchmark_suite(self):
        """Verifies standard multi-file scenario suite defaults and table data."""
        from prubeth.evaluation.benchmark import STANDARD_ENGINEERING_BENCHMARKS
        runner = AutonomousBenchmarkRunner(controller=None)
        report = runner.run_benchmark()
        self.assertEqual(report.total_tasks, len(STANDARD_ENGINEERING_BENCHMARKS))
        self.assertEqual(report.completed_tasks, len(STANDARD_ENGINEERING_BENCHMARKS))
        self.assertEqual(report.autonomy_quotient, 100.0)
        table_data = report.summary_table_data()
        self.assertEqual(len(table_data), len(STANDARD_ENGINEERING_BENCHMARKS))

    def test_handle_benchmark_command(self):
        """Verifies CLI handler executes without error."""
        from unittest.mock import patch
        from prubeth.cli.commands import handle_benchmark_command
        with patch("prubeth.cli.commands.console.print") as mock_print:
            handle_benchmark_command([], controller=None)
            self.assertTrue(mock_print.called)

if __name__ == "__main__":
    unittest.main()
