class StubType:
    def __getitem__(self, item):
        pass


Any = StubType()
Union = StubType()
Sequence = StubType()
Mapping = StubType()
Callable = StubType()
Dict = StubType()
IO = StubType()
