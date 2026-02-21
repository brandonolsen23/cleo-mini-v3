import { useState } from "react";
import { NumericFormat } from "react-number-format";
import Checkbox from "../Checkbox";
import Search from "../Search";
import Percentage from "../Percentage";
import Image from "../Image";

// --- Types ---

interface ProductMarket {
    id: number;
    title: string;
    image: string;
    details: string;
    active: boolean;
    price: number;
    sales: { value: number; percentage: number };
    views: { value: string; percentage: number };
    likes: { value: string; percentage: number };
}

// --- Mock data (exact match from Core 2 template) ---

const products: ProductMarket[] = [
    {
        id: 1,
        title: "Bento Matte 3D Illustration",
        image: "https://picsum.photos/seed/prod1/128/128",
        details: "UI Design Kit",
        active: true,
        price: 98,
        sales: { value: 3200, percentage: 36.8 },
        views: { value: "48m", percentage: 50 },
        likes: { value: "480", percentage: 70 },
    },
    {
        id: 2,
        title: "Cryper \u2013 NFT UI Design Kit",
        image: "https://picsum.photos/seed/prod2/128/128",
        details: "Illustrations",
        active: true,
        price: 98,
        sales: { value: 1234, percentage: 22.5 },
        views: { value: "12k", percentage: 30 },
        likes: { value: "320", percentage: 50 },
    },
    {
        id: 3,
        title: "Fleet - travel shopping kit",
        image: "https://picsum.photos/seed/prod3/128/128",
        details: "3D assets",
        active: true,
        price: 59.5,
        sales: { value: 6200, percentage: -15.9 },
        views: { value: "1m", percentage: 70 },
        likes: { value: "320", percentage: 80 },
    },
    {
        id: 4,
        title: "Bento Matte 3D Illustration",
        image: "https://picsum.photos/seed/prod4/128/128",
        details: "UI Design Kit",
        active: false,
        price: 98,
        sales: { value: 3200, percentage: 36.8 },
        views: { value: "48m", percentage: 50 },
        likes: { value: "480", percentage: 70 },
    },
    {
        id: 5,
        title: "Cryper \u2013 NFT UI Design Kit",
        image: "https://picsum.photos/seed/prod5/128/128",
        details: "UI Design Kit",
        active: true,
        price: 98,
        sales: { value: 1234, percentage: 22.5 },
        views: { value: "12k", percentage: 30 },
        likes: { value: "320", percentage: 50 },
    },
    {
        id: 6,
        title: "Fleet - travel shopping kit",
        image: "https://picsum.photos/seed/prod6/128/128",
        details: "3D assets",
        active: true,
        price: 59.5,
        sales: { value: 6200, percentage: -15.9 },
        views: { value: "1m", percentage: 70 },
        likes: { value: "320", percentage: 80 },
    },
    {
        id: 7,
        title: "Bento Matte 3D Illustration",
        image: "https://picsum.photos/seed/prod7/128/128",
        details: "UI Design Kit",
        active: false,
        price: 98,
        sales: { value: 3200, percentage: 36.8 },
        views: { value: "48m", percentage: 50 },
        likes: { value: "480", percentage: 70 },
    },
    {
        id: 8,
        title: "Cryper \u2013 NFT UI Design Kit",
        image: "https://picsum.photos/seed/prod8/128/128",
        details: "Illustrations",
        active: true,
        price: 98,
        sales: { value: 1234, percentage: 22.5 },
        views: { value: "12k", percentage: 30 },
        likes: { value: "320", percentage: 50 },
    },
    {
        id: 9,
        title: "Fleet - travel shopping kit",
        image: "https://picsum.photos/seed/prod9/128/128",
        details: "UI Design Kit",
        active: true,
        price: 59.5,
        sales: { value: 6200, percentage: -15.9 },
        views: { value: "1m", percentage: 70 },
        likes: { value: "320", percentage: 80 },
    },
    {
        id: 10,
        title: "Bento Matte 3D Illustration",
        image: "https://picsum.photos/seed/prod10/128/128",
        details: "UI Design Kit",
        active: false,
        price: 98,
        sales: { value: 3200, percentage: 36.8 },
        views: { value: "48m", percentage: 50 },
        likes: { value: "480", percentage: 70 },
    },
];

// --- Tab categories ---

const categories = [
    { id: "market", name: "Market" },
    { id: "traffic", name: "Traffic sources" },
    { id: "viewers", name: "Viewers" },
];

// --- Table column headers ---

const tableHead = ["Product", "Status", "Price", "Sales", "Views", "Like"];

// --- Sub-components ---

const ProgressCell = ({
    value,
    percentage,
}: {
    value: string;
    percentage: number;
}) => (
    <td>
        <div className="inline-flex items-center gap-2">
            <div className="min-w-8">{value}</div>
            <div className="relative w-11 h-1.5">
                <div
                    className="absolute top-0 left-0 bottom-0 rounded-[2px] bg-shade-07/40"
                    style={{ width: `${percentage}%` }}
                />
            </div>
        </div>
    </td>
);

// --- Main component ---

const ProductsTableCard = () => {
    const [search, setSearch] = useState("");
    const [activeTab, setActiveTab] = useState("market");
    const [selectedRows, setSelectedRows] = useState<number[]>([]);
    const [selectAll, setSelectAll] = useState(false);

    const handleRowSelect = (id: number) => {
        setSelectedRows((prev) =>
            prev.includes(id)
                ? prev.filter((rowId) => rowId !== id)
                : [...prev, id]
        );
    };

    const handleSelectAll = () => {
        if (selectAll) {
            setSelectedRows([]);
        } else {
            setSelectedRows(products.map((item) => item.id));
        }
        setSelectAll(!selectAll);
    };

    return (
        <div className="card">
            {/* Header: title + search + tabs */}
            <div className="flex items-center">
                <div className="flex items-center min-h-12 pl-5 text-h6">
                    Products
                </div>
                <Search
                    className="w-[17.5rem] ml-6 mr-auto"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search products"
                    isGray
                />
                <div className="inline-flex gap-0.5 rounded-3xl bg-b-surface1 p-1">
                    {categories.map((cat) => (
                        <button
                            key={cat.id}
                            className={`inline-flex items-center h-10 px-4 rounded-3xl text-button transition-all cursor-pointer ${
                                activeTab === cat.id
                                    ? "bg-b-surface2 text-t-primary shadow-widget"
                                    : "text-t-secondary hover:text-t-primary"
                            }`}
                            onClick={() => setActiveTab(cat.id)}
                        >
                            {cat.name}
                        </button>
                    ))}
                </div>
            </div>

            {/* Table */}
            <div className="pt-3 px-1 pb-5">
                <table className="w-full text-body-2 [&_th]:h-[4.25rem] [&_th]:pl-5 [&_th]:py-4 [&_td]:pl-5 [&_td]:py-4 first:[&_th]:pl-4 first:[&_td]:pl-4 last:[&_th]:pr-4 last:[&_td]:pr-4 [&_th]:align-middle [&_th]:text-left [&_th]:text-caption [&_th]:text-t-tertiary/80 [&_th]:font-normal">
                    <thead>
                        <tr>
                            <th>
                                <Checkbox
                                    checked={selectAll}
                                    onChange={() => handleSelectAll()}
                                />
                            </th>
                            {tableHead.map((head) => (
                                <th key={head}>{head}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {products.map((item) => (
                            <tr
                                key={item.id}
                                className="group relative [&_td:not(:first-child)]:relative [&_td]:z-2 [&_td]:border-t [&_td]:border-s-subtle [&_td]:transition-colors hover:[&_td]:border-transparent"
                            >
                                {/* Checkbox + hover overlay */}
                                <td className="w-10">
                                    <div className="box-hover" />
                                    <Checkbox
                                        checked={selectedRows.includes(
                                            item.id
                                        )}
                                        onChange={() =>
                                            handleRowSelect(item.id)
                                        }
                                    />
                                </td>

                                {/* Product: image + title + subtitle */}
                                <td>
                                    <div className="inline-flex items-center">
                                        <div className="shrink-0">
                                            <Image
                                                className="size-16 rounded-xl opacity-100 object-cover"
                                                src={item.image}
                                                width={64}
                                                height={64}
                                                alt=""
                                            />
                                        </div>
                                        <div className="max-w-[17.25rem] pl-5">
                                            <div className="pt-0.5 text-sub-title-1">
                                                {item.title}
                                            </div>
                                            <div className="truncate text-caption text-t-secondary/80">
                                                {item.details}
                                            </div>
                                        </div>
                                    </div>
                                </td>

                                {/* Status badge */}
                                <td>
                                    <div
                                        className={`inline-flex items-center h-7 px-1.75 rounded-lg border text-button leading-none capitalize ${
                                            item.active
                                                ? "label-green"
                                                : "label-red"
                                        }`}
                                    >
                                        {item.active ? "Active" : "Offline"}
                                    </div>
                                </td>

                                {/* Price */}
                                <td>
                                    <NumericFormat
                                        value={item.price}
                                        thousandSeparator=","
                                        decimalScale={2}
                                        fixedDecimalScale
                                        displayType="text"
                                        prefix="$"
                                    />
                                </td>

                                {/* Sales + percentage */}
                                <td>
                                    <div className="inline-flex items-center gap-2">
                                        <NumericFormat
                                            className="min-w-[3.25rem]"
                                            value={item.sales.value}
                                            thousandSeparator=","
                                            fixedDecimalScale
                                            displayType="text"
                                            prefix="$"
                                        />
                                        <Percentage
                                            value={item.sales.percentage}
                                        />
                                    </div>
                                </td>

                                {/* Views + mini bar */}
                                <ProgressCell
                                    value={item.views.value}
                                    percentage={item.views.percentage}
                                />

                                {/* Likes + mini bar */}
                                <ProgressCell
                                    value={item.likes.value}
                                    percentage={item.likes.percentage}
                                />
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default ProductsTableCard;
