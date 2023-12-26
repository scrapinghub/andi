Changes
=======

0.6.0 (2023-12-26)
------------------

* Drop support for Python 3.5-3.7.
* Add support for dependencies that need to be built using custom callables.

0.5.0 (2023-12-12)
------------------

* Add support for dependency metadata via ``typing.Annotated`` (requires
  Python 3.9+).
* Add docs for overrides.
* Add support for Python 3.10-3.12.
* CI improvements.

0.4.1 (2021-02-11)
------------------

* Overrides support in ``andi.plan``

0.4.0 (2020-04-23)
------------------

* ``andi.inspect`` can handle classes now (their ``__init__`` method
  is inspected)
* ``andi.plan`` and ``andi.inspect`` can handle objects which are
  callable via ``__call__`` method.

0.3.0 (2020-04-03)
------------------

* ``andi.plan`` function replacing ``andi.to_provide``.
* Rewrite README explaining the new approach based in ``plan`` method.
* ``andi.inspect`` return non annotated arguments also.

0.2.0 (2020-02-14)
------------------

* Better attrs support (workaround issue with string type annotations).
* Declare Python 3.8 support.
* More tests; ensure dataclasses support.

0.1 (2019-08-28)
----------------

Initial release.
