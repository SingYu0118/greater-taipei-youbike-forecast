import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  technicalSidebar: [
    {
      type: 'category',
      label: 'System design',
      collapsed: false,
      items: ['ARCHITECTURE', 'DATA_PIPELINE', 'DATA_DICTIONARY', 'SOURCES'],
    },
    {
      type: 'category',
      label: 'Modeling and evaluation',
      collapsed: false,
      items: ['MODELING', 'MODEL_CANDIDATE_REVIEW', 'TESTING'],
    },
    {
      type: 'category',
      label: 'Application and operations',
      items: ['API', 'DEPLOYMENT', 'SECURITY'],
    },
    {
      type: 'category',
      label: 'Delivery evidence',
      items: ['IMPLEMENTATION_LOG', 'PRESENTATION_OUTLINE'],
    },
  ],
};

export default sidebars;
