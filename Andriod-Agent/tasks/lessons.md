# Lessons

- No project-specific corrections captured yet.
- For deterministic Android Intent execution tests, do not introduce fallback URLs or alternate success paths unless explicitly requested. The intended intent should either work or produce a clear error that we then fix.
- Start verification with simple Android-native intents before app/package-specific tests like Google Maps, because package availability can distract from validating the generic execution layer.
