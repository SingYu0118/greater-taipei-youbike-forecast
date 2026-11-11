import type {ReactNode} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import Head from '@docusaurus/Head';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Translate from '@docusaurus/Translate';
import styles from './index.module.css';

const sections = [
  {
    number: '01',
    title: <Translate id="home.section.01.title">System design</Translate>,
    body: <Translate id="home.section.01.body">Architecture, collection, reproducibility, and data contracts.</Translate>,
    to: '/docs/ARCHITECTURE',
  },
  {
    number: '02',
    title: <Translate id="home.section.02.title">Modeling</Translate>,
    body: <Translate id="home.section.02.body">Seven model families under leakage-safe temporal validation.</Translate>,
    to: '/docs/MODELING',
  },
  {
    number: '03',
    title: <Translate id="home.section.03.title">Application</Translate>,
    body: <Translate id="home.section.03.body">FastAPI contracts, serving gates, and React application behaviour.</Translate>,
    to: '/docs/API',
  },
  {
    number: '04',
    title: <Translate id="home.section.04.title">Operations</Translate>,
    body: <Translate id="home.section.04.body">Deployment, security, cost controls, testing, and evidence.</Translate>,
    to: '/docs/DEPLOYMENT',
  },
];

export default function Home(): ReactNode {
  const {siteConfig} = useDocusaurusContext();
  const productAppUrl = String(siteConfig.customFields?.productAppUrl ?? 'http://localhost:5173');
  return (
    <Layout>
      <Head>
        <title>Engineering documentation | Greater Taipei YouBike Forecast</title>
        <meta
          name="description"
          content="Bilingual engineering documentation for the Greater Taipei YouBike forecast system."
        />
      </Head>
      <main>
        <section className={styles.hero}>
          <div className={styles.heroGrid}>
            <div>
              <p className={styles.eyebrow}>GREATER TAIPEI / ONE HOUR AHEAD</p>
              <h1>
                <Translate id="home.hero.title">Forecasting station inventory, with evidence.</Translate>
              </h1>
              <p className={styles.lead}>
                <Translate id="home.hero.lead">
                  A bilingual technical record of the data pipeline, temporal validation, model competition, API, and production controls.
                </Translate>
              </p>
              <div className={styles.actions}>
                <a className="button button--primary button--lg" href={productAppUrl}>
                  <Translate id="home.action.product">Open product</Translate>
                </a>
                <Link className="button button--secondary button--lg" to="/docs/ARCHITECTURE">
                  <Translate id="home.action.start">Explore documentation</Translate>
                </Link>
              </div>
            </div>
            <div className={styles.signalPanel} aria-label="System summary">
              <div><span>HORIZON</span><strong>+60 min</strong></div>
              <div><span>NETWORK</span><strong>3,399 stations</strong></div>
              <div><span>VALIDATION</span><strong>3 folds + holdout</strong></div>
              <div><span>CANDIDATES</span><strong>7 models</strong></div>
            </div>
          </div>
        </section>
        <section className={styles.sectionGrid}>
          {sections.map(({number, title, body, to}) => (
            <Link className={clsx(styles.card)} to={to} key={number}>
              <span>{number}</span>
              <h2>{title}</h2>
              <p>{body}</p>
              <b><Translate id="home.section.open">Open section →</Translate></b>
            </Link>
          ))}
        </section>
      </main>
    </Layout>
  );
}
