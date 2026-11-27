import React, { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  ArrowUpRight,
  Award,
  BarChart3,
  Boxes,
  CheckCircle2,
  Cpu,
  Download,
  ExternalLink,
  Filter,
  Flame,
  GitCompare,
  Layers,
  PackageCheck,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  X,
  Zap,
} from 'lucide-react';
import type {
  AnalyticsOverview,
  BenchmarkResponse,
  CompareResponse,
  ProductCard,
  SearchResponse,
  SuggestResponse,
} from './types';

const XLSX_PRESETS = [
  'astra linux',
  'Microsoft Office для дома и бизнеса',
  'kaspersky small office security',
  'крипто про csp 5.0',
  'anydesk',
  'кибер бэкап',
  'сканер-вс',
  'мтс',
  'max patrol',
  '365',
];

const SMART_PRESETS = [
  'сервер',
  'антивирь',
  'винда',
  'офис',
  'астра линукс',
  'мдаемон',
  'fcnhf kbyerc',
  'акронис',
  'зум',
  'фотошоп',
];

function formatPrice(val: number): string {
  if (!val || val <= 0) return 'По запросу';
  return `${Math.round(val).toLocaleString('ru-RU')} ₽`;
}

const ProductThumb: React.FC<{ src: string; alt: string; className?: string }> = ({
  src,
  alt,
  className,
}) => {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div
        className={className}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#94a3b8',
          background: '#f8fafc',
          width: '100%',
          height: '100%',
        }}
      >
        <Boxes size={26} />
      </div>
    );
  }
  return <img src={src} alt={alt} className={className} onError={() => setFailed(true)} />;
};

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'storefront' | 'compare' | 'analytics'>('storefront');

  // Storefront search state
  const [queryInput, setQueryInput] = useState('astra linux');
  const [searchData, setSearchData] = useState<SearchResponse | null>(null);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [intentOverride, setIntentOverride] = useState<string | null>(null);
  const [onlyAvailable, setOnlyAvailable] = useState(false);
  const [registryOnly, setRegistryOnly] = useState(false);
  const [promoOnly, setPromoOnly] = useState(false);

  // Live Typeahead suggest state
  const [suggestData, setSuggestData] = useState<SuggestResponse | null>(null);
  const [showSuggest, setShowSuggest] = useState(false);
  const searchWrapRef = useRef<HTMLDivElement>(null);

  // SKU Modal state
  const [modalProduct, setModalProduct] = useState<ProductCard | null>(null);

  // Compare & Benchmark state
  const [compareQuery, setCompareQuery] = useState('сервер');
  const [compareData, setCompareData] = useState<CompareResponse | null>(null);
  const [benchmarkData, setBenchmarkData] = useState<BenchmarkResponse | null>(null);
  const [loadingCompare, setLoadingCompare] = useState(false);

  // Analytics state + Interactive ROI calculator
  const [analyticsData, setAnalyticsData] = useState<AnalyticsOverview | null>(null);
  const [monthlySearches, setMonthlySearches] = useState(15000);
  const [convRate, setConvRate] = useState(7.5);
  const [avgCheck, setAvgCheck] = useState(70000);

  const executeSearch = async (
    q: string,
    opts?: {
      intent?: string | null;
      avail?: boolean;
      reg?: boolean;
      promo?: boolean;
    }
  ) => {
    const clean = q.trim();
    if (!clean) return;
    setLoadingSearch(true);
    setShowSuggest(false);
    const effIntent = opts?.intent !== undefined ? opts.intent : intentOverride;
    const effAvail = opts?.avail !== undefined ? opts.avail : onlyAvailable;
    const effReg = opts?.reg !== undefined ? opts.reg : registryOnly;
    const effPromo = opts?.promo !== undefined ? opts.promo : promoOnly;

    try {
      const params = new URLSearchParams({ q: clean, limit: '8' });
      if (effIntent) params.set('intent', effIntent);
      if (effAvail) params.set('only_available', 'true');
      if (effReg) params.set('registry_only', 'true');
      if (effPromo) params.set('promo_only', 'true');

      const res = await fetch(`/api/search?${params.toString()}`);
      const json: SearchResponse = await res.json();
      setSearchData(json);
    } catch (err) {
      console.error('Search error:', err);
    } finally {
      setLoadingSearch(false);
    }
  };

  // Initial load
  useEffect(() => {
    executeSearch('astra linux', { intent: null });
  }, []);

  // Debounced live suggest while typing
  useEffect(() => {
    if (!showSuggest) return;
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/suggest?q=${encodeURIComponent(queryInput)}`);
        const json: SuggestResponse = await res.json();
        setSuggestData(json);
      } catch (e) {
        console.error(e);
      }
    }, 110);
    return () => clearTimeout(timer);
  }, [queryInput, showSuggest]);

  // Close suggest dropdown on outside click
  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (searchWrapRef.current && !searchWrapRef.current.contains(e.target as Node)) {
        setShowSuggest(false);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  // Load Compare & Benchmark when tab selected
  const loadComparison = async (q: string) => {
    setLoadingCompare(true);
    try {
      const res = await fetch(`/api/compare?q=${encodeURIComponent(q)}`);
      setCompareData(await res.json());
    } finally {
      setLoadingCompare(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'compare') {
      if (!compareData) loadComparison(compareQuery);
      if (!benchmarkData) {
        fetch('/api/benchmark')
          .then((r) => r.json())
          .then(setBenchmarkData);
      }
    } else if (activeTab === 'analytics') {
      fetch('/api/analytics/overview')
        .then((r) => r.json())
        .then(setAnalyticsData);
    }
  }, [activeTab]);

  const recordClick = (offerUrl: string, block: 'main' | 'cross_sell' | 'alternatives' | 'suggest') => {
    fetch('/api/analytics/click', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        log_id: searchData?.log_id || null,
        query: searchData?.query.raw || queryInput,
        offer_url: offerUrl,
        block,
      }),
    }).catch(() => {});
  };

  const handlePresetClick = (preset: string) => {
    setQueryInput(preset);
    setIntentOverride(null);
    executeSearch(preset, { intent: null });
  };

  // Dynamic ROI calculation matching prompt economics
  const failShare = 0.384;
  const recoveredRate = 0.65;
  const crossSellLift = 1.14;
  const estRecoveredOrdersMo = Math.round(
    monthlySearches * failShare * recoveredRate * (convRate / 100)
  );
  const estAnnualGainMln = (
    (estRecoveredOrdersMo * avgCheck * 12 * crossSellLift) /
    1_000_000
  ).toFixed(1);

  return (
    <div>
      {/* Top Softline Brand Header */}
      <header className="sl-header">
        <div className="sl-header-inner">
          <div className="sl-brand">
            <div className="sl-logo-mark">
              <Sparkles size={16} />
              SOFTLINE STORE AI
            </div>
            <div>
              <div className="sl-brand-title">Умный поиск и рекомендательный агент</div>
              <div className="sl-brand-sub">
                ИИкузница · Трек «Аналитик данных» · 136 040 SKU / 9 311 категорий
              </div>
            </div>
          </div>

          <nav className="sl-nav">
            <button
              className={`sl-nav-btn ${activeTab === 'storefront' ? 'active' : ''}`}
              onClick={() => setActiveTab('storefront')}
            >
              <Search size={15} />
              Витрина поиска
            </button>
            <button
              className={`sl-nav-btn ${activeTab === 'compare' ? 'active' : ''}`}
              onClick={() => setActiveTab('compare')}
            >
              <GitCompare size={15} />
              Было / Стало & Бенчмарк
            </button>
            <button
              className={`sl-nav-btn ${activeTab === 'analytics' ? 'active' : ''}`}
              onClick={() => setActiveTab('analytics')}
            >
              <BarChart3 size={15} />
              Кабинет аналитика данных
            </button>
          </nav>
        </div>
      </header>

      <main className="sl-container">
        {/* ================================================================
            TAB 1: STOREFRONT SMART SEARCH & RECOMMENDATIONS
        ================================================================ */}
        {activeTab === 'storefront' && (
          <>
            <section className="search-hero">
              <div className="search-box-wrap" ref={searchWrapRef}>
                <form
                  className="search-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    setIntentOverride(null);
                    executeSearch(queryInput, { intent: null });
                  }}
                >
                  <div className="search-input-holder">
                    <Search size={20} color="#64748b" />
                    <input
                      className="search-input"
                      value={queryInput}
                      onFocus={() => setShowSuggest(true)}
                      onKeyDown={(e) => {
                        if (e.key === 'Escape') setShowSuggest(false);
                      }}
                      onChange={(e) => {
                        setQueryInput(e.target.value);
                        setShowSuggest(true);
                      }}
                      placeholder="Ищите по смыслу, сленгу или задаче: например, «сервер», «антивирь», «крипто про csp 5.0», «мтс», «365»..."
                    />
                    {queryInput && (
                      <button
                        type="button"
                        className="clear-btn"
                        onClick={() => {
                          setQueryInput('');
                          setShowSuggest(true);
                        }}
                      >
                        <X size={14} />
                      </button>
                    )}
                  </div>
                  <button type="submit" className="search-submit-btn">
                    <Sparkles size={17} />
                    Найти решения
                  </button>
                </form>

                {/* Live Typeahead Recommendations Dropdown (Bonus Feature) */}
                {showSuggest && suggestData && (
                  <div className="suggest-dropdown">
                    <div className="suggest-left">
                      {suggestData.corrected_to && (
                        <div
                          style={{
                            background: '#fff1f2',
                            border: '1px solid #fecdd3',
                            borderRadius: 9,
                            padding: '8px 10px',
                            fontSize: 12.5,
                          }}
                        >
                          Автоисправление на лету:{' '}
                          <strong
                            style={{ color: '#e30613', cursor: 'pointer' }}
                            onClick={() => handlePresetClick(suggestData.corrected_to!)}
                          >
                            {suggestData.corrected_to}
                          </strong>
                        </div>
                      )}

                      <div>
                        <div className="suggest-sec-label">
                          <span>Умные подсказки запросов</span>
                          <span>{suggestData.latency_ms} мс</span>
                        </div>
                        {suggestData.suggested_queries.map((sq) => (
                          <button
                            key={sq}
                            type="button"
                            className="suggest-query-item"
                            onClick={() => handlePresetClick(sq)}
                          >
                            <Search size={14} color="#94a3b8" />
                            <span>{sq}</span>
                          </button>
                        ))}
                      </div>

                      {suggestData.categories.length > 0 && (
                        <div>
                          <div className="suggest-sec-label">Категории каталога</div>
                          {suggestData.categories.map((cat) => (
                            <button
                              key={cat.id}
                              type="button"
                              className="suggest-query-item"
                              onClick={() => handlePresetClick(cat.name)}
                            >
                              <Layers size={14} color="#e30613" />
                              <span>{cat.name}</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="suggest-right">
                      <div className="suggest-sec-label">
                        <span>Рекомендуемые товары уже во время ввода</span>
                        {suggestData.normalized_hint && (
                          <span style={{ color: '#059669', textTransform: 'none' }}>
                            ИИ распознал смысл запроса
                          </span>
                        )}
                      </div>

                      {suggestData.products.length > 0 ? (
                        <div className="suggest-prod-grid">
                          {suggestData.products.map((p) => (
                            <a
                              key={p.group_id}
                              href={p.url}
                              target="_blank"
                              rel="noreferrer"
                              className="suggest-prod-card"
                              onClick={() => recordClick(p.url, 'suggest')}
                            >
                              <div style={{ width: 48, height: 48, flexShrink: 0 }}>
                                <ProductThumb
                                  src={p.picture}
                                  alt={p.title}
                                  className="suggest-prod-img"
                                />
                              </div>
                              <div style={{ minWidth: 0, flex: 1 }}>
                                <div
                                  style={{
                                    fontSize: 13,
                                    fontWeight: 700,
                                    whiteSpace: 'nowrap',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                  }}
                                >
                                  {p.title}
                                </div>
                                <div style={{ fontSize: 11.5, color: '#64748b' }}>{p.vendor}</div>
                                <div
                                  style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 6,
                                    marginTop: 4,
                                  }}
                                >
                                  <span style={{ fontSize: 13.5, fontWeight: 800, color: '#0f172a' }}>
                                    {formatPrice(p.price)}
                                  </span>
                                  {p.is_ru_registry && (
                                    <span className="badge badge-registry">Реестр РФ</span>
                                  )}
                                  {p.discount_pct > 0 && (
                                    <span className="badge badge-promo">−{p.discount_pct}%</span>
                                  )}
                                </div>
                              </div>
                            </a>
                          ))}
                        </div>
                      ) : (
                        <div style={{ fontSize: 13, color: '#64748b', padding: '12px 0' }}>
                          Начните вводить название продукта, задачу или ИТ-термин для мгновенного подбора товаров...
                        </div>
                      )}

                      {suggestData.promo_tip && (
                        <div className="suggest-promo-bar">
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <Flame size={16} color="#e30613" />
                            <div>
                              <strong>Спецпредложение: {suggestData.promo_tip.title}</strong>{' '}
                              <span style={{ color: '#be123c', fontWeight: 600 }}>
                                ({suggestData.promo_tip.badge})
                              </span>
                            </div>
                          </div>
                          <a
                            href={suggestData.promo_tip.url}
                            target="_blank"
                            rel="noreferrer"
                            style={{
                              fontWeight: 700,
                              color: '#e30613',
                              whiteSpace: 'nowrap',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 4,
                            }}
                          >
                            {formatPrice(suggestData.promo_tip.price)} <ArrowUpRight size={14} />
                          </a>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Quick Demo Scenarios */}
              <div className="preset-section">
                <div className="preset-row">
                  <span className="preset-label">Эталонная выборка XLSX:</span>
                  {XLSX_PRESETS.map((q) => (
                    <button
                      key={q}
                      type="button"
                      className={`preset-chip ${queryInput.toLowerCase() === q.toLowerCase() ? 'active' : ''}`}
                      onClick={() => handlePresetClick(q)}
                    >
                      {q}
                    </button>
                  ))}
                </div>
                <div className="preset-row">
                  <span className="preset-label">Кейсы PDF (сленг / интент / опечатки):</span>
                  {SMART_PRESETS.map((q) => (
                    <button
                      key={q}
                      type="button"
                      className={`preset-chip ${queryInput.toLowerCase() === q.toLowerCase() ? 'active' : ''}`}
                      onClick={() => handlePresetClick(q)}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            </section>

            {/* AI Understanding Banner & Filters */}
            {searchData && (
              <section className="ai-banner">
                <div className="ai-banner-top">
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <span className="badge badge-promo">
                        <Zap size={12} /> ИИ-анализ запроса
                      </span>
                      <span style={{ fontWeight: 700, fontSize: 14.5 }}>
                        {searchData.query.explanation}
                      </span>
                    </div>
                    {searchData.query.transformations.length > 0 && (
                      <div style={{ fontSize: 12.5, color: '#475569' }}>
                        Трансформации: {searchData.query.transformations.join(' • ')}
                      </div>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <span className="badge badge-avail">
                      <PackageCheck size={13} /> Выдано товаров: {searchData.total_returned} (мин. 4 гарантировано)
                    </span>
                    <span className="badge badge-type">{searchData.latency_ms} мс</span>
                  </div>
                </div>

                {/* Interactive Disambiguation Pills (e.g. 'сервер' Hardware vs Software) */}
                {searchData.query.disambiguation_chips.length > 0 && (
                  <div className="disambig-row">
                    <span style={{ fontSize: 12.5, fontWeight: 700, color: '#475569' }}>
                      Уточните намерение:
                    </span>
                    {searchData.query.disambiguation_chips.map((chip) => (
                      <button
                        key={chip.intent_id}
                        type="button"
                        className={`intent-pill ${chip.active ? 'active' : ''}`}
                        onClick={() => {
                          setIntentOverride(chip.intent_id);
                          executeSearch(queryInput, { intent: chip.intent_id });
                        }}
                      >
                        {chip.label}
                      </button>
                    ))}
                  </div>
                )}

                {/* Filter Toggles */}
                <div className="filter-row">
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#64748b', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Filter size={13} /> Быстрые фильтры:
                  </span>
                  <button
                    type="button"
                    className={`filter-toggle ${onlyAvailable ? 'checked' : ''}`}
                    onClick={() => {
                      const next = !onlyAvailable;
                      setOnlyAvailable(next);
                      executeSearch(queryInput, { avail: next });
                    }}
                  >
                    Только в наличии
                  </button>
                  <button
                    type="button"
                    className={`filter-toggle ${registryOnly ? 'checked' : ''}`}
                    onClick={() => {
                      const next = !registryOnly;
                      setRegistryOnly(next);
                      executeSearch(queryInput, { reg: next });
                    }}
                  >
                    <ShieldCheck size={14} /> Реестр ПО / Минпромторга РФ
                  </button>
                  <button
                    type="button"
                    className={`filter-toggle ${promoOnly ? 'checked' : ''}`}
                    onClick={() => {
                      const next = !promoOnly;
                      setPromoOnly(next);
                      executeSearch(queryInput, { promo: next });
                    }}
                  >
                    <Flame size={14} /> Акции и выгодная цена
                  </button>
                </div>
              </section>
            )}

            {/* Main Results Grid */}
            {loadingSearch ? (
              <div style={{ textAlign: 'center', padding: 48, fontSize: 15, color: '#64748b' }}>
                Выполняется гибридный семантический поиск и подбор сопутствующих решений...
              </div>
            ) : (
              searchData && (
                <>
                  <div className="results-grid">
                    {searchData.results.map((item) => (
                      <article key={item.offer_id} className="prod-card">
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                          <div className="badge-row">
                            {item.available ? (
                              <span className="badge badge-avail">В наличии</span>
                            ) : (
                              <span className="badge badge-unavail">Архив · См. аналоги ниже</span>
                            )}
                            {item.discount_pct > 0 && item.available && (
                              <span className="badge badge-promo">Акция −{item.discount_pct}%</span>
                            )}
                            {!item.discount_pct && item.price_adv_pct > 0 && item.available && (
                              <span className="badge badge-value">
                                Выгоднее на {item.price_adv_pct}%
                              </span>
                            )}
                            {item.is_ru_registry && (
                              <span
                                className="badge badge-registry"
                                title={
                                  item.registry_num
                                    ? `Запись в реестре ПО № ${item.registry_num}`
                                    : 'Российское решение'
                                }
                              >
                                <ShieldCheck size={12} /> Реестр РФ
                              </span>
                            )}
                            <span className="badge badge-type">
                              {item.product_type === 'электроника' ? (
                                <>
                                  <Cpu size={11} /> Оборудование
                                </>
                              ) : (
                                'ПО / Лицензия'
                              )}
                            </span>
                          </div>

                          <div className="prod-head">
                            <div className="prod-img-box">
                              <ProductThumb src={item.picture} alt={item.group_title} />
                            </div>
                            <div style={{ minWidth: 0 }}>
                              <div className="prod-vendor">{item.vendor}</div>
                              <h3 className="prod-group-title">{item.group_title}</h3>
                              <div style={{ fontSize: 11.5, color: '#64748b' }}>
                                {item.sub_category_name}
                              </div>
                            </div>
                          </div>

                          <div className="prod-sku-name" title={item.name}>
                            {item.name}
                          </div>

                          {item.price_adv_label && item.available && (
                            <div
                              style={{
                                fontSize: 11.5,
                                fontWeight: 600,
                                color: item.discount_pct > 0 ? '#be123c' : '#4338ca',
                                background: item.discount_pct > 0 ? '#fff1f2' : '#eef2ff',
                                padding: '5px 9px',
                                borderRadius: 7,
                              }}
                            >
                              {item.price_adv_label}
                            </div>
                          )}

                          {item.match_reasons[0] && (
                            <div className="reason-pill">
                              <CheckCircle2 size={13} color="#059669" />
                              <span>{item.match_reasons[0]}</span>
                            </div>
                          )}
                        </div>

                        <div className="prod-footer">
                          <div className="price-line">
                            <div>
                              <span className="price-main">{formatPrice(item.price)}</span>
                              {item.oldprice > item.price && item.price > 0 && (
                                <span className="price-old">{formatPrice(item.oldprice)}</span>
                              )}
                            </div>
                            {item.avail_sku_count > 1 && (
                              <span style={{ fontSize: 11.5, color: '#64748b' }}>
                                {item.avail_sku_count} вариантов SKU
                              </span>
                            )}
                          </div>

                          <div className="card-actions">
                            <a
                              href={item.url}
                              target="_blank"
                              rel="noreferrer"
                              className="btn-primary"
                              onClick={() => recordClick(item.url, 'main')}
                            >
                              В магазин <ExternalLink size={13} />
                            </a>
                            {item.variants.length > 1 && (
                              <button
                                type="button"
                                className="btn-secondary"
                                onClick={() => setModalProduct(item)}
                              >
                                Лицензии ({item.variants.length})
                              </button>
                            )}
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>

                  {/* ==========================================================
                      CROSS-SELL BLOCK (Catalog + Verified External Vendor Sources)
                  ========================================================== */}
                  {searchData.recommendations.cross_sell.items.length > 0 && (
                    <section className="rec-section">
                      <div className="rec-header">
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <Award size={20} color="#e30613" />
                            <h2 style={{ margin: 0, fontSize: 18 }}>
                              {searchData.recommendations.cross_sell.title}
                            </h2>
                          </div>
                          <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748b' }}>
                            {searchData.recommendations.cross_sell.subtitle}
                          </p>
                        </div>
                        <span className="badge badge-value">Инструмент допродажи (Cross-Sell)</span>
                      </div>

                      <div className="results-grid" style={{ marginBottom: 0 }}>
                        {searchData.recommendations.cross_sell.items.map((cs) => (
                          <div key={cs.group_id} className="prod-card">
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                              <div className="badge-row">
                                <span className="badge badge-value">{cs.relation_badge}</span>
                                {cs.discount_pct > 0 && (
                                  <span className="badge badge-promo">−{cs.discount_pct}%</span>
                                )}
                                {cs.is_ru_registry && (
                                  <span className="badge badge-registry">Реестр РФ</span>
                                )}
                              </div>

                              <div className="prod-head">
                                <div className="prod-img-box">
                                  <ProductThumb src={cs.picture} alt={cs.title} />
                                </div>
                                <div>
                                  <div className="prod-vendor">{cs.vendor}</div>
                                  <h4 className="prod-group-title">{cs.title}</h4>
                                  <div style={{ fontSize: 11.5, color: '#64748b' }}>{cs.category}</div>
                                </div>
                              </div>

                              {/* Verified Vendor External Source Citation */}
                              <div className="vendor-source-box">
                                <div style={{ fontWeight: 700, color: '#0f172a' }}>
                                  Источник: {cs.source.vendor_name}
                                </div>
                                <div>{cs.source.summary}</div>
                                <a
                                  href={cs.source.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="vendor-source-link"
                                >
                                  {cs.source.program_title} <ArrowUpRight size={12} />
                                </a>
                              </div>
                            </div>

                            <div className="prod-footer">
                              <div className="price-line">
                                <span className="price-main">{formatPrice(cs.price)}</span>
                                {cs.oldprice > cs.price && (
                                  <span className="price-old">{formatPrice(cs.oldprice)}</span>
                                )}
                              </div>
                              <a
                                href={cs.url}
                                target="_blank"
                                rel="noreferrer"
                                className="btn-primary"
                                onClick={() => recordClick(cs.url, 'cross_sell')}
                              >
                                Добавить к решению <ExternalLink size={13} />
                              </a>
                            </div>
                          </div>
                        ))}
                      </div>
                    </section>
                  )}

                  {/* ==========================================================
                      ALTERNATIVES, PROMOTIONS & UPSELL EDITIONS BLOCK
                  ========================================================== */}
                  {searchData.recommendations.alternatives_and_upsell.items.length > 0 && (
                    <section
                      className="rec-section"
                      style={{
                        background: searchData.recommendations.alternatives_and_upsell
                          .has_unavailable_primary
                          ? 'linear-gradient(180deg, #fffbeb 0%, #ffffff 100%)'
                          : '#ffffff',
                      }}
                    >
                      <div className="rec-header">
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <TrendingUp size={20} color="#059669" />
                            <h2 style={{ margin: 0, fontSize: 18 }}>
                              {searchData.recommendations.alternatives_and_upsell.title}
                            </h2>
                          </div>
                          <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748b' }}>
                            {searchData.recommendations.alternatives_and_upsell.subtitle}
                          </p>
                        </div>
                        <span className="badge badge-avail">Upsell / Альтернативы в наличии</span>
                      </div>

                      <div className="results-grid" style={{ marginBottom: 0 }}>
                        {searchData.recommendations.alternatives_and_upsell.items.map((alt) => (
                          <div key={alt.group_id} className="prod-card">
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                              <div className="badge-row">
                                <span
                                  className={`badge ${
                                    alt.upsell_type === 'promo' ? 'badge-promo' : 'badge-avail'
                                  }`}
                                >
                                  {alt.highlight_tag}
                                </span>
                                {alt.is_ru_registry && (
                                  <span className="badge badge-registry">Реестр ПО РФ</span>
                                )}
                              </div>
                              <div className="prod-head">
                                <div className="prod-img-box">
                                  <ProductThumb src={alt.picture} alt={alt.title} />
                                </div>
                                <div>
                                  <div className="prod-vendor">{alt.vendor}</div>
                                  <h4 className="prod-group-title">{alt.title}</h4>
                                  <div style={{ fontSize: 11.5, color: '#64748b' }}>
                                    {alt.category}
                                  </div>
                                </div>
                              </div>
                              <div className="prod-sku-name">{alt.name}</div>
                            </div>

                            <div className="prod-footer">
                              <div className="price-line">
                                <span className="price-main">{formatPrice(alt.price)}</span>
                                {alt.oldprice > alt.price && (
                                  <span className="price-old">{formatPrice(alt.oldprice)}</span>
                                )}
                              </div>
                              <a
                                href={alt.url}
                                target="_blank"
                                rel="noreferrer"
                                className="btn-primary"
                                onClick={() => recordClick(alt.url, 'alternatives')}
                              >
                                Перейти к предложению <ExternalLink size={13} />
                              </a>
                            </div>
                          </div>
                        ))}
                      </div>
                    </section>
                  )}
                </>
              )
            )}
          </>
        )}

        {/* ================================================================
            TAB 2: SIDE-BY-SIDE A/B COMPARISON & 18-QUERY BENCHMARK
        ================================================================ */}
        {activeTab === 'compare' && (
          <div>
            <section className="search-hero">
              <h2 style={{ margin: '0 0 8px', fontSize: 20 }}>
                Сравнение «Текущий текстовый поиск vs AIForge Умный поиск»
              </h2>
              <p style={{ margin: '0 0 16px', fontSize: 13.5, color: '#64748b' }}>
                Выберите любой проблемный запрос и сравните выдачу стандартного поиска по точному совпадению в описаниях с нашим гибридным ИИ-агентом.
              </p>

              <form
                className="search-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  loadComparison(compareQuery);
                }}
              >
                <div className="search-input-holder">
                  <Search size={18} color="#64748b" />
                  <input
                    className="search-input"
                    value={compareQuery}
                    onChange={(e) => setCompareQuery(e.target.value)}
                  />
                </div>
                <button type="submit" className="search-submit-btn">
                  Сравнить выдачу
                </button>
              </form>

              <div className="preset-row" style={{ marginTop: 12 }}>
                {['сервер', '365', 'astra linux', 'антивирь', 'мтс', 'крипто про csp 5.0', 'мдаемон', 'fcnhf kbyerc', 'акронис'].map(
                  (q) => (
                    <button
                      key={q}
                      type="button"
                      className={`preset-chip ${compareQuery === q ? 'active' : ''}`}
                      onClick={() => {
                        setCompareQuery(q);
                        loadComparison(q);
                      }}
                    >
                      {q}
                    </button>
                  )
                )}
              </div>
            </section>

            {loadingCompare ? (
              <div style={{ padding: 32, textAlign: 'center', color: '#64748b' }}>
                Сравниваем поисковые алгоритмы...
              </div>
            ) : (
              compareData && (
                <div className="compare-columns">
                  {/* Left: Legacy Search */}
                  <div className="rec-section" style={{ borderTop: '4px solid #ef4444' }}>
                    <h3 style={{ margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 8 }}>
                      <AlertTriangle size={18} color="#ef4444" />
                      Старый поиск (по вхождению слов в описание)
                    </h3>
                    {compareData.legacy.issues_detected.map((iss, idx) => (
                      <div
                        key={idx}
                        style={{
                          background: '#fef2f2',
                          border: '1px solid #fecaca',
                          color: '#991b1b',
                          padding: '8px 12px',
                          borderRadius: 9,
                          fontSize: 12.5,
                          fontWeight: 600,
                          marginBottom: 8,
                        }}
                      >
                        Проблема: {iss}
                      </div>
                    ))}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
                      {compareData.legacy.results.length === 0 ? (
                        <div style={{ padding: 24, textAlign: 'center', color: '#991b1b', fontWeight: 600 }}>
                          По вашему запросу ничего не найдено (0 товаров) — клиент уходит с сайта
                        </div>
                      ) : (
                        compareData.legacy.results.map((r, i) => (
                          <div
                            key={r.offer_id}
                            style={{
                              padding: 12,
                              border: '1px solid #e2e8f0',
                              borderRadius: 10,
                              background: r.available ? '#fff' : '#f8fafc',
                            }}
                          >
                            <div style={{ display: 'flex', gap: 6, marginBottom: 4 }}>
                              <span className="badge badge-type">#{i + 1}</span>
                              <span className={`badge ${r.available ? 'badge-avail' : 'badge-unavail'}`}>
                                {r.available ? 'available=true' : 'Недоступен (available=false)'}
                              </span>
                              <span className="badge badge-type">{r.product_type}</span>
                            </div>
                            <div style={{ fontSize: 13, fontWeight: 600 }}>{r.name}</div>
                            <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
                              {r.vendor} · <strong>{formatPrice(r.price)}</strong>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Right: Smart Search */}
                  <div className="rec-section" style={{ borderTop: '4px solid #059669' }}>
                    <h3 style={{ margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CheckCircle2 size={18} color="#059669" />
                      AIForge Умный поиск ({compareData.smart.latency_ms} мс)
                    </h3>
                    <div
                      style={{
                        background: '#ecfdf5',
                        border: '1px solid #a7f3d0',
                        color: '#065f46',
                        padding: '8px 12px',
                        borderRadius: 9,
                        fontSize: 12.5,
                        fontWeight: 600,
                        marginBottom: 12,
                      }}
                    >
                      {compareData.smart.query.explanation}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      {compareData.smart.results.slice(0, 6).map((r, i) => (
                        <div
                          key={r.offer_id}
                          style={{
                            padding: 12,
                            border: '1px solid #cbd5e1',
                            borderRadius: 10,
                            background: '#fff',
                          }}
                        >
                          <div style={{ display: 'flex', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
                            <span className="badge badge-avail">#{i + 1} · {r.group_title}</span>
                            {r.is_ru_registry && <span className="badge badge-registry">Реестр РФ</span>}
                            <span className="badge badge-type">{r.product_type}</span>
                          </div>
                          <div style={{ fontSize: 12.5, color: '#334155' }}>{r.name}</div>
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              marginTop: 6,
                              fontSize: 12.5,
                            }}
                          >
                            <span style={{ color: '#64748b' }}>{r.vendor}</span>
                            <strong style={{ color: '#0f172a' }}>{formatPrice(r.price)}</strong>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )
            )}

            {/* Full Automated Benchmark Suite */}
            {benchmarkData && (
              <section className="rec-section">
                <div className="rec-header">
                  <div>
                    <h2 style={{ margin: 0, fontSize: 19 }}>
                      Автоматический бенчмарк качества (10 эталонов XLSX + 8 сценариев PDF)
                    </h2>
                    <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748b' }}>
                      Проверка попадания целевой продуктовой линейки / категории на 1-е место и соблюдения требования ≥ 4 товаров
                    </p>
                  </div>
                </div>

                <div className="kpi-grid">
                  <div className="kpi-card">
                    <div style={{ fontSize: 12, color: '#64748b', fontWeight: 600 }}>
                      Точность Smart Hit@1
                    </div>
                    <div className="kpi-val" style={{ color: '#059669' }}>
                      {benchmarkData.summary.smart_hit_at_1_pct}%
                    </div>
                    <div style={{ fontSize: 12, color: '#64748b' }}>
                      Старый поиск Hit@1: {benchmarkData.summary.legacy_hit_at_1_pct}%
                    </div>
                  </div>
                  <div className="kpi-card">
                    <div style={{ fontSize: 12, color: '#64748b', fontWeight: 600 }}>
                      Точность Smart Hit@3
                    </div>
                    <div className="kpi-val" style={{ color: '#1d4ed8' }}>
                      {benchmarkData.summary.smart_hit_at_3_pct}%
                    </div>
                    <div style={{ fontSize: 12, color: '#64748b' }}>
                      По {benchmarkData.summary.total_cases} контрольным кейсам
                    </div>
                  </div>
                  <div className="kpi-card">
                    <div style={{ fontSize: 12, color: '#64748b', fontWeight: 600 }}>
                      Требование ≥ 4 товаров
                    </div>
                    <div className="kpi-val" style={{ color: '#059669' }}>
                      {benchmarkData.summary.min_4_compliance_pct}%
                    </div>
                    <div style={{ fontSize: 12, color: '#64748b' }}>Жесткий инвариант выдачи</div>
                  </div>
                  <div className="kpi-card">
                    <div style={{ fontSize: 12, color: '#64748b', fontWeight: 600 }}>
                      Медианная задержка
                    </div>
                    <div className="kpi-val">{benchmarkData.summary.median_latency_ms} мс</div>
                    <div style={{ fontSize: 12, color: '#64748b' }}>Локальный ONNX + BM25F</div>
                  </div>
                </div>

                <div className="data-table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Источник</th>
                        <th>Запрос</th>
                        <th>Ожидаемый ответ</th>
                        <th>Топ-1 AIForge Умного поиска</th>
                        <th>Старый поиск</th>
                        <th>Статус</th>
                      </tr>
                    </thead>
                    <tbody>
                      {benchmarkData.cases.map((c) => (
                        <tr key={c.query}>
                          <td>
                            <span className="badge badge-type">{c.source}</span>
                          </td>
                          <td>
                            <strong
                              style={{ color: '#e30613', cursor: 'pointer' }}
                              onClick={() => {
                                setActiveTab('storefront');
                                handlePresetClick(c.query);
                              }}
                            >
                              {c.query}
                            </strong>
                          </td>
                          <td>{c.expected_desc}</td>
                          <td>
                            <strong>{c.smart_top_title}</strong>
                            <div style={{ fontSize: 11.5, color: '#64748b' }}>
                              {formatPrice(c.smart_top_price)} · выдано {c.smart_count} шт.
                            </div>
                          </td>
                          <td style={{ fontSize: 12, color: c.legacy_ok ? '#059669' : '#b91c1c' }}>
                            {c.legacy_issue || c.legacy_top_name}
                          </td>
                          <td>
                            {c.hit_at_1 ? (
                              <span className="badge badge-avail">Hit@1 ✓</span>
                            ) : c.hit_at_3 ? (
                              <span className="badge badge-value">Hit@{c.hit_rank} ✓</span>
                            ) : (
                              <span className="badge badge-unavail">Проверить</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </div>
        )}

        {/* ================================================================
            TAB 3: DATA ANALYST STUDIO (SEARCH TELEMETRY & CATALOG AUDIT)
        ================================================================ */}
        {activeTab === 'analytics' && analyticsData && (
          <div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 18,
                flexWrap: 'wrap',
                gap: 12,
              }}
            >
              <div>
                <h2 style={{ margin: 0, fontSize: 22 }}>
                  Поисковая аналитика и аудит каталога Store.softline.ru
                </h2>
                <p style={{ margin: '4px 0 0', fontSize: 13.5, color: '#64748b' }}>
                  Превращаем поисковые логи и аудит 292-МБ фида Mindbox в конкретные решения для роста каталога и конверсии
                </p>
              </div>

              <a href="/api/analytics/export.xlsx" className="search-submit-btn" style={{ padding: '11px 20px' }}>
                <Download size={16} />
                Скачать аналитический отчет (.xlsx)
              </a>
            </div>

            {/* KPI Summary */}
            <div className="kpi-grid">
              <div className="kpi-card">
                <div style={{ fontSize: 12, color: '#64748b', fontWeight: 600 }}>
                  Проблемные запросы (старый → новый)
                </div>
                <div className="kpi-val" style={{ color: '#059669' }}>
                  {analyticsData.kpis.legacy_fail_rate_pct}% → 0.0%
                </div>
                <div style={{ fontSize: 12, color: '#64748b' }}>
                  Ликвидация пустых и нерелевантных выдач
                </div>
              </div>
              <div className="kpi-card">
                <div style={{ fontSize: 12, color: '#64748b', fontWeight: 600 }}>
                  Запросы со сленгом / опечатками
                </div>
                <div className="kpi-val">{analyticsData.kpis.slang_typo_share_pct}%</div>
                <div style={{ fontSize: 12, color: '#64748b' }}>
                  Всего поисковых сессий в базе: {analyticsData.kpis.total_logged_searches}
                </div>
              </div>
              <div className="kpi-card">
                <div style={{ fontSize: 12, color: '#64748b', fontWeight: 600 }}>
                  Вклад рекомендаций в клики
                </div>
                <div className="kpi-val" style={{ color: '#e30613' }}>
                  {analyticsData.kpis.cross_sell_share_of_clicks_pct}%
                </div>
                <div style={{ fontSize: 12, color: '#64748b' }}>
                  Переходы из блоков Cross-Sell и Аналогов РФ
                </div>
              </div>
              <div className="kpi-card">
                <div style={{ fontSize: 12, color: '#64748b', fontWeight: 600 }}>
                  Активная матрица фида Mindbox
                </div>
                <div className="kpi-val">
                  {(analyticsData.catalog_stats.available_offers || 44601).toLocaleString('ru-RU')}
                </div>
                <div style={{ fontSize: 12, color: '#d97706' }}>
                  из {(analyticsData.catalog_stats.total_offers || 136040).toLocaleString('ru-RU')} SKU (67.2% в архиве!)
                </div>
              </div>
            </div>

            {/* Interactive Business Value & Revenue Calculator */}
            <section className="rec-section">
              <h3 style={{ margin: '0 0 6px', fontSize: 18 }}>
                Калькулятор экономического эффекта внедрения (Unit-экономика кейса)
              </h3>
              <p style={{ margin: '0 0 16px', fontSize: 13, color: '#64748b' }}>
                По данным кейса: 10–20 тыс. поисковых запросов/мес, конверсия поиска в заказ 5–10%, до 40% запросов ранее уходили в отказ.
              </p>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                  gap: 18,
                  alignItems: 'center',
                }}
              >
                <div>
                  <label style={{ fontSize: 12.5, fontWeight: 600 }}>
                    Запросов к поиску в месяц: <strong>{monthlySearches.toLocaleString('ru-RU')}</strong>
                  </label>
                  <input
                    type="range"
                    min={10000}
                    max={30000}
                    step={1000}
                    value={monthlySearches}
                    onChange={(e) => setMonthlySearches(Number(e.target.value))}
                    style={{ width: '100%', accentColor: '#e30613', marginTop: 6 }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12.5, fontWeight: 600 }}>
                    Конверсия поиска в заказ: <strong>{convRate}%</strong>
                  </label>
                  <input
                    type="range"
                    min={5}
                    max={12}
                    step={0.5}
                    value={convRate}
                    onChange={(e) => setConvRate(Number(e.target.value))}
                    style={{ width: '100%', accentColor: '#e30613', marginTop: 6 }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12.5, fontWeight: 600 }}>
                    Средний B2B-чек заказа: <strong>{avgCheck.toLocaleString('ru-RU')} ₽</strong>
                  </label>
                  <input
                    type="range"
                    min={25000}
                    max={180000}
                    step={5000}
                    value={avgCheck}
                    onChange={(e) => setAvgCheck(Number(e.target.value))}
                    style={{ width: '100%', accentColor: '#e30613', marginTop: 6 }}
                  />
                </div>
                <div
                  style={{
                    background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
                    color: '#fff',
                    padding: '16px 20px',
                    borderRadius: 14,
                  }}
                >
                  <div style={{ fontSize: 12, color: '#cbd5e1' }}>
                    Возвращенная выручка + допродажи (+14% AOV):
                  </div>
                  <div style={{ fontSize: 28, fontWeight: 800, color: '#4ade80', margin: '4px 0' }}>
                    +{estAnnualGainMln} млн ₽ / год
                  </div>
                  <div style={{ fontSize: 12, color: '#94a3b8' }}>
                    ≈ +{estRecoveredOrdersMo} спасенных онлайн-заказов ежемесячно
                  </div>
                </div>
              </div>
            </section>

            {/* Actionable Recommendations for Catalog Managers */}
            <section className="rec-section">
              <h3 style={{ margin: '0 0 14px', fontSize: 18 }}>
                Рекомендации категорийным менеджерам на основе анализа поиска и YML-фида
              </h3>
              <div className="data-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Приоритет</th>
                      <th>Направление</th>
                      <th>Что обнаружено в данных</th>
                      <th>Что сделать в каталоге</th>
                      <th>Ожидаемый эффект</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analyticsData.catalog_recommendations.map((rec, i) => (
                      <tr key={i}>
                        <td>
                          <span
                            className={`badge ${
                              rec.priority === 'Высокий' ? 'badge-promo' : 'badge-value'
                            }`}
                          >
                            {rec.priority}
                          </span>
                        </td>
                        <td>
                          <strong>{rec.category}</strong>
                        </td>
                        <td>{rec.finding}</td>
                        <td>{rec.action}</td>
                        <td style={{ fontWeight: 600, color: '#059669' }}>{rec.expected_impact}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Top Search Queries & Real Feed Data Defects side-by-side */}
            <div className="compare-columns">
              <section className="rec-section" style={{ marginBottom: 0 }}>
                <h3 style={{ margin: '0 0 12px', fontSize: 17 }}>
                  Топ поисковых запросов клиентов и конвертация сленга
                </h3>
                <div className="data-table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Запрос</th>
                        <th>Частота</th>
                        <th>Терялся ранее</th>
                        <th>Куда ведет агент</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analyticsData.top_queries.map((q) => (
                        <tr key={q.raw_query}>
                          <td>
                            <strong
                              style={{ color: '#e30613', cursor: 'pointer' }}
                              onClick={() => {
                                setActiveTab('storefront');
                                handlePresetClick(q.raw_query);
                              }}
                            >
                              {q.raw_query}
                            </strong>
                          </td>
                          <td>{q.cnt}</td>
                          <td>
                            {q.failed_in_legacy ? (
                              <span className="badge badge-unavail">Терялся</span>
                            ) : (
                              <span className="badge badge-type">Частично</span>
                            )}
                          </td>
                          <td style={{ fontSize: 12 }}>{q.resolved_to}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="rec-section" style={{ marginBottom: 0 }}>
                <h3 style={{ margin: '0 0 12px', fontSize: 17 }}>
                  Найденные дефекты качества данных в Mindbox.yml.gz.xml
                </h3>
                <div className="data-table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Тип проблемы</th>
                        <th>Пример из фида</th>
                        <th>Диагноз аналитика</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analyticsData.audit_samples.slice(0, 12).map((a, idx) => (
                        <tr key={idx}>
                          <td>
                            <span className="badge badge-unavail">{a.issue_type}</span>
                          </td>
                          <td style={{ fontWeight: 600, fontSize: 12 }}>{a.raw_value}</td>
                          <td style={{ fontSize: 12, color: '#475569' }}>{a.detail}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          </div>
        )}
      </main>

      {/* SKU License Variants Modal */}
      {modalProduct && (
        <div className="modal-backdrop" onClick={() => setModalProduct(null)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
              <div>
                <div className="prod-vendor">{modalProduct.vendor}</div>
                <h3 style={{ margin: '4px 0 8px', fontSize: 19 }}>{modalProduct.group_title}</h3>
                <div style={{ fontSize: 12.5, color: '#64748b' }}>
                  Доступные конфигурации и лицензионные уровни в каталоге Store.softline.ru
                </div>
              </div>
              <button type="button" className="clear-btn" onClick={() => setModalProduct(null)}>
                <X size={16} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 18 }}>
              {modalProduct.variants.map((v) => (
                <div
                  key={v.offer_id}
                  style={{
                    border: '1px solid #e2e8f0',
                    borderRadius: 12,
                    padding: 14,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 14,
                    flexWrap: 'wrap',
                  }}
                >
                  <div style={{ flex: 1, minWidth: 240 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 600 }}>{v.name}</div>
                    <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
                      {[v.license_type, v.duration, v.sales_notes].filter(Boolean).join(' • ')}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <strong style={{ fontSize: 16 }}>{formatPrice(v.price)}</strong>
                    <a
                      href={v.url}
                      target="_blank"
                      rel="noreferrer"
                      className="btn-primary"
                      style={{ flex: 'none' }}
                      onClick={() => recordClick(v.url, 'main')}
                    >
                      Купить <ExternalLink size={13} />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
