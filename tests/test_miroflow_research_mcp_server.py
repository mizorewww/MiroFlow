import asyncio
from pathlib import Path
import sys
import tempfile
import unittest

from src.tool.mcp_servers import miroflow_research_mcp_server as server


class MiroFlowResearchMcpServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        async with server._ACTIVE_TASK_LOCK:
            active_task = server._ACTIVE_TASK
            server._ACTIVE_TASK = None
        if active_task is not None:
            await server._terminate_process_group(active_task.process)

    async def test_new_task_cancels_active_task_and_writes_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            stdout_path = tmp / "old.stdout.log"
            stderr_path = tmp / "old.stderr.log"
            report_path = tmp / "old.md"

            with stdout_path.open("ab") as stdout_file, stderr_path.open(
                "ab"
            ) as stderr_file:
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-c",
                    "import time; time.sleep(30)",
                    stdout=stdout_file,
                    stderr=stderr_file,
                    start_new_session=True,
                )

            async with server._ACTIVE_TASK_LOCK:
                server._ACTIVE_TASK = server.ActiveResearchTask(
                    task_id="old_task",
                    question="old question",
                    context="",
                    report_path=report_path,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                    process=process,
                )
                await server._cancel_active_task_locked(
                    replacement_task_id="new_task",
                    reason="unit test replacement.",
                )

            self.assertIsNotNone(process.returncode)
            self.assertIsNone(server._ACTIVE_TASK)
            self.assertTrue(report_path.exists())
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("old_task", report)
            self.assertIn("new_task", report)
            self.assertIn("unit test replacement", report)


if __name__ == "__main__":
    unittest.main()
