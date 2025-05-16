import asyncio
import logging
import json
from typing import List, Dict, Any, Optional

from llm_providers import BaseLLMProvider
from llm_providers.prompt_library import format_planner_prompt
# Assuming TaskType Enum exists in models.py
from models import TaskType

logger = logging.getLogger(__name__)

class PlanningAgent:
    def __init__(self, llm_provider: BaseLLMProvider):
        self.llm_provider = llm_provider

    async def generate_plan(self, user_query: str, job_id: str) -> List[Dict[str, Any]]:
        """
        Generates a structured execution plan based on the user query using an LLM.
        #TODO: fine tune prompt
        Returns:
            List[Dict[str, Any]]: A list of task dictionaries, validated.

        Raises:
            ValueError: If the LLM response is invalid or plan validation fails.
            RuntimeError: If the LLM call itself fails.
        """
        logger.info(f"[Job {job_id}] Planning Agent: Generating plan for query: '{user_query[:100]}...'")

        prompt = format_planner_prompt(user_query)

        try:
            logger.info(f"[Job {job_id}] Calling LLM Planner...")
            raw_llm_output = await self.llm_provider.generate(
                prompt=prompt,
                temperature=0.1, # Low temperature for deterministic planning,
                max_output_tokens=2048 # Adjust based on expected plan size
            )
            #below is the output/research plan from the AGENT(raw)
            logger.info(f"[Job {job_id}] Raw LLM Planner output:\n{raw_llm_output}")

            # --- Parse and Validate ---
            plan = self._parse_and_validate_plan(raw_llm_output, job_id)
            logger.info(f"[Job {job_id}] Successfully generated and validated plan with {len(plan)} steps.")
            return plan

        except json.JSONDecodeError as e:
            logger.error(f"[Job {job_id}] LLM Planner failed to produce valid JSON: {e}. Raw output: {raw_llm_output}")
            raise ValueError(f"LLM Planner output was not valid JSON: {e}") from e
        except ValueError as e: # Catch validation errors from _parse_and_validate_plan
             logger.error(f"[Job {job_id}] Plan validation failed: {e}. Raw output: {raw_llm_output}")
             raise # Re-raise the specific validation error
        except Exception as e:
            logger.exception(f"[Job {job_id}] Error during LLM Planner call: {e}")
            raise RuntimeError(f"LLM Planner execution failed: {e}") from e


    def _parse_and_validate_plan(self, llm_output: str, job_id: str) -> List[Dict[str, Any]]:
        """Attempts to parse the LLM output as JSON and validate the plan structure."""
        try:
            # Clean potential markdown fences (```json ... ```)
            if llm_output.strip().startswith("```json"):
                llm_output = llm_output.strip()[7:]
                if llm_output.strip().endswith("```"):
                    llm_output = llm_output.strip()[:-3]

            plan_list = json.loads(llm_output.strip())
        except json.JSONDecodeError as e:
            # Re-raise specifically for generate_plan to catch
            raise json.JSONDecodeError(f"Failed to decode LLM output as JSON: {e.msg}", e.doc, e.pos)


        if not isinstance(plan_list, list):
            raise ValueError("Planner output is not a JSON list.")

        validated_plan = []
        valid_task_types = {item.value for item in TaskType} # Get set of valid enum values

        for i, task_dict in enumerate(plan_list):
            if not isinstance(task_dict, dict):
                raise ValueError(f"Task item at index {i} is not a JSON object.")

            # Validate required keys
            if "task_type" not in task_dict or "description" not in task_dict or "parameters" not in task_dict:
                raise ValueError(f"Task item at index {i} is missing required keys (task_type, description, parameters). Found: {task_dict.keys()}")

            # Validate task_type
            task_type = task_dict["task_type"]
            if task_type not in valid_task_types:
                raise ValueError(f"Task item at index {i} has invalid task_type '{task_type}'. Valid types are: {valid_task_types}")

            # Validate parameters type
            if not isinstance(task_dict["parameters"], dict):
                 raise ValueError(f"Task item at index {i} 'parameters' field is not a JSON object.")

            # Basic parameter validation (can be expanded)
            if task_type == TaskType.SEARCH.value or task_type == TaskType.REASON.value:
                 if "query" not in task_dict["parameters"] or not isinstance(task_dict["parameters"]["query"], str):
                      raise ValueError(f"Task item at index {i} ({task_type}) is missing a valid string 'query' parameter.")
            if task_type == TaskType.SYNTHESIZE.value:
                 if "topic" not in task_dict["parameters"] or not isinstance(task_dict["parameters"]["topic"], str):
                      raise ValueError(f"Task item at index {i} ({task_type}) is missing a valid string 'topic' parameter.")
            # REPORT validation might depend on how source_task_id is handled (null ok?)

            # Add validated task to the plan
            validated_plan.append({
                "task_type": TaskType(task_type), # Convert string back to Enum member
                "description": task_dict["description"],
                "parameters": task_dict["parameters"]
            })

        # --- Overall Plan Logic Validation (Basic) ---
        if not validated_plan:
             raise ValueError("Generated plan is empty.")

        # Check if research plans end appropriately
        has_search = any(t["task_type"] == TaskType.SEARCH for t in validated_plan)
        has_synthesize_or_report = any(t["task_type"] in [TaskType.SYNTHESIZE, TaskType.REPORT] for t in validated_plan)
        last_task_type = validated_plan[-1]["task_type"]

        if has_search and not has_synthesize_or_report:
             logger.warning(f"[Job {job_id}] Generated plan includes SEARCH but lacks a final SYNTHESIZE or REPORT step.")
             # Decide whether to raise an error or just warn
             # raise ValueError("Plan includes SEARCH but does not end with SYNTHESIZE or REPORT.")

        if last_task_type not in [TaskType.REPORT, TaskType.SYNTHESIZE]:
             logger.warning(f"[Job {job_id}] Generated plan does not end with REPORT or SYNTHESIZE. Last task: {last_task_type}")
             # Might be acceptable for simple REASON tasks, but worth logging.

        return validated_plan