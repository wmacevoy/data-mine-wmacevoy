Hybrid retrieval = combining dense (vector) semantic search with sparse (keyword / symbolic) search.
It gives the best of both worlds:
	•	Dense retrieval finds conceptual matches (“Scottish play festivals” ≈ Macbeth events).
	•	Sparse retrieval finds exact term matches (“Denver”, “June 2025”, “Colorado”).

You curate the dataset by preparing both:
	1.	Clean, structured metadata for fast keyword filtering.
	2.	Rich, unstructured text for embedding and semantic retrieval.

Then you index both representations in a vector store (dense) and a text/search index (sparse).