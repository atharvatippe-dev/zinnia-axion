# Final Decision Tree with Productive Apps (v2.1)

## Rule Priority (Optimized for Enterprise Monitoring)

**Evaluated top-to-bottom, first match wins:**

```
Rule 1: Meeting Apps (≥50%)           → Productive (conf = 0.85)
Rule 2: Non-Productive Apps (≥66.67%) → Non-Productive (conf = 0.40) [PRIORITY]
Rule 3: Productive Apps (≥70%)        → Productive (conf = 0.75)
Rule 4: Bot Pattern Detected          → Non-Productive (conf = 0.20)
Rule 5: Confidence ≥ 0.60             → Productive
Rule 6: Fallthrough                   → Non-Productive
```

## Why This Ordering is Optimal

### Rule 2 Before Rule 3 (Non-Productive BEFORE Productive)

**Rationale:**
1. **Catch slacking first** - Enterprise monitoring prioritizes detecting non-productive behavior
2. **Higher confidence** - 66.67% threshold means we're sure user is wasting time
3. **Prevents gaming** - User can't claim VS Code usage if YouTube is dominant
4. **Asymmetric thresholds** - Harder to be marked productive (70%) than non-productive (66.67%)

### Threshold Comparison

| Rule | Threshold | Samples Needed (out of 6) | Logic |
|------|-----------|---------------------------|-------|
| Meeting | 50% | 3/6 | Lower bar (meetings are always work) |
| Non-Productive | 66.67% | 4/6 | Higher bar (must be clearly slacking) |
| Productive | **70%** | 5/6 | **Highest bar** (must be clearly working) |

**Key Design:**
- **Meetings:** 50% threshold (easiest to trigger) - meetings are definite work
- **Non-Productive:** 66.67% threshold (2/3 majority) - catch clear time-wasting
- **Productive Apps:** 70% threshold (strict) - ensure genuine productive work, not just app switching

---

## Example Scenarios (10s Polling, 6 Samples per 60s Bucket)

### Scenario 1: Pure Coding (Rule 3 Triggers)

```
T=0s:  VS Code
T=10s: VS Code
T=20s: VS Code
T=30s: VS Code
T=40s: VS Code
T=50s: Terminal
```

**Analysis:**
- productive_ratio = 6/6 = 1.00 (100%)
- non_prod_ratio = 0/6 = 0
- meeting_ratio = 0/6 = 0

**Rule Evaluation:**
```
Rule 1 (Meeting ≥50%)?      NO  (0% < 50%)
Rule 2 (Non-Prod ≥66.67%)?  NO  (0% < 66.67%)
Rule 3 (Productive ≥70%)?   YES (100% >= 70%) ✅
```

**Classification:** **Productive** (productive_app_dominant)  
**Confidence:** 0.75

---

### Scenario 2: Mostly Coding with Brief YouTube (Rule 3 Triggers)

```
T=0s:  VS Code
T=10s: VS Code
T=20s: VS Code
T=30s: VS Code
T=40s: YouTube (1 sample)
T=50s: VS Code
```

**Analysis:**
- productive_ratio = 5/6 = 0.8333 (83.33%)
- non_prod_ratio = 1/6 = 0.1667 (16.67%)
- meeting_ratio = 0/6 = 0

**Rule Evaluation:**
```
Rule 1 (Meeting ≥50%)?      NO  (0% < 50%)
Rule 2 (Non-Prod ≥66.67%)?  NO  (16.67% < 66.67%)
Rule 3 (Productive ≥70%)?   YES (83.33% >= 70%) ✅
```

**Classification:** **Productive** (productive_app_dominant)  
**Confidence:** 0.75

**Note:** YouTube appears but doesn't dominate (only 16.67%), so productive apps win!

---

### Scenario 3: Balanced Mix (Rule 5 Triggers via Confidence)

```
T=0s:  VS Code
T=10s: VS Code
T=20s: VS Code
T=30s: YouTube
T=40s: YouTube
T=50s: Chrome (Gmail)
```

**Analysis:**
- productive_ratio = 3/6 = 0.50 (50%)
- non_prod_ratio = 2/6 = 0.3333 (33.33%)
- meeting_ratio = 0/6 = 0
- Confidence = 0.68 (high due to coding activity in first 30s)

**Rule Evaluation:**
```
Rule 1 (Meeting ≥50%)?      NO  (0% < 50%)
Rule 2 (Non-Prod ≥66.67%)?  NO  (33.33% < 66.67%)
Rule 3 (Productive ≥70%)?   NO  (50% < 70%)  ← Falls short of 70%!
Rule 4 (Bot Pattern)?       NO  (natural input)
Rule 5 (Confidence ≥0.60)?  YES (0.68 >= 0.60) ✅
```

**Classification:** **Productive** (confidence_above_threshold)  
**Confidence:** 0.68

**Note:** Neither productive nor non-productive apps dominate, so confidence score decides.

---

### Scenario 4: Heavy YouTube Usage (Rule 2 Triggers - CATCHES SLACKING!)

```
T=0s:  YouTube
T=10s: YouTube
T=20s: YouTube
T=30s: YouTube
T=40s: VS Code (1 sample)
T=50s: Chrome (Gmail)
```

**Analysis:**
- productive_ratio = 1/6 = 0.1667 (16.67%)
- non_prod_ratio = 4/6 = 0.6667 (66.67%)
- meeting_ratio = 0/6 = 0

**Rule Evaluation:**
```
Rule 1 (Meeting ≥50%)?      NO  (0% < 50%)
Rule 2 (Non-Prod ≥66.67%)?  YES (66.67% >= 66.67%) ✅  ← STOPS HERE!
```

**Classification:** **Non-Productive** (non_productive_app_dominant)  
**Confidence:** 0.40

**Critical:** Rule 2 catches this BEFORE Rule 3 can check productive apps! This prevents users from claiming "I had VS Code open" when they were mostly on YouTube.

---

### Scenario 5: Edge Case - Exactly at Non-Prod Threshold (Rule 2 Triggers)

```
T=0s:  YouTube
T=10s: YouTube
T=20s: YouTube
T=30s: YouTube
T=40s: VS Code
T=50s: VS Code
```

**Analysis:**
- productive_ratio = 2/6 = 0.3333 (33.33%)
- non_prod_ratio = 4/6 = 0.6667 (66.67%)  ← Exactly at threshold!
- meeting_ratio = 0/6 = 0

**Rule Evaluation:**
```
Rule 1 (Meeting ≥50%)?      NO  (0% < 50%)
Rule 2 (Non-Prod ≥66.67%)?  YES (66.67% >= 66.67%) ✅
```

**Classification:** **Non-Productive** (non_productive_app_dominant)  
**Confidence:** 0.40

**Why this matters:** Tie goes to non-productive (66.67% = threshold), preventing edge-case abuse.

---

### Scenario 6: Just Below Productive Threshold (Rule 5 Decides)

```
T=0s:  VS Code
T=10s: VS Code
T=20s: VS Code
T=30s: VS Code
T=40s: Chrome (Stack Overflow)
T=50s: Slack
```

**Analysis:**
- productive_ratio = 4/6 = 0.6667 (66.67%)
- non_prod_ratio = 0/6 = 0
- meeting_ratio = 0/6 = 0
- Confidence = 0.72 (high coding activity)

**Rule Evaluation:**
```
Rule 1 (Meeting ≥50%)?      NO  (0% < 50%)
Rule 2 (Non-Prod ≥66.67%)?  NO  (0% < 66.67%)
Rule 3 (Productive ≥70%)?   NO  (66.67% < 70%)  ← Just below!
Rule 4 (Bot Pattern)?       NO  (natural input)
Rule 5 (Confidence ≥0.60)?  YES (0.72 >= 0.60) ✅
```

**Classification:** **Productive** (confidence_above_threshold)  
**Confidence:** 0.72

**Note:** Falls 3.33% short of productive app threshold, but confidence score catches it!

---

## Why This Configuration is Better

### Comparison: Old vs New Rule Ordering

#### OLD (Rule 2 = Productive BEFORE Rule 3 = Non-Productive):

**Problem Scenario:**
```
Samples: VS Code (3), YouTube (3)
  
Rule 2 (Productive ≥50%): 50% >= 50% → Productive ✅ WINS
Rule 3 (Non-Prod ≥66.67%): Skipped (Rule 2 already matched)

Result: Productive (even though 50% YouTube!)
```

**Issue:** User can game the system by keeping VS Code open while watching YouTube.

#### NEW (Rule 2 = Non-Productive BEFORE Rule 3 = Productive):

**Same Scenario:**
```
Samples: VS Code (3), YouTube (3)
  
Rule 2 (Non-Prod ≥66.67%): 50% < 66.67% → Doesn't trigger
Rule 3 (Productive ≥70%): 50% < 70% → Doesn't trigger
Rule 5 (Confidence ≥0.60): Depends on activity → Decides

Result: Classified based on actual activity (confidence score)
```

**Better:** Neither rule triggers - confidence score evaluates actual work being done.

### Threshold Strategy

**Asymmetric by design:**

| Category | Threshold | Philosophy |
|----------|-----------|------------|
| **Meeting** | 50% | Easy to classify (meetings are definite work) |
| **Non-Productive** | 66.67% | Moderate (2/3 majority = clear time-wasting) |
| **Productive** | **70%** | **Strict** (must be clearly focused on productive tools) |

**Result:**
- Harder to game the system
- Middle ground (50-70% productive apps) falls to confidence score
- Encourages genuine focused work on productive tools

---

## Configuration Settings

```bash
# .env

# Rule ordering: Non-productive checked BEFORE productive
PRODUCTIVE_DOMINANT_RATIO=0.70     # 70% productive apps = productive (strict)
NON_PROD_DOMINANT_RATIO=0.6667     # 66.67% non-productive = non-productive
MEETING_DOMINANT_RATIO=0.50        # 50% meeting = productive (lenient)
```

### Rationale for 70% Productive Threshold:

**With 6 samples per bucket:**
- 70% = 4.2 samples ≈ **5 out of 6 samples must be productive apps**
- Only 1 sample can be non-productive/neutral
- Ensures user is genuinely focused on work

**With 66.67% (old proposal):**
- 66.67% = 4 samples exactly
- 2 samples can be non-productive/neutral
- Too lenient - user could split time 50/50 and still hit productive threshold

---

## Rule Priority Diagram (Updated)

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
      │ Meeting ≥50%?│       conf = 0.85
      └──────┬───────┘
             │ NO
             ▼
      ┌──────────────┐
      │ Rule 2:      │  YES → Non-Productive (non_productive_app_dominant)
      │ Non-Prod     │       conf = 0.40
      │ ≥66.67%?     │       [CATCHES SLACKING FIRST!]
      └──────┬───────┘
             │ NO
             ▼
      ┌──────────────┐
      │ Rule 3:      │  YES → Productive (productive_app_dominant)
      │ Productive   │       conf = 0.75
      │ ≥70%?        │       [STRICT - need 5/6 samples]
      └──────┬───────┘
             │ NO
             ▼
      ┌──────────────┐
      │ Rule 4:      │  YES → Non-Productive (bot_like_input_pattern)
      │ Bot Pattern? │       conf = 0.20
      └──────┬───────┘
             │ NO
             ▼
      ┌──────────────┐
      │ Rule 5:      │  YES → Productive (confidence_above_threshold)
      │ Confidence   │       [Activity-based]
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

## Coverage Matrix: What Gets Classified Where

| Scenario | Productive Ratio | Non-Prod Ratio | Classification | Triggered By |
|----------|------------------|----------------|----------------|--------------|
| Pure coding (VS Code 100%) | 100% | 0% | Productive | Rule 3 |
| Pure YouTube (100%) | 0% | 100% | Non-Productive | Rule 2 |
| Zoom call (100%) | 0% | 0% | Productive | Rule 1 |
| VS Code (83%), YouTube (17%) | 83% | 17% | Productive | Rule 3 |
| VS Code (67%), YouTube (33%) | 67% | 33% | **Confidence** | Rule 5 (< 70%) |
| VS Code (50%), YouTube (50%) | 50% | 50% | **Confidence** | Rule 5 (neither dominates) |
| VS Code (33%), YouTube (67%) | 33% | 67% | **Non-Productive** | Rule 2 ✅ |
| VS Code (17%), YouTube (83%) | 17% | 83% | Non-Productive | Rule 2 |

**Sweet spot for confidence-based:** 50-70% productive apps OR 0-66% non-productive apps

---

## Configuration Tuning Guide

### Strict Enterprise (Current Default)

```bash
PRODUCTIVE_DOMINANT_RATIO=0.70     # Need 70% productive apps
NON_PROD_DOMINANT_RATIO=0.6667     # 66.67% non-productive = slacking
CONFIDENCE_THRESHOLD=0.60          # Moderate activity requirement
```

**Effect:** Fewer false positives for "productive". Users must genuinely focus on productive tools.

### Lenient (Creative/Research Roles)

```bash
PRODUCTIVE_DOMINANT_RATIO=0.50     # Only 50% productive apps needed
NON_PROD_DOMINANT_RATIO=0.75       # 75% non-productive to mark as such (stricter)
CONFIDENCE_THRESHOLD=0.50          # Lower activity bar (reading is productive)
```

**Effect:** More generous for roles where research/reading is common.

### Very Strict (Call Center/Manual Work)

```bash
PRODUCTIVE_DOMINANT_RATIO=0.80     # Need 80% productive apps
NON_PROD_DOMINANT_RATIO=0.50       # Only 50% non-productive = slacking
CONFIDENCE_THRESHOLD=0.70          # High activity required
```

**Effect:** Very hard to be marked productive. Suitable for roles with constant interaction.

---

## Edge Case Analysis

### Edge Case 1: Exactly at Productive Threshold (70%)

```
Samples: VS Code (4), YouTube (1), Chrome (1)

productive_ratio = 4/6 = 0.6667 (66.67%)
Rule 3 check: 0.6667 >= 0.70? NO (falls 3.33% short)
```

**Result:** Falls to Rule 5 (confidence-based)

**Why this is good:** Borderline cases (66-70%) are evaluated on actual activity, not just app presence.

### Edge Case 2: Exactly at Non-Productive Threshold (66.67%)

```
Samples: YouTube (4), VS Code (2)

non_prod_ratio = 4/6 = 0.6667 (66.67%)
Rule 2 check: 0.6667 >= 0.6667? YES ✅
```

**Result:** Non-Productive (non_productive_app_dominant)

**Why this is good:** Tie goes to non-productive (conservative for enterprise monitoring).

### Edge Case 3: Neither Dominates (50/50 Split)

```
Samples: VS Code (3), YouTube (3)

productive_ratio = 3/6 = 0.50 (50%)
non_prod_ratio = 3/6 = 0.50 (50%)

Rule 2 check: 0.50 >= 0.6667? NO
Rule 3 check: 0.50 >= 0.70? NO
```

**Result:** Falls to Rule 5 (confidence-based)

**Why this is perfect:** When apps are evenly split, activity level (keystrokes, clicks, mouse) determines productivity - not just which apps are open!

---

## Why 70% is the Right Threshold for Productive Apps

### With 6 Samples per Bucket:

| Threshold | Samples Needed | Interpretation |
|-----------|----------------|----------------|
| 50% | 3/6 | Half the bucket = too lenient |
| 60% | 3.6 → 4/6 | Better, but still allows 33% distractions |
| 66.67% | 4/6 | Matches non-productive (creates conflicts) |
| **70%** | **4.2 → 5/6** | **Only 1 distraction allowed** ✅ |
| 83.33% | 5/6 | Too strict (same as 70% in practice) |

**70% = 5 out of 6 samples must be productive apps**

This is optimal because:
- Allows 1 brief distraction or context switch (10 seconds)
- Stricter than non-productive threshold (prevents both rules triggering)
- Falls back to confidence for borderline cases (good design)

---

## Testing Scenarios

### Test 1: Verify Non-Prod Priority

**Setup:** Open VS Code (3 samples), YouTube (3 samples)

**Expected:**
- productive_ratio = 50%
- non_prod_ratio = 50%
- Rule 2: NO (50% < 66.67%)
- Rule 3: NO (50% < 70%)
- Rule 5: Confidence decides (likely productive if actively coding)

**Why:** Neither rule triggers - confidence score evaluates actual work.

### Test 2: Verify 70% Productive Threshold

**Setup:** Open VS Code (5 samples), Chrome (1 sample)

**Expected:**
- productive_ratio = 83.33%
- Rule 3: YES (83.33% >= 70%)
- Classification: Productive (productive_app_dominant)

### Test 3: Verify Non-Prod Catches Slacking

**Setup:** Watch YouTube (4 samples), VS Code (2 samples)

**Expected:**
- non_prod_ratio = 66.67%
- Rule 2: YES (66.67% >= 66.67%)
- Classification: Non-Productive (non_productive_app_dominant)
- **Even though VS Code is present!**

---

## Summary

**Final Configuration (Optimized for Enterprise):**

```
Rule Order:
1. Meetings (≥50%) → Productive
2. Non-Productive (≥66.67%) → Non-Productive [PRIORITY - CATCH SLACKING FIRST]
3. Productive (≥70%) → Productive [STRICT - NEED 5/6 SAMPLES]
4-6. Confidence-based or fallthrough

Thresholds:
  PRODUCTIVE_DOMINANT_RATIO = 0.70   (strict - need genuine focus)
  NON_PROD_DOMINANT_RATIO = 0.6667   (moderate - 2/3 majority)
  MEETING_DOMINANT_RATIO = 0.50      (lenient - meetings are work)
```

**Benefits:**
- ✅ Catches time-wasting before giving credit for productive apps
- ✅ Asymmetric thresholds prevent gaming (harder to be productive than non-productive)
- ✅ Borderline cases (50-70%) evaluated on activity, not just app presence
- ✅ Enterprise-appropriate (conservative classification)

**The rule ordering is now optimal for monitoring employee productivity!**
