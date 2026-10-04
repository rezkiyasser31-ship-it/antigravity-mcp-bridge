import os
import sys
import re
import json
import time
import subprocess
import traceback
import psutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from mcp.server.mcpserver import MCPServer

LOG_FILE = Path(__file__).parent / "bridge.log"

def log(msg: str):
    """Write log messages to bridge.log."""
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {msg}\n")
    except Exception:
        pass

MANAGER_INSTRUCTIONS = """
You are an Expert Engineering Manager and Lead Architect. The user is the Product Owner.
Your direct report and execution engine is the local Google Antigravity Agent, which has direct access to the user's workspace, code files, and terminal.

CRITICAL RULES FOR YOUR PERSONA:
- NEVER write code blocks for the user to copy-paste. You are a manager, not a typist. Antigravity does the typing.
- NEVER start delegating tasks immediately for new projects. Always act as an expert: ask clarifying questions, define the tech stack, and create a comprehensive step-by-step Project Plan first.
- Only delegate to Antigravity ONCE the user explicitly approves the project plan.

YOUR WORKFLOW AS MANAGER:
1. PLAN FIRST: Brainstorm with the user, define technical requirements, and plan the architecture or task breakdown.
2. DELEGATE: Once the plan is approved, DO NOT ask the user to copy-paste prompts. YOU directly delegate execution to Antigravity using `delegate_to_antigravity`.
3. INSTRUCT CLEARLY: When delegating, provide clear, actionable instructions, clear acceptance criteria, and target directory. Choose 'flash' for standard tasks or 'pro' for deep reasoning.
4. MONITOR: If the delegation tool returns `status: "still_running"`, wait a moment and use `inspect_antigravity_session` to check its progress.
5. REVIEW & ITERATE: Review Antigravity's execution report. If revisions are needed, use `send_feedback_to_antigravity` to guide Antigravity until the feature is solid.
6. REPORT: Summarize results and next steps back to the user.
"""

app = MCPServer(
    "antigravity-bridge",
    instructions=MANAGER_INSTRUCTIONS
)

USER_HOME = Path.home()
LANGUAGE_SERVER_EXE = str(USER_HOME / r"AppData\Local\Programs\Antigravity\resources\bin\language_server.exe")
AGENTAPI_BAT = str(USER_HOME / r".gemini\antigravity\bin\agentapi.bat")

BRAIN_DIRS = [
    USER_HOME / r".gemini\antigravity\brain",
    USER_HOME / r".gemini\antigravity-ide\brain",
]

def discover_antigravity_env(workspace_path: Optional[str] = None) -> Dict[str, str]:
    """Dynamically discover running language_server port, CSRF token, and project ID."""
    env = dict(os.environ)
    user_home = Path.home()
    target_ws = (workspace_path or "").lower().replace("\\", "/")

    # 1. Discover language_server process details
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            name = (proc.info['name'] or '').lower()
            if 'language_server' in name:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                token_match = re.search(r'--csrf_token\s+([a-f0-9\-]+)', cmdline)
                if token_match:
                    env['ANTIGRAVITY_CSRF_TOKEN'] = token_match.group(1)

                ports = []
                try:
                    for conn in proc.net_connections(kind='tcp'):
                        if conn.status == 'LISTEN':
                            ports.append(conn.laddr.port)
                except Exception:
                    pass

                if ports:
                    # Antigravity uses the higher listening port for LS
                    env['ANTIGRAVITY_LS_ADDRESS'] = f"localhost:{max(ports)}"
                break
    except Exception as e:
        log(f"Error inspecting language_server process: {e}")

    env['ANTIGRAVITY_APP_DATA_DIR'] = str(user_home / '.gemini' / 'antigravity').replace('\\', '/')

    # 2. Discover project_id for target workspace
    try:
        projects_dir = user_home / '.gemini' / 'config' / 'projects'
        fallback_id = None
        latest_mtime = 0

        if projects_dir.exists():
            for pfile in projects_dir.glob("*.json"):
                try:
                    with open(pfile, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        pid = data.get("id")
                        
                        mtime = pfile.stat().st_mtime
                        if pid and mtime > latest_mtime:
                            latest_mtime = mtime
                            fallback_id = pid
                            
                        for res in data.get("projectResources", {}).get("resources", []):
                            f_uri = res.get("folderUri", "").lower()
                            if target_ws in f_uri or target_ws.replace(":", "%3a") in f_uri:
                                env['ANTIGRAVITY_PROJECT_ID'] = pid
                                break
                        if 'ANTIGRAVITY_PROJECT_ID' in env:
                            break
                except Exception:
                    pass

        # Use fallback if exact match wasn't found
        if not env.get('ANTIGRAVITY_PROJECT_ID') and fallback_id:
            env['ANTIGRAVITY_PROJECT_ID'] = fallback_id

    except Exception as e:
        log(f"Error finding project_id: {e}")

    log(f"Discovered env: LS={env.get('ANTIGRAVITY_LS_ADDRESS')}, Project={env.get('ANTIGRAVITY_PROJECT_ID')}, CSRF={bool(env.get('ANTIGRAVITY_CSRF_TOKEN'))}")
    return env

def get_executable_command(subcommand_args: List[str]) -> List[str]:
    """Get the command array using direct exe if available, otherwise bat."""
    if os.path.isfile(LANGUAGE_SERVER_EXE):
        return [LANGUAGE_SERVER_EXE, "agentapi"] + subcommand_args
    if os.path.isfile(AGENTAPI_BAT):
        return [AGENTAPI_BAT] + subcommand_args
    raise FileNotFoundError("Neither language_server.exe nor agentapi.bat found")

def get_transcript_path(conversation_id: str) -> Path:
    """Find transcript.jsonl for a given conversation_id."""
    for b in BRAIN_DIRS:
        p = b / conversation_id / ".system_generated" / "logs" / "transcript.jsonl"
        if p.exists():
            return p
    return BRAIN_DIRS[0] / conversation_id / ".system_generated" / "logs" / "transcript.jsonl"

def read_transcript_steps(transcript_file: Path) -> List[Dict[str, Any]]:
    """Read and parse JSON lines from the transcript."""
    if not transcript_file.exists():
        return []
    steps = []
    try:
        with open(transcript_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        steps.append(json.loads(line))
                    except Exception:
                        pass
    except Exception as e:
        log(f"Error reading transcript {transcript_file}: {e}")
    return steps

def run_agentapi_cmd(subcommand_args: List[str], cwd: Optional[str] = None) -> Dict[str, Any]:
    """Run an agentapi command with auto-discovered environment and return JSON."""
    cmd = get_executable_command(subcommand_args)
    working_dir = cwd
    custom_env = discover_antigravity_env(working_dir)

    log(f"Executing: cmd={cmd[0]} {cmd[1:3]} in cwd={working_dir}")

    result = subprocess.run(
        cmd,
        cwd=working_dir,
        env=custom_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    log(f"Process finished: rc={result.returncode}, stdout_len={len(stdout)}, stderr={stderr}")

    if result.returncode != 0:
        raise RuntimeError(f"Antigravity command error (code {result.returncode}): {stderr or stdout}")

    try:
        return json.loads(stdout)
    except Exception:
        log(f"Output not JSON, raw stdout: {stdout}")
        return {"raw_output": stdout}

def wait_for_response(conversation_id: str, start_step_count: int, timeout_seconds: int = 45) -> Dict[str, Any]:
    """Poll transcript.jsonl until the agent completes its response turn."""
    transcript_file = get_transcript_path(conversation_id)
    deadline = time.time() + timeout_seconds
    tools_called = []
    last_content = ""
    seen_steps = start_step_count
    log(f"Waiting for response: conv={conversation_id}, transcript={transcript_file}")

    while time.time() < deadline:
        steps = read_transcript_steps(transcript_file)
        if len(steps) > seen_steps:
            new_steps = steps[seen_steps:]
            for s in new_steps:
                # Track tool calls
                for call in s.get("tool_calls", []):
                    tool_name = call.get("name", "unknown")
                    if tool_name not in tools_called:
                        tools_called.append(tool_name)
                        log(f"Tool called by Antigravity: {tool_name}")

                # Check for completed model turn
                if s.get("source") == "MODEL" and s.get("type") == "PLANNER_RESPONSE":
                    content = s.get("content", "")
                    tool_calls = s.get("tool_calls", [])
                    status = s.get("status", "")

                    if content and not tool_calls:
                        last_content = content
                        if status == "DONE":
                            log(f"Completed turn found at step {s.get('step_index')}")
                            return {
                                "status": "completed",
                                "conversation_id": conversation_id,
                                "agent_response": last_content,
                                "tools_executed": tools_called,
                                "total_steps": len(steps)
                            }
        time.sleep(1.0)

    # Return partial response if timed out
    steps = read_transcript_steps(transcript_file)
    for s in reversed(steps[start_step_count:]):
        if s.get("source") == "MODEL" and s.get("content"):
            last_content = s.get("content")
            break

    log(f"Wait timed out for conv={conversation_id}")
    return {
        "status": "still_running",
        "conversation_id": conversation_id,
        "message": "Task is taking a while and is still running in the background. Please use `inspect_antigravity_session` in a few moments to check the final results.",
        "partial_response": last_content or "Still thinking...",
        "tools_executed": tools_called,
        "total_steps": len(steps)
    }

@app.tool()
def delegate_to_antigravity(
    task_description: str,
    workspace_path: str,
    acceptance_criteria: Optional[str] = None,
    model: str = "flash",
    timeout_seconds: int = 45
) -> str:
    """[MANAGER TOOL] Delegate a technical task or implementation directive to Antigravity.
    
    Antigravity will inspect files, run commands, create/edit code, or execute tests,
    and report back the complete outcome.

    Args:
        task_description: Detailed task instructions, implementation requirements, or bug details.
        workspace_path: Working directory path (defaults to user project directory).
        acceptance_criteria: Specific requirements or checks Antigravity must fulfill before concluding.
        model: Model tier ('flash' for standard tasks, 'pro' for complex reasoning/refactors). Default 'flash'.
        timeout_seconds: Maximum time to wait for Antigravity (default 240s).
    """
    log(f"delegate_to_antigravity called: task={task_description[:80]}...")
    try:
        ws = workspace_path
        prompt_parts = [
            f"CRITICAL DIRECTIVE: You MUST execute this task inside the following directory: {ws}",
            f"Do not write files to your default project root. Use absolute paths or change directory to {ws} first.",
            f"Task: {task_description}"
        ]
        if acceptance_criteria:
            prompt_parts.append(f"Acceptance Criteria: {acceptance_criteria}")

        formatted_prompt = "\n\n".join(prompt_parts)

        cmd_res = run_agentapi_cmd(["new-conversation", f"--model={model}", formatted_prompt], cwd=ws)
        conv_id = cmd_res.get("response", {}).get("newConversation", {}).get("conversationId")

        if not conv_id:
            log(f"Failed to get conversationId: {cmd_res}")
            return json.dumps({
                "status": "error",
                "error": "Failed to create Antigravity conversation",
                "details": cmd_res
            }, indent=2)

        result = wait_for_response(conv_id, start_step_count=0, timeout_seconds=timeout_seconds)
        return json.dumps(result, indent=2)
    except Exception as e:
        log(f"Exception in delegate_to_antigravity: {traceback.format_exc()}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "trace": traceback.format_exc()
        }, indent=2)

@app.tool()
def send_feedback_to_antigravity(
    conversation_id: str,
    feedback: str,
    timeout_seconds: int = 45
) -> str:
    """[MANAGER TOOL] Send managerial review, follow-up feedback, or next-phase instructions to Antigravity."""
    log(f"send_feedback_to_antigravity called: conv={conversation_id}")
    try:
        transcript_file = get_transcript_path(conversation_id)
        initial_steps = len(read_transcript_steps(transcript_file))

        run_agentapi_cmd(["send-message", conversation_id, feedback])
        result = wait_for_response(conversation_id, start_step_count=initial_steps, timeout_seconds=timeout_seconds)
        return json.dumps(result, indent=2)
    except Exception as e:
        log(f"Exception in send_feedback_to_antigravity: {traceback.format_exc()}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "trace": traceback.format_exc()
        }, indent=2)

@app.tool()
def inspect_workspace(workspace_path: str, max_depth: int = 2) -> str:
    """[MANAGER TOOL] Scan the project directory tree to see existing files before planning."""
    log(f"inspect_workspace called: ws={workspace_path}")
    try:
        ws = Path(workspace_path)
        if not ws.exists():
            return json.dumps({"workspace": str(ws), "exists": False, "files": []})

        entries = []
        base_parts = len(ws.parts)
        for root, dirs, files in os.walk(ws):
            cur_depth = len(Path(root).parts) - base_parts
            if cur_depth >= max_depth:
                dirs.clear()
                continue
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "venv")]
            for f in files:
                rel = Path(root, f).relative_to(ws)
                entries.append(str(rel))

        return json.dumps({
            "workspace": str(ws),
            "exists": True,
            "file_count": len(entries),
            "files": entries[:50]
        }, indent=2)
    except Exception as e:
        log(f"Exception in inspect_workspace: {traceback.format_exc()}")
        return json.dumps({"status": "error", "error": str(e)}, indent=2)

@app.tool()
def inspect_antigravity_session(conversation_id: str, max_steps: int = 15) -> str:
    """[MANAGER TOOL] Review detailed execution logs, tool calls, and step-by-step history of an Antigravity session."""
    log(f"inspect_antigravity_session called: conv={conversation_id}")
    try:
        transcript_file = get_transcript_path(conversation_id)
        steps = read_transcript_steps(transcript_file)
        if not steps:
            return json.dumps({"error": f"No transcript found for {conversation_id}"}, indent=2)

        recent = steps[-max_steps:]
        summarized = []
        for s in recent:
            summarized.append({
                "step_index": s.get("step_index"),
                "source": s.get("source"),
                "type": s.get("type"),
                "status": s.get("status"),
                "content": s.get("content"),
                "tool_calls": [c.get("name") for c in s.get("tool_calls", [])] if "tool_calls" in s else None
            })
        return json.dumps({
            "conversation_id": conversation_id,
            "total_steps": len(steps),
            "recent_steps": summarized
        }, indent=2)
    except Exception as e:
        log(f"Exception in inspect_antigravity_session: {traceback.format_exc()}")
        return json.dumps({"status": "error", "error": str(e)}, indent=2)

# Aliases for backward compatibility
@app.tool()
def ask_antigravity(task: str, workspace_path: str, model: str = "flash", timeout_seconds: int = 180) -> str:
    """Send a task to Antigravity (alias for delegate_to_antigravity)."""
    return delegate_to_antigravity(task_description=task, workspace_path=workspace_path, model=model, timeout_seconds=timeout_seconds)

@app.tool()
def continue_antigravity_conversation(conversation_id: str, message: str, timeout_seconds: int = 180) -> str:
    """Send follow-up to Antigravity (alias for send_feedback_to_antigravity)."""
    return send_feedback_to_antigravity(conversation_id=conversation_id, feedback=message, timeout_seconds=timeout_seconds)

if __name__ == "__main__":
    log("Starting MCP Server...")
    app.run(transport="stdio")
