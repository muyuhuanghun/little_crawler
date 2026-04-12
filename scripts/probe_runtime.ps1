$uri = "http://127.0.0.1:8000/v1/runtime/probe"
try {
  $result = Invoke-RestMethod -Method Get -Uri $uri
  $result | ConvertTo-Json -Depth 8
} catch {
  Write-Error $_
  exit 1
}
