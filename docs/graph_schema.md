# Graph Schema

The MVP graph model uses domain-neutral `Video`, `Scene`, `Entity`, `Event`, and `Tag` nodes with a small fixed relationship vocabulary.

The Strands Extraction Agent hands a validated `GraphExtraction` to the `index_graph`
tool. That tool maps the contract to deterministic, parameterized Neo4j writes; the model
does not generate write Cypher or receive database credentials.
