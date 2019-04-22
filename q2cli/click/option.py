import click


class BoolFlagWithValue(click.Option):
    def __init__(self, param_decls, required=False, default=None,
                 multiple=False, type=type):
        super().__init__(param_decls=param_decls, required=required,
                         default=default, is_flag=True, multiple=multiple,
                         type=type)

    def add_to_parser(self, parser, ctx):
        kwargs = dict(dest=self.name, nargs=0, obj=self)

        parser.add_option(self.opts, action='store_maybe', const=True,
                          **kwargs)

        parser.add_option(self.secondary_opts, action='store_maybe',
                          const=False, **kwargs)
