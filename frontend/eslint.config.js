import sveltePlugin from 'eslint-plugin-svelte';

export default [
  {
    ignores: ['dist/', 'node_modules/'],
  },
  ...sveltePlugin.configs['flat/recommended'],
  {
    rules: {
      'no-unused-vars': 'warn',
      'no-var': 'warn',
      // 宽松配置，后续逐步收紧
      'svelte/require-each-key': 'warn',
      'svelte/no-unused-svelte-ignore': 'warn',
      'svelte/no-useless-mustaches': 'warn',
    },
  },
];
