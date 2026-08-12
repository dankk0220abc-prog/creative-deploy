# Arcana local Tarot knowledge foundation

## Scope

`apps/api/src/creativedeploy_api/arcana/catalog.py` is the checked-in 78-card
reference deck. `knowledge.py` adds local semantic facets at interpretation
time: orientation, suit/element, number or court role, Past/Present/Future
position, three-card composition rules, and a safety boundary. No knowledge is
fetched at runtime.

## Provenance model

Every dispatched card context carries a minimal, serialisable provenance record:
source identifier, bibliography, source type, card locator, knowledge version,
and `repository_local_only` retrieval mode. The bibliographic reference is A. E.
Waite's *The Pictorial Key to the Tarot* (1910). Product text is a concise
CreativeDeploy-authored synthesis: it does not reproduce long passages or any
deck artwork. Existing core card records remain explicitly marked as original
synthesis.

## Retrieval and execution boundary

The first adapter is `TarotFixtureInterpreter`. It receives only the question,
the saved three-card facts, and the local context. It has no HTTP client,
provider credential, API key, or remote model path. A later authorised provider
can consume the same context contract, but the current implementation's live
gate is absent by design.

## Reading boundary

The v2 document treats Past, Present, and Future as a conditional narrative.
It names relationships, trends, tensions, and turning points, then offers small
reflective actions and Journal prompts. It must never present a fixed outcome or
medical, legal, or financial direction.
