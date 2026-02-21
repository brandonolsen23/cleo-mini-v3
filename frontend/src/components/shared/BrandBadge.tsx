export type Category =
  | "grocery"
  | "bigbox"
  | "discount"
  | "specialty"
  | "qsr"
  | "fullservice"
  | "takeout"
  | "fuel"
  | "financial"
  | "automotive";

export const CATEGORY_LABELS: Record<Category, string> = {
  grocery: "Grocery",
  bigbox: "Big-Box Retail",
  discount: "Discount Retail",
  specialty: "Specialty Retail",
  qsr: "QSR",
  fullservice: "Full-Service",
  takeout: "Takeout",
  fuel: "Fuel",
  financial: "Financial",
  automotive: "Automotive",
};

// Soft Rainbow palette mapped to categories
export const CATEGORY_COLORS: Record<Category, string> = {
  grocery:     "bg-[#98F5E1] text-[#065F46]",  // mint
  qsr:         "bg-[#FDE4CF] text-[#92400E]",  // peach
  fullservice: "bg-[#F1C0E8] text-[#831843]",  // mauve
  takeout:     "bg-[#FBF8CC] text-[#713F12]",  // pale yellow
  bigbox:      "bg-[#A3C4F3] text-[#1E3A5F]",  // light blue
  discount:    "bg-[#FFCFD2] text-[#9F1239]",  // pink
  specialty:   "bg-[#CFBAF0] text-[#4C1D95]",  // lavender
  fuel:        "bg-[#90DBF4] text-[#0C4A6E]",  // sky blue
  financial:   "bg-[#B9FBC0] text-[#14532D]",  // light green
  automotive:  "bg-[#8ECEF5] text-[#164E63]",  // cyan
};

export const BRAND_CATEGORY: Record<string, Category> = {
  // Grocery (17)
  Loblaws: "grocery",
  "No Frills": "grocery",
  "Real Canadian Superstore": "grocery",
  "Shoppers Drug Mart": "grocery",
  Zehrs: "grocery",
  Fortinos: "grocery",
  "Wholesale Club": "grocery",
  Sobeys: "grocery",
  FreshCo: "grocery",
  Foodland: "grocery",
  "Longo's": "grocery",
  Safeway: "grocery",
  Metro: "grocery",
  "Food Basics": "grocery",
  "Valu-Mart": "grocery",
  "Your Independent Grocer": "grocery",
  "Farm Boy": "grocery",
  // Big-Box Retail (4)
  Walmart: "bigbox",
  "Canadian Tire": "bigbox",
  "Home Depot": "bigbox",
  Costco: "bigbox",
  // Discount Retail (4)
  "Giant Tiger": "discount",
  Dollarama: "discount",
  "Dollar Tree": "discount",
  Goodwill: "discount",
  // Specialty Retail (13)
  "Best Buy": "specialty",
  Staples: "specialty",
  JYSK: "specialty",
  HomeSense: "specialty",
  PetSmart: "specialty",
  "Sport Chek": "specialty",
  "Tepperman's": "specialty",
  LCBO: "specialty",
  "Toys R Us": "specialty",
  Indigo: "specialty",
  "Rens Pets": "specialty",
  "The Brick": "specialty",
  Starbucks: "specialty",
  // QSR (11)
  "Harvey's": "qsr",
  "Swiss Chalet": "qsr",
  "McDonald's": "qsr",
  "A&W": "qsr",
  "Wendy's": "qsr",
  "Burger King": "qsr",
  "Tim Hortons": "qsr",
  "Mary Brown's": "qsr",
  Popeyes: "qsr",
  "Dairy Queen": "qsr",
  "Taco Bell": "qsr",
  // Full-Service (9)
  Kelseys: "fullservice",
  "Montana's": "fullservice",
  "East Side Mario's": "fullservice",
  "Boston Pizza": "fullservice",
  Chipotle: "fullservice",
  "Five Guys": "fullservice",
  "St. Louis Bar & Grill": "fullservice",
  "Sunset Grill": "fullservice",
  "Wild Wing": "fullservice",
  // Takeout / Fast Casual (9)
  Subway: "takeout",
  "Mr. Sub": "takeout",
  "Mucho Burrito": "takeout",
  "Papa John's": "takeout",
  "Firehouse Subs": "takeout",
  "Pita Pit": "takeout",
  "Domino's": "takeout",
  "Pizza Pizza": "takeout",
  "Pizza Hut": "takeout",
  // Fuel (4)
  Esso: "fuel",
  Mobil: "fuel",
  Pioneer: "fuel",
  Ultramar: "fuel",
  // Automotive (21)
  Toyota: "automotive",
  Lexus: "automotive",
  Honda: "automotive",
  Acura: "automotive",
  Nissan: "automotive",
  Infiniti: "automotive",
  Kia: "automotive",
  Hyundai: "automotive",
  Volvo: "automotive",
  Chrysler: "automotive",
  Ford: "automotive",
  GMC: "automotive",
  "Mercedes-Benz": "automotive",
  Porsche: "automotive",
  "Land Rover": "automotive",
  Volkswagen: "automotive",
  Audi: "automotive",
  BMW: "automotive",
  Jaguar: "automotive",
  Mazda: "automotive",
  Mitsubishi: "automotive",
};

const FALLBACK = "bg-[#E5E7EB] text-[#374151]";

export default function BrandBadge({ brand }: { brand: string }) {
  const category = BRAND_CATEGORY[brand];
  const color = category ? CATEGORY_COLORS[category] : FALLBACK;
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${color}`}>
      {brand}
    </span>
  );
}
