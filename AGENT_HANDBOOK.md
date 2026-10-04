# Antigravity Agent Handbook & System Architecture

**Target Audience:** Antigravity AI Agents & Human Developers
**Purpose:** This document explains the architecture of the Claude-to-Antigravity MCP Bridge. If you are an Antigravity agent troubleshooting this repository on a new machine, read this file to understand how the system is wired.

---

## 1. Core Architecture (The Manager-Implementer Pattern)
This repository contains an MCP (Model Context Protocol) server (`server.py`) that links the Claude Desktop App to the local Antigravity installation.
- **Claude (Manager):** Handles brainstorming, architecture, and project planning. It delegates actual implementation by calling tools provided by this bridge.
- **Antigravity (Implementer):** The local agent (you) that receives tasks from Claude, runs terminal commands, writes code, and reports back.

---

## 2. Key Modifications & Solved Edge Cases
During the development of this bridge, several critical bugs were fixed. If you are modifying the bridge, **do not revert these fixes**.

### A. Dynamic User Paths
Initially, the bridge hardcoded paths (e.g., `C:\Users\yasser\...`). 
* **The Fix:** All paths in `server.py` and `install_bridge.ps1` are dynamically resolved using `Path.home()` or environmental variables. This ensures the bridge works for any Windows user (like `pccom`).

### B. Dynamic Project ID Discovery & Fallback
Antigravity's `new-conversation` command requires an active `ANTIGRAVITY_PROJECT_ID`. 
* **The Problem:** If Claude delegates a task to a brand new folder that hasn't been opened in the Antigravity IDE, the bridge won't find a matching Project ID and the command will fail.
* **The Fix:** The `discover_antigravity_env()` function scans `~/.gemini/config/projects/`. If it cannot find the target workspace, it dynamically grabs the **most recently modified Project ID** as a fallback to ensure the Antigravity daemon wakes up successfully.

### C. Strict Workspace Routing
* **The Problem:** Because we use a fallback Project ID (see above), Antigravity might wake up thinking it is working in "Project A", even though Claude requested files be created in "Folder B". Antigravity would dump files in the wrong place.
* **The Fix:** The hidden system prompt passed to Antigravity explicitly contains a `CRITICAL DIRECTIVE`. It forces Antigravity to respect the requested workspace path and use absolute paths (or change directory) before writing files, overriding the fallback project's root path.

### D. The 45-Second Asynchronous Timeout (Crucial)
* **The Problem:** Claude Desktop has a hardcoded network timeout of roughly 4 minutes (240s) for any MCP tool call. Large coding tasks easily take 5-10 minutes. If the bridge waits for Antigravity to finish, Claude Desktop panics and crashes the connection.
* **The Fix:** The bridge strips Claude's ability to set custom timeouts. `server.py` is hardcoded to release the connection after exactly **45 seconds**. If the task takes longer, the bridge returns `{"status": "still_running"}`. Claude is instructed to gracefully accept this and use the `inspect_antigravity_session` tool to poll the logs until the task finishes.

### E. Installer JSON Corruption
* **The Problem:** Older versions of Windows PowerShell (v5.1) corrupt JSON files with UTF-8 BOM headers when writing to Claude's `claude_desktop_config.json`, causing Claude to wipe the config entirely.
* **The Fix:** `install_bridge.ps1` delegates the actual JSON merging to an inline Python script that uses `utf-8-sig` to safely read and write the configuration without destroying Claude's internal app preferences. The script also contains zero `Pause` statements so agents can run it headlessly.

---

## 3. UI/UX Directives
The system prompt for Claude enforces strict UI/UX guidelines:
- Mobile-first, clean design.
- Premium color palettes (e.g., Slate/Zinc with Indigo/Emerald accents).
- High text contrast and subtle rounded borders (Tailwind).
Claude is instructed to pass these requirements down to Antigravity whenever frontend tasks are delegated.

## 4. Agent Troubleshooting Instructions
If you (an Antigravity Agent) are asked to fix an issue with this bridge:
1. Check `bridge.log` in the repository root for Python exceptions.
2. Check `~/.gemini/antigravity/brain/<conv-id>/.system_generated/tasks/` for installation errors.
3. Ensure Claude Desktop is restarted after any changes to `server.py` or the `claude_desktop_config.json`.
