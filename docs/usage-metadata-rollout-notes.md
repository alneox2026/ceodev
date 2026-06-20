# Usage Metadata Rollout Notes

Date: 2026-06-20

## Implemented

- Added Gemini usage metadata normalization in the gateway.
- Buffered chat responses now include additive `usage` data.
- Persisted assistant turn events receive the same normalized `usage` payload.
- Streaming completion and streaming fallback paths use the same normalization through `TurnAssembler`.
- Pricing basis is `gemini-2.5-flash` standard pricing:
  - input text/image/video: `$0.30` per 1M tokens
  - input audio: `$1.00` per 1M tokens
  - output including thinking tokens: `$2.50` per 1M tokens

## Local Verification

Passed:

```powershell
python -m pytest tests
```

Result: `82 passed`.

Root-level `python -m pytest` still collects the separate `adkagents/*` projects and fails before gateway tests because those projects expect their own working directory or `PYTHONPATH` for `app.*` imports. Run each ADK agent test suite from its own agent directory.

## First Deployed Smoke

Use Maxima first:

```powershell
$response = .\scripts\smoke_gateway.ps1 `
  -ServiceUrl <gateway-url> `
  -AuthToken <firebase-id-token> `
  -AgentId maxima `
  -Message "Return a one sentence answer and no web search."

$response | ConvertTo-Json -Depth 20
```

Expected buffered response includes `reply_text` and `usage`. If the live Agent Runtime event contains `usage_metadata` with prompt/candidate/thought token counts, `usage` should also include `billable_tokens`, `estimated_cost_usd`, and `estimated_cost_breakdown_usd`.

If Agent Runtime only returns `total_token_count`, the gateway preserves that count and skips cost fields because input/output split is unknown.
