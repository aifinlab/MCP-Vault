import json
import unittest

from mcpuniverse.evaluator.evaluator import Evaluator


class TestApproximateComparison(unittest.IsolatedAsyncioTestCase):

    async def test_approximate_evaluation_accepts_values_within_tolerance(self):
        evaluator = Evaluator(
            config={
                "func": "json -> get(value)",
                "op": "approx",
                "value": 1.0,
                "op_args": {"abs_tol": 0.01}
            }
        )

        result = await evaluator.evaluate(json.dumps({"value": 1.005}))

        self.assertEqual(result.passed, True)

    async def test_approximate_evaluation_rejects_values_outside_tolerance(self):
        evaluator = Evaluator(
            config={
                "func": "json -> get(value)",
                "op": "approx",
                "value": 1.0,
                "op_args": {"abs_tol": 0.01}
            }
        )

        result = await evaluator.evaluate(json.dumps({"value": 1.02}))

        self.assertEqual(result.passed, False)


if __name__ == "__main__":
    unittest.main()
