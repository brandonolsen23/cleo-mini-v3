import { Listbox, ListboxButton, ListboxOption, ListboxOptions } from "@headlessui/react";
import Icon from "./Icon";

type SelectOption = {
    id: number;
    name: string;
};

type SelectProps = {
    className?: string;
    value: SelectOption;
    onChange: (value: SelectOption) => void;
    options: SelectOption[];
    placeholder?: string;
    isBlack?: boolean;
};

const Select = ({
    className,
    value,
    onChange,
    options,
    placeholder,
    isBlack,
}: SelectProps) => (
    <Listbox value={value} onChange={onChange}>
        <div className={`relative ${className || ""}`}>
            <ListboxButton
                className={`relative w-full h-12 pl-4 pr-10 rounded-2xl text-left text-body-2 cursor-pointer outline-none transition-all ${
                    isBlack
                        ? "bg-shade-02 text-t-light border border-shade-04"
                        : "bg-b-surface2 text-t-primary border border-s"
                }`}
            >
                <span className="block truncate">
                    {value?.name || placeholder || "Select..."}
                </span>
                <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
                    <Icon
                        className={`!size-5 ${isBlack ? "fill-t-light" : "fill-t-secondary"}`}
                        name="chevron"
                    />
                </span>
            </ListboxButton>
            <ListboxOptions className="absolute z-50 mt-1 w-full max-h-60 overflow-auto rounded-2xl bg-b-surface2 py-1 text-body-2 shadow-dropdown border border-s outline-none">
                {options.map((option) => (
                    <ListboxOption
                        key={option.id}
                        value={option}
                        className="relative cursor-pointer select-none py-2.5 pl-4 pr-10 text-t-primary transition-colors data-[focus]:bg-b-highlight"
                    >
                        {({ selected }) => (
                            <>
                                <span
                                    className={`block truncate ${
                                        selected ? "font-semibold" : "font-normal"
                                    }`}
                                >
                                    {option.name}
                                </span>
                                {selected && (
                                    <span className="absolute inset-y-0 right-0 flex items-center pr-3">
                                        <Icon
                                            className="!size-5 fill-blue"
                                            name="check"
                                        />
                                    </span>
                                )}
                            </>
                        )}
                    </ListboxOption>
                ))}
            </ListboxOptions>
        </div>
    </Listbox>
);

export default Select;
