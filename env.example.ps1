# Copy to env.local.ps1 and fill it in locally. Do not commit that file.
$env:PROXMOX_BASE_URL = "https://pve.example.com:8006"
$env:PROXMOX_TOKEN_ID = "portfolio@pve!readonly"
$env:PROXMOX_TOKEN_SECRET = "REPLACE_WITH_YOUR_LOCAL_TOKEN"
$env:PROXMOX_ENABLE_WRITES = "false"
$env:PROXMOX_TIMEOUT = "15"
# Optional: PEM CA bundle for a certificate issued by your private CA.
# $env:PROXMOX_CA_FILE = "C:\path\to\lab-ca.pem"
