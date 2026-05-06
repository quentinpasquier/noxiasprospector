import { redirect } from "next/navigation";

/**
 * Root route — straight to the targeting page. NoxiasProspect is an
 * internal tool, no public marketing surface.
 */
export default function HomePage(): never {
  redirect("/cibler");
}
