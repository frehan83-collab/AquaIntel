/**
 * UI Primitives — barrel re-export
 *
 * Primary design-system primitives used across the app. Prefer importing
 * from this index instead of individual files:
 *
 *   import { Card, Input, Label, Modal, Tabs, Tab, Badge, OcButton } from "@/components/ui";
 */

// Button (existing)
export { OcButton, buttonVariants } from "./Button";
export type { ButtonProps } from "./Button";

// Card
export { Card } from "./Card";
export type { CardProps, CardVariant, CardPadding } from "./Card";

// Input
export { Input } from "./Input";
export type { InputProps, InputSize } from "./Input";

// Label
export { Label } from "./Label";
export type { LabelProps } from "./Label";

// Modal
export { Modal } from "./Modal";
export type { ModalProps, ModalSize } from "./Modal";

// Tabs
export { Tabs, TabList, Tab, TabPanels, TabPanel } from "./Tabs";
export type {
  TabsProps,
  TabListProps,
  TabProps,
  TabPanelsProps,
  TabPanelProps,
} from "./Tabs";

// Badge
export { Badge } from "./Badge";
export type { BadgeProps, BadgeVariant, BadgeSize } from "./Badge";
