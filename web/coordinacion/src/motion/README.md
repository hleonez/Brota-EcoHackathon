# EcoConecta motion integration

David's motion-only delivery starts from commit b7712cf. It uses native CSS with the existing React, TypeScript and Bootstrap Grid stack. No dependency or build configuration changes are required.

## Ownership

David owns animaciones.css. Javier owns React attributes, state, layout, colors, fonts, focus management and the final import. The stylesheet leaves the manual's logo, palette and typography to the visual layer.

Javier imports ./motion/animaciones.css from src/main.tsx after the visual styles when integrating. This delivery deliberately leaves that entry point to its owner.

## Attribute contract

| Attribute | State | Motion |
| --- | --- | --- |
| data-motion="nav" | data-state="open" or "closed" | Mobile drawer slides from the left, 220 ms, below 1024 px |
| data-motion="dialog" | data-state="open" or "closed" | Centered scale from 0.97 and fade, 200 ms |
| data-motion="notice" | data-state="open" or "closed" | Four-pixel vertical shift and fade, 160 ms |
| data-motion="new-item" | data-state="new" | One opacity emphasis, 600 ms |

The mobile cutoff is the existing 1024 px desktop navigation breakpoint. Javier must confirm it when integrating his new layout.

data-motion-instant disables motion on an individual element, including keyboard-triggered or frequently used interactions. prefers-reduced-motion disables every transition and arrival animation immediately while leaving the open/closed appearance intact.

An element without data-state retains its existing appearance. Desktop navigation is unaffected by the mobile motion rules.

## Lifecycle requirements

- Keep a mounted drawer or notice in the DOM while it moves. Changing the state reverses an interrupted transition from its current appearance.
- For native dialogs, call showModal() for entry. On exit set data-state="closed" first and retain the open dialog until the transition ends. Then call close() and restore focus to the trigger.
- Before closing a drawer, ensure focus returns to its trigger and the closed content is inert. CSS opacity and pointer-events do not remove elements from keyboard navigation.
- Javier owns Escape, aria-expanded, aria-controls, dialog labels, focus trapping and the static signal for a new request.
- Use a transitionend handler filtered to the element itself and opacity. Recheck that the state is still closed before unmounting. A reopening must cancel pending cleanup.
- Include a fallback cleanup bounded by the motion duration in case no transition event fires. With reduced motion or data-motion-instant, complete closing synchronously.
- Preserve live-region messages for notices. Do not delay data, actions or announcements until an animation finishes.
- Keep the same notice node when its text changes. Ordinary text updates must remain immediate.
- Set new only on arrival. Remove that state after the highlight, retaining a static label if needed. Refreshing or filtering existing rows must not retrigger it.
- @starting-style enhances newly mounted entry. Without browser support, content appears immediately.
- Remove legacy .tarjeta.reciente animation and .toast transitions on migrated elements during integration. Do not run both systems on the same node.
- Do not apply the hooks to filters, tables or section changes.

## Acceptance checks

Run npm run check and npm run build from web/coordinacion after the final import.

Check widths 390, 768 and 1440 px. Open and close the menu and dialogs rapidly and confirm the latest state wins without a flash or stale unmount. Test keyboard focus and Escape. Emulate reduced motion and confirm immediate closing, visible notices and the retained static new-item signal. Verify ordinary API refreshes do not move tables or replay arrival emphasis.

The complete application behavior requires Javier's React integration. This CSS alone does not implement a menu, a dialog or their accessibility behavior.

## Standalone verification

The external local fixture loaded this exact stylesheet in the browser at 390, 768 and 1440 px. The mobile menu computed 220 ms transitions; desktop navigation computed no transition. Dialog entry computed 200 ms. Opening, closing, reopening, notice visibility and new-item arrival were exercised, and closing the dialog returned focus to its trigger. The browser parsed the reduced-motion rule and all selectors.

System reduced-motion emulation and the final React lifecycle remain pending for the joint integration check. The fixture is intentionally outside this repository.
