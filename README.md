# q2cli
A [click-based](http://click.pocoo.org/) command line interface for [QIIME 2](https://github.com/biocore/qiime2).

## Installation and usage

To try q2cli, check out the [Installing and using QIIME 2 demo](https://github.com/qiime2/qiime2/wiki/Installing-and-using-QIIME-2).

## Enabling Bash tab completion

To enable tab completion in Bash, run the following command or add it to your `.bashrc`/`.bash_profile`:

```bash
eval "$(_QIIME_COMPLETE=source qiime)"
```

Note: tab completion is currently **VERY** slow, track progress on [#6](https://github.com/qiime2/q2cli/issues/6).
