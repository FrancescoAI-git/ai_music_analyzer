# Implementation Plan - Tailwind CSS Upgrade

## Goal Description
Upgrade the existing Vanilla CSS interface to use **Tailwind CSS** for styling and animations. This will allow for a more modern, maintainable, and "cool" design with built-in animations.

## User Review Required
- [ ] Confirm if a build step (running `npm run build:css`) is acceptable. (Assumed yes as it's standard for Tailwind).

## Proposed Changes

### Configuration
#### [NEW] [tailwind.config.js](file:///Users/francescomartinelli/ai_analyzer/ai_analyzer_ui/tailwind.config.js)
- Configure content paths (`./public/**/*.{html,js}`).
- Extend theme with the "Cyberpunk" colors (Dark backgrounds, Neon Indigo/Purple).
- Add custom animations (keyframes for "breathing" glow, slide-ins).

#### [MODIFY] [package.json](file:///Users/francescomartinelli/ai_analyzer/ai_analyzer_ui/package.json)
- Add `devDependencies`: `tailwindcss`.
- Add `scripts`: `"build:css": "tailwindcss -i ./src/input.css -o ./public/style.css --watch"`.

### Source Files
#### [NEW] [src/input.css](file:///Users/francescomartinelli/ai_analyzer/ai_analyzer_ui/src/input.css)
- Import Tailwind directives (`@tailwind base;`, etc.).
- Add any custom base styles if needed.

#### [MODIFY] [public/index.html](file:///Users/francescomartinelli/ai_analyzer/ai_analyzer_ui/public/index.html)
- **Complete Rewrite of Classes**: Replace standard CSS classes with Tailwind utility classes.
- **Layout**: Use Flexbox/Grid utilities.
- **Styling**: Apply dark mode colors, glassmorphism (`backdrop-blur`, `bg-opacity`), and gradients using Tailwind.
- **Animations**: Add `animate-fade-in`, `hover:scale-105`, and custom animations to elements.

#### [DELETE] [public/style.css](file:///Users/francescomartinelli/ai_analyzer/ai_analyzer_ui/public/style.css)
- This file will be **generated** by Tailwind. We will delete the manual one and replace it with the build output.

## Verification Plan
### Automated Tests
- None.

### Manual Verification
1. Run `npm install`.
2. Run `npm run build:css` (or keep it running).
3. Start server `npm start`.
4. Verify the UI looks even better and has animations.
