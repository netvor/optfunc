from optparse import OptionParser, make_option
import sys, inspect, re

single_char_prefix_re = re.compile('^[a-zA-Z0-9]_')

class ErrorCollectingOptionParser(OptionParser):
    def __init__(self, *args, **kwargs):
        self._errors = []
        # can't use super() because OptionParser is an old style class
        OptionParser.__init__(self, *args, **kwargs)
    
    def error(self, msg):
        self._errors.append(msg)

def func_to_optionparser(func):
    args, varargs, varkw, defaultvals = inspect.getargspec(func)
    defaultvals = defaultvals or ()
    options = dict(zip(args[-len(defaultvals):], defaultvals))
    argstart = 0
    if func.__name__ == '__init__':
        argstart = 1
    if defaultvals:
        required_args = args[argstart:-len(defaultvals)]
    else:
        required_args = args[argstart:]
    
    # Build the OptionParser:
    opt = ErrorCollectingOptionParser(usage = func.__doc__)
    
    helpdict = getattr(func, 'optfunc_arghelp', {})
    
    # Add the options, automatically detecting their -short and --long names
    shortnames = set(['h'])
    for funcname, example in options.items():
        # They either explicitly set the short with x_blah...
        name = funcname
        if single_char_prefix_re.match(name):
            short = name[0]
            name = name[2:]
        # Or we pick the first letter from the name not already in use:
        else:
            for short in name:
                if short not in shortnames:
                    break
        
        shortnames.add(short)
        short_name = '-%s' % short
        long_name = '--%s' % name.replace('_', '-')
        if example in (True, False, bool):
            action = 'store_true'
        else:
            action = 'store'
        opt.add_option(make_option(
            short_name, long_name, action=action, dest=name, default=example,
            help = helpdict.get(funcname, '')
        ))
    
    return opt, required_args

def resolve_args(func, argv):
    parser, required_args = func_to_optionparser(func)
    options, args = parser.parse_args(argv)
    
    # Do we have correct number af required args?
    if len(required_args) != len(args):
        if not hasattr(func, 'optfunc_notstrict'):
            parser._errors.append('Required %d arguments, got %d' % (
                len(required_args), len(args)
            ))
    
    # Ensure there are enough arguments even if some are missing
    args += [None] * (len(required_args) - len(args))
    for i, name in enumerate(required_args):
        setattr(options, name, args[i])
    
    return options.__dict__, parser._errors

def run(obj, argv=None, stderr=sys.stderr):
    argv = argv or sys.argv[1:]
    if inspect.isfunction(obj):
        resolved, errors = resolve_args(obj, argv)
    elif inspect.isclass(obj):
        if hasattr(obj, '__init__'):
            resolved, errors = resolve_args(obj.__init__, argv)
        else:
            resolved, errors = {}, []
    else:
        raise TypeError('arg is not a Python function or class')
    if not errors:
        try:
            return obj(**resolved)
        except Exception, e:
            stderr.write(str(e) + '\n')
    else:
        stderr.write("%s\n" % '\n'.join(errors))

# Decorators
def notstrict(fn):
    fn.optfunc_notstrict = True
    return fn

def arghelp(name, help):
    def inner(fn):
        d = getattr(fn, 'optfunc_arghelp', {})
        d[name] = help
        setattr(fn, 'optfunc_arghelp', d)
        return fn
    return inner
