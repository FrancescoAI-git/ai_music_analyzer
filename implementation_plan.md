# Fix Frontend Display and Parameter Mismatch

## Goal Description
The user reported that results are not displaying in the frontend. Investigation revealed two issues:
1.  `backend_server.py` filters out the `context` field from the response, which the frontend expects to display in the "Technical Context" section.
2.  `index.html` sends `start`/`end` parameters, but the backend expects `trim_start`/`trim_end`, causing audio selections to be ignored.

This plan fixes both issues to ensure correct data flow and display.

## User Review Required
> [!NOTE]
> No breaking changes. This is a bug fix.

## Proposed Changes

### Backend
#### [MODIFY] [backend_server.py](file:///Users/francescomartinelli/ai_analyzer/backend_server.py)
- Add `"context": results.get("context")` to the return dictionary in `analyze_endpoint`.

### Frontend
#### [MODIFY] [index.html](file:///Users/francescomartinelli/ai_analyzer/ai-music-analyzer_UI/index.html)
- Update `FormData` appending to use `trim_start` instead of `start`.
- Update `FormData` appending to use `trim_end` instead of `end`.

## Verification Plan

### Manual Verification
1.  **Upload Audio**: Upload an audio file to the UI.
2.  **Select Region**: Select a specific region.
3.  **Analyze**: Click "Analyze Segment".
4.  **Verify Display**: Check that the "Technical Context" section (top right) is populated with text (not empty or "No data returned").
5.  **Verify Selection**: Check backend logs or context data to ensure the analyzed duration matches the selection (e.g., "Durata: 10.0 secondi" instead of full track).
