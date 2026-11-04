import pymorpheus as m


def test_lemmatize_unicode():
    assert m.lemmatize("ἄνθρωπος") == ["ἄνθρωπος"]
    assert "λόγος" in m.lemmatize("λόγους")
    assert m.lemmatize("ἐποίησεν") == ["ποιέω"]


def test_analyze_features():
    (a,) = m.analyze("ἀνθρώπου")
    assert a.lemma == "ἄνθρωπος"
    assert a.pos == "noun"
    assert a.features == {"gender": "masc", "case": "gen", "number": "sg"}
    assert a.stemtype == "os_ou"


def test_beta_input_and_indeclinable():
    (a,) = m.analyze("kai\\")
    assert a.lemma == "καί"
    assert a.pos == "indeclinable"


def test_capitalized_and_unknown():
    assert m.lemmatize("Καί") == ["καί"]  # lower-cased retry (cruncher -S)
    assert m.analyze("Καί", strict_case=True) == []
    assert m.analyze("") == []
    assert m.analyze("xyzzy") == []
