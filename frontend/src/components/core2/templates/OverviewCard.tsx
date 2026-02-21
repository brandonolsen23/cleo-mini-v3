import { useState } from "react";
import { Link } from "react-router-dom";
import Card from "../Card";
import Icon from "../Icon";
import Percentage from "../Percentage";

const durations = [
    { id: 1, name: "Last 7 days" },
    { id: 2, name: "Last month" },
    { id: 3, name: "Last year" },
];

type OverviewTab = {
    id: number;
    icon: string;
    label: string;
    value: string;
    percent: number;
};

const customersData = [
    { id: 1, name: "Gladyce", avatar: "https://i.pravatar.cc/64?img=1" },
    { id: 2, name: "Elbert", avatar: "https://i.pravatar.cc/64?img=3" },
    { id: 3, name: "Joyce", avatar: "https://i.pravatar.cc/64?img=5" },
    { id: 4, name: "John", avatar: "https://i.pravatar.cc/64?img=8" },
    { id: 5, name: "Elbert", avatar: "https://i.pravatar.cc/64?img=11" },
];

type OverviewCardProps = {
    brandCount?: number;
    brandCountLastMonth?: number;
};

const OverviewCard = ({ brandCount = 0, brandCountLastMonth = 0 }: OverviewCardProps) => {
    const [duration, setDuration] = useState(durations[0]);
    const [activeTab, setActiveTab] = useState(1);

    const tabs: OverviewTab[] = [
        {
            id: 1,
            icon: "profile",
            label: "National Brands Traded",
            value: brandCount.toLocaleString(),
            percent: brandCountLastMonth > 0
                ? Math.round(((brandCount - brandCountLastMonth) / brandCountLastMonth) * 1000) / 10
                : 0,
        },
        {
            id: 2,
            icon: "wallet",
            label: "Balance",
            value: "256k",
            percent: 36.8,
        },
    ];

    return (
        <Card
            title="Overview"
            selectValue={duration}
            selectOnChange={setDuration}
            selectOptions={durations}
        >
            <div className="pt-1">
                {/* Stat tabs */}
                <div className="flex mb-4 p-1.5 border border-s-subtle rounded-4xl bg-b-depth2">
                    {tabs.map((tab) => (
                        <div
                            className={`group flex-1 px-12 py-8 rounded-3xl cursor-pointer transition-all ${
                                activeTab === tab.id
                                    ? "bg-b-surface2 shadow-depth-toggle"
                                    : ""
                            }`}
                            key={tab.label}
                            onClick={() => setActiveTab(tab.id)}
                        >
                            <div
                                className={`flex items-center gap-3 mb-2 text-sub-title-1 transition-colors group-hover:text-t-primary ${
                                    activeTab === tab.id
                                        ? "text-t-primary"
                                        : "text-t-secondary"
                                }`}
                            >
                                <Icon
                                    className={`transition-colors group-hover:fill-t-primary ${
                                        activeTab === tab.id
                                            ? "fill-t-primary"
                                            : "fill-t-secondary"
                                    }`}
                                    name={tab.icon}
                                />
                                <div>{tab.label}</div>
                            </div>
                            <div className="flex items-center gap-4">
                                <div className="text-h2">
                                    {tab.value}
                                </div>
                                <div>
                                    <Percentage value={tab.percent} />
                                    <div className="mt-1 text-body-2 text-t-secondary">
                                        vs last month
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>

                {/* New customers section (shown when Customers tab active) */}
                {activeTab === 1 && (
                    <div className="p-5">
                        <div className="mb-6">
                            <div className="text-sub-title-1">
                                Contacts who recently acquired.
                            </div>
                            <div className="text-body-2 text-t-secondary">
                                Connect with active buyers -&gt;
                            </div>
                        </div>
                        <div className="flex">
                            {customersData.map((customer) => (
                                <div
                                    className="flex-1 px-1 py-8 text-center"
                                    key={customer.id}
                                >
                                    <div className="flex justify-center">
                                        <img
                                            className="size-16 rounded-full object-cover"
                                            src={customer.avatar}
                                            width={64}
                                            height={64}
                                            alt={customer.name}
                                        />
                                    </div>
                                    <div className="mt-4 text-button text-t-secondary">
                                        {customer.name}
                                    </div>
                                </div>
                            ))}
                            <div className="flex-1 px-2 py-8 text-center">
                                <Link
                                    className="group inline-flex flex-col justify-center items-center"
                                    to="/contacts"
                                >
                                    <div className="flex justify-center items-center size-16 rounded-full border border-s-stroke2 transition-colors group-hover:border-s-highlight group-hover:shadow-depth">
                                        <Icon
                                            className="fill-t-secondary transition-colors group-hover:fill-t-primary"
                                            name="arrow-right"
                                        />
                                    </div>
                                    <div className="mt-4 text-button text-t-secondary transition-colors group-hover:text-t-primary">
                                        View all
                                    </div>
                                </Link>
                            </div>
                        </div>
                    </div>
                )}

                {/* Balance section (shown when Balance tab active) */}
                {activeTab === 2 && (
                    <div className="p-5">
                        <div className="text-body-2 text-t-secondary text-center py-16">
                            Balance chart placeholder — wire up with Recharts data.
                        </div>
                    </div>
                )}
            </div>
        </Card>
    );
};

export default OverviewCard;
