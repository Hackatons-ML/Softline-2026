export interface DisambiguationChip {
  intent_id: string;
  label: string;
  active: boolean;
}

export interface ProductVariant {
  offer_id: string;
  name: string;
  price: number;
  oldprice: number;
  discount_pct: number;
  available: boolean;
  license_type: string;
  duration: string;
  nodes_cnt: string;
  sales_notes: string;
  url: string;
}

export interface ProductCard {
  offer_id: string;
  group_id: string;
  group_title: string;
  name: string;
  vendor: string;
  vendor_url: string;
  vendor_slug: string;
  category_id: string;
  root_category_name: string;
  sub_category_name: string;
  category_path: string;
  product_type: string;
  available: boolean;
  price: number;
  oldprice: number;
  min_group_price: number;
  max_group_price: number;
  total_sku_count: number;
  avail_sku_count: number;
  discount_pct: number;
  price_adv_pct: number;
  price_adv_label: string;
  is_ru_registry: boolean;
  registry_num: string;
  picture: string;
  url: string;
  license_type: string;
  duration: string;
  sales_notes: string;
  score: number;
  match_tier: string;
  match_reasons: string[];
  variants: ProductVariant[];
}

export interface VendorSource {
  vendor_name: string;
  program_title: string;
  url: string;
  summary: string;
}

export interface CrossSellItem {
  group_id: string;
  title: string;
  name: string;
  vendor: string;
  category: string;
  price: number;
  oldprice: number;
  discount_pct: number;
  price_adv_label: string;
  is_ru_registry: boolean;
  picture: string;
  url: string;
  relation_badge: string;
  source: VendorSource;
}

export interface AlternativeItem {
  group_id: string;
  title: string;
  name: string;
  vendor: string;
  category: string;
  price: number;
  oldprice: number;
  discount_pct: number;
  price_adv_label: string;
  is_ru_registry: boolean;
  registry_num: string;
  picture: string;
  url: string;
  upsell_type: string;
  highlight_tag: string;
}

export interface SearchResponse {
  query: {
    raw: string;
    normalized: string;
    detected_intent: string;
    is_server_ambiguous: boolean;
    transformations: string[];
    explanation: string;
    rule_id: string | null;
    import_substitution_category: string | null;
    disambiguation_chips: DisambiguationChip[];
  };
  results: ProductCard[];
  total_returned: number;
  latency_ms: number;
  log_id: number;
  recommendations: {
    cross_sell: {
      title: string;
      subtitle: string;
      items: CrossSellItem[];
    };
    alternatives_and_upsell: {
      title: string;
      subtitle: string;
      has_unavailable_primary: boolean;
      items: AlternativeItem[];
    };
  };
}

export interface SuggestResponse {
  prefix: string;
  normalized_hint: string;
  corrected_to?: string;
  suggested_queries: string[];
  categories: { id: string; name: string }[];
  products: {
    group_id: string;
    title: string;
    name: string;
    vendor: string;
    category: string;
    price: number;
    oldprice: number;
    discount_pct: number;
    price_adv_label: string;
    is_ru_registry: boolean;
    picture: string;
    url: string;
    reason: string;
  }[];
  promo_tip: {
    title: string;
    vendor: string;
    price: number;
    badge: string;
    url: string;
  } | null;
  latency_ms: number;
}

export interface CompareResponse {
  query: string;
  legacy: {
    results: {
      offer_id: string;
      name: string;
      vendor: string;
      available: boolean;
      price: number;
      product_type: string;
      url: string;
      picture: string;
    }[];
    total_returned: number;
    latency_ms: number;
    issues_detected: string[];
  };
  smart: SearchResponse;
}

export interface BenchmarkResponse {
  summary: {
    total_cases: number;
    xlsx_cases: number;
    smart_hit_at_1_pct: number;
    smart_hit_at_3_pct: number;
    legacy_hit_at_1_pct: number;
    min_4_compliance_pct: number;
    median_latency_ms: number;
  };
  cases: {
    query: string;
    source: string;
    expected_desc: string;
    target_url: string;
    smart_top_title: string;
    smart_top_name: string;
    smart_top_url: string;
    smart_top_price: number;
    smart_count: number;
    hit_rank: number | null;
    hit_at_1: boolean;
    hit_at_3: boolean;
    min_4_ok: boolean;
    legacy_ok: boolean;
    legacy_top_name: string;
    legacy_issue: string;
    latency_ms: number;
  }[];
}

export interface AnalyticsOverview {
  kpis: {
    total_logged_searches: number;
    legacy_fail_rate_pct: number;
    smart_zero_result_rate_pct: number;
    slang_typo_share_pct: number;
    avg_latency_ms: number;
    ctr_pct: number;
    cross_sell_share_of_clicks_pct: number;
  };
  business_effect: {
    monthly_search_volume: number;
    conversion_rate_pct: number;
    avg_order_value_rub: number;
    recovered_orders_per_month: number;
    estimated_annual_revenue_gain_rub: number;
    estimated_annual_revenue_gain_mln: number;
  };
  catalog_stats: Record<string, any>;
  audit_summary: Record<string, number>;
  audit_samples: {
    issue_type: string;
    entity_id: string;
    raw_value: string;
    detail: string;
  }[];
  top_queries: {
    raw_query: string;
    normalized_query: string;
    detected_intent: string;
    cnt: number;
    failed_in_legacy: number;
    resolved_to: string;
  }[];
  recent_logs: {
    id: number;
    created_at: string;
    raw_query: string;
    normalized_query: string;
    detected_intent: string;
    results_count: number;
    top_title: string;
    latency_ms: number;
    zero_in_legacy_search: number;
    clicked_block: string;
  }[];
  catalog_recommendations: {
    priority: string;
    category: string;
    finding: string;
    action: string;
    expected_impact: string;
  }[];
}
