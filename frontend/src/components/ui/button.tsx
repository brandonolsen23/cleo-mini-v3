import * as React from "react";
import {
  Button as RadixButton,
  IconButton as RadixIconButton,
} from "@radix-ui/themes";

import { cn } from "@/lib/utils";

type ButtonVariant =
  | "default"
  | "destructive"
  | "outline"
  | "secondary"
  | "ghost"
  | "link";
type ButtonSize = "default" | "sm" | "lg" | "icon" | "icon-sm";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  asChild?: boolean;
}

const variantMap: Record<
  string,
  { variant: "solid" | "soft" | "outline" | "ghost"; color?: "red" | "gray" }
> = {
  default: { variant: "solid" },
  destructive: { variant: "solid", color: "red" },
  outline: { variant: "outline" },
  secondary: { variant: "soft", color: "gray" },
  ghost: { variant: "ghost" },
  link: { variant: "ghost" },
};

const sizeMap: Record<string, "1" | "2" | "3"> = {
  default: "3",
  sm: "2",
  lg: "3",
  icon: "3",
  "icon-sm": "1",
};

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "default",
      size = "default",
      asChild,
      ...props
    },
    ref
  ) => {
    const mapped = variantMap[variant] ?? variantMap.default;
    const radixSize = sizeMap[size] ?? "3";
    const isIcon = size === "icon" || size === "icon-sm";

    if (isIcon) {
      return (
        <RadixIconButton
          ref={ref}
          size={radixSize}
          variant={mapped.variant}
          color={mapped.color}
          className={cn(className)}
          asChild={asChild}
          {...(props as any)}
        />
      );
    }

    return (
      <RadixButton
        ref={ref}
        size={radixSize}
        variant={mapped.variant}
        color={mapped.color}
        className={cn(className)}
        asChild={asChild}
        {...(props as any)}
      />
    );
  }
);
Button.displayName = "Button";

export { Button };
