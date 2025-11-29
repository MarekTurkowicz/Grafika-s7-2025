# Mini CAD / Image Processing Toolkit

Interactive desktop application for basic vector drawing and raster image processing, written in Python with Tkinter. The project was created as a series of tasks for a computer graphics course and integrates scene editing, image I/O, color models, geometric transformations, filtering, morphology, and analysis of green areas.

---

## 1. Project Structure

The project is organized as a Python package:

- `main.py`  
  Entry point. Creates and runs the main `App` window.

- `grafix/`
  - `app.py` – main GUI, event handling, history, integration of all tasks.
  - `constants.py` – UI constants (window size, colors, etc.).
  - `utils.py` – helper functions (`parts` for parsing, etc.).
  - `selection.py` – logic for managing the currently selected object (dragging, resizing, handles).
  - `shapes/`
    - `__init__.py`
    - `line.py` – implementation of `Line`.
    - `rect.py` – implementation of `Rect`.
    - `circle.py` – implementation of `Circle`.
    - `image.py` – implementation of `RasterImage` (PPM/JPEG images on canvas).
    - `polygon.py` – implementation of polygon figures for task 7.
    - factory helpers (e.g. `shape_from_dict`).
  - `render.py` – `CanvasSurface`, abstraction over Tkinter `Canvas` for drawing vector/raster graphics.
  - `io/`
    - `__init__.py`
    - `scene_io.py` – `save_scene`, `load_scene`, `scene_to_dict` for JSON serialization.
    - `ppm.py` – P3 / P6 loaders (block reading).
    - `jpeg_io.py` – JPEG read/write with adjustable quality.
  - `image_ops.py` – point operations on pixels:
    - linear color scaling (levels)
    - add/multiply/divide by constant
    - brightness change
    - grayscale (average, luma)
  - `color_models.py` – conversions `RGB ↔ CMYK`.
  - `rgbcube/`
    - `cube_points.py` – 3D RGB cube with sampled points.
    - `cube_sliced.py` – 3D RGB cube with slices/sections.
  - `hsvcone/`
    - `hsv_cone_window.py` – HSV cone visualization.
    - `cone_points.py` – HSV cone with points.
  - `filters.py` – spatial filters (blur, median, Sobel, sharpen, Gaussian, custom kernel).
  - `histogram.py` – histogram computation, stretching, equalization.
  - `thresholds.py` – thresholding methods for binary images.
  - `bezier/`
    - `editor.py` – Bézier curve editor window (task 6).
  - `polygons/`
    - `editor.py` – polygon editor with homogeneous transformations (task 7).
  - `morphology.py` – binary morphological operators (task 8).
  - `green_areas.py` – detection and percentage of green areas (task 9).

---

## 2. User Interface Overview

The main window is divided into three columns:

1. **Left** – drawing canvas (vector shapes, raster images).
2. **Middle panel** – tasks 1–3 and 4a (drawing, I/O, zoom, color conversion, 3D visualizations, point operations).
3. **Right panel** – tasks 4b–5–6–7–8–9 (filters, histogram, thresholding, Bézier editor, polygon editor, morphology, green-area analysis).

Bottom row contains a status bar with contextual messages (current mode, mouse position, operation results).

History of scene states (Undo/Redo) is maintained and bound to standard shortcuts:
- `Ctrl+Z` – Undo
- `Ctrl+Y` or `Ctrl+Shift+Z` – Redo

Selection supports moving, resizing, and showing parameters in an editable text field.

---

## Task 1 – Vector Drawing and Scene Serialization

### Functionality

- Drawing basic vector objects:
  - Lines (`Line`)
  - Rectangles (`Rect`)
  - Circles (`Circle`)
- Selecting objects and editing their parameters via:
  - Mouse (dragging, resizing using handles)
  - Text fields (parameter string)
- Serialization:
  - Save scene to JSON (`save_scene`)
  - Load scene from JSON (`load_scene`)
- Scene is represented as a list of shape objects; each object can be converted to/from dictionary (`scene_to_dict`, `shape_from_dict`).

### UI

- Mode selection (radio buttons): `Select`, `Line`, `Rect`, `Circle`.
- Parameter entry field (e.g. `x1,y1,x2,y2` for line and rect, `cx,cy,r` for circle).
- Buttons:
  - `Rysuj` – draw new object from parameters.
  - `Zastosuj` – apply edited parameters to selected object.
  - `Wyczyść` – clear scene.
  - `Zapisz JSON` – save scene.
  - `Wczytaj JSON` – load scene.

---

## Task 2 – PPM/JPEG I/O, Linear Scaling and Zoom

### PPM and JPEG

- Loading PPM:
  - Automatic detection of P3/P6 format (`read_ppm_auto`) with block reading for performance.
- Loading JPEG:
  - `read_jpeg` for raster import.
- Saving JPEG:
  - `write_jpeg` with adjustable quality (1–100) controlled by a slider.

Raster data is encapsulated in a `RasterImage` shape holding:
- Source width/height
- Source pixel buffer
- Display width/height (scalable)
- Canvas position (x, y)

### Linear Color Scaling (Levels)

- Operation “Levels (min,max)” implemented in `linear_color_scale`.
- Works on the selected raster image:
  - Input range `[in_min, in_max]` is mapped to `[0,255]`.
  - Values below/above range are clamped.

### Zoom

- Zoom changes display size of the selected raster image:
  - Doubling or halving width/height.
  - Implemented by nearest-neighbor scaling in `RasterImage`.

---

## Task 3 – Color Models and 3D Visualizations

### RGB ↔ CMYK Converter

- Interactive converter panel with:
  - RGB input:
    - Sliders [0–255] and text fields.
  - CMYK input:
    - Sliders [0–100 %] and text fields.
- Mode selection: RGB or CMYK as main input.
- Conversion functions:
  - `rgb_to_cmyk(r, g, b)`
  - `cmyk_to_rgb(c, m, y, k)`
- Preview:
  - Canvas rectangle displaying resulting RGB color.
- Numerical output:
  - Current RGB values.
  - Current CMYK values.

All UI elements are synchronized:
- Moving a slider updates text fields.
- Editing text fields updates sliders.
- Switching mode keeps values consistent.

### 3D RGB Cube

- Two windows:
  - Points-based RGB cube (`RGBCubePointsWindow`).
  - Slice-based RGB cube (`RGBCubeSliceWindow`).
- Visualizes distribution of colors in a 3D space (R, G, B axes).

### HSV Cone 3D

- Two windows:
  - Points-based cone (`HSVConePointsWindow`).
  - Full cone (`HSVConeWindow`).
- HSV representation: hue as angle, saturation as radius, value as height.
- Used to better understand HSV color space and transformations.

---

## Task 4 – Point Operations and Spatial Filtering

### 4a. Point-wise Operations

All operations are applied to the selected raster image (`RasterImage`) and modify its `src_pixels`:

- Add / subtract constant  
  `add_constant(pixels, val)`
- Multiply by constant  
  `mul_constant(pixels, factor)`
- Divide by constant  
  `div_constant(pixels, factor)`
- Brightness adjustment  
  `change_brightness(pixels, delta)`
- Grayscale conversions:
  - Average method (`to_grayscale_avg`)
  - Luma-based method (`to_grayscale_luma`)

### 4b. Spatial Filters

Implemented manually as convolution/median operations on pixel buffers:

- Box blur filter (`filter_box_blur`)  
  Simple averaging in a fixed-size neighborhood.
- Median filter (`filter_median`)  
  Noise removal by local median.
- Sobel edge detector (`filter_sobel`)  
  Gradient-based edge detection.
- Sharpen filter (`filter_sharpen`)  
  High-pass enhancement.
- Gaussian blur (`filter_gaussian`)  
  Smoothing using Gaussian kernel.
- Custom kernel filter (`filter_custom`)  
  Kernel defined by the user in a text field (matrix of floats).

All filters:
- Work on whole image.
- Are independent from external libraries (manual implementation).
- Use convolution (for linear filters) or rank operators (for median).

---

## Task 5 – Histogram and Thresholding

### Histogram

- Computation of luminance-based histogram (`compute_histogram`).
- Separate window with graphical histogram:
  - 256 bins displayed as vertical bars.
  - Normalization to panel height.

- Histogram operations:
  - Stretching (`histogram_stretch`):
    - Automatic detection of min/max intensity.
    - Linear mapping to `[0,255]`.
  - Equalization (`histogram_equalize`):
    - Cumulative histogram.
    - Redistribution of intensities for better contrast.

### Binary Thresholding

Multiple thresholding methods implemented in `thresholds.py` and available in the UI:

1. Manual threshold (`threshold_manual`)
   - User provides threshold `T` in [0,255].
2. Percent Black (`threshold_percent_black`)
   - User provides target percentage of black pixels.
3. Mean Iterative Selection (`threshold_mean_iterative`)
   - Iterative update of class means for foreground/background.
4. Entropy-based (`threshold_entropy`)
   - Threshold maximizing combined entropy of foreground/background.

All methods operate on grayscale representation and produce binary images (two-level intensity).

---

## Task 6 – Interactive Bézier Curve Editor

### Functionality

Dedicated Bézier editor window:

- Defining Bézier curves of arbitrary degree:
  - Number of control points and degree driven by user.
- Input via:
  - Mouse:
    - Adding points by clicking.
    - Dragging control points.
  - Text fields:
    - Editing numeric coordinates of control points.
- Real-time updating:
  - Curve is recomputed and redrawn while dragging points.
  - Smooth visual feedback for modifications.
- Multiple curves can be managed in the editor (depending on configuration).
- Implementation uses standard Bézier formulation and De Casteljau-like evaluation (or equivalent polynomial form).

No external libraries are used for curve computation or drawing.

---

## Task 7 – Polygons and Homogeneous Transformations

### Polygon Definition

- Polygons defined interactively:
  - Adding vertices using mouse clicks on canvas.
  - Creating and editing via text fields (list of points).
- Figures represent arbitrary polygons, not limited to convex ones.

### Transformations (Homogeneous Coordinates)

Transformations are implemented using homogeneous coordinates (3×3 matrices):

- Translation by vector:
  - Given vector `(dx, dy)`.
  - Can be executed:
    - Via text fields.
    - By dragging the polygon on the canvas.
- Rotation around arbitrary point:
  - Rotation center defined by:
    - Mouse (click to set pivot).
    - Text fields (numeric coordinates).
  - Rotation angle:
    - From text field or interactive control (dragging).
- Scaling with respect to point:
  - Scale factor `s`.
  - Scaling origin defined by mouse or text input.

All transformations:
- Are composed from 3×3 matrices.
- Modify polygon vertices.
- Are reversible via Undo/Redo in the main app.

Serialization:
- Polygons are included in JSON scene saving/loading alongside other shapes.

---

## Task 8 – Morphological Filters for Binary Images

### Morphological Operations

Implemented in `morphology.py` and applied to binary images:

- Dilation
- Erosion
- Opening (erosion followed by dilation)
- Closing (dilation followed by erosion)
- Hit-or-miss transform:
  - Used for thinning and thickening.
  - User can define structuring elements for hit-or-miss masks.

All operations are implemented manually, pixel-by-pixel, without external image libraries.

### Structuring Element

- User can define structuring element of arbitrary size.
- Representation:
  - 2D mask (e.g. 3×3, 5×5, etc.) specified in a text field.
- Operations respect center of the structuring element and mask values.

---

## Task 9 – Green Area Percentage and Parametric Color Selection

### Green Area Analysis

- Works on RGB raster images (PPM/JPEG).
- Pipeline:
  1. Load color image (same as in previous tasks).
  2. Classify each pixel as “green” or “non-green” based on color rules.
  3. Count number of green pixels and total pixels.
  4. Compute percentage:

     \[
     \text{green\_percentage} = \frac{\text{green\_pixels}}{\text{total\_pixels}} \cdot 100\%
     \]

- Implementation focuses on:
  - Reasonable accuracy of classification.
  - Efficient iteration over pixel buffer.

### Parametrization

- Thresholds and conditions are configurable:
  - Minimum and maximum hue or channel ranges.
  - Saturation/value thresholds or RGB relationships.
- Allows reuse of the same mechanism for other colors or conditions:
  - For example: detection of water, soil, snow, etc.

---

## Controls and Usage

### Running the Application

From the project root:

```bash
python main.py
