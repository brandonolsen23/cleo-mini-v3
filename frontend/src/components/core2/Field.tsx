import Tooltip from "./Tooltip";
import Icon from "./Icon";

type FieldProps = {
    className?: string;
    classInput?: string;
    label?: string;
    tooltip?: string;
    icon?: string;
    value: string;
    onChange: (
        e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
    ) => void;
    placeholder?: string;
    type?: string;
    textarea?: boolean;
    required?: boolean;
    error?: string;
    name?: string;
};

const Field = ({
    className,
    classInput,
    label,
    tooltip,
    icon,
    value,
    onChange,
    placeholder,
    type = "text",
    textarea,
    required,
    error,
    name,
}: FieldProps) => (
    <div className={className}>
        {label && (
            <div className="flex items-center gap-1.5 mb-2">
                <label className="text-body-2 font-semibold text-t-primary">
                    {label}
                </label>
                {tooltip && <Tooltip content={tooltip} />}
            </div>
        )}
        <div className="relative">
            {icon && (
                <div className="absolute top-3 left-3">
                    <Icon className="fill-t-secondary" name={icon} />
                </div>
            )}
            {textarea ? (
                <textarea
                    className={`w-full h-32 px-4 py-3 border rounded-2xl text-body-2 text-t-primary placeholder:text-t-secondary bg-b-surface2 border-s outline-none transition-all resize-none focus:border-s-focus focus:shadow-input-typing ${
                        error ? "!border-red" : ""
                    } ${classInput || ""}`}
                    value={value}
                    onChange={onChange}
                    placeholder={placeholder}
                    required={required}
                    name={name}
                />
            ) : (
                <input
                    className={`w-full h-12 border rounded-2xl text-body-2 text-t-primary placeholder:text-t-secondary bg-b-surface2 border-s outline-none transition-all focus:border-s-focus focus:shadow-input-typing ${
                        icon ? "pl-10.5 pr-4" : "px-4"
                    } ${error ? "!border-red" : ""} ${classInput || ""}`}
                    type={type}
                    value={value}
                    onChange={onChange}
                    placeholder={placeholder}
                    required={required}
                    name={name}
                />
            )}
        </div>
        {error && (
            <p className="mt-1.5 text-caption text-red">{error}</p>
        )}
    </div>
);

export default Field;
