# Version 0.0.5 (2016-10-08)

* ENH: easier tab completion activation: `source tab-qiime` (#84)

* ENH: update language for qiime tools view (#85)

* ENH: update language for qiime tools view (#83)

* MAINT: update peek to match framework (#82)

* REF: set root command help using decorator instead of within constructor (#81)

* ENH: fast Bash tab completion (#79)

* ENH/BUG: add --verbose flag; fix two --cmd-config bugs (#78)

* BUG: fixes broken boolean flag handler (#77)

* ENH: add `qiime info --citations` flag, remove `qiime tools citations` (#76)

* ENH: `qiime tools peek` (#75)

* ENH: `qiime tools extract` displays extracted directory (#74)

* ENH: faster `qiime --version` flag with shorter output (#73)

* ENH: cached CLI state for performance improvements (#67)

* ENH: more descriptive option help text (e.g. required vs optional) (#66)

* ENH: adds support for None as a default value (#65)

* ENH: added defaults for regular parameters (#54)

* TST: update unit tests to work with archive version 0.3.0 (#62)

* ENH: added bool as for #52 (#55)

* ENH: Optional source format on import_data. (#57)

* TST: Update test runner for transformers (#56)

* ENH/REF/MAINT: use new "actions" API; flexible support for output file extensions

* BUG: fixed duplicate command on action

* ENH: Adds `cmd-config` option to cli

* REF: Uses "Handlers" to interface with click allowing better parsing/errors

# Version 0.0.3 (2016-08-08)

* A new command has been added, ``qiime tools plugin-init``, which initializes a new QIIME 2 plugin. This simplifies plugin development by providing a working plugin template that can serve as the basis for a new QIIME 2 plugin. This is developed using [cookiecutter](https://github.com/audreyr/cookiecutter).

* A new command has been added, ``qiime tools citations``, which displays the citations for QIIME and all of the installed plugins. Calling a plugin with ``--help`` (for example, ``qiime my-plugin --help``) now also displays the plugin's citation text, its website, and its user support text.

# Version 0.0.2 (2016-07-19)

* The result of commands can now be saved to an output directory with the `--output-dir` option. This will send any output artifacts/visualizations to the directory if they are not otherwise specified through their normal output options.

* All input options are now prefixed by their type to enable tab-completion. Input artifacts are prefixed with `--i-`, input parameters are `--p-`, metadata is `--m-`, and outputs are prefixed with `--o-`.

* All options are now sorted to make it simpler to read.

* When viewing a visualization, the return/enter key will no longer close the visualization. Use `ctrl-d`, `ctrl-c`, or `q` to quit.

* Improved error message when a command does not exist.

* Various unit-tests have been added.


# Version 0.0.1 (2016-07-14)

Initial alpha release. At this stage, major backwards-incompatible changes are expected to happen.
