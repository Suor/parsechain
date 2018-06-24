from .chains import Ops


__all__ = ['make_chainy']


class Chainy:
    pass

class ChainyList(list, Chainy):
    pass

class ChainyStr(str, Chainy):
    pass

class ChainyHtmlElement(lxml.html.HtmlElement, Chainy):
    pass

chainy_classes = {lxml.html.HtmlElement: ChainyHtmlElement}


def make_chainy(value):
    if isinstance(value, Chainy):
        return value
    elif isinstance(value, str):
        return ChainyStr(value)
    elif isinstance(value, (list, Iterator)):
        return ChainyList(value)
    elif type(value) in chainy_classes:
        value.__class__ = chainy_classes[type(value)]
        return value
    else:
        return value
        # raise ValueError("Don't know how to make chainy %s" % type(value).__class__.__name__)


def make_chainy_op(name, func):
    if name in Ops.NO_ARGS:
        def wrapper(self):
            return make_chainy(func(self))
    else:
        def wrapper(self, *args, **kwargs):
            return make_chainy(func(*args, **kwargs)(self))

    wrapper.__qualname__ = 'Chainy.' + name
    wrapper.__name__ = name
    return wrapper


for name, func in Ops.__dict__.items():
    if name.startswith('_') or not callable(func):
        continue
    setattr(Chainy, name, make_chainy_op(name, func))
