import * as React from "react";
import { TextField } from "@radix-ui/themes";

import { cn } from "@/lib/utils";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, size: _size, color: _color, ...props }, ref) => {
    return (
      <TextField.Root
        size="2"
        variant="surface"
        type={type as any}
        className={cn(className)}
        ref={ref}
        {...(props as any)}
      />
    );
  }
);
Input.displayName = "Input";

export { Input };
