# rachis-cli

![](https://github.com/rachis-org/rachis-cli/workflows/ci-dev/badge.svg)

A [click-based](http://click.pocoo.org/) command line interface for [rachis](https://github.com/rachis-org/rachis).

## Installation and getting help

Visit https://qiime2.org to learn more about rachis-cli and the rachis project.

## Enabling tab completion

### Bash

To enable tab completion in Bash, run the following command or add it to your
`.bashrc`/`.bash_profile`:

```bash
source tab-rachis
```

### ZSH

To enable tab completion in ZSH, run the following commands or add them to your
`.zshrc`:

```bash
autoload -Uz compinit && compinit && autoload bashcompinit && bashcompinit && source tab-rachis
```
