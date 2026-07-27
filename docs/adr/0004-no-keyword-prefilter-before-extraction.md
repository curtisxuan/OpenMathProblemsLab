# No keyword prefilter ahead of extraction

Extraction reads the full LaTeX of every Paper in the Corpus. A reader will reasonably expect a cheap regex gate in front of the model, so: we measured one, and it does not pay. On a sample of 20 recent `math.CO` sources, only 25% contained a formal `conjecture` or `problem` environment, while several of the rest stated open problems purely in prose ("we conjecture", "remains open") — gating on environments would silently discard exactly the unfashionable prose-stated problems we are hunting for.

## Consequences

Cost is not the binding constraint here and should not be treated as one. Papers are small (measured median ~14.5k tokens), so full-text extraction with Haiku over a month of four categories runs roughly $12 batched, and over three years roughly $430. Regex hits are still recorded, as metadata features feeding the Axes — never as an admission test.
