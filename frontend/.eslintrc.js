// M_12 P1: 원본 .eslintrc.js에서 airbnb 제거, 설치된 플러그인만 사용.
// 이유: eslint-config-airbnb 및 관련 플러그인(jsx-a11y, import, react-hooks)이
//       package.json dependencies에 없어 --ignore-scripts 설치 후 사용 불가 (pre-existing 문제).
module.exports = {
  parser: '@typescript-eslint/parser',
  extends: [
    'plugin:@typescript-eslint/recommended',
    'plugin:react/recommended',
  ],
  plugins: ['@typescript-eslint', 'react'],
  settings: {
    react: {
      version: 'detect',
    },
  },
  reportUnusedDisableDirectives: false,
  rules: {
    'no-unused-vars': 'off',
    'max-len': 'off',
    '@typescript-eslint/no-explicit-any': 'off',
    '@typescript-eslint/no-unused-vars': 'off',
    'no-console': 'off',
    'react/jsx-filename-extension': [1, { extensions: ['.tsx', '.jsx'] }],
    'react/react-in-jsx-scope': 'off',
    'react/jsx-props-no-spreading': 'off',
    'react/display-name': 'off',
    'react/require-default-props': 'off',
    '@typescript-eslint/ban-ts-comment': 'off',
    '@typescript-eslint/no-var-requires': 'off',
    'no-shadow': 'off',
    'no-underscore-dangle': 'off',
    'no-use-before-define': 'off',
    'no-param-reassign': 'off',
    // 알 수 없는 규칙을 에러로 처리하지 않음 (설치되지 않은 플러그인 규칙 허용)
    'jsx-a11y/iframe-has-title': 'off',
    'import/order': 'off',
    'import/no-extraneous-dependencies': 'off',
    'react-hooks/exhaustive-deps': 'off',
  },
};
