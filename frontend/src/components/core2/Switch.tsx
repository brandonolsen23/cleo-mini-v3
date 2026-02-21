import { Switch as HeadlessSwitch } from "@headlessui/react";

type SwitchProps = {
    className?: string;
    label?: string;
    checked: boolean;
    onChange: (checked: boolean) => void;
};

const Switch = ({ className, label, checked, onChange }: SwitchProps) => (
    <div className={`inline-flex items-center gap-3 ${className || ""}`}>
        <HeadlessSwitch
            checked={checked}
            onChange={onChange}
            className="group relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent bg-shade-08 transition-colors data-[checked]:bg-blue"
        >
            <span className="pointer-events-none relative inline-block h-5 w-5 rounded-full bg-white shadow-widget ring-0 transition-transform translate-x-0 group-data-[checked]:translate-x-5" />
        </HeadlessSwitch>
        {label && (
            <span className="text-body-2 text-t-primary">{label}</span>
        )}
    </div>
);

export default Switch;
