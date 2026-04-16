# Algorithm Spec (Reverse-Engineered)

> Source basis: publicly accessible page script content at `https://sbti.unun.dev/`.

## 1) Inputs

- `questions`: 30 normal questions with dimension id (`dim`) and option values (typically 1/2/3)
- `specialQuestions`:
  - `drink_gate_q1` (4 options)
  - `drink_gate_q2` (2 options, conditionally visible)
- `NORMAL_TYPES`: 25 normal personality templates, each with a 15-dim `pattern` over `{L,M,H}`

Dimension order used by page logic:

`['S1','S2','S3','E1','E2','E3','A1','A2','A3','Ac1','Ac2','Ac3','So1','So2','So3']`

## 2) Visibility rule

- Base test shows shuffled normal questions + `drink_gate_q1`
- If `app.answers['drink_gate_q1'] === 3`, then inject `drink_gate_q2`

## 3) Raw score aggregation

For each normal dimension `d`:

\[
score_d = \sum_{q \in questions, q.dim=d} answer(q)
\]

Each dimension has 2 normal questions, so score range is 2..6.

## 4) Level mapping

Function equivalent:

```js
if (score <= 3) return 'L';
if (score === 4) return 'M';
return 'H';
```

Then convert levels to numeric vector with:

- `L -> 1`
- `M -> 2`
- `H -> 3`

## 5) Template matching

For each normal type template vector `t` and user vector `u`:

\[
distance(t,u)=\sum_{i=1}^{15}|t_i-u_i|
\]

Tie-breaking order:
1. smaller `distance`
2. larger `exact` (number of exactly matched dimensions)
3. larger `similarity`

with

\[
similarity = \max(0, round((1-distance/30)\times100))
\]

## 6) Special overrides

Let `bestNormal` be top-ranked normal type.

1. If `drink_gate_q2 == 2` (drunk trigger):
   - final type = `DRUNK`
2. Else if `bestNormal.similarity < 60`:
   - final type = `HHHH`
3. Else:
   - final type = `bestNormal`

## 7) Theoretical total answer combinations

From current page structure:

- 30 normal questions: each 3 options => \(3^{30}\)
- `drink_gate_q1`: 4 options
- `drink_gate_q2` appears only when `drink_gate_q1=3`, then has 2 options

Total combinations:

\[
3^{30}\times(3+2)=5\times3^{30}
\]

## 8) Exact distribution calculation method

To compute exact probability under uniform answer combinations:

1. Enumerate all 15-dim level states in \(3^{15}\)
2. For each state, run matching rule above (normal + HHHH threshold)
3. Lift counts back to answer-space:
   - each level state has \(3^{15}\) normal-answer preimages
   - gate contributes multiplier 4 for non-DRUNK paths
4. Add DRUNK mass = \(3^{30}\)
5. Divide by total \(5\times3^{30}\)
