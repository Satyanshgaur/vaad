from vaad.canon.gaps import mine


def test_unknown_word_before_an_anchor_is_reported_only_when_frequent() -> None:
    texts = ["meeting zorbo baje hai"] * 3 + ["call quux baje"] + ["saade aath baje"] * 5
    report = mine(texts, min_count=3)
    words = {(r["kind"], r["word"]) for r in report["candidates"]}  # type: ignore[attr-defined]
    assert words == {("time", "zorbo")}
    assert report["texts"] == 9


def test_the_report_never_contains_sentences() -> None:
    report = mine(["private sentence zorbo baje"] * 3, min_count=3)
    assert "private" not in str(report)


def test_known_number_words_are_not_gaps() -> None:
    assert mine(["paanch rupaye", "dedh kilo", "do ghante"] * 4)["candidates"] == []
