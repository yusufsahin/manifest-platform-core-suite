# Notes

ACL rule grants 'viewer' role 'read' action but requires field masking on
content.ssn and content.salary. The engine MUST produce allow=true AND emit
a maskField Intent for each masked field. Intents are sorted by target ascending
(content.salary < content.ssn lexicographically) for deterministic output.
The consuming app's adapter is responsible for applying the masks.
