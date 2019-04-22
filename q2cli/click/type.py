

class QIIME2Type(click.ParamType):
    def __init__(self, type_ast, type_repr, input=True):
        self.type_repr = type_repr
        self.type_ast = type_ast
        self.multiple = False
        self.union_tail = []
        self.input = input

        if self.ast['type'] == 'expression':
            ast = self.ast
        elif self.ast['type'] == 'union' and self.ast['members']:
            ast = self.ast['members'][0]
        else:
            raise NotImplementedError('Unknown expression type: %r'
                                      % self.ast['type'])

        if self.ast['name'] in {'List', 'Set'}:
            self.multiple = True
            ast = ast['fields'][0]
            # Check for union inside, members cannot be empty (bottom type)
            if ast['type'] == 'union':
                ast = self.ast['members'][0]
                self.union_tail = self.ast['members'][1:]

        self.inner_ast = ast

    def convert(self, value, param, ctx):
        import qiime2.sdk

        if not self.input:
            path = click.Path(dir_okay=False, writable=True)
            return path.convert(value, param, ctx)

        if not self.inner_ast['builtin']:
            try:
                result = qiime2.sdk.Result.load(value)
            except Exception:
                self.fail('%r is not a QIIME 2 Artifact (.qza)' % value, param, ctx)

            if isinstance(result, qiime2.sdk.Visualization):
                self.fail('%r is a QIIME 2 visualization (.qzv), not an '
                          ' Artifact (.qza)' % value, param, ctx)

            return result

        type_expr = qiime2.sdk.type_from_ast(self.ast)


    @property
    def name(self):
        return self.get_metavar('')

    def get_metavar(self, param):
        name_to_var = {
            'Visualization': 'VISUALIZATION',
            'Int': 'INTEGER',
            'Str': 'TEXT',
            'Float': 'NUMBER',
            'Bool': 'BOOLEAN', # Not actually used
        }

        if not self.inner_ast['builtin']:
            metavar = 'ARTIFACT'
        else:
            metavar = name_to_var[self.inner_ast['name']]
            for member in self.union_tail:
                if metavar != name_to_var[member['name']]:
                    metavar = 'VALUE'
                    break

        if metavar == 'NUMBER' and not self.union_tail:
            start, end = self.inner_ast['predicate']['range']
            if start == 0 and end == 1:
                metavar = 'PROPORTION'

        if self.multiple:
            metavar += 'S'

        return metavar + " " + click.style(self.repr, fg='green')

