"""Shared async subprocess helper for all run_* modules."""
import asyncio


async def run_subprocess(cmd: list, timeout: int, env: dict = None) -> dict:
    """Run a subprocess asynchronously with timeout.

    Returns dict with returncode, stdout, stderr.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"Timeout after {timeout}s",
            }
        return {
            "returncode": proc.returncode,
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
        }
    except Exception as e:
        return {"returncode": -1, "stdout": "", "stderr": str(e)}
