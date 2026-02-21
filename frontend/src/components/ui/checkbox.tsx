import * as React from "react";
import { Checkbox as HeadlessCheckbox } from "@headlessui/react";
import { Check } from "@phosphor-icons/react";

import { cn } from "@/lib/utils";

export interface CheckboxProps {
  checked?: boolean;
  onCheckedChange?: (checked: boolean | "indeterminate") => void;
  disabled?: boolean;
  className?: string;
  id?: string;
}

const Checkbox = React.forwardRef<HTMLSpanElement, CheckboxProps>(
  ({ checked = false, onCheckedChange, disabled, className, id }, ref) => (
    <HeadlessCheckbox
      as="span"
      ref={ref}
      id={id}
      checked={checked}
      onChange={(val: boolean) => onCheckedChange?.(val)}
      disabled={disabled}
      className={cn(
        "peer inline-flex h-4 w-4 shrink-0 items-center justify-center rounded border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[checked]:bg-primary data-[checked]:text-primary-foreground cursor-pointer",
        className
      )}
    >
      {checked && <Check className="h-4 w-4" />}
    </HeadlessCheckbox>
  )
);
Checkbox.displayName = "Checkbox";

export { Checkbox };
