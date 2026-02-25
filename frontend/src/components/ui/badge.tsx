import * as React from "react";
import { Badge as RadixBadge, type BadgeProps as RadixBadgeProps } from "@radix-ui/themes";

import { cn } from "@/lib/utils";

type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: BadgeVariant;
}

const variantMap: Record<
  string,
  { variant: RadixBadgeProps["variant"]; color?: RadixBadgeProps["color"] }
> = {
  default: { variant: "solid" },
  secondary: { variant: "soft", color: "gray" },
  destructive: { variant: "solid", color: "red" },
  outline: { variant: "outline" },
};

function Badge({ className, variant = "default", color: _color, ...props }: BadgeProps) {
  const mapped = variantMap[variant] ?? variantMap.default;
  return (
    <RadixBadge
      size="1"
      variant={mapped.variant}
      color={mapped.color}
      className={cn(className)}
      {...props}
    />
  );
}

export { Badge };
