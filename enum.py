import inspect

def get_user_attributes(cls):
    boring = dir(type('dummy', (object,), {}))
    return [item
            for item in inspect.getmembers(cls)
            if item[0] not in boring and not callable(getattr(cls, item[0]))]

def enum(name, **enums):
    # create the class with the given attributes
    NewClass = type(name, (), enums)
    # create a mapping of the enum constants
    # to automatically generated string names
    # which will be added as a class attribute
    # e.g. if enum was created with enum(GO_FRONT=1, GO_BACK=-1)
    # the mappings will be { 1: "go front", -1: "go back" }
    NewClass.str_values = dict( (value, name.lower().replace('_', ' '))
        for name, value in get_user_attributes(NewClass)
    )
    NewClass.values = NewClass.str_values.keys()
    # create a to_str class method for the enum
    def to_str(cls, val): return cls.str_values[val]
    to_str.__doc__ = "string representation of %s" % name
    to_str.__name__ = "to_str"
    setattr(NewClass, "to_str", classmethod(to_str))
    # return the generated enum class
    return NewClass

