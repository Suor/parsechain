from setuptools import setup


# Remove build status and move Gitter link under title for PyPi
README = open('README.rst').read()    \
    .replace('|Build Status|', '', 1)


setup(
    name='parsechain',
    version='0.0.2',
    author='Alexander Schepanovski',
    author_email='suor.web@gmail.com',

    description='Making parsing concise',
    long_description=README,
    url='http://github.com/Suor/parsechain',
    license='BSD',

    install_requires=[
        'funcy>=1.10.2,<2.0',
        'multidict',
        'lxml',
        'cssselect',
    ],
    packages=['parsechain'],

    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',

        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Text Processing :: Markup :: HTML',
        'Intended Audience :: Developers',
    ]
)
