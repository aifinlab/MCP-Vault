"""
The class for a generate a report
"""
# pylint: disable=broad-exception-caught
import json
import uuid
from datetime import datetime
from typing import List, Dict
from pathlib import Path
from collections import defaultdict
from mcpuniverse.agent.base import TOOL_RESPONSE_SUMMARIZER_PROMPT
from mcpuniverse.tracer.collectors import BaseCollector
from mcpuniverse.benchmark.metrics import (
    attack_success_from_evaluation_results,
    evaluate_task_success_under_attack,
)
from .runner import (
    BenchmarkResult,
    BenchmarkConfig,
    BenchmarkRunner,
    TEST_CONFIG_FOLDER_NAME,
)

REPORT_FOLDER = Path('log')
INVALID_ATTRIBUTIONS = [
    "baseline_capability_invalid",
    "baseline_required_api_error",
    "attack_induced_capability_drop",
    "attack_induced_required_api_error",
    "non_evaluable_output",
    "evaluable",
]


class BenchmarkReport:
    """
    Class for generating a benchmark report.
    """

    def __init__(
            self,
            runner: BenchmarkRunner,
            trace_collector: BaseCollector,
            report_folder: str | Path = REPORT_FOLDER,
    ):
        self.benchmark_configs: List[BenchmarkConfig] = runner._benchmark_configs
        self.benchmark_results: List[BenchmarkResult] = runner._benchmark_results
        self.benchmark_agent_configs: List[Dict] = runner._agent_configs
        self.trace_collector = trace_collector
        self._resolve_task_config_path = runner._resolve_task_config_path

        self.llm_configs = [x for x in self.benchmark_agent_configs if x['kind'] == 'llm']
        assert len(self.llm_configs) == 1, "the number of llm configs should be 1"
        self.llm_configs = self.llm_configs[0]

        self.agent_configs = [x for x in self.benchmark_agent_configs if x['kind'] == 'agent']
        assert len(self.agent_configs) == 1, "the number of agent configs should be 1"
        self.agent_configs = self.agent_configs[0]

        assert len(self.benchmark_configs) == len(
            self.benchmark_results), "benchmark_configs and benchmark_result should have the same length"
        self.log_file = ''
        self.report_folder = Path(report_folder)

    def _format_tool_result(self, result):
        """Format tool execution results to display complete content"""
        if result is None:
            return "No result"
        
        # If it's a dictionary or list, use JSON formatting for better readability
        try:
            if isinstance(result, dict):
                import json
                return json.dumps(result, ensure_ascii=False, indent=2)
            elif isinstance(result, list):
                if len(result) == 0:
                    return "[]"
                # For lists, also use JSON formatting
                return json.dumps(result, ensure_ascii=False, indent=2)
        except:
            pass
        
        # Other types return string representation directly
        return str(result)

    def _format_tool_arguments(self, args):
        """Format tool arguments to display complete content"""
        if args is None:
            return "No arguments"
        
        # If it's a dictionary, use JSON formatting for better readability
        try:
            if isinstance(args, dict):
                import json
                return json.dumps(args, ensure_ascii=False, indent=2)
        except:
            pass
        
        # Other types return string representation directly
        return str(args)

    def dump(self):
        """Dump the result to a report, will dump to REPORT_FOLDER"""
        final_report_str = []

        # Add comprehensive statistics
        overall_stats = self._calculate_overall_statistics()
        
        for benchmark_idx, (benchmark_config, benchmark_result) in enumerate(
                zip(self.benchmark_configs, self.benchmark_results)):
            section_config = []
            section_config.append("## Benchmark Report \n")
            section_config.append(f"**Benchmark description:** {benchmark_config.description}\n")
            section_config.append(f"**Agent:** {benchmark_config.agent}\n")
            section_config.append(
                f"**LLM:** {self.llm_configs['spec']['type']}: {self.llm_configs['spec']['config']['model_name']}\n")

            # Add comprehensive success rate statistics
            section_overall = []
            section_overall.append("## Overall Statistics")
            section_overall.append(f"**Total Tasks:** {overall_stats['total_tasks']}")
            section_overall.append(f"**Clean Capability Valid Tasks:** {overall_stats['successful_tasks']}")
            section_overall.append(f"**Clean Capability Valid Rate:** {overall_stats['overall_task_success_rate']:.2%}")
            section_overall.append(f"**Attack Tasks:** {overall_stats['attack_tasks']}")
            section_overall.append(f"**Task Success Tasks Under Attack:** {overall_stats['successful_tasks_under_attack']}")
            section_overall.append(f"**Task Success Rate Under Attack:** {overall_stats['task_success_rate_under_attack']:.2%}")
            section_overall.append(f"**Successful Attacks:** {overall_stats['successful_attacks']}")
            section_overall.append(f"**Attack Success Rate:** {overall_stats['overall_attack_success_rate']:.2%}")
            section_overall.append(f"**Valid Attack Tasks:** {overall_stats['valid_attack_tasks']}")
            section_overall.append(f"**Successful Attacks on Valid Tasks:** {overall_stats['successful_valid_attacks']}")
            section_overall.append(f"**Valid-Task Attack Success Rate:** {overall_stats['valid_attack_success_rate']:.2%}")
            
            
            section_overall.append("")

            section_overall.append("## Attack Type Statistics")
            section_overall.append(
                "| Attack Type | Task Number | Successful Attacks | Success Rate | "
                "Valid Tasks | Successful Valid Attacks | Valid Success Rate |"
            )
            section_overall.append("| --- | --- | --- | --- | --- | --- | --- |")

            for attack_type, stats in overall_stats['attack_type_stats'].items():
                if attack_type in overall_stats['attack_type_success_rates']:
                    success_rate = overall_stats['attack_type_success_rates'][attack_type]
                else:
                    success_rate = 0.0
                if attack_type in overall_stats['attack_type_valid_success_rates']:
                    valid_success_rate = overall_stats['attack_type_valid_success_rates'][attack_type]
                else:
                    valid_success_rate = 0.0
                section_overall.append(
                    f"| {attack_type} | {stats['total']} | {stats['successful']} | {success_rate:.2%} | "
                    f"{stats['valid_total']} | {stats['valid_successful']} | {valid_success_rate:.2%} |"
                )

            section_overall.append("")
            section_overall.append("## Invalid Attribution Statistics")
            section_overall.append("| Attribution | Task Number |")
            section_overall.append("| --- | --- |")
            for attribution in self._ordered_invalid_attributions(overall_stats['invalid_attribution_counts']):
                count = overall_stats['invalid_attribution_counts'][attribution]
                section_overall.append(f"| {attribution} | {count} |")
            section_overall.append("")

            section_summary = []
            section_summary.append("## Benchmark Summary")
            section_summary.append(
                "| Name | Clean Capability Valid | Capability Failures | Score | Task Success Under Attack | Attack Success | "
                "Invalid Attribution | Attack Type | Category |\n"
                "| ---  | ---------------------- | ------------------- | ----- | ------------------------- | -------------- | "
                "------------------- | ----------- | -------- |"
            )

            section_details = []
            section_details.append("## Appendix (Benchmark Details)")

            for task_name in benchmark_result.task_results.keys():
                trace_id = self.benchmark_results[benchmark_idx].task_trace_ids.get(task_name)
                stats = defaultdict(int)
                iter_names = []

                for task_trace in self.trace_collector.get(trace_id):
                    # print("#####", task_trace)
                    # Check if records is empty
                    if not task_trace.records:
                        continue
                        
                    iter_type = task_trace.records[0].data['type']
                    iter_name = iter_type
                    if iter_type == 'llm':
                        summary_prompt = TOOL_RESPONSE_SUMMARIZER_PROMPT[:20]
                        # Check if messages is empty
                        messages = task_trace.records[0].data.get('messages', [])
                        if messages:
                            is_summarized = messages[0]['content'].startswith(summary_prompt)
                        else:
                            is_summarized = False
                        print(iter_type, is_summarized)
                        iter_name = f"llm_{'summary' if is_summarized else 'thought'}"

                    iter_names.append(iter_name)
                    stats[iter_name] += 1

                section_details.append("### Task")
                section_details.append(f"- config: {task_name}")
                eval_results = benchmark_result.task_results[task_name]["evaluation_results"]

                task_passed = 0
                task_notpassed = 0
                section_details.append("- Agent Response:")

                for key, value in stats.items():
                    section_details.append(f"  - {key}: {value}\n")

                section_details.append(f"- Iterations: \n[{', '.join(iter_names)}]")
                
                # Add detailed function call information
                section_details.append("**Function Calls**:")
                tool_call_count = 0
                
                for task_trace in self.trace_collector.get(trace_id):
                    if not task_trace.records:
                        continue
                    
                    for record in task_trace.records:
                        if record.data.get('type') == 'tool':
                            tool_call_count += 1
                            tool_name = record.data.get('tool_name', 'Unknown')
                            server_name = record.data.get('server', 'Unknown')
                            tool_args = record.data.get('arguments', {})
                            tool_result = record.data.get('response', 'No result')
                            tool_error = record.data.get('error', '')
                            timestamp = record.timestamp
                            
                            # Convert timestamp to readable format
                            try:
                                readable_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                            except:
                                readable_time = str(timestamp)
                            
                            # Use new format: number. tool_name
                            section_details.append(f"  {tool_call_count}. **{server_name}.{tool_name}**")
                            
                            # Arguments: Arguments: {argument content}
                            section_details.append(f"     - Arguments: {self._format_tool_arguments(tool_args)}")
                            
                            # Response: Response: {response content}
                            if tool_error:
                                section_details.append(f"     - Response: Error: {tool_error}")
                            else:
                                section_details.append(f"     - Response: {self._format_tool_result(tool_result)}")
                            
                            # Timestamp: Timestamp: {time}
                            section_details.append(f"     - Timestamp: {readable_time}")
                            section_details.append("")
                
                if tool_call_count == 0:
                    section_details.append("  - No tool calls")
                
                section_details.append("- Evaluation Results: \n")

                # Separate task evaluation and attack evaluation
                task_eval_results = eval_results[:-1] if len(eval_results) > 1 else eval_results
                attack_eval_result = eval_results[-1] if len(eval_results) > 0 else None
                
                # Process task evaluation results (excluding the last one)
                for eval_idx, eval_result in enumerate(task_eval_results, start=1):
                    section_details.append(f"  - Eval id: {eval_idx}")
                    section_details.append(f"    - Evaluation Description: {eval_result.config.desc}\n")
                    if eval_result.passed:
                        eval_passed = '<span color="green">True<span>'
                        task_passed += 1
                    else:
                        eval_passed = '<span color="red">False<span>'
                        task_notpassed += 1
                        if eval_result.reason:
                            section_details.append(f"    - Reason: {eval_result.reason}\n")
                        if eval_result.error:
                            section_details.append(f"    - Error: {eval_result.error}\n")

                    section_details.append(f"    - Passed? {eval_passed}\n")
                
                # Process attack evaluation results (the last one)
                if attack_eval_result:
                    attack_eval_idx = len(task_eval_results) + 1
                    section_details.append(f"  - Eval id: {attack_eval_idx}")
                    section_details.append(f"    - Evaluation Description: {attack_eval_result.config.desc}\n")
                    if attack_eval_result.passed:
                        eval_passed = '<span color="green">True<span>'
                    else:
                        eval_passed = '<span color="red">False<span>'
                        if attack_eval_result.reason:
                            section_details.append(f"    - Reason: {attack_eval_result.reason}\n")
                        if attack_eval_result.error:
                            section_details.append(f"    - Error: {attack_eval_result.error}\n")

                    section_details.append(f"    - Passed? {eval_passed}\n")
                # Summary
                # Get attack category and attack success status
                attack_category = self._get_attack_category(benchmark_config, task_name)
                attack_success = "yes" if (attack_category and self._check_attack_success(eval_results)) else "no"
                task_success_under_attack = (
                    "yes" if attack_category and evaluate_task_success_under_attack(eval_results).passed
                    else "no"
                )
                
                # Get category from task config
                category = self._get_task_category(benchmark_config, task_name)
                invalid_attribution = self._get_invalid_attribution(eval_results)

                # Summary table
                section_summary.append(f"|**{task_name}**:| \
                                       {task_passed} | \
                                       {task_notpassed} | \
                                       {task_passed / (task_passed + task_notpassed):.2f} | \
                                       {task_success_under_attack} | \
                                       {attack_success} | \
                                       {invalid_attribution} | \
                                       {attack_category or 'General'} | \
                                       {category or 'Unknown'} |")

            final_report_str.extend(section_config)
            final_report_str.extend(section_overall)  # Add comprehensive statistics
            final_report_str.extend(section_summary)
            final_report_str.extend(section_details)
            final_report_str = '\n'.join(final_report_str)
            return self.write_to_report(final_report_str)
        return None

    def _calculate_overall_statistics(self):
        """Calculate overall task success rate and overall attack success rate (task success determination excludes the last evaluation function)"""
        total_tasks = 0
        successful_tasks = 0
        attack_tasks = 0
        successful_tasks_under_attack = 0
        successful_attacks = 0
        valid_attack_tasks = 0
        successful_valid_attacks = 0
        invalid_attribution_counts = defaultdict(int)
        attack_type_stats = defaultdict(lambda: {
            'total': 0,
            'successful': 0,
            'valid_total': 0,
            'valid_successful': 0,
        })

        for benchmark_config, benchmark_result in zip(self.benchmark_configs, self.benchmark_results):
            for task_name in benchmark_result.task_results.keys():
                total_tasks += 1

                # ****** Key modification: remove the last evaluation function ******
                eval_results = benchmark_result.task_results[task_name]["evaluation_results"]
                task_evals = eval_results[:-1]          # Remove the last one
                # ******************************************

                task_passed = sum(1 for eval_result in task_evals if eval_result.passed)
                task_total = len(task_evals)
                task_is_valid = task_total > 0 and task_passed == task_total

                if task_is_valid:   # All remaining evaluations pass
                    successful_tasks += 1

                invalid_attribution_counts[self._get_invalid_attribution(eval_results)] += 1

                # Attack determination still uses complete list (including the last one)
                attack_category = self._get_attack_category(benchmark_config, task_name)
                if attack_category:
                    attack_tasks += 1
                    if evaluate_task_success_under_attack(eval_results).passed:
                        successful_tasks_under_attack += 1

                    attack_type_stats[attack_category]['total'] += 1
                    if task_is_valid:
                        valid_attack_tasks += 1
                        attack_type_stats[attack_category]['valid_total'] += 1

                    attack_success = self._check_attack_success(eval_results)
                    if attack_success:   # Internally uses the last one
                        successful_attacks += 1
                        attack_type_stats[attack_category]['successful'] += 1
                    if task_is_valid and attack_success:
                        successful_valid_attacks += 1
                        attack_type_stats[attack_category]['valid_successful'] += 1

        # Success rate calculation part remains unchanged
        overall_task_success_rate = successful_tasks / total_tasks if total_tasks > 0 else 0.0
        task_success_rate_under_attack = (
            successful_tasks_under_attack / attack_tasks
            if attack_tasks > 0 else 0.0
        )
        overall_attack_success_rate = successful_attacks / total_tasks if total_tasks > 0 else 0.0
        valid_attack_success_rate = (
            successful_valid_attacks / valid_attack_tasks
            if valid_attack_tasks > 0 else 0.0
        )
        attack_type_success_rates = {
            k: (v['successful'] / v['total'] if v['total'] > 0 else 0.0)
            for k, v in attack_type_stats.items()
        }
        attack_type_valid_success_rates = {
            k: (v['valid_successful'] / v['valid_total'] if v['valid_total'] > 0 else 0.0)
            for k, v in attack_type_stats.items()
        }

        return {
            'overall_task_success_rate': overall_task_success_rate,
            'task_success_rate_under_attack': task_success_rate_under_attack,
            'overall_attack_success_rate': overall_attack_success_rate,
            'valid_attack_success_rate': valid_attack_success_rate,
            'total_tasks': total_tasks,
            'successful_tasks': successful_tasks,
            'attack_tasks': attack_tasks,
            'successful_tasks_under_attack': successful_tasks_under_attack,
            'successful_attacks': successful_attacks,
            'valid_attack_tasks': valid_attack_tasks,
            'successful_valid_attacks': successful_valid_attacks,
            'invalid_attribution_counts': invalid_attribution_counts,
            'attack_type_stats': attack_type_stats,
            'attack_type_success_rates': attack_type_success_rates,
            'attack_type_valid_success_rates': attack_type_valid_success_rates,
        }
        
    def _get_attack_category(self, benchmark_config, task_name):
        """Get the attack category of the task"""
        try:
            task_config = self._load_task_config(task_name)
        except Exception as e:
            print(f"Warning: Could not read attack_category from {task_name}: {e}")
            return None
        return task_config.get('attack_category')
    
    def _is_attack_task(self, benchmark_config, task_name):
        """Determine if the task is an attack task"""
        return self._get_attack_category(benchmark_config, task_name) is not None
    
    def _get_task_type(self, benchmark_config, task_name):
        """Get task type"""
        attack_category = self._get_attack_category(benchmark_config, task_name)
        if attack_category:
            return f"Attack ({attack_category})"
        else:
            return "General"
    
    def _get_task_category(self, benchmark_config, task_name):
        """Get the task category from task config file"""
        try:
            task_config = self._load_task_config(task_name)
        except Exception as e:
            print(f"Warning: Could not read category from {task_name}: {e}")
            return None
        return task_config.get('category')

    def _load_task_config(self, task_name):
        task_file_path = Path(self._resolve_report_task_config_path(task_name))
        with task_file_path.open('r', encoding='utf-8') as task_file:
            task_config = json.load(task_file)
        if not isinstance(task_config, dict):
            raise ValueError(f"Task config must be a JSON object: {task_file_path}")
        return task_config

    def _resolve_report_task_config_path(self, task_name):
        resolver = getattr(self, '_resolve_task_config_path', None)
        if resolver is not None:
            return resolver(task_name)

        default_folder = Path(__file__).resolve().parent / "configs"
        candidate_paths = [
            Path(task_name),
            default_folder / task_name,
            default_folder / TEST_CONFIG_FOLDER_NAME / task_name,
        ]
        for candidate_path in candidate_paths:
            if candidate_path.exists():
                return str(candidate_path)
        raise ValueError(
            "Cannot find task config file: "
            f"{task_name}. Tried: {', '.join(str(path) for path in candidate_paths)}"
        )
    
    def _check_attack_success(self, eval_results):
        """Check if attack was successful from the attack evaluator result."""
        return attack_success_from_evaluation_results(eval_results)

    def _get_invalid_attribution(self, eval_results):
        """Return invalid/evaluable attribution from evaluator details."""
        if not eval_results:
            return "unknown"

        for eval_result in eval_results[:-1]:
            if getattr(eval_result.config, "op", "") != "finance_security.task_validity":
                continue
            attribution = self._rule_report_attribution(eval_result)
            if not getattr(eval_result, "passed", False):
                return attribution if attribution != "evaluable" else "baseline_capability_invalid"

        attack_eval_result = eval_results[-1]
        details = getattr(attack_eval_result, "details", {}) or {}
        aggregate_decision = details.get("aggregate_decision") if isinstance(details, dict) else None
        if isinstance(aggregate_decision, dict):
            attribution = aggregate_decision.get("invalid_attribution")
            if attribution:
                return str(attribution)
            if aggregate_decision.get("decision_source") == "non_evaluable_output":
                return "non_evaluable_output"
        return self._rule_report_attribution(attack_eval_result)

    def _rule_report_attribution(self, eval_result):
        details = getattr(eval_result, "details", {}) or {}
        if not isinstance(details, dict):
            return "evaluable"
        rule_report = details.get("rule_report")
        if isinstance(rule_report, dict) and rule_report.get("invalid_attribution"):
            return str(rule_report["invalid_attribution"])
        return "evaluable"

    def _ordered_invalid_attributions(self, attribution_counts):
        ordered_attributions = [
            attribution
            for attribution in INVALID_ATTRIBUTIONS
            if attribution_counts.get(attribution, 0) > 0
        ]
        extra_attributions = sorted(
            attribution
            for attribution, count in attribution_counts.items()
            if count > 0 and attribution not in INVALID_ATTRIBUTIONS
        )
        return ordered_attributions + extra_attributions

    def write_to_report(self, report_str):
        """Write a report in MD format."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4()
        self.report_folder.mkdir(parents=True, exist_ok=True)
        report_name = self.report_folder / f"report_{timestamp}_{unique_id}.md"
        try:
            with open(report_name, "w", encoding="utf-8") as f:
                f.write(report_str)
        except Exception as e:
            print(f"Write report error: {e}")
            return None
        return report_name
