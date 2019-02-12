ParseChain |Build Status|
==========

A way to parse html fluently and as declarative as possible. This is in **alpha stage** now, things will change.


Installation
-------------

::

    pip install parsechain


Usage
-----

.. code:: python

    import requests
    from parsechain import C, Response

    # Fetch html and cast it
    response = Response.cast(requests.get(...))

    # Get a movie title and rating
    title = response.css('h1 .title').text
    rating = response.css('.left-box').inner_text.re(r'IMDb: ([\d.]+)').float

    # Or both
    movie = response.root.multi({
        'title': C.css('h1 .title').text,
        'rating': C.css('.left-box').inner_text.re(r'IMDb: ([\d.]+)').float,
    })


The last example could be extended to show chains reuse:


.. code:: python

    def by_label(label):
        return C.css('.left-box').inner_text.re(fr'{label}: ([\w.]+)')

    parse_movie = C.multi({
        'title': C.css('h1 .title').text,
        'rating': by_label('IMDb').float,
        'status': by_label('Status').strip,
    })

    movie = parse_movie(response.root)  # Pass a root of a tree


The complete list of available ops could be seen in ``parsechain.chains.Ops`` class. Proper documentation to follow, some day ;)


.. |Build Status| image:: https://travis-ci.org/Suor/parsechain.svg?branch=master
   :target: https://travis-ci.org/Suor/parsechain
