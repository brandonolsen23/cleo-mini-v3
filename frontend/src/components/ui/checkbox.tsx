import * as React from "react";
import { Checkbox as RadixCheckbox } from "@radix-ui/themes";

import { cn } from "@/lib/utils";

export interface CheckboxProps {
  checked?: boolean;
  onCheckedChange?: (checked: boolean | "indeterminate") => void;
  disabled?: boolean;
  className?: string;
  id?: string;
}

const Checkbox = React.forwardRef<HTMLButtonElement, CheckboxProps>(
  ({ checked = false, onCheckedChange, disabled, className, id }, ref) => (
    <RadixCheckbox
      ref={ref}
      id={id}
      size="1"
      variant="surface"
      checked={checked}
      onCheckedChange={(val) => onCheckedChange?.(val)}
      disabled={disabled}
      className={cn(className)}
    />
  )
);
Checkbox.displayName = "Checkbox";

export { Checkbox };
