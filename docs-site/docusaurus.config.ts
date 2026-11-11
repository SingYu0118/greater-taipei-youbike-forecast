import type {Config} from '@docusaurus/types';
import type {UserThemeConfig} from '@docusaurus/theme-common';
import {themes as prismThemes} from 'prism-react-renderer';

const productAppUrl = process.env.PRODUCT_APP_URL ?? 'http://localhost:5173';

const config: Config = {
  title: 'Greater Taipei YouBike Forecast',
  tagline: 'Engineering documentation for one-hour-ahead station forecasting',
  favicon: 'img/favicon.svg',
  url: 'https://greater-taipei-youbike-forecast-docs.pages.dev',
  baseUrl: '/',
  organizationName: 'SingYu0118',
  projectName: 'greater-taipei-youbike-forecast',
  onBrokenLinks: 'throw',
  markdown: {hooks: {onBrokenMarkdownLinks: 'warn'}},
  trailingSlash: false,
  customFields: {productAppUrl},
  i18n: {
    defaultLocale: 'en',
    locales: ['en', 'zh-Hant'],
    localeConfigs: {
      en: {label: 'English', htmlLang: 'en'},
      'zh-Hant': {label: '繁體中文', htmlLang: 'zh-Hant'},
    },
  },
  plugins: [
    [
      '@docusaurus/plugin-content-docs',
      {
        path: '../docs',
        routeBasePath: 'docs',
        sidebarPath: './sidebars.ts',
        editUrl:
          'https://github.com/SingYu0118/greater-taipei-youbike-forecast/edit/main/',
        showLastUpdateTime: true,
      },
    ],
    ['@docusaurus/plugin-content-pages', {path: 'src/pages'}],
    '@docusaurus/plugin-sitemap',
  ],
  themes: [
    ['@docusaurus/theme-classic', {customCss: './src/css/custom.css'}],
    [
      require.resolve('@easyops-cn/docusaurus-search-local'),
      {
        hashed: 'filename',
        indexDocs: true,
        indexBlog: false,
        indexPages: true,
        language: ['en', 'zh'],
        docsDir: '../docs',
        highlightSearchTermsOnTargetPage: true,
        explicitSearchResultPath: true,
        searchResultLimits: 10,
      },
    ],
  ],
  themeConfig: {
    metadata: [
      {name: 'theme-color', content: '#f28c00'},
      {
        name: 'description',
        content:
          'Bilingual technical documentation for the Greater Taipei YouBike forecasting system.',
      },
    ],
    navbar: {
      title: 'YouBike Forecast Docs',
      logo: {alt: 'YouBike Forecast', src: 'img/logo.svg'},
      hideOnScroll: false,
      items: [
        {href: productAppUrl, label: 'Product', position: 'left'},
        {type: 'docSidebar', sidebarId: 'technicalSidebar', position: 'left', label: 'Documentation'},
        {to: '/docs/MODELING', label: 'Modeling', position: 'left'},
        {to: '/docs/API', label: 'API', position: 'left'},
        {type: 'localeDropdown', position: 'right'},
        {
          href: 'https://github.com/SingYu0118/greater-taipei-youbike-forecast',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    docs: {
      sidebar: {hideable: true, autoCollapseCategories: true},
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Product',
          items: [
            {label: 'Open application', href: productAppUrl},
            {label: 'API contract', to: '/docs/API'},
          ],
        },
        {
          title: 'System',
          items: [
            {label: 'Architecture', to: '/docs/ARCHITECTURE'},
            {label: 'Data pipeline', to: '/docs/DATA_PIPELINE'},
            {label: 'Modeling', to: '/docs/MODELING'},
          ],
        },
        {
          title: 'Operate',
          items: [
            {label: 'API', to: '/docs/API'},
            {label: 'Deployment', to: '/docs/DEPLOYMENT'},
            {label: 'Security', to: '/docs/SECURITY'},
          ],
        },
        {
          title: 'Project',
          items: [
            {label: 'Implementation log', to: '/docs/IMPLEMENTATION_LOG'},
            {label: 'GitHub', href: 'https://github.com/SingYu0118/greater-taipei-youbike-forecast'},
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Greater Taipei YouBike Forecast.`,
    },
    prism: {theme: prismThemes.github, darkTheme: prismThemes.dracula},
    colorMode: {defaultMode: 'light', respectPrefersColorScheme: false},
  } satisfies UserThemeConfig,
};

export default config;
