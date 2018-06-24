from collections import Iterator

from funcy import cached_property
import lxml.html

from .wrappers import make_chainy


class Response:
    def __init__(self, method=None, url=None, body=None, status=None, reason=None, headers=None):
        self.method = method
        self.url = url
        self.body = body
        self.status = status
        self.reason = reason
        self.headers = headers

    @classmethod
    def cast(cls, response):
        # Cast from requests response
        if hasattr(response, 'request'):
            return cls(method=response.request.method, url=response.request.url,
                       status=response.status_code, reason=response.reason,
                       body=response.text, headers=res.headers)
        else:
            raise TypeError("Can't cast from %s" % (response.__class__.__name__))


    def __str__(self):
        url = self.url[:47] + '...' if self.url and len(self.url) > 50 else self.url
        return 'Response(%s, %s %s, %d chars)' % (self.status, self.method, url, len(self.body))
    __repr__ = __str__

    @cached_property
    def root(self):
        return make_chainy(lxml.html.fromstring(self.body))

    def css(self, selector):
        return self.root.css(selector)

    def xpath(self, query, **params):
        return self.root.xpath(query, **params)


