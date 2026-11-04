# Drives the real SEGES NUAR workbook through Excel COM.
# Works on a temporary copy, writes only to unlocked input cells, never saves.
param([string]$Workbook, [string]$JobFile, [string]$Out)
$ErrorActionPreference = 'Stop'
$job = Get-Content -Raw -Encoding UTF8 $JobFile | ConvertFrom-Json
$RowNos = 18, 20, 22, 24, 26
$tmp = Join-Path $env:TEMP ("nuar_" + [guid]::NewGuid().ToString('N') + ".xlsx")
Copy-Item -LiteralPath $Workbook -Destination $tmp

function Set-Cell($ws, $addr, $v) {
    $r = $ws.Range($addr)
    if ($null -eq $v) { $r.ClearContents() | Out-Null }
    # A leading apostrophe stops Excel turning text such as "20. aug." into a date.
    elseif ($v -is [string]) { $r.Value2 = "'" + $v }
    else { $r.Value2 = [double]$v }
}

$xl = New-Object -ComObject Excel.Application
$out_lines = New-Object System.Collections.Generic.List[string]
$sw = [Diagnostics.Stopwatch]::StartNew()
try {
    $xl.Visible = $false
    $xl.DisplayAlerts = $false
    $xl.ScreenUpdating = $false
    $wb = $xl.Workbooks.Open($tmp, 0, $true)
    $xl.Calculation = -4135   # manual
    $ws = $wb.Worksheets.Item('NUAR-regneark')
    $regn = $wb.Worksheets.Item('Regn')
    $out_lines.Add((@('case', 'slot') + @($job.outputs | ForEach-Object { $_.name })) -join "`t")

    $touched = @{}
    for ($i = 0; $i -lt $job.cases.Count; $i++) {
        $case = $job.cases[$i]
        foreach ($p in $case.site.PSObject.Properties) { Set-Cell $ws $p.Name $p.Value }
        foreach ($a in @($touched.Keys)) { Set-Cell $ws $a $null }
        $touched = @{}
        $slot = 0
        foreach ($row in $case.rows) {
            $n = $RowNos[$slot]
            foreach ($p in $row.PSObject.Properties) {
                $a = "$($p.Name)$n"
                Set-Cell $ws $a $p.Value
                $touched[$a] = 1
            }
            $slot++
        }
        $xl.Calculate()
        for ($s = 0; $s -lt $case.rows.Count; $s++) {
            $n = $RowNos[$s]
            $vals = foreach ($o in $job.outputs) {
                $sh = if ($o.sheet -eq 'Regn') { $regn } else { $ws }
                $v = $sh.Range("$($o.col)$n").Value2
                if ($v -is [int]) { "#ERR" } elseif ($v -is [double]) { $v.ToString('R', [Globalization.CultureInfo]::InvariantCulture) } else { "$v" }
            }
            $out_lines.Add((@($i, $s) + @($vals)) -join "`t")
        }
    }
    $wb.Close($false)
}
finally {
    $xl.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($xl)
    Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue
}
[IO.File]::WriteAllLines($Out, $out_lines, (New-Object Text.UTF8Encoding($false)))
Write-Output ("{0} cases in {1:F1} s" -f $job.cases.Count, $sw.Elapsed.TotalSeconds)
