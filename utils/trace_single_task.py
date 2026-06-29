# SPDX-FileCopyrightText: 2025 MiromindAI
#
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
import os
import pathlib
from pathlib import Path
import dotenv
import hydra

from src.logging.logger import bootstrap_logger
from config import config_name, config_path, debug_config
from src.core.pipeline import (
    create_pipeline_components,
    execute_task_pipeline,
)
from src.utils.markdown_export import write_task_markdown
from omegaconf import DictConfig


def _normalize_cli_text(value) -> str:
    """Fire parses comma-separated CLI values as tuples; turn them back into text."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(_normalize_cli_text(item) for item in value)
    return str(value)


async def single_task(
    cfg: DictConfig,
    logger: logging.Logger,
    task_id: str = "task_1",
    task_description: str = "Write a python code to say 'Hello, World!', use python to execute the code.",
    task_file_name: str = "",
    config_file_name: str = "",
) -> None:
    """Asynchrono us main function."""
    task_id = _normalize_cli_text(task_id)
    task_description = _normalize_cli_text(task_description)
    task_file_name = _normalize_cli_text(task_file_name)
    config_file_name = _normalize_cli_text(config_file_name)

    if os.getenv("MIROFLOW_PRINT_CONFIG", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        debug_config(cfg, logger)
    else:
        logger.debug("Skipping full config dump; set MIROFLOW_PRINT_CONFIG=1 to show it.")
    logs_dir = Path(cfg.output_dir)
    main_agent_tool_manager, sub_agent_tool_managers, output_formatter = (
        create_pipeline_components(cfg, logs_dir=str(logs_dir))
    )

    task_name = task_id
    log_path = pathlib.Path(".") / pathlib.Path(cfg.output_dir) / f"{task_name}.log"
    logger.info(f"logger_path is {log_path.absolute()}")

    # Execute task using the pipeline
    final_summary, final_boxed_answer, _ = await execute_task_pipeline(
        cfg=cfg,
        task_name=task_name,
        task_id=task_id,
        task_file_name=task_file_name,
        task_description=task_description,
        main_agent_tool_manager=main_agent_tool_manager,
        sub_agent_tool_managers=sub_agent_tool_managers,
        output_formatter=output_formatter,
        # relative to the folder where shell command is launched.
        log_path=log_path.absolute(),
    )

    markdown_path = write_task_markdown(
        output_path=pathlib.Path(".") / pathlib.Path(cfg.output_dir) / f"{task_name}.md",
        task_id=task_id,
        task_description=task_description,
        final_summary=final_summary,
        final_boxed_answer=final_boxed_answer,
        log_path=log_path.absolute(),
        config_name=config_file_name or "<unknown>",
    )

    # Print task result
    logger.info(
        f"Final Output for Task: {task_id}, summary = {final_summary}, boxed_answer = {final_boxed_answer}"
    )
    logger.info(f"Markdown report saved to {markdown_path.absolute()}")


def main(
    *args,
    task_id: str = "task_1",
    task: str = "Write a python code to say 'Hello, World!', use python to execute the code.",
    task_file_name: str = "",
    config_file_name: str = "",
):
    config_file_name = _normalize_cli_text(config_file_name)
    task_id = _normalize_cli_text(task_id)
    task = _normalize_cli_text(task)
    task_file_name = _normalize_cli_text(task_file_name)

    if config_file_name:
        chosen_config_name = config_file_name
    else:
        chosen_config_name = config_name()

    dotenv.load_dotenv()
    with hydra.initialize_config_dir(config_dir=config_path(), version_base=None):
        cfg = hydra.compose(config_name=chosen_config_name, overrides=list(args))
        logger = bootstrap_logger(
            level=os.getenv("LOGGER_LEVEL", "INFO"), to_console=True
        )

        # Test if logger is working
        logger.info("Logger initialized successfully")

        # Tracing functionality removed - miroflow-contrib deleted
        asyncio.run(
            single_task(
                cfg,
                logger,
                str(task_id),
                task,
                task_file_name,
                chosen_config_name,
            )
        )
