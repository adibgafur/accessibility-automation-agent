"""
GUIrilla Detector - Visual GUI element detection using GUIrilla-See-0.7B.

GUIrilla-See-0.7B is a 0.7B parameter model based on Florence 2-large,
fine-tuned for open-vocabulary GUI element detection. It takes a screenshot
and outputs bounding boxes + labels for detected UI elements.

This module is the fallback engine: used when UFO2's UIA detection fails
(e.g., after a software update changes the UI structure).

Dependencies:
    - transformers (HuggingFace model loading)
    - torch (inference)
    - Pillow (screenshot capture and image processing)

Optimised for low-spec hardware:
    - INT8 quantization support
    - Lazy model loading
    - Configurable image resize
    - Model caching in .cache/guirilla/
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from ..utils.config_manager import config
from ..utils.error_handler import GUIDetectionError, ModelLoadError
from .base import (
    BaseDetector,
    BoundingBox,
    DetectionResult,
    DetectionSource,
    DetectorState,
    ElementType,
    UIElement,
)


# ======================================================================
# GUIrilla Detector
# ======================================================================


class GUIrillaDetector(BaseDetector):
    """
    Visual GUI element detector using GUIrilla-See-0.7B.

    Takes screenshots and runs them through the Florence 2-based
    model to detect UI elements visually. This is a fallback for
    when UFO2's UIA tree doesn't match the actual UI (e.g., after
    software updates).

    Configuration (from config/guirilla_config.yaml):
        - model.name: HuggingFace model ID
        - quantization.type: "int8", "fp16", or "fp32"
        - inference.confidence_threshold: Minimum confidence
        - inference.max_detections: Max elements to return
        - visual.max_image_size: Resize screenshots to this max dimension
    """

    def __init__(self) -> None:
        super().__init__(name="GUIrilla")

        # Lazy-loaded
        self._model = None
        self._processor = None
        self._torch = None
        self._pil = None

        # Config
        self._model_name: str = config.get(
            "guirilla.model.name",
            "macpaw-research/GUIrilla-See-0.7B",
        )
        self._quantization: str = config.get(
            "guirilla.quantization.type", "int8"
        )
        self._confidence_threshold: float = config.get(
            "gui_detection.guirilla_confidence_threshold", 0.5
        )
        self._max_detections: int = config.get(
            "guirilla.inference.max_detections", 10
        )
        self._max_image_size: int = config.get(
            "guirilla.visual.max_image_size", 1024
        )
        self._cache_dir: str = config.get(
            "guirilla.cache.cache_dir", ".cache/models/guirilla"
        )
        self._device: str = config.get("guirilla.model.device", "cpu")
        self._timeout: float = config.get(
            "guirilla.inference.timeout", 10.0
        )

        logger.info(
            f"GUIrillaDetector created | model={self._model_name} | "
            f"quantization={self._quantization} | device={self._device}"
        )

    # ------------------------------------------------------------------
    # Lazy imports
    # ------------------------------------------------------------------

    def _ensure_imports(self) -> None:
        """Lazy-import ML libraries."""
        if self._torch is None:
            try:
                import torch
                self._torch = torch
                logger.debug(f"PyTorch imported | CUDA available: {torch.cuda.is_available()}")
            except ImportError as exc:
                raise GUIDetectionError(
                    f"PyTorch not installed: {exc}. Run: pip install torch"
                )

        if self._pil is None:
            try:
                from PIL import Image, ImageGrab
                self._pil = {"Image": Image, "ImageGrab": ImageGrab}
                logger.debug("Pillow imported")
            except ImportError as exc:
                raise GUIDetectionError(
                    f"Pillow not installed: {exc}. Run: pip install Pillow"
                )

    # ------------------------------------------------------------------
    # BaseDetector interface
    # ------------------------------------------------------------------

    def load(self) -> None:
        """
        Load the GUIrilla-See-0.7B model from HuggingFace.

        Downloads on first run, then uses the cached version.
        Supports INT8 quantization for low-spec hardware.

        Raises:
            ModelLoadError: If the model fails to download or load.
        """
        if self._state == DetectorState.READY:
            logger.debug("GUIrillaDetector already loaded")
            return

        self._state = DetectorState.LOADING
        logger.info(f"Loading GUIrilla model: {self._model_name}...")

        try:
            self._ensure_imports()

            from transformers import AutoProcessor, AutoModelForCausalLM

            # Ensure cache directory exists
            cache_path = Path(self._cache_dir)
            cache_path.mkdir(parents=True, exist_ok=True)

            # Determine device
            device = self._device
            if device == "cuda" and not self._torch.cuda.is_available():
                device = "cpu"
                logger.warning("CUDA not available, falling back to CPU")

            # Load processor
            self._processor = AutoProcessor.from_pretrained(
                self._model_name,
                cache_dir=str(cache_path),
                trust_remote_code=True,
            )

            # Load model with quantization
            model_kwargs = {
                "cache_dir": str(cache_path),
                "trust_remote_code": True,
            }

            if self._quantization == "int8" and device == "cpu":
                model_kwargs["torch_dtype"] = self._torch.float32
                # INT8 quantization via bitsandbytes if available
                try:
                    model_kwargs["load_in_8bit"] = True
                    logger.info("Loading model with INT8 quantization")
                except Exception:
                    logger.warning("INT8 quantization not available, using FP32")
            elif self._quantization == "fp16":
                model_kwargs["torch_dtype"] = self._torch.float16

            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_name,
                **model_kwargs,
            )

            if not model_kwargs.get("load_in_8bit"):
                self._model = self._model.to(device)

            self._model.eval()
            self._device = device

            self._state = DetectorState.READY
            logger.info(
                f"GUIrilla model loaded | device={device} | "
                f"quantization={self._quantization}"
            )

        except Exception as exc:
            self._state = DetectorState.ERROR
            raise ModelLoadError(
                f"Failed to load GUIrilla model: {exc}",
                context={"model": self._model_name},
            )

    def unload(self) -> None:
        """Release model and free GPU/CPU memory."""
        if self._model is not None:
            del self._model
            self._model = None

        if self._processor is not None:
            del self._processor
            self._processor = None

        # Free CUDA memory
        if self._torch is not None and self._torch.cuda.is_available():
            self._torch.cuda.empty_cache()

        self._state = DetectorState.UNLOADED
        logger.info("GUIrilla model unloaded")

    def detect(
        self,
        window_title: Optional[str] = None,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> DetectionResult:
        """
        Detect UI elements by taking a screenshot and running inference.

        Args:
            window_title: Title of the target window (used for logging).
            region: (x, y, w, h) region to capture.

        Returns:
            DetectionResult with detected UIElements.
        """
        if self._state != DetectorState.READY:
            return DetectionResult(
                success=False,
                error_message="GUIrilla model not loaded",
                source=DetectionSource.GUIRILLA,
            )

        self._state = DetectorState.DETECTING
        start = time.time()

        try:
            # Capture screenshot
            screenshot = self._capture_screenshot(region)
            if screenshot is None:
                self._state = DetectorState.READY
                return DetectionResult(
                    success=False,
                    error_message="Failed to capture screenshot",
                    source=DetectionSource.GUIRILLA,
                )

            # Resize for model input
            screenshot = self._resize_image(screenshot)

            # Run inference
            elements = self._run_inference(screenshot, region)

            elapsed = (time.time() - start) * 1000
            self._detection_count += 1
            self._total_time_ms += elapsed
            self._state = DetectorState.READY

            result = DetectionResult(
                elements=elements[:self._max_detections],
                source=DetectionSource.GUIRILLA,
                success=True,
                detection_time_ms=elapsed,
                window_title=window_title or "",
            )

            logger.info(
                f"GUIrilla detected {result.count} elements in "
                f"{elapsed:.1f}ms"
            )
            return result

        except Exception as exc:
            self._error_count += 1
            self._state = DetectorState.READY
            elapsed = (time.time() - start) * 1000

            logger.error(f"GUIrilla detection failed: {exc}")
            return DetectionResult(
                success=False,
                error_message=str(exc),
                source=DetectionSource.GUIRILLA,
                detection_time_ms=elapsed,
            )

    def detect_element(
        self,
        query: str,
        window_title: Optional[str] = None,
    ) -> Optional[UIElement]:
        """
        Find a specific UI element by name/description.

        Uses the model's open-vocabulary capability to find elements
        matching the natural-language query.

        Args:
            query: Description of the element (e.g., "Save button").
            window_title: Window to search in.

        Returns:
            Best matching UIElement or None.
        """
        result = self.detect(window_title=window_title)
        if not result.success or result.count == 0:
            return None

        # Search by name match
        match = result.find_by_name(query)
        if match is not None:
            return match

        # If no exact match, return highest confidence element
        result.sort_by_confidence()
        return result.elements[0] if result.elements else None

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    def _capture_screenshot(
        self, region: Optional[Tuple[int, int, int, int]] = None
    ) -> Optional[Any]:
        """Capture a screenshot."""
        try:
            ImageGrab = self._pil["ImageGrab"]

            if region:
                x, y, w, h = region
                img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            else:
                img = ImageGrab.grab()

            return img
        except Exception as exc:
            logger.error(f"Screenshot capture failed: {exc}")
            return None

    def _resize_image(self, image: Any) -> Any:
        """
        Resize image to fit within max_image_size while preserving
        aspect ratio.
        """
        w, h = image.size
        max_dim = max(w, h)

        if max_dim <= self._max_image_size:
            return image

        scale = self._max_image_size / max_dim
        new_w = int(w * scale)
        new_h = int(h * scale)

        Image = self._pil["Image"]
        return image.resize((new_w, new_h), Image.LANCZOS)

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def _run_inference(
        self,
        image: Any,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> List[UIElement]:
        """
        Run the GUIrilla model on a screenshot.

        Uses the Florence 2 object detection task to find UI elements.

        Args:
            image: PIL Image of the screen/region.
            region: Original region offset for coordinate adjustment.

        Returns:
            List of detected UIElements.
        """
        if self._model is None or self._processor is None:
            return []

        try:
            # Florence 2 object detection prompt
            task_prompt = "<OD>"

            inputs = self._processor(
                text=task_prompt,
                images=image,
                return_tensors="pt",
            )

            # Move inputs to device
            inputs = {
                k: v.to(self._device) if hasattr(v, "to") else v
                for k, v in inputs.items()
            }

            # Run inference
            with self._torch.no_grad():
                generated_ids = self._model.generate(
                    input_ids=inputs.get("input_ids"),
                    pixel_values=inputs.get("pixel_values"),
                    max_new_tokens=1024,
                    num_beams=3,
                    do_sample=False,
                )

            # Decode output
            generated_text = self._processor.batch_decode(
                generated_ids, skip_special_tokens=False
            )[0]

            # Parse the model output into elements
            elements = self._parse_model_output(
                generated_text, image.size, region
            )

            return elements

        except Exception as exc:
            logger.error(f"GUIrilla inference error: {exc}")
            return []

    def _parse_model_output(
        self,
        output_text: str,
        image_size: Tuple[int, int],
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> List[UIElement]:
        """
        Parse Florence 2 model output into UIElement objects.

        The output format is typically:
            <OD> label <loc_x1><loc_y1><loc_x2><loc_y2> ...

        Coordinates are normalised to 0-999 range.

        Args:
            output_text: Raw model output string.
            image_size: (width, height) of the input image.
            region: Offset for region-based detection.

        Returns:
            List of UIElements parsed from the output.
        """
        elements = []
        img_w, img_h = image_size
        offset_x = region[0] if region else 0
        offset_y = region[1] if region else 0

        try:
            # Use the processor's post-processing if available
            if hasattr(self._processor, "post_process_generation"):
                parsed = self._processor.post_process_generation(
                    output_text,
                    task="<OD>",
                    image_size=image_size,
                )

                if "<OD>" in parsed:
                    od_result = parsed["<OD>"]
                    bboxes = od_result.get("bboxes", [])
                    labels = od_result.get("labels", [])

                    for i, (bbox, label) in enumerate(zip(bboxes, labels)):
                        if len(bbox) != 4:
                            continue

                        x1, y1, x2, y2 = [int(v) for v in bbox]
                        x1 += offset_x
                        y1 += offset_y
                        x2 += offset_x
                        y2 += offset_y

                        w = x2 - x1
                        h = y2 - y1

                        if w <= 0 or h <= 0:
                            continue

                        element_type = self._classify_label(label)

                        # Confidence decreases with detection index
                        confidence = max(
                            0.5,
                            0.95 - (i * 0.05),
                        )

                        element = UIElement(
                            name=label.strip(),
                            element_type=element_type,
                            bbox=BoundingBox(x=x1, y=y1, width=w, height=h),
                            confidence=confidence,
                            source=DetectionSource.GUIRILLA,
                        )
                        elements.append(element)

            else:
                # Fallback: basic text parsing
                elements = self._parse_output_text_fallback(
                    output_text, img_w, img_h, offset_x, offset_y
                )

        except Exception as exc:
            logger.error(f"Error parsing GUIrilla output: {exc}")

        # Filter by confidence
        elements = [
            e for e in elements if e.confidence >= self._confidence_threshold
        ]

        return elements

    def _parse_output_text_fallback(
        self,
        text: str,
        img_w: int,
        img_h: int,
        offset_x: int,
        offset_y: int,
    ) -> List[UIElement]:
        """
        Fallback parser for model output when post_process_generation
        is not available.

        Looks for patterns like: label<loc_XXX><loc_YYY><loc_XXX><loc_YYY>
        """
        import re

        elements = []
        # Pattern: text followed by 4 location tokens
        pattern = r"([^<]+)<loc_(\d+)><loc_(\d+)><loc_(\d+)><loc_(\d+)>"
        matches = re.findall(pattern, text)

        for i, match in enumerate(matches):
            label, x1_n, y1_n, x2_n, y2_n = match

            # Convert from 0-999 normalised to pixel coordinates
            x1 = int(int(x1_n) / 999 * img_w) + offset_x
            y1 = int(int(y1_n) / 999 * img_h) + offset_y
            x2 = int(int(x2_n) / 999 * img_w) + offset_x
            y2 = int(int(y2_n) / 999 * img_h) + offset_y

            w = x2 - x1
            h = y2 - y1

            if w <= 0 or h <= 0:
                continue

            element_type = self._classify_label(label.strip())
            confidence = max(0.5, 0.95 - (i * 0.05))

            elements.append(UIElement(
                name=label.strip(),
                element_type=element_type,
                bbox=BoundingBox(x=x1, y=y1, width=w, height=h),
                confidence=confidence,
                source=DetectionSource.GUIRILLA,
            ))

        return elements

    def _classify_label(self, label: str) -> ElementType:
        """
        Classify a detected label into an ElementType.

        Args:
            label: Text label from the model output.

        Returns:
            Best-guess ElementType.
        """
        lbl = label.lower()

        if "button" in lbl or "btn" in lbl:
            return ElementType.BUTTON
        elif "text" in lbl and ("field" in lbl or "input" in lbl or "box" in lbl):
            return ElementType.TEXT_FIELD
        elif "input" in lbl or "edit" in lbl:
            return ElementType.TEXT_FIELD
        elif "checkbox" in lbl or "check box" in lbl:
            return ElementType.CHECKBOX
        elif "radio" in lbl:
            return ElementType.RADIO_BUTTON
        elif "dropdown" in lbl or "combo" in lbl or "select" in lbl:
            return ElementType.DROPDOWN
        elif "menu" in lbl:
            if "item" in lbl:
                return ElementType.MENU_ITEM
            return ElementType.MENU
        elif "tab" in lbl:
            return ElementType.TAB
        elif "link" in lbl or "hyperlink" in lbl:
            return ElementType.LINK
        elif "icon" in lbl:
            return ElementType.ICON
        elif "image" in lbl or "img" in lbl or "picture" in lbl:
            return ElementType.IMAGE
        elif "label" in lbl or "text" in lbl:
            return ElementType.LABEL
        elif "scroll" in lbl:
            return ElementType.SCROLLBAR
        elif "slider" in lbl:
            return ElementType.SLIDER
        elif "toolbar" in lbl:
            return ElementType.TOOLBAR
        elif "window" in lbl or "dialog" in lbl:
            return ElementType.WINDOW
        else:
            return ElementType.UNKNOWN

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_model_info(self) -> Dict:
        """Return model information."""
        return {
            "model_name": self._model_name,
            "quantization": self._quantization,
            "device": self._device,
            "loaded": self._model is not None,
            "max_image_size": self._max_image_size,
            "confidence_threshold": self._confidence_threshold,
        }


__all__ = ["GUIrillaDetector"]
