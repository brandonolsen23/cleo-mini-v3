import { Tooltip as ReactTooltip } from "react-tooltip";
import Icon from "./Icon";

type TooltipProps = {
    className?: string;
    content: string;
    place?: "top" | "bottom" | "left" | "right";
};

let tooltipCounter = 0;

const Tooltip = ({ className, content, place = "top" }: TooltipProps) => {
    const id = `tooltip-${++tooltipCounter}`;

    return (
        <>
            <button
                className={`inline-flex text-[0] ${className || ""}`}
                data-tooltip-id={id}
                data-tooltip-content={content}
                data-tooltip-place={place}
            >
                <Icon className="fill-t-tertiary" name="help" />
            </button>
            <ReactTooltip
                id={id}
                className="!rounded-lg !bg-shade-02 !px-3 !py-2 !text-caption !text-t-light !shadow-dropdown"
            />
        </>
    );
};

export default Tooltip;
