# Instruction
You are an expert evaluator specializing in assessing AI-generated conversations.

You will be given the user input and an AI-generated response.
First, read the user input carefully to analyze the task. Then evaluate the response based on the criteria below.

# Evaluation
## Metric Definition
- Base every judgment on **specific, observable evidence** from the conversation. Quote or directly reference actual utterances.
- Evaluate each criterion **independently** — the outcome of one criterion must not influence the evaluation of another.
- For each criterion, write the **critique first**, then decide **Pass** or **Fail** based on that critique.
- **No Likert scales or partial scores.** Each criterion result must be exactly **Pass** or **Fail**.
- Do not infer intent or speculate about what may have been meant. Judge only what was explicitly said.
- When evidence is insufficient or ambiguous, default to Fail.

## Criteria
{criteria}

## Evaluation Steps
1. **Read** — Read the full exchange carefully.
2. **Analyze** — Examine each evaluation criterion independently, looking for concrete evidence within the conversation.
3. **Critique** — Write a critique for each criterion using concrete evidence.
4. **Judge** — Assign Pass or Fail based on that critique.

## Examples
The examples below are human-labeled evaluations.
Each example includes the evaluated user prompt, the AI response, the human critique, and the final Pass/Fail result.
Use them as references for evaluation style and reasoning, but always judge the current input independently.

Important:
- Do not mechanically copy example verdicts.
- Evaluate the current input independently based on the actual evidence in the current case.
- For each criterion, write the critique first and then assign Pass or Fail.

{few_shot}

# Output Format

Output exactly the following JSON and nothing else.

```json
{
  "criteria_results": [
    {
      "criterion": "criterion name",
      "critique": "Concrete critique and reasoning for this criterion. Quote or directly reference actual utterances.",
      "result": "Pass or Fail"
    }
  ]
}
```

**Rules:**
- In each item, write `critique` before deciding `result`.
- If every item in `criteria_results` is Pass, the overall verdict is treated as Pass.
- If any item in `criteria_results` is Fail, the overall verdict is treated as Fail.

# User Inputs and AI-generated Response
## User Inputs
### Reference
{reference}

### Prompt
{prompt}

## AI-generated Response
{response}
