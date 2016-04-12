# q2cli
A [click-based](http://click.pocoo.org/) command line interface for [QIIME 2](https://github.com/biocore/qiime2).

# Installation and usage

To use this you'll need to have QIIME 2 installed, as well as some plugins to interact with. Since there are not official releases of these packages yet, you can install the development versions as follows. First we'll just get the interface working. *(The `setuptools` specification seems to be required due to an issue described [here](https://github.com/pypa/setuptools/issues/523).)*

```bash
conda create -n q2cli python=3.5 jupyter scikit-bio 'setuptools<20.5.0' -c biocore
source activate q2cli
# install qiime and q2cli
pip install https://github.com/biocore/qiime2/archive/master.zip https://github.com/qiime2/q2cli/archive/master.zip
```

You can now run ``qiime --help`` to see the available commands. You can discover what plugins you currently have installed with ``qiime plugins``

```bash
qiime --help
qiime --plugins
qiime --version
```

There's not much to do without some plugins, so install the ``feature-table`` plugin and execute the ``qiime --plugins`` command again.

```bash
pip install https://github.com/qiime2/q2-feature-table/archive/master.zip
qiime --plugins
```

You should now see that you have one plugin installed.

If you call ``qiime --help`` again, you'll see that you now have a new command available, corresponding to that plugin. To see what subcommands that plugin defines, call it with ``-help``:

```bash
qiime feature-table --help
```

Install the ``diversity`` plugin as well. You'll then have two plugins installed, as well as a couple more workflows.

```bash
pip install https://github.com/qiime2/q2-diversity/archive/master.zip
qiime --plugins
qiime diversity --help
```

Next you should try to run a command that actually does some work. ``qiime diversity feature_table_to_pcoa`` is a good one to try. You can download demo input ``qtf`` files to work with [here](https://github.com/qiime2/q2d3/tree/master/demo/analysis-dir). Here's the command I ran:

```bash
qiime diversity feature_table_to_pcoa --feature_table table.qtf --phylogeny phylogeny.qtf --metric unweighted_unifrac --depth 50 --distance_matrix uu-dm.qtf --pcoa_results uu-pc.qtf
```
