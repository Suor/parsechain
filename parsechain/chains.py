import re
import datetime
from collections import Mapping, Sequence

from funcy import first, second, last, walk_values, flip, re_find, silent, juxt, notnone, \
    lmap, lmapcat, ldistinct, lcat, re_finder, is_mapping
import lxml.html


class ChainError(Exception):
    pass


class Link:
    def __init__(self, func, *, args=None, name=None):
        assert not isinstance(func, (Link, Chain))
        assert callable(func)
        self.name = name
        self.func = func
        self.args = args

    def __call__(self, *args):
        func = self.func if self.args is None else self.func(*self.args)
        return func(*args)

    def __str__(self):
        result = self.name or self.func.__name__
        if self.args is not None:
            result += f'({", ".join(map(repr, self.args))})'
        return result

    def __repr__(self):
        return f'<Link: {self}>'


class Chain(tuple):
    def __repr__(self):
        return 'C.' + '.'.join(map(str, self))
    __str__ = __repr__
    __name__ = property(__str__)

    def __call__(self, *args):
        # TODO: better check. Base it on function not on arg.
        if len(args) == 1 and is_elements(args[0]):
            value, = args
            for link in self:
                # print(f'Calling {name} on {value}...')
                if value is None:
                    return None
                try:
                    value = link(value)
                except Exception as e:
                    if isinstance(value, lxml.html.HtmlElement):
                        value = re.sub(r'\s+', ' ', Ops.outer_html(value))[:100]
                    raise ChainError(f'Link .{link} failed on {value} in {self}.') from e
            return value
        else:
            *head, last = self
            return Chain(head + [Link(last.func, name=last.name, args=args)])

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(f'No attribute {name} on chain')
        if not hasattr(Ops, name):
            raise ValueError(f'Unknown op {name}')
        return self + Link(getattr(Ops, name), name=name)

    def __or__(self, other):
        # TODO: nicer repr for this?
        # return Chain((('(%s | %s)' % (self, other), notnone_fn(self, other)),))
        return C.call(notnone_fn)(self, other)

    def __add__(self, other):
        if isinstance(other, Link):
            other = (other,)
        elif isinstance(other, (list, tuple)):
            other = tuple(other)
        elif callable(other):
            other = (Link(other),)
        else:
            raise TypeError(f"Can't add chain and {type(other).__name__}")
        return Chain(tuple(self) + other)

    def call(self, func):
        return self + func


C = Chain()


# Chain implementation helpers

def is_elements(arg):
    return isinstance(arg, lxml.html.HtmlElement) or \
        isinstance(arg, list) and arg and all(isinstance(el, lxml.html.HtmlElement) for el in arg)

def multi(coll):
    def make_apply(el):
        return lambda f: f(el) if callable(f) else f

    if is_mapping(coll):
        return lambda el: walk_values(make_apply(el), coll)
    else:
        return lambda el: lmap(make_apply(el), coll)

def notnone_fn(*funcs):
    return lambda val: first(filter(notnone, juxt(*funcs)(val)))


# Processing wrappers

def _list_first(func):
    return lambda els: func(els[0]) if isinstance(els, list) else func(els)

def _list_mapcat(func):
    return lambda els: lmapcat(func, els) if isinstance(els, list) else func(els)

def _list_map(func):
    return lambda els: lmap(func, els) if isinstance(els, list) else func(els)

class Ops:
    const = lambda x: lambda _: x
    multi = multi

    # Traverse
    css = lambda selector: _list_mapcat(lambda el: el.cssselect(selector))
    xpath = lambda query, **params: _list_mapcat(lambda el: el.xpath(query, **params))
    parent = _list_map(lambda el: el.getparent())
    prev = _list_map(lambda el: el.getprevious())
    next = _list_map(lambda el: el.next())

    # Microdata
    def itemscope(name):
        return C.css(f'[itemscope][itemprop={name}]')

    def itemprop(name):
        return C.css(f'[itemprop={name}]')

    def microdata(name):
        return C.css(f'[itemprop={name}]').lmap(C.attr('content') | C.inner_text)

    # Select
    def get(els):
        if len(els) == 0:
            raise ValueError("Trying to get value from empty list: %r..." % els[:3])
        if len(els) > 1:
            raise ValueError("Trying to get single value from multivalue list: %r..." % els[:3])
        return first(els)
    first = first
    second = second
    last = last

    # Access
    text = _list_first(lambda el: el.text)
    texts = lambda els: [el.text for el in els]
    tail = _list_first(lambda el: el.tail)
    attr = lambda name: _list_first(lambda el: el.attrib.get(name))
    attrs = lambda name: lambda els: [el.attrib.get(name) for el in els]

    @_list_first
    def head(el):
        prev = el.getprevious()
        return prev.tail if prev is not None else el.getparent().text

    inner_text = _list_first(lambda el: lxml.html.tostring(el, encoding='unicode', method='text'))
    inner_html = _list_first(lambda el: (el.text or '') +
                             ''.join(lxml.html.tostring(sub, encoding='unicode') for sub in el))
    outer_html = _list_first(lambda el: lxml.html.tostring(el, encoding='unicode'))

    # Text utils
    strip = lambda text: text.strip()
    clean = lambda dirt: lambda text: text.strip(dirt)
    split = lambda by: lambda text: text.split(by)
    re = re_finder

    def re_sub(pattern, repl, count=0, flags=0):
        return lambda text: re.sub(pattern, repl, text, count=count, flags=flags)

    # Data utils
    len = len
    def map(f):
        if isinstance(f, (Mapping, Sequence)):
            f = C.multi(f)
        return lambda els: lmap(f, els)

    # Data cleaning
    float = float
    int = int
    clean_float = lambda text: float(re.sub(r'[^\d,.]', '', text).replace(',', '.'))
    clean_int = lambda text: int(re.sub(r'\D', '', text))

    def date(text):
        months = 'январ феврал март апрел ма июн июл август сентябр октябр ноябр декабр'
        months = dict(flip(enumerate(months.split(), start=1)))

        m = re_find(r'(\d+)\s+(\w+)\s+(\d+)', text)
        if m:
            day, month, year = m
            return datetime.date(int(year), months[month[:-1]], int(day))

    def duration(text):
        regexes = [
            r'()(?:(\d\d):)?(\d\d):(\d\d)(?:\s|$)',
            re.compile(r'''\s* (?:(\d+)\s*д[еньяй.]*)?
                           \s* (?:(\d+)\s*ч[ас.]*)?
                           \s* (?:(\d+)\s*м[инуты.]*)?
                           ()''', re.I | re.X)
        ]
        for regex in regexes:
            m = re_find(regex, text)
            if m:
                days, hours, minutes, seconds = [silent(int)(p) or 0 for p in m]
                if days == hours == minutes == 0:
                    return None
                return (days * 24 + hours * 60 + minutes) * 60 + seconds
                # return datetime.timedelta(days=days, hours=hours, minutes=minutes)

    NO_ARGS = {'parent', 'prev', 'next', 'get', 'first', 'second', 'last',
               'text', 'texts', 'tail', 'head', 'inner_text', 'inner_html', 'outer_html',
               'strip', 'len', 'float', 'int', 'clean_float', 'clean_int', 'date', 'duration'}


# Chain.register('float', _list_first(float))
# @Chain.register
# def func(...):
#     pass


# Advanced introspection

def chain_nodes(nodes, chain):
    """Returns nodes matched by chain."""
    if not chain:
        return nodes

    link, *rest = chain
    if link.func is Ops.const:
        return []
    elif link.func is Ops.multi:
        coll, = link.args
        if isinstance(coll, list):
            coll = dict(enumerate(coll))
        return {k: chain_nodes(nodes, subchain + rest) for k, subchain in coll.items()}
    elif link.func is notnone_fn:
        return ldistinct(lcat(chain_nodes(nodes, subchain + rest) for subchain in link.args))
    else:
        # Doing this manually in case the link encapsulates a chain we can unpack
        func = link.func if link.args is None else link.func(*link.args)
        if isinstance(func, Chain):
            return chain_nodes(nodes, func + rest)
        else:
            next_value = func(nodes)
            return chain_nodes(next_value, rest) if is_elements(next_value) else nodes


def flat_chain_nodes(nodes, chain):
    return flatten_dict(chain_nodes(nodes, chain))


def flatten_dict(d, path='', sep='.'):
    res = {}
    for k, v in d.items():
        new_path = path + sep + str(k) if path else k
        if is_mapping(v):
            res.update(flatten_dict(v, path=new_path, sep=sep))
        else:
            res[new_path] = v
    return res
