import { useState } from "react";
import Card from "../Card";
import type { TopBrand, TopBrandsByPeriod } from "@/types/dashboard";

function brandLogoPath(name: string): string {
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
    return `${import.meta.env.BASE_URL}brands/${slug}.png`;
}

// --- Duration options ---

const durations = [
    { id: 1, name: "Month" },
    { id: 2, name: "6 months" },
    { id: 3, name: "Year" },
    { id: 4, name: "All time" },
];

const periodKey: Record<number, keyof TopBrandsByPeriod> = {
    1: "month",
    2: "6months",
    3: "year",
    4: "all",
};

// --- Brand row sub-component ---

const BrandLogo = ({ name }: { name: string }) => {
    const [failed, setFailed] = useState(false);
    if (failed) {
        return (
            <div className="shrink-0 flex items-center justify-center size-10 rounded-full bg-shade-09 text-caption font-semibold text-t-secondary">
                {name.slice(0, 2).toUpperCase()}
            </div>
        );
    }
    return (
        <img
            className="shrink-0 size-10 rounded-full object-cover bg-shade-09"
            src={brandLogoPath(name)}
            alt={name}
            onError={() => setFailed(true)}
        />
    );
};

const BrandItem = ({ brand, maxCount }: { brand: TopBrand; maxCount: number }) => {
    const pct = maxCount > 0 ? (brand.count / maxCount) * 100 : 0;
    return (
        <div className="flex items-center">
            <BrandLogo name={brand.brand} />
            <div className="grow pl-4 min-w-0">
                <div className="flex justify-between mb-2 text-sub-title-1">
                    <div className="truncate mr-2">{brand.brand}</div>
                    <div className="shrink-0 text-t-secondary">
                        {brand.count}
                    </div>
                </div>
                <div className="relative h-3 rounded-[2px] bg-shade-09">
                    <div
                        className="absolute top-0 left-0 bottom-0 rounded-[2px] bg-gradient-to-r from-[#E1E1E1] to-shade-07 opacity-30"
                        style={{ width: `${pct}%` }}
                    />
                </div>
            </div>
        </div>
    );
};

// --- Main component ---

type TopBrandsCardProps = {
    data?: TopBrandsByPeriod;
};

const CountriesCard = ({ data }: TopBrandsCardProps) => {
    const [duration, setDuration] = useState(durations[3]);

    const key = periodKey[duration.id] ?? "all";
    const brands = data?.[key] ?? [];
    const maxCount = brands.length > 0 ? brands[0].count : 0;

    return (
        <Card
            classHead="!pl-3"
            title="Top Brands"
            selectValue={duration}
            selectOnChange={setDuration}
            selectOptions={durations}
        >
            <div className="flex flex-col gap-5 p-3 pb-5">
                {brands.length > 0 ? (
                    brands.map((brand) => (
                        <BrandItem key={brand.brand} brand={brand} maxCount={maxCount} />
                    ))
                ) : (
                    <div className="text-body-2 text-t-secondary text-center py-4">
                        No brand data for this period
                    </div>
                )}
            </div>
        </Card>
    );
};

export default CountriesCard;
