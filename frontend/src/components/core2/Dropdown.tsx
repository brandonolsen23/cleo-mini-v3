import { Menu, MenuButton, MenuItems, MenuItem } from "@headlessui/react";
import Icon from "./Icon";

type DropdownItem = {
    label: string;
    icon?: string;
    onClick?: () => void;
    danger?: boolean;
};

type DropdownProps = {
    className?: string;
    items: DropdownItem[];
    trigger?: React.ReactNode;
};

const Dropdown = ({ className, items, trigger }: DropdownProps) => (
    <Menu as="div" className={`relative ${className || ""}`}>
        <MenuButton className="action">
            {trigger || <Icon className="fill-inherit" name="dots" />}
        </MenuButton>
        <MenuItems className="absolute right-0 z-50 mt-2 w-56 rounded-2xl bg-b-surface2 py-2 shadow-dropdown border border-s outline-none">
            {items.map((item, index) => (
                <MenuItem key={index}>
                    <button
                        className={`flex items-center gap-3 w-full px-4 py-2.5 text-body-2 text-left transition-colors data-[focus]:bg-b-highlight ${
                            item.danger
                                ? "text-red fill-red"
                                : "text-t-primary fill-t-secondary"
                        }`}
                        onClick={item.onClick}
                    >
                        {item.icon && (
                            <Icon
                                className="!size-5 fill-inherit"
                                name={item.icon}
                            />
                        )}
                        {item.label}
                    </button>
                </MenuItem>
            ))}
        </MenuItems>
    </Menu>
);

export default Dropdown;
