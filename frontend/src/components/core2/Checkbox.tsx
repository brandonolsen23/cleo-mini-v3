import { Checkbox as HeadlessCheckbox } from "@headlessui/react";
import Icon from "./Icon";

type CheckboxProps = {
    className?: string;
    label?: string;
    checked: boolean;
    onChange: (checked: boolean) => void;
};

const Checkbox = ({ className, label, checked, onChange }: CheckboxProps) => (
    <div className={`inline-flex items-center gap-2.5 ${className || ""}`}>
        <HeadlessCheckbox
            checked={checked}
            onChange={onChange}
            className="group flex items-center justify-center w-6 h-6 rounded-md border-2 border-s transition-colors cursor-pointer data-[checked]:bg-blue data-[checked]:border-blue"
        >
            <Icon
                className="!size-4 fill-white opacity-0 transition-opacity group-data-[checked]:opacity-100"
                name="check"
            />
        </HeadlessCheckbox>
        {label && (
            <span className="text-body-2 text-t-primary cursor-pointer" onClick={() => onChange(!checked)}>
                {label}
            </span>
        )}
    </div>
);

export default Checkbox;
