# Control coordination for authorized agent implementation

24 October 2026. Control verified the human's actual message in agent-design thread `01a16c65-cf68-78f0-becc-95dafb861edc`: build the two agents there, test their boundaries, and prepare OpenAI credential configuration. This supersedes planning-only scope for that chat's own runtime package. Do not move the work or create another agent chat.

## Ownership and activation

- Agent owner: `agents/`, its isolated development dependencies/tests and `agents/.env`; existing planning/agents/ and handoffs/agents-design.md remain theirs.
- Backend owner: backend/, config/, persistence, snapshot/conditional acceptance, task/resource/event continuation. Backend foundation assignment remains contracts/agent-foundation-v0.1.md.
- Frontend/demo owner unchanged. Control owns shared contract review and integration decisions.
- User-authorized implementation does not by itself approve a researched investment thesis, model choice, unresolved investment gates or implicit paid calls. Live model transport remains explicit opt-in under the supplied key/model and approved policy, consistent with the agent implementation plan.
- No credentials should be copied into source, contracts, handoffs, UI, logs or test fixtures. Existing root `.gitignore` covers **/.env; agents/.venv is now ignored too.

## Known Windows credential setup limitation

The human already encountered PowerShell `PSSecurityException` because running .ps1 files is disabled. Do not repeatedly prescribe direct script invocation as the only setup path or suggest disabling execution policy. Direct editing is the verified alternative pattern used for the Crustdata key:

```powershell
notepad C:\Users\ASUS\Desktop\ThesisOS\agents\.env
```

User adds `OPENAI_API_KEY=...` to that file, preserving existing lines. The agent key helper may remain for environments where scripts are allowed; an inline interactive setup alternative can also be provided by its owner. Keep model configuration explicit and separate; do not guess a usable model from key presence.

## Integration checkpoints

1. Agent owner reports exact compiled-graph input/output models and passing mocked-boundary tests; distinguish deterministic test evidence from genuine model behavior.
2. Backend owner reports the detached context/evaluation/conditional-acceptance slice and concurrency/staleness proof. A graph's own version checks cannot replace current database checks at acceptance.
3. Control compares actual models: company/person/role provenance, approval/version refs, evidence manifest, proposal disposition, specific gap/task intents, no-change/stale outcomes and data mode. Any projection to public v0.1 must preserve uncertainty and wire compatibility; conceptual monitor is not a license to rename operational states.
4. Choose the runtime dependency boundary explicitly before claiming backend integration. Separate development virtual environments do not automatically allow backend imports of the agent package. Compare a compatible installed package in the backend environment against a bounded JSON/CLI subprocess if needed; do not add an unplanned long-running service or second scheduler.
5. Only after approved policy, available runtime/model configuration and bounded call authorization are present, exercise one real assessment and changed-evidence reassessment with saved history. It may remain monitor. Preserve source/assessment mode labels and show failure separately from investment rejection.

Status: ownership and authorization synchronized. No graph/backend runtime integration or live semantic validation is claimed by this note. Await tested owner handoffs; do not duplicate their implementations in control.


## Human authorized real testing

The human has now saved the key and explicitly authorized the chats to use it for real testing. Control notified all three implementation owners. Prior opt-in requirement is satisfied for bounded validation calls; successful authentication/model behavior is not yet established. Agent owner may use an explicitly synthetic test policy/evidence packet for actual software/model testing without misrepresenting it as reviewed fund policy. Backend integration uses isolated test storage and preserves current demo mode. All real tests must distinguish actual API responses from mocked tests and retain usage/latency/failure evidence without secrets. Thesis approval remains separate.
