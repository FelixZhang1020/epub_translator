Source:
{{content.source}}

Current translation:
{{content.target}}

{{#if feedback}}
Improve based on this feedback. Output ONLY the improved translation.
Feedback: {{feedback}}
{{else if pipeline.suggested_changes}}
Improve based on these suggestions. Output ONLY the improved translation.
Suggestions: {{pipeline.suggested_changes}}
{{/if}}
