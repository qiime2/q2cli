# ----------------------------------------------------------------------------
# Copyright (c) 2016-2021, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
# Some of the source code in this file is derived from original work:
#
# Copyright (c) 2014 by the Pallets team.
#
# To see the license for the original work, see licenses/click.LICENSE.rst
# Specific reproduction and derivation of original work is marked below.
# ----------------------------------------------------------------------------

import click.parser as parser
import click.exceptions as exceptions


class Q2Option(parser.Option):
    @property
    def takes_value(self):
        # store_maybe should take a value so that we hit the right branch
        # in OptionParser._match_long_opt
        return (super().takes_value or self.action == 'store_maybe'
                or self.action == 'append_greedy')

    def _maybe_take(self, state):
        if not state.rargs:
            return None
        # In a more perfect world, we would have access to all long opts
        # and could verify against those instead of just the prefix '--'
        if state.rargs[0].startswith('--'):
            return None
        return state.rargs.pop(0)

    # Specific technique derived from original:
    # < https://github.com/pallets/click/blob/
    #   c6042bf2607c5be22b1efef2e42a94ffd281434c/click/core.py#L867 >
    # Copyright (c) 2014 by the Pallets team.
    def process(self, value, state):
        # actions should update state.opts and state.order

        if (self.dest in state.opts
                and self.action not in ('append', 'append_const',
                                        'append_maybe', 'append_greedy',
                                        'count')):
            raise exceptions.UsageError(
                'Option %r was specified multiple times in the command.'
                % self._get_opt_name())
        elif self.action == 'store_maybe':
            assert value == ()
            value = self._maybe_take(state)
            if value is None:
                state.opts[self.dest] = self.const
            else:
                state.opts[self.dest] = value
            state.order.append(self.obj)  # can't forget this
        elif self.action == 'append_maybe':
            assert value == ()
            value = self._maybe_take(state)
            if value is None:
                state.opts.setdefault(self.dest, []).append(self.const)
            else:
                while value is not None:
                    state.opts.setdefault(self.dest, []).append(value)
                    value = self._maybe_take(state)
            state.order.append(self.obj)  # can't forget this
        elif self.action == 'append_greedy':
            assert value == ()
            value = self._maybe_take(state)
            while value is not None:
                state.opts.setdefault(self.dest, []).append(value)
                value = self._maybe_take(state)
            state.order.append(self.obj)  # can't forget this
        elif self.takes_value and value.startswith('--'):
            # Error early instead of cascading the parse error to a "missing"
            # parameter, which they ironically did provide
            raise parser.BadOptionUsage(
                self, '%s option requires an argument' % self._get_opt_name())
        else:
            super().process(value, state)

    def _get_opt_name(self):
        if hasattr(self.obj, 'secondary_opts'):
            return ' / '.join(self.obj.opts + self.obj.secondary_opts)
        if hasattr(self.obj, 'get_error_hint'):
            return self.obj.get_error_hint(None)
        return ' / '.join(self._long_opts)


class Q2Parser(parser.OptionParser):
    # Modified from original:
    # < https://github.com/pallets/click/blob/
    #   ic6042bf2607c5be22b1efef2e42a94ffd281434c/click/parser.py#L228 >
    # Copyright (c) 2014 by the Pallets team.
    def add_option(self, opts, dest, action=None, nargs=1, const=None,
                   obj=None):
        """Adds a new option named `dest` to the parser.  The destination
        is not inferred (unlike with optparse) and needs to be explicitly
        provided.  Action can be any of ``store``, ``store_const``,
        ``append``, ``appnd_const`` or ``count``.
        The `obj` can be used to identify the option in the order list
        that is returned from the parser.
        """
        if obj is None:
            obj = dest
        opts = [parser.normalize_opt(opt, self.ctx) for opt in opts]

        # BEGIN MODIFICATIONS
        if action == 'store_maybe' or action == 'append_maybe':
            # Specifically target this branch:
            # < https://github.com/pallets/click/blob/
            #   c6042bf2607c5be22b1efef2e42a94ffd281434c/click/parser.py#L341 >
            # this happens to prevents click from reading any arguments itself
            # because it will only "pop" off rargs[:0], which is nothing
            nargs = 0
            if const is None:
                raise ValueError("A 'const' must be provided when action is "
                                 "'store_maybe' or 'append_maybe'")
        elif action == 'append_greedy':
            nargs = 0

        option = Q2Option(opts, dest, action=action, nargs=nargs,
                          const=const, obj=obj)
        # END MODIFICATIONS
        self._opt_prefixes.update(option.prefixes)
        for opt in option._short_opts:
            self._short_opt[opt] = option
        for opt in option._long_opts:
            self._long_opt[opt] = option

    def parse_args(self, args):
        backup = args.copy()  # args will be mutated by super()
        try:
            return super().parse_args(args)
        except exceptions.UsageError:
            if '--help' in backup:
                # all is forgiven
                return {'help': True}, [], ['help']
            raise

    # Override of private member:
    # < https://github.com/pallets/click/blob/
    #   ic6042bf2607c5be22b1efef2e42a94ffd281434c/click/parser.py#L321 >
    def _match_long_opt(self, opt, explicit_value, state):
        if opt not in self._long_opt:
            from q2cli.util import get_close_matches
            # This is way better than substring matching
            possibilities = get_close_matches(opt, self._long_opt)
            raise exceptions.NoSuchOption(opt, possibilities=possibilities,
                                          ctx=self.ctx)

        return super()._match_long_opt(opt, explicit_value, state)
