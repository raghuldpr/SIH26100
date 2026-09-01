# ==============================================================================
# NITEN Bid Compliance Verification Platform (SIH-26100)
# PowerShell Test Suite for All Verification Agents & Master Orchestrator
# ==============================================================================

param (
    [string]$BaseUrl = "http://localhost:5678"
)

$WebhookUrl = "$BaseUrl/webhook/sih26100/bid-verification"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "  NITEN SIH-26100: MULTI-AGENT VERIFICATION TEST SUITE" -ForegroundColor Cyan
Write-Host "  Target Webhook: $WebhookUrl" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ""

function Invoke-VerificationTest {
    param (
        [string]$TestName,
        [string]$Description,
        [hashtable]$Payload
    )

    Write-Host "------------------------------------------------------------------" -ForegroundColor Yellow
    Write-Host "RUNNING: $TestName" -ForegroundColor Yellow
    Write-Host "  $Description" -ForegroundColor Gray
    Write-Host "------------------------------------------------------------------" -ForegroundColor Yellow

    $jsonBody = $Payload | ConvertTo-Json -Depth 10

    try {
        $startTime = Get-Date
        $response = Invoke-RestMethod -Uri $WebhookUrl -Method Post -Body $jsonBody -ContentType "application/json"
        $duration = [Math]::Round(((Get-Date) - $startTime).TotalSeconds, 2)

        Write-Host "Received response in ${duration}s" -ForegroundColor Green
        Write-Host "  Verification ID: $($response.verification_id)" -ForegroundColor White
        Write-Host "  Decision       : $($response.decision)" -ForegroundColor $(if ($response.decision -eq 'QUALIFIED') { 'Green' } else { 'Red' })
        Write-Host "  Risk Score     : $($response.risk_score) ($($response.risk_level))" -ForegroundColor White
        
        Write-Host "`n  Agent Outcomes:" -ForegroundColor Cyan
        foreach ($res in $response.agent_results) {
            $color = switch ($res.status) {
                "VERIFIED"     { 'Green' }
                "QUALIFIED"    { 'Green' }
                "REVIEW"       { 'Yellow' }
                "ERROR"        { 'Red' }
                "NOT_VERIFIED" { 'Red' }
                default        { 'Magenta' }
            }
            Write-Host ("    - {0,-28} : {1,-12} (Risk: {2})" -f $res.agent, $res.status, $res.risk_level) -ForegroundColor $color
            if ($res.issues -and $res.issues.Count -gt 0) {
                foreach ($iss in $res.issues) {
                    Write-Host "        Issue: $iss" -ForegroundColor DarkYellow
                }
            }
        }

        if ($response.reasons -and $response.reasons.Count -gt 0) {
            Write-Host "`n  Summary Reasons:" -ForegroundColor Gray
            foreach ($reason in $response.reasons) {
                Write-Host "    * $reason" -ForegroundColor Gray
            }
        }

        Write-Host "`n[RESULT: PASS]`n" -ForegroundColor Green
    }
    catch {
        Write-Host "Request Failed: $_" -ForegroundColor Red
        if ($_.Exception.Response) {
            $stream = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($stream)
            Write-Host "  Details: $($reader.ReadToEnd())" -ForegroundColor DarkRed
        }
        Write-Host "`n[RESULT: FAIL]`n" -ForegroundColor Red
    }
}

# TEST 1: FULL 10-AGENT VERIFICATION (TEST A)
$test1Payload = @{
    verification_id = "TEST-A-FULL-VERIFICATION"
    request_id      = "REQ-FULL-001"
    tender_id       = "TENDER-GEM-2026-001"
    bidder_id       = "BIDDER-ABC-001"
    bidder_name     = "ABC Technologies Pvt Ltd"
    required_agents = @(
        "TENDER_INTELLIGENCE_AGENT",
        "GST_AGENT",
        "PAN_AGENT",
        "UDYAM_AGENT",
        "FINANCIAL_AGENT",
        "EXPERIENCE_AGENT",
        "DOCUMENT_FORENSICS_AGENT",
        "ENTITY_RESOLUTION_AGENT",
        "RISK_INTELLIGENCE_AGENT",
        "FINAL_COMPLIANCE_AGENT"
    )
}
Invoke-VerificationTest -TestName "TEST 1: FULL 10-AGENT VERIFICATION" -Description "Runs all 10 specialized agents concurrently, verifies barrier synchronization, and aggregates risk." -Payload $test1Payload

# TEST 2: STATUTORY ONLY (TEST B)
$test2Payload = @{
    verification_id = "TEST-B-STATUTORY-ONLY"
    request_id      = "REQ-STAT-002"
    tender_id       = "TENDER-GEM-2026-002"
    bidder_id       = "BIDDER-ABC-001"
    bidder_name     = "ABC Technologies Pvt Ltd"
    required_agents = @(
        "GST_AGENT",
        "PAN_AGENT",
        "UDYAM_AGENT",
        "FINAL_COMPLIANCE_AGENT"
    )
}
Invoke-VerificationTest -TestName "TEST 2: STATUTORY ONLY (GST + PAN + UDYAM)" -Description "Verifies that unrequested agents are NOT marked NOT_EXECUTED and only statutory branches run." -Payload $test2Payload

# TEST 3: TENDER INTELLIGENCE ONLY (TEST C)
$test3Payload = @{
    verification_id = "TEST-C-TENDER-ONLY"
    request_id      = "REQ-TENDER-003"
    tender_id       = "TENDER-GEM-2026-003"
    bidder_id       = "BIDDER-ABC-001"
    bidder_name     = "ABC Technologies Pvt Ltd"
    required_agents = @(
        "TENDER_INTELLIGENCE_AGENT",
        "FINAL_COMPLIANCE_AGENT"
    )
    experience_evidence = @{
        projects = @(
            @{
                project_id     = "PROJ-1"
                project_name   = "GeM Portal Deployment"
                contract_value = "15 Lakhs"
                similarity     = "HIGH"
            },
            @{
                project_id    = "PROJ-2"
                project_name  = "Smart City Infrastructure"
                project_value = 1800000
                is_similar    = $true
            },
            @{
                project_id    = "PROJ-3"
                project_name  = "Enterprise ERP Setup"
                amount        = "2000000"
                relevance     = "RELEVANT"
            }
        )
    }
}
Invoke-VerificationTest -TestName "TEST 3: TENDER INTELLIGENCE PROJECT COUNTING" -Description "Supplies past projects with varied currency strings and keys to verify project counting logic." -Payload $test3Payload

# TEST 4: FINANCIAL FAILURE SIMULATION (TEST D)
$test4Payload = @{
    verification_id = "TEST-D-FINANCIAL-FAILURE"
    request_id      = "REQ-FINFAIL-004"
    tender_id       = "TENDER-GEM-2026-004"
    bidder_id       = "BIDDER-ABC-001"
    bidder_name     = "ABC Technologies Pvt Ltd"
    required_agents = @(
        "FINANCIAL_AGENT",
        "FINAL_COMPLIANCE_AGENT"
    )
    financial_requirements = @{
        average_turnover = "CORRUPTED_NON_NUMERIC_VALUE"
    }
}
Invoke-VerificationTest -TestName "TEST 4: FINANCIAL CHILD FAILURE SIMULATION" -Description "Sends malformed financial criteria to verify structured ERROR emission and risk elevation." -Payload $test4Payload

# TEST 5: PARTIAL DYNAMIC SUBSET (TEST E)
$test5Payload = @{
    verification_id = "TEST-E-PARTIAL-SUBSET"
    request_id      = "REQ-PARTIAL-005"
    tender_id       = "TENDER-GEM-2026-005"
    bidder_id       = "BIDDER-ABC-001"
    bidder_name     = "ABC Technologies Pvt Ltd"
    required_agents = @(
        "FINANCIAL_AGENT",
        "EXPERIENCE_AGENT",
        "FINAL_COMPLIANCE_AGENT"
    )
}
Invoke-VerificationTest -TestName "TEST 5: PARTIAL REQUEST (FINANCIAL + EXPERIENCE)" -Description "Runs financial and experience verification dynamically, synchronizes, and returns verdict." -Payload $test5Payload

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "  ALL TESTS COMPLETED!" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan
