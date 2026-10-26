import { Route, Routes } from "react-router";

import { Groups } from "./Groups";
import { GroupRoute } from "./GroupView";
import { NotFound } from "./NotFound";

/** The signed-in screens. `onSignedOut` must be stable: the screens reload when it changes. */
export function AppRoutes({ onSignedOut }: { onSignedOut: () => void }) {
  return (
    <Routes>
      <Route path="/" element={<Groups onSignedOut={onSignedOut} />} />
      <Route path="/groups/:groupId" element={<GroupRoute onSignedOut={onSignedOut} />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
