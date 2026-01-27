"""Background generators."""
from PIL import Image
import numpy as np
import colorsys


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def create_solid_background(width: int, height: int, color: str) -> Image.Image:
    """Create solid color background."""
    rgb = hex_to_rgb(color)
    return Image.new('RGB', (width, height), rgb)


def create_gradient_background(width: int, height: int, colors: str) -> Image.Image:
    """Create vertical gradient background from two colors."""
    color1, color2 = colors.split(',')
    rgb1 = hex_to_rgb(color1.strip())
    rgb2 = hex_to_rgb(color2.strip())

    img = Image.new('RGB', (width, height))
    pixels = img.load()

    for y in range(height):
        ratio = y / height
        r = int(rgb1[0] * (1 - ratio) + rgb2[0] * ratio)
        g = int(rgb1[1] * (1 - ratio) + rgb2[1] * ratio)
        b = int(rgb1[2] * (1 - ratio) + rgb2[2] * ratio)
        for x in range(width):
            pixels[x, y] = (r, g, b)

    return img


def create_image_background(width: int, height: int, path: str) -> Image.Image:
    """Load image and crop/resize to fit target dimensions (no distortion)."""
    img = Image.open(path).convert('RGB')

    # Calculate aspect ratios
    target_ratio = width / height
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        # Image is wider - crop horizontally
        new_width = int(img.height * target_ratio)
        left = (img.width - new_width) // 2
        img = img.crop((left, 0, left + new_width, img.height))
    elif img_ratio < target_ratio:
        # Image is taller - crop vertically
        new_height = int(img.width / target_ratio)
        top = (img.height - new_height) // 2
        img = img.crop((0, top, img.width, top + new_height))

    # Resize to exact dimensions
    return img.resize((width, height), Image.Resampling.LANCZOS)


def get_background(width: int, height: int, bg_type: str, bg_value: str) -> Image.Image:
    """Get background image based on type."""
    if bg_type == 'gradient':
        return create_gradient_background(width, height, bg_value)
    elif bg_type == 'image':
        return create_image_background(width, height, bg_value)
    else:  # color (default)
        return create_solid_background(width, height, bg_value)


def get_luminance(r: int, g: int, b: int) -> float:
    """Calculate relative luminance (0-1)."""
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB to hex color."""
    return f'#{r:02x}{g:02x}{b:02x}'


def calculate_auto_subtitle_color(background: Image.Image) -> str:
    """
    Calculate optimal subtitle color based on background bottom region.
    Subtitles appear at bottom, so we analyze that area.
    Returns white or black based on luminance for best readability.
    """
    width, height = background.size

    # Sample bottom 20% where subtitles appear
    bottom_region = background.crop((0, int(height * 0.8), width, height))
    sample = bottom_region.resize((100, 20), Image.Resampling.NEAREST)
    pixels = np.array(sample).reshape(-1, 3)

    # Calculate average luminance
    avg_luminance = np.mean([get_luminance(p[0], p[1], p[2]) for p in pixels])

    # Simple: white text on dark, black text on light
    # But for video, white with dark bg box usually works best
    # Return a slightly off-white or off-black for softer look
    if avg_luminance < 0.5:
        return '#ffffff'  # White on dark
    else:
        return '#1a1a1a'  # Near-black on light


def calculate_auto_title_color(background: Image.Image) -> str:
    """
    Calculate optimal title color based on background center region.
    Title appears centered, so we analyze the center area.
    Returns white or near-black based on luminance for best readability.
    """
    width, height = background.size

    # Sample center 60% where title appears
    margin_x = int(width * 0.2)
    margin_y = int(height * 0.2)
    center_region = background.crop((margin_x, margin_y, width - margin_x, height - margin_y))
    sample = center_region.resize((100, 100), Image.Resampling.NEAREST)
    pixels = np.array(sample).reshape(-1, 3)

    # Calculate average luminance
    avg_luminance = np.mean([get_luminance(p[0], p[1], p[2]) for p in pixels])

    # White text on dark, near-black on light
    if avg_luminance < 0.5:
        return '#ffffff'  # White on dark
    else:
        return '#1a1a1a'  # Near-black on light


def calculate_auto_wave_color(background: Image.Image) -> str:
    """
    Calculate optimal wave color based on background.

    Strategy:
    1. Sample center 40% of image (where visualizer appears)
    2. Extract dominant colors via k-means clustering
    3. Calculate center region luminance
    4. Pick color with best contrast, boost saturation
    """
    width, height = background.size

    # Crop center 40% region
    margin_x = int(width * 0.3)
    margin_y = int(height * 0.3)
    center_region = background.crop((margin_x, margin_y, width - margin_x, height - margin_y))

    # Resize for faster processing
    sample = center_region.resize((100, 100), Image.Resampling.NEAREST)
    pixels = np.array(sample).reshape(-1, 3)

    # Calculate average luminance of center
    avg_luminance = np.mean([get_luminance(p[0], p[1], p[2]) for p in pixels])

    # Simple k-means clustering (3 clusters)
    from random import sample as random_sample
    n_clusters = 3

    # Initialize centroids randomly
    indices = random_sample(range(len(pixels)), min(n_clusters, len(pixels)))
    centroids = pixels[indices].astype(float)

    # Run k-means for 10 iterations
    for _ in range(10):
        # Assign pixels to nearest centroid
        distances = np.sqrt(((pixels[:, np.newaxis] - centroids) ** 2).sum(axis=2))
        labels = distances.argmin(axis=1)

        # Update centroids
        for i in range(n_clusters):
            mask = labels == i
            if mask.sum() > 0:
                centroids[i] = pixels[mask].mean(axis=0)

    # Find color with best contrast against center luminance
    best_color = None
    best_contrast = 0

    for centroid in centroids:
        r, g, b = int(centroid[0]), int(centroid[1]), int(centroid[2])
        color_luminance = get_luminance(r, g, b)
        contrast = abs(color_luminance - avg_luminance)

        # Convert to HSV to check/boost saturation
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)

        # Prefer more saturated colors
        score = contrast + s * 0.3

        if score > best_contrast:
            best_contrast = score
            # Boost saturation and adjust value for visibility
            new_s = max(0.7, s)  # Minimum 70% saturation
            new_v = 0.9 if avg_luminance < 0.5 else 0.7  # Bright on dark, darker on bright
            best_color = (h, new_s, new_v)

    # If no good contrast found, use complementary approach
    if best_contrast < 0.2:
        # Dark background -> bright cyan/green, Light background -> deep purple/blue
        if avg_luminance < 0.5:
            return '#00ff88'  # Bright green
        else:
            return '#6b21a8'  # Deep purple

    # Convert back to RGB
    r, g, b = colorsys.hsv_to_rgb(best_color[0], best_color[1], best_color[2])
    return rgb_to_hex(int(r * 255), int(g * 255), int(b * 255))
