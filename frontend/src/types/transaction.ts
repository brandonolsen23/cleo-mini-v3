export interface TransactionSummary {
  rt_id: string;
  address: string;
  city: string;
  municipality: string;
  population: number | null;
  sale_price: string;
  sale_date: string;
  sale_date_iso: string;
  seller: string;
  buyer: string;
  building_sf: string;
  ppsf: string | null;
  has_photos: boolean;
  brands: string[];
  _search_text: string;
}

export interface TransactionDetail {
  rt_id: string;
  skip_index: number;
  brands: string[];
  transaction: {
    address: {
      address: string;
      address_suite: string;
      city: string;
      municipality: string;
      province: string;
      postal_code: string;
      alternate_addresses: string[];
    };
    sale_date: string;
    sale_date_iso: string;
    sale_price: string;
    sale_price_raw: string;
    rt_number: string;
    arn: string;
    pins: string[];
  };
  transferor: PartyInfo;
  transferee: PartyInfo;
  site: {
    legal_description: string;
    site_area: string;
    site_area_units: string;
    site_frontage: string;
    site_frontage_units: string;
    site_depth: string;
    site_depth_units: string;
    zoning: string;
    pins: string[];
    arn: string;
  };
  consideration: {
    cash: string;
    assumed_debt: string;
    chattels: string;
    verbatim: string;
    chargees: string[];
  };
  broker: {
    brokerage: string;
    phone: string;
  };
  description: string;
  ppsf: string | null;
  photos: string[];
  export_extras: {
    postal_code: string;
    building_sf: string;
    additional_fields: Record<string, string>;
  };
}

export interface PartyInfo {
  name: string;
  contact: string;
  phone: string;
  address: string;
  alternate_names: string[];
  company_lines: string[];
  contact_lines: string[];
  address_lines: string[];
  phones: string[];
  officer_titles: string[];
  aliases: string[];
  attention: string;
}
