if [ -n "${ZSH_VERSION-}" ]; then
  autoload -Uz compinit && compinit && autoload bashcompinit && bashcompinit && source tab-qiime
elif [ -n "${BASH_VERSION-}" ]; then
  source tab-qiime
fi
