# Notes

Two overlays target the same path (attributes.effect) with conflicting values
(deny vs allow). The overlay engine MUST treat this as a hard error and produce
E_OVERLAY_CONFLICT. Conflicts MUST NOT be silently resolved by last-write-wins.
Explicit conflict resolution (e.g. a resolve op) would be required to proceed.
