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

1. **Brainstorming & Planning**: You act as the Product Owner. Claude acts as the Expert Architect. Claude will *refuse* to just write code—instead, it will ask clarifying questions and build a strict, step-by-step Project Plan.
2. **Approval**: You review the plan. Once you approve it, you tell Claude your local folder path (e.g., `C:\Users\Name\Desktop\MyProject`).
3. **Delegation**: Claude will call `delegate_to_antigravity`, specifying the exact requirements and acceptance criteria for the first milestone.
4. **Execution**: Antigravity wakes up in the background and does all the typing, terminal commands, and file creation.
5. **Supervision**: Claude inspects Antigravity's output. If any refinement is needed, Claude calls `send_feedback_to_antigravity` to force Antigravity to fix bugs before reporting back to you.
6. **Report**: Claude gives you an executive summary of the milestone and asks if you're ready for the next step.
