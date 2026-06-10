"""Knowledge Graph integration package.

Externalized construction-domain knowledge (lumber specs, framing roles, IRC
code rules) lives in Neo4j (AuraDB Free for prod, ephemeral testcontainer for
CI). All entities follow a universal versioning convention defined in
``provenance.py``.

Submodules are imported lazily (no eager imports here) so unit tests for
individual modules don't transitively require the full backend dependency
graph.

Submodule map:

* ``client``     — :class:`Neo4jClient`, connection management
* ``provenance`` — versioning convention + ``create_versioned_node`` /
  ``rollback_version``
* ``seed``       — idempotent seed data (lumber, framing roles, IRC rules)
* ``loader``     — ``load_lumber_specs`` for startup-time in-memory cache
"""
