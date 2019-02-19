from parsechain import make_chainy


def test_str():
    s = make_chainy(' hey!')
    assert s.trim == 'hey!'
    assert s.strip() == 'hey!'
    assert s.strip('!').trim == 'hey'
