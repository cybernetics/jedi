import parsing_representation as pr
import evaluate_representation as er
import debug
import builtin
import settings


class RecursionDecorator(object):
    """
    A decorator to detect recursions in statements. In a recursion a statement
    at the same place, in the same module may not be executed two times.
    """
    def __init__(self, func):
        self.func = func
        self.reset()

    def __call__(self, stmt, *args, **kwargs):
        #print stmt, len(self.node_statements())
        if self.push_stmt(stmt):
            return []
        else:
            result = self.func(stmt, *args, **kwargs)
            self.pop_stmt()
        return result

    def push_stmt(self, stmt):
        self.current = RecursionNode(stmt, self.current)
        if self._check_recursion():
            debug.warning('catched recursion', stmt)
            self.pop_stmt()
            return True
        return False

    def pop_stmt(self):
        if self.current is not None:
            # I don't know how current can be None, but sometimes it happens
            # with Python3.
            self.current = self.current.parent

    def _check_recursion(self):
        test = self.current
        while True:
            test = test.parent
            if self.current == test:
                return True
            if not test:
                return False

    def reset(self):
        self.top = None
        self.current = None

    def node_statements(self):
        result = []
        n = self.current
        while n:
            result.insert(0, n.stmt)
            n = n.parent
        return result


class RecursionNode(object):
    """ A node of the RecursionDecorator. """
    def __init__(self, stmt, parent):
        self.script = stmt.get_parent_until()
        self.position = stmt.start_pos
        self.parent = parent
        self.stmt = stmt

        # Don't check param instances, they are not causing recursions
        # The same's true for the builtins, because the builtins are really
        # simple.
        self.is_ignored = isinstance(stmt, pr.Param) \
                                   or (self.script == builtin.Builtin.scope)

    def __eq__(self, other):
        if not other:
            return None
        return self.script == other.script \
                    and self.position == other.position \
                    and not self.is_ignored and not other.is_ignored


class ExecutionRecursionDecorator(object):
    """
    Catches recursions of executions.
    It is designed like a Singelton. Only one instance should exist.
    """
    def __init__(self, func):
        self.func = func
        self.reset()

    def __call__(self, execution, evaluate_generator=False):
        debug.dbg('Execution recursions: %s' % execution, self.recursion_level,
                            self.execution_count, len(self.execution_funcs))
        if self.check_recursion(execution, evaluate_generator):
            result = []
        else:
            result = self.func(execution, evaluate_generator)
        self.cleanup()
        return result

    @classmethod
    def cleanup(cls):
        cls.parent_execution_funcs.pop()
        cls.recursion_level -= 1

    @classmethod
    def check_recursion(cls, execution, evaluate_generator):
        in_par_execution_funcs = execution.base in cls.parent_execution_funcs
        in_execution_funcs = execution.base in cls.execution_funcs
        cls.recursion_level += 1
        cls.execution_count += 1
        cls.execution_funcs.add(execution.base)
        cls.parent_execution_funcs.append(execution.base)

        if cls.execution_count > settings.max_executions:
            return True

        if isinstance(execution.base, (er.Generator, er.Array)):
            return False
        module = execution.get_parent_until()
        if evaluate_generator or module == builtin.Builtin.scope:
            return False

        if in_par_execution_funcs:
            if cls.recursion_level > settings.max_function_recursion_level:
                return True
        if in_execution_funcs and \
                len(cls.execution_funcs) > settings.max_until_execution_unique:
            return True
        if cls.execution_count > settings.max_executions_without_builtins:
            return True
        return False

    @classmethod
    def reset(cls):
        cls.recursion_level = 0
        cls.parent_execution_funcs = []
        cls.execution_funcs = set()
        cls.execution_count = 0