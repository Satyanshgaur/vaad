# Test split (private)

The test tasks are **not published** until the paper is out, so models cannot train on them.
Their SHA256 hashes are in `../SPLITS.lock` and their word 6-gram hashes are in
`../test_ngrams.txt` (used by the gate 10 leakage guard in CI).

Maintainers: `scripts/private_sync.sh pull` fetches the files from the private repo.
