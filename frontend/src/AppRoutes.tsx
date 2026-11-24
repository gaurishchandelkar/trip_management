import { Route, Routes } from "react-router";

import type { Member } from "./api";
import { Groups } from "./Groups";
import { GroupRoute } from "./GroupView";
import { NotFound } from "./NotFound";
import { Profile } from "./Profile";

/** The signed-in screens. `onSignedOut` must be stable: the screens reload when it changes. */
export function AppRoutes({
  member,
  onSignedOut,
  onProfileSaved,
}: {
  member: Member;
  onSignedOut: () => void;
  onProfileSaved: (member: Member) => void;
}) {
  return (
    <Routes>
      <Route path="/" element={<Groups onSignedOut={onSignedOut} />} />
      <Route path="/groups/:groupId" element={<GroupRoute onSignedOut={onSignedOut} />} />
      <Route
        path="/profile"
        element={<Profile member={member} onSaved={onProfileSaved} onSignedOut={onSignedOut} />}
      />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
