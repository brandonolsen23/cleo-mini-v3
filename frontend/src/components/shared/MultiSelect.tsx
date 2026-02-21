import React from "react";
import {
  Popover,
  PopoverButton,
  PopoverPanel,
  Transition,
} from "@headlessui/react";
import { CaretDown, X } from "@phosphor-icons/react";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";

export interface MultiSelectOption {
  value: string;
  label: string;
  color?: string;
}

interface MultiSelectProps {
  options: MultiSelectOption[];
  selected: string[];
  onChange: (selected: string[]) => void;
  placeholder?: string;
  label?: string;
}

export default function MultiSelect({
  options,
  selected,
  onChange,
  placeholder = "All",
  label,
}: MultiSelectProps) {
  const toggle = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value));
    } else {
      onChange([...selected, value]);
    }
  };

  const clear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange([]);
  };

  const displayText =
    selected.length === 0
      ? placeholder
      : selected.length === 1
        ? options.find((o) => o.value === selected[0])?.label ?? selected[0]
        : `${selected.length} selected`;

  return (
    <div className="flex items-center">
      {label && (
        <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider mr-2">
          {label}
        </span>
      )}
      <Popover className="relative">
        <PopoverButton as={React.Fragment}>
          <Button variant="outline" size="sm" className="min-w-[120px] justify-between gap-1.5">
            <span className="truncate text-left flex-1">
              {displayText}
            </span>
            {selected.length > 0 ? (
              <X size={14} className="text-muted-foreground hover:text-foreground shrink-0" onClick={clear} />
            ) : (
              <CaretDown size={14} className="text-muted-foreground shrink-0" />
            )}
          </Button>
        </PopoverButton>
        <Transition
          enter="transition ease-out duration-100"
          enterFrom="opacity-0 scale-95"
          enterTo="opacity-100 scale-100"
          leave="transition ease-in duration-75"
          leaveFrom="opacity-100 scale-100"
          leaveTo="opacity-0 scale-95"
        >
          <PopoverPanel
            anchor="bottom start"
            className="z-50 mt-1 w-56 max-h-64 overflow-auto rounded-xl border border-border bg-popover shadow-dropdown outline-none"
          >
            {options.length === 0 ? (
              <div className="px-3 py-2 text-sm text-muted-foreground">No options</div>
            ) : (
              options.map((opt) => (
                <label
                  key={opt.value}
                  className="flex items-center gap-2 px-3 py-1.5 hover:bg-accent cursor-pointer select-none"
                >
                  <Checkbox
                    checked={selected.includes(opt.value)}
                    onCheckedChange={() => toggle(opt.value)}
                  />
                  {opt.color && (
                    <span className={`inline-block w-2.5 h-2.5 rounded-full shrink-0 ${opt.color}`} />
                  )}
                  <span className="text-sm truncate">{opt.label}</span>
                </label>
              ))
            )}
          </PopoverPanel>
        </Transition>
      </Popover>
    </div>
  );
}
