import { useEffect } from "react";

export const PRODUCT_NAME = "Caravan";

/** Names the screen in the browser tab. `null` leaves the title as it is, such as while loading. */
export function useDocumentTitle(screen: string | null) {
  useEffect(() => {
    if (screen !== null) document.title = `${screen} · ${PRODUCT_NAME}`;
  }, [screen]);
}
