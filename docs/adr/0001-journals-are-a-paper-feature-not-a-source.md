# The four major journals are a Paper feature, not a source of Papers

The project was conceived as collecting open problems from arXiv *and* from the four major mathematics journals. Crossref exposes metadata and abstracts for all four (Annals `0003-486X`, JAMS `0894-0347`, Inventiones `0020-9910`, Acta `0001-5962`) but no full text and no open licence, and open problems live in a paper's body rather than its abstract — so the journals cannot be an ingestion path at all. We ingest arXiv LaTeX only, and attach Venue of Record to a Paper by matching its DOI.

## Consequences

There is one fetch path, not two. Venue of Record becomes an Axis input rather than a scope boundary — and we expect to weight it *negatively*: a Conjecture stated in Annals or Inventiones has already been attacked by the strongest people in the field, which is evidence against tractability, not for it. The venues that suit our criteria are the unfashionable ones nobody has bothered with.
