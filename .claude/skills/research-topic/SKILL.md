---
name: research-topic
description: Run the research-and-summarize pipeline on a topic, save the report under reports/, and get a critique of it.
argument-hint: "<topic>"
disable-model-invocation: true
---

# Research a topic

Topic: $ARGUMENTS

If no topic was given, ask the user for one before doing anything else.

1. Delegate the run to the **pipeline-runner** subagent, passing the topic. Do not run `main.py` yourself; the run log is long and should stay out of this conversation.
2. If the runner reports a failure, show the user its error summary and stop.
3. Otherwise, delegate to the **report-critic** subagent, passing the report path and log path the runner returned.
4. Reply to the user with:
   - the report path
   - the runner's short summary (subtopics, documents kept, revisions)
   - the critic's top findings
