import { useEffect } from "react";

export const PRODUCT_NAME = "Caravan";

/** Names the screen in the browser tab. */
export function useDocumentTitle(screen: string) {
  useEffect(() => {
    document.title = `${screen} · ${PRODUCT_NAME}`;
  }, [screen]);
}
