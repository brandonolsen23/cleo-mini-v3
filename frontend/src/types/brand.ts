export interface BrandStore {
  brand: string;
  store_name: string;
  address: string;
  city: string;
  province: string;
  postal_code: string;
  lat: number | null;
  lng: number | null;
  prop_id: string | null;
  has_transactions: boolean;
  transaction_count: number;
}
