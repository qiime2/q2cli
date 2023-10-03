# q2cli

![](https://github.com/qiime2/q2cli/workflows/ci-dev/badge.svg)

A [click-based](http://click.pocoo.org/) command line interface for [QIIME
2](https://github.com/qiime2/qiime2).

## Installation and getting help

Visit https://qiime2.org to learn more about q2cli and the QIIME 2 project.

## Enabling tab completion

### Bash

To enable tab completion in Bash, run the following command or add it to your
`.bashrc`/`.bash_profile`:

```bash
source tab-qiime
```

### ZSH

To enable tab completion in ZSH, run the following commands or add them to your
`.zshrc`:

```bash
autoload -Uz compinit && compinit && autoload bashcompinit && bashcompinit && source tab-qiime
```
