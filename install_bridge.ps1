# install_bridge.ps1
Write-Host "==========================================="
Write-Host "Antigravity <-> Claude MCP Bridge Installer"
Write-Host "==========================================="
Write-Host ""

# 1. Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[+] Found Python: $pythonVersion"
} catch {
    Write-Host "[-] Python is not installed or not in PATH."
    Write-Host "Please install Python from python.org or the Microsoft Store."
    Exit
}

# 2. Install dependencies
Write-Host "[*] Installing required Python libraries (mcp, psutil)..."
python -m pip install mcp psutil --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "[-] Failed to install dependencies. Please check your Python installation."
    Exit
}

# 3. Get directory of this script
$scriptPath = $MyInvocation.MyCommand.Path
$bridgeDir = Split-Path -Parent $scriptPath
$serverPath = Join-Path $bridgeDir "server.py"

# 4. Find all Claude Desktop config paths
$candidatePaths = @(
    "$env:APPDATA\Claude\claude_desktop_config.json",
    "$env:LOCALAPPDATA\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json"
)

# 5 & 6 & 7. Update JSON safely using Python (works on all versions)
Write-Host "[*] Updating Claude config files..."

foreach ($configPath in $candidatePaths) {
    $configDir = Split-Path -Parent $configPath
    if (-not (Test-Path -Path $configDir)) {
        New-Item -ItemType Directory -Force -Path $configDir | Out-Null
    }

    $pythonScript = @"
import json
import os
import sys

config_path = r'$configPath'
server_path = r'$serverPath'

config = {}
if os.path.exists(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            content = f.read().strip()
            if content:
                config = json.loads(content)
    except Exception as e:
        print(f"[-] Could not parse existing config: {e}. Creating fresh.")

if "mcpServers" not in config:
    config["mcpServers"] = {}

config["mcpServers"]["antigravity"] = {
    "command": "python",
    "args": [server_path]
}

with open(config_path, 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=2)

print(f"[+] Successfully merged Antigravity bridge into {config_path}!")
"@

    $pythonScriptFile = Join-Path $env:TEMP "patch_claude_config.py"
    Set-Content -Path $pythonScriptFile -Value $pythonScript -Encoding UTF8
    python $pythonScriptFile
    Remove-Item $pythonScriptFile -ErrorAction SilentlyContinue
}

Write-Host "[+] Successfully added Antigravity bridge to Claude!"
Write-Host ""
Write-Host "IMPORTANT: Please completely close and restart Claude Desktop for the changes to take effect."
Write-Host ""
