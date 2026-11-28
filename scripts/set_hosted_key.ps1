param(
    [ValidatePattern('^[a-z0-9-]+$')][string]$SecretName = 'rahbar-secret-alt',
    [string]$Distro = 'Ubuntu-22.04'
)
$ErrorActionPreference = 'Stop'
$secureKey = Read-Host 'Paste the fresh Groq key (input is hidden)' -AsSecureString
$pointer = [IntPtr]::Zero
try {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer).Trim()
    if ([string]::IsNullOrWhiteSpace($plainKey)) { throw 'The key is empty' }
    $encodedKey = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($plainKey))
    $payload = @{
        apiVersion = 'v1'; kind = 'Secret'; type = 'Opaque'
        metadata = @{ name = $SecretName; namespace = 'rahbar' }
        data = @{ LLM_API_KEY = $encodedKey }
    } | ConvertTo-Json -Depth 6 -Compress
    $payload | & wsl -d $Distro --exec kubectl apply -f -
    if ($LASTEXITCODE -ne 0) { throw 'Kubernetes rejected the secret update' }
    Write-Output 'Key saved locally in Kubernetes. No key was printed or written to a repository file.'
} finally {
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    Remove-Variable plainKey,encodedKey,payload,secureKey -ErrorAction SilentlyContinue
}
