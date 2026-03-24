# Productive Apps Classification Feature

## Overview

Added support for **PRODUCTIVE_APPS** configuration to complement the existing **NON_PRODUCTIVE_APPS** and **MEETING_APPS** lists. This gives you granular control over which apps should be classified as productive vs non-productive.

## What Changed

### Configuration Files

**`.env` and `.env.example`:**
- Added `PRODUCTIVE_APPS` - comma-separated list of productive applications
- Added `PRODUCTIVE_DOMINANT_RATIO` threshold (default: 0.50 = 50%)
- Expanded `NON_PRODUCTIVE_APPS` list with more gaming/entertainment apps

**`backend/config.py`:**
- Added `PRODUCTIVE_APPS` list parsing
- Added `PRODUCTIVE_DOMINANT_RATIO` config parameter

**`backend/productivity.py`:**
- Added `_is_productive_event()` helper function
- Updated `_compute_ratios()` to return 4-tuple: `(productive_ratio, non_prod_ratio, meeting_ratio, distraction_ratio)`
- Updated decision tree with new Rule 2 for productive app dominance
- Updated `Bucket` dataclass to store `productive_ratio`

---

## Updated Decision Tree (6 Rules)

The classification engine evaluates rules **top-to-bottom**, and the **first matching rule wins**.

### Rule 1: Meeting Apps (Highest Priority)

**Condition:** `meeting_ratio >= 0.50` (≥50% of samples are meeting apps)

**Result:**
- State: **Productive**
- Confidence: Boosted to **0.85**
- Reason: `"meeting_detected"`

**Examples:**
- User on Zoom call for 35 seconds out of 60s bucket (6 samples, 3+ are Zoom)
- User in Microsoft Teams for entire 60s

**Why this works:**
- Meetings are real work (talking, listening, presenting)
- No keyboard/mouse activity is expected during meetings
- Always productive regardless of interaction metrics

---

### Rule 2: Non-Productive Apps Dominant (PRIORITY MOVED UP!)

**Condition:** `non_prod_ratio >= 0.6667` (≥66.67% of samples are non-productive apps)

**Result:**
- State: **Non-Productive**
- Confidence: Capped at **0.40**
- Reason: `"non_productive_app_dominant"`

**Default Non-Productive Apps:**
```
youtube, netflix, reddit, twitter, x.com, instagram, facebook,
tiktok, twitch, discord, spotify, steam, epic games,
league of leagues, fortnite, valorant, minecraft, roblox
```

**Why this is checked BEFORE productive apps:**
- Catches slacking behavior first (more important for enterprise monitoring)
- Higher threshold (66.67%) means we're confident user is wasting time
- Prevents gaming the system (can't mark VS Code as productive while YouTube is dominant)

**Example:**
```
T=0s:  YouTube
T=10s: YouTube
T=20s: YouTube
T=30s: YouTube
T=40s: VS Code (1 sample only)
T=50s: Chrome (Gmail)
```

**Analysis:**
- non_prod_ratio = 4/6 = 0.6667 (66.67%)
- productive_ratio = 1/6 = 0.1667 (16.67%)
- **Rule 2 triggers FIRST:** 0.6667 >= 0.6667 ✅
- **Classification:** Non-Productive (non_productive_app_dominant)
- **Result:** Even though VS Code is present, YouTube dominance wins

---

### Rule 3: Productive Apps Dominant (NEW!)

**Condition:** `productive_ratio >= 0.70` (≥70% of samples are productive apps)

**Result:**
- State: **Productive**
- Confidence: Boosted to **0.75**
- Reason: `"productive_app_dominant"`

**Default Productive Apps:**
```
visual studio code, vscode, pycharm, intellij, android studio, xcode,
sublime text, atom, vim, emacs, cursor, figma, sketch,
adobe photoshop, adobe illustrator, blender, unity, unreal engine,
docker, postman, tableau, excel, word, powerpoint, outlook,
notion, obsidian, roam research, jira, confluence, linear,
asana, trello, monday.com
```

**Examples:**

#### Example 1: Developer Coding (10s polling, 60s bucket)
```
T=0s:  VS Code
T=10s: VS Code
T=20s: VS Code  
T=30s: Chrome (Stack Overflow)
T=40s: VS Code
T=50s: Terminal
```

**Analysis:**
- productive_count = 4 (VS Code appears 3 times, Terminal once)
- productive_ratio = 4/6 = 0.6667 (66.67%)
- **Rule 2 triggers:** 0.6667 >= 0.50 ✅
- **Classification:** Productive (productive_app_dominant)

#### Example 2: Designer Working (10s polling, 60s bucket)
```
T=0s:  Figma
T=10s: Figma
T=20s: Chrome (Dribbble inspiration)
T=30s: Figma
T=40s: Slack (quick reply)
T=50s: Figma
```

**Analysis:**
- productive_count = 4 (Figma appears 4 times)
- productive_ratio = 4/6 = 0.6667 (66.67%)
- **Rule 2 triggers:** 0.6667 >= 0.50 ✅
- **Classification:** Productive (productive_app_dominant)

---

### Rule 3: Non-Productive Apps Dominant

**Condition:** `non_prod_ratio >= 0.6667` (≥66.67% of samples are non-productive apps)

**Result:**
- State: **Non-Productive**
- Confidence: Capped at **0.40**
- Reason: `"non_productive_app_dominant"`

**Default Non-Productive Apps:**
```
youtube, netflix, reddit, twitter, x.com, instagram, facebook,
tiktok, twitch, discord, spotify, steam, epic games,
league of legends, fortnite, valorant, minecraft, roblox
```

**Example:**
```
T=0s:  YouTube
T=10s: YouTube
T=20s: YouTube
T=30s: YouTube
T=40s: Chrome (Gmail)
T=50s: VS Code
```

**Analysis:**
- non_prod_count = 4 (YouTube appears 4 times)
- non_prod_ratio = 4/6 = 0.6667 (66.67%)
- **Rule 3 triggers:** 0.6667 >= 0.6667 ✅
- **Classification:** Non-Productive (non_productive_app_dominant)

**Note:** Higher threshold (66.67% vs 50%) means we're stricter about marking as non-productive.

---

### Rule 4: Anti-Cheat (Bot Detection)

**Condition:** Suspicious input pattern detected (metronomic keystrokes/clicks with no natural pauses)

**Result:**
- State: **Non-Productive**
- Confidence: Capped at **0.20**
- Reason: `"bot_like_input_pattern"`

**Detection Logic:**
- Too few zero-interaction samples (< 25% of samples have zero activity)
- Too few distinct interaction values (< 3 unique values)
- Indicates auto-clicker or key repeater

---

### Rule 5: Confidence-Based

**Condition:** `confidence >= 0.60` (high activity/presence signals)

**Result:**
- State: **Productive**
- Reason: `"confidence_above_threshold"`

**Confidence Formula:**
```
base = 0.35×density + 0.20×presence + 0.25×coverage + 0.20×idle_penalty

modifiers:
  × distraction_mult  (0.70 if distraction ≥ 30%)
  × non_prod_penalty  (1.0 - 0.5 × non_prod_ratio)
  × anti_cheat_mult   (0.30 if suspicious)

final_confidence = clamp(base × modifiers, 0.0, 1.0)
```

**Example:**
```
T=0s:  Chrome (GitHub)
T=10s: Terminal
T=20s: Slack
T=30s: Chrome (Documentation)
T=40s: Terminal
T=50s: Chrome (GitHub)
```

**Analysis:**
- No dominant productive/non-productive/meeting apps
- High keystroke/click activity
- Confidence = 0.72
- **Rule 5 triggers:** 0.72 >= 0.60 ✅
- **Classification:** Productive (confidence_above_threshold)

---

### Rule 6: Fallthrough (Insufficient Activity)

**Condition:** None of the above rules matched

**Result:**
- State: **Non-Productive**
- Reason: `"insufficient_activity_signals"`

**Example:**
```
T=0s:  Finder (idle)
T=10s: Finder (idle)
T=20s: Safari (reading)
T=30s: Safari (reading)
T=40s: Terminal (idle)
T=50s: Finder (idle)
```

**Analysis:**
- productive_ratio = 0 (Finder/Safari not in PRODUCTIVE_APPS)
- meeting_ratio = 0
- non_prod_ratio = 0
- Confidence = 0.25 (low activity: reading without interaction)
- **Rule 6 triggers:** Fallthrough
- **Classification:** Non-Productive (insufficient_activity_signals)

---

## Rule Priority Diagram

```
┌─────────────────────────────────────────────────────────┐
│  60-second bucket with 6 samples (10s polling)         │
│  Calculate: productive_ratio, non_prod_ratio,          │
│            meeting_ratio, confidence                    │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
      ┌──────────────┐
      │ Rule 1:      │  YES → Productive (meeting_detected)
      │ Meeting ≥50%?│
      └──────┬───────┘
             │ NO
             ▼
      ┌──────────────┐
      │ Rule 2:      │  YES → Productive (productive_app_dominant)
      │ Productive   │        confidence = 0.75
      │ App ≥50%?    │
      └──────┬───────┘
             │ NO
             ▼
      ┌──────────────┐
      │ Rule 3:      │  YES → Non-Productive (non_productive_app_dominant)
      │ Non-Prod     │        confidence = 0.40
      │ ≥66.67%?     │
      └──────┬───────┘
             │ NO
             ▼
      ┌──────────────┐
      │ Rule 4:      │  YES → Non-Productive (bot_like_input_pattern)
      │ Bot Pattern? │        confidence = 0.20
      └──────┬───────┘
             │ NO
             ▼
      ┌──────────────┐
      │ Rule 5:      │  YES → Productive (confidence_above_threshold)
      │ Confidence   │
      │ ≥0.60?       │
      └──────┬───────┘
             │ NO
             ▼
      ┌──────────────┐
      │ Rule 6:      │  → Non-Productive (insufficient_activity_signals)
      │ Fallthrough  │
      └──────────────┘
```

---

## Configuration Examples

### Example 1: Software Development Company

```bash
# Productive apps - coding, design, project management
PRODUCTIVE_APPS=visual studio code,vscode,pycharm,intellij,xcode,cursor,figma,docker,postman,github desktop,jira,confluence,notion

# Non-productive - social media, streaming, gaming
NON_PRODUCTIVE_APPS=youtube,netflix,reddit,twitter,instagram,facebook,tiktok,spotify,steam,league of legends,fortnite

# Meetings - video conferencing
MEETING_APPS=zoom,microsoft teams,google meet,slack huddle

# Thresholds
PRODUCTIVE_DOMINANT_RATIO=0.50  # 50% productive apps = productive
NON_PROD_DOMINANT_RATIO=0.6667  # 66.67% non-productive = non-productive
MEETING_DOMINANT_RATIO=0.50     # 50% meeting = productive
```

### Example 2: Creative Agency

```bash
# Productive apps - design, video editing, client tools
PRODUCTIVE_APPS=figma,sketch,adobe photoshop,adobe illustrator,adobe premiere,final cut pro,blender,cinema 4d,notion,asana,trello

# Non-productive
NON_PRODUCTIVE_APPS=youtube,netflix,reddit,instagram,facebook,tiktok

# Meetings
MEETING_APPS=zoom,google meet,facetime

# Thresholds (more lenient for creative work)
PRODUCTIVE_DOMINANT_RATIO=0.40  # 40% productive apps = productive (watching tutorials/research is common)
NON_PROD_DOMINANT_RATIO=0.70    # 70% non-productive = non-productive (stricter)
```

### Example 3: Customer Support Team

```bash
# Productive apps - CRM, ticketing, communication
PRODUCTIVE_APPS=zendesk,salesforce,intercom,helpscout,slack,microsoft outlook,notion,excel

# Non-productive (be careful not to mark legitimate tools as non-productive)
NON_PRODUCTIVE_APPS=youtube,netflix,reddit,instagram,facebook,spotify,steam

# Meetings
MEETING_APPS=zoom,microsoft teams,google meet

# Thresholds
PRODUCTIVE_DOMINANT_RATIO=0.50
NON_PROD_DOMINANT_RATIO=0.6667
```

---

## How to Customize

### Adding New Productive Apps

1. Edit `.env`:
   ```bash
   PRODUCTIVE_APPS=vscode,pycharm,...,your-new-app
   ```

2. Matching is case-insensitive and substring-based:
   - `"visual studio code"` matches "Visual Studio Code", "vscode", "code.exe"
   - `"figma"` matches "Figma", "FIGMA", "Figma Desktop"

3. Restart backend service:
   ```bash
   pkill -f "python.*flask"
   python3 -m flask run
   ```

### Adjusting Thresholds

**More Strict (harder to be productive):**
```bash
PRODUCTIVE_DOMINANT_RATIO=0.60     # Need 60% productive apps
NON_PROD_DOMINANT_RATIO=0.50       # Only 50% non-productive = non-productive
CONFIDENCE_THRESHOLD=0.70          # Need higher activity for confidence-based
```

**More Lenient (easier to be productive):**
```bash
PRODUCTIVE_DOMINANT_RATIO=0.40     # Only 40% productive apps needed
NON_PROD_DOMINANT_RATIO=0.75       # Need 75% non-productive to mark as such
CONFIDENCE_THRESHOLD=0.50          # Lower activity threshold
```

### Industry-Specific Tuning

**Data Science / Research:**
- Add Jupyter, RStudio, MATLAB to productive apps
- Consider adding "arxiv", "papers" to productive patterns
- Lower activity thresholds (reading papers = productive but low interaction)

**Sales / Marketing:**
- Add Salesforce, HubSpot, Mailchimp to productive apps
- LinkedIn might be productive (prospecting) - consider context
- CRM tools should be in productive apps

**Video Production:**
- Add Premiere Pro, DaVinci Resolve, After Effects to productive apps
- YouTube might be legitimate (research/reference) - be careful with non-productive classification

---

## Testing the Configuration

### Scenario 1: Verify Productive App Detection

1. Open VS Code and work for 60 seconds
2. Check dashboard - should show as productive with reason: `"productive_app_dominant"`
3. Expected: 100% productive time

### Scenario 2: Verify Non-Productive Detection

1. Watch YouTube for 60 seconds (4+ out of 6 samples)
2. Check dashboard - should show as non-productive with reason: `"non_productive_app_dominant"`
3. Expected: 100% non-productive time

### Scenario 3: Mixed Usage

```
Scenario: 60 seconds
  - VS Code: 30 seconds (3 samples)
  - YouTube: 20 seconds (2 samples)
  - Slack: 10 seconds (1 sample)

Analysis:
  - productive_ratio = 3/6 = 0.50
  - non_prod_ratio = 2/6 = 0.3333
  - meeting_ratio = 0

Classification:
  - Rule 2 triggers (productive_ratio == 0.50) ✅
  - Result: Productive (productive_app_dominant)
```

---

## Backward Compatibility

**Existing behavior preserved:**
- If you don't set `PRODUCTIVE_APPS`, it defaults to a comprehensive list
- Existing classifications (meeting, non-productive, confidence) still work
- Old dashboards display new `productive_app_dominant` reason correctly

**Migration:**
- No database changes required
- No code deployment needed (just restart backend)
- Configuration-only update

---

## Summary

**New Capability:**
- ✅ Explicitly mark apps as productive (IDEs, design tools, productivity software)
- ✅ Fine-grained control via `PRODUCTIVE_DOMINANT_RATIO` threshold
- ✅ Boosted confidence (0.75) for known productive apps
- ✅ Rule 2 in decision tree (evaluated before non-productive rule)

**Benefits:**
- More accurate classification for knowledge workers
- Reduced false negatives (coding with low interaction now correctly marked productive)
- Industry-specific customization
- Transparent reasoning (`productive_app_dominant` shows in dashboards)

**No Drawbacks:**
- Backward compatible
- No performance impact
- Easy to customize
- Can disable by setting `PRODUCTIVE_DOMINANT_RATIO=1.0` (never triggers)
