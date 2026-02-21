export interface DashboardStats {
  total_transactions: number;
  total_properties: number;
  total_parties: number;
  properties_with_brands: number;
  brands_traded_current_month: number;
  brands_traded_last_month: number;
  geocoded_properties: number;
  properties_with_gw: number;
}

export interface YearCount {
  year: string;
  count: number;
}

export interface YearVolume {
  year: string;
  volume: number;
}

export interface MonthVolume {
  month: string;
  volume: number;
}

export interface MonthCount {
  month: string;
  count: number;
}

export interface CityCount {
  city: string;
  count: number;
  population: number | null;
}

export interface PriceRange {
  range: string;
  count: number;
}

export interface RecentTransaction {
  rt_id: string;
  address: string;
  city: string;
  sale_price: string;
  sale_date: string;
  buyer: string;
}

export interface LargestMonthlyTransaction {
  month: string;
  rt_id: string;
  address: string;
  city: string;
  sale_price: string;
}

export interface TopBrand {
  brand: string;
  count: number;
}

export interface TopBrandsByPeriod {
  month: TopBrand[];
  "6months": TopBrand[];
  year: TopBrand[];
  all: TopBrand[];
}

export interface DashboardData {
  stats: DashboardStats;
  transactions_by_year: YearCount[];
  volume_by_year: YearVolume[];
  volume_by_month: MonthVolume[];
  transactions_by_month: MonthCount[];
  top_cities: CityCount[];
  price_ranges: PriceRange[];
  recent_transactions: RecentTransaction[];
  largest_monthly: LargestMonthlyTransaction[];
  recently_sold_brands: string[];
  top_brand_12mo: TopBrand | null;
  top_brands_by_period: TopBrandsByPeriod;
}
