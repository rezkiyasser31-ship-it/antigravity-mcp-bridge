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

# 4. Find Claude Desktop config
$standardPath = "$env:APPDATA\Claude\claude_desktop_config.json"
$msixPath = "$env:LOCALAPPDATA\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json"

$configPath = $null
if (Test-Path -Path $msixPath) {
    $configPath = $msixPath
} else {
    $configPath = $standardPath
    $configDir = Split-Path -Parent $configPath
    if (-not (Test-Path -Path $configDir)) {
        New-Item -ItemType Directory -Force -Path $configDir | Out-Null
    }
}

Write-Host "[+] Using Claude Desktop config at: $configPath"

# 5. Read existing or create new config
$configObj = @{ mcpServers = @{} }
if (Test-Path $configPath) {
    $content = Get-Content $configPath -Raw
    if (-not [string]::IsNullOrWhiteSpace($content)) {
        try {
            $configObj = ConvertFrom-Json $content -AsHashtable
            if (-not $configObj.ContainsKey("mcpServers")) {
                $configObj["mcpServers"] = @{}
            }
        } catch {
            Write-Host "[-] Existing config is invalid JSON. Creating a new one..."
            $configObj = @{ mcpServers = @{} }
        }
    }
}

# 6. Add Antigravity server
if (-not $configObj.ContainsKey("mcpServers")) {
    $configObj["mcpServers"] = @{}
}

$configObj["mcpServers"]["antigravity"] = @{
    command = "python"
    args = @($serverPath)
}

# 7. Save config
$jsonContent = ConvertTo-Json -InputObject $configObj -Depth 10
Set-Content -Path $configPath -Value $jsonContent -Encoding UTF8

Write-Host "[+] Successfully added Antigravity bridge to Claude!"
Write-Host ""
Write-Host "IMPORTANT: Please completely close and restart Claude Desktop for the changes to take effect."
Write-Host ""
