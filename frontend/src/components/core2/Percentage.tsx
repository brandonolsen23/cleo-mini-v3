import Icon from "./Icon";

type PercentageProps = {
    className?: string;
    value: number;
    isLarge?: boolean;
};

const Percentage = ({ className, value, isLarge }: PercentageProps) => {
    const isPositive = value >= 0;

    return (
        <div
            className={`inline-flex items-center gap-0.5 rounded-lg border px-1.75 ${
                isLarge ? "h-8 text-body-2 font-semibold" : "h-7 text-caption font-semibold"
            } ${
                isPositive
                    ? "border-green/30 bg-green-light text-green"
                    : "border-red/30 bg-red-light text-red"
            } ${className || ""}`}
        >
            <Icon
                className={`!size-4 ${isPositive ? "fill-green" : "fill-red rotate-180"}`}
                name="arrow-up"
            />
            {Math.abs(value)}%
        </div>
    );
};

export default Percentage;
