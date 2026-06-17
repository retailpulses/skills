---
name: higgsfield-guide
description: Generate images and videos using Higgsfield AI platform via accio-mcp-cli. Use when the user wants to generate images from text, create videos from images, check generation status, or manage Higgsfield credentials. Trigger phrases include "generate image", "generate video", "text to image", "image to video", "生成图片", "生成视频", "文生图", "图生视频", "Higgsfield", "higgsfield".
---

# Higgsfield AI — Image & Video Generation

Generate images and videos using the Higgsfield AI platform through `accio-mcp-cli`.

## Prerequisites

Ensure the user has connected Higgsfield credentials:

```bash
# Check authorization
accio-mcp-cli call list_all_authorizations --provider higgsfield

# Check stored credentials
accio-mcp-cli call check_higgsfield_credentials --json '{"user_id": "USER_ID"}'
```

If not connected, guide the user to [Higgsfield API Keys](https://cloud.higgsfield.ai/api-keys), then:

```bash
accio-mcp-cli call set_higgsfield_credentials --json '{"user_id": "USER_ID", "api_key": "hf_xxx", "api_key_secret": "hf_yyy"}'
```

## Important: Parameter Passing

**Always use `--json` format** to pass parameters. This avoids type coercion issues (e.g. numeric `user_id` being parsed as integer instead of string).

```bash
# CORRECT
accio-mcp-cli call generate_higgsfield_image --json '{"prompt": "...", "user_id": "USER_ID"}'

# WRONG — user_id will be parsed as integer and rejected
accio-mcp-cli call generate_higgsfield_image --user_id USER_ID --prompt "..."
```

---

## Text-to-Image Generation

### Tool: `generate_higgsfield_image`

### Supported Models

| Model ID | Description | Resolution | Notes |
| :--- | :--- | :--- | :--- |
| `higgsfield-ai/soul/standard` | Flagship model (default) | 480p / 720p / 1080p | Best general-purpose option |
| `flux-pro/kontext/max/text-to-image` | FLUX.2 Pro | Standard | Supports `seed` and `negative_prompt` for more control |
| `bytedance/seedream/v4/text-to-image` | ByteDance Seedream v4 | **2K / 4K only** | Higher quality; does NOT support 720p/1080p |

### Usage Examples

```bash
# Default model (Soul Standard)
accio-mcp-cli call generate_higgsfield_image --json '{
  "prompt": "A futuristic cyberpunk city with neon lights",
  "user_id": "USER_ID",
  "wait_for_completion": true
}'

# FLUX Pro with seed for reproducibility
accio-mcp-cli call generate_higgsfield_image --json '{
  "prompt": "A futuristic cyberpunk city with neon lights",
  "model_id": "flux-pro/kontext/max/text-to-image",
  "seed": 42,
  "negative_prompt": "blurry, low quality",
  "user_id": "USER_ID",
  "wait_for_completion": true
}'

# Seedream v4 (MUST specify 2K or 4K resolution)
accio-mcp-cli call generate_higgsfield_image --json '{
  "prompt": "A futuristic cyberpunk city with neon lights",
  "model_id": "bytedance/seedream/v4/text-to-image",
  "resolution": "2K",
  "user_id": "USER_ID",
  "wait_for_completion": true
}'
```

### Model-Specific Constraints

- **Seedream v4**: Resolution parameter MUST be `"2K"` or `"4K"`. Passing `"720p"` or `"1080p"` will return a 400 error.
- **FLUX Pro**: Accepts optional `seed` (integer) and `negative_prompt` (string).
- **Soul Standard**: Works with default parameters, no special constraints.

### Known Non-Working Models

| Model ID | Status | Reason |
| :--- | :--- | :--- |
| `reve/text-to-image` | ❌ Failed | Returns `Generation failed` |
| `bytedance/seedream/v4/edit` | ❌ Failed | Requires `image_urls` — this is an editing model, not text-to-image |

---

## Image-to-Video Generation

### Tool: `generate_higgsfield_video`

### Supported Models & Duration Limits

| Model ID | Description | Duration Support | Notes |
| :--- | :--- | :--- | :--- |
| `higgsfield-ai/dop/lite` | DOP Lite | **Fixed 5s** | Fastest generation speed |
| `higgsfield-ai/dop/standard` | DOP Standard | **Fixed 5s** | Balanced quality/speed |
| `higgsfield-ai/dop/turbo` | DOP Turbo | **Fixed 5s** | Highest quality in DOP series |
| `kling-video/v2.1/pro/image-to-video` | Kling (Kuaishou) | **5s or 10s** (discrete) | Set `duration_seconds` to 5 or 10; values in between (e.g. 7) default to 5s |
| `bytedance/seedance/v1/pro/image-to-video` | Seedance (ByteDance) | **5s or 10s** (discrete) | Set `duration_seconds` to 5 or 10; values in between default to 5s, values >10 are capped to 10s |

### Duration Behavior Summary

- **DOP Lite / Standard / Turbo**: `duration_seconds` parameter is **ignored**. Always generates 5s video.
- **Kling / Seedance**: Support **discrete** duration values of **5s** and **10s**. Values <10 produce 5s; set to 10 for 10s output. Values >10 are capped to 10s.

### Usage Examples

```bash
# DOP Standard (always 5s regardless of duration_seconds)
accio-mcp-cli call generate_higgsfield_video --json '{
  "prompt": "Cinematic camera flythrough of a city",
  "image_url": "https://example.com/image.png",
  "model_id": "higgsfield-ai/dop/standard",
  "duration_seconds": 5,
  "user_id": "USER_ID",
  "wait_for_completion": false
}'

# Kling 10s video
accio-mcp-cli call generate_higgsfield_video --json '{
  "prompt": "Cinematic camera flythrough of a city",
  "image_url": "https://example.com/image.png",
  "model_id": "kling-video/v2.1/pro/image-to-video",
  "duration_seconds": 10,
  "user_id": "USER_ID",
  "wait_for_completion": false
}'

# Seedance 10s video (max supported)
accio-mcp-cli call generate_higgsfield_video --json '{
  "prompt": "Cinematic camera flythrough of a city",
  "image_url": "https://example.com/image.png",
  "model_id": "bytedance/seedance/v1/pro/image-to-video",
  "duration_seconds": 10,
  "user_id": "USER_ID",
  "wait_for_completion": false
}'
```

### Known Non-Working Models

| Model ID | Status | Reason |
| :--- | :--- | :--- |
| `higgsfield-ai/dop/preview` | ❌ Failed | Not a valid model slug; use `lite`, `standard`, or `turbo` instead |

---

## Async Task Management

Video generation (and sometimes image generation) is asynchronous. Use these tools to manage tasks:

### Check Status

```bash
accio-mcp-cli call get_higgsfield_generation_status --json '{
  "request_id": "REQUEST_ID",
  "user_id": "USER_ID"
}'
```

**Status values**: `queued` → `in_progress` → `completed` / `failed`

### Cancel a Queued Task

```bash
accio-mcp-cli call cancel_higgsfield_generation --json '{
  "request_id": "REQUEST_ID",
  "user_id": "USER_ID"
}'
```

Only works for tasks still in `queued` status.

### Recommended Polling Strategy

For long-running video tasks, set up a **cron job** to poll every 2 minutes:

```
Schedule: { "kind": "every", "everyMs": 120000 }
Payload: agent message to check status and report when completed
```

When all tasks are completed or failed, remove the cron job automatically.

---

## Credential Management

| Tool | Description |
| :--- | :--- |
| `set_higgsfield_credentials` | Set/update API key and secret |
| `check_higgsfield_credentials` | Verify credentials exist and are valid |
| `delete_higgsfield_credentials` | Remove stored credentials |
| `list_higgsfield_users` | List all user IDs with stored credentials |

---

## Workflow Recommendations

### Image Generation Workflow

1. Choose a model based on requirements (general → Soul, controllable → FLUX Pro, high-res → Seedream v4)
2. Use `wait_for_completion: true` for images (usually completes in <30s)
3. Display the result image URL inline using markdown

### Video Generation Workflow

1. First generate or obtain a source image
2. Choose a video model:
   - Need speed? → DOP Lite (5s only)
   - Need quality? → DOP Turbo (5s only)
   - Need 10s video? → Kling or Seedance
3. Submit with `wait_for_completion: false` (video generation takes 2-5 minutes)
4. Set up a cron job to poll status every 2 minutes
5. Report results and clean up cron job when all tasks complete

### Batch Comparison Workflow

When comparing multiple models:
1. Submit all requests in parallel with `wait_for_completion: false`
2. Create a single cron job to poll all request IDs
3. Present results in a comparison table when all complete
