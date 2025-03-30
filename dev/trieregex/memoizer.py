from functools import partial
from typing import Any, Callable, Dict, Type


class Memoizer:
    """Decorator class for increasing the processing speed of a function using 
    memoization with cache-clearing capability
    """
    __slots__ = ['func', 'cache']

    def __init__(self, func):
        # type: (Callable) -> None
        self.func = func
        self.cache = {}  # type: Dict[str, Any]

    def __call__(self, *args):
        # type: (Any) -> Dict[str, Any]
        stringed = str(args)
        if stringed not in self.cache:
            self.cache[stringed] = self.func(*args)
        return self.cache[stringed]

    def __get__(self, instance, owner):
        # type: (object, Type) -> Callable
        fn = partial(self.__call__, instance)
        fn.__name__ = f'[Memoizer-decorated function] {self.func.__name__}'
        fn.__doc__ = f'[Memoizer-decorated function] {self.func.__doc__}'
        fn.clear_cache = self._clear_cache
        return fn

    def _clear_cache(self):
        # type: () -> None
        self.cache.clear()
