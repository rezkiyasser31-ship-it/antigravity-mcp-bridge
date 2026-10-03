# Antigravity Bridge for Claude Desktop (Manager-Implementer Architecture)

This MCP integration defines the relationship between **Claude Desktop** and **Antigravity**:
* **Claude = Engineering Manager & Lead Architect**: Brainstorms with you, designs systems, breaks down project milestones, directly delegates implementation tasks, and reviews the results.
* **Antigravity = Hands & Implementation Engine**: Lives inside your environment, interacts with the local filesystem, executes terminal commands, writes code, and runs tests.

---

## Manager Tools Available in Claude Desktop

| Tool | Purpose |
| :--- | :--- |
| `inspect_workspace` | Scans the user's workspace directory tree so Claude knows what files exist before designing solutions. |
| `delegate_to_antigravity` | Directly delegates a task with context, workspace path, and explicit acceptance criteria. No copy-pasting needed. |
| `send_feedback_to_antigravity` | Provides managerial review, code corrections, or next-phase instructions to keep the session going. |
| `inspect_antigravity_session` | Reviews execution logs, tool calls, and step-by-step history if Claude wants to inspect details. |

---

## How It Works in Practice

1. **Brainstorming**: You chat with Claude in Claude Desktop to explore your idea, architecture, or feature.
2. **Delegation**: When you decide to implement, you tell Claude: *"Go ahead and implement this in my project."*
3. **Execution**: Claude calls `delegate_to_antigravity`, specifying the exact requirements and acceptance criteria.
4. **Supervision**: Claude inspects Antigravity's output and tools executed. If any refinement is needed, Claude calls `send_feedback_to_antigravity` to iterate.
5. **Report**: Claude gives you an executive summary of what was accomplished and discusses the next milestone with you.
