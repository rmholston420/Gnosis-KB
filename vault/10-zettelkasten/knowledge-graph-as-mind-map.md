---
title: The Knowledge Graph as a Mind Map
tags: [knowledge-graph, zettelkasten, graph-theory, LightRAG, retrieval]
note_type: permanent
created: 2024-03-20
---

# The Knowledge Graph as a Mind Map

A knowledge graph represents information as a network of **entities (nodes) and relations (edges)**. Unlike a flat index or a folder hierarchy, it preserves the relational structure of thought: this concept entails that one, which contradicts this other, which is an example of that broader category.

## From Notes to Graph

In Gnosis, two graph layers are maintained simultaneously:

1. **Wikilink graph** — explicit `[[note-title]]` references between notes, extracted at sync time. This mirrors the author's *intentional* associations.
2. **LightRAG graph** — entities and relations extracted from note content by an LLM, stored in a graph database. This surfaces *implicit* associations the author may not have noticed.

The combination gives both explicit navigation ("I know I want to follow this link") and serendipitous discovery ("I didn't know these two concepts were connected").

## Graph-RAG vs. Vector-RAG

Traditional retrieval-augmented generation (RAG) uses vector similarity to find relevant passages. **Graph-RAG** (as in LightRAG and Microsoft's GraphRAG) retrieves by traversing the knowledge graph:

| | Vector RAG | Graph RAG |
|---|---|---|
| Unit retrieved | Passage chunks | Entities + relations |
| Query strength | Semantic similarity | Multi-hop reasoning |
| Blind spot | Relational structure | Dense factual corpora |

For a personal knowledge base built around thematic inquiry — as opposed to a document corpus — graph-RAG tends to give more coherent answers because the graph preserves the *structure of reasoning*, not just surface lexical similarity.

## Related

- [[zettelkasten-method]]
- [[emergence-and-complexity]]
- [[epistemology-and-justified-belief]]
