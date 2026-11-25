# Contributing to OpenDither

Thanks for helping! Bug reports, new palettes, UI polish and new language ports are all welcome.

## Running the tests

```bash
# JavaScript (Node 16+)
cd js && npm test

# Python
cd python
pip install -e ".[dev]"
pytest
OPENDITHER_NO_NUMBA=1 pytest     # also test the pure-Python engine
```

## Changing the algorithms

The spec in [`spec/ALGORITHMS.md`](spec/ALGORITHMS.md) is the source of truth. If you change how
pixels come out (a new algorithm, a different formula):

1. Update the spec.
2. Update the JavaScript reference in `js/src/opendither.js`.
3. Regenerate the vectors: `cd js && npm run vectors`.
4. Update every other implementation until its tests pass again.

Pure refactors and UI changes must not change `spec/test-vectors.json`.

## Adding a palette

Add it to `spec/palettes.json`, `js/src/opendither.js` (`PALETTES`) and
`python/opendither/palettes.py`. The tests check that all three match.

## Porting to a new language

1. Create a folder named after the language (`rust/`, `go/`, `csharp/`…).
2. Implement the pipeline in `spec/ALGORITHMS.md`. Follow the evaluation order written there; it
   matters for bit-exact results.
3. Build the 64×48 test image described in `spec/test-vectors.json`, run every case, and compare the
   SHA-256 of your RGBA output with the stored hash.
4. Add your test command to `.github/workflows/test.yml`.

Tips: use 64-bit floats everywhere, do 32-bit unsigned wrap-around for the `random` hash, break
nearest-color ties toward the lowest palette index, and use a *stable* sort in median cut.
