import json
import re
import datetime
from collections import Mapping, Sequence
from functools import wraps

from funcy import first, second, last, walk_values, flip, re_find, silent, juxt, notnone, \
    lmap, lmapcat, ldistinct, lcat, re_finder, is_mapping, lfilter
import dateparser
import lxml.html


class ChainError(Exception):
    pass


class Link:
    def __init__(self, func, *, args=None, kwargs=None, name=None):
        assert not isinstance(func, (Link, Chain))
        assert callable(func)
        self.name = name
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}

    def __call__(self, *args):
        func = self.func if self.args is None else self.func(*self.args, **self.kwargs)
        return func(*args)

    def __str__(self):
        result = self.name or self.func.__name__
        args_reprs = []
        if self.args is not None:
            args_reprs.extend(['...'] if self.args is ... else map(repr, self.args))
        if self.kwargs:
            args_reprs.extend(f'{name}={repr(value)}' for name, value in kwargs.items())
        if args_reprs:
            result += f'({", ".join(args_reprs)})'
        return result

    def __repr__(self):
        return f'<Link: {self}>'


class Chain(tuple):
    def __repr__(self):
        return 'C.' + '.'.join(map(str, self))
    __str__ = __repr__
    __name__ = property(__str__)

    def __call__(self, *args, **kwargs):
        # Rebuild the chain if waiting for args
        if self and self[-1].args is ...:
            *head, last = self
            return Chain(head + [Link(last.func, name=last.name, args=args, kwargs=kwargs)])
        else:
            assert len(args) == 1 and not kwargs, "Expecting single value to rpocess by chain"
            value, = args
            for link in self:
                if value is None:
                    return None
                try:
                    value = link(value)
                except Exception as e:
                    if isinstance(value, lxml.html.HtmlElement):
                        value = re.sub(r'\s+', ' ', Ops.outer_html(value))[:100]
                    raise ChainError(f'Link .{link} failed on {value} in {self}.') from e
            return value

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(f'No attribute {name} on chain')
        if not hasattr(Ops, name):
            raise ValueError(f'Unknown op {name}')

        # Add new link and mark args as waiting for filling in if function has them
        func = getattr(Ops, name)
        has_args = getattr(func, 'has_args', False)
        return self + Link(func, name=name, args=... if has_args else None)

    def __or__(self, other):
        # TODO: nicer repr for this?
        # return Chain((('(%s | %s)' % (self, other), notnone_fn(self, other)),))
        return Chain((Link(notnone_fn, args=(self, other)),))

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

def has_args(func):
    # Wrap functions from other modules or just mark directly local ones
    if getattr(func, '__module__', None) != __name__:
        wrapper = wraps(func)(lambda *a, **kw: func(*a, **kw))
    else:
        wrapper = func
    wrapper.has_args = True
    return wrapper

def is_elements(arg):
    return isinstance(arg, lxml.html.HtmlElement) or \
        isinstance(arg, list) and arg and all(isinstance(el, lxml.html.HtmlElement) for el in arg)

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
    const = has_args(lambda x: lambda _: x)

    @has_args
    def multi(coll):
        def make_apply(el):
            return lambda f: f(el) if callable(f) else f

        if is_mapping(coll):
            return lambda el: walk_values(make_apply(el), coll)
        else:
            return lambda el: lmap(make_apply(el), coll)

    # Traverse
    css = has_args(lambda selector: _list_mapcat(lambda el: el.cssselect(selector)))
    xpath = has_args(lambda query, **params: _list_mapcat(lambda el: el.xpath(query, **params)))
    parent = _list_map(lambda el: el.getparent())
    prev = _list_map(lambda el: el.getprevious())
    next = _list_map(lambda el: el.getnext())

    # Microdata
    @has_args
    def itemscope(name):
        return C.css(f'[itemscope][itemprop*={name}]')

    @has_args
    def itemprop(name):
        return C.css(f'[itemprop*={name}]')

    @has_args
    def microdata(name):
        return C.css(f'[itemprop*={name}]').map(C.attr('content') | C.inner_text)

    def ld(node):
        text = C.css('script[type="application/ld+json"]').inner_text(node)
        return json.loads(text)

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
    slice = has_args(lambda start, stop=None, step=None: lambda val: val[slice(start, stop, step)])

    # Access
    text = _list_first(lambda el: el.text)
    texts = lambda els: [el.text for el in els]
    tail = _list_first(lambda el: el.tail)
    attr = has_args(lambda name: _list_first(lambda el: el.attrib.get(name)))
    attrs = has_args(lambda name: lambda els: [el.attrib.get(name) for el in els])

    @_list_first
    def head(el):
        prev = el.getprevious()
        return prev.tail if prev is not None else el.getparent().text

    inner_text = _list_first(lambda el: lxml.html.tostring(el, encoding='unicode', method='text'))
    inner_html = _list_first(lambda el: (el.text or '') +
                             ''.join(lxml.html.tostring(sub, encoding='unicode') for sub in el))
    outer_html = _list_first(lambda el: lxml.html.tostring(el, encoding='unicode'))

    @_list_first
    def html_to_text(html):
        """Cleans html preserving newlines"""
        if isinstance(html, lxml.html.HtmlElement):
            html = Ops.inner_html(html)

        html = re.sub(r'\s+', ' ', html).strip()
        html = re.sub(r'<br[^>]*>|</li>', '\n', html, flags=re.I)
        html = re.sub(r'</p>', '\n\n', html, flags=re.I)
        if not html or html.isspace():
            return ''
        return lxml.html.tostring(lxml.html.fromstring(html), encoding='unicode', method='text')

    # Text utils
    # TODO: make these two work with bytes?
    trim = lambda text: str.strip(text)
    strip = has_args(lambda dirt=None: lambda text: str.strip(text, dirt))
    normspace = normalize_whitespace = lambda text: re.sub(r'\s+', ' ', text).strip()
    split = has_args(lambda by: lambda text: text.split(by))
    re = has_args(re_finder)

    @has_args
    def re_sub(pattern, repl, count=0, flags=0):
        return lambda text: re.sub(pattern, repl, text, count=count, flags=flags)

    # Data utils
    len = len

    @has_args
    def map(f):
        if not callable(f) and isinstance(f, (Mapping, Sequence)):
            f = C.multi(f)
        return lambda els: lmap(f, els)
    filter = has_args(lambda pred: lambda seq: lfilter(pred, seq))

    # Data cleaning
    float = float
    int = int
    clean_float = lambda text: float(re.sub(r'[^\d,.]', '', text).replace(',', '.'))
    clean_int = lambda text: int(re.sub(r'\D', '', text))

    date = dateparser.parse

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
