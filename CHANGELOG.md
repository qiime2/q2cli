# Version 0.0.2 (2016-07-19)

* The result of commands can now be saved to an output directory with the `--output-dir` option. This will send any output artifacts/visualizations to the directory if they are not otherwise specified through their normal output options.

* All input options are now prefixed by their type to enable tab-completion. Input artifacts are prefixed with `--i-`, input parameters are `--p-`, metadata is `--m-`, and outputs are prefixed with `--o-`.

* All options are now sorted to make it simpler to read.

* When viewing a visualization, the return/enter key will no longer close the visualization. Use `ctrl-d`, `ctrl-c`, or `q` to quit.

* Improved error message when a command does not exist.

* Various unit-tests have been added.


# Version 0.0.1 (2016-07-14)

Initial alpha release. At this stage, major backwards-incompatible changes are expected to happen.
