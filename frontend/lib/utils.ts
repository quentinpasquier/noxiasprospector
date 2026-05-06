import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind class names safely (used by all shadcn/ui components). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
