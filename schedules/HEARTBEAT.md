# Heartbeat Checklist

On each tick, perform these checks in order. If nothing needs attention, respond `HEARTBEAT_OK`.

## Checks
- [ ] Check `output.log` in the project root relative to where you run commands. Read the end of the file. 
  - If there are recent errors: synthesize them into a short summary report.
  - If there are no errors: output EXACTLY "Apex Systems Healthy".
- [ ] Review any pending scheduled task results
- [ ] Check system memory usage (if shell access available)
- [ ] Scan for any unresolved errors from previous sessions

## Rules
- If you find errors in `output.log`, outline them as an alert. Do NOT include `HEARTBEAT_OK`.
- If you find NO errors in `output.log`, output EXACTLY "Apex Systems Healthy" (which functions as an alert to notify the user). Do NOT include `HEARTBEAT_OK`.
- Never infer tasks from prior chats — only follow this checklist
